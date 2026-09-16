"""Position-based filling of server-reanalyzed HWPX templates."""
import copy
import hashlib
import io
import zipfile
from collections import Counter

from lxml import etree

from hwpx.package import read_hwpx
from hwpx.template import analyze_a, parse_xml, target


def _selected(edits):
    selected = [e for e in (edits or []) if e.get('selected') is True and e.get('value') not in (None, '')]
    ids = Counter(e.get('fieldId') for e in selected)
    if any(count > 1 for count in ids.values()):
        raise ValueError('Conflicting edits for the same field')
    for e in selected:
        if not isinstance(e.get('value'), str):
            raise ValueError('Field value must be a string')
    return selected


def _expected(raw, digest, edits):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('A hash mismatch')
    pkg = read_hwpx(raw)
    analysis = analyze_a(raw)
    fields = {f['field_id']: f for f in analysis['fields']}
    selected = _selected(edits)
    roots, operations, occupied = {}, [], set()
    for e in selected:
        f = fields.get(e['fieldId'])
        if not f or not f['editable']:
            raise ValueError('Unknown or protected field')
        loc = f['location']
        sec = loc['section']
        if sec not in roots:
            roots[sec] = parse_xml(pkg.get_bytes(sec))
        node = target(roots[sec], f, create=True)
        offset = loc.get('insert_offset')
        address = (sec, roots[sec].getroottree().getpath(node), offset)
        if address in occupied:
            raise ValueError('Overlapping edits')
        occupied.add(address)
        if offset is not None and not 0 <= offset <= len(node.text or ''):
            raise ValueError('Invalid insertion offset')
        operations.append((offset if offset is not None else -1, node, e['value'], f['rule']))
    # Resolve every position before mutation and insert from right to left.
    for offset, node, value, rule in sorted(operations, key=lambda item: item[0], reverse=True):
        if rule == 'rule4':
            text = node.text or ''
            node.text = text[:offset] + value + text[offset:]
        else:
            node.text = value
    return pkg, roots, selected


def _check_evidence(selected, proposals, blocks):
    def get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    source = {get(b, 'blockId'): get(b, 'text', get(b, 'originalText', '')) for b in (blocks or [])}
    for e in selected:
        if e.get('origin') in ('manual', 'user'):
            continue
        candidates = [p for p in (proposals or []) if p.get('fieldId') == e['fieldId'] and p.get('value') == e['value']]
        valid = False
        for p in candidates:
            ids, quote = p.get('sourceBlockIds') or [], p.get('evidenceQuote') or ''
            if ids and all(i in source for i in ids) and isinstance(quote, str) and quote:
                valid = any(quote in source[i] and e['value'] in quote for i in ids)
            if valid:
                break
        if not valid:
            raise ValueError('Automatic value requires matching source evidence; review as a manual edit if transformed')


def validate_native(result, original, digest, edits):
    errors = []
    try:
        original_pkg, expected, selected = _expected(original, digest, edits)
        out = read_hwpx(result)
        if original_pkg.item_paths != out.item_paths:
            raise ValueError('ZIP entries changed')
        for name in original_pkg.item_paths:
            actual = out.get_bytes(name)
            if name in expected:
                if etree.tostring(parse_xml(actual), method='c14n') != etree.tostring(expected[name], method='c14n'):
                    raise ValueError('Unexpected structure or value change: ' + name)
            elif actual != original_pkg.get_bytes(name):
                raise ValueError('Protected entry changed: ' + name)
    except Exception as exc:
        errors.append({'type': 'output-validation', 'message': str(exc), 'severity': 'error'})
    return {'passed': not errors, 'errors': errors, 'warnings': [],
            'checks': [] if errors else [{'name': 'selected-values-and-protected-structure', 'status': 'passed'}],
            'report': {'inputHash': hashlib.sha256(original).hexdigest(), 'outputHash': hashlib.sha256(result).hexdigest(),
                       'visualValidation': 'not-run'}}


def read_field_value(original, result, field_id, edits=None):
    analysis = analyze_a(original)
    f = next((f for f in analysis['fields'] if f['field_id'] == field_id), None)
    if not f or not f['editable']:
        raise ValueError('Unknown or protected field')
    sec = f['location']['section']
    old_root = parse_xml(read_hwpx(original).get_bytes(sec))
    old_node = target(old_root, f, create=True)
    node_path = old_root.getroottree().getpath(old_node)
    new_root = parse_xml(read_hwpx(result).get_bytes(sec))
    nodes = new_root.xpath(node_path, namespaces={k: v for k, v in old_root.nsmap.items() if k})
    if not nodes:
        return ''
    actual = nodes[0].text or ''
    offset = f['location'].get('insert_offset')
    if offset is None:
        return actual
    if edits is not None:
        selected = {e['fieldId']: e['value'] for e in _selected(edits)}
        shift = 0
        for other in analysis['fields']:
            loc = other['location']
            if other['field_id'] in selected and loc.get('insert_offset', -1) < offset and all(loc.get(k) == f['location'].get(k) for k in ('section', 'table_path', 'row', 'col', 'paragraph_index', 'run_index')):
                shift += len(selected[other['field_id']])
        if field_id not in selected:
            return ''
        start = offset + shift
        return actual[start:start + len(selected[field_id])]
    before = old_node.text or ''
    prefix, suffix = before[:offset], before[offset:]
    if not actual.startswith(prefix) or (suffix and not actual.endswith(suffix)):
        raise ValueError('Fixed inline label changed')
    return actual[len(prefix):len(actual)-len(suffix) if suffix else None]


def generate_native(raw, digest, edits, proposals=None, blocks=None):
    response = {'result_id': 'result-' + digest[:16], 'resultHash': None, 'resultBytes': None,
                'changedFields': [], 'warnings': [], 'errors': [], 'unchanged': False, 'summary': None}
    try:
        pkg, roots, selected = _expected(raw, digest, edits)
        _check_evidence(selected, proposals, blocks)
        if not selected:
            response.update(resultHash=hashlib.sha256(raw).hexdigest(), resultBytes=raw, unchanged=True)
            return response
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as zin, zipfile.ZipFile(buf, 'w') as zout:
            zout.comment = zin.comment
            for info in zin.infolist():
                data = pkg.get_bytes(info.filename)
                if info.filename in roots:
                    data = etree.tostring(roots[info.filename], encoding='UTF-8', xml_declaration=True)
                zout.writestr(copy.copy(info), data)
        result = buf.getvalue()
        verified = validate_native(result, raw, digest, edits)
        if not verified['passed']:
            response['errors'] = verified['errors']
            return response
        response.update(resultHash=hashlib.sha256(result).hexdigest(), resultBytes=result,
                        changedFields=[{k: e.get(k) for k in ('fieldId', 'value', 'origin', 'sourceBlockIds')} for e in selected])
        response['warnings'] = [{'type': 'layout-unverified', 'severity': 'warning',
                                 'message': '내용 증가에 따른 줄 배치와 페이지 이동은 한글에서 확인 필요'}]
    except Exception as exc:
        response['errors'] = [{'type': 'generation', 'message': str(exc), 'severity': 'error'}]
    return response

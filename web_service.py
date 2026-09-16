"""Stateless API adapter for the native HWPX fill engine."""
import base64
import binascii
import hashlib
from collections import Counter

from hwpx.analyze import analyze_a
from hwpx.errors import DomainError
from hwpx.fill import _check_evidence
from hwpx.generate import generate_result
from hwpx.package import read_hwpx
from hwpx.rules import connect_rules
from hwpx.source import extract_b
from hwpx.validate import validate_output
from hwpx.xml import read_xml
from solar.client import api_key, suggest

MAX_WIRE = 3_800_000
MAX_FILES = 2_500_000


class APIError(Exception):
    def __init__(self, code, message, status=400, details=None):
        self.code, self.message, self.status, self.details = code, message, status, details


def plain(value):
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return {k: plain(getattr(value, k)) for k in value.__slots__}


def decode_file(value):
    if not isinstance(value, dict) or not isinstance(value.get('base64'), str):
        raise APIError('INVALID_INPUT', 'base64 파일이 필요합니다')
    if len(value['base64']) > MAX_WIRE:
        raise APIError('SIZE_LIMIT', '파일 크기 제한을 초과했습니다', 413)
    try:
        raw = base64.b64decode(value['base64'], validate=True)
    except (ValueError, binascii.Error):
        raise APIError('INVALID_BASE64', '파일 인코딩이 올바르지 않습니다')
    if len(raw) > MAX_FILES:
        raise APIError('SIZE_LIMIT', '파일 크기 제한을 초과했습니다', 413)
    return raw


def source_input(value, a_size=0):
    if not isinstance(value, dict) or value.get('kind') not in ('hwpx', 'txt', 'md'):
        raise APIError('INVALID_SOURCE', 'B는 HWPX, TXT, Markdown 또는 텍스트여야 합니다')
    if 'text' in value:
        if value['kind'] == 'hwpx' or not isinstance(value['text'], str):
            raise APIError('INVALID_SOURCE', '텍스트 형식이 올바르지 않습니다')
        raw = value['text'].encode('utf-8')
    else:
        raw = decode_file(value)
    if len(raw) + a_size > MAX_FILES:
        raise APIError('SIZE_LIMIT', 'A와 B 합계는 2,500,000바이트 이하여야 합니다', 413)
    if not raw:
        raise APIError('EMPTY_SOURCE', 'B 내용이 비어 있습니다')
    return extract_b(raw, kind=value['kind'])


def analysis_input(payload):
    raw = decode_file(payload.get('a'))
    package = read_hwpx(raw)
    if not package.has_path('Contents/content.hpf'):
        raise APIError('UNSUPPORTED_FORMAT', '한글에서 저장한 HWPX 양식을 사용해 주세요')
    digest = hashlib.sha256(raw).hexdigest()
    return raw, digest, analyze_a(read_xml(package), a_bytes=raw, a_sha256=digest)


def checked_suggestions(fields, blocks, proposals):
    allowed = {f['fieldId'] for f in fields if f.get('editable') is True}
    counts = Counter(p.get('fieldId') for p in proposals if isinstance(p, dict) and isinstance(p.get('fieldId'), str))
    accepted, warnings = [], []
    for p in proposals:
        try:
            if not isinstance(p, dict) or p.get('fieldId') not in allowed or counts[p['fieldId']] != 1:
                raise ValueError('unknown or duplicate field')
            if not isinstance(p.get('value'), str) or not p['value'] or not isinstance(p.get('sourceBlockIds'), list):
                raise ValueError('invalid proposal')
            _check_evidence([{'fieldId': p['fieldId'], 'value': p['value'], 'origin': 'solar'}], [p], blocks)
            accepted.append({k: p.get(k) for k in ('fieldId', 'value', 'sourceBlockIds', 'evidenceQuote', 'reason')} | {'needsReview': True, 'origin': 'rule' if p.get('origin') == 'rule' else 'solar'})
        except (ValueError, TypeError, KeyError):
            warnings.append('ID·원문 근거·중복 검사에 실패한 제안을 제외했습니다')
    return accepted, warnings


def dispatch(payload):
    if not isinstance(payload, dict):
        raise APIError('INVALID_INPUT', 'JSON 객체가 필요합니다')
    action = payload.get('action')
    response = {'action': action, 'status': 'ok', 'engine': 'hwpx'}
    if action == 'status':
        return response | {'version': '1.1.0', 'solarConfigured': bool(api_key())}
    if action == 'suggest':
        fields, blocks = payload.get('fields'), payload.get('blocks')
        if not isinstance(fields, list) or not isinstance(blocks, list):
            raise APIError('INVALID_INPUT', '입력란과 원문 블록 목록이 필요합니다')
        if any(not isinstance(f, dict) or not isinstance(f.get('fieldId'), str) for f in fields) or any(
            not isinstance(b, dict) or not isinstance(b.get('blockId'), str) or not isinstance(b.get('text'), str) for b in blocks):
            raise APIError('INVALID_INPUT', '입력란 또는 원문 형식이 잘못되었습니다')
        try:
            proposals, warnings = suggest([f for f in fields if f.get('editable') is True], blocks)
        except Exception:
            proposals, warnings = [], ['Solar 호출 실패 수동 입력은 가능합니다']
        proposals, rejected = checked_suggestions(fields, blocks, proposals)
        return response | {'suggestions': proposals, 'warnings': warnings + rejected}
    if action not in ('analyze', 'generate'):
        raise APIError('INVALID_ACTION', '지원하지 않는 요청입니다')
    raw, digest, analysis = analysis_input(payload)
    if action == 'analyze':
        source = source_input(payload.get('b'), len(raw))
        rules = connect_rules(analysis.fields, source.blocks, None, digest)['results']
        proposals, warnings = checked_suggestions(analysis.fields, source.blocks, [p | {'origin': 'rule'} for p in rules if p.get('status') == 'suggested'])
        return response | {'analysis': plain(analysis), 'source': plain(source), 'suggestions': proposals,
                           'warnings': analysis.warnings + warnings, 'ruleResults': rules}
    if payload.get('aHash') != digest:
        raise APIError('HASH_MISMATCH', '분석한 A와 생성할 A가 다릅니다 다시 분석해 주세요', 409)
    edits = payload.get('edits')
    if not isinstance(edits, list) or any(not isinstance(e, dict) or not isinstance(e.get('fieldId'), str)
        or not isinstance(e.get('value'), str) or not isinstance(e.get('selected'), bool)
        or e.get('origin') not in ('manual', 'user', 'rule', 'solar') for e in edits):
        raise APIError('INVALID_EDITS', '편집 목록의 형식이 잘못되었습니다')
    source = source_input(payload['b'], len(raw)) if payload.get('b') else None
    proposals = payload.get('suggestions', [])
    if not isinstance(proposals, list) or any(not isinstance(p, dict) for p in proposals):
        raise APIError('INVALID_INPUT', '제안 목록의 형식이 잘못되었습니다')
    # Source blocks and XML positions received from the browser are never used for generation
    proposals, _ = checked_suggestions(analysis.fields, source.blocks if source else [], proposals)
    result = generate_result(raw, digest, analysis.fields, edits, proposals, source.blocks if source else [], None, None)
    if result['errors'] or result['resultBytes'] is None:
        raise APIError('GENERATION_FAILED', '선택한 입력값 또는 원문 근거를 확인해 주세요', 422, {'errors': result['errors']})
    report = validate_output(result['resultBytes'], raw, analysis.fields, edits, digest)
    if not report['passed']:
        raise APIError('VALIDATION_FAILED', '구조 검증에 실패해 결과를 제공하지 않습니다', 422, report)
    if len(result['resultBytes']) > MAX_FILES:
        raise APIError('SIZE_LIMIT', '결과 파일 크기 제한을 초과했습니다', 413)
    result['resultBytes'] = base64.b64encode(result['resultBytes']).decode('ascii')
    result['fileName'] = '작성본.hwpx'
    return response | {'result': result, 'report': report}

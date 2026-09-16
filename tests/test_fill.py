"""Real-template fill regression through the public bytes contract.

Checks hash, invalid/protected fields, exact cell/inline placement, multiple
insertions, special characters, result structure and unchanged ZIP entries.
"""
import hashlib
import io
from pathlib import Path
import zipfile

from lxml import etree
import pytest

from hwpx.analyze import analyze_a
from hwpx.generate import generate_result
from hwpx.validate import validate_output
from hwpx.xml import read_xml
from hwpx.template import analyze_a as analyze_positions

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph'}


@pytest.fixture(scope='module')
def document():
    raw = (Path(__file__).parent / 'fixtures/A.hwpx').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, digest, analyze_a(read_xml(raw), a_bytes=raw, a_sha256=digest)


def field_by_label(analysis, label):
    matches = [f for f in analysis.fields if ''.join(f['label'].split()) == ''.join(label.split()) and f['editable']]
    assert matches, label
    return matches[0]


def generate(document, pairs, digest=None):
    raw, actual_hash, a = document
    edits = [{'fieldId': fid, 'value': value, 'selected': True, 'origin': 'manual'} for fid, value in pairs]
    result = generate_result(raw, digest or actual_hash, a.fields, edits, None, None, None, None)
    return result, edits


def text_at(raw, field):
    loc = field['location']
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        root = etree.fromstring(archive.read(loc['section']))
    table = root.findall('.//hp:tbl', NS)[loc['table_path'][0]]
    cells = [c for c in table.findall('hp:tr/hp:tc', NS)
             if c.find('hp:cellAddr', NS).get('rowAddr') == str(loc['row'])
             and c.find('hp:cellAddr', NS).get('colAddr') == str(loc['col'])]
    assert len(cells) == 1
    if field['rule'] == 'rule4':
        ps = cells[0].find('hp:subList', NS).findall('hp:p', NS)
        run = ps[loc['paragraph_index']].findall('hp:run', NS)[loc['run_index']]
        return run.find('hp:t', NS).text or ''
    return ''.join(t.text or '' for t in cells[0].findall('.//hp:t', NS))


def test_hash_mismatch(document):
    f = field_by_label(document[2], '단체명')
    result, _ = generate(document, [(f['fieldId'], '김하늘')], digest='0'*64)
    assert result['errors'] and result['resultBytes'] is None


def test_unknown_field(document):
    result, _ = generate(document, [('f-unknown', '값')])
    assert result['errors'] and not result['changedFields'] and result['resultBytes'] is None


def test_unit_placeholder_protected(document):
    raw, _, _ = document
    f = next(f for f in analyze_positions(raw)['fields'] if f['rule'] == 'rule3')
    result, _ = generate(document, [(f['field_id'], '99999')])
    assert result['errors'] and result['resultBytes'] is None


@pytest.mark.parametrize('label,value', [
    ('단 체 명', '늘배움 평생학교'), ('시 설 명', '늘배움 평생학교'),
    ('성 명', '김하늘'), ('전 화', '02-0000-1000'), ('팩 스', '02-0000-1001'),
    ('우편번호', '03000'), ('이메일', 'test@example.com'),
    ('성명', 'A & B < C > D'), ('우편번호', '<>&test'),
])
def test_fill_at_selected_position(document, label, value):
    raw, digest, a = document
    f = field_by_label(a, label)
    position = next(p for p in analyze_positions(raw)['fields'] if p['field_id'] == f['fieldId'])
    result, edits = generate(document, [(f['fieldId'], value)])
    assert not result['errors'], result['errors']
    expected = text_at(raw, position)
    if position['rule'] == 'rule4':
        offset = position['location']['insert_offset']
        expected = expected[:offset] + value + expected[offset:]
    else:
        expected = value
    assert text_at(result['resultBytes'], position) == expected
    assert validate_output(result['resultBytes'], raw, a.fields, edits, digest)['passed']
    assert result['resultHash'] == hashlib.sha256(result['resultBytes']).hexdigest()


def test_same_run_multi_insert(document):
    raw, _, a = document
    positions = analyze_positions(raw)['fields']
    targets = [next(p for p in positions if p['label'] == label) for label in ('상근직원수', '회원수')]
    for key in ('section', 'table_path', 'row', 'col', 'paragraph_index', 'run_index'):
        assert targets[0]['location'][key] == targets[1]['location'][key]
    values = ['5', '100']
    result, _ = generate(document, [(p['field_id'], v) for p, v in zip(targets, values)])
    assert not result['errors']
    expected = text_at(raw, targets[0])
    for p, value in sorted(zip(targets, values), key=lambda pair: pair[0]['location']['insert_offset'], reverse=True):
        offset = p['location']['insert_offset']
        expected = expected[:offset] + value + expected[offset:]
    assert text_at(result['resultBytes'], targets[0]) == expected


def test_sample_structure_and_untouched_entries(document):
    raw, digest, a = document
    pairs = [(field_by_label(a, label)['fieldId'], value) for label, value in
             [('단체명', '늘배움'), ('시설명', '학교'), ('성명', '김하늘'), ('전화', '02-0000'), ('팩스', '02-0001'), ('우편번호', '03000'), ('이메일', 'test@example.com')]]
    result, edits = generate(document, pairs)
    assert not result['errors']
    assert {x['fieldId'] for x in result['changedFields']} == {fid for fid, _ in pairs}
    with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(io.BytesIO(result['resultBytes'])) as filled:
        assert filled.namelist() == original.namelist()
        assert filled.infolist()[0].filename == 'mimetype'
        assert filled.infolist()[0].compress_type == zipfile.ZIP_STORED
        assert filled.testzip() is None
        for name in original.namelist():
            if name == 'Contents/section0.xml':
                etree.fromstring(filled.read(name))
            else:
                assert filled.read(name) == original.read(name), name
    assert validate_output(result['resultBytes'], raw, a.fields, edits, digest)['passed']

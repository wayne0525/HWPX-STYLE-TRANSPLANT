import hashlib
import io
import unittest
import zipfile
from xml.etree import ElementTree as ET

from hwpx.analyze import analyze_a
from hwpx.generate import generate_result
from hwpx.xml import read_xml

HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
OPF = 'http://www.idpf.org/2007/opf/'


def document():
    cell = lambda col, text: f'<hp:tc><hp:cellAddr colAddr="{col}" rowAddr="0"/><hp:cellSpan colSpan="1" rowSpan="1"/><hp:subList><hp:p id="1"><hp:run charPrIDRef="0"><hp:t>{text}</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
    section = f'<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="{HP}"><hp:p><hp:run><hp:tbl rowCnt="1" colCnt="2"><hp:tr>{cell(0,"성명")}{cell(1,"")}</hp:tr></hp:tbl></hp:run></hp:p></hs:sec>'
    manifest = f'<opf:package xmlns:opf="{OPF}"><opf:manifest><opf:item id="s2" href="section2.xml"/><opf:item id="s0" href="section0.xml"/></opf:manifest><opf:spine><opf:itemref idref="s2"/><opf:itemref idref="s0"/></opf:spine></opf:package>'
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('mimetype', 'application/hwp+zip')
        z.writestr('Contents/content.hpf', manifest)
        z.writestr('Contents/section0.xml', section)
        z.writestr('Contents/section2.xml', section)
        z.writestr('BinData/preserve.bin', b'preserve')
    return b.getvalue()


class TestNativeEngine(unittest.TestCase):
    def setUp(self):
        self.raw = document()
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def analysis(self):
        return analyze_a(read_xml(self.raw), a_bytes=self.raw, a_sha256=self.digest)

    def generate(self, edits, fields=None, digest=None):
        return generate_result(self.raw, digest or self.digest, fields or self.analysis().fields, edits, None, None, None, None)

    def change_sections(self, change):
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.raw)) as zin, zipfile.ZipFile(buf, 'w') as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if 'section' in info.filename:
                    data = change(data.decode()).encode()
                zout.writestr(info, data)
        self.raw = buf.getvalue()
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def test_merged_label_uses_cell_span(self):
        self.change_sections(lambda s: s.replace('colAddr="1"', 'colAddr="2"').replace('colSpan="1"', 'colSpan="2"', 1))
        self.assertEqual(len(self.analysis().fields), 2)
        self.assertEqual(self.analysis().fields[0]['location']['column']['columnIndex'], 2)

    def test_inline_multiple_values_preserve_labels(self):
        from hwpx.fill import read_field_value
        self.change_sections(lambda s: s.replace('<hp:t></hp:t>', '<hp:t>직명 : (성명 : )</hp:t>'))
        fs = [f for f in self.analysis().fields if f['editable']]
        self.assertEqual(len(fs), 4)
        edits = [{'fieldId': f['fieldId'], 'value': '교장' if f['label'] == '직명' else '김하늘', 'selected': True, 'origin': 'manual'} for f in fs]
        r = self.generate(edits)
        self.assertFalse(r['errors'])
        for e in edits:
            self.assertEqual(read_field_value(self.raw, r['resultBytes'], e['fieldId'], edits), e['value'])

    def test_manifest_order_and_stable_ids(self):
        self.assertEqual(read_xml(self.raw).section_paths_in_order, ['Contents/section2.xml', 'Contents/section0.xml'])
        a = self.analysis()
        self.assertEqual(len(a.fields), 2)
        self.assertEqual(a.fields, self.analysis().fields)
        self.assertNotEqual(a.fields[0]['fieldId'], a.fields[1]['fieldId'])

    def test_empty_cell_selected_location_and_hash(self):
        f = self.analysis().fields[1]
        r = self.generate([{'fieldId': f['fieldId'], 'value': '김 & <하늘>', 'selected': True, 'origin': 'manual'}])
        self.assertFalse(r['errors'])
        out = r['resultBytes']
        self.assertEqual(r['resultHash'], hashlib.sha256(out).hexdigest())
        with zipfile.ZipFile(io.BytesIO(out)) as z, zipfile.ZipFile(io.BytesIO(self.raw)) as a:
            self.assertEqual(z.read('Contents/section2.xml'), a.read('Contents/section2.xml'))
            self.assertEqual(z.read('BinData/preserve.bin'), b'preserve')
            root = ET.fromstring(z.read('Contents/section0.xml'))
            self.assertEqual([n.text for n in root.iter('{'+HP+'}t')], ['성명', '김 & <하늘>'])

    def test_no_selection_is_byte_identical(self):
        self.assertEqual(self.generate([])['resultBytes'], self.raw)

    def test_hash_and_duplicate_rejected(self):
        f = self.analysis().fields[0]
        e = {'fieldId': f['fieldId'], 'value': '김', 'selected': True, 'origin': 'manual'}
        self.assertTrue(self.generate([e], digest='0'*64)['errors'])
        self.assertTrue(self.generate([e,e])['errors'])

    def test_client_location_cannot_redirect(self):
        import copy
        fs = copy.deepcopy(self.analysis().fields)
        fs[0]['location'] = fs[1]['location']
        r = self.generate([{'fieldId': fs[0]['fieldId'], 'value': '김', 'selected': True, 'origin': 'manual'}], fields=fs)
        self.assertFalse(r['errors'])
        with zipfile.ZipFile(io.BytesIO(r['resultBytes'])) as z:
            self.assertIn('김', z.read('Contents/section2.xml').decode())
            self.assertNotIn('김', z.read('Contents/section0.xml').decode())

    def test_automatic_without_evidence_rejected(self):
        f = self.analysis().fields[0]
        self.assertTrue(self.generate([{'fieldId': f['fieldId'], 'value': '김', 'selected': True, 'origin': 'solar'}])['errors'])

    def test_output_tamper_rejected(self):
        from hwpx.validate import validate_output
        f = self.analysis().fields[0]
        edits = [{'fieldId': f['fieldId'], 'value': '김', 'selected': True, 'origin': 'manual'}]
        result = self.generate(edits)['resultBytes']
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(result)) as zin, zipfile.ZipFile(buf, 'w') as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == 'Contents/section2.xml':
                    data = data.replace('성명'.encode(), '금액'.encode())
                zout.writestr(info, data)
        self.assertFalse(validate_output(buf.getvalue(), self.raw, self.analysis().fields, edits, self.digest)['passed'])

    def test_source_ids_and_automatic_fill(self):
        from hwpx.source import extract_b
        b = extract_b('성명: 김하늘\n주소: 서울', kind='txt')
        self.assertEqual(len(set(x.blockId for x in b.blocks)), 2)
        f = self.analysis().fields[0]
        p = {'fieldId': f['fieldId'], 'value': '김하늘', 'sourceBlockIds': [b.blocks[0].blockId], 'evidenceQuote': '성명: 김하늘'}
        e = dict(p, selected=True, origin='solar')
        r = generate_result(self.raw, self.digest, self.analysis().fields, [e], [p], b.blocks, None, None)
        self.assertFalse(r['errors'])

    def test_native_b_extraction(self):
        from hwpx.source import extract_b
        b = extract_b(self.raw, kind='hwpx')
        self.assertEqual([x.text for x in b.blocks if x.text.strip()], ['성명', '성명'])

    def test_native_gold_checks_position_and_wrong_value(self):
        from scripts.evaluate import evaluate_quality
        f = self.analysis().fields[0]
        edits = [{'fieldId': f['fieldId'], 'value': '김하늘', 'selected': True, 'origin': 'manual'}]
        gold = {x['fieldId']: ('김하늘' if x == f else None) for x in self.analysis().fields}
        ok = evaluate_quality(self.raw, self.digest, None, gold, edits, human_reviewed=True)
        self.assertTrue(ok['passed'])
        edits[0]['value'] = '다른사람'
        wrong = evaluate_quality(self.raw, self.digest, None, gold, edits, human_reviewed=True)
        self.assertFalse(wrong['passed'])
        self.assertEqual(wrong['metrics']['miswrite_count'], 1)

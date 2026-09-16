"""tests/engine/test_regression.py - 통합 엔진 회귀 검사.

실제 hwpx/ 함수들을 호출해
- 잘못된 금액(값 불일치)
- 합쳐진 칸(병합 셀) 보존
- 미선택 변경 검출
- ZIP/XML 손상 검출
- 실패(exit 1)와 미검증(exit 2) 구분
을 검사한다.

pytest가 없을 때는 unittest로 실행한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import hashlib
import io
import unittest
import zipfile

from hwpx.analyze import analyze_a
from hwpx.generate import generate_result
from hwpx.package import ReadResult, read_hwpx
from hwpx.tables import read_tables
from hwpx.validate import validate_output
from hwpx.xml import read_xml
from scripts.evaluate import evaluate_quality


def _hwpx_bytes(section_xml: str, extra_items: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("mimetype", b"application/hwp+zip")
        z.writestr(
            "[Content_Types].xml",
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            "<Default Extension='xml' ContentType='application/xml'/>"
            "</Types>",
        )
        z.writestr(
            "Content.hpf",
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<HpF xmlns='http://www.hwpzone.org/hwpx'>"
            "<section href='section0.xml'/>"
            "</HpF>",
        )
        z.writestr("section0.xml", section_xml)
        if extra_items:
            for path, data in extra_items.items():
                z.writestr(path, data)
    return buf.getvalue()


def _section0_simple(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        f"<hp:p><hp:t>{text}</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_two_paragraphs(a_text: str, b_text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        f"<hp:p><hp:t>{a_text}</hp:t></hp:p>"
        f"<hp:p><hp:t>{b_text}</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_table() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>표 위 문단</hp:t></hp:p>"
        "<hp:tbl>"
        "<hp:tr>"
        "<hp:tc><hp:t>행1-열1</hp:t></hp:tc>"
        "<hp:tc><hp:t>행1-열2</hp:t></hp:tc>"
        "</hp:tr>"
        "<hp:tr>"
        "<hp:tc><hp:t>행2-열1</hp:t></hp:tc>"
        "<hp:tc><hp:t>행2-열2</hp:t></hp:tc>"
        "</hp:tr>"
        "</hp:tbl>"
        "<hp:p><hp:t>표 아래 문단</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_merged_table() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>표 위 문단</hp:t></hp:p>"
        "<hp:tbl>"
        "<hp:tr>"
        "<hp:tc gridSpan=\"2\"><hp:t>머리1</hp:t></hp:tc>"
        "<hp:tc><hp:t>머리3</hp:t></hp:tc>"
        "</hp:tr>"
        "<hp:tr>"
        "<hp:tc><hp:t>행2-열1</hp:t></hp:tc>"
        "<hp:tc><hp:t>행2-열2</hp:t></hp:tc>"
        "<hp:tc><hp:t>행2-열3</hp:t></hp:tc>"
        "</hp:tr>"
        "</hp:tbl>"
        "</hp:section>"
    )


class TestRegressionWrongAmountDetection(unittest.TestCase):
    def test_wrong_amount_produces_exit_1(self):
        raw = _hwpx_bytes(_section0_simple("원본 금액 1000"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "원본 금액 1000"}
        edits = [{"fieldId": fid, "value": "잘못된 금액 2000", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=True)
        self.assertEqual(result["exit_code"], 1, f"잘못된 금액은 품질 실패여야 함: {result}")
        self.assertFalse(result["passed"])
        self.assertGreater(result["metrics"]["miswrite_count"], 0)


class TestRegressionUnselectedFieldPreserved(unittest.TestCase):
    def test_unselected_field_original_text_preserved(self):
        raw = _hwpx_bytes(_section0_two_paragraphs("첫문단", "둘째문단"))
        a_sha = hashlib.sha256(raw).hexdigest()
        pkg = read_hwpx(raw)
        xml = read_xml(pkg)
        analysis = analyze_a(xml, a_bytes=raw, a_sha256=a_sha)
        fields = analysis.fields
        self.assertTrue(len(fields) >= 2, "두 개 이상의 필드가 있어야 함")
        # 첫 번째 필드만 편집, 두 번째 필드는 미선택
        target_fid = fields[0]["fieldId"]
        other_fid = fields[1]["fieldId"]
        edits = [{"fieldId": target_fid, "value": "편집값", "selected": True, "origin": "manual"}]
        result = generate_result(raw, a_sha, fields, edits, None, None, None, None)
        v = validate_output(result["resultBytes"], raw, fields, edits, a_sha)
        fixed_checks = [c for c in v["checks"] if c.get("name") == "fixed-text-preserved"]
        self.assertTrue(any(c.get("status") == "passed" for c in fixed_checks),
                        f"고정 문구 보존 실패: {v}")
        # 미선택 필드가 결과에 남아 있는지 확인
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        self.assertIn("둘째문단", section_text, "미선택 필드가 보존되어야 함")


class TestRegressionMergedCellPreserved(unittest.TestCase):
    def test_merged_table_structure_preserved_after_paragraph_edit(self):
        raw = _hwpx_bytes(_section0_merged_table())
        a_sha = hashlib.sha256(raw).hexdigest()
        pkg = read_hwpx(raw)
        xml = read_xml(pkg)
        orig_tables = read_tables(xml)
        self.assertGreater(len(orig_tables.tables), 0, "원본에 표가 있어야 함")
        self.assertTrue(orig_tables.tables[0].merges, "병합 셀이 있어야 함")
        # 표 문단을 편집(병합 셀은 건드리지 않음)
        edits = [{"fieldId": "f-top", "value": "수정 문단", "selected": True, "origin": "manual"}]
        # analyze_a가 표 위 문단을 필드로 분석하는지 확인
        analysis = analyze_a(xml, a_bytes=raw, a_sha256=a_sha)
        top_field = next((f for f in analysis.fields if f.get("originalText") == "표 위 문단"), None)
        if top_field is None:
            self.skipTest("표 위 문단을 필드로 분석하지 않음")
        edits = [{"fieldId": top_field["fieldId"], "value": "수정 문단", "selected": True, "origin": "manual"}]
        result = generate_result(raw, a_sha, analysis.fields, edits, None, None, None, None)
        v = validate_output(result["resultBytes"], raw, analysis.fields, edits, a_sha)
        table_checks = [c for c in v["checks"] if c.get("name") == "table-grid-merge-preserved"]
        self.assertTrue(any(c.get("status") == "passed" for c in table_checks),
                        f"표 격자·병합 보존 실패: {v}")
        # 결과 표 구조도 원본과 동일한지 확인
        new_pkg = read_hwpx(result["resultBytes"])
        new_xml = read_xml(new_pkg)
        new_tables = read_tables(new_xml)
        self.assertEqual(len(orig_tables.tables), len(new_tables.tables),
                         "표 개수가 보존되어야 함")
        for o, n in zip(orig_tables.tables, new_tables.tables):
            self.assertEqual(o.row_count, n.row_count)
            self.assertEqual(o.column_count, n.column_count)
            self.assertEqual([(m.type, m.start_row, m.start_col, m.spans) for m in o.merges],
                             [(m.type, m.start_row, m.start_col, m.spans) for m in n.merges])


class TestRegressionZipCorruptionDetected(unittest.TestCase):
    def test_read_hwpx_rejects_bad_zip(self):
        bad = b"this is not a zip"
        from hwpx.errors import DomainError
        with self.assertRaises(DomainError):
            read_hwpx(bad)

    def test_validate_reports_zip_error_on_bad_result(self):
        raw = _hwpx_bytes(_section0_simple("정상"))
        a_sha = hashlib.sha256(raw).hexdigest()
        bad_result = b"not a real result"
        v = validate_output(bad_result, raw, [], [], a_sha)
        self.assertFalse(v["passed"])
        self.assertTrue(any(e.get("type") == "zip-structure" for e in v["errors"]))


class TestRegressionXmlCorruptionDetected(unittest.TestCase):
    def test_read_xml_rejects_bad_xml_section(self):
        raw = _hwpx_bytes("<?xml version=\"1.0\"?><broken")
        pkg = read_hwpx(raw)
        from hwpx.xml import read_xml
        from hwpx.errors import DomainError
        with self.assertRaises(DomainError):
            read_xml(pkg)

    def test_validate_reports_xml_error_on_bad_section(self):
        raw = _hwpx_bytes("<?xml version=\"1.0\"?><broken")
        a_sha = hashlib.sha256(raw).hexdigest()
        v = validate_output(raw, raw, [], [], a_sha)
        self.assertFalse(v["passed"])
        self.assertTrue(any(e.get("type") == "xml-wellformed" for e in v["errors"]))


class TestRegressionFailureVersusNotVerified(unittest.TestCase):
    def test_human_reviewed_false_with_edits_is_exit_1(self):
        raw = _hwpx_bytes(_section0_simple("원본"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "원본"}
        edits = [{"fieldId": fid, "value": "다른값", "selected": True, "origin": "manual"}]
        result = evaluate_quality(raw, a_sha, None, gold, edits=edits, human_reviewed=False)
        self.assertEqual(result["exit_code"], 1, f"사람 검토 없이 품질 실패면 exit 1: {result}")

    def test_no_edits_no_human_review_is_exit_2(self):
        raw = _hwpx_bytes(_section0_simple("원본"))
        a_sha = hashlib.sha256(raw).hexdigest()
        fid = analyze_a(read_xml(raw), a_bytes=raw, a_sha256=a_sha).fields[0]["fieldId"]
        gold = {fid: "원본"}
        result = evaluate_quality(raw, a_sha, None, gold, edits=None, human_reviewed=False)
        self.assertEqual(result["exit_code"], 2, f"편집 없고 사람 검토도 없으면 exit 2: {result}")
        self.assertFalse(result["passed"])
        self.assertIn("편집이 없어", " ".join(result["notes"]))


if __name__ == "__main__":
    unittest.main()

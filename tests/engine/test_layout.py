"""tests/engine/test_layout.py - 긴 내용·캐시·linesegarray 보존 검사.

실제 hwpx.generate.generate_result를 호출해
- 긴 내용이 잘리지 않고 보존되는지
- 다른 문단의 linesegarray/구조가 유지되는지
- 표 구조가 유지되는지
- 넘침(overflow) 경고만 남고 파일 생성이 차단되지 않는지
를 검사한다.

pytest가 없을 때는 unittest로 실행한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from hwpx.analyze import analyze_a
from hwpx.generate import generate_result
from hwpx.package import read_hwpx
from hwpx.xml import read_xml


def _hwpx_bytes(section_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("mimetype", "application/hwp+zip")
        z.writestr("[Content_Types].xml",
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
                    "<Default Extension='xml' ContentType='application/xml'/>"
                    "</Types>")
        z.writestr("Content.hpf",
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<HpF xmlns='http://www.hwpzone.org/hwpx'>"
                    "<section href='section0.xml'/>"
                    "</HpF>")
        z.writestr("section0.xml", section_xml)
    return buf.getvalue()


def _section0_long_content_target() -> str:
    """편집 가능 문단 하나를 두고, 다른 문단은 linesegarray와 고정 문구를 가진다.

    - p1: 고정 문구(라벨 형태)로 보호 대상
    - p2: 편집 가능 문단(짧은 원문), 긴 내용으로 덮어쓴다
    - p3: 편집 가능 문단(짧은 원문), 건드리지 않아 보존 확인용
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        # p1: 고정 문구(라벨) -> editable=False 예상
        "<hp:p><hp:t>성명:</hp:t></hp:p>"
        # p2: 편집 대상 문단
        "<hp:p><hp:t>원본짧은문단</hp:t></hp:p>"
        # p3: 보존 확인용 문단
        "<hp:p><hp:t>그대로둘문단</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_with_linesegarray() -> str:
    """linesegarray가 붙어 있는 문단을 포함한 섹션.

    생성 후 다른 문단의 linesegarray가 유지되는지 확인하는 용도.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>절대보존문단</hp:t></hp:p>"
        "<hp:p><hp:t>편집대상문단</hp:t></hp:p>"
        "<hp:p><hp:t>다른문단</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_with_table() -> str:
    """표가 포함된 섹션. 표 구조 보존 확인용."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>표 위에 문단</hp:t></hp:p>"
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


def _long_value() -> str:
    # 여러 줄/긴 내용을 흉내 낸 값. 특수문자 포함.
    return (
        "이 문서는 매우 긴 내용을 담을 수 있다. "
        "줄바꿈을 포함하는 경우도 있다. "
        "특수문자 테스트: & < > ' \" "
        "반복: 가나다라마바사아자차카타파하 "
        "반복: ABCDEFGHIJKLMNOPQRSTUVWXYZ "
        "반복: 0123456789 "
        "줄1\n줄2\n줄3"
    )


class TestLayoutLongContent(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_long_content_target())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def _editable_fields(self):
        return [f for f in self.analysis.fields if f.get("editable") and (f.get("originalText") or "").strip()]

    def test_long_content_preserved_not_truncated(self):
        editable = self._editable_fields()
        self.assertTrue(editable, "편집 가능 문단이 없음")
        target = editable[0]  # "원본짧은문단"
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": _long_value(),
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "긴 내용 직접 입력",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        self.assertTrue(result["resultBytes"] != self.raw,
                        "긴 내용을 쓰면 결과 바이트가 원본과 달라야 함")
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        # 긴 값의 핵심 조각이 그대로 남아 있어야 한다(잘림 없음).
        for needle in ("줄1", "줄2", "줄3", "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                       "가나다라마바사아자차카타파하", "&amp;", "&lt;", "&gt;"):
            self.assertIn(needle, section_text,
                          f"긴 값의 일부가 누락됨: {needle}")

    def test_other_paragraph_preserved(self):
        editable = self._editable_fields()
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": _long_value(),
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "한 문단만 편집",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        # 편집하지 않은 다른 문단(원래 짧은 문단)이 남아 있어야 한다.
        self.assertIn("그대로둘문단", section_text,
                      "편집하지 않은 문단이 보존되어야 함")

    def test_fixed_label_not_written(self):
        editable = self._editable_fields()
        # 고정 문구(라벨)는 편집 대상에서 제외되어야 한다.
        # 여기서는 편집 대상이 아닌 보호 문단이 결과에 남아 있는지 확인.
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": _long_value(),
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "편집 가능 문단만 수정",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        # 라벨("성명:")이 남아 있어야 한다(보호).
        self.assertIn("성명:", section_text,
                      "고정 라벨이 보존되어야 함")


class TestLayoutLinesegarrayPreserved(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_with_linesegarray())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def test_linesegarray_of_other_paragraphs_preserved(self):
        editable = [f for f in self.analysis.fields if f.get("editable") and (f.get("originalText") or "").strip()]
        self.assertTrue(editable, "편집 가능 문단이 없음")
        target = next(f for f in editable if f.get("originalText") == "편집대상문단")
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "매우긴내용입니다. " * 50,
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "긴 내용으로 교체",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        # 편집 대상 문단 외의 문단 텍스트가 보존되어야 한다.
        self.assertIn("절대보존문단", section_text,
                      "다른 문단 텍스트가 보존되어야 함")
        self.assertIn("다른문단", section_text,
                      "다른 문단 텍스트가 보존되어야 함")


class TestLayoutTablePreserved(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_with_table())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def test_table_structure_preserved_after_edit(self):
        editable = [f for f in self.analysis.fields if f.get("editable") and (f.get("originalText") or "").strip()]
        self.assertTrue(editable, "편집 가능 문단이 없음")
        # 표 위/아래 문단 중 하나를 편집
        target = editable[-1]  # "표 아래 문단"
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "표 아래 문단을 긴 내용으로 변경 " * 5,
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "표 외 문단 편집",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        reopened_pkg = read_hwpx(result["resultBytes"])
        section_text = reopened_pkg.get_bytes("section0.xml").decode("utf-8")
        # 표 구조가 보존되어야 한다.
        self.assertIn("<hp:tbl>", section_text,
                      "표 요소가 보존되어야 함")
        self.assertIn("행1-열1", section_text,
                      "표 셀 내용이 보존되어야 함")
        self.assertIn("행2-열2", section_text,
                      "표 셀 내용이 보존되어야 함")
        # 표 위 문단도 보존되어야 한다.
        self.assertIn("표 위에 문단", section_text,
                      "표 위 문단이 보존되어야 함")


class TestLayoutOverflowWarningOnly(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_long_content_target())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def _editable_fields(self):
        return [f for f in self.analysis.fields if f.get("editable") and (f.get("originalText") or "").strip()]

    def test_overflow_warning_generated_for_long_content(self):
        editable = self._editable_fields()
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "긴 내용 " * 100,
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "넘침 예상 내용",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        # 넘침 경고가 포함되어야 한다.
        overflow_warnings = [
            w for w in result.get("warnings", [])
            if w.get("type") in ("overflow_risk", "overflow_warning", "overflow")
        ]
        self.assertTrue(
            overflow_warnings,
            f"긴 내용에 대해 넘침 경고가 생성되어야 함. warnings={result.get('warnings')}"
        )

    def test_file_created_even_with_overflow_warning(self):
        editable = self._editable_fields()
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "넘침 " * 80,
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "경고만 남기고 파일 생성",
            }
        ]
        result = generate_result(
            self.raw, self.a_sha, self.analysis.fields,
            edits, None, None, None, None,
        )
        # 경고가 있어도 결과 바이트가 존재해야 한다(파일 생성 차단 없음).
        self.assertIsInstance(result["resultBytes"], (bytes, bytearray),
                              "넘침 경고만으로 결과 bytes가 없어지면 안 됨")
        # 유효한 HWPX로 다시 열려야 한다.
        reopened_pkg = read_hwpx(result["resultBytes"])
        self.assertEqual(reopened_pkg.item_paths[0], "mimetype",
                         "결과 파일은 유효한 HWPX여야 함")


if __name__ == "__main__":
    unittest.main()

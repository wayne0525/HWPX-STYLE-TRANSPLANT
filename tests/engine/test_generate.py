"""tests/engine/test_generate.py -- 생성 결과 검사.

실제 hwpx.generate.generate_result를 호출해 원본 구간 기입 규칙을 검사한다.
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


def _section0_simple() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>안녕하세요</hp:t></hp:p>"
        "<hp:p><hp:t></hp:t></hp:p>"
        "<hp:p><hp:t>끝</hp:t></hp:p>"
        "</hp:section>"
    )


class TestGenerateResult(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_simple())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def _section_text(self, result: dict):
        pkg = read_hwpx(result["resultBytes"])
        section_name = None
        for name in pkg.item_paths:
            if name.lower().endswith(".xml") and "section" in name.lower():
                section_name = name
                break
        self.assertIsNotNone(section_name, "section xml을 찾지 못함")
        return pkg.get_bytes(section_name).decode("utf-8")

    def test_hangul_and_escapes_written_and_outside_bytes_unchanged(self):
        fields = self.analysis.fields
        editable = [f for f in fields if f.get("editable") and (f.get("originalText") or "").strip()]
        self.assertTrue(editable, "편집 가능 문단이 없음")
        target = editable[0]  # "안녕하세요" 문단
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "김가람 & 홍길동 <테스트> '따옴표' \"쌍따옴표\" <br/>",
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "직접 입력",
            }
        ]
        result = generate_result(
            self.raw,
            self.a_sha,
            self.analysis.fields,
            edits,
            None,
            None,
            None,
            None,
        )
        self.assertTrue(result["resultBytes"] != self.raw)
        text = self._section_text(result)
        self.assertNotIn("안녕하세요", text)  # 편집 대상이므로 사라짐
        self.assertIn("끝", text)  # 편집되지 않은 다른 문단 보존
        self.assertIn("김가람", text)
        self.assertIn("&amp;", text)
        self.assertIn("&lt;테스트&gt;", text)
        self.assertIn("&apos;따옴표&apos;", text)
        self.assertIn("&quot;쌍따옴표&quot;", text)
        self.assertIn("<br/>", text)

    def test_empty_auto_proposal_and_unselected_preserved(self):
        fields = self.analysis.fields
        editable = [f for f in fields if f.get("editable")]
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "",
                "selected": False,
                "origin": "solar",
                "evidence": None,
                "note": "빈 자동 제안",
            }
        ]
        result = generate_result(
            self.raw,
            self.a_sha,
            self.analysis.fields,
            edits,
            None,
            None,
            None,
            None,
        )
        self.assertEqual(result["resultBytes"], self.raw)
        self.assertFalse(result["changedFields"])

    def test_manual_clear_selected(self):
        fields = self.analysis.fields
        editable = [f for f in fields if f.get("editable") and (f.get("originalText") or "").strip()]
        target = editable[1]  # "끝" 문단
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "",
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "명시적 수동 비우기",
            }
        ]
        result = generate_result(
            self.raw,
            self.a_sha,
            self.analysis.fields,
            edits,
            None,
            None,
            None,
            None,
        )
        self.assertTrue(result["resultBytes"] != self.raw)
        text = self._section_text(result)
        self.assertIn("안녕하세요", text)
        self.assertNotIn("끝", text)

    def test_overlapping_ranges_rejected(self):
        fields = self.analysis.fields
        editable = [f for f in fields if f.get("editable") and (f.get("originalText") or "").strip()]
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "시작",
                "selected": True,
                "origin": "manual",
                "note": "첫 편집",
            },
            {
                "fieldId": target["fieldId"],
                "value": "끝",
                "selected": True,
                "origin": "manual",
                "note": "겹치는 편집",
            },
        ]
        result = generate_result(
            self.raw,
            self.a_sha,
            self.analysis.fields,
            edits,
            None,
            None,
            None,
            None,
        )
        self.assertTrue(any(e.get("type") == "conflict" for e in result.get("warnings", [])) or result.get("errors"))


if __name__ == "__main__":
    unittest.main()

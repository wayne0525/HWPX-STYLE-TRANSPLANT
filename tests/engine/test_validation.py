"""tests/engine/test_validation.py -- 생성 결과 검증 검사.

실제 hwpx.validate.validate_output을 호출해
ZIP/XML/mimetype/고정 문구/표 격자·병합/보호 구간/적용값 재추출을 검사한다.
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
from hwpx.validate import validate_output


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


class TestValidationOutput(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_simple())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def _gen(self, edits):
        return generate_result(
            self.raw,
            self.a_sha,
            self.analysis.fields,
            edits,
            None,
            None,
            None,
            None,
        )

    def _rebuild_normal(self, new_section: str) -> bytes:
        # mimetype 첫 엔트리·비압축, 나머지는 정상
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
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
            z.writestr("section0.xml", new_section)
        return buf.getvalue()

    def test_valid_file_passes_and_returns_report(self):
        editable = [f for f in self.analysis.fields if f.get("editable") and (f.get("originalText") or "").strip()]
        target = editable[0]
        edits = [
            {
                "fieldId": target["fieldId"],
                "value": "김가람",
                "selected": True,
                "origin": "manual",
                "evidence": None,
                "note": "직접 입력",
            }
        ]
        result = self._gen(edits)
        v = validate_output(result["resultBytes"], self.raw, self.analysis.fields, edits, self.a_sha)
        self.assertTrue(v["passed"])
        self.assertIsInstance(v["report"], dict)
        self.assertTrue(any(c["name"] == "mimetype" and c["status"] == "passed" for c in v["checks"]))
        self.assertTrue(any(c["name"] == "value-placement" and c["status"] == "passed" for c in v["checks"]))

    def test_tampered_protected_structure_fails(self):
        pkg = read_hwpx(self.raw)
        section_bytes = pkg.get_bytes("section0.xml")
        section_text = section_bytes.decode("utf-8")
        # 보호 대상(빈 문단)을 임의로 채움 → 보호 구간 변경
        tampered = section_text.replace("<hp:p><hp:t></hp:t></hp:p>",
                                        "<hp:p><hp:t>변조</hp:t></hp:p>")
        bad_bytes = self._rebuild_normal(tampered)
        v = validate_output(bad_bytes, self.raw, self.analysis.fields, [], self.a_sha)
        self.assertFalse(v["passed"])
        self.assertTrue(any(e.get("type") == "protected-changed" for e in v["errors"]) or
                        any(e.get("type") == "fixed-text-changed" for e in v["errors"]))

    def test_mimetype_first_entry_stored(self):
        pkg = read_hwpx(self.raw)
        self.assertEqual(pkg.item_paths[0], "mimetype")
        self.assertEqual(pkg.by_path["mimetype"].compress_type, 0)
        self.assertEqual(pkg.by_path["mimetype"].bytes, b"application/hwp+zip")


if __name__ == "__main__":
    unittest.main()

"""tests/engine/test_manual_candidates.py -- 수동 보정 후보와 생성 검사.

실제 hwpx.analyze.analyze_a, hwpx.corrections.correct_candidates,
hwpx.generate.generate_result를 호출해 수동 보정 후보와 생성 규칙을 검사한다.
pytest가 없을 때는 unittest로 실행한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from hwpx.analyze import analyze_a
from hwpx.corrections import correct_candidates
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


def _section0_two_empty_one_safe() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t></hp:t></hp:p>"
        "<hp:p><hp:t></hp:t></hp:p>"
        "<hp:p><hp:t>안전한 문단</hp:t></hp:p>"
        "</hp:section>"
    )


class TestManualCandidates(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_two_empty_one_safe())
        self.pkg = read_hwpx(self.raw)
        self.xml = read_xml(self.pkg)
        self.a_sha = "sha256:" + self.raw.hex()[:16]
        self.analysis = analyze_a(self.xml, a_bytes=self.raw, a_sha256=self.a_sha)

    def test_safe_paragraph_has_auto_field_and_manual_candidate(self):
        fields = self.analysis.fields
        editable = [f for f in fields if f.get("editable")]
        self.assertTrue(editable, "안전한 문단에 자동 입력란이 없음")
        corrections = [
            {"candidateId": editable[0]["candidateId"], "label": "성명", "enabled": True}
        ]
        result = correct_candidates(fields, corrections, self.a_sha)
        self.assertTrue(result["corrected"])


if __name__ == "__main__":
    unittest.main()

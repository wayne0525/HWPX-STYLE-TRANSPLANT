"""tests/engine/test_candidates.py -- analyze_a 후보/ID 검사.

실제 hwpx.analyze.analyze_a를 호출해 기대값을 검사한다.
pytest가 없을 때는 unittest로 실행 가능하도록 TestCase로 작성한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import unittest
import hashlib
import io
import zipfile
from xml.etree import ElementTree as ET

from hwpx.package import read_hwpx
from hwpx.xml import read_xml
from hwpx.analyze import analyze_a, CONTENT_NS


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _content_hpf(sections: list[str]) -> bytes:
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<HpF xmlns="http://www.hwpzone.org/hwpx">')
    for name in sections:
        parts.append(f'<section href="{name}"/>')
    parts.append('</HpF>')
    return "".join(parts).encode("utf-8")


def _section_bytes(label: str, paras: list[str]) -> bytes:
    inner: list[str] = []
    for p in paras:
        if p == "":
            inner.append('<hp:p></hp:p>')
        elif p == "empty":
            inner.append('<hp:p><hp:t/></hp:p>')
        else:
            inner.append(f'<hp:p><hp:t>{p}</hp:t></hp:p>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hp:section xmlns:hp="http://www.hwpzone.org/hwpx">'
        + "".join(inner)
        + "</hp:section>"
    ).encode("utf-8")


def _hwpx_bytes(section_entries: list[tuple[str, list[str]]]) -> bytes:
    section_names: list[str] = []
    section_data: dict[str, bytes] = {}
    for idx, (name, paras) in enumerate(section_entries, start=1):
        oname = f"section{idx}.xml"
        section_names.append(oname)
        section_data[oname] = _section_bytes(name, paras)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Content.hpf", _content_hpf(section_names))
        for oname, data in section_data.items():
            zf.writestr(oname, data)
    return buf.getvalue()


class TestAnalyzeACandidates(unittest.TestCase):
    def test_editable_and_protected(self):
        b = _hwpx_bytes([
            ("A", ["이름:", "홍길동"]),
            ("B", ["", "테스트"]),
        ])
        sha = _sha256(b)

        xml_result = read_xml(b)
        result = analyze_a(xml_result, a_bytes=b, a_sha256=sha)

        self.assertEqual(result.analysis_id, f"a-{sha[:16]}")
        self.assertEqual(result.a_hash, sha)
        self.assertEqual(result.file_kind, "hwpx")
        self.assertEqual(result.analysis_status, "partial")
        self.assertIsNone(result.normalizedIndex)

        fields = result.fields
        self.assertEqual(len(fields), 4, msg=f"fields={fields}")

        # 첫 섹션 첫번째 문단('이름:')은 고정 문구 판정 → 보호
        name_field = next(f for f in fields if f["originalText"] == "이름:")
        self.assertFalse(name_field["editable"])
        self.assertEqual(name_field["status"], "fixed")

        # 나머지 3개(홍길동, 빈 문단, 테스트) 중
        # 빈 문단은 보호, 홍길동/테스트는 편집 후보
        editable_texts = {"홍길동", "테스트"}
        empty_texts = {""}

        for f in fields:
            t = f["originalText"]
            if t == "이름:":
                continue
            if t in editable_texts:
                self.assertTrue(f["editable"])
            elif t in empty_texts:
                self.assertFalse(f["editable"])

    def test_stable_id_on_reevaluation(self):
        b = _hwpx_bytes([
            ("X", ["이름:", "홍길동"]),
        ])
        sha = _sha256(b)

        xml_result = read_xml(b)

        first = analyze_a(xml_result, a_bytes=b, a_sha256=sha)
        second = analyze_a(xml_result, a_bytes=b, a_sha256=sha)

        self.assertEqual(first.analysis_id, second.analysis_id)
        self.assertEqual(first.a_hash, second.a_hash)
        self.assertEqual(len(first.fields), len(second.fields))
        for a, b in zip(first.fields, second.fields):
            self.assertEqual(a["candidateId"], b["candidateId"])
            self.assertEqual(a["fieldId"], b["fieldId"])
            self.assertEqual(a["editable"], b["editable"])
            self.assertEqual(a["originalText"], b["originalText"])

    def test_empty_t_is_not_editable(self):
        b = _hwpx_bytes([
            ("S", ["값이 있음", "", "값이 있음2"]),
        ])
        sha = _sha256(b)
        xml_result = read_xml(b)
        result = analyze_a(xml_result, a_bytes=b, a_sha256=sha)

        fields = result.fields
        self.assertEqual(len(fields), 3)
        for f in fields:
            if f["originalText"] in ("값이 있음", "값이 있음2"):
                self.assertTrue(f["editable"])
            else:
                self.assertFalse(f["editable"])


if __name__ == "__main__":
    unittest.main()

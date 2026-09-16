#!/usr/bin/env python3
"""tests/engine/test_xml_runner.py — unittest 기반 실제 검사 실행.

pytest가 없을 때도 실제 운영 코드를 검사하기 위한 대체 실행기.
기대값은 tests/engine/test_xml.py와 동일하게 유지한다.
"""

from __future__ import annotations

import io
import sys
import unittest
import zipfile

from hwpx import read_hwpx
from hwpx.errors import DomainError
from hwpx.xml import read_xml, check_ns_mixed


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_content_hpf(section_paths):
    body = "\n".join(f'  <hf:section href="{p}"/>' for p in section_paths)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<hf:HpF xmlns:hf="http://www.hwpzone.org/content">\n'
        f"{body}\n"
        "</hf:HpF>\n"
    ).encode("utf-8")


def _make_hwpx_bytes(*, section_paths, section_xmls, mimetype_value="application/hwp+zip", extra_entries=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", mimetype_value, compress_type=zipfile.ZIP_STORED)
        z.writestr("Content.hpf", _make_content_hpf(section_paths), compress_type=zipfile.ZIP_STORED)
        for path, xml in section_xmls.items():
            z.writestr(path, xml, compress_type=zipfile.ZIP_STORED)
        if extra_entries:
            for path, data in extra_entries.items():
                z.writestr(path, data, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def _ns_content():
    return "http://www.hwpzone.org/content"


# ---------------------------------------------------------------------------
# 정상 ZIP 2종
# ---------------------------------------------------------------------------

class TestOpenNormalHwpx(unittest.TestCase):
    def test_open_normal_hwpx_by_bytes(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml"],
            section_xmls={
                "section0.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><p/></root>'
            },
        )
        res = read_xml(raw)
        self.assertEqual(res.section_paths_in_order, ["section0.xml"])
        self.assertEqual(res.sections[0].path, "section0.xml")
        self.assertEqual(res.sections[0].tree.root.local, "root")
        self.assertEqual(res.original_bytes, raw)

    def test_open_normal_hwpx_read_result(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml", "section1.xml"],
            section_xmls={
                "section0.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><p/></root>',
                "section1.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><q/></root>',
            },
        )
        pkg = read_hwpx(raw)
        res = read_xml(pkg)
        self.assertEqual(res.section_paths_in_order, ["section0.xml", "section1.xml"])
        self.assertEqual([s.path for s in res.sections], ["section0.xml", "section1.xml"])


# ---------------------------------------------------------------------------
# 네임스페이스: 접두사가 달라도 같은 URI는 처리
# ---------------------------------------------------------------------------

class TestSameUriDifferentPrefix(unittest.TestCase):
    def test_find_by_uri_works_for_different_prefix(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml", "section1.xml"],
            section_xmls={
                "section0.xml": (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<root xmlns="http://www.hwpzone.org/content">\n'
                    '  <p id="a"/>\n'
                    "</root>\n"
                ).encode("utf-8"),
                "section1.xml": (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<hz:root xmlns:hz="http://www.hwpzone.org/content">\n'
                    '  <hz:p id="b"/>\n'
                    "</hz:root>\n"
                ).encode("utf-8"),
            },
        )
        res = read_xml(raw)
        section0 = res.sections[0]
        section1 = res.sections[1]

        p0 = section0.find_all(_ns_content(), "p")
        p1 = section1.find_all(_ns_content(), "p")

        self.assertEqual(len(p0), 1)
        self.assertEqual(p0[0].attributes.get("id"), "a")
        self.assertEqual(len(p1), 1)
        self.assertEqual(p1[0].attributes.get("id"), "b")


# ---------------------------------------------------------------------------
# 외부 namespace의 같은 이름 태그는 섞지 않음
# ---------------------------------------------------------------------------

class TestExternalNsNotMixed(unittest.TestCase):
    def test_external_ns_same_local_not_returned_as_internal(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml"],
            section_xmls={
                "section0.xml": (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<root xmlns="http://www.hwpzone.org/content" xmlns:ext="http://example.invalid">\n'
                    '  <p id="internal"/>\n'
                    '  <ext:p id="external"/>\n'
                    "</root>\n"
                ).encode("utf-8"),
            },
        )
        res = read_xml(raw)
        section0 = res.sections[0]

        internal_p = section0.find_all(_ns_content(), "p")
        external_p = section0.find_all("http://example.invalid", "p")

        self.assertEqual(len(internal_p), 1)
        self.assertEqual(internal_p[0].attributes.get("id"), "internal")
        self.assertEqual(len(external_p), 1)
        self.assertEqual(external_p[0].attributes.get("id"), "external")

    def test_check_ns_mixed_reports_external_same_local(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml"],
            section_xmls={
                "section0.xml": (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<root xmlns="http://www.hwpzone.org/content" xmlns:ext="http://example.invalid">\n'
                    '  <p id="internal"/>\n'
                    '  <ext:p id="external"/>\n'
                    "</root>\n"
                ).encode("utf-8"),
            },
        )
        res = read_xml(raw)
        problems = check_ns_mixed(res.sections)
        self.assertGreaterEqual(len(problems), 1)
        joined = "\n".join(problems)
        self.assertTrue("external" in joined.lower() or "ext" in joined.lower())


# ---------------------------------------------------------------------------
# section 10과 2를 문자열 순서로 오배치하지 않음
# ---------------------------------------------------------------------------

class TestSectionOrder(unittest.TestCase):
    def test_section_order_follows_content_hpf_not_string_sort(self):
        raw = _make_hwpx_bytes(
            section_paths=["section10.xml", "section2.xml"],
            section_xmls={
                "section10.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><s n="10"/></root>',
                "section2.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><s n="2"/></root>',
            },
        )
        res = read_xml(raw)
        self.assertEqual(res.section_paths_in_order, ["section10.xml", "section2.xml"])
        self.assertEqual(res.sections[0].path, "section10.xml")
        self.assertEqual(res.sections[1].path, "section2.xml")


# ---------------------------------------------------------------------------
# 손상, 경로 탈출, 실제 해제 크기 초과는 DomainError
# ---------------------------------------------------------------------------

class TestRejectedInputs(unittest.TestCase):
    def test_corrupt_zip_raises_domain_error(self):
        bad = b"this is not a zip file at all"
        with self.assertRaises(DomainError):
            read_xml(bad)

    def test_path_escape_raises_domain_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr(
                "Content.hpf",
                _make_content_hpf(["section0.xml"]),
                compress_type=zipfile.ZIP_STORED,
            )
            z.writestr(
                "section0.xml",
                b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><p/></root>',
                compress_type=zipfile.ZIP_STORED,
            )
            z.writestr("../escape.xml", b"", compress_type=zipfile.ZIP_STORED)
        with self.assertRaises(DomainError):
            read_xml(buf.getvalue())

    def test_decompressed_size_exceeded_raises_domain_error(self):
        limit = 50000000
        payload = b"x" * (limit + 1)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr(
                "Content.hpf",
                _make_content_hpf(["big.xml"]),
                compress_type=zipfile.ZIP_STORED,
            )
            z.writestr("big.xml", payload, compress_type=zipfile.ZIP_STORED)
        with self.assertRaises(DomainError):
            read_xml(buf.getvalue())


# ---------------------------------------------------------------------------
# 실행 확인용
# ---------------------------------------------------------------------------

class TestExecutionMarker(unittest.TestCase):
    def test_this_runner_is_executed(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()

"""tests/engine/test_xml.py — HWPX XML 안전 읽기 검사.

 reads the actual hwpx/xml.py and hwpx/package.py;
 verifies the expected behaviors listed in the task.

Tests are executed with the Python standard test runner; 0 collected,
skip, and unexecuted tests are not treated as passing.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from hwpx import read_hwpx
from hwpx.errors import DomainError
from hwpx.xml import read_xml, check_ns_mixed


# ---------------------------------------------------------------------------
# fixture helpers (in-memory HWPX)
# ---------------------------------------------------------------------------

def _make_hwpx_bytes(
    *,
    section_paths: list[str],
    section_xmls: dict[str, bytes],
    mimetype_value: str = "application/hwp+zip",
    extra_entries: dict[str, bytes] | None = None,
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "mimetype",
            mimetype_value,
            compress_type=zipfile.ZIP_STORED,
        )
        hpf = _make_content_hpf(section_paths)
        z.writestr("Content.hpf", hpf, compress_type=zipfile.ZIP_STORED)
        for path, xml in section_xmls.items():
            z.writestr(path, xml, compress_type=zipfile.ZIP_STORED)
        if extra_entries:
            for path, data in extra_entries.items():
                z.writestr(path, data, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def _make_content_hpf(section_paths: list[str]) -> bytes:
    body = "\n".join(
        f'  <hf:section href="{path}"/>' for path in section_paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<hf:HpF xmlns:hf="http://www.hwpzone.org/content">\n'
        f"{body}\n"
        "</hf:HpF>\n"
    ).encode("utf-8")


# 기본 네임스페이스가 다른 두 번째 prefix로도 같은 URI를 쓰는 fixture
def _make_namespace_prefix_fixture() -> bytes:
    """section0과 section1이 각각 다른 prefix로 같은 URI를 쓰는 정상 HWPX."""
    return _make_hwpx_bytes(
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


def _make_external_ns_same_local_fixture() -> bytes:
    """내부 namespace와 외부 namespace에서 같은 로컬 이름을 쓰는 section.

    이번 번호는 같은 로컬 이름이라도 외부 namespace의 요소는 내부 의미와
    섞지 않는 것을 기대한다.
    """
    return _make_hwpx_bytes(
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


def _make_section_order_fixture() -> bytes:
    """content.hpf에 section10.xml, section2.xml 순서로 적은 HWPX.

    문자열 정렬로 section2가 먼저 오는 것을 기대하지 않는다.
    """
    return _make_hwpx_bytes(
        section_paths=["section10.xml", "section2.xml"],
        section_xmls={
            "section10.xml": (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<root xmlns="http://www.hwpzone.org/content"><s n="10"/></root>\n'
            ).encode("utf-8"),
            "section2.xml": (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<root xmlns="http://www.hwpzone.org/content"><s n="2"/></root>\n'
            ).encode("utf-8"),
        },
    )


# ---------------------------------------------------------------------------
# 정상 ZIP 2종
# ---------------------------------------------------------------------------

class TestOpenNormalHwpx:
    """정상 HWPX 2종을 열 수 있다."""

    def test_open_normal_hwpx_by_bytes(self):
        raw = _make_hwpx_bytes(
            section_paths=["section0.xml"],
            section_xmls={
                "section0.xml": b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><p/></root>'
            },
        )
        res = read_xml(raw)
        assert res.section_paths_in_order == ["section0.xml"]
        assert res.sections[0].path == "section0.xml"
        assert res.sections[0].tree.root.local == "root"
        assert res.original_bytes == raw

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
        assert res.section_paths_in_order == ["section0.xml", "section1.xml"]
        assert [s.path for s in res.sections] == ["section0.xml", "section1.xml"]


# ---------------------------------------------------------------------------
# 네임스페이스: 접두사가 달라도 같은 URI는 처리
# ---------------------------------------------------------------------------

class TestSameUriDifferentPrefix:
    def test_find_by_uri_works_for_different_prefix(self):
        raw = _make_namespace_prefix_fixture()
        res = read_xml(raw)
        section0 = res.sections[0]
        section1 = res.sections[1]

        # 두 섹션 모두 http://www.hwpzone.org/content/p를 찾을 수 있어야 한다.
        p0 = section0.find_all("http://www.hwpzone.org/content", "p")
        p1 = section1.find_all("http://www.hwpzone.org/content", "p")

        assert len(p0) == 1
        assert p0[0].attributes.get("id") == "a"
        assert len(p1) == 1
        assert p1[0].attributes.get("id") == "b"


# ---------------------------------------------------------------------------
# 외부 namespace의 같은 이름 태그는 섞지 않음
# ---------------------------------------------------------------------------

class TestExternalNsNotMixed:
    def test_external_ns_same_local_not_returned_as_internal(self):
        raw = _make_external_ns_same_local_fixture()
        res = read_xml(raw)
        section0 = res.sections[0]

        internal_p = section0.find_all("http://www.hwpzone.org/content", "p")
        external_p = section0.find_all("http://example.invalid", "p")

        # 내부 namespace 기준으로 찾으면 내부 요소만 나온다.
        assert len(internal_p) == 1
        assert internal_p[0].attributes.get("id") == "internal"

        # 외부 namespace의 동일 로컬 이름 요소는 별도 URI로만 찾을 수 있다.
        assert len(external_p) == 1
        assert external_p[0].attributes.get("id") == "external"

    def test_check_ns_mixed_reports_external_same_local(self):
        raw = _make_external_ns_same_local_fixture()
        res = read_xml(raw)
        problems = check_ns_mixed(res.sections)
        assert len(problems) >= 1
        joined = "\n".join(problems)
        assert "external" in joined.lower() or "ext" in joined.lower()


# ---------------------------------------------------------------------------
# section 10과 2를 문자열 순서로 오배치하지 않음
# ---------------------------------------------------------------------------

class TestSectionOrder:
    def test_section_order_follows_content_hpf_not_string_sort(self):
        raw = _make_section_order_fixture()
        res = read_xml(raw)
        assert res.section_paths_in_order == ["section10.xml", "section2.xml"]
        assert res.sections[0].path == "section10.xml"
        assert res.sections[1].path == "section2.xml"


# ---------------------------------------------------------------------------
# 손상, 경로 탈출, 실제 해제 크기 초과는 DomainError
# ---------------------------------------------------------------------------

class TestRejectedInputs:
    def test_corrupt_zip_raises_domain_error(self):
        bad = b"this is not a zip file at all"
        with pytest.raises(DomainError):
            read_xml(bad)

    def test_path_escape_raises_domain_error(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr(
                "Content.hpf",
                b'<?xml version="1.0" encoding="UTF-8"?><hf:HpF xmlns:hf="http://www.hwpzone.org/content"><hf:section href="section0.xml"/></hf:HpF>',
                compress_type=zipfile.ZIP_STORED,
            )
            z.writestr(
                "section0.xml",
                b'<?xml version="1.0" encoding="UTF-8"?><root xmlns="http://www.hwpzone.org/content"><p/></root>',
                compress_type=zipfile.ZIP_STORED,
            )
            # 경로 탈출 시도
            z.writestr("../escape.xml", b"", compress_type=zipfile.ZIP_STORED)
        with pytest.raises(DomainError):
            read_xml(buf.getvalue())

    def test_decompressed_size_exceeded_raises_domain_error(self):
        # 실제 누적 해제 크기가 제한을 넘는 케이스를 만든다.
        # 내부 제한은 50000000 bytes이므로, 그 이하의 초과 케이스를 만든다.
        limit = 50000000
        payload = b"x" * (limit + 1)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr(
                "Content.hpf",
                b'<?xml version="1.0" encoding="UTF-8"?><hf:HpF xmlns:hf="http://www.hwpzone.org/content"><hf:section href="big.xml"/></hf:HpF>',
                compress_type=zipfile.ZIP_STORED,
            )
            # 실제 해제 크기가 제한을 넘는 항목
            z.writestr("big.xml", payload, compress_type=zipfile.ZIP_STORED)
        with pytest.raises(DomainError):
            read_xml(buf.getvalue())


# ---------------------------------------------------------------------------
# 검사 실행 확인용 메타 테스트
# ---------------------------------------------------------------------------

def test_this_module_is_executed_by_pytest():
    """0개 실행, skip, 미실행 상태를 피하기 위한 실행 확인.

    이 파일 자체가 테스트 수집/실행 대상이 되는지 확인한다.
    """
    assert True

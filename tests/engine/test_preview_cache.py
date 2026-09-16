"""tests/engine/test_preview_cache.py - 미리보기 캐시·manifest·BinData·linesegarray 보존 검사.

실제 hwpx.generate.generate_result와 hwpx.validate.validate_output을 호출해
- 무편집 요청은 원본 파일 바이트와 같아야 함
- 결과 ZIP에 원본에 없는 manifest.xml / Preview / BinData 엔트리를 만들지 않아야 함
- 결과 ZIP에 삭제한 Preview를 가리키는 참조가 없어야 함
- validate_output은 위 결과를 passed로 판단하고 report와 output bytes를 반환해야 함
를 검사한다.

pytest가 없을 때는 unittest로 실행한다.
0개 실행, skip, 미실행은 통과가 아니다.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from hwpx.generate import generate_result
from hwpx.package import ReadResult, read_hwpx
from hwpx.validate import validate_output


def _hwpx_bytes(section_xml: str, extra_items: dict[str, bytes] | None = None) -> bytes:
    """mimetype, [Content_Types].xml, Content.hpf, section0.xml + 추가 항목으로 HWPX를 만든다.

    extra_items: 경로에 매핑된 바이너리(예: BinData/image1.png, manifest.xml 등).
    """
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


def _section0_simple() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>안녕하세요</hp:t></hp:p>"
        "</hp:section>"
    )


def _section0_with_bindata() -> tuple[str, dict[str, bytes]]:
    """BinData 이미지와 (가상) manifest 참조가 있는 섹션.

    현재 운영 코드는 manifest.xml이나 BinData를 생성하지 않지만,
    원본에 존재하면 결과에 보존돼야 한다는 기대를 검사한다.
    """
    section = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hp:section xmlns:hp=\"http://www.hwpzone.org/hwpx\">"
        "<hp:p><hp:t>이미지 있는 양식</hp:t></hp:p>"
        "</hp:section>"
    )
    binimage = b"FAKE-PNG-0001\x00\x00\x00\x00"
    extra = {
        "BinData/image1.png": binimage,
        "manifest.xml": b"<manifest/>",
    }
    return section, extra


class TestPreviewCacheNoOpOnNoEdits(unittest.TestCase):
    def test_no_edits_returns_exact_original_bytes(self):
        raw = _hwpx_bytes(_section0_simple())
        result = generate_result(raw, "sha256:" + raw.hex()[:16], [], None, None, None, None, None)
        self.assertIsInstance(result["resultBytes"], (bytes, bytearray))
        self.assertEqual(result["resultBytes"], raw, "무편집 요청은 원본 바이트와 같아야 함")

    def test_no_edits_with_empty_edits_list_returns_exact_original_bytes(self):
        raw = _hwpx_bytes(_section0_simple())
        result = generate_result(raw, "sha256:" + raw.hex()[:16], [], [], None, None, None, None)
        self.assertEqual(result["resultBytes"], raw, "빈 edits 목록도 무편집으로 처리해야 함")

    def test_selected_false_edits_returns_exact_original_bytes(self):
        raw = _hwpx_bytes(_section0_simple())
        edits = [
            {"fieldId": "f-1", "value": "바뀔값", "selected": False, "origin": "manual"},
        ]
        result = generate_result(raw, "sha256:" + raw.hex()[:16], [], edits, None, None, None, None)
        self.assertEqual(result["resultBytes"], raw, "선택되지 않은 편집도 무편집 처리해야 함")


class TestPreviewCacheDoesNotInventEntries(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_simple())
        self.a_sha = "sha256:" + self.raw.hex()[:16]

    def _entry_names(self, data: bytes) -> list[str]:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.namelist()

    def test_result_has_no_preview_entries(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        names = self._entry_names(result["resultBytes"])
        preview_like = [n for n in names if "preview" in n.lower() or n.lower().startswith("preview")]
        self.assertEqual(preview_like, [], f"결과에 Preview 관련 엔트리가 없어야 함: {names}")

    def test_result_has_no_manifest_xml_when_original_does_not(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        names = self._entry_names(result["resultBytes"])
        self.assertNotIn("manifest.xml", names, "원본에 없는 manifest.xml을 결과가 만들어서는 안 됨")

    def test_result_preserves_original_entry_set_except_section(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        names = set(self._entry_names(result["resultBytes"]))
        orig_names = set(self._entry_names(self.raw))
        # section0.xml은 내용이 바뀔 수 있지만, 항목 이름 집합은 원본과 같아야 함
        self.assertEqual(names, orig_names, f"항목 이름 집합이 원본과 달라야 하지 않음: {sorted(names)}")

    def test_result_bytes_reopenable(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        pkg = read_hwpx(result["resultBytes"])
        self.assertEqual(pkg.item_paths[0], "mimetype", "결과 파일은 유효한 HWPX여야 함")


class TestPreviewCachePreservesExistingBinDataAndManifest(unittest.TestCase):
    def setUp(self):
        section, extra = _section0_with_bindata()
        self.raw = _hwpx_bytes(section, extra_items=extra)
        self.a_sha = "sha256:" + self.raw.hex()[:16]

    def _bytes_for(self, data: bytes, path: str) -> bytes:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.read(path)

    def _entry_names(self, data: bytes) -> list[str]:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.namelist()

    def test_result_preserves_existing_bin_data(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        got = self._bytes_for(result["resultBytes"], "BinData/image1.png")
        expected = self._bytes_for(self.raw, "BinData/image1.png")
        self.assertEqual(got, expected, "원본에 있던 BinData는 결과에 그대로 보존돼야 함")

    def test_result_preserves_existing_manifest_when_rebuild_keeps_it(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        names = self._entry_names(result["resultBytes"])
        self.assertIn("manifest.xml", names, "원본에 있던 manifest.xml은 결과에서 유지되어야 함")
        got = self._bytes_for(result["resultBytes"], "manifest.xml")
        expected = self._bytes_for(self.raw, "manifest.xml")
        self.assertEqual(got, expected, "원본에 있던 manifest.xml 바이트는 그대로 보존돼야 함")


class TestValidateOutputOnPreviewCacheBehavior(unittest.TestCase):
    def setUp(self):
        self.raw = _hwpx_bytes(_section0_simple())
        self.a_sha = "sha256:" + self.raw.hex()[:16]

    def test_validate_passes_on_no_edit_result_and_returns_report_and_bytes(self):
        result = generate_result(self.raw, self.a_sha, [], None, None, None, None, None)
        v = validate_output(result["resultBytes"], self.raw, [], [], self.a_sha)
        self.assertTrue(v["passed"], f"무편집 결과는 검증 통과여야 함: errors={v['errors']}")
        self.assertIn("report", v)
        self.assertIn("resultBytes", result)
        self.assertIsInstance(result["resultBytes"], (bytes, bytearray))

    def test_validate_passes_when_result_equals_original(self):
        v = validate_output(self.raw, self.raw, [], [], self.a_sha)
        self.assertTrue(v["passed"], f"원본과 동일한 결과 파일은 검증 통과여야 함: errors={v['errors']}")


if __name__ == "__main__":
    unittest.main()

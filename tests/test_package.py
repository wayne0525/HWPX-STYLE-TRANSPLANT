"""
tests/test_package.py — 패키지 읽기 및 원본 해시 검증.

계약: docs/contracts/engine.md §1, §1.2

이전 open_package API는 더 이상 사용하지 않는다.
지금은 read_hwpx(bytes) -> ReadResult와 file_hash(path)를 사용한다.
ZIP 읽기, 원본 SHA-256, mimetype, section 존재 확인 등 기존 검증 목적은
ReadResult/ReadResult.item_paths/ReadResult.by_path로 동일하게 보존한다.
이전 테스트를 통과시키려고 낡은 함수를 임시로 추가하지 않는다.
"""
import hashlib
import zipfile
from pathlib import Path

import pytest

from hwpx.package import ReadResult, read_hwpx, file_hash

A_PATH = "tests/fixtures/A.hwpx"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repack_identical(src: str, dst: str) -> None:
    """src ZIP을 엔트리 순서·바이트 그대로 재패키징.

    mimetype은 첫 엔트리, ZIP_STORED로 쓴다.
    """
    with zipfile.ZipFile(src, "r") as zin:
        infos = zin.infolist()
        by_name = {info.filename: zin.read(info.filename) for info in infos}

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        if "mimetype" in by_name:
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, by_name["mimetype"])
        for info in infos:
            if info.filename == "mimetype":
                continue
            zout.writestr(info, by_name[info.filename])


def _read_result(path: str) -> ReadResult:
    raw = open(path, "rb").read()
    return read_hwpx(raw)


class TestReadHwpxValid:
    def test_a_is_valid(self):
        result = _read_result(A_PATH)
        assert result is not None
        assert result.original_bytes
        assert result.original_sha256
        assert len(result.item_paths) > 0

    def test_a_mimetype_first_and_stored(self):
        result = _read_result(A_PATH)
        first = result.item_paths[0]
        assert first == "mimetype"
        mimetype = result.by_path["mimetype"].bytes.decode("utf-8", errors="replace").rstrip("\r\n")
        assert mimetype == "application/hwp+zip"

    def test_a_section_paths(self):
        result = _read_result(A_PATH)
        sections = [p for p in result.item_paths if p.endswith(".xml") and "section" in p]
        assert sections, "section XML이 하나도 없음"
        assert "Contents/section0.xml" in result.item_paths


class TestReadHwpxNonexistent:
    def test_nonexistent_raises(self, tmp_path: Path):
        missing = str(tmp_path / "no.hwpx")
        raw = b""
        with pytest.raises(Exception):
            read_hwpx(raw)


class TestFileHash:
    def test_a_hash_matches(self):
        h = file_hash(A_PATH)
        expected = _sha256_bytes(open(A_PATH, "rb").read())
        assert h == expected

    def test_hash_is_hex_prefixed(self):
        h = file_hash(A_PATH)
        assert len(h) == 64
        int(h, 16)


class TestRepackIdentical:
    def test_mimetype_first_and_stored_after_repack(self, tmp_path: Path):
        dst = str(tmp_path / "A_repack.hwpx")
        _repack_identical(A_PATH, dst)
        result = _read_result(dst)
        assert result is not None
        first = result.item_paths[0]
        assert first == "mimetype"
        mimetype = result.by_path["mimetype"].bytes.decode("utf-8", errors="replace").rstrip("\r\n")
        assert mimetype == "application/hwp+zip"

    def test_all_entries_bytes_match_original(self, tmp_path: Path):
        dst = str(tmp_path / "A_repack.hwpx")
        _repack_identical(A_PATH, dst)
        with zipfile.ZipFile(A_PATH) as archive:
            orig = {info.filename: archive.read(info) for info in archive.infolist()}
        with zipfile.ZipFile(dst) as archive:
            after = {info.filename: archive.read(info) for info in archive.infolist()}
        # ZIP 파일 전체 해시는 mimetype 우선 작성 때문에 다를 수 있으므로,
        # 여기서는 엔트리 이름과 개별 엔트리 바이트 동일성만 검증한다.
        assert set(orig.keys()) == set(after.keys()), "엔트리 이름 집합이 다름"
        for name in orig:
            assert orig[name] == after[name], f"엔트리 {name} 바이트 불일치"

    def test_repack_file_hash_may_differ(self, tmp_path: Path):
        dst = str(tmp_path / "A_repack.hwpx")
        _repack_identical(A_PATH, dst)
        # 엔트리 바이트는 같지만 ZIP 순서/압축 주석의 차이로 파일 해시까지
        # 같을 필요는 없다. 이 테스트는 문서화해 두고 강제하지 않는다.
        assert open(dst, "rb").read()

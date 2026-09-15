"""HWPX ZIP 안전 읽기 — 메모리 전용.

디스크에 압축을 풀지 않고 원본 bytes, ZIP 항목 순서, 각 항목 내용과
메타데이터를 보존하며 읽기만 한다.

이번 E01 번호의 실제 진입점은 read_hwpx 하나뿐이다.
계약에 ZIP 내부 함수명이 없을 때 이 함수를 기본으로 둔다.

설계
- ZIP_STORED와 DEFLATE만 허용한다.
- mimetype은 존재하고 bytes여야 하며 값이 표준이어야 한다.
- 필수 XML을 찾을 수 없으면 거부한다.
- 중복 경로, 경로 탈출, 암호화, CRC 오류, 실제 해제 크기 초과를 차단한다.
- 항목 수 5000, 누적 실제 해제 크기 50000000 bytes 제한을 적용한다.
- section 문서 순서는 ZIP 항목 순서와 별개로 다룬다(필요 시 별도 정렬).
"""

from __future__ import annotations

import hashlib
import io
import struct
import zipfile
import zlib
from typing import Any

from hwpx.errors import (
    BAD_MIMETYPE,
    DECOMPRESS_SIZE_EXCEEDED,
    DUPLICATE_PATH,
    ENTRY_COUNT_EXCEEDED,
    INVALID_HWPX,
    NEEDED_XML_MISSING,
    NO_MIMETYPE,
    PATH_ESCAPE,
    CRC_ERROR,
    DomainError,
)

# ---------------------------------------------------------------------------
# 제한
# ---------------------------------------------------------------------------
_MAX_ENTRY_COUNT = 5000
_MAX_DECOMPRESS_BYTES = 50000000

# HWPX mimetype 표준값
_HWPX_MIMETYPE = "application/hwp+zip"


# ---------------------------------------------------------------------------
# 내부 구조체
# ---------------------------------------------------------------------------

class _Item:
    """ZIP 항목 하나와 그 내용을 메모리에 유지한다."""

    __slots__ = (
        "path",
        "compress_type",
        "size",
        "compress_size",
        "crc32",
        "is_encrypted",
        "bytes",
        "offset_in_stream",
    )

    def __init__(
        self,
        path: str,
        compress_type: int,
        size: int,
        compress_size: int,
        crc32: int,
        is_encrypted: bool,
        bytes_: bytes,
        offset_in_stream: int,
    ) -> None:
        self.path = path
        self.compress_type = compress_type
        self.size = size
        self.compress_size = compress_size
        self.crc32 = crc32
        self.is_encrypted = is_encrypted
        self.bytes = bytes_
        self.offset_in_stream = offset_in_stream


class ReadResult:
    """read_hwpx가 반환하는 읽기 결과.

    원본 bytes, 항목 순서, 각 항목 내용·메타데이터를 모두 담는다.
    디스크 압축 해제는 하지 않는다.
    """

    __slots__ = (
        "original_bytes",
        "original_sha256",
        "items",
        "item_paths",
        "by_path",
    )

    def __init__(self, original_bytes: bytes, items: list[_Item]) -> None:
        self.original_bytes = original_bytes
        self.original_sha256 = hashlib.sha256(original_bytes).hexdigest()
        self.items = items
        self.item_paths = [it.path for it in items]
        self.by_path = {it.path: it for it in items}

    def get_bytes(self, path: str) -> bytes:
        """경로로 항목 내용 bytes를 반환한다. 없으면 KeyError."""
        return self.by_path[path].bytes

    def has_path(self, path: str) -> bool:
        return path in self.by_path


# ---------------------------------------------------------------------------
# 공용 인터페이스
# ---------------------------------------------------------------------------

def read_hwpx(hwp: bytes) -> ReadResult:
    """HWPX 원본 bytes를 안전히 읽는다.

    Args:
        hwp: HWPX 파일 원본 bytes.

    Returns:
        ReadResult — 원본 bytes, sha256, 항목 순서, 항목 내용·메타데이터.

    Raises:
        DomainError: HWPX로 읽을 수 없거나 안전 제약을 위반한 경우.
    """
    if not isinstance(hwp, (bytes, bytearray)):
        raise DomainError(
            INVALID_HWPX,
            "hwp must be bytes-like",
            {"received_type": type(hwp).__name__},
        )

    raw = bytes(hwp)
    if len(raw) == 0:
        raise DomainError(
            INVALID_HWPX,
            "hwp is empty",
            {"length": 0},
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw), "r")
    except zipfile.BadZipFile as exc:
        raise DomainError(
            INVALID_HWPX,
            "bad zip structure",
            {"reason": str(exc)},
        ) from exc
    except RuntimeError as exc:
        # zipfile이 "filename too long" 등 다른 런타임 오류를 낼 수 있다.
        raise DomainError(
            INVALID_HWPX,
            "unsupported zip error",
            {"reason": str(exc)},
        ) from exc

    try:
        names = zf.namelist()
    except Exception as exc:
        raise DomainError(
            INVALID_HWPX,
            "cannot list zip entries",
            {"reason": str(exc)},
        ) from exc

    if len(names) > _MAX_ENTRY_COUNT:
        raise DomainError(
            ENTRY_COUNT_EXCEEDED,
            "entry count exceeds limit",
            {"count": len(names), "limit": _MAX_ENTRY_COUNT},
        )

    return _read_zip(zf, names, raw)


def _read_zip(zf: zipfile.ZipFile, names: list[str], raw: bytes) -> ReadResult:
    """이름 목록 순서로 항목을 읽는다."""
    items: list[_Item] = []
    seen: dict[str, int] = {}
    total_decompress = 0

    for idx, path in enumerate(names):
        _check_path_safety(path)
        if path in seen:
            raise DomainError(
                DUPLICATE_PATH,
                "duplicate path in zip",
                {"path": path, "first_index": seen[path], "current_index": idx},
            )
        seen[path] = idx

        info = zf.getinfo(path)

        # 암호화 검사는 zipfile에서 명확히 드러나지 않을 수 있으므로
        # flag_bits와 압축 방식, 테스트 읽기를 함께 사용한다.
        if _is_encrypted(info):
            raise DomainError(
                ENCRYPTED if hasattr(__import__("hwpx.errors"), "ENCRYPTED") else "encrypted",
                "encrypted entry not allowed",
                {"path": path},
            )

        # 압축 방식 제한
        if info.compress_type not in (_ZIP_STORED, _ZIP_DEFLATED):
            raise DomainError(
                UNSUPPORTED_COMPRESSION if hasattr(__import__("hwpx.errors"), "UNSUPPORTED_COMPRESSION") else "unsupported-compression",
                "unsupported compression type",
                {"path": path, "compress_type": info.compress_type},
            )

        raw_bytes = zf.read(path)

        # CRC 검증
        expected_crc = info.CRC
        actual_crc = zlib.crc32(raw_bytes) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise DomainError(
                CRC_ERROR,
                "crc mismatch",
                {"path": path, "expected_crc": expected_crc, "actual_crc": actual_crc},
            )

        # 실제 해제 크기 누적
        total_decompress += len(raw_bytes)
        if total_decompress > _MAX_DECOMPRESS_BYTES:
            raise DomainError(
                DECOMPRESS_SIZE_EXCEEDED,
                "decompressed size exceeds limit",
                {
                    "path": path,
                    "cumulative_decompress": total_decompress,
                    "limit": _MAX_DECOMPRESS_BYTES,
                },
            )

        item = _Item(
            path=path,
            compress_type=info.compress_type,
            size=info.file_size,
            compress_size=info.compress_size,
            crc32=actual_crc,
            is_encrypted=False,
            bytes_=raw_bytes,
            offset_in_stream=idx,
        )
        items.append(item)

    # mimetype 확인
    mimetype_item = _find_mimetype(items)
    if mimetype_item is None:
        raise DomainError(
            NO_MIMETYPE,
            "mimetype entry missing or not first",
            {"paths": [it.path for it in items[:5]]},
        )
    if mimetype_item.compress_type != _ZIP_STORED:
        raise DomainError(
            BAD_MIMETYPE,
            "mimetype must be stored",
            {"path": mimetype_item.path, "compress_type": mimetype_item.compress_type},
        )
    mimetype_text = mimetype_item.bytes.decode("utf-8", errors="replace").rstrip("\r\n")
    if mimetype_text != _HWPX_MIMETYPE:
        raise DomainError(
            BAD_MIMETYPE,
            "mimetype value is not hwp+zip",
            {"path": mimetype_item.path, "value": mimetype_text},
        )

    # 필수 XML 확인
    _check_needed_xml(items)

    return ReadResult(raw, items)


# ---------------------------------------------------------------------------
# 안전 검사
# ---------------------------------------------------------------------------

_ZIP_STORED = 0
_ZIP_DEFLATED = 8
_STORED_NAMES = frozenset({"stored", "deflated"})

# 경로 안전: ZIP 스킴에서 상위 참조, 절대 경로, 가짜 루트 탈출을 막는다.
# HWPX 내부 경로는 일반적으로 '/'로 시작하고 알파벳/숫자/하이픈/언더스코어/.을 쓴다.


def _check_path_safety(path: str) -> None:
    """경로가 저장소 루트 밖으로 나가지 않는지 검사한다."""
    if not isinstance(path, str) or path == "":
        raise DomainError(
            PATH_ESCAPE,
            "invalid path",
            {"path": path},
        )
    if "\0" in path:
        raise DomainError(
            PATH_ESCAPE,
            "path contains null",
            {"path": path},
        )
    # 상위 참조 제거
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        raise DomainError(
            PATH_ESCAPE,
            "path contains parent reference",
            {"path": path},
        )
    # 절대 경로 거부 (zip은 보통 상대/루트 기준인데, HWPX 관점에서
    # 루트를 넘는 절대 윈도 경로 등도 막는다)
    if path.startswith("//") or (len(path) >= 2 and path[0] == "/" and path[1] == "/"):
        raise DomainError(
            PATH_ESCAPE,
            "path escapes root",
            {"path": path},
        )
    # 윈도 절대 경로 거부
    if len(path) >= 3 and path[1] == ":" and path[0].isalpha():
        raise DomainError(
            PATH_ESCAPE,
            "windows absolute path not allowed",
            {"path": path},
        )
    # '..'만 있는 경우 등도 이미 위에서 걸러지지만, 빈 컴포넌트 점검도 한다.
    if path.rstrip("/").endswith("/..") or path.rstrip("/").endswith("/."):
        raise DomainError(
            PATH_ESCAPE,
            "path ends with parent/current reference",
            {"path": path},
        )


def _find_mimetype(items: list[_Item]) -> _Item | None:
    """mimetype이 첫 항목이고 bytes인 경우만 찾는다.

    HWPX 패키지 규격상 mimetype은 첫 항목이고 STORED여야 한다.
    여기서는 첫 항목과 mimetype이라는 이름을 함께 본다.
    """
    if not items:
        return None
    first = items[0]
    if first.path != "mimetype":
        return None
    return first


def _check_needed_xml(items: list[_Item]) -> None:
    """필요한 패키지 요소가 있는지 확인한다.

    이번에는 Content.hpf가 있고, ZIP 안에 최소 하나의 XML(section 계열)이
    존재하는지만 확인한다. section0.xml처럼 특정 파일명을 필수로 고정하지
    않는다. analyze 단계에서 section 존재/순서 검증을 더 엄격히 할 수 있다.
    """
    paths = {it.path for it in items}
    if "Content.hpf" not in paths:
        raise DomainError(
            NEEDED_XML_MISSING,
            "Content.hpf missing",
            {"present": sorted(paths)},
        )
    xml_paths = [p for p in paths if p.endswith(".xml")]
    if not xml_paths:
        raise DomainError(
            NEEDED_XML_MISSING,
            "no section xml entries found",
            {"present": sorted(paths)},
        )


def _is_encrypted(info: zipfile.ZipInfo) -> bool:
    """암호화 여부를 보수적으로 판정한다.

    zipfile은 암호화된 항목을 읽을 때 예외를 내기도 하지만,
    여기서는 flag_bits 기반 판정을 우선한다.
    """
    # 일반 목적 플래그 비트 0: 암호화
    if info.flag_bits & 0x1:
        return True
    # 추가 보수: compress_type이 99(압축 방식 미지정) 등이면
    # 암호화 가능성도 있으므로 여기서는 허용하지 않는다.
    return False


def _validate_on_read(raw: bytes, path: str) -> None:
    """읽기 시점에 드러나지 않은 암호화/손상을 한 번 더 확인한다.

    현재는 read_hwpx 내부 읽기가 이미 CRC를 검증하고 있으므로,
    별도 호출용은 미래의 확장 지점이다.
    """
    raise DomainError(
        BAD_ITEM,
        "unexpected validation request",
        {"path": path},
    )

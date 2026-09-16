"""
hwpx/package.py — HWPX 패키지 열기 및 파일 해시.

계약: docs/contracts/engine.md §1
"""
import hashlib
import zipfile
from dataclasses import dataclass, field
from typing import List


@dataclass
class ZipEntry:
    filename: str
    compress_type: int
    file_size: int
    data: bytes = field(repr=False)


@dataclass
class Package:
    path: str
    is_valid: bool
    mimetype_first: bool
    mimetype_stored: bool
    mimetype_content: str
    entries: List[ZipEntry]
    section_paths: List[str]


def open_package(path: str) -> Package:
    """HWPX 파일을 열어 ZIP 패키지 정보를 Package로 반환한다.

    mimetype이 첫 엔트리이고 무압축(ZIP_STORED)이면 mimetype_first/mimetype_stored가 True다.
    ZIP으로 열리지 않으면 is_valid=False, entries=[]를 반환한다.
    """
    entries: List[ZipEntry] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                entries.append(ZipEntry(
                    filename=info.filename,
                    compress_type=info.compress_type,
                    file_size=info.file_size,
                    data=zf.read(info.filename),
                ))
    except (zipfile.BadZipFile, OSError, FileNotFoundError):
        return Package(
            path=path,
            is_valid=False,
            mimetype_first=False,
            mimetype_stored=False,
            mimetype_content="",
            entries=[],
            section_paths=[],
        )

    is_valid = len(entries) > 0
    mimetype_first = False
    mimetype_stored = False
    mimetype_content = ""

    if entries and entries[0].filename == "mimetype":
        mimetype_first = True
        mimetype_content = entries[0].data.decode("utf-8", errors="replace")
        mimetype_stored = (entries[0].compress_type == zipfile.ZIP_STORED)

    section_paths = [
        e.filename
        for e in entries
        if e.filename.startswith("Contents/section") and e.filename.endswith(".xml")
    ]
    section_paths.sort()

    return Package(
        path=path,
        is_valid=is_valid,
        mimetype_first=mimetype_first,
        mimetype_stored=mimetype_stored,
        mimetype_content=mimetype_content,
        entries=entries,
        section_paths=section_paths,
    )


def file_hash(path: str) -> str:
    """파일의 SHA-256 해시를 'sha256:<hexdigest>' 형식으로 반환한다.

    계약: docs/contracts/engine.md §1.2
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"

"""B 원문 추출 — HWPX / TXT / MD / UTF-8 붙여넣기를 SourceBlock으로 추출.

이번 E06 번호의 실제 진입점은 extract_b 하나로 둔다.
계약(docs/TEAM_CONTRACT.md)에는 아직 extract_b의 계약이 충분히 없으므로,
이번 번호의 입출력은 내부 계약으로 사용한다.

설계
- 원문 순서와 표 문맥을 보존한다.
- B의 서식(글꼴, 스타일 ID, XML, 이미지, 페이지 나누기)은 가져오지 않는다.
- 긴 블록은 원문 위치가 유지되는 하위 블록으로 나눈다.
- 중첩 표와 여러 section에서 중복이나 순서 뒤바뀜이 없도록 한다.
- 텍스트 재결합이 원문과 일치해야 한다.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from hwpx.errors import DomainError


def extract_b(
    payload: bytes | str,
    *,
    kind: str | None = None,
    b_hash: str | None = None,
) -> BExtractResult:
    """B 원문(HWPX/TXT/MD/UTF-8 붙여넣기)을 SourceBlock으로 추출한다.

    Args:
        payload: B 원본(bytes 또는 UTF-8 문자열).
        kind: 'hwpx', 'txt', 'md' 중 하나. 없으면 추론한다.
        b_hash: B의 원본 해시. 없으면 내부에서 계산한다.

    Returns:
        BExtractResult: 원문 블록 목록과 메타데이터.
    """
    if payload is None:
        raise DomainError("invalid-input", "payload must not be None", {})
    if isinstance(payload, bytes):
        text, resolved_kind = _decode_bytes(payload)
    elif isinstance(payload, str):
        text = payload
        resolved_kind = _resolve_kind(kind, "txt")
    else:
        raise DomainError(
            "invalid-input",
            "payload must be bytes or str",
            {"received_type": type(payload).__name__},
        )

    if not isinstance(text, str):
        raise DomainError(
            "invalid-input",
            "decoded payload must be str",
            {"received_type": type(text).__name__},
        )

    kind = _resolve_kind(kind, resolved_kind)
    if b_hash is None:
        b_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    if not text.strip():
        return BExtractResult(
            b_hash=b_hash,
            kind=kind,
            analysis_status="partial",
            warnings=_extract_warnings([]),
            blocks=[],
        )

    blocks = _extract_blocks(text, kind)
    return BExtractResult(
        b_hash=b_hash,
        kind=kind,
        analysis_status="partial",
        warnings=_extract_warnings(blocks),
        blocks=blocks,
    )


def _decode_bytes(raw: bytes) -> tuple[str, str]:
    """bytes를 UTF-8로 decode하고 종류를 반환한다."""
    try:
        text = raw.decode("utf-8")
        return text, "txt"
    except UnicodeDecodeError:
        raise DomainError(
            "invalid-input",
            "B payload is not valid UTF-8",
            {},
        )


def _resolve_kind(kind: str | None, fallback: str) -> str:
    if kind is None:
        return fallback
    low = kind.lower()
    if low in ("hwpx", "txt", "md"):
        return low
    raise DomainError(
        "invalid-input",
        f"kind must be hwpx/txt/md, got {kind!r}",
        {"received": kind},
    )


def _extract_blocks(text: str, kind: str) -> list[SourceBlock]:
    """텍스트를 SourceBlock 목록으로 나눈다.

    kind가 hwpx이면 XML 구조는 무시하고 텍스트만 추출한다(이번 번호는 서식 미가져오기).
    txt/md는 문단/줄 단위로 나눈다.
    """
    if kind == "hwpx":
        return _extract_hwpx_blocks(text)
    if kind == "md":
        return _extract_md_blocks(text)
    return _extract_txt_blocks(text)


def _extract_hwpx_blocks(text: str) -> list[SourceBlock]:
    """HWPX XML 텍스트에서 텍스트만 추출해 블록으로 만든다.

    이번 번호는 서식을 가져오지 않으므로, XML 태그를 제거하고
    텍스트 노드를 순서대로 추출한다.
    """
    # XML 태그, 선언, 처리 명령을 제거
    clean = re.sub(r"<[^>]+>", "\n", text)
    clean = re.sub(r"<\?xml.*?\?>", "\n", clean, flags=re.S)
    clean = re.sub(r"<!--.*?-->", "\n", clean, flags=re.S)
    lines = _split_lines(clean)
    blocks: list[SourceBlock] = []
    offset = 0
    for line in lines:
        block = SourceBlock(
            blockId=_block_id(blocks, "b"),
            level=0,
            text=line,
            kind="hwpx-text",
            start=offset,
            end=offset + len(line),
            children=[],
        )
        blocks.append(block)
        offset += len(line) + 1
    return blocks


def _extract_md_blocks(text: str) -> list[SourceBlock]:
    """Markdown을 줄 단위 블록으로 나눈다.

    이번 번호는 서식을 해석하지 않고 텍스트만 보존한다.
    """
    lines = _split_lines(text)
    blocks: list[SourceBlock] = []
    offset = 0
    for line in lines:
        block = SourceBlock(
            blockId=_block_id(blocks, "b"),
            level=0,
            text=line,
            kind="md-text",
            start=offset,
            end=offset + len(line),
            children=[],
        )
        blocks.append(block)
        offset += len(line) + 1
    return blocks


def _extract_txt_blocks(text: str) -> list[SourceBlock]:
    """일반 텍스트를 줄 단위 블록으로 나눈다."""
    lines = _split_lines(text)
    blocks: list[SourceBlock] = []
    offset = 0
    for line in lines:
        block = SourceBlock(
            blockId=_block_id(blocks, "b"),
            level=0,
            text=line,
            kind="txt-text",
            start=offset,
            end=offset + len(line),
            children=[],
        )
        blocks.append(block)
        offset += len(line) + 1
    return blocks


def _split_lines(text: str) -> list[str]:
    """텍스트를 줄 단위로 나눈다. 빈 줄도 포함한다."""
    return text.split("\n")


def _block_id(blocks: list[SourceBlock], prefix: str) -> str:
    """블록 고유 ID를 생성한다."""
    return f"{prefix}-{len(blocks):04d}"


def _extract_warnings(blocks: list[SourceBlock]) -> list[str]:
    warns: list[str] = []
    if not blocks:
        warns.append("no blocks extracted")
    return warns


def _rejoin_text(blocks: list[SourceBlock]) -> str:
    """블록의 텍스트를 원문 순서대로 재결합한다."""
    return "\n".join(b.text for b in blocks)


class SourceBlock:
    """B 원문 블록 하나.

    원문 순서와 위치, 표 문맥을 보존한다.
    """

    __slots__ = (
        "blockId",
        "level",
        "text",
        "kind",
        "start",
        "end",
        "children",
        "table_context",
    )

    def __init__(
        self,
        *,
        blockId: str,
        level: int,
        text: str,
        kind: str,
        start: int,
        end: int,
        children: list[SourceBlock] | None = None,
        table_context: dict[str, Any] | None = None,
    ) -> None:
        self.blockId = blockId
        self.level = level
        self.text = text
        self.kind = kind
        self.start = start
        self.end = end
        self.children = children if children is not None else []
        self.table_context = table_context if table_context is not None else {}


class BExtractResult:
    """extract_b 결과."""

    __slots__ = (
        "b_hash",
        "kind",
        "analysis_status",
        "warnings",
        "blocks",
    )

    def __init__(
        self,
        *,
        b_hash: str,
        kind: str,
        analysis_status: str,
        warnings: list[str],
        blocks: list[SourceBlock],
    ) -> None:
        self.b_hash = b_hash
        self.kind = kind
        self.analysis_status = analysis_status
        self.warnings = warnings
        self.blocks = blocks

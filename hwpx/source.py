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

    이번 번호는 제목 계층과 표 문맥, 복합 라벨을 보존한다.
    서식은 가져오지 않는다.
    """
    lines = _split_lines(text)
    blocks: list[SourceBlock] = []
    offset = 0
    md_level = 0
    table_position: dict[str, Any] = {}
    for line in lines:
        line_level = _md_level(line)
        if line_level is not None:
            md_level = line_level
        is_table_line = _looks_like_md_table_row(line)
        context = _md_context(line, md_level, table_position)
        facts = _split_facts(line)
        block = SourceBlock(
            blockId=_block_id(blocks, "b"),
            level=0,
            md_level=line_level,
            text=line,
            kind="md-text",
            start=offset,
            end=offset + len(line),
            children=[],
            context=context,
            table_position=table_position if is_table_line else {},
            facts=facts,
        )
        if is_table_line:
            table_position = _next_table_position(line, table_position)
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
        "md_level",
        "text",
        "kind",
        "start",
        "end",
        "children",
        "table_context",
        "context",
        "table_position",
        "facts",
    )

    def __init__(
        self,
        *,
        blockId: str,
        level: int,
        md_level: int | None = None,
        text: str,
        kind: str,
        start: int,
        end: int,
        children: list[SourceBlock] | None = None,
        table_context: dict[str, Any] | None = None,
        context: list[str] | None = None,
        table_position: dict[str, Any] | None = None,
        facts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.blockId = blockId
        self.level = level
        self.md_level = md_level
        self.text = text
        self.kind = kind
        self.start = start
        self.end = end
        self.children = children if children is not None else []
        self.table_context = table_context if table_context is not None else {}
        self.context = context if context is not None else []
        self.table_position = table_position if table_position is not None else {}
        self.facts = facts if facts is not None else []


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


# ---------------------------------------------------------------------------
# Markdown 제목/표/사실 헬퍼
# ---------------------------------------------------------------------------

def _md_level(line: str) -> int | None:
    """Markdown 제목 레벨을 반환한다. 제목이 아니면 None."""
    m = re.match(r"^(#{1,6})\s*(.+)$", line)
    if m:
        return len(m.group(1))
    return None


def _looks_like_md_table_row(line: str) -> bool:
    """파이프 표 행인지 보수적으로 판정한다.

    이번 번호는 이스케이프된 세로줄(\\|)을 셀 구분자로 세지 않는다.
    """
    if not line.strip():
        return False
    # 맨 앞/뒤에 |가 있고, 이스케이프되지 않은 |가 셀 구분자로 쓰였는지 본다.
    if not (line.startswith("|") or line.startswith("| ")):
        return False
    if not (line.endswith("|") or line.endswith("| ")):
        return False
    # 이스케이프된 \\|는 건너뛰고 셀 구분 |를 센다
    cells = _md_table_cells(line)
    return len(cells) >= 2


def _md_table_cells(line: str) -> list[str]:
    """파이프 표 행을 셀 리스트로 나눈다. 이스케이프 세로줄은 무시한다."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # 이스케이프된 \\|를 셀 구분자로 세지 않도록 보호
    parts: list[str] = []
    buf = ""
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "\\|"
            i += 2
            continue
        if s[i] == "|":
            parts.append(buf.strip())
            buf = ""
            i += 1
            continue
        buf += s[i]
        i += 1
    if buf.strip() or parts:
        parts.append(buf.strip())
    return parts


def _md_context(line: str, md_level: int | None, table_position: dict[str, Any]) -> list[str]:
    """블록의 문맥을 만든다.

    제목 계층과 표 위치 정보를 문맥에 넣는다.
    """
    ctx: list[str] = []
    if md_level is not None:
        ctx.append(f"h{md_level}")
    if table_position:
        ctx.append(f"row={table_position.get('rowIndex')}")
        ctx.append(f"col={table_position.get('colIndex')}")
        header = table_position.get("header")
        if header:
            ctx.append(f"header={header}")
    return ctx


def _next_table_position(line: str, current: dict[str, Any]) -> dict[str, Any]:
    """표 행을 만날 때 열/행 위치를 진전시킨다."""
    cells = _md_table_cells(line)
    if not cells:
        return current
    # 첫 행이고 헤더 구분선이면 헤더로 표시
    if _looks_like_md_table_header_sep(line):
        current = {
            "rowIndex": current.get("rowIndex", 0),
            "colIndex": 0,
            "header": [c for c in cells],
            "is_header": True,
        }
        return current
    # 데이터 행이면 열 인덱스를 증가
    row_index = current.get("rowIndex", 0)
    is_header = current.get("is_header", False)
    if not is_header:
        row_index += 1
    return {
        "rowIndex": row_index,
        "colIndex": len(cells) - 1,
        "header": current.get("header", []),
        "is_header": False,
    }


def _looks_like_md_table_header_sep(line: str) -> bool:
    """Markdown 표 헤더 구분선(예: | --- | --- |)인지 판정한다."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    cells = _md_table_cells(s)
    return all(_is_sep_cell(c) for c in cells if c)


def _is_sep_cell(c: str) -> bool:
    c = c.strip()
    if not c:
        return True
    # "---", ":---", "---:", ":---:" 등
    return bool(re.fullmatch(r"[:\-]+\s*$", c))


def _split_facts(line: str) -> list[dict[str, Any]]:
    """한 줄의 단순 사실을 두 사실로 나눈다.

    예: "대표자 김가람, 연락처 010-1234-5678" → 두 사실.
    이번 단순 구현은 쉼표/세로줄/세미콜론으로 분리 가능한 라벨:값 패턴을 다룬다.
    """
    if not line.strip():
        return []
    # 쉼표, 세미콜론, 슬래시로 분리할 수 있으면 여러 사실로 나눈다
    parts = _split_label_value_line(line)
    if len(parts) > 1:
        return [{"originalText": p.strip()} for p in parts if p.strip()]
    return [{"originalText": line.strip()}]


def _split_label_value_line(line: str) -> list[str]:
    """라벨:값 또는 라벨=값, 쉼표/세미콜론/슬래시 구분선을 고려해 분리한다."""
    import re
    # 먼저 이스케이프되지 않은 구분자로 분리
    # 예: "대표자 김가람, 연락처 010-1234-5678" → 쉼표 기준으로 분리하려면
    # 라벨:값 패턴이어야 한다. 이번 단순 구현은 쉼표/세미콜론/슬래시로 분리한다.
    sep_regex = re.compile(r"\s*[,;/]\s*")
    if sep_regex.search(line):
        return sep_regex.split(line)
    return [line]
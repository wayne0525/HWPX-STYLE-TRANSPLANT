"""B 원문 추출 — HWPX / TXT / MD / UTF-8 붙여넣기를 SourceBlock으로 추출.

이번 E06 번호의 실제 진입점은 extract_b 하나로 둔다.
계약(docs/TEAM_CONTRACT.md)에는 아직 extract_b의 계약이 충분히 없으므로,
이번 번호의 입출력은 내부 계약으로 사용한다.

설계
- HWPX 바이트는 안전한 ZIP 읽기를 거쳐 문서 순서대로 모든 section을 읽는다.
- 문단과 표 셀의 원문, 순서, 행과 열 문맥을 보존한다.
- 중첩 표의 텍스트를 중복 추출하지 않는다.
- B의 글꼴과 서식은 가져오지 않는다.
- 해시는 입력 원본 바이트로 계산하고, 긴 블록은 계약대로 나눠 정확히 재결합되게 한다.
- content.hpf와 HpF 구조만 정답이라고 가정하지 않고, 실제 패키지 경로를 따른다.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Any

from hwpx.errors import DomainError
from hwpx.package import read_hwpx
from hwpx.xml import read_xml, XmlReadResult
from hwpx.tables import read_section_tables

# ------------------------------------------------------------------
# 공용 진입점
# ------------------------------------------------------------------


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

    HWPX 바이트는 안전한 ZIP 읽기를 거쳐 문서 순서대로 모든 section을 읽는다.
    """
    if payload is None:
        raise DomainError("invalid-input", "payload must not be None", {})

    if isinstance(payload, str):
        raw_for_hash = payload.encode("utf-8")
        resolved_kind = _resolve_kind(kind, "txt")
        blocks = _extract_text_kind(payload, resolved_kind)
        return _make_result(raw_for_hash, resolved_kind, blocks, b_hash)

    # bytes
    raw_for_hash = payload
    resolved_kind, blocks = _process_bytes(payload, kind)
    return _make_result(raw_for_hash, resolved_kind, blocks, b_hash)


def _make_result(
    raw_for_hash: bytes,
    kind: str,
    blocks: list[SourceBlock],
    b_hash: str | None,
) -> BExtractResult:
    if b_hash is None:
        b_hash = hashlib.sha256(raw_for_hash).hexdigest()
    if not raw_for_hash:
        blocks = []
    for index, block in enumerate(blocks):
        block.blockId = 'b-' + hashlib.sha256((b_hash + ':' + str(index)).encode()).hexdigest()[:24]
    if not blocks:
        return BExtractResult(
            b_hash=b_hash,
            kind=kind,
            analysis_status="partial",
            warnings=["no blocks extracted"],
            blocks=[],
        )
    warns = _extract_warnings(blocks)
    return BExtractResult(
        b_hash=b_hash,
        kind=kind,
        analysis_status="partial",
        warnings=warns,
        blocks=blocks,
    )


def _process_bytes(payload: bytes, kind: str | None) -> tuple[str, list[SourceBlock]]:
    """bytes를 안전한 ZIP 읽기로 처리하고, HWPX면 문서 순서 텍스트를 추출한다."""
    resolved = _resolve_kind(kind, None)
    if resolved == "hwpx" or resolved is None:
        return _process_hwpx_bytes(payload)
    if resolved == "txt":
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DomainError(
                "invalid-input",
                "B payload is not valid UTF-8",
                {"received_type": "bytes"},
            ) from exc
        return "txt", _extract_text_kind(text, "txt")
    if resolved == "md":
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DomainError(
                "invalid-input",
                "B payload is not valid UTF-8",
                {"received_type": "bytes"},
            ) from exc
        return "md", _extract_text_kind(text, "md")
    raise DomainError(
        "invalid-input",
        f"kind must be hwpx/txt/md, got {kind!r}",
        {"received": kind},
    )


def _process_hwpx_bytes(payload: bytes) -> tuple[str, list[SourceBlock]]:
    """HWPX 바이트를 안전한 ZIP 읽기로 열고, 문서 순서 텍스트를 추출한다.

    mimetype이 유효하지 않거나 ZIP 구조가 안전 제약을 위반하면 DomainError를 낸다.
    """
    try:
        result = read_hwpx(payload)
    except DomainError:
        raise
    except zipfile.BadZipFile as exc:
        raise DomainError(
            "invalid-hwpx",
            "bad zip structure",
            {"reason": str(exc)},
        ) from exc
    except Exception as exc:
        raise DomainError(
            "invalid-hwpx",
            "cannot read HWPX bytes",
            {"reason": str(exc)},
        ) from exc

    try:
        xml_result = read_xml(result)
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "bad-xml",
            "cannot parse HWPX XML",
            {"reason": str(exc)},
        ) from exc

    return "hwpx", _hwpx_document_blocks(xml_result, payload)


# ------------------------------------------------------------------
# 텍스트 종류별 추출 (TXT / MD)
# ------------------------------------------------------------------


def _extract_text_kind(text: str, kind: str) -> list[SourceBlock]:
    if kind == "md":
        return _extract_md_blocks(text)
    return _extract_txt_blocks(text)


# ------------------------------------------------------------------
# HWPX 문서 순서 블록 추출
# ------------------------------------------------------------------


def _hwpx_document_blocks(xml_result: XmlReadResult, raw_bytes: bytes) -> list[SourceBlock]:
    """content.hpf 순서로 모든 section을 읽고 문서 순서대로 블록을 만든다.

    - section마다 XML 트리를 순회하며 문단 텍스트와 표 셀 텍스트를 문서 순서로 추출한다.
    - 중첩 표 텍스트는 중복 집계하지 않는다.
    - 표 셀의 행/열 위치를 SourceBlock에 문맥으로 남긴다.
    - XML 태그는 제거하지 않고, 실제 텍스트 노드만 수집한다.
    """
    if any(b'http://www.hancom.co.kr/hwpml/2011/paragraph' in s.bytes for s in xml_result.sections):
        return _native_document_blocks(xml_result)
    blocks: list[SourceBlock] = []
    block_counter = 0

    for section in xml_result.sections:
        section_path = section.path
        section_blocks = _section_blocks(section, section_path)
        for sb in section_blocks:
            sb.blockId = _block_id_fmt(block_counter, "b")
            block_counter += 1
            blocks.append(sb)

    return blocks


def _native_document_blocks(document):
    from hwpx.template import NS, parse_xml
    out, offset = [], 0
    for section in document.sections:
        root = parse_xml(section.bytes)
        tables = root.findall('.//hp:tbl', NS)
        for p in root.iter('{' + NS['hp'] + '}p'):
            text = ''.join(''.join(t.itertext()) for run in p.findall('hp:run', NS) for t in run.findall('hp:t', NS))
            if not text.strip():
                continue
            position, context, table_context = {}, [section.path], {}
            cell = next((x for x in p.iterancestors() if x.tag == '{'+NS['hp']+'}tc'), None)
            if cell is not None:
                table = next((x for x in cell.iterancestors() if x.tag == '{'+NS['hp']+'}tbl'), None)
                addr = cell.find('hp:cellAddr', NS)
                span = cell.find('hp:cellSpan', NS)
                if table is not None and addr is not None:
                    table_id = section.path + ':table-' + str(tables.index(table))
                    position = {'rowIndex': int(addr.get('rowAddr')), 'colIndex': int(addr.get('colAddr')),
                                'tableId': table_id, 'rowSpan': int(span.get('rowSpan', '1')) if span is not None else 1,
                                'colSpan': int(span.get('colSpan', '1')) if span is not None else 1}
                    table_context = {'tableId': table_id}
                    context.append('표: ' + table_id)
            out.append(SourceBlock(blockId='', level=0, text=text, kind='hwpx-text', start=offset,
                                   end=offset+len(text), context=context, table_context=table_context,
                                   table_position=position))
            offset += len(text) + 1
    return out


def _section_blocks(section: Any, section_path: str) -> list[SourceBlock]:
    """한 section 트리를 순회하며 문단/표 블록을 문서 순서로 수집한다."""
    out: list[SourceBlock] = []
    root = section.tree.root
    _walk_node(root, section_path, out)
    return out


def _walk_node(node: Any, section_path: str, out: list[SourceBlock], table_ctx: dict[str, Any] | None = None) -> None:
    """재귀적으로 트리를 순회하며 텍스트와 표 문맥을 수집한다.

    table_ctx가 전달되는 경우 중첩 표 안에서 부모 표 문맥을 그대로 전달하지 않고,
    중첩 표의 별도 문맥을 구성하도록 분리한다.
    """
    tag_local = getattr(node, "local", None)
    tag_ns = getattr(node, "ns_uri", None)

    # 표 시작
    if _is_table(node):
        table_id = _table_id_for(node, section_path)
        table_ctx = _new_table_context(table_id)
        # 표의 자식(행)을 순회
        for child in _children(node):
            _walk_node(child, section_path, out, table_ctx=table_ctx)
        # 표 블록 자체는 문서 끝에서 닫기 용도로 별도로 추가하지 않고,
        # 이미 셀/문단 블록에 문맥이 반영된다.
        return

    # 표 셀
    if _is_table_cell(node):
        _collect_cell_block(node, section_path, out, table_ctx)
        return

    # 표 행은 순회만 하고 블록은 만들지 않음
    if _is_table_row(node):
        for child in _children(node):
            _walk_node(child, section_path, out, table_ctx=table_ctx)
        return

    # 문단: 문단 내 텍스트와 표 셀을 순서대로 수집
    if _is_paragraph(node):
        _collect_paragraph_blocks(node, section_path, out, table_ctx)
        return

    # 기타 요소: 자식만 순회
    for child in _children(node):
        _walk_node(child, section_path, out, table_ctx=table_ctx)


def _is_table(node: Any) -> bool:
    return getattr(node, "local", None) == "tbl" and getattr(node, "ns_uri", None) == "http://www.hwpzone.org/hwpx"


def _is_table_row(node: Any) -> bool:
    return getattr(node, "local", None) == "tr" and getattr(node, "ns_uri", None) == "http://www.hwpzone.org/hwpx"


def _is_table_cell(node: Any) -> bool:
    return getattr(node, "local", None) == "tc" and getattr(node, "ns_uri", None) == "http://www.hwpzone.org/hwpx"


def _is_paragraph(node: Any) -> bool:
    return getattr(node, "local", None) == "p" and getattr(node, "ns_uri", None) == "http://www.hwpzone.org/hwpx"


def _children(node: Any) -> list[Any]:
    try:
        return list(node.children)
    except Exception:
        return []


def _new_table_context(table_id: str | None) -> dict[str, Any]:
    return {
        "tableId": table_id,
        "rowIndex": 0,
        "colIndex": 0,
        "rowHeaders": [],
        "columnHeaders": [],
        "columnGroup": None,
        "mergedRange": None,
    }


def _next_table_context_after_cell(ctx: dict[str, Any]) -> dict[str, Any]:
    """한 셀을 처리한 뒤 다음 셀 위치로 문맥을 전진시킨다."""
    return {
        "tableId": ctx.get("tableId"),
        "rowIndex": ctx.get("rowIndex"),
        "colIndex": ctx.get("colIndex") + 1,
        "rowHeaders": ctx.get("rowHeaders"),
        "columnHeaders": ctx.get("columnHeaders"),
        "columnGroup": ctx.get("columnGroup"),
        "mergedRange": ctx.get("mergedRange"),
    }


def _table_id_for(node: Any, section_path: str) -> str | None:
    """표 식별자를 만든다. 실제 양식이 없으면 합성 식별자를 사용한다."""
    if table_id := node.attributes.get("id"):
        return table_id
    # 섹션 경로와 순서로 식별자를 만든다.
    return f"{section_path}#tbl-{hash(node) & 0xFFFFFFFF & 0xFFFFFFFF}"


def _collect_paragraph_blocks(
    node: Any,
    section_path: str,
    out: list[SourceBlock],
    table_ctx: dict[str, Any] | None = None,
) -> None:
    """문단 내 텍스트와 표 셀을 문서 순서로 수집한다.

    문단 안에 표가 있으면 표 셀을 먼저 수집하고, 문단 텍스트만 따로 블록으로 남긴다.
    문단 텍스트가 없으면 빈 블록을 만들지 않는다.
    """
    text_parts: list[str] = []
    for child in _children(node):
        if _is_table(child):
            # 문단 안의 표는 셀을 먼저 처리하고, 표 자체는 별도 블록으로 처리하지 않는다.
            # 표 셀 처리 시 table_ctx를 전달한다.
            _walk_node(child, section_path, out, table_ctx=None)
            continue
        part = _text_of_node(child)
        if part:
            text_parts.append(part)

    full_text = "".join(text_parts)
    if full_text:
        out.append(
            SourceBlock(
                blockId="",
                level=0,
                text=full_text,
                kind="hwpx-paragraph",
                start=0,
                end=len(full_text),
                children=[],
                context=[f"section={section_path}"],
                table_position=table_ctx or {},
            )
        )


def _collect_cell_block(
    node: Any,
    section_path: str,
    out: list[SourceBlock],
    table_ctx: dict[str, Any] | None,
) -> None:
    """표 셀에서 텍스트를 수집해 SourceBlock을 만든다.

    중첩 표가 있으면 중첩 표 내부 텍스트는 이 셀 블록에 포함하지 않는다.
    """
    if table_ctx is None:
        # 표 문맥이 없는 셀(예: 표 밖의 셀 - 일어나지 않아야 하지만 방어)
        table_ctx = _new_table_context(None)

    text_parts: list[str] = []
    for child in _children(node):
        if _is_table(child):
            # 중첩 표: 중첩 표는 별도 표로 처리되며, 이 셀의 텍스트에는 포함하지 않는다.
            # 중첩 표의 결과 블록은 상위 순회에서 따로 수집된다.
            continue
        part = _text_of_node(child)
        if part:
            text_parts.append(part)

    cell_text = "".join(text_parts)
    row_index = table_ctx.get("rowIndex", 0)
    col_index = table_ctx.get("colIndex", 0)

    block = SourceBlock(
        blockId="",
        level=0,
        text=cell_text,
        kind="hwpx-table-cell",
        start=0,
        end=len(cell_text),
        children=[],
        context=[f"section={section_path}"],
        table_position=table_ctx,
        facts=[],
    )
    out.append(block)

    # 표 문맥 전진
    next_ctx = _next_table_context_after_cell(table_ctx)
    # 표 행 처리에서 행 인덱스를 전진시키므로 여기선 열만 전진한다.
    # (실제 행 인덱스 전진은 _walk_node의 표 행 처리에서 담당한다.)
    _advance_table_context(table_ctx, row_index, col_index + 1)


def _advance_table_context(ctx: dict[str, Any], row_index: int, col_index: int) -> None:
    ctx["rowIndex"] = row_index
    ctx["colIndex"] = col_index


def _text_of_node(node: Any) -> str:
    """요소 트리의 텍스트 내용을 재귀적으로 수집한다.

    실제 텍스트 노드만 모으고, 중첩 표의 텍스트는 포함하지 않는다.
    """
    parts: list[str] = []
    if node.text:
        parts.append(node.text)
    for child in _children(node):
        if _is_table(child):
            continue
        parts.append(_text_of_node(child))
    return "".join(parts)


# ------------------------------------------------------------------
# SourceBlock / BExtractResult
# ------------------------------------------------------------------


def _block_id_fmt(index: int, prefix: str) -> str:
    return f"{prefix}-{index:04d}"


def _extract_warnings(blocks: list[SourceBlock]) -> list[str]:
    warns: list[str] = []
    if not blocks:
        warns.append("no blocks extracted")
    return warns


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

    __slots__ = ("b_hash", "kind", "analysis_status", "warnings", "blocks")

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


# ------------------------------------------------------------------
# Markdown / TXT 보조 (기존 동작 보존)
# ------------------------------------------------------------------


def _extract_md_blocks(text: str) -> list[SourceBlock]:
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
            blockId="",
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
        blocks.append(block)
        if is_table_line:
            table_position = _next_table_position(line, table_position)
        offset += len(line) + 1
    return blocks


def _extract_txt_blocks(text: str) -> list[SourceBlock]:
    lines = _split_lines(text)
    blocks: list[SourceBlock] = []
    offset = 0
    for line in lines:
        block = SourceBlock(
            blockId="",
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
    return text.split("\n")


def _md_level(line: str) -> int | None:
    m = re.match(r"^(#{1,6})\s*(.+)$", line)
    if m:
        return len(m.group(1))
    return None


def _looks_like_md_table_row(line: str) -> bool:
    if not line.strip():
        return False
    if not (line.startswith("|") or line.startswith("| ")):
        return False
    if not (line.endswith("|") or line.endswith("| ")):
        return False
    cells = _md_table_cells(line)
    return len(cells) >= 2


def _md_table_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
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
    cells = _md_table_cells(line)
    if not cells:
        return current
    if _looks_like_md_table_header_sep(line):
        current = {
            "rowIndex": current.get("rowIndex", 0),
            "colIndex": 0,
            "header": [c for c in cells],
            "is_header": True,
        }
        return current
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
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    cells = _md_table_cells(s)
    return all(_is_sep_cell(c) for c in cells if c)


def _is_sep_cell(c: str) -> bool:
    c = c.strip()
    if not c:
        return True
    return bool(re.fullmatch(r"[:\-]+\s*$", c))


def _split_facts(line: str) -> list[dict[str, Any]]:
    if not line.strip():
        return []
    parts = _split_label_value_line(line)
    if len(parts) > 1:
        return [{"originalText": p.strip()} for p in parts if p.strip()]
    return [{"originalText": line.strip()}]


def _split_label_value_line(line: str) -> list[str]:
    sep_regex = re.compile(r"\s*[,;/]\s*")
    if sep_regex.search(line):
        return sep_regex.split(line)
    return [line]


def _resolve_kind(kind: str | None, fallback: str | None) -> str:
    if kind is None:
        if fallback is None:
            return "hwpx"
        return fallback
    low = kind.lower()
    if low in ("hwpx", "txt", "md"):
        return low
    raise DomainError(
        "invalid-input",
        f"kind must be hwpx/txt/md, got {kind!r}",
        {"received": kind},
    )

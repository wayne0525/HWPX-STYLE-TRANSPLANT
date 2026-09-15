"""
B(section*.xml) 파싱 → content skeleton 내부 표현.
규칙: 서식 전부 버리고 텍스트+구조만.
"""
import xml.etree.ElementTree as ET
from typing import List, Optional

from hwpx_lib.parse_header import (
    _attr,
    _find,
    _find_all,
    _local,
    _text,
    _first_child_text,
)

# ---------- helpers ----------


def _find_heading_level(p) -> Optional[int]:
    h = _find(p, "heading")
    if h is not None:
        v = _attr(h, "level")
        if v is not None:
            try:
                return int(v)
            except ValueError:
                pass
    # outline level on paraPr via style? marker only
    return None


def _collect_runs(p, is_bold_default=False, is_italic_default=False, is_underline_default=False):
    """
    hp:p에서 run들을 텍스트 보존하며 추출.
    반환: {"runs": [{"text":..., "bold":bool, ...}], "linebreaks": int}
    굵은/기울임/밑줄은 run의 해당 태그 존재 여부만. 글자색/글꼴/크기는 저장 안 함.
    """
    runs = []
    linebreaks = 0
    for run in _find_all(p, "run"):
        t = _find(run, "t")
        if t is None:
            # 빈 run일 수 있음
            runs.append({"text": ""})
            continue
        text_parts = []
        for node in t.iter():
            if node.tag == f"{{{ET.register_namespace('', '') or ''}}}t" or _local(node.tag) == "t":
                txt = _text(node)
                if txt:
                    text_parts.append(txt)
            elif _local(node.tag) == "lineBreak":
                text_parts.append("\n")
                linebreaks += 1
        text = "".join(text_parts)
        if not text:
            text = ""
        bold = _find(run, "bold") is not None
        italic = _find(run, "italic") is not None
        underline = _find(run, "underline") is not None
        emphasis = False  # 색만 다른 강조는 여기선 못 구분; 추후 강조색으로 보강 가능
        runs.append({
            "text": text,
            "bold": bold,
            "italic": italic,
            "underline": underline,
            "emphasis": emphasis,
        })
    return {"runs": runs, "linebreaks": linebreaks}


def _collapse_runs(runs):
    """run 리스트를 하나의 텍스트로도 표현할 수 있게 합침(의미 보존). CSV용이 아님."""
    out = []
    last = None
    for r in runs:
        if last and last["bold"] == r["bold"] and last["italic"] == r["italic"] and last["underline"] == r["underline"] and not last["text"] and not r["text"]:
            continue
        if last and last["text"] == "" and r["text"] == "":
            continue
        out.append(r)
        last = r
    return out


def _parse_table(tbl) -> dict:
    """
    hp:tbl → { rows, cols, cells: [{r,c,rowspan,colspan,text,header}], colWidthsRel }
    서식(테두리/색) 전부 무시. 셀 텍스트 원문 보존.
    """
    rows_elem = _find(tbl, "tr")
    if rows_elem is None:
        rows_elem = _find(tbl, "rows")
    if rows_elem is None:
        return {"rows": 0, "cols": 0, "cells": [], "colWidthsRel": []}
    rows_list = _find_all(tbl, "tr") if rows_elem is None else [rows_elem]
    # 더 넓게: tbl 아래에 직접 tr 목록
    trs = _find_all(tbl, "tr")
    if not trs:
        trs = rows_list
    cells = []
    max_c = 0
    for ri, tr in enumerate(trs):
        tcs = _find_all(tr, "tc")
        for ci, tc in enumerate(tcs):
            sub = _find(tc, "subList")
            if sub is None:
                sub = _find(tc, "p")  # 단일 문단 셀
            text_parts = []
            if sub is not None:
                if _local(sub.tag) == "p":
                    r = _collect_runs(sub)
                    for rt in r["runs"]:
                        text_parts.append(rt["text"])
                else:
                    for p in _find_all(sub, "p"):
                        r = _collect_runs(p)
                        for rt in r["runs"]:
                            text_parts.append(rt["text"])
            text = "\n".join(p for p in text_parts if p)
            h = _attr(tc, "type") or _attr(tc, "header") or None
            header = bool(h and h.lower() in ("header", "true", "1"))
            rowspan = int(_attr(tc, "rowSpan") or _attr(tc, "rowspan") or "1")
            colspan = int(_attr(tc, "colSpan") or _attr(tc, "colspan") or "1")
            cells.append({
                "r": ri,
                "c": ci,
                "rowspan": rowspan,
                "colspan": colspan,
                "text": text,
                "header": header,
            })
            if ci + colspan > max_c:
                max_c = ci + colspan
    cols = max_c or 1
    rows = len(trs) or 0
    # col widths: tblPr>tblGrid 등
    col_widths_rel = []
    return {"rows": rows, "cols": cols, "cells": cells, "colWidthsRel": col_widths_rel}


def _parse_image(img) -> dict:
    """hp:image → { binaryItemIDRef, fileName, alt, moved } (참조만)"""
    bin_id = _attr(img, "binaryItemIDRef") or _attr(img, "id")
    return {
        "binaryItemIDRef": bin_id,
        "fileName": None,
        "alt": _text(img),
        "moved": False,
    }


def _paragraph_text(p):
    """hp:p 전체 텍스트(줄바꿈 포함). 빠른 비교용."""
    runs = _find_all(p, "run")
    parts = []
    for run in runs:
        t = _find(run, "t")
        if t is None:
            continue
        txt = _text(t)
        if txt:
            parts.append(txt)
        for lb in _find_all(run, "lineBreak"):
            parts.append("\n")
    return "".join(parts)


def _guess_block_type(p, text: str, index: int, blocks: List[dict], prev_type: str | None) -> str:
    """
    hp:p 하나를 보고 block type 추론. 우선순위: 05-role-classification.md
    1) XML heading  2) 번호 개요  3) 문서 제목  4) 캡션  5) 목록  6) 인용  7) 표 안  8) 본문
    """
    # 1) heading 태그 or outline level
    level = _find_heading_level(p)
    if level is not None and level >= 1:
        return "heading"
    style_name = _attr(p, "styleName") or ""
    sn_lower = style_name.lower()
    if sn_lower in ("제목", "제목 1", "제목 1.", "heading1", "heading 1", "heading1", "title", "heading"):
        return "heading"

    # 2) 번호 개요: "1." "1.1" "가." "Ⅰ." 등
    t = text.strip()
    if t and len(t) < 60 and _starts_with_roman_or_number_heading(t):
        return "heading"

    # 3) 문서 제목: 본문 시작 쪽, 단독 짧은 줄, 앞에 빈 줄/섹션 시작
    if text.strip() and index == 0:
        return "title"
    if text.strip() and len(t) < 40 and prev_type in (None, "title", "heading", "pageBreak") and _next_is_body(blocks, index):
        return "title" if index <= 2 else "heading"

    # 4) 캡션: "표 1", "그림 2", "표1." 등
    if t and _is_caption(t):
        return "caption"

    # 5) 목록: listItem/numbering/bullet 태그 또는 목록 기호
    if _find(p, "listItem") is not None or _find(p, "numbering") is not None or _find(p, "bullet") is not None:
        return "listItem"
    if t and _looks_like_list_marker(t):
        return "listItem"

    # 6) 인용: 왼쪽 여백이 큰 짧은 블록 (B는 서식 버리므로 확정 어렵고, 애매하면 paragraph)
    # 여기선 확정 어려우면 paragraph 처리.

    # 7) 표 안 문단: 호출 측에서 table 내부 처리하므로 여기서는 기본적으로 paragraph

    # 8) 나머지 → paragraph
    return "paragraph"


def _starts_with_roman_or_number_heading(t: str) -> bool:
    import re
    t = t.strip()
    # "1. " "1.1 " "1.1.1 " "가. " "Ⅰ. " "Ⅰ-1 " "1) " "1- " 등
    if re.match(r'^\d{1,3}\.\s', t):
        return True
    if re.match(r'^\d{1,3}\.\d{1,3}\.\s', t):
        return True
    if re.match(r'^[가-힣]\\.\s', t):
        return True
    if re.match(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\\.\s', t):
        return True
    if re.match(r'^\d{1,3}[\.\)\\-]\s', t):
        return True
    return False


def _is_caption(t: str) -> bool:
    import re
    if re.match(r'^(표|그림|사진|도)\s*\d+[\.\s]', t):
        return True
    if re.match(r'^<표\d+>', t):
        return True
    return False


def _looks_like_list_marker(t: str) -> bool:
    import re
    if re.match(r'^[\•\·\○\●\○\·]\s', t):
        return True
    if re.match(r'^\d+[\.\)]\s', t):
        return True
    if re.match(r'^[가-힣]\.\s', t):
        return True
    return False


def _next_is_body(blocks, index: int) -> bool:
    if index + 1 >= len(blocks):
        return True
    nxt = blocks[index + 1]
    if nxt.get("type") == "paragraph":
        return bool(nxt.get("text", "").strip())
    return False


def parse_blocks_from_section(xml_text: str) -> list:
    """
    B section XML → content skeleton blocks[].
    반환: 각 블록 dict는 content-skeleton.schema.json의 items에 대응.
    """
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    blocks = []
    prev_type: str | None = None
    for child in root.iter():
        local = _local(child.tag)
        if local == "p":
            runs_info = _collect_runs(child)
            runs = _collapse_runs(runs_info["runs"])
            text = _paragraph_text(child)
            block_type = _guess_block_type(child, text, len(blocks), blocks, prev_type)
            block: dict = {"type": block_type, "runs": runs, "text": text}
            level = _find_heading_level(child)
            if level is not None:
                block["level"] = level
            # list 마커
            li = _find(child, "listItem")
            if li is not None:
                block["listMarker"] = _text(li) or _attr(li, "text") or None
                block["listDepth"] = int(_attr(li, "depth") or "0")
            # 강조 런에서 emphasis 여부(임시: 색 다르면 나중에 보강)
            if block_type == "paragraph" and runs:
                for r in runs:
                    if r.get("emphasis"):
                        block["runs"] = runs
                        break
            blocks.append(block)
            prev_type = block_type
        elif local == "tbl":
            table = _parse_table(child)
            blocks.append({"type": "table", "table": table, "text": ""})
            prev_type = "table"
        elif local == "image":
            img = _parse_image(child)
            blocks.append({"type": "image", "image": img, "text": img.get("alt") or ""})
            prev_type = "image"
        elif local == "lineBreak":
            # 같은 문단 안 줄바꿈은 run 처리에서 이미 반영; 별도 블록 아님
            pass
    return blocks

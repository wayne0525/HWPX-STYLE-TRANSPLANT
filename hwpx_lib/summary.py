"""
A 스타일 프로필 + B 내용 골격을 Solar 프롬프트용 요약으로 직렬화.
원칙: 숫자/서식만, 문장X. 사람은 pt/mm/% 단위.
"""
from typing import Any, Dict, List


def summarize_style(profA: Dict[str, Any]) -> Dict[str, Any]:
    """A 스타일 프로필을 Solar에 줄 요약으로 만듦 (문장X)."""
    page = profA.get("page", {}) or {}
    roles = profA.get("roles", {}) or {}
    char_properties = profA.get("charProperties", []) or []
    para_properties = profA.get("paraProperties", []) or []
    border_fills = profA.get("borderFills", []) or []
    styles = profA.get("styles", []) or []
    notes = profA.get("notes", []) or []

    # 본문 대표 슬롯 추정: 최빈 (paraPrIDRef, charPrIDRef) 조합 (표 제외하긴 어려움; 일단은 전체 집계)
    from collections import Counter
    combo = Counter()
    for pp in para_properties:
        pid = pp.get("id")
        for cp in char_properties:
            cid = cp.get("id")
            combo[(pid, cid)] += 1
    body_combo = combo.most_common(1)
    body_pp_id, body_cp_id = (body_combo[0][0] if body_combo else (None, None))

    def find_cp(cid):
        return next((c for c in char_properties if c.get("id") == cid), None)

    def find_pp(pid):
        return next((p for p in para_properties if p.get("id") == pid), None)

    # 역할별 슬롯 요약 (현재 미추론 상태이면 present: false 그대로)
    role_summary = {}
    for name, slot in roles.items():
        if not isinstance(slot, dict):
            continue
        present = slot.get("present", False)
        role_summary[name] = {
            "present": present,
            "source": slot.get("source", "unknown"),
            "charPrIDRef": slot.get("ids", {}).get("charPrIDRef"),
            "paraPrIDRef": slot.get("ids", {}).get("paraPrIDRef"),
            "styleIDRef": slot.get("ids", {}).get("styleIDRef"),
            "borderFillIDRef": slot.get("ids", {}).get("borderFillIDRef"),
            "fontHangul": slot.get("fontHangul"),
            "fontLatin": slot.get("fontLatin"),
            "sizePt": slot.get("sizePt"),
            "color": slot.get("color"),
            "bold": slot.get("bold"),
            "lineSpacing": slot.get("lineSpacing", {}).get("display") if isinstance(slot.get("lineSpacing"), dict) else None,
            "align": slot.get("align"),
            "spaceBeforePt": slot.get("spaceBeforePt"),
            "spaceAfterPt": slot.get("spaceAfterPt"),
            "indentMm": slot.get("indentMm"),
            "unknownReason": slot.get("unknownReason"),
        }

    table_chrome = profA.get("tableChrome", {}) or {}

    return {
        "sourceFile": profA.get("sourceFile"),
        "extraction": profA.get("extraction", {}),  # method 등
        "page": {
            "paper": page.get("paper"),
            "orientation": page.get("orientation"),
            "widthMm": page.get("widthMm"),
            "heightMm": page.get("heightMm"),
            "marginMm": page.get("marginMm", {}),
            "columns": page.get("columns"),
        },
        "bodyGuess": {
            "paraPrIDRef": body_pp_id,
            "charPrIDRef": body_cp_id,
            "sizePt": find_cp(body_cp_id).get("sizePt") if body_cp_id and find_cp(body_cp_id) else None,
            "fontHangulFace": find_cp(body_cp_id).get("fontHangulFace") if body_cp_id and find_cp(body_cp_id) else None,
            "fontLatinFace": find_cp(body_cp_id).get("fontLatinFace") if body_cp_id and find_cp(body_cp_id) else None,
            "fontHangulRef": find_cp(body_cp_id).get("raw", {}).get("fontRef@hangul") if body_cp_id and find_cp(body_cp_id) else None,
            "fontLatinRef": find_cp(body_cp_id).get("raw", {}).get("fontRef@latin") if body_cp_id and find_cp(body_cp_id) else None,
            "color": find_cp(body_cp_id).get("color") if body_cp_id and find_cp(body_cp_id) else None,
            "bold": find_cp(body_cp_id).get("bold") if body_cp_id and find_cp(body_cp_id) else None,
            "align": find_pp(body_pp_id).get("align") if body_pp_id and find_pp(body_pp_id) else None,
            "lineSpacingDisplay": find_pp(body_pp_id).get("lineSpacingDisplay") if body_pp_id and find_pp(body_pp_id) else None,
            "spaceBeforePt": find_pp(body_pp_id).get("spaceBeforePt") if body_pp_id and find_pp(body_pp_id) else None,
            "spaceAfterPt": find_pp(body_pp_id).get("spaceAfterPt") if body_pp_id and find_pp(body_pp_id) else None,
            "indentMm": find_pp(body_pp_id).get("indentMm") if body_pp_id and find_pp(body_pp_id) else None,
            "note": "A는 문장 없이 ID 기반 최빈 조합으로 추정. 표 내부 문단 포함 가능성 있음.",
        },
        "roles": role_summary,
        "tableChrome": {
            "present": table_chrome.get("present", False),
            "outerWidthMm": table_chrome.get("outerWidthMm"),
            "lineStyle": table_chrome.get("lineStyle"),
            "lineColor": table_chrome.get("lineColor"),
            "headerFill": table_chrome.get("headerFill"),
            "bodyFill": table_chrome.get("bodyFill"),
        },
        "rawCounts": profA.get("rawCounts", {}),
        "charPropertiesCount": len(char_properties),
        "paraPropertiesCount": len(para_properties),
        "borderFillsCount": len(border_fills),
        "stylesCount": len(styles),
        "notes": notes,
    }


def summarize_skeleton(blocks: List[Dict[str, Any]], stats: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """B 내용 골격을 Solar에 줄 요약으로 만듦 (텍스트 원문 보존, 서식X)."""
    out_blocks = []
    for b in blocks:
        btype = b.get("type", "paragraph")
        block = {"type": btype}
        if btype == "title":
            block["text"] = b.get("text", "")
        elif btype == "heading":
            block["level"] = b.get("level")
            block["text"] = b.get("text", "")
        elif btype == "paragraph":
            runs = b.get("runs", [])
            text = b.get("text", "")
            # 런 단위 강조만 보존 (색/글꼴/크기 제외)
            run_summary = []
            for r in runs:
                rt = r.get("text", "")
                if not rt:
                    continue
                run_summary.append({
                    "text": rt,
                    "bold": bool(r.get("bold")),
                    "italic": bool(r.get("italic")),
                    "underline": bool(r.get("underline")),
                })
            block["runs"] = run_summary
            block["text"] = text
        elif btype == "listItem":
            block["listMarker"] = b.get("listMarker")
            block["listDepth"] = b.get("listDepth")
            block["text"] = b.get("text", "")
            block["runs"] = [{"text": b.get("text", "")}]
        elif btype == "table":
            tbl = b.get("table", {})
            block["rows"] = tbl.get("rows")
            block["cols"] = tbl.get("cols")
            block["cells"] = [
                {
                    "r": c.get("r"),
                    "c": c.get("c"),
                    "rowspan": c.get("rowspan"),
                    "colspan": c.get("colspan"),
                    "text": c.get("text", ""),
                    "header": bool(c.get("header")),
                }
                for c in (tbl.get("cells") or [])
            ]
        elif btype == "caption":
            block["text"] = b.get("text", "")
        elif btype == "image":
            block["imageRef"] = b.get("image", {}).get("binaryItemIDRef")
            block["alt"] = b.get("image", {}).get("alt")
        else:
            block["text"] = b.get("text", "")
        out_blocks.append(block)

    return {
        "sourceFile": stats.get("sourceFile") if stats else None,
        "stats": stats or {},
        "blocks": out_blocks,
    }

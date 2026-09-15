"""
A(header.xml) 파싱 → style profile 내부 표현.
규칙: A의 문장은 절대 추출하지 않는다. 역할별 대표 서식만.
"""
import xml.etree.ElementTree as ET

from hwpx_lib.units import (
    color_to_hex,
    height_to_pt,
    hwpx_to_mm,
    line_spacing_display,
    line_width_to_mm,
)

# ---------- xml helpers (local-name based, namespace-agnostic) ----------


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return node.text.strip()


def _attr(node, name: str) -> str | None:
    if node is None:
        return None
    return node.get(name)


def _find(parent, local_name: str):
    for el in parent.iter():
        if _local(el.tag) == local_name:
            return el
    return None


def _find_all(parent, local_name: str):
    return [el for el in parent.iter() if _local(el.tag) == local_name]


def _first_child_text(parent, local_name: str) -> str | None:
    return _text(_find(parent, local_name))


# ---------- charPr ----------

FONT_LANGS = ("hangul", "latin", "hanja", "japanese", "other", "symbol", "user")


def _parse_charpr(cp, font_map=None) -> dict:
    out: dict = {"id": _attr(cp, "id"), "raw": {}}
    # font refs: 실제 font face 이름으로 치환
    for lang in FONT_LANGS:
        ref = _find(cp, "fontRef")
        if ref is None:
            continue
        fid = _attr(ref, lang)
        if not fid:
            continue
        face = None
        if font_map and lang.upper() in font_map:
            face = font_map[lang.upper()].get(str(fid))
        out[f"font{lang.capitalize()}Face"] = face
        out["raw"][f"fontRef@{lang}"] = fid
        out["raw"][f"font{lang.capitalize()}Face"] = face
    # heightsizePt
    height = _attr(cp, "height")
    out["sizePt"] = height_to_pt(height)
    out["raw"]["height"] = height
    # color
    tc = color_to_hex(_attr(cp, "textColor"))
    if tc:
        out["color"] = tc
    sc = _attr(cp, "shadeColor")
    if sc and sc.lower() != "none":
        out["shadeColor"] = color_to_hex(sc) or sc
    out["bold"] = _find(cp, "bold") is not None
    out["italic"] = _find(cp, "italic") is not None
    underline = _find(cp, "underline")
    if underline is not None:
        out["underline"] = True
        out["raw"]["underlineType"] = _attr(underline, "type")
        out["raw"]["underlineShape"] = _attr(underline, "shape")
    out["strikeout"] = _find(cp, "strikeout") is not None
    sup = _find(cp, "supscript")
    sub = _find(cp, "subscript")
    out["superscript"] = sup is not None
    out["subscript"] = sub is not None
    spacing = _find(cp, "spacing")
    if spacing is not None:
        out["spacing"] = _attr(spacing, "hangul") or _attr(spacing, "latin")
        out["raw"]["spacing"] = out["spacing"]
    ratio = _find(cp, "ratio")
    if ratio is not None:
        out["ratio"] = _attr(ratio, "hangul") or _attr(ratio, "latin")
    bfr = _attr(cp, "borderFillIDRef")
    if bfr:
        out["borderFillIDRef"] = bfr
    return out


# ---------- paraPr ----------


def _parse_parapr(pp) -> dict:
    out: dict = {"id": _attr(pp, "id"), "raw": {}}
    align = _attr(pp, "align")
    if align:
        out["align"] = align.lower()
    ls = _find(pp, "lineSpacing")
    if ls is not None:
        lt = _attr(ls, "type")
        lv = _attr(ls, "value")
        out["lineSpacingType"] = lt
        out["lineSpacingValue"] = lv
        out["lineSpacingDisplay"] = line_spacing_display(lt, lv)
        out["raw"]["lineSpacing"] = f"{lt}={lv}"
    for sp in ("before", "after"):
        raw = _attr(pp, sp)
        if raw is not None:
            out[f"space{sp.capitalize()}Pt"] = height_to_pt(raw)
            out["raw"][sp] = raw
    for m in ("left", "right"):
        raw = _attr(pp, m)
        if raw is not None:
            out[f"margin{m.capitalize()}Mm"] = hwpx_to_mm(raw)
            out["raw"][f"margin{m}"] = raw
    indent = _attr(pp, "indent")
    if indent is not None:
        out["indentMm"] = hwpx_to_mm(indent)
        out["raw"]["indent"] = indent
    ol = _find(pp, "outlineLevel")
    if ol is not None:
        out["outlineLevel"] = int(_attr(ol, "val") or _text(ol) or "0")
    # border
    bd = _find(pp, "border")
    if bd is not None:
        out["border"] = True
    bfr = _attr(pp, "borderFillIDRef")
    if bfr:
        out["borderFillIDRef"] = bfr
    return out


# ---------- borderFill ----------


def _parse_borderfill(bf) -> dict:
    out: dict = {"id": _attr(bf, "id"), "raw": {}}
    # line(s)
    for side in ("top", "bottom", "left", "right"):
        ln = _find(bf, side)
        if ln is not None:
            v = _attr(ln, "val")
            if v and v.upper() != "NONE":
                out[f"line{side.capitalize()}"] = {
                    "type": v,
                    "widthMm": line_width_to_mm(_attr(ln, "width")),
                    "color": color_to_hex(_attr(ln, "color")),
                    "raw": {"width": _attr(ln, "width"), "color": _attr(ln, "color")},
                }
    fill = _find(bf, "fillBrush")
    if fill is not None:
        sf = _find(fill, "winBrush") or _find(fill, "fillBrush")
        if sf is not None:
            col = color_to_hex(_attr(sf, "color"))
            if col:
                out["fillColor"] = col
                out["raw"]["fillColor"] = col
    cm = _find(bf, "cellMargin")
    if cm is not None:
        out["cellMarginMm"] = {}
        for side in ("left", "right", "top", "bottom"):
            mv = _attr(cm, side)
            if mv is not None:
                out["cellMarginMm"][side] = hwpx_to_mm(mv)
                out["raw"][f"cellMargin{side}"] = mv
    return out


# ---------- style ----------


def _parse_style(st) -> dict:
    out: dict = {"id": _attr(st, "id"), "name": _attr(st, "name"), "type": _attr(st, "type")}
    pp = _attr(st, "paraPrIDRef")
    if pp:
        out["paraPrIDRef"] = pp
    cp = _attr(st, "charPrIDRef")
    if cp:
        out["charPrIDRef"] = cp
    return out


# ---------- page (section에서 읽음, 여기선 helper만) ----------


def parse_page_from_section(section_xml_text: str) -> dict:
    """A의 section에서 첫 hp:secPr > hp:pagePr 추출 → page dict."""
    if not section_xml_text or not section_xml_text.strip():
        return {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}}
    try:
        root = ET.fromstring(section_xml_text)
    except Exception:
        return {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}}
    # find first hp:p with secPr
    secpr = None
    for p in _find_all(root, "p"):
        run = _find(p, "run")
        if run is not None:
            sp = _find(run, "secPr")
            if sp is not None:
                secpr = sp
                break
    if secpr is None:
        return {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}}
    pp = _find(secpr, "pagePr")
    if pp is None:
        return {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}}
    landscape = _attr(pp, "landscape")
    w = _attr(pp, "width")
    h = _attr(pp, "height")
    from hwpx_lib.units import paper_info as _pi

    info = _pi(w, h, landscape)
    margin = _find(pp, "margin")
    margin_mm = {}
    if margin is not None:
        for side in ("top", "bottom", "left", "right", "header", "footer"):
            mv = _attr(margin, side)
            if mv is not None:
                margin_mm[side] = hwpx_to_mm(mv)
    colpr = _find(pp, "colPr")
    col_count = None
    if colpr is not None:
        col_count = int(_attr(colpr, "colCount") or "1")
    return {
        "paper": info["paper"],
        "orientation": info["orientation"],
        "widthMm": info.get("widthMm"),
        "heightMm": info.get("heightMm"),
        "marginMm": margin_mm,
        "columns": col_count,
        "raw": {"width": w, "height": h, "landscape": landscape, "margin": _attr(margin, "top")},
    }

def _read_file_utf8(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


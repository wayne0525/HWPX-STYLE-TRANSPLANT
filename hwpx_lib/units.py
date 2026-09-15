"""
단위 변환 — HWPX 내부 수치 ↔ 사람이 읽는 단위(pt, mm, %)
참조: references/02-units.md
"""


def height_to_pt(height):
    """charPr @height(HWPUNIT 스케일) → pt. pt = height/100. None이면 None."""
    if height is None:
        return None
    try:
        return round(int(height) / 100, 2)
    except (TypeError, ValueError):
        return None


def line_spacing_display(ls_type, ls_value):
    """lineSpacing type/value → 사용자 표시 문자열. 예: "160%", "고정 18pt" """
    if ls_type is None or ls_value is None:
        return None
    if ls_type == "PERCENT":
        return f"{ls_value}%"
    if ls_type == "FIXED":
        pt = height_to_pt(ls_value)
        return f"고정 {pt}pt" if pt is not None else "고정 (값 판독 불가)"
    if ls_type == "AT_LEAST":
        pt = height_to_pt(ls_value)
        return f"최소 {pt}pt" if pt is not None else "최소 (값 판독 불가)"
    if ls_type == "LINE":
        return "unknown"
    return "unknown"


def hwpx_to_mm(hwpx):
    """HWPUNIT → mm. 1mm ≈ 283.465 HWPUNIT. None이면 None."""
    if hwpx is None:
        return None
    try:
        return round(float(hwpx) / 283.465, 1)
    except (TypeError, ValueError):
        return None


def mm_to_hwpx(mm):
    """mm → HWPUNIT(정수). C 만들 때 사용. None이면 None."""
    if mm is None:
        return None
    try:
        return round(float(mm) * 283.465)
    except (TypeError, ValueError):
        return None


def pt_to_hwpx(pt):
    """pt → HWPUNIT. 1pt = 100 HWPUNIT. None이면 None."""
    if pt is None:
        return None
    try:
        return round(float(pt) * 100)
    except (TypeError, ValueError):
        return None


def paper_info(width_hwpx, height_hwpx, landscape):
    """
    용지 정보 → paper(A4/B5/기타 mm), orientation(portrait/landscape/unknown),
    widthMm, heightMm.
    landscape: 'WIDELY' 등 마커이면 가로, 아니면 세로.
    """
    w = hwpx_to_mm(width_hwpx) if width_hwpx is not None else None
    h = hwpx_to_mm(height_hwpx) if height_hwpx is not None else None
    if landscape and str(landscape).strip().lower() in ("widely", "landscape"):
        orient = "landscape"
        if w is not None and h is not None:
            w, h = h, w
    else:
        orient = "portrait"

    paper = "unknown"
    if w is not None and h is not None:
        if abs(w - 210) < 3 and abs(h - 297) < 3:
            paper = "A4"
        elif abs(w - 182) < 3 and abs(h - 257) < 3:
            paper = "B5"
        elif abs(w - 297) < 3 and abs(h - 420) < 3:
            paper = "A3"
        else:
            paper = f"{w} x {h}mm"
    return {
        "paper": paper,
        "orientation": orient,
        "widthMm": w,
        "heightMm": h,
    }


def line_width_to_mm(raw):
    """
    borderFill width → mm.
    XML에 "0.12mm" 문자열일 수도, HWPUNIT 수치일 수도 있음.
    값이 100 미만이면 mm 스케일로 간주, 크면 HWPUNIT으로 추정.
    None이면 None.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.endswith("mm"):
            try:
                return round(float(raw[:-2]), 3)
            except ValueError:
                return None
        try:
            v = float(raw)
            if v < 100:
                return round(v, 3)
            return round(v / 283.465, 3)
        except ValueError:
            return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v < 100:
        return round(v, 3)
    return round(v / 283.465, 3)


def color_to_hex(raw):
    """color 값 → #RRGGBB. None이면 None. shadeColor='none' 등은 None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("none", "null", ""):
        return None
    if s.lower().startswith("#"):
        return s.upper()
    s2 = s.lstrip("#")
    if len(s2) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in s2):
        return f"#{s2[-6:].upper()}"
    return None

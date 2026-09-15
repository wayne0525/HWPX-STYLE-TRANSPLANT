"""
A header.xml → style profile 내부 표현 빌드.
규칙: A의 문장은 절대 추출하지 않는다. 역할별 대표 서식만(역할 추론은 아직 미구현).
"""
from hwpx_lib.parse_header import (
    _find_all,
    _parse_charpr,
    _parse_parapr,
    _parse_borderfill,
    _parse_style,
    _read_file_utf8,
    parse_page_from_section,
)
from hwpx_lib.unpack import find_in_tmp


def _empty_roles():
    return {
        "documentTitle": {"present": False, "unknownReason": "미추론"},
        "heading1": {"present": False, "unknownReason": "미추론"},
        "heading2": {"present": False, "unknownReason": "미추론"},
        "heading3": {"present": False, "unknownReason": "미추론"},
        "body": {"present": False, "unknownReason": "미추론"},
        "caption": {"present": False, "unknownReason": "미추론"},
        "list": {"present": False, "unknownReason": "미추론"},
        "tableHeader": {"present": False, "unknownReason": "미추론"},
        "tableBody": {"present": False, "unknownReason": "미추론"},
        "quote": {"present": False, "unknownReason": "미추론"},
        "emphasis": {"present": False, "unknownReason": "미추론"},
        "headerChrome": {"present": False, "unknownReason": "미추론"},
        "footerChrome": {"present": False, "unknownReason": "미추론"},
    }


def build_style_profile(
    tmp_dir: str,
    sourceFile: str,
    section_xml_text: str | None = None,
    font_map: dict[str, dict[str, str]] | None = None,
) -> dict:
    import xml.etree.ElementTree as ET

    header_path = find_in_tmp(tmp_dir, "Contents/header.xml")
    if not header_path:
        return {
            "sourceFile": sourceFile,
            "extraction": {"method": "xml", "openedHeaderXml": False},
            "page": {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}},
            "roles": _empty_roles(),
            "tableChrome": {"present": False},
            "charProperties": [],
            "paraProperties": [],
            "borderFills": [],
            "styles": [],
            "notes": ["Contents/header.xml을 찾지 못함"],
            "rawCounts": {"charPr": 0, "paraPr": 0, "borderFill": 0, "style": 0},
        }
    try:
        tree = ET.parse(header_path)
        root = tree.getroot()
    except Exception as e:
        return {
            "sourceFile": sourceFile,
            "extraction": {"method": "xml", "openedHeaderXml": True},
            "page": {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}},
            "roles": _empty_roles(),
            "tableChrome": {"present": False},
            "charProperties": [],
            "paraProperties": [],
            "borderFills": [],
            "styles": [],
            "notes": [f"header.xml 파싱 오류: {str(e)}"],
            "rawCounts": {"charPr": 0, "paraPr": 0, "borderFill": 0, "style": 0},
        }
    cp_list = []
    for cp in _find_all(root, "charPr"):
        try:
            parsed = _parse_charpr(cp, font_map=font_map)
            if parsed:
                cp_list.append(parsed)
        except Exception:
            pass
    pp_list = []
    for pp in _find_all(root, "paraPr"):
        try:
            parsed = _parse_parapr(pp)
            if parsed:
                pp_list.append(parsed)
        except Exception:
            pass
    bf_list = []
    for bf in _find_all(root, "borderFill"):
        try:
            parsed = _parse_borderfill(bf)
            if parsed:
                bf_list.append(parsed)
        except Exception:
            pass
    st_list = []
    for st in _find_all(root, "style"):
        try:
            parsed = _parse_style(st)
            if parsed:
                st_list.append(parsed)
        except Exception:
            pass
    page = {"paper": "unknown", "orientation": "unknown", "marginMm": {}, "raw": {}}
    if section_xml_text:
        page = parse_page_from_section(section_xml_text)
    else:
        sec_path = find_in_tmp(tmp_dir, "Contents/section0.xml")
        if sec_path:
            sec_text = _read_file_utf8(sec_path)
            page = parse_page_from_section(sec_text)
    return {
        "sourceFile": sourceFile,
        "extraction": {"method": "xml", "openedHeaderXml": True},
        "page": page,
        "roles": _empty_roles(),
        "tableChrome": {"present": False},
        "charProperties": cp_list,
        "paraProperties": pp_list,
        "borderFills": bf_list,
        "styles": st_list,
        "notes": [],
        "rawCounts": {"charPr": len(cp_list), "paraPr": len(pp_list), "borderFill": len(bf_list), "style": len(st_list)},
    }

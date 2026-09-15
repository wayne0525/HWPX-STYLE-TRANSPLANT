"""
fontfaces/fonts → font 매핑.
charPr의 fontRef(@hangul/@latin/@hanja/@japanese/@other/@symbol/@user) ID를
실제 글꼴 이름으로 치환하는 데 사용.
"""
import xml.etree.ElementTree as ET
from typing import Dict


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _attr(node, k: str) -> str | None:
    return node.get(k) if node is not None else None


def build_font_map(root: ET.Element) -> Dict[str, Dict[str, str]]:
    """
    header.xml root에서 fontfaces 구조를 파싱해
    { lang: { font_id_str: face_name } } 반환.
    lang 예: 'HANGUL', 'LATIN', 'HANJA', 'JAPANESE', 'OTHER', 'SYMBOL', 'USER'.
    font_id_str은 문자열(key로 쓰기 위해).
    font element의 face 속성값을 이름으로 사용.
    fontface 아래 여러 font 중 lang별 fontface를 찾아 mapping.
    """
    out: Dict[str, Dict[str, str]] = {}
    for el in root.iter():
        if _local(el.tag) == "fontface":
            lang = _attr(el, "lang")
            if not lang:
                continue
            mapping: Dict[str, str] = {}
            for font in el:
                if _local(font.tag) == "font":
                    fid = _attr(font, "id")
                    face = _attr(font, "face")
                    if fid is not None:
                        mapping[str(fid)] = face if face else f"id{fid}"
            out[lang] = mapping
    return out


def resolve_font(face_name: str | None, lang_map: Dict[str, Dict[str, str]], lang: str, fid: str | None) -> str | None:
    """
    fontRef의 face 속성(있으면 그걸 우선) + id→name 매핑으로 실제 글꼴 이름 결정.
    face_name이 명시적으로 있으면 우선, 없으면 lang_map[lang][fid] 사용.
    """
    if face_name:
        return face_name
    if lang and fid and lang in lang_map and fid in lang_map[lang]:
        return lang_map[lang][fid]
    return None

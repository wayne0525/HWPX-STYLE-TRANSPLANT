"""
repack.py — A_style.hwpx + B blocks → C HWPX ZIP 재조립 (공개 API).
내부 구현은 build_section.assemble_C가 담당.
"""
import os
from typing import List, Dict, Any, Optional

from hwpx_lib.build_section import assemble_C, build_role_map
from hwpx_lib.parse_section import parse_blocks_from_section
from hwpx_lib.style_profile import build_style_profile
from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp


def repack(
    fileA_path: str,
    fileB_path: str,
    out_path: Optional[str] = None,
    blocksB: Optional[List[Dict[str, Any]]] = None,
    profA: Optional[Dict[str, Any]] = None,
) -> str:
    """
    A_style.hwpx와 B_content.hwpx(또는 blocksB+profA)로부터
    C HWPX(ZIP)를 조립해 out_path에 저장. 반환: out_path.

    blocksB/profA를 직접 넘기면 재파싱 생략.
    """
    if blocksB is None or profA is None:
        from hwpx_lib.unpack import open_hwpx as _ow, close_hwpx as _cw, find_in_tmp as _ft
        # B 파싱
        if blocksB is None:
            _tmpB = _ow(fileB_path)
            _secB_path = _ft(_tmpB, "Contents/section0.xml")
            _secB_text = ""
            if _secB_path:
                with open(_secB_path, "r", encoding="utf-8") as _f:
                    _secB_text = _f.read()
            blocksB = parse_blocks_from_section(_secB_text)
            _cw(_tmpB)
        # A 프로파일
        if profA is None:
            _tmpA = _ow(fileA_path)
            _secA_path = _ft(_tmpA, "Contents/section0.xml")
            _secA_text = ""
            if _secA_path:
                with open(_secA_path, "r", encoding="utf-8") as _f:
                    _secA_text = _f.read()
            profA = build_style_profile(_tmpA, fileA_path, section_xml_text=_secA_text)
            _cw(_tmpA)

    return assemble_C(fileA_path, blocksB, profA=profA, out_path=out_path)

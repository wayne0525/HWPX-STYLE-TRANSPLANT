"""
4번: C HWPX 조립 — B의 내용 골격을 A의 서식으로 채워 section0.xml 생성.
원칙: A 서식만 사용, B 서식 무시, B 텍스트·구조만 사용.
"""
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple


NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS_HS = "http://www.hancom.co.kr/hwpml/2011/section"
ET.register_namespace("hp", NS_HP)
ET.register_namespace("hs", NS_HS)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


# ---------- section0.xml 빌더 ----------


def build_section0(
    blocksB: List[Dict[str, Any]],
    body_charPrIDRef: Optional[str] = None,
    body_paraPrIDRef: Optional[str] = None,
    title_charPrIDRef: Optional[str] = None,
    title_paraPrIDRef: Optional[str] = None,
    heading1_charPrIDRef: Optional[str] = None,
    heading1_paraPrIDRef: Optional[str] = None,
    heading2_charPrIDRef: Optional[str] = None,
    heading2_paraPrIDRef: Optional[str] = None,
    heading3_charPrIDRef: Optional[str] = None,
    heading3_paraPrIDRef: Optional[str] = None,
    caption_charPrIDRef: Optional[str] = None,
    caption_paraPrIDRef: Optional[str] = None,
    sec_pr_xml: str = "",  # A 원본의 <hp:secPr>...</hp:secPr> XML 문자열
) -> bytes:
    """
    B 블록 리스트를 받아 A의 서식 ID만으로 section0.xml 본문을 구성,
    Bytes(EUC-KR 인코딩, XML 선언 포함)로 반환.

    기본 본문 서식은 body_charPrIDRef/body_paraPrIDRef(없으면 "0"/"0").
    제목/표제/캡션은 별도 ID 없으면 본문 서식 차용.

    반환 XML 구조:
      <hp:section xmlns:hp=... xmlns:hh=... id="0">
        <hp:p id="..." charPrIDRef="..." paraPrIDRef="...">
          <hp:r id="..." charPrIDRef="...">
            <hp:t>...</hp:t>
          </hp:r>
          ...
        </hp:p>
        ...
      </hp:section>
    """
    body_cp = body_charPrIDRef or "0"
    body_pp = body_paraPrIDRef or "0"
    title_cp = title_charPrIDRef or body_cp
    title_pp = title_paraPrIDRef or body_pp
    h1_cp = heading1_charPrIDRef or body_cp
    h1_pp = heading1_paraPrIDRef or body_pp
    h2_cp = heading2_charPrIDRef or body_cp
    h2_pp = heading2_paraPrIDRef or body_pp
    h3_cp = heading3_charPrIDRef or body_cp
    h3_pp = heading3_paraPrIDRef or body_pp
    cap_cp = caption_charPrIDRef or body_cp
    cap_pp = caption_paraPrIDRef or body_pp

    section = ET.Element(f"{{{NS_HS}}}sec")
    section.set("id", "0")

    for idx, block in enumerate(blocksB):
        btype = block.get("type", "paragraph")
        text = block.get("text", "") or ""
        runs = block.get("runs") or []
        txt_source = text if not runs else "".join(r.get("text", "") or "" for r in runs)

        # 서식 매핑
        if btype == "title":
            cp, pp = title_cp, title_pp
        elif btype == "heading":
            lvl = block.get("level", 1)
            if lvl == 1:
                cp, pp = h1_cp, h1_pp
            elif lvl == 2:
                cp, pp = h2_cp, h2_pp
            elif lvl == 3:
                cp, pp = h3_cp, h3_pp
            else:
                cp, pp = h1_cp, h1_pp
        elif btype == "caption":
            cp, pp = cap_cp, cap_pp
        else:
            cp, pp = body_cp, body_pp

        p = ET.SubElement(section, f"{{{NS_HP}}}p")
        p.set("id", str(idx + 1))
        p.set("styleIDRef", "0")
        p.set("pageBreak", "0")
        p.set("columnBreak", "0")
        p.set("merged", "0")
        p.set("paraPrIDRef", str(pp))

        run = ET.SubElement(p, f"{{{NS_HP}}}run")
        run.set("charPrIDRef", str(cp))

        # 첫 paragraph의 run 안에 A 원본 secPr을 그대로 삽입 (페이지 정보 포함)
        if idx == 0 and sec_pr_xml:
            # secPr XML에 네임스페이스 선언이 없으면 파싱 불가 — 선언 추가
            ns_decl = ' xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph" xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"'
            fixed = sec_pr_xml.replace("<hp:secPr", "<hp:secPr" + ns_decl, 1)
            sec_pr_el = ET.fromstring(fixed)
            run.append(sec_pr_el)

        if txt_source:
            t = ET.SubElement(run, f"{{{NS_HP}}}t")
            t.text = txt_source

        # 모든 paragraph 끝에 linesegarray 추가 (줄 배치 정보 — 없으면 텍스트 위치 안 잡힘)
        linesegarray = ET.SubElement(p, f"{{{NS_HP}}}linesegarray")
        lineseg = ET.SubElement(linesegarray, f"{{{NS_HP}}}lineseg")
        lineseg.set("textpos", "0")
        lineseg.set("vertpos", str(idx * 1000))  # 임시 세로 위치
        lineseg.set("vertsize", "1000")
        lineseg.set("textheight", "1000")
        lineseg.set("baseline", "850")
        lineseg.set("spacing", "600")
        lineseg.set("horzpos", "0")
        lineseg.set("horzsize", "45920")
        lineseg.set("flags", "393216")

    body = ET.tostring(section, encoding="utf-8")
    decl = b'<?xml version="1.0" encoding="UTF-8"?>\r\n'
    return decl + body


# ---------- role→서식 ID 매핑 빌더 ----------


def build_role_map(
    profA: Dict[str, Any],
    preferred_body_block_idx: int = 0,
) -> Dict[str, Tuple[str, str]]:
    """
    profA(style_profile)의 roles + charProperties/paraProperties에서
    역할별 (charPrIDRef, paraPrIDRef) 튜플을 추출.

    반환 예:
      {
        "body": ("0", "0"),
        "title": ("8", "4"),
        "heading1": ("8", "4"),
        "heading2": ("8", "4"),
        "heading3": ("8", "4"),
        "caption": ("0", "0"),
      }

    미확인 역할은 ("0","0")으로 폴백.
    """
    roles = profA.get("roles") or {}
    char_props = profA.get("charProperties") or []
    para_props = profA.get("paraProperties") or []

    def cp_size(cp_id: str) -> Optional[float]:
        for cp in char_props:
            if str(cp.get("id")) == str(cp_id):
                return cp.get("sizePt")
        return None

    def pp_align(pp_id: str):
        for pp in para_props:
            if str(pp.get("id")) == str(pp_id):
                return pp.get("align")
        return None

    out: Dict[str, Tuple[str, str]] = {}
    for role_name in ("body", "title", "heading1", "heading2", "heading3", "caption"):
        slot = roles.get(role_name, {})
        if not isinstance(slot, dict):
            out[role_name] = ("0", "0")
            continue
        cp_id = slot.get("charPrIDRef")
        pp_id = slot.get("paraPrIDRef")
        if cp_id in (None, "", False) or pp_id in (None, "", False):
            # 미추론 상태면 bodyGuess에서 가져온다
            bg = profA.get("bodyGuess") or {}
            if role_name == "body":
                out[role_name] = (
                    str(bg.get("charPrIDRef") or "0"),
                    str(bg.get("paraPrIDRef") or "0"),
                )
            else:
                out[role_name] = (
                    str(bg.get("charPrIDRef") or "0"),
                    str(bg.get("paraPrIDRef") or "0"),
                )
        else:
            out[role_name] = (str(cp_id), str(pp_id))

    return out


# ---------- 통합 조립 ----------


def assemble_C(
    fileA_path: str,
    blocksB: List[Dict[str, Any]],
    profA: Optional[Dict[str, Any]] = None,
    out_path: Optional[str] = None,
) -> str:
    """
    A_style.hwpx + B 블록 + profA → C section0.xml + ZIP 조립.
    Returns out_path.
    """
    import zipfile, os, shutil, tempfile
    from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp

    if profA is None:
        from hwpx_lib.style_profile import build_style_profile
        tmpA = open_hwpx(fileA_path)
        secA_path = find_in_tmp(tmpA, "Contents/section0.xml")
        secA_text = ""
        sec_pr_xml = ""  # A 원본의 secPr XML (page 정보 포함)
        if secA_path:
            with open(secA_path, "r", encoding="utf-8") as f:
                secA_text = f.read()
            import re as _re
            m = _re.search(r'<hp:secPr[^>]*>.*?</hp:secPr>', secA_text, _re.DOTALL)
            if m:
                sec_pr_xml = m.group(0)
        profA = build_style_profile(tmpA, fileA_path, section_xml_text=secA_text)
        close_hwpx(tmpA)
    else:
        # profA가 dict로 제공됨 — A 파일에서 secPr XML 추출
        import re as _re
        tmpA2 = open_hwpx(fileA_path)
        secA_path2 = find_in_tmp(tmpA2, "Contents/section0.xml")
        if secA_path2:
            with open(secA_path2, "r", encoding="utf-8") as f:
                secA_text2 = f.read()
            m = _re.search(r'<hp:secPr[^>]*>.*?</hp:secPr>', secA_text2, _re.DOTALL)
            if m:
                sec_pr_xml = m.group(0)
        close_hwpx(tmpA2)

    role_map = build_role_map(profA)

    section_bytes = build_section0(
        blocksB,
        body_charPrIDRef=role_map.get("body", ("0", "0"))[0],
        body_paraPrIDRef=role_map.get("body", ("0", "0"))[1],
        title_charPrIDRef=role_map.get("title", role_map["body"])[0],
        title_paraPrIDRef=role_map.get("title", role_map["body"])[1],
        heading1_charPrIDRef=role_map.get("heading1", role_map["body"])[0],
        heading1_paraPrIDRef=role_map.get("heading1", role_map["body"])[1],
        heading2_charPrIDRef=role_map.get("heading2", role_map["body"])[0],
        heading2_paraPrIDRef=role_map.get("heading2", role_map["body"])[1],
        heading3_charPrIDRef=role_map.get("heading3", role_map["body"])[0],
        heading3_paraPrIDRef=role_map.get("heading3", role_map["body"])[1],
        caption_charPrIDRef=role_map.get("caption", role_map["body"])[0],
        caption_paraPrIDRef=role_map.get("caption", role_map["body"])[1],
        sec_pr_xml=sec_pr_xml,
    )

    # 임시 디렉토리에 A_style.hwpx 풀기
    tmp_dir = tempfile.mkdtemp(prefix="hwpx_C_")
    try:
        with zipfile.ZipFile(fileA_path, "r") as zin:
            zin.extractall(tmp_dir)

        # section0.xml 교체 (원본 백업 후 덮어쓰기)
        sec_path = os.path.join(tmp_dir, "Contents", "section0.xml")
        backup_path = sec_path + ".bak"
        if os.path.exists(sec_path):
            shutil.copy2(sec_path, backup_path)
        with open(sec_path, "wb") as f:
            f.write(section_bytes)

        # ZIP 재조립 — mimetype은 첫 엔트리 + 무압축(store) 필수
        if out_path is None:
            base = os.path.splitext(os.path.basename(fileA_path))[0]
            out_path = os.path.join(os.path.dirname(fileA_path) or ".", f"{base}_C.hwpx")
        # mimetype 먼저 무압축으로
        mimetype_path = os.path.join(tmp_dir, "mimetype")
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            if os.path.exists(mimetype_path):
                zout.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            for dirpath, dirnames, filenames in os.walk(tmp_dir):
                for fn in filenames:
                    if fn == "mimetype" or fn.endswith(".bak"):
                        continue
                    full = os.path.join(dirpath, fn)
                    arcname = os.path.relpath(full, tmp_dir)
                    zout.write(full, arcname)

        return out_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------- 테스트 하니스 (main) ----------


if __name__ == "__main__":
    import sys, os, json

    ROOT = os.path.abspath(os.path.dirname(__file__))
    DRIVE = os.path.normpath(os.path.join(ROOT, "..", ".."))
    A = os.path.join(DRIVE, "Downloads", "hwpx-train-pairs", "08_corp_status", "A_style.hwpx")
    B = os.path.join(DRIVE, "Downloads", "hwpx-train-pairs", "08_corp_status", "B_content.hwpx")

    print(f"A = {A}  exists={os.path.exists(A)}")
    print(f"B = {B}  exists={os.path.exists(B)}")
    if not os.path.exists(A) or not os.path.exists(B):
        print("A/B 없음 → 테스트 스킵")
        sys.exit(0)

    from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
    from hwpx_lib.parse_section import parse_blocks_from_section
    from hwpx_lib.style_profile import build_style_profile
    from hwpx_lib.summary import summarize_style

    # B 파싱
    tmpB = open_hwpx(B)
    secB_path = find_in_tmp(tmpB, "Contents/section0.xml")
    secB_text = ""
    if secB_path:
        with open(secB_path, "r", encoding="utf-8") as f:
            secB_text = f.read()
    blocksB = parse_blocks_from_section(secB_text)
    close_hwpx(tmpB)
    print(f"\nB blocks: {len(blocksB)}개")
    print(f"유형별: { {b.get('type') for b in blocksB} }")

    # A 프로파일
    tmpA = open_hwpx(A)
    secA_path = find_in_tmp(tmpA, "Contents/section0.xml")
    secA_text = ""
    if secA_path:
        with open(secA_path, "r", encoding="utf-8") as f:
            secA_text = f.read()
    profA = build_style_profile(tmpA, A, section_xml_text=secA_text)
    close_hwpx(tmpA)

    role_map = build_role_map(profA)
    print(f"\nrole_map: {json.dumps({k: list(v) for k, v in role_map.items()}, ensure_ascii=False, indent=2)}")

    section_bytes = build_section0(
        blocksB,
        body_charPrIDRef=role_map["body"][0],
        body_paraPrIDRef=role_map["body"][1],
        title_charPrIDRef=role_map.get("title", role_map["body"])[0],
        title_paraPrIDRef=role_map.get("title", role_map["body"])[1],
        heading1_charPrIDRef=role_map.get("heading1", role_map["body"])[0],
        heading1_paraPrIDRef=role_map.get("heading1", role_map["body"])[1],
    )

    print(f"\nsection0.xml 크기: {len(section_bytes)} bytes")
    print("section0.xml 앞부분 (200bytes):")
    print(section_bytes[:200].decode("utf-8", errors="replace"))

    # C 조립
    out = assemble_C(A, blocksB, profA=profA)
    print(f"\nC 출력: {out}  size={os.path.getsize(out)} bytes")
    print("C ZIP 유효성:", zipfile.is_zipfile(out))
    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
        print(f"C 포함 파일 수: {len(names)}")
        print("section0.xml 포함:", "Contents/section0.xml" in names)

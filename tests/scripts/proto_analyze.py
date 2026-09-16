"""
tests/scripts/proto_analyze.py — A.hwpx 규칙 1~3 임시 분석 (프로토타입 확인용).
"""
import sys, re, json
sys.path.insert(0, "/mnt/c/Users/dylan/HWPX-STYLE-TRANSPLANT")

import zipfile
from lxml import etree

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


def cell_texts(tc):
    """셀 안의 모든 hp:t 텍스트를 리스트로 반환 (중첩 표 고려 X — MVP)."""
    out = []
    for p in tc.findall(".//hp:p", NS):
        for run in p.findall(".//hp:run", NS):
            t = run.find("hp:t", NS)
            if t is not None and t.text:
                out.append(t.text)
    return out


def cell_text(tc):
    return "".join(cell_texts(tc))


def cell_text_stripped(tc):
    return cell_text(tc).strip()


def is_empty(cell_text_stripped):
    return cell_text_stripped == ""


def is_guidance(cell_text_stripped):
    return cell_text_stripped.startswith("※")


def is_placeholder_or_unit_only(cell_text_stripped):
    """자리표시자나 단위만 있는 셀."""
    t = cell_text_stripped
    if not t:
        return False
    # 괄호+공백만
    if re.fullmatch(r"[\s()]*", t):
        return True
    # '원'만 (공백/괄호 허용)
    if re.fullmatch(r"[\s()]*원\s*", t):
        return True
    # '천원'만
    if re.fullmatch(r"[\s()]*천원\s*", t):
        return True
    # '년 월 일' 패턴
    if re.fullmatch(r"[\s()]*년\s*월\s*일\s*", t):
        return True
    # 날짜 자리표시: (  .  .  ),  .  .  등
    if re.fullmatch(r"[\s()]*\d*\s*\.\s*\d*\s*\.\s*\d*\s*", t):
        return True
    # 괄호 패턴 (  ), (원), (  ) 등 — 짧고 괄호로 감싸진 자리표시
    if re.fullmatch(r"[\s()]*\(.*\)\s*", t) and 1 <= len(t) <= 15:
        return True
    return False


def is_label_cell(cell_text_stripped):
    """규칙 1에서 라벨로 볼 수 있는 셀인지. 숫자만/단위만/공백만/안내문은 제외."""
    t = cell_text_stripped
    if not t or not t.strip():
        return False
    if is_guidance(t):
        return False
    if is_placeholder_or_unit_only(t):
        return False
    if re.fullmatch(r"[\d\s,.]+", t):
        return False
    return True


A = "/mnt/c/Users/dylan/HWPX-STYLE-TRANSPLANT/tests/fixtures/A.hwpx"
with zipfile.ZipFile(A) as zf:
    xml = zf.read("Contents/section0.xml")
root = etree.fromstring(xml)
tables = root.findall(".//hp:tbl", NS)

print(f"A.hwpx: 표 {len(tables)}개\n")

candidates = []
taken = set()  # (table_idx, col, row)

for t_idx, tbl in enumerate(tables):
    cells = list(tbl.findall(".//hp:tc", NS))
    cell_map = {}
    for tc in cells:
        addr = tc.find("hp:cellAddr", NS)
        col = int(addr.get("colAddr", 0)) if addr is not None else 0
        row = int(addr.get("rowAddr", 0)) if addr is not None else 0
        cell_map[(col, row)] = tc
    if not cell_map:
        continue
    max_col = max(c for c, _ in cell_map)
    max_row = max(r for _, r in cell_map)

    # 규칙 1: 라벨 셀 + 오른쪽 빈셀
    for (col, row), tc in sorted(cell_map.items()):
        key = (t_idx, col, row)
        if key in taken:
            continue
        t = cell_text_stripped(tc)
        if not is_label_cell(t):
            continue
        right_col = col + 1
        if right_col > max_col:
            continue
        right_tc = cell_map.get((right_col, row))
        if right_tc is None:
            continue
        if is_guidance(cell_text_stripped(right_tc)):
            continue
        if not is_empty(cell_text_stripped(right_tc)):
            # 값이 있거나 placeholder/unit이면 규칙 3 대상: 규칙 1에서는 패스
            continue
        unit = "text"
        lbl = t
        if "우편" in lbl or re.search(r"우편\s*번호", lbl):
            unit = "postal-code"
        elif "전화" in lbl or "팩스" in lbl or "연락처" in lbl:
            unit = "phone"
        elif "이메일" in lbl or "e-mail" in lbl:
            unit = "email"
        elif "성명" in lbl or "이름" in lbl:
            unit = "person-name"
        elif "금액" in lbl or "천원" in lbl or "원" in lbl:
            unit = "money"
        taken.add((t_idx, right_col, row))
        candidates.append({
            "rule": "rule1",
            "label": lbl,
            "table_idx": t_idx,
            "row": row,
            "col": right_col,
            "unit": unit,
            "empty_right": True,
        })

    # 규칙 2: 헤더 행(첫 행에 텍스트 있는 셀이 하나라도 있으면) 아래의 빈 셀
    has_header = any(cell_text_stripped(cell_map[(c, 0)]) for c in range(max_col + 1) if (c, 0) in cell_map)
    if has_header:
        for (col, row), tc in sorted(cell_map.items()):
            key = (t_idx, col, row)
            if key in taken:
                continue
            if row == 0:
                continue
            t = cell_text_stripped(tc)
            if not is_empty(t):
                continue
            if is_guidance(t):
                continue
            taken.add((t_idx, col, row))
            candidates.append({
                "rule": "rule2",
                "label": "",
                "table_idx": t_idx,
                "row": row,
                "col": col,
                "unit": "text",
                "empty_right": False,
            })

    # 규칙 3: 자리표시자/단위만 있는 셀
    for (col, row), tc in sorted(cell_map.items()):
        key = (t_idx, col, row)
        if key in taken:
            continue
        t = cell_text_stripped(tc)
        if is_empty(t):
            continue
        if is_guidance(t):
            continue
        if not is_placeholder_or_unit_only(t):
            continue
        unit = "text"
        if "천원" in t:
            unit = "money"
        elif re.search(r"원\b", t):
            unit = "money"
        elif re.search(r"년.*월.*일", t) or re.search(r"\\d.*\\.\\s*\\d.*\\.\\s*\\d", t):
            unit = "date"
        taken.add((t_idx, col, row))
        candidates.append({
            "rule": "rule3",
            "label": "",
            "table_idx": t_idx,
            "row": row,
            "col": col,
            "unit": unit,
            "empty_right": False,
        })

print(f"=== 후보 총 {len(candidates)}개 ===\n")
for i, c in enumerate(candidates, 1):
    print(f"{i:02d}. [{c['rule']}] table#{c['table_idx']} "
          f"row={c['row']:02d} col={c['col']:02d} "
          f"label='{c['label'][:25]}' unit={c['unit']}")

print("\n=== 예상 vs 실제: 프로그램명/성명/우편번호 ===")
for c in candidates:
    if "프로그램" in c["label"] or "성명" in c["label"] or "우편" in c["label"]:
        print(f"  FOUND: {c}")
print("프로그램명/성명/우편번호 관련 후보가 없으면 위에 'FOUND'가 출력 안 됨.")

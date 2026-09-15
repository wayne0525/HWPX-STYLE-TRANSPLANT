import sys, os, json
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.style_profile import build_style_profile
from hwpx_lib.parse_section import parse_blocks_from_section

A = os.path.join(os.path.expanduser("~"), "Downloads", "hwpx-train-pairs", "08_corp_status", "A_style.hwpx")
B = os.path.join(os.path.expanduser("~"), "Downloads", "hwpx-train-pairs", "08_corp_status", "B_content.hwpx")

print("A =", A, "exists?", os.path.exists(A))
print("B =", B, "exists?", os.path.exists(B))

# A 파싱
tmpA = open_hwpx(A)
profA = build_style_profile(tmpA, A)
secA = find_in_tmp(tmpA, "Contents/section0.xml")
secA_text = open(secA, "r", encoding="utf-8").read() if secA else ""
pageA = profA.get("page", {})
print("\n=== A page ===")
print(json.dumps(pageA, ensure_ascii=False, indent=2))
print("charProperties:", len(profA.get("charProperties", [])))
print("paraProperties:", len(profA.get("paraProperties", [])))
print("borderFills:", len(profA.get("borderFills", [])))
print("styles:", len(profA.get("styles", [])))

# 본문 최빈 조합 (표 제외)
combos = Counter()
for pp in profA.get("paraProperties", []):
    pid = pp.get("id")
    for cp in profA.get("charProperties", []):
        cid = cp.get("id")
        combos[(pid, cid)] += 1

print("\n=== 본문 최빈 (paraPr, charPr) 조합 상위 6 ===")
for (pid, cid), cnt in combos.most_common(6):
    pp = next((p for p in profA["paraProperties"] if p.get("id") == pid), {})
    cp = next((c for c in profA["charProperties"] if c.get("id") == cid), {})
    print(f"  ({pid},{cid}) x{cnt} | sizePt={cp.get('sizePt')} fontHangul={cp.get('fontHangul')} fontLatin={cp.get('fontLatin')} align={pp.get('align')} lineSpacing={pp.get('lineSpacingDisplay')} bold={cp.get('bold')} spaceBeforePt={pp.get('spaceBeforePt')} spaceAfterPt={pp.get('spaceAfterPt')}")

# 표 테두리 정보
print("\n=== borderFill 중 표 관련 (cellMargin 있거나 line 있는 것) ===")
for bf in profA.get("borderFills", []):
    has_line = any(k.startswith("line") for k in bf)
    has_fill = "fillColor" in bf
    has_cell = "cellMarginMm" in bf
    if has_line or has_fill or has_cell:
        print(f"  id={bf.get('id')} line={has_line} fill={has_fill} cellMargin={has_cell} fillColor={bf.get('fillColor')}")

close_hwpx(tmpA)

# B 파싱 (내용 골격)
tmpB = open_hwpx(B)
blocks = parse_blocks_from_section(open(find_in_tmp(tmpB, "Contents/section0.xml"), "r", encoding="utf-8").read())
print("\n=== B blocks 수 ===", len(blocks))
type_counts = Counter(b["type"] for b in blocks)
print("유형별:", dict(type_counts))
print("\n=== B 첫 3개 블록 ===")
for b in blocks[:3]:
    print(json.dumps(b, ensure_ascii=False, indent=2))
close_hwpx(tmpB)

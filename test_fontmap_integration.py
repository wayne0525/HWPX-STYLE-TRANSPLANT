import sys, os, json
sys.path.insert(0, ".")
from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.fontmap import build_font_map
from hwpx_lib.style_profile import build_style_profile

A = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/A_style.hwpx")
tmp = open_hwpx(A)
header_path = find_in_tmp(tmp, "Contents/header.xml")
print("header.xml:", header_path)
import xml.etree.ElementTree as ET
rootA = ET.parse(header_path).getroot() if header_path else None
font_map = build_font_map(rootA) if rootA is not None else {}
print("\n=== font_map (lang → id→face) ===")
for lang, m in sorted(font_map.items()):
    print(f"  {lang}: {dict(sorted(m.items()))}")

print("\n=== build_style_profile(font_map=font_map) 결과: charProperties[0] font 필드 ===")
profA = build_style_profile(tmp, A, font_map=font_map)
cp0 = profA["charProperties"][0] if profA["charProperties"] else None
if cp0:
    print(json.dumps(cp0, ensure_ascii=False, indent=2))
else:
    print("charProperties empty")

print("\n=== 본문 최빈 (paraPrIDRef, charPrIDRef) 조합 top3 ===")
from collections import Counter
combo = Counter()
for pp in profA.get("paraProperties", []):
    pid = pp.get("id")
    for cp in profA.get("charProperties", []):
        cid = cp.get("id")
        combo[(pid, cid)] += 1
for (pid, cid), cnt in combo.most_common(3):
    cp = next((c for c in profA["charProperties"] if c["id"] == cid), None)
    pp = next((p for p in profA["paraProperties"] if p["id"] == pid), None)
    print(f"  ({pid},{cid}) x{cnt} | sizePt={cp.get('sizePt') if cp else None} "
          f"fontHangulFace={cp.get('fontHangulFace') if cp else None} "
          f"fontLatinFace={cp.get('fontLatinFace') if cp else None} "
          f"align={pp.get('align') if pp else None} "
          f"lineSpacing={pp.get('lineSpacingDisplay') if pp else None}")
close_hwpx(tmp)

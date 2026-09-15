import sys, os
sys.path.insert(0, ".")
from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.parse_section import parse_blocks_from_section

B = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/B_content.hwpx")
tmp = open_hwpx(B)
sec_path = find_in_tmp(tmp, "Contents/section0.xml")
print("section0.xml:", sec_path)
text = open(sec_path, "r", encoding="utf-8").read()
blocks = parse_blocks_from_section(text)
print(f"\n총 블록: {len(blocks)}")
print("유형별:", {t: sum(1 for b in blocks if b["type"] == t) for t in set(b["type"] for b in blocks)})
print()
for i, b in enumerate(blocks[:12]):
    t = b["type"]
    txt = b["text"]
    print(f"[{i:02d}] type={t:10} text={txt[:50]!r}")
close_hwpx(tmp)

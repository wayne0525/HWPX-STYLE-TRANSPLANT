import sys, os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.parse_header import _read_file_utf8, _local, _attr, _find, _find_all, _text

B = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/B_content.hwpx")
tmpB = open_hwpx(B)
secB = find_in_tmp(tmpB, "Contents/section0.xml")
rootB = ET.parse(secB).getroot()

print("=== B 섹션 전체 hp:p (텍스트 + 바로 앞뒤 관계) ===\n")
paragraphs = []
for el in rootB.iter():
    if _local(el.tag) == "p":
        text = "".join(_text(t) or "" for t in _find_all(el, "t"))
        styleName = _attr(el, "styleName")
        heading = _find(el, "heading")
        level = _attr(heading, "level") if heading is not None else None
        paragraphs.append({"text": text, "styleName": styleName, "heading_level": level})

for i, p in enumerate(paragraphs):
    t = p["text"].strip()
    marker = ""
    if i == 0:
        marker = " ← [첫 블록]"
    elif t and len(t) < 40 and (i+1 < len(paragraphs) and paragraphs[i+1]["text"].strip()):
        marker = " ← [짧은 줄 + 다음 본문 있음 → 제목/Heading 후보]"
    print(f"[{i:2}] level={p['heading_level']} style={p['styleName']!r} text={t[:70]!r}{marker}")

close_hwpx(tmpB)

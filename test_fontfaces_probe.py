import sys, os
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp

A = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/A_style.hwpx")

tmpA = open_hwpx(A)
hp = find_in_tmp(tmpA, "Contents/header.xml")
print("header.xml:", hp)
if hp:
    root = ET.parse(hp).getroot()

    def local(tag):
        return tag.split("}")[-1] if "}" in tag else tag

    # fontfaces/fonts 탐색
    print("\n=== fontfaces / fonts 태그 탐색 ===")
    for el in root.iter():
        if local(el.tag) in ("fontfaces", "fonts"):
            print("태그:", local(el.tag), "속성:", el.attrib)
            for child in el:
                print("  자식:", local(child.tag), "속성:", child.attrib)
                # 그 아래 face 등
                for sub in child:
                    print("    sub:", local(sub.tag), "속성:", sub.attrib, "text=", (sub.text or "").strip()[:60])
                    for sub2 in sub:
                        print("      sub2:", local(sub2.tag), "속성:", sub2.attrib, "text=", (sub2.text or "").strip()[:60])
    print("\n=== charPr fontRef @hangul/@latin 값 샘플 (상위 10) ===")
    cnt = 0
    for el in root.iter():
        if local(el.tag) == "charPr":
            for sub in el:
                if local(sub.tag) == "fontRef":
                    print("  charPr fontRef:", sub.attrib)
                    cnt += 1
                    if cnt >= 10:
                        break
            if cnt >= 10:
                break
close_hwpx(tmpA)

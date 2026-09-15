import sys, os, json
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp, list_texts

A = os.path.join(os.path.expanduser("~"), "Downloads", "hwpx-train-pairs", "08_corp_status", "A_style.hwpx")
B = os.path.join(os.path.expanduser("~"), "Downloads", "hwpx-train-pairs", "08_corp_status", "B_content.hwpx")

tmpA = open_hwpx(A)
print("=== A tmp 내부 파일 목록 (전체) ===")
for rel in list_texts(tmpA):
    print(" ", rel)
print()
hp = find_in_tmp(tmpA, "Contents/header.xml")
print("=== find_in_tmp(Contents/header.xml) 결과 ===", hp)
if hp:
    print("=== header.xml 크기 ===", os.path.getsize(hp))
    try:
        root = ET.parse(hp).getroot()
        print("=== header.xml 루트 태그 ===", root.tag)
        print("=== 루트 직접 자식 태그(local) 목록 ===", [_el(tag) for tag in root])
        # charPr 있는지 트리 깊이 탐색
        def find_tags(node, target):
            res = []
            for el in node.iter():
                if _local(el.tag) == target:
                    res.append(el)
            return res
        def _local(tag):
            return tag.split('}')[-1] if '}' in tag else tag
        print("=== charPr 개수 (iter 전체) ===", len(find_tags(root, 'charPr')))
        print("=== paraPr 개수 ===", len(find_tags(root, 'paraPr')))
        print("=== borderFill 개수 ===", len(find_tags(root, 'borderFill')))
        print("=== style 개수 ===", len(find_tags(root, 'style')))
        # 상위 몇 개 charPr id 찍기
        cps = find_tags(root, 'charPr')
        print("=== charPr id 샘플 (up to 5) ===", [_attr(c, 'id') for c in cps[:5]])
    except Exception as e:
        print("header.xml 파싱 에러:", e)
close_hwpx(tmpA)

import sys, os
sys.path.insert(0, ".")
from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.parse_section import parse_blocks_from_section

B = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/B_content.hwpx")
tmp = open_hwpx(B)
sec_path = find_in_tmp(tmp, "Contents/section0.xml")
text = open(sec_path, "r", encoding="utf-8").read()
blocks = parse_blocks_from_section(text)
print("=== B 전체 블록 (번호 개요/짧은 줄 + 본문 패턴 보기) ===\n")
for i, b in enumerate(blocks):
    t = b["type"]
    txt = b.get("text", "")
    stripped = txt.strip()
    # 번호 개요 후보 체크
    import re
    is_num_heading = bool(re.match(r'^\d{1,3}\.\s', stripped)) or bool(re.match(r'^[가-힣]\.\s', stripped)) or bool(re.match(r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\.\s', stripped))
    short = len(stripped) < 60 and stripped
    # 앞뒤 문맥
    prev_txt = blocks[i-1]["text"].strip() if i > 0 else ""
    next_txt = blocks[i+1]["text"].strip() if i+1 < len(blocks) else ""
    flag = ""
    if is_num_heading:
        flag = " [번호개요후보]"
    elif short and i <= 3:
        flag = " [문서초단백본문장]"
    elif short and next_txt and not prev_txt:
        flag = " [앞빈줄+뒤본문→제목/절후보]"
    elif short and prev_txt and next_txt:
        flag = " [앞뒤본문→문맥절후보]"
    if stripped == "":
        flag = " [빈줄]"
    print(f"[{i:02d}] type={t:10} len={len(stripped):3} isNum={is_num_heading} {flag}")
    print(f"       text={stripped[:80]!r}")
close_hwpx(tmp)

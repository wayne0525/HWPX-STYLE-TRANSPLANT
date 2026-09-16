"""
단계 3용 A.hwpx 셀 맵 분석 — 라벨·빈셀·병합 위치 확인용.
"""
import zipfile
from lxml import etree

A = "tests/fixtures/A.hwpx"
NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}

with zipfile.ZipFile(A) as zf:
    xml = zf.read("Contents/section0.xml")

root = etree.fromstring(xml)
tables = root.findall(".//hp:tbl", NS)

def cell_text(tc):
    parts = []
    sub = tc.find("hp:subList", NS)
    if sub is None:
        return ""
    for p in sub.findall("hp:p", NS):
        for run in p.findall("hp:run", NS):
            t = run.find("hp:t", NS)
            if t is not None and t.text:
                parts.append(t.text)
    return "".join(parts)

for ti, tbl in enumerate(tables):
    print(f"\n===== 표#{ti} =====")
    rows = {}
    for tc in tbl.findall(".//hp:tc", NS):
        addr = tc.find("hp:cellAddr", NS)
        col = int(addr.get("colAddr", 0))
        row = int(addr.get("rowAddr", 0))
        span = tc.find("hp:cellSpan", NS)
        cspan = int(span.get("colSpan", 1)) if span is not None else 1
        rspan = int(span.get("rowSpan", 1)) if span is not None else 1
        txt = cell_text(tc).strip()
        rows.setdefault(row, []).append((col, txt, cspan, rspan, tc))
    for r in sorted(rows):
        cells = sorted(rows[r])
        line = f"  행{r:02d}: "
        for col, txt, cspan, rspan, tc in cells:
            span_note = f" [colSpan={cspan},rowSpan={rspan}]" if (cspan>1 or rspan>1) else ""
            label = "★" if txt else "·"
            disp = txt[:35] if txt else "(빈셀)"
            line += f"[{col:02d}]{span_note}:{label}{disp} | "
        print(line)

print("\n\n===== 규칙별 후보 예상 =====")
print("""
규칙1(라벨 오른쪽 빈셀) 후보:
  표#1: [프로그램명→생활문해와 스마트폰 기초]는 colSpan=2(라벨이 0,1 차지) → 오른쪽 빈셀 없음
  표#3: [단 체 명→(빈셀)@col1], [사 업 명→생활문해...], [사업기간→(빈셀)@col1], 
         [사업대상→(빈셀)@col1], [사업목적→○○], ...
  표#4: [연번→(빈셀)], [성 명→(빈셀)], [소속(직급)→(빈셀)], [경력 및 자격증→(빈셀)], [비고→(빈셀)]
         → 헤더 아래 빈셀 = 규칙2
  표#5: [운영일시→(빈셀)], [학습목표(주제)→(빈셀)], [교육내용→(빈셀)], [교수방법→(빈셀)]
         → 헤더 아래 빈셀 = 규칙2
  표#10: [시 설 명→(빈셀)@col1], [주  소→(우...)], [연락처→대표전화...], 
          [홈페이지→(빈셀)@col2], [등록기관→(빈셀)@col2], [등록일→(빈셀)@col4], ...
규칙3(단위/자리표시자만):
  표#1: 천원(여러 행) = 단위만 → 단위=돈
  표#3: 천원, 천원(자부담률    %) = 단위+자리표시
  표#6: 0 = 실제 값 → 제외
  표#7: 0 = 실제 값 → 제외
""")

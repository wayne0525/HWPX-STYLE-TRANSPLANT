import sys, os, json, base64

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

print("=== 3번: Solar 이식 보고서 검증 ===\n")

# 프로덕션 응답 읽기 (solar_reply 전체 파싱)
resp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "solar_real_resp_full.json")
if not os.path.exists(resp_path):
    # fallback: solar_real_resp.json
    resp_path2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "solar_real_resp.json")
    if os.path.exists(resp_path2):
        resp_path = resp_path2
    else:
        print(f"응답 파일 없음: {resp_path} / {resp_path2}")
        sys.exit(1)
with open(resp_path, "r", encoding="utf-8") as f:
    resp = json.load(f)
print(f"응답 상태: {resp.get('status')}")
print(f"solar_reply 전체 길이: {len(resp.get('solar_reply', ''))} chars")
print()

# A 실제 값 파싱
from hwpx_lib.unpack import open_hwpx as _open_hwpx, close_hwpx as _close_hwpx, find_in_tmp as _find_in_tmp
from hwpx_lib.style_profile import build_style_profile as _build_style_profile
A_path = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/A_style.hwpx")
_tmp = _open_hwpx(A_path)
profA = _build_style_profile(_tmp, A_path)
_close_hwpx(_tmp)
page = profA["page"]
print("A의 page:", json.dumps(page, ensure_ascii=False, indent=2))
print()

# Solar 원문(solar_reply) 전체 파싱 → 이식 보고서 추출
solar_reply = resp.get("solar_reply", resp.get("solar_reply_preview", ""))
report = None
if solar_reply:
    try:
        parsed = json.loads(solar_reply)
        # transplant_report 구조면 그걸, 아니면 원문 자체가 보고서
        if isinstance(parsed, dict) and ("roleMap" in parsed or "applied" in parsed or "transplant_report" in parsed):
            if "transplant_report" in parsed and isinstance(parsed["transplant_report"], dict):
                report = parsed["transplant_report"]
            else:
                report = parsed
        else:
            report = {"raw_solar_reply": solar_reply[:2000], "parse_note": "roleMap/applied/transplant_report 없는 구조"}
    except Exception as e:
        report = {"raw_solar_reply": solar_reply[:2000], "parse_note": f"solar_reply JSON 파싱 실패: {e}"}
else:
    report = {"raw_solar_reply": "(solar_reply 없음)", "parse_note": "Solar 원문 없음"}

if report is None:
    report = {"raw_solar_reply": str(resp), "parse_note": "보고서 구조 파악 불가"}
applied = report.get("applied", [])
print("=== applied 항목과 A 실제 값 비교 ===\n")
page = profA["page"]
for item in applied:
    name = item.get("item")
    val_a = item.get("valueFromA")
    status = item.get("status")
    print(f"[{name}]")
    print(f"  Solar applied.valueFromA: {val_a}")
    print(f"  status: {status}")
    if name == "용지":
        actual_paper = f"{page.get('widthMm')}x{page.get('heightMm')}mm {page.get('orientation')}"
        print(f"  A 실제 용지: {actual_paper}")
        if val_a != actual_paper and val_a != f"{page.get('widthMm')}x{page.get('heightMm')}mm {page.get('orientation')}":
            print(f"  ⚠️ 불일치: Solar이 A 실제 용지({actual_paper}) 대신 '{val_a}' 기입")
    elif name == "여백":
        mm = page.get("marginMm", {})
        actual = f"위 {mm.get('top')}/아래 {mm.get('bottom')}/좌 {mm.get('left')}/우 {mm.get('right')} mm"
        print(f"  A 실제 여백: {actual}")
        if val_a != actual:
            print(f"  ⚠️ 불일치: Solar이 A 실제 여백({actual}) 대신 '{val_a}' 기입")
    print()

# roleMap 검증
roleMap = report.get("roleMap", [])
print(f"=== roleMap ({len(roleMap)}개) ===")
for rm in roleMap:
    print(f"  fromB={rm.get('fromB','')[:50]!r} → toASlot={rm.get('toASlot')} fallback={rm.get('fallback')} note={rm.get('note','')[:40]!r}")
print()

# gaps
gaps = report.get("gaps", [])
print(f"=== gaps ({len(gaps)}개) ===")
for g in gaps:
    print(f"  {g}")
print()

# output
output = report.get("output", {})
print(f"=== output ===")
print(f"  format: {output.get('format')}")
print(f"  fileName: {output.get('fileName')}")
print(f"  fallbackReason: {output.get('fallbackReason')}")
print()

print("=== 3번 검증 완료 ===")

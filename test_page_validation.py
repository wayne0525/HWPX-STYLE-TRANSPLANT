import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

resp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "solar_real_resp_full.json")
with open(resp_path, encoding="utf-8") as f:
    resp = json.load(f)

solar_reply = resp.get("solar_reply") or resp.get("solar_reply_preview") or ""
print("solar_reply 길이:", len(solar_reply))
reply = None
try:
    reply = json.loads(solar_reply)
except Exception as e:
    print("solar_reply JSON 파싱 실패:", e)
    reply = {"raw": solar_reply[:2000]}

applied = reply.get("applied") if isinstance(reply, dict) else None
print("\n=== applied 항목 (용지/방향/여백 관련) ===")
if isinstance(applied, list):
    for it in applied:
        item = it.get("item","")
        val = it.get("valueFromA")
        status = it.get("status")
        if any(k in item for k in ("용지","방향","여백","margin","paper","orientation")):
            print(f"  [{item}] valueFromA={val!r} status={status}")
else:
    print("  applied가 리스트가 아님:", type(applied), applied)

# A 실제 page 값 (style_summary 참고)
ss = resp.get("style_summary") or {}
page = ss.get("page", {}) if isinstance(ss, dict) else {}
print("\n=== A style_summary.page ===")
print(json.dumps(page, ensure_ascii=False, indent=2))

print("\n=== page 값 일치 여부 확인 ===")
actual_paper = f"{page.get('widthMm')}x{page.get('heightMm')}mm {page.get('orientation')}"
actual_margin = f"위 {page.get('marginMm',{}).get('top')}/아래 {page.get('marginMm',{}).get('bottom')}/좌 {page.get('marginMm',{}).get('left')}/우 {page.get('marginMm',{}).get('right')} mm"
print(f"  A 실제 용지: {actual_paper}")
print(f"  A 실제 여백: {actual_margin}")
if isinstance(applied, list):
    paper_val = next((it.get("valueFromA") for it in applied if it.get("item")=="용지"), None)
    orient_val = next((it.get("valueFromA") for it in applied if it.get("item")=="방향"), None)
    margin_val = next((it.get("valueFromA") for it in applied if "여백" in it.get("item","")), None)
    print(f"  Solar 용지: {paper_val!r}  -> 일치? {paper_val == actual_paper}")
    print(f"  Solar 방향: {orient_val!r}  -> 일치? {orient_val == page.get('orientation')}")
    print(f"  Solar 여백: {margin_val!r}  -> 일치? {margin_val == actual_margin}")

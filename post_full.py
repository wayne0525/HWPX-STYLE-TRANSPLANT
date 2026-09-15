import sys, os, json, base64, urllib.request, urllib.error

URL = "https://hwpx-style-transplant.vercel.app/api/transplant"

here = os.path.dirname(os.path.abspath(__file__))
req_path = os.path.join(here, "solar_real_req.json")
with open(req_path, "r", encoding="utf-8") as f:
    body = f.read().encode("utf-8")

req = urllib.request.Request(
    URL,
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    out_path = os.path.join(here, "solar_real_resp_full.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"응답 저장: {out_path} ({len(raw)} bytes)")
    j = json.loads(raw)
    print("상태:", j.get("status"))
    sp = j.get("solar_reply_preview", "")
    print("solar_reply_preview 길이:", len(sp))
    try:
        obj = json.loads(sp)
        print("preview 최상위 keys:", list(obj.keys())[:15])
        print("preview 전체 keys:", list(obj.keys()))
    except Exception as e:
        print("preview JSON 파싱 실패:", e)
        print("원문 앞부분:", sp[:400].replace("\n", "\\n"))
    # style_summary의 page 값도 확인
    ss = j.get("style_summary", {})
    print("\n=== style_summary.page ===")
    print(json.dumps(ss.get("page") or {}, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode("utf-8", errors="replace")[:500])
except urllib.error.URLError as e:
    print("URLError:", e.reason)

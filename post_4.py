import sys, os, json, base64, urllib.request, urllib.error

URL = "https://hwpx-style-transplant.vercel.app/api/transplant"

here = os.path.dirname(os.path.abspath(__file__))
A = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/A_style.hwpx")
B = os.path.expanduser("~/Downloads/hwpx-train-pairs/08_corp_status/B_content.hwpx")

body = json.dumps({
    "fileA": base64.b64encode(open(A, "rb").read()).decode(),
    "fileB": base64.b64encode(open(B, "rb").read()).decode(),
    "model": "solar-pro4",
    "skill_context": "4-verify",
}).encode("utf-8")

req = urllib.request.Request(
    URL, data=body, headers={"Content-Type": "application/json"}, method="POST",
)
out_path = os.path.join(here, "solar_real_resp_4.json")
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(raw)
    print(f"응답 저장: {out_path} ({len(raw)} bytes)")
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code, e.read().decode("utf-8", errors="replace")[:500])
except urllib.error.URLError as e:
    print("URLError:", e.reason)

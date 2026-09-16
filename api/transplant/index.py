import base64
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from hwpx_lib.unpack import open_hwpx, close_hwpx, find_in_tmp
from hwpx_lib.style_profile import build_style_profile
from hwpx_lib.parse_section import parse_blocks_from_section
from hwpx_lib.summary import summarize_style, summarize_skeleton
from hwpx_lib.parse_header import _read_file_utf8
from hwpx_lib.repack import repack

TMP_ROOT = "/tmp"

SOLAR_BASE_URL = os.environ.get("SOLAR_BASE_URL", "https://api.upstage.ai/v1")
SOLAR_API_KEY = os.environ.get("SOLAR_API_KEY")
SOLAR_MODEL = os.environ.get("SOLAR_MODEL", "solar-pro4")


def call_solar(messages, **kwargs):
    if not SOLAR_API_KEY:
        raise ValueError("SOLAR_API_KEY environment variable is not set")

    payload = {
        "model": SOLAR_MODEL,
        "messages": messages,
        "stream": False,
        **kwargs,
    }

    req = Request(
        f"{SOLAR_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {SOLAR_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Solar API HTTP {e.code}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"Solar API network error: {e.reason}") from e

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"Unexpected Solar response: {json.dumps(data)[:1000]}")
    return choices[0].get("message", {}).get("content", "")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body)
        except Exception:
            self._send_json({"error": "invalid JSON body"}, 400)
            return

        fileA_b64 = payload.get("fileA")
        fileB_b64 = payload.get("fileB")

        if not fileA_b64 or not fileB_b64:
            self._send_json({"error": "fileA and fileB (base64) are required"}, 400)
            return

        tag = uuid.uuid4().hex[:8]
        fileA_path = os.path.join(TMP_ROOT, f"fileA_{tag}.hwpx")
        fileB_path = os.path.join(TMP_ROOT, f"fileB_{tag}.hwpx")

        try:
            with open(fileA_path, "wb") as f:
                f.write(base64.b64decode(fileA_b64))
            with open(fileB_path, "wb") as f:
                f.write(base64.b64decode(fileB_b64))
        except Exception as e:
            self._send_json({"error": f"failed to write tmp files: {str(e)}"}, 500)
            return

        # --- 파싱 + 요약 직렬화 ---
        try:
            from hwpx_lib.fontmap import build_font_map
            import xml.etree.ElementTree as ET
            tmpA = open_hwpx(fileA_path)
            header_path = find_in_tmp(tmpA, "Contents/header.xml")
            rootA = ET.parse(header_path).getroot() if header_path else None
            font_map = build_font_map(rootA) if rootA is not None else {}
            profA = build_style_profile(tmpA, fileA_path, font_map=font_map)
            secA_path = find_in_tmp(tmpA, "Contents/section0.xml")
            secA_text = _read_file_utf8(secA_path) if secA_path else ""
            close_hwpx(tmpA)
        except Exception as e:
            self._send_json({"error": f"A 파싱 실패: {str(e)}", "detail": str(e)}, 500)
            return

        try:
            tmpB = open_hwpx(fileB_path)
            secB_path = find_in_tmp(tmpB, "Contents/section0.xml")
            blocksB = parse_blocks_from_section(_read_file_utf8(secB_path)) if secB_path else []
            close_hwpx(tmpB)
        except Exception as e:
            self._send_json({"error": f"B 파싱 실패: {str(e)}", "detail": str(e)}, 500)
            return

        style_summary = summarize_style(profA)
        skeleton_summary = summarize_skeleton(blocksB, {"sourceFile": fileB_path, "blockCount": len(blocksB)})

        system_prompt = (
            "당신은 HWPX 서식 이식 전문가다. 아래 데이터를 보고 SKILL.md 프로토콜에 따라 "
            "이식 보고서(transplant report)를 JSON으로만 출력한다.\n"
            "규칙:\n"
            "- A의 문장·표 값·날짜·이름은 절대 쓰지 않는다. 서식(글꼴/크기/색/줄간격/여백/선굵기/용지/방향)만 사용한다.\n"
            "- B의 서식(글꼴/색/줄간격/여백/선굵기)은 무시한다. 텍스트와 구조만 사용한다.\n"
            "- B의 문장을 요약·윤문·번역하지 않는다.\n"
            "- A의 ID를 B에 그대로 붙이지 않는다. 역할은 슬롯(본문/제목1/표헤더 등)으로만 매핑한다.\n"
            "- 읽지 못한 값은 unknown + 이유를 적는다. 지어내지 않는다.\n"
            "- 결과는 반드시 JSON으로만 출력하며, 아래 스키마를 정확히 따른다:\n"
            "  {\n"
            "    \"roleMap\": [ {\"fromB\": \"B-block-N (type): 텍스트앞쪽\", \"toASlot\": \"documentTitle|heading1|heading2|heading3|body|caption|list|quote|emphasis|tableHeader|tableBody|미매핑\", \"fallback\": bool, \"note\": \"...\"} ],\n"
            "    \"applied\": [ {\"item\": \"한글 글꼴|영문 글꼴|본문 크기|본문 색|제목1 크기|제목1 굵기|제목1 색|제목1 글꼴|본문 정렬|줄간격|spaceBeforePt|spaceAfterPt|선 굵기|표 헤더 배경|표 본문 배경|표 선 스타일|용지|방향|여백(위/아래/좌/우 mm)|머리글/바닥글 여부|미설정\", \"valueFromA\": \"A에서 읽은 실제 값 또는 unknown\", \"status\": \"yes|estimate|no\", \"note\": \"\"} ],\n"
            "    \"gaps\": [ \"누락 항목 설명\" ],\n"
            "    \"output\": {\"format\": \"hwpx|docx|pdf\", \"fileName\": \"C_주제_서식이식.hwpx\", \"fallbackReason\": null|string}\n"
            "  }\n"
            "- applied의 '용지' 항목에는 A page의 실제 값(예: '297.0 x 210.0mm landscape')을 그대로 쓴다.\n"
            "- applied의 '방향' 항목에는 A page orientation(예: 'landscape' 또는 'portrait')을 그대로 쓴다.\n"
            "- applied의 '여백(위/아래/좌/우 mm)' 항목에는 A page marginMm의 실제 값(예: '위 12.0 / 아래 12.0 / 좌 24.0 / 우 24.0 mm')을 그대로 쓴다.\n"
            "- A의 page가 있으면 applied에 반드시 용지·방향·여백 항목을 포함한다.\n"
            "- 결과는 반드시 JSON으로만 출력한다.\n"
        )
        user_prompt = (
            "## [필독] A의 페이지 서식 (용지·방향·여백) — 이 값을 그대로 따라야 한다\n"
            + json.dumps(style_summary.get("page", {}), ensure_ascii=False, indent=2)
            + "\n\n"
            "## A의 서식 프로필 (요약)\n"
            + json.dumps(style_summary, ensure_ascii=False, indent=2)
            + "\n\n## B의 내용 골격 (요약, 텍스트 원문)\n"
            + json.dumps(skeleton_summary, ensure_ascii=False, indent=2)
            + "\n\n## 출력\n"
            "위 데이터를 바탕으로 이식 보고서를 JSON으로만 출력하라. "
            "roleMap(B블록→A슬롯), applied(適用 항목: yes/estimate/no), gaps(누락), output(format/hwpx/docx/pdf/파일명)를 포함한다.\n"
            "사용자 요약표(①)와 주의/누락(②)은 이 JSON에서 추출할 것이다."
        )

        try:
            solar_reply = call_solar(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4000,
            )
        except ValueError as e:
            self._send_json({"error": str(e)}, 500)
            return
        except RuntimeError as e:
            self._send_json({"error": f"solar_error: {str(e)}"}, 502)
            return

        # Solar 응답을 transplant-report 형태로 파싱 시도
        report = None
        try:
            report = json.loads(solar_reply)
        except Exception:
            report = {"raw_solar_reply": solar_reply, "parse_note": "Solar 응답이 JSON이 아니어서 원문 그대로 전달"}

        # C HWPX 조립 (A 서식 + B 블록)
        C_hwpx_b64 = None
        C_hwpx_filename = None
        try:
            out_path = repack(fileA_path, fileB_path, blocksB=blocksB, profA=profA)
            with open(out_path, "rb") as _f:
                C_hwpx_b64 = base64.b64encode(_f.read()).decode("ascii")
            C_hwpx_filename = report.get("output", {}).get("fileName") if isinstance(report, dict) else None
            if not C_hwpx_filename:
                base = os.path.splitext(os.path.basename(fileA_path))[0]
                C_hwpx_filename = f"{base}_서식이식.hwpx"
            os.unlink(out_path)
        except Exception as e:
            C_hwpx_b64 = None
            C_hwpx_filename = None

        self._send_json(
            {
                "status": "solar_reply_ok",
                "fileA_path": fileA_path,
                "fileB_path": fileB_path,
                "style_summary": style_summary,
                "skeleton_summary": skeleton_summary,
                "transplant_report": report,
                "solar_reply": solar_reply,
                "solar_reply_preview": solar_reply[:1500] if len(solar_reply) > 1500 else solar_reply,
                "C_hwpx_base64": C_hwpx_b64,
                "C_hwpx_filename": C_hwpx_filename,
            },
            200,
        )

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

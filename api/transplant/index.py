"""Vercel entry point and local HTTP handler."""
import json
from http.server import BaseHTTPRequestHandler

from web_service import APIError, MAX_WIRE, dispatch
from hwpx.errors import DomainError


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._send_json(dispatch({'action': 'status'}))

    def do_POST(self):
        try:
            if self.headers.get('Transfer-Encoding'):
                raise APIError('INVALID_INPUT', 'Content-Length가 필요합니다')
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                raise APIError('INVALID_INPUT', '잘못된 Content-Length')
            if not 0 < length <= MAX_WIRE:
                raise APIError('SIZE_LIMIT', '요청은 3,800,000바이트 이하여야 합니다', 413)
            try:
                payload = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise APIError('INVALID_JSON', 'JSON 요청을 확인해 주세요')
            self._send_json(dispatch(payload))
        except APIError as exc:
            self._send_json({'code': exc.code, 'message': exc.message, 'details': exc.details}, exc.status)
        except DomainError as exc:
            self._send_json({'code': exc.code, 'message': exc.message, 'details': exc.details}, 422)
        except Exception:
            self._send_json({'code': 'INTERNAL_ERROR', 'message': '처리 중 오류가 발생했습니다', 'details': None}, 500)

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        if len(body) > MAX_WIRE:
            body = json.dumps({'code': 'SIZE_LIMIT', 'message': '응답 크기 제한을 초과했습니다', 'details': None}, ensure_ascii=False).encode('utf-8')
            status = 413
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

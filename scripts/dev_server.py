"""Serve public files and the production API together on localhost."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.transplant.index import handler as APIHandler


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)

    _send_json = APIHandler._send_json

    def do_GET(self):
        if self.path.split('?')[0] == '/api/transplant':
            return APIHandler.do_GET(self)
        return super().do_GET()

    def do_POST(self):
        if self.path.split('?')[0] != '/api/transplant':
            self.send_error(404)
            return
        APIHandler.do_POST(self)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5186)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

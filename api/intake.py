import sys
import os
import json
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(__file__))

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b""
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}

            guest_id = payload.get("guest_id")
            if not guest_id:
                self._json_response(400, {"error": "Missing guest_id"})
                return

            import user_context as uc
            uc.save_intake_v2(guest_id, payload)
            
            self._json_response(200, {"success": True})

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"FUNCTION ERROR: {exc}\n{tb}")
            self._json_response(500, {
                "error": "Internal server error",
                "details": str(exc),
                "trace": tb
            })

    def _json_response(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

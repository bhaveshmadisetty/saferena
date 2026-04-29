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
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            path_parts = self.path.split("?")
            url_path = path_parts[0]
            parts = url_path.strip("/").split("/")
            guest_id = parts[-1] if len(parts) > 2 else None

            if not guest_id or guest_id == "opening":
                self._json_response(400, {"error": "Missing guest_id"})
                return

            import user_context as uc
            ctx = uc.get_context(guest_id)
            
            if not ctx:
                self._json_response(200, {"message": "Hey — what's on your mind today?"})
                return
            
            msg = uc.get_opening_message(ctx)
            # Returns pre-written message. Zero tokens used, zero count increment.
            self._json_response(200, {"message": msg, "path": ctx.get("path", "deep")})

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"FUNCTION ERROR: {exc}\n{tb}")
            self._json_response(500, {
                "error": "Internal server error",
                "details": str(exc)
            })

    def _json_response(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

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
            # Parse guest_id from path /api/history/{guest_id} or /api/history-encrypted/{guest_id}
            path_parts = self.path.split("?")
            url_path = path_parts[0]
            parts = url_path.strip("/").split("/")
            guest_id = parts[-1] if len(parts) > 2 else None

            # Detect if this is an encrypted history request
            is_encrypted = "history-encrypted" in url_path

            if not guest_id or guest_id in ("history", "history-encrypted"):
                self._json_response(400, {"error": "Missing guest_id"})
                return

            try:
                import supabase_memory as mem
                _memory_available = mem.is_enabled()
            except ImportError:
                _memory_available = False
                mem = None

            if not _memory_available:
                if is_encrypted:
                    self._json_response(200, {"encryptedMessages": []})
                else:
                    self._json_response(200, {"history": []})
                return

            if is_encrypted:
                # E2EE: Return encrypted blobs for client-side decryption
                encrypted = mem.load_encrypted_messages(guest_id, limit=30)
                self._json_response(200, {"encryptedMessages": encrypted})
            else:
                # Legacy: Return plaintext history
                recent = mem.load_recent_messages(guest_id, limit=30)
                history = [{"role": m["role"], "content": m["message"]} for m in reversed(recent)]
                self._json_response(200, {"history": history})

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"FUNCTION ERROR: {exc}\n{tb}")
            self._json_response(500, {
                "error": "Internal server error",
                "details": str(exc)
            })

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

import sys
import os
import json
import traceback
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
import httpx

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
            # Parse guest_id from path /api/status/{guest_id}
            path_parts = self.path.split("?")
            url_path = path_parts[0]
            parts = url_path.strip("/").split("/")
            guest_id = parts[-1] if len(parts) > 2 else None

            if not guest_id or guest_id == "status":
                self._json_response(400, {"error": "Missing guest_id"})
                return

            import user_context as uc
            ctx = uc.get_context(guest_id)
            
            if not ctx:
                self._json_response(200, {"has_context": False})
                return
            
            # Auto-unlock logic
            if ctx.get("is_locked") and ctx.get("unlock_at"):
                unlock_at = datetime.fromisoformat(ctx["unlock_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > unlock_at:
                    if uc.is_enabled():
                        try:
                            # Patch the row to unlock
                            uc._get_client().patch(
                                f"{uc._REST_URL}/user_context",
                                headers=uc._HEADERS,
                                params={"guest_id": f"eq.{guest_id}"},
                                json={"is_locked": False, "unlock_at": None, "session_msg_count": 0}
                            )
                        except Exception as e:
                            print(f"[status] Error auto-unlocking: {e}")
                    
                    self._json_response(200, {
                        "has_context": True, 
                        "rate_limit": {"allowed": True, "remaining": 15}
                    })
                    return

            # If still locked
            if ctx.get("is_locked"):
                self._json_response(200, {
                    "has_context": True,
                    "rate_limit": {"allowed": False, "remaining": 0, "unlock_at": ctx.get("unlock_at")}
                })
                return
            
            # Normal state
            msg_count = ctx.get("session_msg_count", 0)
            self._json_response(200, {
                "has_context": True,
                "rate_limit": {"allowed": True, "remaining": max(0, 15 - msg_count)}
            })

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

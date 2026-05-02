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
                max_msgs = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
                self._json_response(200, {
                    "has_context": False,
                    "rate_limit": {
                        "allowed": True, 
                        "remaining": max_msgs,
                        "max_messages": max_msgs
                    }
                })
                return
            
            # Auto-unlock logic
            if ctx.get("is_locked") and ctx.get("unlock_at"):
                unlock_at = datetime.fromisoformat(ctx["unlock_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > unlock_at:
                    uc.reset_context(guest_id)
                    max_msgs = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
                    self._json_response(200, {
                        "has_context": True, 
                        "rate_limit": {"allowed": True, "remaining": max_msgs, "max_messages": max_msgs}
                    })
                    return

            # If still locked
            if ctx.get("is_locked"):
                max_msgs = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
                self._json_response(200, {
                    "has_context": True,
                    "rate_limit": {
                        "allowed": False, 
                        "remaining": 0, 
                        "unlock_at": ctx.get("unlock_at"),
                        "max_messages": max_msgs
                    }
                })
                return
            
            # Normal state
            msg_count = ctx.get("session_msg_count", 0)
            # Configurable limit for status response
            max_msgs = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
            self._json_response(200, {
                "has_context": True,
                "rate_limit": {
                    "allowed": True, 
                    "remaining": max(0, max_msgs - msg_count),
                    "max_messages": max_msgs
                }
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

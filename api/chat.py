"""
Vercel Python serverless function for /api/chat endpoint.
Uses BaseHTTPRequestHandler (the standard Vercel Python format).

MEMORY INTEGRATION:
- Reads optional guestId from payload
- Saves user message to Supabase before inference
- Loads recent messages from Supabase for context
- Saves assistant reply to Supabase after inference
- All memory calls are wrapped in try/except — if Supabase fails,
  the existing pipeline runs exactly as before.
"""

import sys
import os

# Ensure the api/ directory is on the path so rag_pipeline_lite can be imported
sys.path.insert(0, os.path.dirname(__file__))

from http.server import BaseHTTPRequestHandler
import json
import traceback


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b""
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}

            messages = payload.get("messages", [])
            session_id = payload.get("sessionId")
            guest_id = payload.get("guestId", "")  # NEW: read guest_id from payload

            if not isinstance(messages, list):
                self._json_response(400, {"error": "'messages' must be an array"})
                return

            # ---- MEMORY: Save user message & load history ----
            memory_context = ""
            if guest_id:
                try:
                    import supabase_memory as mem
                    # Extract the last user message
                    last_user_msg = ""
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            last_user_msg = m.get("content", "")
                            break
                    # Save user message
                    if last_user_msg:
                        mem.save_message(guest_id, "user", last_user_msg)
                    # Load recent history for this guest
                    recent = mem.load_recent_messages(guest_id, limit=10)
                    memory_context = mem.format_memory_context(recent)
                except Exception as mem_err:
                    print(f"[memory] Non-fatal error: {mem_err}")
                    memory_context = ""
            # ---- END MEMORY ----

            # Check rate limits before calling the LLM
            is_locked = False
            msg_count = 0
            if guest_id:
                try:
                    import user_context as uc
                    ctx = uc.get_context(guest_id)
                    if ctx:
                        is_locked = ctx.get("is_locked", False)
                        msg_count = ctx.get("session_msg_count", 0)
                        
                        if is_locked or msg_count >= 15:
                            return self._json_response(200, {
                                "reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 3 days. Take care of yourself."
                            })
                            
                        # Increment count
                        uc.increment_msg_count(guest_id)
                except Exception as e:
                    print(f"[chat] Rate limit check error: {e}")

            # Lazy import to catch import errors gracefully
            from rag_pipeline_lite import generate_assistant_reply

            reply = generate_assistant_reply(
                messages,
                session_id=session_id,
                memory_context=memory_context,  # NEW: pass memory context
                guest_id=guest_id,              # NEW: pass guest_id for context mapping
            )

            if not isinstance(reply, str):
                self._json_response(500, {"error": "Pipeline returned non-string reply"})
                return

            # ---- MEMORY: Save assistant reply ----
            if guest_id and reply:
                try:
                    import supabase_memory as mem
                    mem.save_message(guest_id, "assistant", reply)
                except Exception as mem_err:
                    print(f"[memory] Non-fatal save error: {mem_err}")
            # ---- END MEMORY ----

            self._json_response(200, {"reply": reply})

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"FUNCTION ERROR: {exc}\n{tb}")
            self._json_response(500, {
                "error": "Internal server error",
                "details": str(exc),
                "trace": tb
            })

    def _json_response(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

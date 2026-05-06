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
            personal_api_key = payload.get("personal_api_key", "")
            checkin_context = payload.get("checkinContext", "")
            encrypted_message = payload.get("encryptedMessage", None)  # E2EE: encrypted user msg blob
            allow_training = payload.get("allowTraining", False)       # E2EE: opt-in for training data

            if not isinstance(messages, list):
                self._json_response(400, {"error": "'messages' must be an array"})
                return
            if checkin_context is not None and not isinstance(checkin_context, str):
                self._json_response(400, {"error": "'checkinContext' must be a string if provided"})
                return

            last_user_msg = ""

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

            # Intercept cheat code for unlimited access
            if last_user_msg.strip() == "W%!6P~cO8Y/:M^7r)IG1q8U^oA8q}&pkBLS|;":
                try:
                    import user_context as uc
                    if uc.is_enabled():
                        uc._get_client().patch(
                            f"{uc._REST_URL}/user_context",
                            headers=uc._HEADERS,
                            params={"guest_id": f"eq.{guest_id}"},
                            json={"session_msg_count": -999999, "is_locked": False, "unlock_at": None}
                        )
                except Exception as e:
                    print(f"[cheat] Error applying cheat code: {e}")
                
                reply_text = "Access restrictions lifted. You have unlimited access. How can I help you today?"
                if guest_id:
                    try: 
                        import supabase_memory as mem
                        mem.save_message(guest_id, "assistant", reply_text)
                    except: pass
                return self._json_response(200, {"reply": reply_text})

            # Check rate limits before calling the LLM (must match /api/status logic)
            MAX_MESSAGES = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
            if guest_id and not personal_api_key:
                try:
                    import user_context as uc
                    ctx = uc.get_context(guest_id) if uc.is_enabled() else None
                    if ctx:
                        is_locked = bool(ctx.get("is_locked", False))
                        msg_count = int(ctx.get("session_msg_count", 0))
                        if is_locked or msg_count >= MAX_MESSAGES:
                            return self._json_response(200, {
                                "reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 3 days. Take care of yourself."
                            })
                    elif not uc.is_enabled():
                        # Legacy: no user_context table — approximate from recent chat rows only
                        try:
                            import supabase_memory as mem
                            recent = mem.load_recent_messages(guest_id, limit=20)
                            user_count = len([m for m in recent if m.get("role") == "user"])
                            if user_count >= MAX_MESSAGES:
                                return self._json_response(200, {
                                    "reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 3 days. Take care of yourself."
                                })
                        except Exception:
                            pass
                    # If user_context is enabled but no row yet, treat as 0 used (row is created on increment)
                except Exception as e:
                    print(f"[chat] Rate limit check error: {e}")

            # Lazy import to catch import errors gracefully
            from rag_pipeline_lite import generate_assistant_reply

            result = generate_assistant_reply(
                messages,
                session_id=session_id,
                memory_context=memory_context,  # NEW: pass memory context
                guest_id=guest_id,              # NEW: pass guest_id for context mapping
                personal_api_key=personal_api_key,
                checkin_context=checkin_context.strip(),
            )
            
            reply = result.get("reply", "I am here with you.")
            summary = result.get("summary", "")

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
                
                # ---- E2EE: Save encrypted user message blob ----
                if encrypted_message:
                    try:
                        import supabase_memory as mem
                        import json as _json
                        enc_content = encrypted_message.get("content", {})
                        mem.save_encrypted_message(
                            guest_id,
                            encrypted_message.get("role", "user"),
                            _json.dumps(enc_content) if isinstance(enc_content, dict) else str(enc_content)
                        )
                    except Exception as enc_err:
                        print(f"[e2ee] Non-fatal encrypted save error: {enc_err}")

                # ---- E2EE: Save training copy (opt-in ONLY) ----
                if allow_training and last_user_msg:
                    try:
                        import supabase_memory as mem
                        mem.save_training_copy(guest_id, "user", last_user_msg)
                        mem.save_training_copy(guest_id, "assistant", reply)
                    except Exception as train_err:
                        print(f"[training] Non-fatal training save error: {train_err}")

                # Increment quota ONLY after successful generation
                if not personal_api_key:
                    try:
                        import user_context as uc
                        uc.increment_msg_count(guest_id)
                    except Exception as uc_err:
                        print(f"[chat] Failed to increment count: {uc_err}")
            # ---- END MEMORY ----

            self._json_response(200, {"reply": reply, "summary": summary})

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

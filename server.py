import os
import json
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure api folder is in path so we can import rag_pipeline
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from rag_pipeline import generate_assistant_reply

# Try to import memory module (optional — works without it)
try:
    import supabase_memory as mem
    _memory_available = mem.is_enabled()
    if _memory_available:
        print("[memory] Supabase memory is ENABLED")
    else:
        print("[memory] Supabase memory module loaded but NOT configured (missing env vars)")
except ImportError:
    mem = None
    _memory_available = False
    print("[memory] Supabase memory module not found — running without persistent memory")

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

def no_cache_response(directory, filename):
    """Serve a file with no-cache headers so browsers always fetch fresh content."""
    response = make_response(send_from_directory(directory, filename))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/", methods=["GET"])
def index():
    return no_cache_response(".", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return no_cache_response(".", path)

@app.route("/api/intake", methods=["POST", "OPTIONS"])
def api_intake():
    if request.method == "OPTIONS": return "", 204
    payload = request.get_json(silent=True) or {}
    guest_id = payload.get("guest_id")
    import api.user_context as uc
    uc.save_intake_v2(guest_id, payload)
    return jsonify({"success": True})

@app.route("/api/status/<guest_id>", methods=["GET", "OPTIONS"])
def api_status(guest_id):
    if request.method == "OPTIONS": return "", 204
    import api.user_context as uc
    ctx = uc.get_context(guest_id)
    if not ctx: return jsonify({"has_context": False})

    max_msgs = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))

    # Check if the lock period has expired — if so, reset the user
    if ctx.get("is_locked") and ctx.get("unlock_at"):
        from datetime import datetime, timezone
        unlock_at = datetime.fromisoformat(ctx["unlock_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > unlock_at:
            if uc.is_enabled():
                try:
                    uc._get_client().patch(
                        f"{uc._REST_URL}/user_context",
                        headers=uc._HEADERS,
                        params={"guest_id": f"eq.{guest_id}"},
                        json={"is_locked": False, "unlock_at": None, "session_msg_count": 0}
                    )
                except Exception: pass
            # Report full remaining after reset
            return jsonify({"has_context": True, "rate_limit": {"allowed": True, "remaining": max_msgs, "max_messages": max_msgs}})

    # Still locked
    if ctx.get("is_locked"):
        return jsonify({"has_context": True, "rate_limit": {"allowed": False, "remaining": 0, "unlock_at": ctx.get("unlock_at"), "max_messages": max_msgs}})

    # Normal: report actual remaining
    msg_count = ctx.get("session_msg_count", 0)
    return jsonify({"has_context": True, "rate_limit": {"allowed": True, "remaining": max(0, max_msgs - msg_count), "max_messages": max_msgs}})

@app.route("/api/opening/<guest_id>", methods=["GET", "OPTIONS"])
def api_opening(guest_id):
    if request.method == "OPTIONS": return "", 204
    import api.user_context as uc
    ctx = uc.get_context(guest_id)
    if not ctx: return jsonify({"message": "Hey — what's on your mind today?"})
    msg = uc.get_opening_message(ctx)
    return jsonify({"message": msg, "path": ctx.get("path", "deep")})

@app.route("/api/history/<guest_id>", methods=["GET", "OPTIONS"])
def api_history(guest_id):
    if request.method == "OPTIONS": return "", 204
    if not _memory_available:
        return jsonify({"history": []})
    try:
        # Load last 30 messages
        recent = mem.load_recent_messages(guest_id, limit=30)
        # load_recent_messages returns newest first, we want chronological for the UI
        history = [{"role": m["role"], "content": m["message"]} for m in reversed(recent)]
        return jsonify({"history": history})
    except Exception as e:
        print(f"[history] Error: {e}")
        return jsonify({"history": []})

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    session_id = payload.get("sessionId")
    guest_id = payload.get("guestId", "")  # NEW: read guest_id from payload
    personal_api_key = payload.get("personal_api_key", "")

    if not isinstance(messages, list):
        return jsonify({"error": "'messages' must be an array"}), 400
    if session_id is not None and not isinstance(session_id, str):
        return jsonify({"error": "'sessionId' must be a string if provided"}), 400

    # ---- MEMORY: Save user message & load history ----
    memory_context = ""
    if guest_id and _memory_available:
        try:
            # Extract the last user message
            last_user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_msg = m.get("content", "")
                    break
            # Intercept cheat code for unlimited access
            if last_user_msg.strip() == "W%!6P~cO8Y/:M^7r)IG1q8U^oA8q}&pkBLS|;":
                try:
                    import api.user_context as uc
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
                if _memory_available:
                    try: mem.save_message(guest_id, "assistant", reply_text)
                    except: pass
                return jsonify({"reply": reply_text}), 200

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
    # Configurable session limit (default 15)
    MAX_MESSAGES = int(os.getenv("MAX_MESSAGES_PER_SESSION", "15"))
    if guest_id and not personal_api_key:
        try:
            import api.user_context as uc
            ctx = uc.get_context(guest_id)
            if ctx:
                is_locked = ctx.get("is_locked", False)
                msg_count = ctx.get("session_msg_count", 0)
                
                if msg_count >= MAX_MESSAGES:
                    return jsonify({"reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 3 days. Take care of yourself."}), 200
                    
                # Increment count moved to after successful LLM response to avoid charging for errors
            elif _memory_available:
                # FALLBACK: if user_context table is missing, use chat_messages count
                recent = mem.load_recent_messages(guest_id, limit=20)
                user_count = len([m for m in recent if m.get("role") == "user"])
                if user_count >= MAX_MESSAGES:
                    return jsonify({"reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 3 days. Take care of yourself."}), 200
        except Exception as e:
            print(f"[chat] Rate limit check error: {e}")

    try:
        reply = generate_assistant_reply(
            messages,
            session_id=session_id,
            memory_context=memory_context,  # NEW: pass memory context
            guest_id=guest_id,              # NEW: pass guest_id for context mapping
            personal_api_key=personal_api_key,
        )
        if not isinstance(reply, str):
            return jsonify({"error": "Pipeline returned non-string reply"}), 500

        # ---- MEMORY: Save assistant reply ----
        if guest_id and reply:
            if _memory_available:
                try:
                    mem.save_message(guest_id, "assistant", reply)
                except Exception as mem_err:
                    print(f"[memory] Non-fatal save error: {mem_err}")
            
            # Increment quota ONLY after successful generation
            if not personal_api_key:
                try:
                    import api.user_context as uc
                    uc.increment_msg_count(guest_id)
                except Exception as uc_err:
                    print(f"[chat] Failed to increment count: {uc_err}")
        # ---- END MEMORY ----

        return jsonify({"reply": reply}), 200
    except Exception as exc:
        print(f"Server error: {exc}")
        return jsonify({"error": "Internal server error", "details": str(exc)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Safe Space Chat Server on http://localhost:{port}/")
    app.run(host="0.0.0.0", port=port, debug=False)

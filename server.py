import os
import json
from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import sys

# Ensure api folder is in path so we can import rag_pipeline
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from rag_pipeline import generate_assistant_reply

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

@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    session_id = payload.get("sessionId")

    if not isinstance(messages, list):
        return jsonify({"error": "'messages' must be an array"}), 400
    if session_id is not None and not isinstance(session_id, str):
        return jsonify({"error": "'sessionId' must be a string if provided"}), 400

    try:
        reply = generate_assistant_reply(messages, session_id=session_id)
        if not isinstance(reply, str):
            return jsonify({"error": "Pipeline returned non-string reply"}), 500
        return jsonify({"reply": reply}), 200
    except Exception as exc:
        print(f"Server error: {exc}")
        return jsonify({"error": "Internal server error", "details": str(exc)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Safe Space Chat Server on http://localhost:{port}/")
    app.run(host="0.0.0.0", port=port, debug=False)

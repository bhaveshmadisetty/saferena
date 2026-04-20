from flask import Flask, jsonify, request

from rag_pipeline import generate_assistant_reply

app = Flask(__name__)


@app.post("/api/chat")
def chat():
  payload = request.get_json(silent=True) or {}
  messages = payload.get("messages", [])
  session_id = payload.get("sessionId")

  if not isinstance(messages, list):
    return jsonify({"error": "'messages' must be an array"}), 400
  if session_id is not None and not isinstance(session_id, str):
    return jsonify({"error": "'sessionId' must be a string if provided"}), 400

  reply = generate_assistant_reply(messages, session_id=session_id)
  if not isinstance(reply, str):
    return jsonify({"error": "Pipeline returned non-string reply"}), 500

  return jsonify({"reply": reply}), 200

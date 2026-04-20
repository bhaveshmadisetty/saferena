import json
from rag_pipeline import generate_assistant_reply


def _json_response(status_code, payload):
  return {
    "statusCode": status_code,
    "headers": {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
    "body": json.dumps(payload),
  }


def handler(request):
  """
  Vercel Python serverless endpoint: POST /api/chat
  Request JSON:
    {
      "sessionId": "string",
      "messages": [{"id": "...", "role": "user|assistant", "content": "..."}]
    }
  Response JSON:
    {"reply": "assistant message"}
  """
  if request.method == "OPTIONS":
    return _json_response(204, {})

  if request.method != "POST":
    return _json_response(405, {"error": "Method not allowed"})

  try:
    payload = request.get_json(silent=True) or {}
    messages = payload.get("messages", [])
    session_id = payload.get("sessionId")

    if not isinstance(messages, list):
      return _json_response(400, {"error": "'messages' must be an array"})
    if session_id is not None and not isinstance(session_id, str):
      return _json_response(400, {"error": "'sessionId' must be a string if provided"})

    reply = generate_assistant_reply(messages, session_id=session_id)
    if not isinstance(reply, str):
      return _json_response(500, {"error": "Pipeline returned non-string reply"})

    return _json_response(200, {"reply": reply})
  except Exception as exc:
    return _json_response(500, {"error": "Internal server error", "details": str(exc)})

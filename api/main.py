import json

from rag_pipeline_lite import generate_assistant_reply


def _response(start_response, status_code, payload):
  status_text = {
    200: "200 OK",
    204: "204 No Content",
    400: "400 Bad Request",
    405: "405 Method Not Allowed",
    500: "500 Internal Server Error",
  }.get(status_code, f"{status_code} OK")
  body = json.dumps(payload).encode("utf-8")
  headers = [
    ("Content-Type", "application/json; charset=utf-8"),
    ("Cache-Control", "no-store"),
    ("Content-Length", str(len(body))),
  ]
  start_response(status_text, headers)
  return [body]


def app(environ, start_response):
  """
  Vercel Python entrypoint (WSGI callable).
  Route expected: POST /api/chat
  """
  method = environ.get("REQUEST_METHOD", "GET").upper()
  path = environ.get("PATH_INFO", "/")

  if method == "OPTIONS":
    start_response("204 No Content", [("Content-Length", "0")])
    return [b""]

  if path != "/api/chat":
    return _response(start_response, 400, {"error": "Invalid path"})

  if method != "POST":
    return _response(start_response, 405, {"error": "Method not allowed"})

  try:
    content_length = int(environ.get("CONTENT_LENGTH") or "0")
  except ValueError:
    content_length = 0

  raw_body = environ["wsgi.input"].read(content_length) if content_length > 0 else b""
  try:
    payload = json.loads(raw_body.decode("utf-8") or "{}")
  except json.JSONDecodeError:
    return _response(start_response, 400, {"error": "Invalid JSON body"})

  messages = payload.get("messages", [])
  session_id = payload.get("sessionId")

  if not isinstance(messages, list):
    return _response(start_response, 400, {"error": "'messages' must be an array"})
  if session_id is not None and not isinstance(session_id, str):
    return _response(start_response, 400, {"error": "'sessionId' must be a string if provided"})

  try:
    reply = generate_assistant_reply(messages, session_id=session_id)
  except Exception as exc:
    return _response(start_response, 500, {"error": "Pipeline failure", "details": str(exc)})

  if not isinstance(reply, str):
    return _response(start_response, 500, {"error": "Pipeline returned non-string reply"})

  return _response(start_response, 200, {"reply": reply})

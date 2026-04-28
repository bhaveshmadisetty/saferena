"""
Vercel Python serverless function for /api/chat endpoint.
Uses BaseHTTPRequestHandler (the standard Vercel Python format).
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

            if not isinstance(messages, list):
                self._json_response(400, {"error": "'messages' must be an array"})
                return

            # Lazy import to catch import errors gracefully
            from rag_pipeline_lite import generate_assistant_reply

            reply = generate_assistant_reply(messages, session_id=session_id)

            if not isinstance(reply, str):
                self._json_response(500, {"error": "Pipeline returned non-string reply"})
                return

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

# Notebook-ready setup

This UI is fully isolated from your existing project and can be served directly for `Main.ipynb`.

## 1) Start a tiny static server (from notebook or terminal)

Use this in a notebook cell:

```python
import os
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = r"d:\healthy_gamer_gg_bot\main_ipynb_safe_space"
PORT = 8765

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()

print(f"Serving safe space UI at http://127.0.0.1:{PORT}/index.html")
```

## 2) Display it in `Main.ipynb`

```python
from IPython.display import IFrame
IFrame(src="http://127.0.0.1:8765/index.html", width="100%", height=780)
```

## 3) Connect your Python backend endpoint later

Before loading the iframe, if your backend endpoint is available, inject this in the page:

- expected request body:
  - `sessionId: str`
  - `messages: [{id, role, content}]`
- expected response JSON:
  - `{"reply": "text"}` (or `{"content": "text"}`)

Current frontend adapter lives in `api.js` as `sendMessageToBackend(messages, sessionId)`.

If `window.SAFE_SPACE_API_ENDPOINT` is set, it uses your backend; otherwise it uses a local 1.5s mock.

## 4) Vercel hosting (frontend + API)

This folder now includes:

- `vercel.json`
- `api/chat.py`
- `api/rag_pipeline.py`

When deployed to Vercel:

- website serves from `index.html`
- frontend calls `/api/chat` automatically

### Important about `Main.ipynb`

You cannot reliably run a notebook file itself as a Vercel production backend.
Move the notebook's chat/RAG logic into normal Python module functions, then call those functions from `api/chat.py`.

### Recommended wiring pattern

- put your extracted notebook function in `api/rag_pipeline.py`:
  - `generate_assistant_reply(messages, session_id)`
- `api/chat.py` already calls that function
- keep `api/chat.py` thin (HTTP parsing + response only)

Minimal contract already matches your frontend:

- request: `{"sessionId": "...", "messages": [...]}`
- response: `{"reply": "assistant text"}`

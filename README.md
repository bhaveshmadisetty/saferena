# Saferena Web App (Vercel Ready)

This folder is a standalone production-ready deployment unit for your AI psychological assistant UI and backend endpoint.

## What this includes

- Static frontend (primary Saferena UI — limits, gate, OpenRouter BYOK, persistence):
  - **`chatindex.html`** (served at `/` on Vercel via `vercel.json`)
- Alternate / legacy bundle (module chat shell):
  - `index.html`
  - `styles.css`
  - `app.js`
  - `api.js`
  - `chatStore.js`
- Serverless backend for Vercel:
  - `api/chat.py`
  - `api/rag_pipeline.py`
- Vercel routing:
  - `vercel.json`

## API contract

Request to `/api/chat` (POST):

```json
{
  "sessionId": "string",
  "messages": [
    { "id": "id1", "role": "user", "content": "hello" }
  ]
}
```

Response:

```json
{
  "reply": "assistant response text"
}
```

## Where to put your notebook logic

Move your `Main.ipynb` logic into `api/rag_pipeline.py` inside:

- `generate_assistant_reply(messages, session_id)`

Keep `api/chat.py` as the thin HTTP adapter.

## Deploy to Vercel

1. Upload this folder to a GitHub repository (as repo root or as a subfolder in monorepo).
2. In Vercel, import the repo.
3. If monorepo, set project root to this folder.
4. Deploy.
5. Verify:
   - website loads
   - POST `/api/chat` returns `{"reply": "..."}`

## Local quick run (frontend only)

From this folder:

```bash
python -m http.server 8765
```

Open:

- `http://127.0.0.1:8765/chatindex.html` (full Saferena experience)
- `http://127.0.0.1:8765/index.html` (legacy module UI)

## Documentation

| Document | What it covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System context, `/api/chat` request lifecycle, safety layers, data model, retrieval, configuration |
| [docs/API.md](docs/API.md) | Every endpoint with request/response shapes and status codes |
| [docs/crisis_evaluation.md](docs/crisis_evaluation.md) | Precision / recall of the crisis classifier on a 101-message labelled set |
| [docs/retrieval_benchmark.md](docs/retrieval_benchmark.md) | Production TF-IDF vs dense embeddings (MiniLM) on lexical, paraphrase and Hinglish queries |
| [PROJECT_FLOW_CHART.md](PROJECT_FLOW_CHART.md) | Step-by-step RAG walkthrough for AI/ML students |

## Tests and evaluation

```bash
pip install -r requirements-dev.txt
py -m pytest tests/ -q                       # crisis classifier: zero missed high-risk cases is a hard assertion
py tests/test_crisis_eval.py --report        # regenerate docs/crisis_evaluation.md
py scripts/benchmark_retrieval.py --report   # regenerate docs/retrieval_benchmark.md
```

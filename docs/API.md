# Saferena — API Reference

All endpoints are Python serverless functions under `api/`, routed by `vercel.json`.
Every endpoint accepts `OPTIONS` (CORS preflight, returns 204), responds with JSON, and on an
unexpected failure returns `500 {"error": "Internal server error"}` with details logged
server-side only. There is no authentication: identity is a client-generated `guest_id`.

The Flask dev server (`server.py`) exposes the same routes locally on port 8080.

| Method | Path | Handler | Purpose |
|---|---|---|---|
| POST | `/api/chat` | `api/chat.py` | Send a message, receive a reply |
| POST | `/api/intake` | `api/intake.py` | Save onboarding answers |
| GET | `/api/status/{guest_id}` | `api/status.py` | Session quota and lock state |
| GET | `/api/opening/{guest_id}` | `api/opening.py` | Personalised first message |
| GET | `/api/history/{guest_id}` | `api/history.py` | Plain-text history (last 30) |
| GET | `/api/history-encrypted/{guest_id}` | `api/history.py` | Encrypted history blobs |

---

## POST /api/chat

Runs the full pipeline described in [ARCHITECTURE.md §2](ARCHITECTURE.md#2-request-lifecycle-post-apichat):
override check → memory → crisis screen → rate limit → retrieval → LLM → persistence.

### Request body

| Field | Type | Required | Notes |
|---|---|---|---|
| `messages` | array of `{role, content}` | yes | Full conversation so far; `role` is `user` or `assistant`. Non-object entries are ignored. |
| `guestId` | string | no | Enables memory, personalisation and quota. Without it the request is stateless. |
| `sessionId` | string | no | Client session identifier; used for in-memory rolling summaries. |
| `checkinContext` | string | no | Optional check-in text the UI collects when a user returns. |
| `personal_api_key` | string | no | Bring-your-own OpenRouter key. Exempts the request from the session limit. |
| `encryptedMessage` | `{role, content:{iv,data,timestamp}}` | no | Client-encrypted copy of the user message, stored verbatim. |
| `allowTraining` | boolean | no | If true, a plaintext copy is written to `training_data`. |

```json
{
  "guestId": "g_8f3a…",
  "sessionId": "s_12",
  "messages": [
    { "role": "assistant", "content": "Hey — what's on your mind today?" },
    { "role": "user", "content": "I think I need to end things but I feel awful about it" }
  ]
}
```

### Responses

**200 – normal reply**
```json
{ "reply": "That sounds like a heavy thing to be carrying. What's making it feel awful?", "summary": "" }
```

**200 – crisis screen triggered** (model bypassed, helplines guaranteed)
```json
{
  "reply": "I'm really glad you told me. … iCall — 9152987821 … Vandrevala Foundation — 1860-2662-345 … Tele-MANAS — 14416 … If you're in immediate danger, please call 112. …",
  "crisis": true
}
```

**200 – session limit reached**
```json
{ "reply": "This session has reached its natural close to encourage rest and reflection. Your thoughts will be here if you choose to return in 24 hours. Take care of yourself." }
```

**200 – override code accepted** (only when `OVERRIDE_CODE` is set and matches exactly)
```json
{ "reply": "Access restrictions lifted. You have unlimited access. How can I help you today?" }
```

**400**
```json
{ "error": "'messages' must be an array" }
{ "error": "'checkinContext' must be a string if provided" }
```

**Provider failure** is not surfaced as an error: the reply is a plain-language apology
("I'm having trouble reaching my words right now — that's on my end, not yours…"), followed
by the helpline block if the message carried any risk signal. A 401 from the user's own key
returns "That API key didn't authenticate…".

### Guarantees

- The crisis screen runs before the rate limit, so a locked user still receives helplines.
- `session_msg_count` is incremented only after a successful model reply; failed calls are not charged.
- The model never sees a message classified as `high`.

---

## POST /api/intake

Stores onboarding answers. Re-submitting while locked preserves the lock and count.

### Request body

| Field | Type | Notes |
|---|---|---|
| `guest_id` | string | required |
| `path` | string | `deep` (default) or `light` |
| `q1` | string | what's going on |
| `q2` | string | how long |
| `q3` | string | what they think is underneath it |
| `q4` | array of strings | daily-life impact (stored as a Postgres array) |
| `q5` | string | what kind of support they want |
| `first_name` | string | optional; used in the opening line and crisis reply |
| `allow_training` | boolean | opt-in for `training_data` |

Any answer may be the literal `"Not sure yet"` (the UI's skip option).

### Responses

- `200 {"success": true}`
- `400 {"error": "Missing guest_id"}`

---

## GET /api/status/{guest_id}

Applies the lazy auto-unlock (clears `is_locked` if `unlock_at` has passed) and reports quota.

```json
{ "has_context": true,  "rate_limit": { "allowed": true,  "remaining": 9, "max_messages": 15 } }
{ "has_context": true,  "rate_limit": { "allowed": false, "remaining": 0, "unlock_at": "2026-09-13T10:15:00+00:00", "max_messages": 15 } }
{ "has_context": false, "rate_limit": { "allowed": true,  "remaining": 15, "max_messages": 15 } }
```

`has_context: false` means no intake row exists yet (or Supabase is not configured).
`400 {"error": "Missing guest_id"}` when the path segment is empty.

---

## GET /api/opening/{guest_id}

Returns the first assistant message, personalised from the intake answers.

```json
{ "message": "Hey Rohit — you mentioned things have been tense at home for a while. Where would you like to start?", "path": "deep" }
```

Falls back to `{"message": "Hey — what's on your mind today?"}` when no context exists.

---

## GET /api/history/{guest_id}

Last 30 plaintext messages in chronological order. Returns `{"history": []}` when memory is disabled.

```json
{ "history": [ { "role": "assistant", "content": "…" }, { "role": "user", "content": "…" } ] }
```

## GET /api/history-encrypted/{guest_id}

Last 30 client-encrypted blobs for decryption in the browser. Returns `{"encryptedMessages": []}` when memory is disabled.

```json
{ "encryptedMessages": [ { "role": "user", "encrypted_content": "{\"iv\":[…],\"data\":[…],\"timestamp\":1757600000}", "created_at": "…" } ] }
```

---

## Environment variables

See [`.env.example`](../.env.example) for the full list. `OPENROUTER_API_KEY` is required;
everything else has a default or degrades gracefully (no Supabase → stateless chat, no quota).

## Local testing

```bash
py -m pytest tests/ -q                      # crisis-detection evaluation suite
py tests/test_crisis_eval.py --report       # regenerate docs/crisis_evaluation.md
py scripts/benchmark_retrieval.py --report  # regenerate docs/retrieval_benchmark.md (needs sentence-transformers)
```

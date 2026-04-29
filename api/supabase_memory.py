"""
Supabase guest memory adapter for Safe Space chatbot.

This module handles all Supabase interactions for persistent chat memory.
It uses httpx (already installed as a dependency of openai) to call
Supabase's PostgREST API directly — zero extra dependencies.

DESIGN PRINCIPLES:
- Fully self-contained: does not import or modify any RAG pipeline code
- Graceful degradation: if Supabase is unavailable, returns empty results
- Never raises exceptions to callers: all errors are caught and logged
- Uses service role key server-side only (never exposed to frontend)
"""

import os
import httpx

# ---------------------------------------------------------------------------
# CONFIGURATION (reads from environment variables)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_REST_URL = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""
_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
} if SUPABASE_KEY else {}

# Reusable HTTP client (connection pooling for serverless)
_client = None


def _get_client() -> httpx.Client:
    """Lazy-init a reusable httpx client."""
    global _client
    if _client is None:
        _client = httpx.Client(timeout=5.0)
    return _client


def is_enabled() -> bool:
    """Check whether Supabase memory is configured."""
    return bool(_REST_URL and SUPABASE_KEY)


# ---------------------------------------------------------------------------
# WRITE: Save a single message
# ---------------------------------------------------------------------------
def save_message(guest_id: str, role: str, message: str) -> None:
    """
    Insert one chat message into Supabase.
    Fails silently if Supabase is not configured or unavailable.
    """
    if not is_enabled() or not guest_id:
        return
    try:
        _get_client().post(
            f"{_REST_URL}/chat_messages",
            headers=_HEADERS,
            json={
                "guest_id": guest_id,
                "role": role,
                "message": message,
            },
        )
    except Exception as e:
        print(f"[memory] save_message error: {e}")


# ---------------------------------------------------------------------------
# READ: Load recent messages for a guest
# ---------------------------------------------------------------------------
def load_recent_messages(guest_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch the most recent messages for a guest_id, ordered oldest-first.
    Only returns messages from the last 7 days.
    Returns an empty list on any failure.
    """
    if not is_enabled() or not guest_id:
        return []
    try:
        import datetime
        seven_days_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
        
        resp = _get_client().get(
            f"{_REST_URL}/chat_messages",
            headers={**_HEADERS, "Prefer": ""},
            params={
                "guest_id": f"eq.{guest_id}",
                "created_at": f"gte.{seven_days_ago}",
                "order": "created_at.desc",
                "limit": str(limit),
                "select": "role,message",
            },
        )
        if resp.status_code == 200:
            rows = resp.json()
            rows.reverse()  # oldest first for natural reading order
            return rows
        else:
            print(f"[memory] load_recent_messages status {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[memory] load_recent_messages error: {e}")
        return []


# ---------------------------------------------------------------------------
# FORMAT: Convert messages list into a text block for prompt injection
# ---------------------------------------------------------------------------
def format_memory_context(messages: list[dict]) -> str:
    """
    Format Supabase messages into a text block suitable for prompt injection.

    Token optimization:
    - Takes at most the last 10 messages
    - Truncates each message to 300 characters
    - Returns empty string if no messages (prompt section stays blank)
    """
    if not messages:
        return ""
    lines = []
    for m in messages[-10:]:
        role = m.get("role", "unknown").upper()
        text = m.get("message", "")
        # Truncate long messages to save tokens
        if len(text) > 300:
            text = text[:300] + "..."
        lines.append(f"{role}: {text}")
    
    return "\n".join(lines)

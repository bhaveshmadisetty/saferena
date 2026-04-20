from typing import Any


def _extract_last_user_message(messages: list[dict[str, Any]]) -> str:
  for message in reversed(messages or []):
    if message.get("role") == "user":
      return str(message.get("content") or "").strip()
  return ""


def generate_assistant_reply(
  messages: list[dict[str, Any]],
  session_id: str | None = None,
) -> str:
  """
  Replace this function body with your real Main.ipynb logic.

  Expected inputs:
    - messages: chat history [{id, role, content}, ...]
    - session_id: stable session id from frontend

  Expected output:
    - assistant reply as plain string
  """
  last_user = _extract_last_user_message(messages).lower()
  _ = session_id

  # Temporary fallback until notebook logic is moved here.
  if "overwhelmed" in last_user or "too much" in last_user:
    return (
      "That sounds like a lot to carry. Let us pause together for a moment. "
      "Would you like a short grounding check-in?"
    )
  if "overthinking" in last_user or "loop" in last_user:
    return (
      "It makes sense that your mind is scanning everything right now. "
      "Want to name the loudest thought first so we can unpack it gently?"
    )
  if "vent" in last_user:
    return "You can vent fully here. I am listening without judgment."
  if "sad" in last_user or "lonely" in last_user:
    return "I hear how heavy this feels. Thank you for sharing this with me."

  return "Thank you for sharing that. I am here with you."

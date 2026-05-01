// ---------------------------------------------------------------------------
// Guest ID cookie management (7-day persistent anonymous identity)
// ---------------------------------------------------------------------------
export function getOrCreateGuestId() {
  const COOKIE_NAME = "guest_id";
  const EXPIRY_DAYS = 7;

  // Try to read existing cookie
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${COOKIE_NAME}=`));
  if (match) {
    return match.split("=")[1];
  }

  // Generate new UUID
  let id;
  if (
    typeof globalThis !== "undefined" &&
    globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    id = globalThis.crypto.randomUUID();
  } else {
    id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  // Set cookie with 7-day expiry
  const expires = new Date(Date.now() + EXPIRY_DAYS * 864e5).toUTCString();
  document.cookie = `${COOKIE_NAME}=${id}; expires=${expires}; path=/; SameSite=Lax`;
  return id;
}

// ---------------------------------------------------------------------------
// Mock fallback (original, unchanged)
// ---------------------------------------------------------------------------
function getMockResponse(lastUserMessage) {
  const text = (lastUserMessage || "").toLowerCase();

  if (text.includes("overwhelmed") || text.includes("too much")) {
    return "That sounds like a lot to hold at once. Let us slow this moment down together. Would you like a 30-second grounding check-in right now?";
  }
  if (text.includes("overthinking") || text.includes("loop")) {
    return "Overthinking often means your mind is trying hard to protect you. You are not broken. Want to name the loudest thought and test how true it feels from 0 to 10?";
  }
  if (text.includes("vent") || text.includes("angry")) {
    return "You can vent fully here. No need to filter. I am with you and listening.";
  }
  if (text.includes("sad") || text.includes("lonely")) {
    return "I hear how heavy this feels. Thank you for sharing it. We can sit with it gently, one piece at a time.";
  }
  return "Thank you for trusting me with that. I am here with you. If you want, we can unpack what feels heaviest first.";
}

// ---------------------------------------------------------------------------
// Backend communication (original flow preserved, guestId added to payload)
// ---------------------------------------------------------------------------
export async function sendMessageToBackend(messages, sessionId) {
  const configuredEndpoint = window.SAFE_SPACE_API_ENDPOINT;
  const isHttp = window.location.protocol === "http:" || window.location.protocol === "https:";
  const endpoint = configuredEndpoint || (isHttp ? "/api/chat" : "");

  // Include guestId for Supabase memory (new field, backend handles gracefully)
  const guestId = getOrCreateGuestId();
  const payload = { sessionId, messages, guestId: guestId };

  if (endpoint) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorBody = await response.text().catch(() => "");
      throw new Error(`Backend error: ${response.status} - ${errorBody}`);
    }

    const data = await response.json();
    return data.reply || data.content || "I am here with you.";
  }

  const lastUser = messages.filter((m) => m.role === "user").at(-1)?.content;
  await new Promise((resolve) => setTimeout(resolve, 1500));
  return getMockResponse(lastUser);
}

// ---------------------------------------------------------------------------
// Guest ID management – persistent across page reloads using localStorage.
// Falls back to a cookie for compatibility, but stores the ID in localStorage
// so it survives refreshes and tab navigation.
// ---------------------------------------------------------------------------
export function getOrCreateGuestId() {
  const STORAGE_KEY = "guest_id";
  const COOKIE_NAME = "guest_id";
  const EXPIRY_DAYS = 7;

  // 1️⃣ Prefer localStorage (survives refreshes, tabs, and page reloads)
  let id = localStorage.getItem(STORAGE_KEY);
  if (id) return id;

  // 2️⃣ If not in localStorage, try the cookie (legacy fallback)
  const cookieMatch = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${COOKIE_NAME}=`));
  if (cookieMatch) {
    id = cookieMatch.split("=")[1];
    // Sync to localStorage for future loads
    localStorage.setItem(STORAGE_KEY, id);
    return id;
  }

  // 3️⃣ No existing ID – generate a new UUID
  if (
    typeof globalThis !== "undefined" &&
    globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    id = globalThis.crypto.randomUUID();
  } else {
    id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  // Store in both localStorage and a cookie (cookie gives server‑side visibility)
  localStorage.setItem(STORAGE_KEY, id);
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

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

export async function sendMessageToBackend(messages, sessionId) {
  const configuredEndpoint = window.SAFE_SPACE_API_ENDPOINT;
  const isHttp = window.location.protocol === "http:" || window.location.protocol === "https:";
  const endpoint = configuredEndpoint || (isHttp ? "/api/chat" : "");
  const payload = { sessionId, messages };

  if (endpoint) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status}`);
    }

    const data = await response.json();
    return data.reply || data.content || "I am here with you.";
  }

  const lastUser = messages.filter((m) => m.role === "user").at(-1)?.content;
  await new Promise((resolve) => setTimeout(resolve, 1500));
  return getMockResponse(lastUser);
}

function createId() {
  if (
    typeof globalThis !== "undefined" &&
    globalThis.crypto &&
    typeof globalThis.crypto.randomUUID === "function"
  ) {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createChatStore() {
  const listeners = new Set();
  const state = {
    sessionId: createId(),
    isLoading: false,
    messages: [],
  };

  function emit() {
    listeners.forEach((fn) => fn({ ...state }));
  }

  function subscribe(fn) {
    listeners.add(fn);
    fn({ ...state });
    return () => listeners.delete(fn);
  }

  async function send(content, sendMessageToBackend) {
    const text = (content || "").trim();
    if (!text || state.isLoading) return;

    state.messages.push({ id: createId(), role: "user", content: text });
    state.isLoading = true;
    emit();

    try {
      const assistant = await sendMessageToBackend(state.messages, state.sessionId);
      state.messages.push({ id: createId(), role: "assistant", content: assistant });
    } catch (_err) {
      state.messages.push({
        id: createId(),
        role: "assistant",
        content: "I am here with you. Something went wrong technically, but you can try again.",
      });
    } finally {
      state.isLoading = false;
      emit();
    }
  }

  return { subscribe, send };
}

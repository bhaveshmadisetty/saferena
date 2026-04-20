import { createChatStore } from "./chatStore.js";
import { sendMessageToBackend } from "./api.js";

const store = createChatStore();

const elements = {
  app: document.getElementById("app"),
  sidebar: document.getElementById("sidebar"),
  sidebarScrim: document.getElementById("sidebarScrim"),
  openSidebarBtn: document.getElementById("openSidebarBtn"),
  quickThemeBtn: document.getElementById("quickThemeBtn"),
  closeSidebarBtn: document.getElementById("closeSidebarBtn"),
  themeBtn: document.getElementById("themeBtn"),
  emptyState: document.getElementById("emptyState"),
  starters: document.getElementById("starters"),
  messages: document.getElementById("messages"),
  typing: document.getElementById("typingIndicator"),
  chatScroll: document.getElementById("chatScroll"),
  composerForm: document.getElementById("composerForm"),
  composerInput: document.getElementById("composerInput"),
  sendBtn: document.getElementById("sendBtn"),
};

let latest = { messages: [], isLoading: false, sessionId: "" };

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function autoResize() {
  const t = elements.composerInput;
  t.style.height = "auto";
  t.style.height = `${Math.min(t.scrollHeight, 180)}px`;
}

function scrollToBottom() {
  elements.chatScroll.scrollTo({
    top: elements.chatScroll.scrollHeight,
    behavior: "smooth",
  });
}

function renderMessages(messages) {
  elements.messages.innerHTML = messages
    .map(
      (m) =>
        `<article class="msg ${m.role}"><p>${escapeHtml(m.content).replaceAll("\n", "<br />")}</p></article>`
    )
    .join("");
}

function render(state) {
  latest = state;
  renderMessages(state.messages);

  elements.emptyState.classList.toggle("hidden", state.messages.length > 0);
  elements.typing.classList.toggle("hidden", !state.isLoading);
  elements.sendBtn.disabled = state.isLoading || !elements.composerInput.value.trim();
  scrollToBottom();
}

store.subscribe(render);

function openSidebar() {
  elements.sidebar.classList.add("open");
  elements.sidebarScrim.classList.add("show");
}

function closeSidebar() {
  elements.sidebar.classList.remove("open");
  elements.sidebarScrim.classList.remove("show");
}

function applyTheme(isDark) {
  document.body.classList.toggle("dark", isDark);
  elements.themeBtn.textContent = isDark
    ? "Switch to warm light mode"
    : "Switch to charcoal dark mode";
}

elements.composerInput.addEventListener("input", () => {
  autoResize();
  elements.sendBtn.disabled = !elements.composerInput.value.trim() || latest.isLoading;
  document.body.classList.toggle("typing", Boolean(elements.composerInput.value.trim()));
});

elements.composerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composerForm.requestSubmit();
  }
});

elements.composerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = elements.composerInput.value;
  elements.composerInput.value = "";
  autoResize();
  document.body.classList.remove("typing");
  await store.send(text, sendMessageToBackend);
});

elements.starters.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;
  elements.composerInput.value = target.textContent || "";
  autoResize();
  elements.composerInput.focus();
  elements.sendBtn.disabled = false;
  document.body.classList.add("typing");
});

elements.openSidebarBtn.addEventListener("click", openSidebar);
elements.closeSidebarBtn.addEventListener("click", closeSidebar);
elements.sidebarScrim.addEventListener("click", closeSidebar);

elements.themeBtn.addEventListener("click", () => {
  applyTheme(!document.body.classList.contains("dark"));
});

elements.quickThemeBtn.addEventListener("click", () => {
  applyTheme(!document.body.classList.contains("dark"));
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSidebar();
});

applyTheme(false);
autoResize();

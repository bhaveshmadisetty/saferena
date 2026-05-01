import re

filepath = r"d:\chat bot web\main_ipynb_safe_space\index_merged.html"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add messagesHistory at the top of the STATE
state_match = re.search(r'const STATE = \{[\s\S]*?\};', content)
if state_match:
    old_state = state_match.group(0)
    new_state = old_state.replace('msgCount: 0,', 'msgCount: 0,\n  messagesHistory: [],')
    content = content.replace(old_state, new_state)

# 2. Update sendMessage
send_message_block = """async function sendMessage() {
  if (!STATE.inputEnabled || STATE.isLocked) return;
  const text = els.composerInput.value.trim();
  if (!text) return;

  // Clear input
  els.composerInput.value = '';
  autoResizeTextarea();

  // Append user message
  appendMessage('user', `<p>${escapeHTML(text)}</p>`);
  STATE.messagesHistory.push({ role: 'user', content: text });

  STATE.msgCount++;
  updateUsageUI();

  // Check limit
  if (STATE.msgCount >= STATE.MAX_MSGS) {
    disableInput();
    await sleep(200);
    showGate();
    return;
  }

  // Show typing, get AI response
  disableInput();
  showTyping();

  let replyLines = ["I am here with you."];
  try {
      const response = await fetch('/api/chat', { 
        method:'POST', 
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: STATE.messagesHistory, guestId: getGuestId() }) 
      });
      const data = await response.json();
      const reply = data.reply || data.content || "I am here with you.";
      STATE.messagesHistory.push({ role: 'assistant', content: reply });
      replyLines = reply.split('\\n');
  } catch(e) {
      console.error(e);
      replyLines = ["Sorry, I'm having trouble connecting right now."];
  }

  hideTyping();
  appendMessage('ai', msgLinesToHTML(replyLines));

  STATE.msgCount++;
  updateUsageUI();
  enableInput();

  if (STATE.msgCount >= STATE.MAX_MSGS) {
    disableInput();
    await sleep(300);
    showGate();
  }
}"""

# Use regex to replace the existing sendMessage function
content = re.sub(r'async function sendMessage\(\) \{[\s\S]*?\}\s*(?=\/\* ───)', send_message_block + '\n\n', content)

# 3. Modify init() and revealCuratedMessage() to use ob:complete
# revealCuratedMessage currently uses: const ctx = selectCuratedMessage(STATE.onboardingContext);
# We need to change it to take a message argument directly
reveal_curated_old = """async function revealCuratedMessage() {
  const ctx = selectCuratedMessage(STATE.onboardingContext);

  // 1. Show preparing label + typing for 1.4s
  showTyping();"""

reveal_curated_new = """async function revealCuratedMessage(customMessage) {
  // 1. Show preparing label + typing for 1.4s
  showTyping();"""
content = content.replace(reveal_curated_old, reveal_curated_new)

# In revealCuratedMessage, replace `const lines = ctx.message;` with `const lines = customMessage.split('\\n');`
content = content.replace("const lines = ctx.message;", "const lines = customMessage.split('\\n');")

# Remove `renderCheckinTags(ctx.tags);` from init()
content = re.sub(r'const ctx = selectCuratedMessage\(STATE\.onboardingContext\);\s*renderCheckinTags\(ctx\.tags\);', '', content)

# Modify init() to wait for ob:complete
init_old = """async function init() {
  getGuestId();

  // Restore saved note
  try {
    const saved = localStorage.getItem('ss_future_note');
    if (saved) els.noteTextSidebar.value = saved;
  } catch(e) {}

  // Init usage UI at zero
  updateUsageUI();

  // Populate mobile sheet
  populateSheet();

  // Begin curated reveal sequence
  await sleep(200);
  await revealCuratedMessage();
}"""

init_new = """async function init() {
  getGuestId();

  try {
    const saved = localStorage.getItem('ss_future_note');
    if (saved) els.noteTextSidebar.value = saved;
  } catch(e) {}

  updateUsageUI();
  populateSheet();

  window.addEventListener('ob:complete', async (e) => {
    const msg = e.detail?.openingMessage || "I'm here for you.";
    STATE.messagesHistory.push({ role: 'assistant', content: msg });
    
    // Check if we have tags in the payload to render
    if (e.detail?.q1) {
      renderCheckinTags([e.detail.q1]);
    }
    
    await sleep(200);
    await revealCuratedMessage(msg);
  });
}"""

content = content.replace(init_old, init_new)

with open(r"d:\chat bot web\main_ipynb_safe_space\index.html", 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated JS and wrote to index.html successfully.")

import re

filepath = r"d:\chat bot web\main_ipynb_safe_space\index.html"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix init()
# Find the global init() function (not the one inside IIFE)
# It looks like:
# async function init() {
#   getGuestId();
#   ...
#   await sleep(200);
#   await revealCuratedMessage();
# }

init_pattern = re.compile(r"async function init\(\) \{[\s\S]*?await revealCuratedMessage\(\);\s*\}", re.MULTILINE)

new_init = """async function init() {
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
      // Create tags from q1, q2, q3 etc
      const tags = [];
      if (e.detail.q1) tags.push(e.detail.q1);
      if (e.detail.q2) tags.push(e.detail.q2);
      // We don't have renderCheckinTags in chatindex.html actually! Wait, yes we do:
      // renderCheckinTags exists.
      if (typeof renderCheckinTags === 'function') {
        renderCheckinTags(tags);
      }
    }
    
    await sleep(200);
    await revealCuratedMessage(msg);
  });
}"""

# Replace only the first occurrence to avoid the IIFE one
content = init_pattern.sub(new_init, content, count=1)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("init() replaced")

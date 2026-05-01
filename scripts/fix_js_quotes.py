import re

with open(r"d:\chat bot web\main_ipynb_safe_space\index.html", "r", encoding="utf-8") as f:
    html = f.read()

# We only want to replace inside <script> tags
def fix_script(match):
    script_content = match.group(0)
    # List of words with single quotes to fix
    words = [
        "doesn't", "don't", "can't", "won't", "I'm", "I'll", "what's", "that's", "here's", "There's", "You're", "you're", "I've", "you've", "It's", "it's", "Something's"
    ]
    
    # Simple regex to replace these words inside script
    # It's safer to just escape them: "doesn\'t"
    # But wait, if they are already inside double quotes, escaping them is harmless.
    # If they are inside single quotes, escaping them fixes the syntax error.
    for w in words:
        escaped_w = w.replace("'", "\\'")
        # Only replace if not already escaped
        script_content = re.sub(r"(?<!\\)" + re.escape(w), escaped_w, script_content, flags=re.IGNORECASE)
    
    return script_content

# Regex to find script tags
fixed_html = re.sub(r"<script.*?>[\s\S]*?</script>", fix_script, html, flags=re.IGNORECASE)

with open(r"d:\chat bot web\main_ipynb_safe_space\index.html", "w", encoding="utf-8") as f:
    f.write(fixed_html)

print("Fixed syntax errors in JS.")

import re

with open(r"d:\chat bot web\main_ipynb_safe_space\src\css\styles.css", 'r', encoding='utf-8') as f:
    css = f.read()

# We only want the block that starts with `/* ─── ONBOARDING OVERLAY ─── */` or similar
# Let's search for "ob-bg" or "ob-" root variables.
start_idx = css.find('/* ==========================================\n   ONBOARDING OVERLAY')
if start_idx == -1:
    start_idx = css.find('/* ONBOARDING')
    if start_idx == -1:
        # Just grab everything from where --ob-bg is defined
        start_idx = css.find(':root {\n  --ob-bg')

ob_css = ""
if start_idx != -1:
    # Read backwards to the start of the comment block if possible
    comment_start = css.rfind('/*', 0, start_idx+10)
    if comment_start != -1:
        start_idx = comment_start
    ob_css = css[start_idx:]
else:
    print("Could not find onboarding CSS block")

if ob_css:
    # Inject it into index.html
    with open(r"d:\chat bot web\main_ipynb_safe_space\index.html", 'r', encoding='utf-8') as f:
        html = f.read()
    
    html = html.replace('</style>', ob_css + '\n</style>')
    
    with open(r"d:\chat bot web\main_ipynb_safe_space\index.html", 'w', encoding='utf-8') as f:
        html = f.write(html)
    print("Injected ob_css into index.html")

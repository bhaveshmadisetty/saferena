import os
import re

old_index = r"d:\chat bot web\main_ipynb_safe_space\index_backup.html"
new_ui = r"d:\chat bot web\chatindex.html"
target_index = r"d:\chat bot web\main_ipynb_safe_space\index.html"

with open(old_index, 'r', encoding='utf-8') as f:
    old_html = f.read()

with open(new_ui, 'r', encoding='utf-8') as f:
    new_html = f.read()

# 1. Extract the onboarding overlay from the old html
ob_start = old_html.find('<!-- ONBOARDING OVERLAY -->')
ob_end = old_html.find('<!-- /ob-overlay -->') + len('<!-- /ob-overlay -->')
ob_overlay_html = old_html[ob_start:ob_end]

# 2. Extract the onboarding inline script from the old html
script_start_idx = old_html.find('<script>\n(function() {\n  // ─── helpers ───────────────────────────────')
script_end_idx = old_html.find('})(); // end IIFE\n</script>') + len('})(); // end IIFE\n</script>')
ob_script_html = old_html[script_start_idx:script_end_idx]

# Combine both
full_ob_block = ob_overlay_html + "\n\n" + ob_script_html

# 3. Inject into new_html before </body>
new_html_with_ob = new_html.replace('</body>', full_ob_block + '\n</body>')

with open(r"d:\chat bot web\main_ipynb_safe_space\index_merged.html", 'w', encoding='utf-8') as f:
    f.write(new_html_with_ob)

print("Merged OB into index_merged.html successfully.")

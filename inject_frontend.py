import re

with open('D:/healthy_gamer_gg_bot/main_ipynb_safe_space/onboarding-overlay.html', 'r', encoding='utf-8') as f:
    content = f.read()

css_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
if css_match:
    css = css_match.group(1).strip()
    with open('src/css/styles.css', 'a', encoding='utf-8') as f:
        f.write('\n\n/* ONBOARDING OVERLAY STYLES */\n\n' + css + '\n')
    print("Injected CSS into styles.css")

html_match = re.search(r'<div id="ob-overlay">.*?</div><!-- /ob-overlay -->', content, re.DOTALL)
script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)

if html_match and script_match:
    html_block = html_match.group(0)
    script_block = '<script>\n' + script_match.group(1).strip() + '\n</script>'
    
    with open('index.html', 'r', encoding='utf-8') as f:
        idx_content = f.read()
        
    injection = f'\n    <!-- ONBOARDING OVERLAY -->\n    {html_block}\n\n    {script_block}\n\n    <script type="module" src="./src/js/app.js"></script>\n  </body>'
    
    idx_content = idx_content.replace('    <script type="module" src="./src/js/app.js"></script>\n  </body>', injection)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(idx_content)
    print("Injected HTML/JS into index.html")
else:
    print("Failed to find HTML or Script block")

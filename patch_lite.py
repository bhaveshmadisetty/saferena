import re

with open('api/rag_pipeline_lite.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add guest_id to signature
content = content.replace(
'''def generate_assistant_reply(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
    memory_context: str = "",  # Supabase persistent memory (optional add-on)
) -> str:''',
'''def generate_assistant_reply(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
    memory_context: str = "",  # Supabase persistent memory (optional add-on)
    guest_id: str = "",        # User context mapping
) -> str:''')

# Replace the prompt assignment
match = re.search(r'    prompt = f"""\nYou are talking to a real person in a real conversation.*?REPEAT COUNT: \{repeat_count\}', content, re.DOTALL)
if match:
    new_prompt = '''    from api.user_context import build_system_prompt_v2
    base_prompt = build_system_prompt_v2(guest_id)

    prompt = f"""{base_prompt}

---
REPEAT COUNT: {repeat_count}'''
    content = content[:match.start()] + new_prompt + content[match.end():]
    
    with open('api/rag_pipeline_lite.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully patched rag_pipeline_lite.py')
else:
    print('Failed to find prompt block')

import os
from openai import OpenAI

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

models_to_test = [
    "google/gemma-7b-it:free",
    "mistralai/mistral-7b-instruct",
    "openrouter/auto-free",
    "huggingfaceh4/zephyr-7b-beta:free",
    "gryphe/mythomist-7b:free",
    "qwen/qwen-2-7b-instruct:free",
    "google/gemma-2-9b-it:free"
]

for model in models_to_test:
    print(f"Testing {model}...")
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            timeout=5
        )
        print(f"  SUCCESS: {res.choices[0].message.content}")
    except Exception as e:
        print(f"  FAILED: {e}")

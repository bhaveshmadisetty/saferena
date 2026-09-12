import os
from openai import OpenAI

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

models_to_test = [
    "openrouter/free",
    "google/gemma-7b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free"
]

for model in models_to_test:
    print(f"Testing {model}...")
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            timeout=10
        )
        print(f"  SUCCESS: {res.choices[0].message.content}")
    except Exception as e:
        print(f"  FAILED: {e}")

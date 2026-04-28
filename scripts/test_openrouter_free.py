import os
from openai import OpenAI

API_KEY = "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"
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

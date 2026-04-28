import os
from openai import OpenAI
import sys

API_KEY = "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"
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

try:
    print("Testing qwen/qwen-2.5-coder-32b-instruct...")
    response = client.chat.completions.create(
        model="qwen/qwen-2.5-coder-32b-instruct",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    print("Error:", repr(e))

print("\n----------------\n")
try:
    print("Testing qwen3-coder...")
    response = client.chat.completions.create(
        model="qwen3-coder",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    print("Error:", repr(e))

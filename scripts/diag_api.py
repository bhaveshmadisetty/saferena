import os
import sys
from openai import OpenAI

# Using the EXACT key from rag_pipeline.py
API_KEY = "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"
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def test_api(model_name):
    print(f"Testing model: {model_name}...")
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Say 'ready'"}],
            max_tokens=200,
            timeout=10
        )
        print(f"  SUCCESS: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    print("Beginning OpenRouter diagnostics...\n")
    test_api("qwen3-coder")
    test_api("mistralai/mistral-7b-instruct")
    test_api("meta-llama/llama-3.1-8b-instruct")

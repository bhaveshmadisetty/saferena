import os
from openai import OpenAI
import sys

# Using the EXACT key and logic from rag_pipeline.py
API_KEY = "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"
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

def test_model(model_name):
    print(f"\n--- Testing model: {model_name} ---")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=20
        )
        print(f"SUCCESS: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"FAILED: {repr(e)}")
        return False

# Test the models used in the pipeline
models_to_test = [
    "qwen/qwen-2.5-coder-32b-instruct", # The one I put in rag_pipeline.py
    "google/gemma-2-9b-it:free",       # Used for summary
    "qwen3-coder"                      # The one from the original notebook
]

for model in models_to_test:
    test_model(model)

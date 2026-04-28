import os
import sys

# Add api folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from rag_pipeline import generate_assistant_reply

def test_pipeline():
    print("Testing RAG Pipeline with qwen3-coder...")
    try:
        messages = [{"role": "user", "content": "I am feeling a bit stressed today."}]
        reply = generate_assistant_reply(messages, session_id="test_session")
        print(f"Pipeline Reply: {reply}")
        if reply and len(reply) > 10:
            print("SUCCESS: Pipeline returned a valid response.")
        else:
            print("FAILED: Pipeline returned a short or empty response.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_pipeline()

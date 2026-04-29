import json
import os
import faiss
import numpy as np
from typing import Any
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# ---------------------------------------------------------------------
# GLOBAL INITIALIZATION (Runs once when the module loads)
# ---------------------------------------------------------------------
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dataset3.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "api_error.log")

print("Loading dataset...")
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

texts = []
metadata = []

# Process the dataset to extract stream, analysis, and questions
for item in dataset:
    # 1. STREAM (empathy)
    for stream_item in item.get("drk_stream", []):
        texts.append(stream_item)
        metadata.append({
            "type": "stream",
            "topic": item["topic"],
            "emotions": item.get("emotions", []),
            "intent": "empathy"
        })

    # 2. ANALYSIS (reasoning)
    for key, analysis in item.get("drk_analysis_modes", {}).items():
        texts.append(analysis)
        metadata.append({
            "type": "analysis",
            "topic": item["topic"],
            "mode": key,
            "intent": "reasoning"
        })

    # 3. QUESTIONS (exploration)
    for q in item.get("deep_questions", []):
        texts.append(q)
        metadata.append({
            "type": "question",
            "topic": item["topic"],
            "intent": "exploration"
        })

print("Loading SentenceTransformer model (BAAI/bge-small-en-v1.5)...")
model = SentenceTransformer('BAAI/bge-small-en-v1.5')

print("Encoding vectors and initializing FAISS index...")
embeddings = model.encode(texts, convert_to_numpy=True)
faiss.normalize_L2(embeddings)
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)
print(f"Index ready with {index.ntotal} vectors.")

# ---------------------------------------------------------------------
# INITIALIZE LLM CLIENT
# ---------------------------------------------------------------------
API_KEY = "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"
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# In-memory dictionary to track per-session summaries
session_summaries = {}

# ---------------------------------------------------------------------
# PIPELINE FUNCTIONS
# ---------------------------------------------------------------------

def retrieve(query: str, k: int = 5, threshold: float = 0.65) -> list[dict]:
    query_embedding = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)

    distances, indices = index.search(query_embedding, k)
    results = []

    for i, idx in enumerate(indices[0]):
        score = distances[0][i]
        if idx != -1 and score > threshold:
            results.append({
                "text": texts[idx],
                "meta": metadata[idx],
                "score": float(score)
            })

    return results

def build_context(results: list[dict]) -> str:
    stream = None
    analysis = None
    question = None

    for r in results:
        if r["meta"]["type"] == "stream" and not stream:
            stream = r["text"]
        elif r["meta"]["type"] == "analysis" and not analysis:
            analysis = r["text"]
        elif r["meta"]["type"] == "question" and not question:
            question = r["text"]

    if not analysis and stream:
        analysis = stream

    context = ""
    if stream:
        context += f"{stream}\n\n"
    if analysis and analysis != stream:
        context += f"{analysis}\n\n"
    if question:
        context += f"Example reflective question:\n{question}"

    return context.strip()

def update_summary(chat_history: list[dict], previous_summary: str = "") -> str:
    history_text = ""
    for turn in chat_history[-6:]:
        history_text += f"User: {turn['user']}\n"

    prompt = f"""
Summarize the user's emotional state and situation.

Rules:
- Keep it very short (1–2 lines max)
- Focus only on important emotional patterns (e.g., sadness, confusion, attachment)
- Do NOT repeat the full conversation
- Do NOT add new information
- Just update what has already been observed

Previous summary:
{previous_summary}

New conversation:
{history_text}

Updated summary:
"""
    try:
        response = client.chat.completions.create(
            # Using the user's preferred model
            model="qwen3-coder",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error updating summary: {e}")
        print(f"Summary Error: {str(e)}")
        return previous_summary

def generate_assistant_reply(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
    memory_context: str = "",  # Supabase persistent memory (optional add-on)
    guest_id: str = "",        # User context mapping
) -> str:
    if not messages:
        return "I am here with you."

    chat_history = []
    current_user = None
    
    for m in messages:
        if m.get("role") == "user":
            current_user = m.get("content")
        elif m.get("role") == "assistant" and current_user is not None:
            chat_history.append({"user": current_user, "assistant": m.get("content")})
            current_user = None

    last_user_query = ""
    if messages[-1].get("role") == "user":
        last_user_query = messages[-1].get("content")
    else:
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_query = m.get("content")
                break

    sid = session_id or "default"
    prev_summary = session_summaries.get(sid, "")

    results = retrieve(last_user_query, k=5)
    context = build_context(results)

    # Count recent repetitions
    last_user_messages_only = [t["user"] for t in chat_history[-5:]]
    repeat_count = last_user_messages_only.count(last_user_query)

    # Build history text block
    history_text = ""
    for turn in chat_history[-3:]:
        history_text += f"[MEMORY]\nUSER: {turn['user']}\nASSISTANT: {turn['assistant']}\n\n"

    from api.user_context import build_system_prompt_v2
    base_prompt = build_system_prompt_v2(guest_id)

    prompt = f"""{base_prompt}

---
REPEAT COUNT: {repeat_count}

USER STATE (IMPORTANT):
{prev_summary}

---

RECENT CHAT:
{history_text}

---

PERSISTENT MEMORY (from previous sessions, use naturally if relevant):
{memory_context}

---

CONTEXT (use only if helpful):
{context}

---

USER:
{last_user_query}

---

REPLY:
"""

    try:
        response = client.chat.completions.create(
            # Using qwen3-coder as confirmed by the user
            model="qwen3-coder",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=500
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)
        
        # Surface the actual error to the user if it's a known issue
        if "402" in str(e):
            reply = "I'm sorry, I'm hitting a credit limit on the current AI model. We might need to try a different free model or check the API key settings."
        elif "401" in str(e):
            reply = "There seems to be an issue with the API key authentication. Please double check your OpenRouter key."
        else:
            reply = "I'm having a bit of trouble with my connection to the AI right now. (Ref: " + str(e)[:50] + "...)"

    # Process and save the summary
    chat_history.append({"user": last_user_query, "assistant": reply})
    new_summary = update_summary(chat_history, prev_summary)
    session_summaries[sid] = new_summary

    return reply

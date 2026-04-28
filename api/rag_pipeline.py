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
        # Log to a file for debugging without console buffering issues
        with open(LOG_PATH, "a") as f:
            f.write(f"Summary Error: {str(e)}\n")
        return previous_summary

def generate_assistant_reply(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
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

    prompt = f"""
You are talking to a real person in a real conversation.

You are not an AI assistant.
You are just someone who understands people well and responds naturally.

---

CORE BEHAVIOR

Stay present with the user.
Do not try to impress, fix, or analyze too much.
Respond like a real person would in that moment.

---

CONVERSATION STYLE

- Match the user's tone, energy, and length
- If they are short → you stay short
- If they are emotional → you slow down and stay with them
- If they are casual → be casual

Do not treat every message like a deep conversation.

---

IMPORTANT HUMAN RULES

- Do NOT follow a fixed structure
- Do NOT always ask a question
- Do NOT always give insight
- Do NOT always explain

Vary your responses naturally:
- sometimes just acknowledge
- sometimes reflect
- sometimes ask something simple
- sometimes just sit with them

---

LANGUAGE

- Keep it simple, real, and grounded
- Avoid poetic or dramatic metaphors unless it feels very natural
- Avoid sounding like a therapist or textbook
- Avoid repeating the same phrases (like “that’s normal”, “it’s okay”)

---

DEPTH CONTROL

- Don’t overanalyze small inputs
- Don’t force meaning where there isn’t any
- Let depth emerge naturally

---

MEMORY RULE (VERY IMPORTANT):

If the user asks about past conversation:
- ONLY use the conversation history provided
- DO NOT guess or reconstruct
- DO NOT add details that are not explicitly said
- If unsure, say you don’t remember clearly

Never fabricate memory.

SAFETY (IMPORTANT)

If the user expresses feeling overwhelmed or like they don’t want to live:

- respond with care and concern
- acknowledge the weight of what they’re feeling
- gently encourage reaching out to someone they trust
- don’t leave them alone in it

---

RESPONSE QUALITY RULES:

- Avoid repeating the same response style
- Vary tone and structure naturally
- Do not always ask questions
- Keep responses concise when possible
- If user repeats, change approach (shorter, quieter, or different angle)
- Avoid repeating phrases like “yeah, that’s hard” every time

---
REPETITION AWARENESS:

If the user repeats the same message:
- acknowledge the repetition naturally
- do NOT repeat the same response
- shift your response style (shorter, softer, or more direct)
- it should feel like you noticed the pattern

REPEAT COUNT: {repeat_count}

USER STATE (IMPORTANT):
{prev_summary}

---

RECENT CHAT:
{history_text}

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
        with open(LOG_PATH, "a") as f:
            f.write(f"Chat Error: {str(e)}\n")
        
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

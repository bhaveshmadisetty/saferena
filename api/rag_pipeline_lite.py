"""
Lightweight RAG pipeline for Vercel deployment.

Uses scikit-learn TF-IDF instead of sentence-transformers + FAISS.
This avoids the heavy torch dependency that exceeds Vercel's memory limits.

The heavy pipeline (rag_pipeline.py) is kept intact for local development.
"""

import json
import os
import math
import re
from typing import Any
from openai import OpenAI

# ---------------------------------------------------------------------
# GLOBAL INITIALIZATION (Runs once when the module loads)
# ---------------------------------------------------------------------
DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dataset3.json")

print("[lite] Loading dataset...")
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

# Also index user_signals and tags for better keyword matching
topic_keywords = {}
for item in dataset:
    topic = item["topic"]
    signals = item.get("user_signals", [])
    tags = item.get("tags", [])
    emotions = item.get("emotions", [])
    topic_keywords[topic] = " ".join(signals + tags + emotions).lower()

# ---------------------------------------------------------------------
# LIGHTWEIGHT TF-IDF RETRIEVAL (pure Python, no torch/sklearn needed)
# ---------------------------------------------------------------------

def _tokenize(text):
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"[a-z']+", text.lower())

# Build vocabulary and document frequency
_all_docs = texts + list(topic_keywords.values())
_vocab_df = {}
_doc_count = len(_all_docs)

for doc in _all_docs:
    seen = set()
    for token in _tokenize(doc):
        if token not in seen:
            _vocab_df[token] = _vocab_df.get(token, 0) + 1
            seen.add(token)

def _tfidf_vec(text):
    """Compute a simple TF-IDF vector for text."""
    tokens = _tokenize(text)
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    total = len(tokens) or 1
    vec = {}
    for t, count in tf.items():
        idf = math.log((_doc_count + 1) / (_vocab_df.get(t, 0) + 1)) + 1
        vec[t] = (count / total) * idf
    return vec

def _cosine_sim(v1, v2):
    """Cosine similarity between two sparse vectors (dicts)."""
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

# Pre-compute TF-IDF vectors for all texts
_text_vectors = [_tfidf_vec(t) for t in texts]

print(f"[lite] Index ready with {len(texts)} entries (TF-IDF).")

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

def retrieve(query: str, k: int = 5, threshold: float = 0.05) -> list[dict]:
    """Retrieve top-k matching texts using TF-IDF cosine similarity."""
    query_vec = _tfidf_vec(query)
    scored = []
    for i, tv in enumerate(_text_vectors):
        score = _cosine_sim(query_vec, tv)
        if score > threshold:
            scored.append((score, i))

    # Also check topic keyword matches for better recall
    for topic, kw_text in topic_keywords.items():
        kw_vec = _tfidf_vec(kw_text)
        kw_score = _cosine_sim(query_vec, kw_vec)
        if kw_score > threshold:
            # Boost all entries from this topic
            for i, m in enumerate(metadata):
                if m["topic"] == topic and not any(s[1] == i for s in scored):
                    scored.append((kw_score * 0.8, i))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, idx in scored[:k]:
        results.append({
            "text": texts[idx],
            "meta": metadata[idx],
            "score": score
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
        print(f"[lite] Error updating summary: {e}")
        return previous_summary

def generate_assistant_reply(
    messages: list[dict[str, Any]],
    session_id: str | None = None,
    memory_context: str = "",  # Supabase persistent memory (optional add-on)
    guest_id: str = "",        # User context mapping
    personal_api_key: str = "",
    checkin_context: str = "",
) -> dict[str, str]:
    if not messages:
        return {"reply": "I am here with you.", "summary": ""}

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

    checkin_block = checkin_context.strip() if isinstance(checkin_context, str) else ""

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

USER-EDITABLE CHECK-IN CONTEXT (use as current self-described context; prioritize when relevant):
{checkin_block}

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
        # Override client if personal API key is provided
        active_client = client
        if personal_api_key:
            active_client = OpenAI(
                api_key=personal_api_key,
                base_url="https://openrouter.ai/api/v1"
            )
        
        response = active_client.chat.completions.create(
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

    return {"reply": reply, "summary": new_summary}

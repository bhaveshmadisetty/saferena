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
# INITIALIZE LLM CLIENT (values from prompt_config)
# ---------------------------------------------------------------------
try:
    from .prompt_config import API_KEY, BASE_URL, CHAT_MODEL, SUMMARY_MODEL
    from .prompt_config import CHAT_TEMPERATURE, SUMMARY_TEMPERATURE
    from .prompt_config import CHAT_MAX_TOKENS, SUMMARY_MAX_TOKENS
    from .prompt_config import SUMMARY_PROMPT_TEMPLATE, CHAT_PROMPT_TEMPLATE
except (ImportError, SystemError, ValueError):
    from prompt_config import API_KEY, BASE_URL, CHAT_MODEL, SUMMARY_MODEL
    from prompt_config import CHAT_TEMPERATURE, SUMMARY_TEMPERATURE
    from prompt_config import CHAT_MAX_TOKENS, SUMMARY_MAX_TOKENS
    from prompt_config import SUMMARY_PROMPT_TEMPLATE, CHAT_PROMPT_TEMPLATE

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# In-memory dictionary to track per-session summaries
session_summaries = {}

def sanitize_reply(reply: str) -> str:
    """Strip meta-notes, stage directions, and parenthetical leaks from the AI reply."""
    import re
    # Remove parenthetical meta-notes: (Note: ...), (note: ...), etc.
    reply = re.sub(r'\(\s*[Nn]ote[^)]*\)', '', reply)
    # Remove bracketed meta-notes: [Note: ...], [note: ...]
    reply = re.sub(r'\[\s*[Nn]ote[^]]*\]', '', reply)
    # Remove trailing meta-lines that start with Note: or similar
    reply = re.sub(r'\s*[Nn]ote:\s*.*', '', reply)
    # Remove any double spaces left behind
    reply = re.sub(r'\s{2,}', ' ', reply).strip()
    return reply

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

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        prev_summary=previous_summary,
        history_text=history_text
    )
    try:
        response = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=SUMMARY_TEMPERATURE,
            max_tokens=SUMMARY_MAX_TOKENS
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
    crisis_level: str = "none",  # Deterministic safety signal from api/crisis.py
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

    # Extract last 3 bot replies for variety enforcement
    last_3_assistant = [turn["assistant"] for turn in chat_history[-3:] if "assistant" in turn]
    last_3_replies = "\n".join(last_3_assistant) if last_3_assistant else "None yet."

    # Same import fallback as prompt_config above: the serverless handlers put
    # api/ itself on sys.path and there is no api/__init__.py, so "api.user_context"
    # raises ModuleNotFoundError there.
    try:
        from .user_context import build_system_prompt_v2
    except ImportError:
        from user_context import build_system_prompt_v2
    base_prompt = build_system_prompt_v2(guest_id)

    # Append the deterministic safety annotation so the model adapts its tone.
    # "high" is already intercepted in api/chat.py and never reaches here.
    if crisis_level and crisis_level != "none":
        try:
            try:
                from .crisis import prompt_annotation
            except ImportError:
                from crisis import prompt_annotation
            base_prompt += prompt_annotation(crisis_level)
        except Exception as e:
            print(f"[lite] crisis annotation unavailable: {e}")

    checkin_block = checkin_context.strip() if isinstance(checkin_context, str) else ""

    prompt = CHAT_PROMPT_TEMPLATE.format(
        system_prompt=base_prompt,
        repeat_count=repeat_count,
        prev_summary=prev_summary,
        history_text=history_text,
        memory_context=memory_context,
        checkin_block=checkin_block,
        context=context,
        last_user_query=last_user_query,
        last_3_replies=last_3_replies
    )

    try:
        # Override client if personal API key is provided
        active_client = client
        if personal_api_key:
            active_client = OpenAI(
                api_key=personal_api_key,
                base_url="https://openrouter.ai/api/v1"
            )

        response = active_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=CHAT_TEMPERATURE,
            max_tokens=CHAT_MAX_TOKENS
        )
        reply = sanitize_reply(response.choices[0].message.content.strip())
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(error_msg)

        # Surface the actual error to the user if it's a known issue
        # Keep user-facing copy human. Only mention the key when the user
        # supplied one; otherwise don't expose provider internals in chat.
        if "401" in str(e) and personal_api_key:
            reply = "That API key didn't authenticate. Could you double-check it? You can also remove it and continue on the shared limit."
        else:
            reply = "I'm having trouble reaching my words right now — that's on my end, not yours. Could you give it another moment and try again?"
        reply = sanitize_reply(reply)

        # Safety net: if the model failed on a distressing message, make sure
        # helplines still reach the user rather than a bare error.
        if crisis_level and crisis_level != "none":
            try:
                try:
                    from .crisis import HELPLINE_BLOCK
                except ImportError:
                    from crisis import HELPLINE_BLOCK
                reply += "\n\nAnd while I sort myself out — if things feel heavy right now, please reach out:\n\n" + HELPLINE_BLOCK
            except Exception:
                pass


    # Process and save the summary
    chat_history.append({"user": last_user_query, "assistant": reply})
    new_summary = update_summary(chat_history, prev_summary)
    session_summaries[sid] = new_summary

    return {"reply": reply, "summary": new_summary}


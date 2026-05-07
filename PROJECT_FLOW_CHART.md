# Safe Space AI Chatbot - Project Flow Chart for AI/ML Students

## Project Overview

This is a **mental health support chatbot** inspired by Dr. K (Healthy Gamer GG) that uses **RAG (Retrieval-Augmented Generation)** architecture. It demonstrates key AI/ML concepts including vector embeddings, similarity search, LLM integration, and prompt engineering.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND LAYER                                 │
│  (chatindex.html / index.html + app.js + chatStore.js)                   │
│                                                                         │
│  User Input → Display Messages → Session Management (sessionId/guestId)  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ POST /api/chat
                                 │ {sessionId, messages, guestId, personal_api_key}
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND SERVER                                    │
│  ┌──────────────┐                    ┌──────────────┐                    │
│  │ Flask Server │                    │ Vercel       │                    │
│  │ server.py    │        OR          │ api/main.py   │                    │
│  │ (Local Dev)  │                    │ (Production)  │                    │
│  └──────┬───────┘                    └──────┬───────┘                    │
│         │                                   │                             │
│         └───────────────────┬───────────────┘                             │
│                             │                                             │
│                             ▼                                             │
│              ┌──────────────────────────────┐                             │
│              │   Rate Limit & Session Mgmt  │                             │
│              │   - Check message count (15)  │                             │
│              │   - Lock after limit (24 hours)│                             │
│              └──────────────┬───────────────┘                             │
└─────────────────────────────┼─────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RAG PIPELINE LAYER                                    │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    api/rag_pipeline.py                         │       │
│  │  (Heavy: SentenceTransformers + FAISS) OR                    │       │
│  │  api/rag_pipeline_lite.py                                     │       │
│  │  (Lightweight: TF-IDF + Cosine Similarity)                    │       │
│  └───────────────────────────┬───────────────────────────────────┘       │
│                              │                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    STEP 1: RETRIEVAL                           │     │
│  │  Input: User Query (last_user_query)                          │     │
│  │                                                               │     │
│  │  ┌─────────────────┐      ┌─────────────────┐                │     │
│  │  │ VECTOR SEARCH   │      │  TF-IDF SEARCH  │                │     │
│  │  │ (Heavy Version) │  OR  │ (Lite Version) │                │     │
│  │  └────────┬────────┘      └────────┬────────┘                │     │
│  │           │                        │                           │     │
│  │           ▼                        ▼                           │     │
│  │  ┌──────────────────────────────────────────┐                │     │
│  │  │     Data: data/dataset3.json             │                │     │
│  │  │     - drk_stream (empathy responses)     │                │     │
│  │  │     - drk_analysis_modes (reasoning)     │                │     │
│  │  │     - deep_questions (exploration)       │                │     │
│  │  └──────────────────────────────────────────┘                │     │
│  │                                                               │     │
│  │  Output: Top-K relevant texts (with scores > threshold)        │     │
│  └───────────────────────────┬───────────────────────────────────┘     │
│                              │                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    STEP 2: CONTEXT BUILDING                     │     │
│  │  Input: Retrieved results (stream, analysis, question)          │     │
│  │                                                               │     │
│  │  Output: Formatted context string                              │     │
│  └───────────────────────────┬───────────────────────────────────┘     │
│                              │                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    STEP 3: PROMPT ASSEMBLY                     │     │
│  │  Components:                                                    │     │
│  │  1. System Prompt (from prompt_config.py)                       │     │
│  │     - Base rules (1-2 sentences, no therapist claim)           │     │
│  │     - Path-specific style (deep vs general)                     │     │
│  │     - Situation guidelines (breakup, anxiety, etc.)             │     │
│  │     - Mood/tone directives                                      │     │
│  │     - Session progress directives (9, 11, 15 msg thresholds)    │     │
│  │                                                               │     │
│  │  2. User Context (from Supabase user_context)                  │     │
│  │     - Onboarding answers (q1-q5)                              │     │
│  │     - Name, path, support needs                                │     │
│  │                                                               │     │
│  │  3. Persistent Memory (from Supabase chat_messages)            │     │
│  │     - Last 10 messages from previous sessions                  │     │
│  │                                                               │     │
│  │  4. Chat History (current session, last 3 turns)              │     │
│  │                                                               │     │
│  │  5. Retrieved Context (from RAG pipeline)                     │     │
│  │                                                               │     │
│  │  6. Last User Query                                           │     │
│  │                                                               │     │
│  │  Template: CHAT_PROMPT_TEMPLATE                               │     │
│  └───────────────────────────┬───────────────────────────────────┘     │
│                              │                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    STEP 4: LLM INFERENCE                       │     │
│  │                                                               │     │
│  │  Model: DeepSeek (via OpenRouter API)                         │     │
│  │  Client: OpenAI SDK (base_url = openrouter.ai/api/v1)         │     │
│  │                                                               │     │
│  │  Parameters:                                                   │     │
│  │    - temperature: 0.7 (chat), 0.3 (summary)                  │     │
│  │    - max_tokens: 110 (chat), 100 (summary)                   │     │
│  │                                                               │     │
│  │  Output: Assistant Reply (1-2 sentences)                      │     │
│  └───────────────────────────┬───────────────────────────────────┘     │
│                              │                                           │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                    STEP 5: SUMMARIZATION                       │     │
│  │  Update session summary using LLM                              │     │
│  │  Input: Last 6 chat turns + previous summary                  │     │
│  │  Output: Updated 1-2 line summary                            │     │
│  │  Stored in: session_summaries (in-memory dict)                │     │
│  └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────┼─────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                        │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ Supabase          │    │ Supabase          │    │ Dataset          │  │
│  │ user_context      │    │ chat_messages     │    │ dataset3.json    │  │
│  │ (onboarding data) │    │ (chat history)    │    │ (knowledge base) │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Flow: What Happens When User Sends a Message

### 1. Frontend Sends Request
```javascript
// Frontend (app.js) sends:
{
  "sessionId": "uuid-string",
  "guestId": "guest_12345",
  "messages": [
    {"id": "1", "role": "user", "content": "I feel anxious about my breakup"}
  ],
  "personal_api_key": ""  // or user's OpenRouter key
}
```

### 2. Backend Receives Request (`server.py` → `/api/chat`)

**Step 2a: Memory Context (Supabase)**
- Extract last user message
- Save user message to `chat_messages` table
- Load last 10 messages from Supabase → format as `memory_context`

**Step 2b: Rate Limiting**
- Get user context from `user_context` table
- Check `session_msg_count` (max 15 messages)
- If >= 15: Return lock message, set `unlock_at` (24 hours later)
- If < 15: Continue

### 3. RAG Pipeline (`api/rag_pipeline.py`)

**Step 3a: Vectorize Query**
```python
# Heavy version (local dev):
query_embedding = model.encode([query])  # BAAI/bge-small-en-v1.5
faiss.normalize_L2(query_embedding)

# Lite version (Vercel):
query_vec = _tfidf_vec(query)  # TF-IDF weights
```

**Step 3b: Similarity Search**
```python
# Heavy: FAISS IndexFlatIP (inner product / cosine similarity)
distances, indices = index.search(query_embedding, k=5)

# Lite: Cosine similarity between sparse TF-IDF vectors
score = _cosine_sim(query_vec, doc_vec)
```

**Step 3c: Filter by Threshold**
- Heavy: threshold = 0.65
- Lite: threshold = 0.05

**Step 3d: Build Context**
```python
context = f"{stream_response}\n\n{analysis}\n\n{question}"
```

### 4. Prompt Assembly (`api/prompt_config.py`)

The final prompt sent to LLM:
```
{system_prompt}  ← Assembled from user's onboarding + path + situation

---

REPEAT COUNT: {repeat_count}  ← Prevent repetitive replies

USER STATE:
{prev_summary}  ← From session_summaries dict

---

RECENT CHAT:
{history_text}  ← Last 3 turns of current session

---

PERSISTENT MEMORY:
{memory_context}  ← From Supabase (previous sessions)

---

USER-EDITABLE CHECK-IN:
{checkin_block}  ← User's current self-description

---

CONTEXT:
{context}  ← From RAG retrieval

---

USER:
{last_user_query}

---

LAST 3 BOT REPLIES:
{last_3_replies}  ← Ensure variety

---

REPLY (1-2 sentences only):
```

### 5. LLM Generation

```python
response = client.chat.completions.create(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7,
    max_tokens=110
)
reply = response.choices[0].message.content
```

### 6. Post-Processing

**Step 6a: Save to Memory**
- Save assistant reply to Supabase `chat_messages`
- Increment `session_msg_count` in `user_context`

**Step 6b: Update Summary**
```python
new_summary = update_summary(chat_history, prev_summary)
session_summaries[session_id] = new_summary
```

**Step 6c: Return to Frontend**
```json
{
  "reply": "That kind of anxiety after a breakup can feel overwhelming. What's the heaviest part for you right now?"
}
```

---

## AI/ML Concepts Demonstrated

### 1. **RAG (Retrieval-Augmented Generation)**
- **What**: Combining retrieval of relevant documents with LLM generation
- **Why**: Reduces hallucinations, provides domain-specific knowledge
- **Implementation**: Query → Embed → Search → Retrieve → Inject into prompt → Generate

### 2. **Vector Embeddings**
- **Model**: `BAAI/bge-small-en-v1.5` (1024 dimensions)
- **Concept**: Map text to dense vectors in semantic space
- **Similarity**: Cosine similarity / Inner Product (FAISS IndexFlatIP)

### 3. **TF-IDF (Lite Version)**
- **TF (Term Frequency)**: How often a word appears in a document
- **IDF (Inverse Document Frequency)**: How rare the word is across all documents
- **Cosine Similarity**: Angle between vectors (ignores magnitude)

### 4. **Vector Database (FAISS)**
- **What**: Facebook AI Similarity Search
- **Index**: `IndexFlatIP` (exhaustive search, good for small datasets)
- **Normalization**: L2 normalization makes inner product = cosine similarity

### 5. **Prompt Engineering**
- **System Prompt**: Sets behavior, rules, constraints
- **Few-shot Learning**: Examples of desired output style
- **Context Injection**: Dynamic insertion of retrieved content
- **Temperature**: Controls randomness (0.3 = focused, 0.7 = creative)

### 6. **Session State Management**
- **Summary**: LLM-generated compression of conversation
- **Purpose**: Maintain context across long conversations without exceeding token limits
- **Approach**: Rolling window (last 6 turns) + previous summary

### 7. **Personalization**
- **Onboarding**: Collect user preferences (path, situation, mood, support type)
- **Dynamic Prompts**: Assemble system prompt based on user profile
- **Result**: Different conversation styles for different users

---

## Dataset Structure (`data/dataset3.json`)

```json
[
  {
    "topic": "breakup_decision_phase",
    "tags": ["considering breakup", "doubt", "fear of loneliness"],
    "emotions": ["uncertainty", "fear", "guilt"],
    "user_signals": ["Should I leave?", "I don't love them anymore"],
    
    "drk_stream": [
      "I actually believe you here…",
      "and it's like your mind is stuck between what you know and what feels safe…"
    ],  // Empathetic responses (emotion-first)
    
    "drk_analysis_modes": {
      "neuro": "Your brain is wired to avoid uncertainty...",
      "psych": "This often comes from a need for emotional safety...",
      "philosophy": "Sometimes the suffering isn't just the situation..."
    },  // Reasoning from different perspectives
    
    "deep_questions": [
      "When you think about leaving, is it the loneliness that scares you?",
      "Do you feel stuck because you still love them?"
    ]  // Open-ended exploration prompts
  }
]
```

**RAG Retrieval Strategy**: For each query, retrieve ONE item from each category (stream, analysis, question) to provide a balanced response.

---

## Two RAG Implementations Compared

| Feature | Heavy (`rag_pipeline.py`) | Lite (`rag_pipeline_lite.py`) |
|---------|---------------------------|--------------------------------|
| Embedding Model | SentenceTransformers (BAAI/bge-small-en-v1.5) | Custom TF-IDF |
| Vector DB | FAISS (IndexFlatIP) | Pure Python dicts |
| Dependencies | torch, sentence-transformers, faiss | None (stdlib only) |
| Memory | ~500MB+ (model weights) | ~1MB (vocabulary) |
| Speed | Slower (model inference) | Faster (simple math) |
| Accuracy | Higher (semantic understanding) | Lower (keyword-based) |
| Use Case | Local development | Vercel serverless (512MB limit) |

---

## Key Files for Students to Study

| File | What to Learn |
|------|----------------|
| `api/rag_pipeline.py` | Vector embeddings, FAISS, similarity search |
| `api/rag_pipeline_lite.py` | TF-IDF, cosine similarity, lightweight ML |
| `api/prompt_config.py` | Prompt engineering, system prompts, personalization |
| `api/chat.py` | API design, JSON handling, error handling |
| `server.py` | Flask server, CORS, rate limiting, memory integration |
| `api/user_context.py` | Database operations, user state management |
| `api/supabase_memory.py` | Persistent storage, chat history retrieval |
| `data/dataset3.json` | Knowledge base structure, RAG data prep |

---

## Token Flow (Context Window Management)

```
Max Context: ~4096 tokens (DeepSeek)
├── System Prompt: ~500-600 tokens
├── Previous Summary: ~20 tokens
├── Recent Chat (3 turns): ~150 tokens
├── Persistent Memory (10 msgs): ~500 tokens
├── Retrieved Context (RAG): ~150 tokens
├── Last 3 Bot Replies: ~50 tokens
└── User Query: ~20 tokens
Total: ~1400 tokens (leaves room for generation)
```

---

## Safety & Ethics in AI Design

1. **Not a Therapist**: Clear disclaimer in system prompt
2. **Crisis Resources**: Automatic mention of iCall (9152987821) and Vandrevala Foundation
3. **Session Limits**: 15 messages max → encourages real-world help-seeking
4. **Rate Limiting**: 3-day cooldown prevents dependency
5. **Toxic Positivity Ban**: No "you'll be fine" responses
6. **Privacy**: Service role key server-side only, guest IDs (no PII)

---

## Deployment Architecture

```
Local Development:
  User → localhost:8080 → Flask (server.py) → RAG Pipeline (Heavy) → OpenRouter → DeepSeek

Production (Vercel):
  User → https://app.vercel.app → Serverless Function (api/main.py) → RAG Pipeline (Lite) → OpenRouter → DeepSeek
```

---

## Learning Exercises for Students

1. **Understand RAG**: Remove the retrieval step, observe how responses change
2. **Embedding Visualization**: Use t-SNE to plot dataset3.json vectors in 2D
3. **Prompt A/B Testing**: Change temperature from 0.3 to 0.9, compare outputs
4. **TF-IDF vs Embeddings**: Compare retrieval quality between lite and heavy versions
5. **Add New Topic**: Add a new topic to dataset3.json, test if bot can discuss it
6. **Session Summary**: Print the summary after each turn, observe how it evolves
7. **Token Counting**: Add token counting to each prompt section, optimize for cost

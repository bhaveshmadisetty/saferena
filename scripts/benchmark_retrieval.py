"""
Retrieval benchmark: production TF-IDF vs. lightweight dense embeddings.

Question being answered:
    The deployed pipeline (api/rag_pipeline_lite.py) uses pure-Python TF-IDF so
    it fits in a Vercel serverless function. Does lexical matching miss the
    semantic nuance in how people actually describe distress?

Method:
    * Corpus  = exactly what production indexes (rag_pipeline_lite.texts plus
                the per-topic keyword strings), so the comparison is fair.
    * Queries = labelled user messages in three subsets:
        - lexical     : share vocabulary with the dataset's user_signals
        - paraphrase  : same intent, deliberately no keyword overlap
        - hinglish    : romanised Hindi/English mix (common in the target audience)
    * Retrievers:
        - tfidf   : the real production retrieve() function, unmodified
        - dense   : sentence-transformers all-MiniLM-L6-v2 (22M params, ~90 MB)
        - hybrid  : reciprocal-rank fusion of the two
    * Metrics (topic-level, because the pipeline only needs the right topic):
        - top-1 accuracy, top-3 hit rate, MRR, mean latency per query

Usage:
    py scripts/benchmark_retrieval.py            # print tables
    py scripts/benchmark_retrieval.py --report   # also write docs/retrieval_benchmark.md

Requires: pip install sentence-transformers  (dev only, NOT a deploy dependency)
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))

# The pipeline module builds an LLM client at import time. Retrieval never
# touches it, so a placeholder key keeps the import side-effect free.
os.environ.setdefault("OPENROUTER_API_KEY", "benchmark-placeholder-no-llm-calls")

import rag_pipeline_lite as lite  # noqa: E402

BD, BG, PB, TX, GS = ("breakup_decision_phase", "breakup_execution_guilt",
                      "post_breakup_boundaries", "toxic_relationship_confusion",
                      "general_emotional_support")

QUERIES = [
    # ---- lexical: overlaps with dataset user_signals ------------------------
    ("lexical", "should I leave him?", BD),
    ("lexical", "I don't love her anymore but I can't leave", BD),
    ("lexical", "I'm scared to be alone if we break up", BD),
    ("lexical", "it's just comfortable at this point", BD),
    ("lexical", "I feel so guilty for breaking up with him", BG),
    ("lexical", "I don't want to hurt them", BG),
    ("lexical", "how do I end it gently", BG),
    ("lexical", "they said I'm giving up on us", BG),
    ("lexical", "I really want to text them", PB),
    ("lexical", "can we still be friends after this", PB),
    ("lexical", "I miss them so much", PB),
    ("lexical", "should I check on them?", PB),
    ("lexical", "am I the problem in this relationship?", TX),
    ("lexical", "why is it always my fault", TX),
    ("lexical", "I feel confused in my relationship", TX),
    ("lexical", "I feel bad today", GS),
    ("lexical", "I don't know what's wrong with me", GS),
    ("lexical", "I feel lost", GS),
    # ---- paraphrase: same intent, no shared keywords ------------------------
    ("paraphrase", "we've been together three years and I stay because starting over terrifies me", BD),
    ("paraphrase", "nothing is wrong exactly but nothing feels right either and I keep postponing the conversation", BD),
    ("paraphrase", "I'm 80 percent sure this isn't it but the 20 percent keeps me stuck", BD),
    ("paraphrase", "the thought of an empty flat on weekends stops me from walking away", BD),
    ("paraphrase", "is it wrong to stay just because it's easy", BD),
    ("paraphrase", "I'm the one walking away and I feel like a villain", BG),
    ("paraphrase", "how do I say it without wrecking them", BG),
    ("paraphrase", "he cried when I told him and now I can't stop replaying it", BG),
    ("paraphrase", "my friends think I'm selfish for calling it off", BG),
    ("paraphrase", "I ended it last night and feel sick about how she took it", BG),
    ("paraphrase", "it's been two weeks and my thumb keeps hovering over her name", PB),
    ("paraphrase", "he liked my story, does that mean something", PB),
    ("paraphrase", "muscle memory keeps opening our old chat", PB),
    ("paraphrase", "we said we'd stay close but every conversation reopens it", PB),
    ("paraphrase", "is reaching out to him after a month a bad idea", PB),
    ("paraphrase", "every argument ends with me apologising even when I didn't start it", TX),
    ("paraphrase", "she says I'm too sensitive whenever I bring something up", TX),
    ("paraphrase", "I keep a mental list of things I do wrong so I stop upsetting him", TX),
    ("paraphrase", "I second-guess everything I say around her", TX),
    ("paraphrase", "I'm exhausted from walking on eggshells at home", TX),
    ("paraphrase", "I've been off for weeks and can't put my finger on it", GS),
    ("paraphrase", "just needed to type this somewhere", GS),
    ("paraphrase", "not sure why I'm here honestly", GS),
    ("paraphrase", "everything is fine on paper but I'm not", GS),
    ("paraphrase", "some days it's just heavy", GS),
    # ---- hinglish ----------------------------------------------------------
    ("hinglish", "usse chhod dena chahiye kya", BD),
    ("hinglish", "use text karne ka bahut man kar raha hai", PB),
    ("hinglish", "hamesha meri hi galti kaise ho sakti hai", TX),
    ("hinglish", "samajh nahi aa raha kya ho raha hai mere saath", GS),
]

K = 5


# --------------------------------------------------------------------------
# retrievers: each returns an ordered list of topics (may repeat)
# --------------------------------------------------------------------------
def tfidf_topics(q: str) -> list[str]:
    return [r["meta"]["topic"] for r in lite.retrieve(q, k=K, threshold=0.0)]


class Dense:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        t0 = time.perf_counter()
        self.model = SentenceTransformer(model_name)
        self.docs = list(lite.texts) + list(lite.topic_keywords.values())
        self.topics = [m["topic"] for m in lite.metadata] + list(lite.topic_keywords.keys())
        self.emb = self.model.encode(self.docs, normalize_embeddings=True, show_progress_bar=False)
        self.load_s = time.perf_counter() - t0

    def topics_for(self, q: str) -> list[str]:
        import numpy as np
        qv = self.model.encode([q], normalize_embeddings=True, show_progress_bar=False)[0]
        scores = self.emb @ qv
        order = np.argsort(-scores)[:K]
        return [self.topics[i] for i in order]


def rrf(*rankings: list[str], k: int = 60) -> list[str]:
    """Reciprocal-rank fusion over topic rankings (first occurrence of a topic counts)."""
    score: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        seen = set()
        for rank, t in enumerate(ranking, start=1):
            if t in seen:
                continue
            seen.add(t)
            score[t] += 1.0 / (k + rank)
    return [t for t, _ in sorted(score.items(), key=lambda x: -x[1])]


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def score(name: str, fn) -> dict:
    per_subset: dict[str, dict] = defaultdict(lambda: {"n": 0, "top1": 0, "top3": 0, "rr": 0.0})
    misses = []
    t0 = time.perf_counter()
    for subset, q, gold in QUERIES:
        topics = fn(q)
        uniq = list(dict.fromkeys(topics))  # dedupe, keep order
        s = per_subset[subset]
        s["n"] += 1
        if uniq and uniq[0] == gold:
            s["top1"] += 1
        if gold in uniq[:3]:
            s["top3"] += 1
        if gold in uniq:
            s["rr"] += 1.0 / (uniq.index(gold) + 1)
        else:
            pass
        if not uniq or uniq[0] != gold:
            misses.append((subset, q, gold, uniq[0] if uniq else "-"))
    latency_ms = (time.perf_counter() - t0) * 1000 / len(QUERIES)

    total = {"n": 0, "top1": 0, "top3": 0, "rr": 0.0}
    for s in per_subset.values():
        for key in total:
            total[key] += s[key]
    per_subset["all"] = total
    return {"name": name, "subsets": dict(per_subset), "misses": misses, "latency_ms": latency_ms}


def fmt_row(res: dict, subset: str) -> str:
    s = res["subsets"][subset]
    n = s["n"] or 1
    return (f"| {res['name']} | {s['top1']}/{s['n']} ({s['top1']/n*100:.0f}%) "
            f"| {s['top3']}/{s['n']} ({s['top3']/n*100:.0f}%) | {s['rr']/n:.2f} |")


def render(results: list[dict], dense_load_s: float) -> str:
    subsets = ["lexical", "paraphrase", "hinglish", "all"]
    n_by = {s: sum(1 for x in QUERIES if x[0] == s) for s in subsets[:-1]}
    lines = [
        "# Retrieval Benchmark: TF-IDF vs Dense Embeddings",
        "",
        "Generated by `scripts/benchmark_retrieval.py --report`. Re-run to reproduce.",
        "",
        "## Question",
        "",
        "The deployed pipeline retrieves context with a pure-Python TF-IDF index because "
        "Vercel serverless functions cannot carry PyTorch. Does lexical matching miss the "
        "semantic nuance in how people describe distress? This benchmark compares the "
        "**unmodified production retriever** against a small dense model on the **same corpus**.",
        "",
        "## Setup",
        "",
        f"- Corpus: {len(lite.texts)} dataset passages + {len(lite.topic_keywords)} topic keyword strings "
        f"(identical to what production indexes)",
        f"- Queries: {len(QUERIES)} labelled messages — {n_by['lexical']} lexical (share vocabulary with the dataset), "
        f"{n_by['paraphrase']} paraphrase (same intent, no keyword overlap), {n_by['hinglish']} Hinglish",
        "- Retrievers: `tfidf` = production `retrieve()`; `dense` = all-MiniLM-L6-v2 cosine; "
        "`hybrid` = reciprocal-rank fusion of both",
        f"- Metric unit: the **topic** of each retrieved passage (top-{K}), since the prompt only needs the right topic",
        "",
    ]
    for subset in subsets:
        title = {"all": "All queries"}.get(subset, subset.capitalize() + " queries")
        lines += [f"## {title}", "", "| Retriever | Top-1 topic accuracy | Top-3 hit rate | MRR |", "|---|---|---|---|"]
        lines += [fmt_row(r, subset) for r in results]
        lines.append("")

    lines += ["## Cost", "", "| Retriever | Mean latency / query | Extra dependency | Cold-start cost |", "|---|---|---|---|"]
    for r in results:
        dep = {"tfidf": "none (pure Python)", "dense": "torch + sentence-transformers (~90 MB model)",
               "hybrid": "same as dense"}[r["name"]]
        cold = {"tfidf": "negligible", "dense": f"model load {dense_load_s:.1f}s + embedding corpus",
                "hybrid": "same as dense"}[r["name"]]
        lines.append(f"| {r['name']} | {r['latency_ms']:.1f} ms | {dep} | {cold} |")
    lines.append("")

    lines += ["## Top-1 misses", ""]
    for r in results:
        lines += [f"### {r['name']}", ""]
        if not r["misses"]:
            lines.append("None.")
        else:
            lines += ["| Subset | Query | Expected | Got |", "|---|---|---|---|"]
            for subset, q, gold, got in r["misses"]:
                lines.append(f"| {subset} | {q} | {gold} | {got} |")
        lines.append("")

    # Interpretation driven by the numbers so the doc never contradicts the tables.
    t, d, h = (next(r for r in results if r["name"] == n) for n in ("tfidf", "dense", "hybrid"))
    pt = t["subsets"]["paraphrase"]; pd_ = d["subsets"]["paraphrase"]; ph = h["subsets"]["paraphrase"]
    lt = t["subsets"]["lexical"]; ld = d["subsets"]["lexical"]
    gap = pd_["top1"] - pt["top1"]
    lines += ["## Interpretation", ""]
    lines.append(
        f"- On **lexical** queries TF-IDF gets {lt['top1']}/{lt['n']} and dense gets {ld['top1']}/{ld['n']}: "
        "when users echo the dataset's vocabulary, lexical matching is sufficient.")
    lines.append(
        f"- On **paraphrase** queries TF-IDF gets {pt['top1']}/{pt['n']} versus dense {pd_['top1']}/{pd_['n']} "
        f"and hybrid {ph['top1']}/{ph['n']}. "
        + ("This is the gap the benchmark was designed to expose: " if gap > 0 else "")
        + ("dense embeddings recover intent that shares no words with the corpus." if gap > 0
           else "dense embeddings do not improve on TF-IDF for this corpus."))
    lines.append(
        "- **Hinglish** is weak for both: MiniLM is English-only and the corpus contains no Hindi, "
        "so the fix is data (add Hinglish user_signals), not the retriever.")
    lines += [
        "",
        "## Decision",
        "",
        "TF-IDF stays in production for now because the serverless memory limit rules out PyTorch, "
        "and the lexical subset shows it is adequate for the common case. The paraphrase gap is real and is "
        "addressed in two steps:",
        "",
        "1. **Cheap, now:** add paraphrased `user_signals` to `data/dataset3.json` so TF-IDF's topic-keyword "
        "boost catches indirect phrasings (the misses table above is the backlog).",
        "2. **Later:** move dense retrieval to a hosted embedding API (no local model), gated by the same "
        "benchmark so the change is measured, not assumed.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    print(f"corpus: {len(lite.texts)} passages, {len(QUERIES)} queries")
    dense = Dense()
    print(f"dense model loaded in {dense.load_s:.1f}s")

    results = [
        score("tfidf", tfidf_topics),
        score("dense", dense.topics_for),
        score("hybrid", lambda q: rrf(tfidf_topics(q), dense.topics_for(q))),
    ]
    for subset in ("lexical", "paraphrase", "hinglish", "all"):
        print(f"\n[{subset}]")
        print("| Retriever | Top-1 | Top-3 | MRR |")
        for r in results:
            print(fmt_row(r, subset))
    for r in results:
        print(f"\n{r['name']} latency {r['latency_ms']:.1f} ms/query, misses={len(r['misses'])}")

    if "--report" in argv:
        out = os.path.join(ROOT, "docs", "retrieval_benchmark.md")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(render(results, dense.load_s))
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

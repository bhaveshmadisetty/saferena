"""
Deterministic crisis detection for Safe Space.

WHY THIS EXISTS:
The system prompt asks the LLM to surface helplines when a user mentions
self-harm. That instruction is best-effort — the model can ignore it, the
API can be rate-limited, the key can be exhausted, or the request can fail
outright. In any of those cases a user in crisis would receive a generic
fallback string and no helpline.

This module screens the user's message in code, before and independently of
the model, so the helpline response is guaranteed. It is intentionally
simple and dependency-free.

Tuned for an Indian audience (iCall, Vandrevala, Tele-MANAS).
"""

import re

# ---------------------------------------------------------------------------
# HELPLINES (India)
# ---------------------------------------------------------------------------
HELPLINE_BLOCK = (
    "**iCall** — 9152987821 (Mon–Sat, 10am–8pm)\n"
    "**Vandrevala Foundation** — 1860-2662-345 (24x7)\n"
    "**Tele-MANAS** — 14416 (24x7, government helpline)"
)

# ---------------------------------------------------------------------------
# PATTERNS
# ---------------------------------------------------------------------------
# High confidence: explicit intent or planning. These trigger the crisis
# response immediately, replacing the model's reply.
_HIGH_RISK = [
    r"\bkill(ing)?\s+my\s?self\b",
    r"\bkms\b",
    r"\bend(ing)?\s+(my|this)\s+life\b",
    r"\btake\s+my\s+(own\s+)?life\b",
    r"\bcommit\s+suicide\b",
    r"\bsuicide\b",
    r"\bsuicidal\b",
    r"\bwant(s|ed)?\s+to\s+die\b",
    r"\bwanna\s+die\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bdon'?t\s+want\s+to\s+(be\s+here|exist|live|wake\s+up)\b",
    r"\bdo\s?n'?t\s+want\s+to\s+live\b",
    r"\bno\s+(reason|point)\s+(to|in)\s+liv",
    r"\bnothing\s+to\s+live\s+for\b",
    r"\bcut(ting)?\s+my\s?self\b",
    r"\bhurt(ing)?\s+my\s?self\b",
    r"\bharm(ing)?\s+my\s?self\b",
    r"\bself[\s-]?harm\b",
    r"\boverdos(e|ing)\b",
    r"\bhang\s+my\s?self\b",
    r"\bjump\s+off\b",
    r"\bslit\s+my\s+wrist",
    r"\bwrote\s+a\s+(suicide\s+)?note\b",
    r"\bgoodbye\s+forever\b",
    r"\bthis\s+is\s+my\s+last\b",
]

# Lower confidence: distress worth flagging to the model so it responds with
# extra care, but NOT worth overriding the conversation for.
_ELEVATED_RISK = [
    r"\bhopeless\b",
    r"\bworthless\b",
    r"\bcan'?t\s+(go\s+on|do\s+this\s+an?y?more|take\s+it\s+an?y?more)\b",
    r"\bgive\s+up\s+on\s+everything\b",
    r"\bdisappear\b",
    r"\bnobody\s+would\s+(care|notice|miss)\b",
    r"\bburden\s+to\s+everyone\b",
    r"\bnumb\b",
    r"\bempty\s+inside\b",
]

_HIGH_RE = [re.compile(p, re.IGNORECASE) for p in _HIGH_RISK]
_ELEVATED_RE = [re.compile(p, re.IGNORECASE) for p in _ELEVATED_RISK]

# Phrases that indicate the user is describing something other than their own
# present intent (past tense, third party, hypothetical, media).
_NEGATION_RE = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(my|a|his|her|their)\s+(friend|brother|sister|cousin|mom|mother|dad|father|colleague|classmate)\b",
        r"\bused\s+to\s+(feel|think|want)\b",
        r"\b(movie|film|show|series|book|song|character|news|article)\b",
        r"\bnot\s+suicidal\b",
        r"\bi'?m\s+not\s+going\s+to\b",
        r"\bwould\s+never\b",
    ]
]


def _has_negation(text: str) -> bool:
    return any(r.search(text) for r in _NEGATION_RE)


def assess(text: str) -> str:
    """
    Classify a user message.

    Returns "high", "elevated", or "none".
    """
    if not text or not isinstance(text, str):
        return "none"

    if any(r.search(text) for r in _HIGH_RE):
        # Still return high on negation, but downgrade to elevated so a user
        # talking about a friend gets care rather than an interrupted session.
        return "elevated" if _has_negation(text) else "high"

    if any(r.search(text) for r in _ELEVATED_RE):
        return "elevated"

    return "none"


def crisis_reply(first_name: str = "") -> str:
    """
    The guaranteed response for a high-risk message.

    Validates first, surfaces helplines, then invites the user to continue —
    it does not end the conversation or lecture.
    """
    name = f" {first_name}" if first_name else ""
    return (
        f"I'm really glad you told me{name}. What you're carrying sounds genuinely heavy, "
        "and I don't want you to be alone with it right now.\n\n"
        "Before we keep going — please reach out to someone who can stay with you properly:\n\n"
        f"{HELPLINE_BLOCK}\n\n"
        "If you're in immediate danger, please call **112**.\n\n"
        "I'm still here. If you want to keep talking, I'm listening — what's been happening?"
    )


def prompt_annotation(level: str) -> str:
    """
    Text injected into the system prompt so the model adapts its tone.
    Used for the "elevated" level, where we do not override the reply.
    """
    if level == "elevated":
        return (
            "\n⚠️ SAFETY SIGNAL: This message contains distress markers. "
            "Slow down. Validate explicitly and do not offer solutions or reframes. "
            "If the user's risk seems to be escalating, gently surface iCall (9152987821) "
            "and Vandrevala Foundation (1860-2662-345).\n"
        )
    if level == "high":
        return (
            "\n🚨 SAFETY SIGNAL: Possible risk of self-harm. Lead with warmth and "
            "helplines before anything else.\n"
        )
    return ""

"""
AI feedback analysis for CTMS.

Uses the Claude API (one HTTP request) to:
  1. classify a student comment as positive / neutral / negative
  2. write a short factual summary of many comments

If no API key is set, or the API call fails for any reason (no internet,
timeout, bad key), it falls back to a simple keyword matcher so the system
keeps working. The original student comment is never changed.

Config (environment variables, never hard-coded):
  ANTHROPIC_API_KEY  - your API key (if missing, the fallback is used)
  AI_MODEL           - optional, defaults to claude-haiku-4-5-20251001
"""
import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
VALID = {"positive", "neutral", "negative"}


# ---------------------------------------------------------------------------
# Claude API call
# ---------------------------------------------------------------------------

def _call_claude(system_prompt, user_text, max_tokens=300):
    """Send one request to the Claude API. Returns text, or None on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    body = json.dumps({
        "model": os.environ.get("AI_MODEL", DEFAULT_MODEL),
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_text}],
    }).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["content"][0]["text"].strip()
    except Exception:
        # Never show raw errors to users; the caller will use the fallback.
        return None


# ---------------------------------------------------------------------------
# Public functions used by the views
# ---------------------------------------------------------------------------

def analyze_sentiment(comment: str) -> str:
    """Return 'positive', 'neutral' or 'negative' for a feedback comment."""
    if not comment or not comment.strip():
        return "neutral"

    answer = _call_claude(
        "You classify student feedback about an online tutorial. "
        "Reply with exactly one word: positive, neutral, or negative.",
        comment,
        max_tokens=5,
    )
    if answer:
        label = answer.lower().strip(" .!\n")
        if label in VALID:
            return label

    return _keyword_sentiment(comment)


def summarize_feedback(comments: list[str]) -> str:
    """Short factual summary of feedback comments (no invented facts)."""
    if not comments:
        return "No feedback has been submitted yet."

    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(comments))
    answer = _call_claude(
        "You summarise student feedback about a lecturer's online tutorials "
        "for an administrator. Write 2 to 3 plain sentences. Use ONLY what is "
        "in the comments. Do not invent facts, and do not judge whether the "
        "lecturer is good or bad.",
        numbered,
        max_tokens=250,
    )
    return answer or _keyword_summary(comments)


# ---------------------------------------------------------------------------
# Fallback (no API key / API unavailable)
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "good", "great", "excellent", "clear", "clearly", "helpful", "engaging",
    "well", "amazing", "fantastic", "wonderful", "patient", "knowledgeable",
    "organized", "informative", "enjoyed", "enjoyable", "best", "easy",
    "understand", "understood", "interactive", "encouraging", "thorough",
    "responsive", "supportive", "love", "loved", "awesome", "perfect",
}

NEGATIVE_WORDS = {
    "bad", "poor", "late", "confusing", "confused", "boring", "unclear",
    "disorganized", "rude", "unhelpful", "worst", "terrible", "awful",
    "difficult", "hard", "problem", "issue", "slow", "disappointing",
    "disappointed", "inaudible", "lag", "lagging", "cut", "cancelled",
    "cancel", "never", "not", "no", "poorly", "weak", "struggled", "fail",
}


def _keyword_sentiment(comment: str) -> str:
    words = [w.strip(".,!?;:\"'()").lower() for w in comment.split()]
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _keyword_summary(comments: list[str]) -> str:
    total = len(comments)
    labels = [_keyword_sentiment(c) for c in comments]
    pos, neg = labels.count("positive"), labels.count("negative")
    parts = []
    if pos:
        parts.append(f"{pos} of {total} comments were positive.")
    if neg:
        parts.append(f"{neg} of {total} comments raised concerns worth reviewing.")
    if not pos and not neg:
        parts.append(f"All {total} comments were largely neutral in tone.")
    return " ".join(parts)

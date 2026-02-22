"""
Review context: summarize and extract themes from Google Place Details review text.

Uses up to 5 reviews returned by Place Details. Optional LLM for summary + themes;
fallback to keyword-based themes when no API key.
"""

import os
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Simple theme keywords (fallback when no LLM)
REVIEW_THEME_KEYWORDS = {
    "quality": ["quality", "great work", "excellent", "professional", "skilled", "done right"],
    "service": ["service", "friendly", "courteous", "responsive", "on time", "punctual"],
    "price": ["price", "fair", "reasonable", "worth it", "affordable", "quote"],
    "timeliness": ["fast", "quick", "on time", "scheduled", "timely", "same day"],
    "trust": ["trust", "recommend", "honest", "reliable", "dependable"],
}


def _get_review_texts(reviews: List[Dict], max_chars: int = 3000) -> List[str]:
    """Extract non-empty review texts, capped for API."""
    texts = []
    total = 0
    for r in reviews:
        t = (r.get("text") or "").strip()
        if not t:
            continue
        if total + len(t) > max_chars:
            break
        texts.append(t)
        total += len(t)
    return texts


def _fallback_themes(texts: List[str]) -> List[str]:
    """Extract themes from keyword matching (no LLM)."""
    combined = " ".join(texts).lower()
    found = []
    for theme, keywords in REVIEW_THEME_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            found.append(theme)
    return found[:5] if found else []


def _llm_summarize_reviews(texts: List[str], rating: Optional[float], review_count: Optional[int]) -> Dict[str, Any]:
    """Call OpenAI to summarize and extract themes. Returns {} on failure."""
    try:
        from openai import OpenAI
    except ImportError:
        return {}
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}
    client = OpenAI()
    combined = "\n---\n".join(texts[:5])[:4000]
    prompt = f"""Based on these Google reviews (rating: {rating}, total reviews: {review_count}), provide:
1. A 2-3 sentence summary of what customers say (praise and complaints).
2. A list of 3-5 short theme labels (e.g. "quality", "timeliness", "value", "professionalism").

Reviews:
{combined}

Respond with JSON only: {{"summary": "...", "themes": ["...", "..."]}}"""
    try:
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            timeout=20,
        )
        import json
        content = (r.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)
        data = json.loads(content)
        return {
            "review_summary": data.get("summary") or "",
            "review_themes": data.get("themes") if isinstance(data.get("themes"), list) else [],
        }
    except Exception as e:
        logger.warning("Review context LLM failed: %s", e)
        return {}


def build_review_context(
    reviews: List[Dict],
    rating: Optional[float] = None,
    review_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build review context from Place Details reviews (text + rating + count).

    Returns:
        - review_summary: 2-3 sentence summary (LLM if key set, else short fallback)
        - review_themes: list of theme strings (e.g. quality, service, timeliness)
        - review_sample_snippets: first 2-3 short snippets (first 80 chars each)
    """
    texts = _get_review_texts(reviews)
    out = {
        "review_summary": None,
        "review_themes": [],
        "review_sample_snippets": [],
    }
    if not texts:
        if review_count and review_count > 0:
            out["review_summary"] = f"{review_count} reviews on Google (rating: {rating}). No review text available from API."
        return out

    # Sample snippets (always)
    out["review_sample_snippets"] = [(t[:80] + "..." if len(t) > 80 else t) for t in texts[:3]]

    # Try LLM first
    llm_out = _llm_summarize_reviews(texts, rating, review_count or len(texts))
    if llm_out:
        out["review_summary"] = llm_out.get("review_summary")
        out["review_themes"] = llm_out.get("review_themes") or []
        return out

    # Fallback: keyword themes + short summary
    themes = _fallback_themes(texts)
    out["review_themes"] = themes
    n = len(texts)
    rc = review_count or n
    out["review_summary"] = (
        f"{rc} reviews on Google (rating: {rating}). "
        + (f"Themes mentioned: {', '.join(themes)}. " if themes else "")
        + "Sample: " + (texts[0][:120] + "..." if len(texts[0]) > 120 else texts[0])
    )
    return out

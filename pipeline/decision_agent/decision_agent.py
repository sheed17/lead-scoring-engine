"""
Decision Agent: single owner of judgment. Makes clear decisions and explains them.

- Input: normalized_signals (semantic signals dict), agency_type ("seo" | "marketing").
- Output: Decision(verdict, confidence, reasoning, primary_risks, what_would_change).
- One LLM call per lead; strict JSON output; no RAG, no embeddings.
- LLM acts as senior agency operator, not reporter. No hedging; no restating raw data.
"""

import os
import json
import re
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Literal, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 30
PROMPT_VERSION_PREFIX = "v1"


@dataclass
class Decision:
    """Single decision output: verdict + reasoning + risks + what would change."""
    verdict: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: float
    reasoning: str
    primary_risks: List[str]
    what_would_change: List[str]


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def _build_system_message(agency_type: Literal["seo", "marketing"]) -> str:
    if agency_type == "seo":
        return (
            "You are a senior SEO agency operator. Your job is to decide whether a business "
            "is worth pursuing for SEO and explain why. Consider rankability, content potential, "
            "technical gaps, and execution friction. You must choose exactly one verdict: HIGH, MEDIUM, or LOW. "
            "Do not hedge. Do not restate raw data; interpret signals and explain what they mean for SEO. "
            "Include 1-3 primary_risks and 1-3 what_would_change. Output only valid JSON."
        )
    else:
        return (
            "You are a senior marketing agency operator. Your job is to decide whether a business "
            "is worth pursuing for marketing and explain why. Consider growth intent, digital maturity, "
            "conversion gaps, and client risk. You must choose exactly one verdict: HIGH, MEDIUM, or LOW. "
            "Do not hedge. Do not restate raw data; interpret signals and explain what they mean for marketing. "
            "Include 1-3 primary_risks and 1-3 what_would_change. Output only valid JSON."
        )


def _format_signals_for_prompt(semantic: Dict[str, str]) -> str:
    lines = [f"- {k}: {v}" for k, v in semantic.items()]
    return "\n".join(lines) if lines else "No signals."


def _build_user_message(semantic_signals: Dict[str, str], lead_name: str = "") -> str:
    signals_block = _format_signals_for_prompt(semantic_signals)
    name_line = f"Business: {lead_name}\n\n" if lead_name else ""
    return f"""{name_line}Semantic signals (factual; interpret them, do not restate):

{signals_block}

Return a JSON object with exactly these keys (no other text):
- "verdict": exactly one of "HIGH", "MEDIUM", "LOW"
- "confidence": number between 0.0 and 1.0
- "reasoning": one short paragraph interpreting the signals and why this verdict
- "primary_risks": array of 1-3 short risk strings
- "what_would_change": array of 1-3 short strings describing what would change your decision

Output only the JSON object."""


def _parse_response(text: str) -> Optional[Decision]:
    """Parse LLM response into Decision. Returns None on failure."""
    raw = (text or "").strip()
    if not raw:
        return None
    # Strip markdown code block if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    verdict_raw = (data.get("verdict") or "").strip().upper()
    if verdict_raw not in ("HIGH", "MEDIUM", "LOW"):
        return None
    confidence = data.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence = max(0.0, min(1.0, float(confidence)))
    else:
        confidence = 0.5
    reasoning = (data.get("reasoning") or "No reasoning provided.").strip()
    primary_risks = data.get("primary_risks")
    if not isinstance(primary_risks, list):
        primary_risks = []
    primary_risks = [str(x).strip() for x in primary_risks if x][:3]
    what_would_change = data.get("what_would_change")
    if not isinstance(what_would_change, list):
        what_would_change = []
    what_would_change = [str(x).strip() for x in what_would_change if x][:3]
    return Decision(
        verdict=verdict_raw,
        confidence=confidence,
        reasoning=reasoning,
        primary_risks=primary_risks,
        what_would_change=what_would_change,
    )


def _fallback_decision() -> Decision:
    """Safe fallback when LLM fails or parse fails."""
    return Decision(
        verdict="LOW",
        confidence=0.0,
        reasoning="Decision unavailable; LLM or parse error.",
        primary_risks=[],
        what_would_change=[],
    )


class DecisionAgent:
    """
    Single owner of judgment: takes normalized signals + agency_type, returns one Decision.

    No RAG, no embeddings. One LLM call per lead. Every decision should be logged verbatim
    with prompt_version for future learning.
    """

    def __init__(
        self,
        agency_type: Literal["seo", "marketing"] = "marketing",
        model: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ):
        self.agency_type = agency_type
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.prompt_version = prompt_version or f"{PROMPT_VERSION_PREFIX}_{agency_type}"

    def decide(
        self,
        normalized_signals: Dict[str, Any],
        lead_name: str = "",
    ) -> Decision:
        """
        Run one decision: build prompt, call LLM once, return Decision.

        normalized_signals: semantic signals (e.g. from build_semantic_signals).
        lead_name: optional for prompt context.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set; returning fallback decision")
            return _fallback_decision()
        client = _get_client()
        if not client:
            logger.warning("openai package not installed; returning fallback decision")
            return _fallback_decision()

        system = _build_system_message(self.agency_type)
        user = _build_user_message(normalized_signals, lead_name)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                timeout=REQUEST_TIMEOUT,
            )
            choice = response.choices[0] if response.choices else None
            if not choice or not getattr(choice, "message", None):
                return _fallback_decision()
            text = (choice.message.content or "").strip()
            decision = _parse_response(text)
            if decision is None:
                logger.warning("Decision parse failed; raw response: %s", text[:500])
                return _fallback_decision()
            return decision
        except Exception as e:
            logger.warning("DecisionAgent LLM request failed: %s", e)
            return _fallback_decision()

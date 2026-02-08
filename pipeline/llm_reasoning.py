"""
Optional LLM step for refining reasoning and synthesis.

Called only when --llm_reasoning is enabled. Input = deterministic context
(dimensions + evidence). Output = refined reasoning_summary, primary_themes,
suggested_outreach_angles. Does not change dimension status or evidence.
Falls back to deterministic output on missing API key, timeout, or parse error.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Default model; override with OPENAI_MODEL
DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT = 30


def _get_client():
    """Lazy import to avoid requiring openai when --llm_reasoning is off."""
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def refine_with_llm(
    context: Dict[str, Any],
    lead_name: Optional[str] = None,
    similar_summaries: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Refine reasoning_summary, primary_themes, and suggested_outreach_angles using an LLM.

    Does not modify context_dimensions or evidence. On any failure, returns
    the original context fields (reasoning_summary, primary_themes, suggested_outreach_angles).

    Args:
        context: Output from context.build_context() with context_dimensions,
                 reasoning_summary, priority_suggestion, primary_themes,
                 suggested_outreach_angles, confidence.
        lead_name: Optional business name for prompt context.
        similar_summaries: Optional list of text snippets from similar past leads (RAG).

    Returns:
        Same structure as context but with possibly updated:
        - reasoning_summary (refined wording)
        - primary_themes (list of strings)
        - suggested_outreach_angles (list of strings)
        - reasoning_source: "llm" if successful, "deterministic" if fallback
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; using deterministic output")
        return {**context, "reasoning_source": "deterministic"}

    client = _get_client()
    if not client:
        logger.warning("openai package not installed; using deterministic output")
        return {**context, "reasoning_source": "deterministic"}

    dimensions_text = _format_dimensions_for_prompt(context.get("context_dimensions", []))
    prompt = _build_prompt(
        dimensions_text,
        context.get("reasoning_summary", ""),
        lead_name,
        similar_summaries=similar_summaries or [],
    )

    try:
        model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You refine opportunity intelligence for sales outreach. "
                        "Output valid JSON only, no markdown. Do not change dimension status or evidence; "
                        "only refine the reasoning summary and suggest themes and outreach angles."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            timeout=REQUEST_TIMEOUT,
        )
        choice = response.choices[0] if response.choices else None
        if not choice or not getattr(choice, "message", None):
            return _fallback(context)
        text = (choice.message.content or "").strip()
        # Strip markdown code block if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        data = json.loads(text)
        return {
            **context,
            "reasoning_summary": data.get("reasoning_summary") or context.get("reasoning_summary", ""),
            "primary_themes": data.get("primary_themes") if isinstance(data.get("primary_themes"), list) else context.get("primary_themes", []),
            "suggested_outreach_angles": data.get("suggested_outreach_angles") if isinstance(data.get("suggested_outreach_angles"), list) else context.get("suggested_outreach_angles", []),
            "reasoning_source": "llm",
        }
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("LLM response parse error: %s; using deterministic output", e)
        return _fallback(context)
    except Exception as e:
        logger.warning("LLM request failed: %s; using deterministic output", e)
        return _fallback(context)


def _fallback(context: Dict) -> Dict:
    return {**context, "reasoning_source": "deterministic"}


def _format_dimensions_for_prompt(dimensions: List[Dict]) -> str:
    lines = []
    for d in dimensions:
        name = d.get("dimension", "")
        status = d.get("status", "Unknown")
        evidence = d.get("evidence", [])
        lines.append(f"- {name}: {status}. Evidence: {'; '.join(evidence[:3])}")
    return "\n".join(lines) if lines else "No dimensions."


def _build_prompt(
    dimensions_text: str,
    current_summary: str,
    lead_name: Optional[str],
    similar_summaries: Optional[List[str]] = None,
) -> str:
    name_line = f"Business: {lead_name}\n\n" if lead_name else ""
    rag_block = ""
    if similar_summaries:
        rag_block = "\nSimilar past summaries (use for style/angle ideas, do not copy):\n" + "\n".join(
            f"- {s[:400]}" for s in similar_summaries[:5]
        ) + "\n\n"
    return f"""{name_line}Context dimensions (do not change status or evidence):

{dimensions_text}
{rag_block}
Current reasoning summary: {current_summary}

Return a JSON object with exactly these keys:
- "reasoning_summary": one short paragraph refining the above summary (clear, actionable).
- "primary_themes": list of 1-5 short theme strings (e.g. "Paid growth / conversion", "Reputation").
- "suggested_outreach_angles": list of 1-5 concrete outreach angle strings for sales.

Output only the JSON object, no other text."""

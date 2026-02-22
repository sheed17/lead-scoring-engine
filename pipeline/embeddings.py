"""
Embeddings for RAG: embed context text (reasoning + dimensions) via OpenAI.
Phase 2: retrieve similar past summaries to improve LLM refinement.
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def _get_client():
    try:
        from openai import OpenAI
        return OpenAI()
    except ImportError:
        return None


def get_embedding(text: str) -> Optional[List[float]]:
    """
    Embed text using OpenAI. Returns list of floats or None on failure.
    """
    if not (text or "").strip():
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    client = _get_client()
    if not client:
        return None
    try:
        model = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        r = client.embeddings.create(input=[text.strip()[:8000]], model=model)
        if r.data and len(r.data) > 0:
            return r.data[0].embedding
    except Exception as e:
        logger.warning("Embedding failed: %s", e)
    return None


def text_to_embed(context: dict) -> str:
    """
    Build a single string from context for embedding (and similarity search).
    Uses reasoning_summary plus a short dimension summary.
    """
    parts = [context.get("reasoning_summary") or ""]
    for d in context.get("context_dimensions") or []:
        name = d.get("dimension", "")
        status = d.get("status", "")
        if name and status:
            parts.append(f"{name}: {status}")
    return " ".join(p for p in parts if p).strip()

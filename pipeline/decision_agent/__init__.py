"""
Decision Agent: single owner of judgment for the pipeline.

Consumes normalized (semantic) signals + agency_type; outputs one verdict (HIGH/MEDIUM/LOW)
with reasoning, risks, and what_would_change. No RAG, no embeddings. One LLM call per lead.
"""

from .decision_agent import Decision, DecisionAgent

__all__ = ["Decision", "DecisionAgent"]

"""
Minimal feedback loop: append-only lead outcomes. No ML; logging only.
UI or CRM can call record_lead_outcome() when contact/reply/call/close is known.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_OUTCOMES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "lead_outcomes.jsonl",
)


def _snapshot_hash(canonical_summary_v1: dict) -> str:
    """Deterministic hash of canonical summary for idempotency / versioning."""
    if not canonical_summary_v1:
        return ""
    # Sort keys for stable hash
    blob = json.dumps(canonical_summary_v1, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def record_lead_outcome(
    lead_id: str,
    snapshot_hash: str,
    worth_pursuing_at_time: str,
    contacted: bool = False,
    replied: bool = False,
    call_booked: bool = False,
    closed: bool = False,
    timestamp: Optional[str] = None,
    path: Optional[str] = None,
) -> None:
    """
    Append one outcome row to data/lead_outcomes.jsonl.
    lead_id: e.g. place_id or internal ID
    snapshot_hash: from _snapshot_hash(canonical_summary_v1)
    worth_pursuing_at_time: "Yes" | "No" | "Maybe" at time of run
    """
    path = path or DEFAULT_OUTCOMES_PATH
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    row = {
        "lead_id": lead_id,
        "snapshot_hash": snapshot_hash,
        "worth_pursuing_at_time": worth_pursuing_at_time,
        "contacted": bool(contacted),
        "replied": bool(replied),
        "call_booked": bool(call_booked),
        "closed": bool(closed),
        "timestamp": ts,
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        logger.warning("Failed to record lead outcome: %s", e)

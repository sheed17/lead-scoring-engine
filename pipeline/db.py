"""
SQLite persistence for Context-First Opportunity Intelligence.

Stores runs, leads, signals, context dimensions, and lead embeddings (Phase 2 RAG).
"""

import os
import sqlite3
import json
import uuid
import logging
from collections import Counter
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default path; override with OPPORTUNITY_DB_PATH
DEFAULT_DB_DIR = "data"
DEFAULT_DB_NAME = "opportunity_intelligence.db"


def get_db_path() -> str:
    """Return path to SQLite DB file."""
    path = os.getenv("OPPORTUNITY_DB_PATH")
    if path:
        return path
    os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
    return os.path.join(DEFAULT_DB_DIR, DEFAULT_DB_NAME)


def _get_conn() -> sqlite3.Connection:
    """Get connection with row factory for dict-like rows."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                config TEXT,
                leads_count INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'running'
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                place_id TEXT NOT NULL,
                name TEXT,
                address TEXT,
                latitude REAL,
                longitude REAL,
                raw_place_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES runs(id),
                UNIQUE(run_id, place_id)
            );

            CREATE TABLE IF NOT EXISTS lead_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL UNIQUE,
                signals_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS context_dimensions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL UNIQUE,
                dimensions_json TEXT NOT NULL,
                reasoning_summary TEXT NOT NULL,
                priority_suggestion TEXT,
                primary_themes_json TEXT,
                outreach_angles_json TEXT,
                overall_confidence REAL,
                reasoning_source TEXT DEFAULT 'deterministic',
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS lead_embeddings (
                lead_id INTEGER NOT NULL UNIQUE,
                embedding_json TEXT NOT NULL,
                text_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL UNIQUE,
                agency_type TEXT NOT NULL,
                signals_snapshot TEXT,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT NOT NULL,
                primary_risks TEXT,
                what_would_change TEXT,
                prompt_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE INDEX IF NOT EXISTS idx_leads_run ON leads(run_id);
            CREATE INDEX IF NOT EXISTS idx_context_lead ON context_dimensions(lead_id);
            CREATE INDEX IF NOT EXISTS idx_decisions_lead ON decisions(lead_id);

            CREATE TABLE IF NOT EXISTS lead_embeddings_v2 (
                lead_id INTEGER NOT NULL,
                embedding_json TEXT NOT NULL,
                text_snapshot TEXT NOT NULL,
                embedding_version TEXT NOT NULL,
                embedding_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (lead_id, embedding_version, embedding_type),
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );

            CREATE TABLE IF NOT EXISTS lead_outcomes (
                lead_id INTEGER NOT NULL UNIQUE,
                vertical TEXT,
                agency_type TEXT,
                contacted INTEGER DEFAULT 0,
                proposal_sent INTEGER DEFAULT 0,
                closed INTEGER DEFAULT 0,
                close_value_usd REAL,
                service_sold TEXT,
                notes TEXT,
                status TEXT,
                updated_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );
        """)
        conn.commit()
        # Optional columns (migration for existing DBs)
        for sql in [
            "ALTER TABLE runs ADD COLUMN run_stats TEXT",
            "ALTER TABLE context_dimensions ADD COLUMN no_opportunity INTEGER",
            "ALTER TABLE context_dimensions ADD COLUMN no_opportunity_reason TEXT",
            "ALTER TABLE context_dimensions ADD COLUMN priority_derivation TEXT",
            "ALTER TABLE context_dimensions ADD COLUMN validation_warnings TEXT",
            "ALTER TABLE leads ADD COLUMN dentist_profile_v1_json TEXT",
            "ALTER TABLE leads ADD COLUMN llm_reasoning_layer_json TEXT",
            "ALTER TABLE leads ADD COLUMN sales_intervention_intelligence_json TEXT",
            "ALTER TABLE leads ADD COLUMN objective_decision_layer_json TEXT",
        ]:
            try:
                conn.execute(sql)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
    finally:
        conn.close()


def create_run(config: Optional[Dict] = None) -> str:
    """Create a new run; return run_id (UUID)."""
    init_db()
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(config or {}) if config else None
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO runs (id, created_at, config, status) VALUES (?, ?, ?, ?)",
            (run_id, now, config_json, "running")
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Created run %s", run_id[:8])
    return run_id


def insert_lead(run_id: str, lead: Dict) -> int:
    """Insert a lead; return lead_id."""
    now = datetime.now(timezone.utc).isoformat()
    raw_json = json.dumps(lead, default=str) if lead.get("_place_details") else None
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO leads (run_id, place_id, name, address, latitude, longitude, raw_place_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                lead.get("place_id", ""),
                lead.get("name"),
                lead.get("address"),
                lead.get("latitude"),
                lead.get("longitude"),
                raw_json,
                now,
            )
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_lead_signals(lead_id: int, signals: Dict) -> None:
    """Store signals JSON for a lead."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO lead_signals (lead_id, signals_json, created_at) VALUES (?, ?, ?)",
            (lead_id, json.dumps(signals, default=str), now)
        )
        conn.commit()
    finally:
        conn.close()


def insert_decision(
    lead_id: int,
    agency_type: str,
    signals_snapshot: Optional[Dict],
    verdict: str,
    confidence: float,
    reasoning: str,
    primary_risks: List[str],
    what_would_change: List[str],
    prompt_version: str,
) -> None:
    """Store one decision (Decision Agent output) for a lead. Verbatim for future learning."""
    now = datetime.now(timezone.utc).isoformat()
    signals_json = json.dumps(signals_snapshot, default=str) if signals_snapshot else None
    risks_json = json.dumps(primary_risks) if primary_risks else None
    change_json = json.dumps(what_would_change) if what_would_change else None
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO decisions (lead_id, agency_type, signals_snapshot, verdict, confidence,
               reasoning, primary_risks, what_would_change, prompt_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_id,
                agency_type,
                signals_json,
                verdict,
                confidence,
                reasoning,
                risks_json,
                change_json,
                prompt_version,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_context_dimensions(
    lead_id: int,
    dimensions: List[Dict],
    reasoning_summary: str,
    overall_confidence: float,
    priority_suggestion: Optional[str] = None,
    primary_themes: Optional[List[str]] = None,
    outreach_angles: Optional[List[str]] = None,
    reasoning_source: str = "deterministic",
    no_opportunity: bool = False,
    no_opportunity_reason: Optional[str] = None,
    priority_derivation: Optional[str] = None,
    validation_warnings: Optional[List[str]] = None,
) -> None:
    """Store context dimensions and reasoning for a lead."""
    now = datetime.now(timezone.utc).isoformat()
    dimensions_json = json.dumps(dimensions, default=str)
    themes_json = json.dumps(primary_themes) if primary_themes is not None else None
    angles_json = json.dumps(outreach_angles) if outreach_angles is not None else None
    warnings_json = json.dumps(validation_warnings) if validation_warnings else None
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO context_dimensions
               (lead_id, dimensions_json, reasoning_summary, priority_suggestion,
                primary_themes_json, outreach_angles_json, overall_confidence, reasoning_source,
                no_opportunity, no_opportunity_reason, priority_derivation, validation_warnings, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_id,
                dimensions_json,
                reasoning_summary,
                priority_suggestion,
                themes_json,
                angles_json,
                overall_confidence,
                reasoning_source,
                1 if no_opportunity else 0,
                no_opportunity_reason,
                priority_derivation,
                warnings_json,
                now,
            )
        )
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
        conn.execute(
            """INSERT INTO context_dimensions
               (lead_id, dimensions_json, reasoning_summary, priority_suggestion,
                primary_themes_json, outreach_angles_json, overall_confidence, reasoning_source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_id,
                dimensions_json,
                reasoning_summary,
                priority_suggestion,
                themes_json,
                angles_json,
                overall_confidence,
                reasoning_source,
                now,
            )
        )
        conn.commit()
    finally:
        conn.close()


def update_lead_dentist_data(
    lead_id: int,
    dentist_profile_v1: Optional[Dict] = None,
    llm_reasoning_layer: Optional[Dict] = None,
    sales_intervention_intelligence: Optional[Dict] = None,
    objective_decision_layer: Optional[Dict] = None,
) -> None:
    """Store dentist vertical profile, LLM reasoning layer, sales intervention intelligence, and/or objective decision layer for a lead."""
    conn = _get_conn()
    try:
        if dentist_profile_v1 is not None:
            conn.execute(
                "UPDATE leads SET dentist_profile_v1_json = ? WHERE id = ?",
                (json.dumps(dentist_profile_v1, default=str), lead_id),
            )
        if llm_reasoning_layer is not None:
            conn.execute(
                "UPDATE leads SET llm_reasoning_layer_json = ? WHERE id = ?",
                (json.dumps(llm_reasoning_layer, default=str), lead_id),
            )
        if sales_intervention_intelligence is not None:
            conn.execute(
                "UPDATE leads SET sales_intervention_intelligence_json = ? WHERE id = ?",
                (json.dumps(sales_intervention_intelligence, default=str), lead_id),
            )
        if objective_decision_layer is not None:
            conn.execute(
                "UPDATE leads SET objective_decision_layer_json = ? WHERE id = ?",
                (json.dumps(objective_decision_layer, default=str), lead_id),
            )
        conn.commit()
    except sqlite3.OperationalError:
        # Columns may not exist on old DBs
        pass
    finally:
        conn.close()


def insert_lead_embedding(lead_id: int, embedding: List[float], text_snapshot: str) -> None:
    """Store embedding vector and text snapshot for RAG (Phase 2)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO lead_embeddings (lead_id, embedding_json, text_snapshot, created_at)
               VALUES (?, ?, ?, ?)""",
            (lead_id, json.dumps(embedding), text_snapshot[:5000], now)
        )
        conn.commit()
    finally:
        conn.close()


def insert_lead_embedding_v2(
    lead_id: int,
    embedding: List[float],
    text: str,
    embedding_version: str,
    embedding_type: str,
) -> None:
    """Store embedding in lead_embeddings_v2 (versioned, typed)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO lead_embeddings_v2
               (lead_id, embedding_json, text_snapshot, embedding_version, embedding_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lead_id, json.dumps(embedding), text[:5000], embedding_version, embedding_type, now)
        )
        conn.commit()
    finally:
        conn.close()


def get_lead_embedding_v2(
    lead_id: int,
    embedding_version: str,
    embedding_type: str,
) -> Optional[Dict]:
    """Return stored embedding row or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT lead_id, embedding_json, text_snapshot, embedding_version, embedding_type, created_at
               FROM lead_embeddings_v2
               WHERE lead_id = ? AND embedding_version = ? AND embedding_type = ?""",
            (lead_id, embedding_version, embedding_type),
        ).fetchone()
        if not row:
            return None
        return {
            "lead_id": row["lead_id"],
            "embedding_json": row["embedding_json"],
            "embedding": json.loads(row["embedding_json"]) if row["embedding_json"] else [],
            "text_snapshot": row["text_snapshot"],
            "embedding_version": row["embedding_version"],
            "embedding_type": row["embedding_type"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def upsert_lead_outcome(
    lead_id: int,
    vertical: Optional[str] = None,
    agency_type: Optional[str] = None,
    contacted: Optional[bool] = None,
    proposal_sent: Optional[bool] = None,
    closed: Optional[bool] = None,
    close_value_usd: Optional[float] = None,
    service_sold: Optional[str] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Insert outcome row or update existing. Only provided fields are updated."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT lead_id FROM lead_outcomes WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if existing:
            updates = ["updated_at = ?"]
            params: List[Any] = [now]
            if vertical is not None:
                updates.append("vertical = ?")
                params.append(vertical)
            if agency_type is not None:
                updates.append("agency_type = ?")
                params.append(agency_type)
            if contacted is not None:
                updates.append("contacted = ?")
                params.append(1 if contacted else 0)
            if proposal_sent is not None:
                updates.append("proposal_sent = ?")
                params.append(1 if proposal_sent else 0)
            if closed is not None:
                updates.append("closed = ?")
                params.append(1 if closed else 0)
            if close_value_usd is not None:
                updates.append("close_value_usd = ?")
                params.append(close_value_usd)
            if service_sold is not None:
                updates.append("service_sold = ?")
                params.append(service_sold)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            params.append(lead_id)
            conn.execute(
                f"UPDATE lead_outcomes SET {', '.join(updates)} WHERE lead_id = ?",
                params,
            )
        else:
            _c = 1 if contacted else 0 if contacted is not None else 0
            _p = 1 if proposal_sent else 0 if proposal_sent is not None else 0
            _cl = 1 if closed else 0 if closed is not None else 0
            conn.execute(
                """INSERT INTO lead_outcomes
                   (lead_id, vertical, agency_type, contacted, proposal_sent, closed,
                    close_value_usd, service_sold, notes, status, updated_at, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (lead_id, vertical, agency_type, _c, _p, _cl, close_value_usd,
                 service_sold, notes, status or "new", now, now),
            )
        conn.commit()
    finally:
        conn.close()


def get_lead_outcome(lead_id: int) -> Optional[Dict]:
    """Return outcome row for lead or None."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT lead_id, vertical, agency_type, contacted, proposal_sent, closed,
                      close_value_usd, service_sold, notes, status, updated_at, created_at
               FROM lead_outcomes WHERE lead_id = ?""",
            (lead_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def get_similar_lead_ids_v2(
    embedding: List[float],
    limit: int = 25,
    embedding_version: str = "v1_structural",
    embedding_type: str = "objective_state",
    exclude_lead_id: Optional[int] = None,
) -> List[tuple]:
    """
    Return (lead_id, similarity, text_snapshot) from lead_embeddings_v2,
    ordered by cosine similarity. Excludes exclude_lead_id if provided.
    """
    conn = _get_conn()
    try:
        if exclude_lead_id is not None:
            rows = conn.execute(
                """SELECT lead_id, embedding_json, text_snapshot
                   FROM lead_embeddings_v2
                   WHERE embedding_version = ? AND embedding_type = ? AND lead_id != ?""",
                (embedding_version, embedding_type, exclude_lead_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT lead_id, embedding_json, text_snapshot
                   FROM lead_embeddings_v2
                   WHERE embedding_version = ? AND embedding_type = ?""",
                (embedding_version, embedding_type),
            ).fetchall()
        scored = []
        for row in rows:
            try:
                other = json.loads(row["embedding_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            sim = _cosine_similarity(embedding, other)
            scored.append((row["lead_id"], round(sim, 4), row["text_snapshot"] or ""))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]
    finally:
        conn.close()


def get_similar_outcome_stats(
    lead_embedding: List[float],
    limit: int = 25,
    embedding_version: str = "v1_structural",
    embedding_type: str = "objective_state",
) -> Dict:
    """
    Compute similarity-based outcome stats for similar leads.
    Returns n_similar, n_with_outcomes, close_rate, contacted_rate, proposal_rate, top_service_sold.
    If n_with_outcomes < 5, sets insufficient_outcomes: True.
    """
    similar = get_similar_lead_ids_v2(
        lead_embedding,
        limit=limit,
        embedding_version=embedding_version,
        embedding_type=embedding_type,
    )
    n_similar = len(similar)
    if n_similar == 0:
        return {"n_similar": 0, "n_with_outcomes": 0, "insufficient_outcomes": True}

    lead_ids = [x[0] for x in similar]
    placeholders = ",".join("?" * len(lead_ids))
    conn = _get_conn()
    try:
        rows = conn.execute(
            f"""SELECT lead_id, contacted, proposal_sent, closed, close_value_usd, service_sold
                FROM lead_outcomes WHERE lead_id IN ({placeholders})""",
            lead_ids,
        ).fetchall()
    finally:
        conn.close()

    n_with_outcomes = len(rows)
    if n_with_outcomes < 5:
        return {
            "n_similar": n_similar,
            "n_with_outcomes": n_with_outcomes,
            "insufficient_outcomes": True,
        }

    contacted_count = sum(1 for r in rows if r["contacted"])
    proposal_count = sum(1 for r in rows if r["proposal_sent"])
    closed_count = sum(1 for r in rows if r["closed"])
    services = [r["service_sold"] for r in rows if r["service_sold"]]
    top_service = None
    if services:
        top_service = Counter(services).most_common(1)[0][0]

    return {
        "n_similar": n_similar,
        "n_with_outcomes": n_with_outcomes,
        "contacted_rate": round(contacted_count / n_with_outcomes, 2) if n_with_outcomes else 0,
        "proposal_rate": round(proposal_count / n_with_outcomes, 2) if n_with_outcomes else 0,
        "close_rate": round(closed_count / n_with_outcomes, 2) if n_with_outcomes else 0,
        "top_service_sold": top_service,
        "insufficient_outcomes": False,
    }


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity; 0 if vectors invalid."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_similar_lead_ids(
    embedding: List[float],
    limit: int = 5,
    exclude_run_id: Optional[str] = None,
) -> List[tuple]:
    """
    Return (lead_id, similarity, text_snapshot) for leads with stored embeddings,
    ordered by cosine similarity (highest first). Excludes leads from exclude_run_id.
    """
    conn = _get_conn()
    try:
        if exclude_run_id:
            rows = conn.execute(
                """SELECT le.lead_id, le.embedding_json, le.text_snapshot
                   FROM lead_embeddings le
                   JOIN leads l ON l.id = le.lead_id
                   WHERE l.run_id != ?""",
                (exclude_run_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT lead_id, embedding_json, text_snapshot FROM lead_embeddings"
            ).fetchall()
        scored = []
        for row in rows:
            try:
                other = json.loads(row["embedding_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            sim = _cosine_similarity(embedding, other)
            scored.append((row["lead_id"], round(sim, 4), row["text_snapshot"] or ""))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]
    finally:
        conn.close()


def update_run_completed(run_id: str, leads_count: int, run_stats: Optional[Dict] = None) -> None:
    """Set run status to completed, leads_count, and optional run_stats (health/coverage metrics)."""
    conn = _get_conn()
    try:
        stats_json = json.dumps(run_stats) if run_stats else None
        conn.execute(
            "UPDATE runs SET status = ?, leads_count = ?, run_stats = ? WHERE id = ?",
            ("completed", leads_count, stats_json, run_id)
        )
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
        conn.execute(
            "UPDATE runs SET status = ?, leads_count = ? WHERE id = ?",
            ("completed", leads_count, run_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_run_failed(run_id: str) -> None:
    """Set run status to failed."""
    conn = _get_conn()
    try:
        conn.execute("UPDATE runs SET status = ? WHERE id = ?", ("failed", run_id))
        conn.commit()
    finally:
        conn.close()


def get_leads_with_context_deduped_by_place_id(limit_runs: int = 10) -> List[Dict]:
    """
    Get leads from latest completed runs, one per place_id (most recent run wins).
    For export when --dedupe-by-place-id is set.
    """
    runs = list_runs(limit=limit_runs, status="completed")
    by_place = {}
    for r in runs:
        for lead in get_leads_with_context_by_run(r["id"]):
            pid = lead.get("place_id")
            if pid and pid not in by_place:
                by_place[pid] = lead
    return list(by_place.values())


def get_latest_run_id() -> Optional[str]:
    """Return the most recent run id by created_at."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM runs WHERE status = 'completed' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_run(run_id: str) -> Optional[Dict]:
    """Get run by id."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "config": json.loads(row["config"]) if row["config"] else None,
            "leads_count": row["leads_count"],
            "status": row["status"],
            "run_stats": json.loads(row["run_stats"]) if (row.keys() and "run_stats" in row.keys() and row["run_stats"]) else None,
        }
    finally:
        conn.close()


def list_runs(limit: int = 50, status: Optional[str] = None) -> List[Dict]:
    """List runs, newest first. Optionally filter by status (e.g. 'completed', 'running', 'failed')."""
    conn = _get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM runs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "config": json.loads(row["config"]) if row["config"] else None,
                "leads_count": row["leads_count"],
                "status": row["status"],
                "run_stats": json.loads(row["run_stats"]) if (row.keys() and "run_stats" in row.keys() and row["run_stats"]) else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def delete_run(run_id: str) -> int:
    """
    Delete a run and all its leads, signals, context, and embeddings.
    Returns number of leads deleted.
    """
    conn = _get_conn()
    try:
        lead_ids = [row["id"] for row in conn.execute("SELECT id FROM leads WHERE run_id = ?", (run_id,)).fetchall()]
        n = len(lead_ids)
        if not lead_ids:
            conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            conn.commit()
            return 0
        placeholders = ",".join("?" * len(lead_ids))
        conn.execute(f"DELETE FROM decisions WHERE lead_id IN ({placeholders})", lead_ids)
        conn.execute(f"DELETE FROM lead_embeddings WHERE lead_id IN ({placeholders})", lead_ids)
        conn.execute(f"DELETE FROM context_dimensions WHERE lead_id IN ({placeholders})", lead_ids)
        conn.execute(f"DELETE FROM lead_signals WHERE lead_id IN ({placeholders})", lead_ids)
        conn.execute("DELETE FROM leads WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
        return n
    finally:
        conn.close()


def prune_runs(
    keep_last_n: Optional[int] = None,
    older_than_days: Optional[int] = None,
) -> int:
    """
    Delete runs by retention policy. Returns total number of leads deleted.
    - keep_last_n: keep only the N most recent completed runs (by created_at).
    - older_than_days: delete runs created more than this many days ago.
    At least one of keep_last_n or older_than_days must be set.
    """
    runs = list_runs(limit=10000)
    to_delete = set()
    if keep_last_n is not None and keep_last_n > 0:
        completed = [r for r in runs if r.get("status") == "completed"]
        completed.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        for r in completed[keep_last_n:]:
            to_delete.add(r["id"])
    if older_than_days is not None and older_than_days > 0:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        for r in runs:
            if r.get("created_at") and r["created_at"] < cutoff:
                to_delete.add(r["id"])
    total = 0
    for run_id in to_delete:
        total += delete_run(run_id)
    return total


def get_leads_with_context_by_run(run_id: str) -> List[Dict]:
    """
    Return all leads for a run with signals and context dimensions joined.
    Each item: lead fields + signals_json (parsed) + context fields (dimensions, reasoning, etc.)
    """
    conn = _get_conn()
    try:
        try:
            rows = conn.execute(
                """SELECT l.id AS lead_id, l.run_id, l.place_id, l.name, l.address, l.latitude, l.longitude,
                          ls.signals_json, cd.dimensions_json, cd.reasoning_summary, cd.priority_suggestion,
                          cd.primary_themes_json, cd.outreach_angles_json, cd.overall_confidence, cd.reasoning_source,
                          cd.no_opportunity, cd.no_opportunity_reason, cd.priority_derivation, cd.validation_warnings
                   FROM leads l
                   LEFT JOIN lead_signals ls ON ls.lead_id = l.id
                   LEFT JOIN context_dimensions cd ON cd.lead_id = l.id
                   WHERE l.run_id = ?
                   ORDER BY l.id""",
                (run_id,)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """SELECT l.id AS lead_id, l.run_id, l.place_id, l.name, l.address, l.latitude, l.longitude,
                          ls.signals_json, cd.dimensions_json, cd.reasoning_summary, cd.priority_suggestion,
                          cd.primary_themes_json, cd.outreach_angles_json, cd.overall_confidence, cd.reasoning_source
                   FROM leads l
                   LEFT JOIN lead_signals ls ON ls.lead_id = l.id
                   LEFT JOIN context_dimensions cd ON cd.lead_id = l.id
                   WHERE l.run_id = ?
                   ORDER BY l.id""",
                (run_id,)
            ).fetchall()
        out = []
        for row in rows:
            lead = {
                "lead_id": row["lead_id"],
                "run_id": row["run_id"],
                "place_id": row["place_id"],
                "name": row["name"],
                "address": row["address"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "raw_signals": json.loads(row["signals_json"]) if row["signals_json"] else {},
                "context_dimensions": json.loads(row["dimensions_json"]) if row["dimensions_json"] else [],
                "reasoning_summary": row["reasoning_summary"] or "",
                "priority_suggestion": row["priority_suggestion"],
                "primary_themes": json.loads(row["primary_themes_json"]) if row["primary_themes_json"] else [],
                "suggested_outreach_angles": json.loads(row["outreach_angles_json"]) if row["outreach_angles_json"] else [],
                "confidence": row["overall_confidence"],
                "reasoning_source": row["reasoning_source"],
            }
            if row.get("no_opportunity") is not None:
                lead["no_opportunity"] = bool(row["no_opportunity"])
                lead["no_opportunity_reason"] = row.get("no_opportunity_reason")
            if row.get("priority_derivation") is not None:
                lead["priority_derivation"] = row["priority_derivation"]
            if row.get("validation_warnings") is not None:
                try:
                    lead["validation_warnings"] = json.loads(row["validation_warnings"])
                except (TypeError, json.JSONDecodeError):
                    lead["validation_warnings"] = []
            out.append(lead)
        return out
    finally:
        conn.close()


def get_leads_with_decisions_by_run(run_id: str) -> List[Dict]:
    """
    Return all leads for a run with signals and decision joined.
    Each item: lead fields + raw_signals + verdict, confidence, reasoning, primary_risks, what_would_change, agency_type, prompt_version.
    """
    conn = _get_conn()
    try:
        try:
            rows = conn.execute(
                """SELECT l.id AS lead_id, l.run_id, l.place_id, l.name, l.address, l.latitude, l.longitude,
                          ls.signals_json,
                          d.agency_type, d.verdict, d.confidence, d.reasoning, d.primary_risks, d.what_would_change, d.prompt_version,
                          l.dentist_profile_v1_json, l.llm_reasoning_layer_json, l.sales_intervention_intelligence_json, l.objective_decision_layer_json
                   FROM leads l
                   LEFT JOIN lead_signals ls ON ls.lead_id = l.id
                   LEFT JOIN decisions d ON d.lead_id = l.id
                   WHERE l.run_id = ?
                   ORDER BY l.id""",
                (run_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """SELECT l.id AS lead_id, l.run_id, l.place_id, l.name, l.address, l.latitude, l.longitude,
                          ls.signals_json,
                          d.agency_type, d.verdict, d.confidence, d.reasoning, d.primary_risks, d.what_would_change, d.prompt_version
                   FROM leads l
                   LEFT JOIN lead_signals ls ON ls.lead_id = l.id
                   LEFT JOIN decisions d ON d.lead_id = l.id
                   WHERE l.run_id = ?
                   ORDER BY l.id""",
                (run_id,),
            ).fetchall()
        out = []
        for row in rows:
            lead = {
                "lead_id": row["lead_id"],
                "run_id": row["run_id"],
                "place_id": row["place_id"],
                "name": row["name"],
                "address": row["address"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "raw_signals": json.loads(row["signals_json"]) if row["signals_json"] else {},
                "verdict": row["verdict"] if row.get("verdict") else None,
                "confidence": row["confidence"] if row.get("confidence") is not None else None,
                "reasoning": row["reasoning"] or "",
                "primary_risks": json.loads(row["primary_risks"]) if row.get("primary_risks") else [],
                "what_would_change": json.loads(row["what_would_change"]) if row.get("what_would_change") else [],
                "agency_type": row["agency_type"] if row.get("agency_type") else None,
                "prompt_version": row["prompt_version"] if row.get("prompt_version") else None,
            }
            try:
                if row["dentist_profile_v1_json"] is not None:
                    lead["dentist_profile_v1"] = json.loads(row["dentist_profile_v1_json"])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
            try:
                if row["llm_reasoning_layer_json"] is not None:
                    lead["llm_reasoning_layer"] = json.loads(row["llm_reasoning_layer_json"])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
            try:
                if row["sales_intervention_intelligence_json"] is not None:
                    lead["sales_intervention_intelligence"] = json.loads(row["sales_intervention_intelligence_json"])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
            try:
                if row["objective_decision_layer_json"] is not None:
                    lead["objective_decision_layer"] = json.loads(row["objective_decision_layer_json"])
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
            out.append(lead)
        return out
    finally:
        conn.close()


def get_leads_with_decisions_deduped_by_place_id(limit_runs: int = 10) -> List[Dict]:
    """Get leads from latest completed runs with decisions, one per place_id (most recent run wins)."""
    runs = list_runs(limit=limit_runs, status="completed")
    by_place = {}
    for r in runs:
        for lead in get_leads_with_decisions_by_run(r["id"]):
            pid = lead.get("place_id")
            if pid and pid not in by_place:
                by_place[pid] = lead
    return list(by_place.values())

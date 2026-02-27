"""
Background job worker — runs in a daemon thread.

Polls for pending jobs and executes them sequentially.
For production, replace with Celery + Redis.
"""

import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from pipeline.db import (
    get_ask_lightweight_cache,
    get_ask_places_cache,
    get_prospect_list,
    list_members_for_list,
    list_territory_prospects,
    get_pending_jobs,
    link_territory_prospect_diagnostic,
    save_diagnostic,
    upsert_ask_lightweight_cache,
    upsert_ask_places_cache,
    upsert_list_member,
    update_job_status,
    update_territory_scan_status,
)
from backend.services.enrichment_service import run_diagnostic
from backend.services.npl_service import (
    criterion_cache_key,
    matches_tier1_criteria,
    needs_lightweight_check,
    run_lightweight_service_page_check,
)
from backend.services.territory_service import (
    _build_tier1_rows,
    _fetch_territory_candidates,
    run_list_rescan_job,
    run_territory_scan_job,
)

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

POLL_INTERVAL = 2  # seconds
ASK_PLACES_CACHE_TTL_SECONDS = 15 * 60
ASK_LIGHT_CACHE_TTL_SECONDS = 10 * 60


def _is_fresh_iso(updated_at: str | None, ttl_seconds: int) -> bool:
    if not updated_at:
        return False
    try:
        ts = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() <= ttl_seconds
    except Exception:
        return False


def _run_deep_brief_job(job: dict) -> dict:
    job_id = job["id"]
    user_id = job.get("user_id", 1)
    inp = job.get("input", {}) or {}
    job_type = str(job.get("type") or "")
    max_prospects = int(inp.get("max_prospects") or 25)
    max_prospects = max(1, min(max_prospects, 25))
    concurrency = int(inp.get("concurrency") or 3)
    concurrency = max(1, min(concurrency, 5))

    tasks: list[dict] = []
    if job_type == "territory_deep_scan":
        scan_id = str(inp.get("scan_id") or "")
        rows = list_territory_prospects(scan_id, user_id) if scan_id else []
        for r in rows:
            if r.get("full_brief_ready"):
                continue
            tasks.append(
                {
                    "kind": "territory",
                    "prospect_id": int(r["id"]),
                    "place_id": r.get("place_id"),
                    "business_name": r.get("business_name"),
                    "city": r.get("city"),
                    "state": r.get("state"),
                    "website": r.get("website"),
                }
            )
    elif job_type == "list_deep_briefs":
        list_id = int(inp.get("list_id") or 0)
        lst = get_prospect_list(list_id, user_id) if list_id else None
        rows = list_members_for_list(list_id) if lst else []
        for r in rows:
            resp = r.get("response") or {}
            if isinstance(resp, dict) and resp.get("brief"):
                continue
            tasks.append(
                {
                    "kind": "list",
                    "list_id": list_id,
                    "place_id": r.get("place_id"),
                    "business_name": (resp.get("business_name") or r.get("business_name")),
                    "city": (resp.get("city") or r.get("city")),
                    "state": (resp.get("state") or r.get("state")),
                }
            )
    else:
        return {"processed": 0, "created": 0, "failed": 0, "total": 0}

    tasks = [t for t in tasks if t.get("business_name") and t.get("city")][:max_prospects]
    total = len(tasks)
    if total == 0:
        return {"processed": 0, "created": 0, "failed": 0, "total": 0, "message": "No prospects required deep brief build."}

    def _run_one(t: dict) -> dict:
        result = run_diagnostic(
            business_name=str(t["business_name"]),
            city=str(t["city"]),
            state=str(t.get("state") or ""),
            website=t.get("website"),
        )
        diag_id = save_diagnostic(
            user_id=user_id,
            job_id=job_id,
            place_id=result.get("place_id") or t.get("place_id"),
            business_name=result.get("business_name") or str(t["business_name"]),
            city=result.get("city") or str(t["city"]),
            brief=result.get("brief"),
            response=result,
            state=result.get("state") or t.get("state"),
        )
        if t["kind"] == "territory":
            link_territory_prospect_diagnostic(int(t["prospect_id"]), int(diag_id), full_brief_ready=True)
        elif t["kind"] == "list":
            upsert_list_member(
                list_id=int(t["list_id"]),
                diagnostic_id=int(diag_id),
                place_id=t.get("place_id"),
                business_name=result.get("business_name") or str(t["business_name"]),
                city=result.get("city") or str(t["city"]),
                state=result.get("state") or t.get("state"),
            )
        return {"diagnostic_id": int(diag_id), "place_id": t.get("place_id")}

    processed = 0
    created = 0
    failed = 0
    diag_ids: list[int] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_map = {pool.submit(_run_one, t): t for t in tasks}
        for fut in as_completed(future_map):
            processed += 1
            try:
                one = fut.result()
                created += 1
                if one.get("diagnostic_id"):
                    diag_ids.append(int(one["diagnostic_id"]))
            except Exception:
                failed += 1
                logger.exception("Deep brief item failed")

            update_job_status(
                job_id,
                "running",
                result={
                    "phase": "deep_brief_build",
                    "processed": processed,
                    "created": created,
                    "failed": failed,
                    "total": total,
                },
            )

    return {
        "phase": "deep_brief_build",
        "processed": processed,
        "created": created,
        "failed": failed,
        "total": total,
        "diagnostic_ids": diag_ids,
        "message": f"Deep brief build complete: {created}/{total} created ({failed} failed).",
    }


def _build_npl_payload(row: dict, diagnostic: dict | None) -> dict:
    resp = (diagnostic or {}).get("response") if isinstance(diagnostic, dict) else None
    return {
        "prospect_id": row.get("id"),
        "diagnostic_id": row.get("diagnostic_id"),
        "place_id": row.get("place_id"),
        "business_name": row.get("business_name"),
        "city": row.get("city"),
        "state": row.get("state"),
        "website": row.get("website"),
        "rating": row.get("rating"),
        "user_ratings_total": row.get("user_ratings_total"),
        "rank": row.get("rank"),
        "rank_score": row.get("rank_key"),
        "full_brief_ready": bool(row.get("full_brief_ready")),
        "opportunity_profile": (resp or {}).get("opportunity_profile"),
        "primary_leverage": (resp or {}).get("primary_leverage"),
        "constraint": (resp or {}).get("constraint"),
    }


def _run_npl_find_job(job: dict) -> dict:
    job_id = job["id"]
    inp = job.get("input", {}) or {}
    intent = inp.get("intent") or {}
    accuracy_mode = str(inp.get("accuracy_mode") or "verified").strip().lower()
    if accuracy_mode not in {"fast", "verified"}:
        accuracy_mode = "verified"
    city = str(intent.get("city") or "").strip()
    state = intent.get("state") or None
    vertical = str(intent.get("vertical") or "dentist").strip()
    limit = int(intent.get("limit") or 10)
    limit = max(1, min(limit, 25))
    criteria = intent.get("criteria") or []
    missing_service_criteria = [c for c in criteria if c.get("type") == "missing_service_page_light"]
    requires_light = bool(intent.get("requires_lightweight")) or needs_lightweight_check(criteria)
    requires_verified = accuracy_mode == "verified" and bool(missing_service_criteria)
    scored_cap = min(max(limit * 2, limit), 50)

    update_job_status(
        job_id,
        "running",
        result={
            "phase": "candidate_fetch",
            "intent": intent,
            "accuracy_mode": accuracy_mode,
            "criteria": criteria,
            "progress": {"candidates_found": 0, "scored": 0, "list_count": 0},
            "partial_results": [],
        },
    )

    places_cache_key = f"{city.lower()}|{str(state or '').upper()}|{vertical.lower()}|{scored_cap}"
    candidates: list[dict] = []
    candidates_cached = False
    cached_places = get_ask_places_cache(places_cache_key)
    if cached_places and _is_fresh_iso(cached_places.get("updated_at"), ASK_PLACES_CACHE_TTL_SECONDS):
        payload = cached_places.get("data") or {}
        rows_cached = payload.get("candidates") if isinstance(payload, dict) else None
        if isinstance(rows_cached, list):
            candidates = rows_cached
            candidates_cached = True

    if not candidates:
        def _candidate_progress_cb(queries_done: int, queries_total: int, raw_collected: int) -> None:
            update_job_status(
                job_id,
                "running",
                result={
                    "phase": "candidate_fetch",
                    "intent": intent,
                    "accuracy_mode": accuracy_mode,
                    "criteria": criteria,
                    "progress": {
                        "candidate_queries_done": queries_done,
                        "candidate_queries_total": queries_total,
                        "raw_candidates_collected": raw_collected,
                        "candidates_found": 0,
                        "scored": 0,
                        "list_count": 0,
                    },
                    "partial_results": [],
                },
            )

        candidates = _fetch_territory_candidates(
            city=city,
            state=state,
            vertical=vertical,
            limit=scored_cap,
            progress_cb=_candidate_progress_cb,
        )
        upsert_ask_places_cache(places_cache_key, {"candidates": candidates})

    candidates = candidates[:scored_cap]
    total_candidates = len(candidates)

    update_job_status(
        job_id,
        "running",
        result={
            "phase": "details_scoring",
            "intent": intent,
            "accuracy_mode": accuracy_mode,
            "criteria": criteria,
            "progress": {
                "candidates_found": total_candidates,
                "scored": 0,
                "list_count": 0,
                "details_cache_hit": candidates_cached,
            },
            "partial_results": [],
        },
    )

    score_progress = {"processed": 0, "failed": 0}

    def _score_progress_cb(processed: int, failed_count: int) -> None:
        score_progress["processed"] = processed
        score_progress["failed"] = failed_count

    rows, failed_count = _build_tier1_rows(
        candidates,
        city=city,
        state=state,
        filters={},
        progress_cb=_score_progress_cb,
    )
    score_progress["processed"] = len(candidates)
    score_progress["failed"] = failed_count

    ranked_rows = rows[:]
    for idx, row in enumerate(ranked_rows, start=1):
        row["rank"] = idx

    filtered_rows: list[dict] = []
    partial_payload: list[dict] = []

    if not requires_light:
        for row in ranked_rows:
            if matches_tier1_criteria(criteria, row):
                filtered_rows.append(row)
                payload = _build_npl_payload(row, diagnostic=None)
                partial_payload.append(payload)
                if len(partial_payload) >= limit:
                    break
            if len(partial_payload) and len(partial_payload) % 5 == 0:
                update_job_status(
                    job_id,
                    "running",
                    result={
                        "phase": "filtering",
                        "intent": intent,
                        "accuracy_mode": accuracy_mode,
                        "criteria": criteria,
                        "progress": {
                            "candidates_found": total_candidates,
                            "scored": score_progress["processed"],
                            "failed": score_progress["failed"],
                            "list_count": len(partial_payload),
                        },
                        "partial_results": partial_payload[:],
                    },
                )
    else:
        checked = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            future_map = {}
            for row in ranked_rows:
                if not matches_tier1_criteria([c for c in criteria if c.get("type") != "missing_service_page_light"], row):
                    continue
                place_id = str(row.get("place_id") or "")
                if not place_id:
                    continue
                criterion = missing_service_criteria[0] if missing_service_criteria else {}
                ckey = criterion_cache_key(criterion)
                cached = get_ask_lightweight_cache(place_id, ckey)
                if cached and _is_fresh_iso(cached.get("updated_at"), ASK_LIGHT_CACHE_TTL_SECONDS):
                    lw = cached.get("result") or {}
                    checked += 1
                    if lw.get("matches"):
                        filtered_rows.append(row)
                        partial_payload.append(_build_npl_payload(row, diagnostic=None))
                    continue
                future = pool.submit(run_lightweight_service_page_check, row.get("website"), criterion, 5)
                future_map[future] = (row, ckey)

            for fut in as_completed(future_map):
                row, ckey = future_map[fut]
                checked += 1
                try:
                    lw = fut.result()
                except Exception:
                    lw = {"matches": False}
                place_id = str(row.get("place_id") or "")
                if place_id:
                    upsert_ask_lightweight_cache(place_id, ckey, lw)
                if lw.get("matches"):
                    filtered_rows.append(row)
                    partial_payload.append(_build_npl_payload(row, diagnostic=None))
                if checked % 5 == 0 or len(partial_payload) == limit:
                    update_job_status(
                        job_id,
                        "running",
                        result={
                            "phase": "lightweight_check",
                            "intent": intent,
                            "accuracy_mode": accuracy_mode,
                            "criteria": criteria,
                            "progress": {
                                "candidates_found": total_candidates,
                                "scored": score_progress["processed"],
                                "lightweight_checked": checked,
                                "failed": score_progress["failed"],
                                "list_count": min(len(partial_payload), limit),
                            },
                            "partial_results": partial_payload[:limit],
                        },
                    )
                if len(partial_payload) >= limit:
                    break

    verified_progress: dict[str, int] = {"processed": 0, "failed": 0}
    verified_payload: list[dict] = []

    if requires_verified:
        candidates_for_verify = sorted(
            filtered_rows,
            key=lambda x: float(x.get("rank_key") or 0),
            reverse=True,
        )[: min(max(limit * 3, limit), 25)]

        def _verify_row(row: dict) -> dict:
            result = run_diagnostic(
                business_name=str(row.get("business_name") or ""),
                city=str(row.get("city") or ""),
                state=str(row.get("state") or ""),
                website=row.get("website"),
            )
            verified_missing = [
                str(s).strip().lower()
                for s in (result.get("service_intelligence") or {}).get("missing_services", [])
            ]
            must_have_missing = [str(c.get("service") or "").strip().lower() for c in missing_service_criteria]
            verified_match = all(any(ms in vm for vm in verified_missing) for ms in must_have_missing if ms)
            if not verified_match:
                return {"verified_match": False}
            out = _build_npl_payload(
                row,
                diagnostic={"response": result},
            )
            return {"verified_match": True, "payload": out}

        update_job_status(
            job_id,
            "running",
            result={
                "phase": "verified_diagnostic",
                "intent": intent,
                "accuracy_mode": accuracy_mode,
                "criteria": criteria,
                "progress": {
                    "candidates_found": total_candidates,
                    "scored": score_progress["processed"],
                    "verifying": len(candidates_for_verify),
                    "processed": 0,
                    "failed": 0,
                    "list_count": 0,
                },
                "partial_results": [],
            },
        )

        with ThreadPoolExecutor(max_workers=3) as pool:
            future_map = {pool.submit(_verify_row, r): r for r in candidates_for_verify}
            for fut in as_completed(future_map):
                verified_progress["processed"] += 1
                try:
                    one = fut.result()
                    if one.get("verified_match") and one.get("payload"):
                        verified_payload.append(one["payload"])
                except Exception:
                    verified_progress["failed"] += 1
                    logger.exception("Verified ask row failed")

                update_job_status(
                    job_id,
                    "running",
                    result={
                        "phase": "verified_diagnostic",
                        "intent": intent,
                        "accuracy_mode": accuracy_mode,
                        "criteria": criteria,
                        "progress": {
                            "candidates_found": total_candidates,
                            "scored": score_progress["processed"],
                            "verifying": len(candidates_for_verify),
                            "processed": verified_progress["processed"],
                            "failed": verified_progress["failed"],
                            "list_count": min(len(verified_payload), limit),
                        },
                        "partial_results": verified_payload[:limit],
                    },
                )
                if len(verified_payload) >= limit:
                    break

        verified_payload.sort(key=lambda x: float(x.get("rank_score") or 0), reverse=True)
        prospects = verified_payload[:limit]
        total_matches = len(verified_payload)
    else:
        filtered_rows.sort(key=lambda x: float(x.get("rank_key") or 0), reverse=True)
        top_rows = filtered_rows[:limit]
        prospects = [_build_npl_payload(r, diagnostic=None) for r in top_rows]
        total_matches = len(filtered_rows)

    return {
        "phase": "completed",
        "intent": intent,
        "accuracy_mode": accuracy_mode,
        "criteria": criteria,
        "requires_lightweight": requires_light,
        "requires_verified": requires_verified,
        "total_matches": total_matches,
        "prospects": prospects,
        "progress": {
            "candidates_found": total_candidates,
            "scored": score_progress["processed"],
            "failed": score_progress["failed"],
            "verified_processed": verified_progress["processed"] if requires_verified else 0,
            "list_count": len(prospects),
        },
    }


def _process_job(job: dict) -> None:
    job_id = job["id"]
    user_id = job.get("user_id", 1)
    job_type = job.get("type", "diagnostic")
    inp = job.get("input", {})

    logger.info("Processing %s job %s for user %s", job_type, job_id, user_id)
    update_job_status(job_id, "running")

    try:
        if job_type == "territory_scan":
            result = run_territory_scan_job(job)
            update_job_status(job_id, "completed", result=result)
            logger.info("Territory job %s completed", job_id)
            return

        if job_type == "list_rescan":
            result = run_list_rescan_job(job)
            update_job_status(job_id, "completed", result=result)
            logger.info("List rescan job %s completed", job_id)
            return

        if job_type in {"territory_deep_scan", "list_deep_briefs"}:
            result = _run_deep_brief_job(job)
            update_job_status(job_id, "completed", result=result)
            logger.info("Deep brief job %s completed", job_id)
            return

        if job_type == "npl_find":
            result = _run_npl_find_job(job)
            update_job_status(job_id, "completed", result=result)
            logger.info("NPL job %s completed", job_id)
            return

        result = run_diagnostic(
            business_name=inp["business_name"],
            city=inp["city"],
            state=inp.get("state"),
            website=inp.get("website"),
        )

        diag_id = save_diagnostic(
            user_id=user_id,
            job_id=job_id,
            place_id=result.get("place_id"),
            business_name=result.get("business_name", inp["business_name"]),
            city=result.get("city", inp["city"]),
            brief=result.get("brief"),
            response=result,
            state=result.get("state") or inp.get("state"),
        )

        result["diagnostic_id"] = diag_id
        if inp.get("prospect_id"):
            try:
                link_territory_prospect_diagnostic(int(inp["prospect_id"]), diag_id, full_brief_ready=True)
            except Exception:
                logger.exception("Failed linking prospect %s to diagnostic %s", inp.get("prospect_id"), diag_id)
        update_job_status(job_id, "completed", result=result)
        logger.info("Job %s completed → diagnostic %s", job_id, diag_id)

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Job %s failed: %s\n%s", job_id, exc, tb)
        if job_type in {"territory_scan", "list_rescan"}:
            scan_id = inp.get("scan_id") or job_id
            try:
                update_territory_scan_status(scan_id, "failed", error=str(exc))
            except Exception:
                logger.exception("Failed to mark scan %s as failed", scan_id)
        update_job_status(job_id, "failed", error=str(exc))


def _worker_loop() -> None:
    logger.info("Job worker started")
    while not _stop_event.is_set():
        try:
            jobs = get_pending_jobs(limit=1)
            if jobs:
                _process_job(jobs[0])
            else:
                _stop_event.wait(timeout=POLL_INTERVAL)
        except Exception:
            logger.exception("Worker loop error")
            _stop_event.wait(timeout=POLL_INTERVAL)
    logger.info("Job worker stopped")


def start_worker() -> None:
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="job-worker")
    _worker_thread.start()


def stop_worker() -> None:
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5)

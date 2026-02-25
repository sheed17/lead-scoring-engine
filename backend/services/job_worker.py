"""
Background job worker — runs in a daemon thread.

Polls for pending jobs and executes them sequentially.
For production, replace with Celery + Redis.
"""

import logging
import threading
import time
import traceback

from pipeline.db import get_pending_jobs, update_job_status, save_diagnostic
from backend.services.enrichment_service import run_diagnostic

logger = logging.getLogger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

POLL_INTERVAL = 2  # seconds


def _process_job(job: dict) -> None:
    job_id = job["id"]
    user_id = job.get("user_id", 1)
    inp = job.get("input", {})

    logger.info("Processing job %s for user %s", job_id, user_id)
    update_job_status(job_id, "running")

    try:
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
        update_job_status(job_id, "completed", result=result)
        logger.info("Job %s completed → diagnostic %s", job_id, diag_id)

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Job %s failed: %s\n%s", job_id, exc, tb)
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

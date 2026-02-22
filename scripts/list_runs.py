#!/usr/bin/env python3
"""
List enrichment runs and optionally prune by retention policy.

Usage:
    python scripts/list_runs.py
    python scripts/list_runs.py --limit 20
    python scripts/list_runs.py --status completed
    python scripts/list_runs.py --prune-keep 5          # keep last 5 completed runs
    python scripts/list_runs.py --prune-older-than 30   # delete runs older than 30 days
    python scripts/list_runs.py --prune-keep 3 --dry-run # show what would be deleted
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.db import list_runs, delete_run, prune_runs, get_db_path


def main():
    parser = argparse.ArgumentParser(description="List or prune enrichment runs")
    parser.add_argument("--limit", type=int, default=20, help="Max runs to list (default 20)")
    parser.add_argument("--status", choices=["completed", "running", "failed"], help="Filter by status")
    parser.add_argument("--prune-keep", type=int, metavar="N", help="Prune: keep only last N completed runs")
    parser.add_argument("--prune-older-than", type=int, metavar="DAYS", help="Prune: delete runs older than N days")
    parser.add_argument("--dry-run", action="store_true", help="With prune: only show what would be deleted")
    args = parser.parse_args()

    if args.prune_keep is not None or args.prune_older_than is not None:
        if args.dry_run:
            runs = list_runs(limit=1000)
            to_delete_ids = set()
            if args.prune_keep is not None and args.prune_keep > 0:
                completed = [r for r in runs if r.get("status") == "completed"]
                completed.sort(key=lambda r: r.get("created_at") or "", reverse=True)
                for r in completed[args.prune_keep:]:
                    to_delete_ids.add(r["id"])
            if args.prune_older_than is not None and args.prune_older_than > 0:
                from datetime import datetime, timezone, timedelta
                cutoff = (datetime.now(timezone.utc) - timedelta(days=args.prune_older_than)).isoformat()
                for r in runs:
                    if r.get("created_at") and r["created_at"] < cutoff:
                        to_delete_ids.add(r["id"])
            to_delete = [r for r in runs if r["id"] in to_delete_ids]
            if not to_delete:
                print("No runs would be deleted.")
            else:
                print(f"Would delete {len(to_delete)} run(s):")
                for r in to_delete[:20]:
                    print(f"  {r['id'][:8]}... {r['created_at']} leads={r.get('leads_count')} {r.get('status')}")
                if len(to_delete) > 20:
                    print(f"  ... and {len(to_delete) - 20} more")
        else:
            n = prune_runs(keep_last_n=args.prune_keep, older_than_days=args.prune_older_than)
            print(f"Pruned {n} lead(s) from old runs.")
        return

    db_path = get_db_path()
    if not os.path.isfile(db_path):
        print(f"No database at {db_path}. Run enrichment first.")
        return

    runs = list_runs(limit=args.limit, status=args.status)
    if not runs:
        print("No runs found.")
        return

    print(f"Runs (db: {db_path})\n")
    for r in runs:
        stats = r.get("run_stats") or {}
        coverage = stats.get("signal_coverage_pct")
        extra = f"  coverage={coverage}%" if coverage is not None else ""
        print(f"  {r['id'][:8]}...  {r['created_at']}  leads={r.get('leads_count') or 0}  {r.get('status')}{extra}")


if __name__ == "__main__":
    main()

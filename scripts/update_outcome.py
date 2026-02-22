#!/usr/bin/env python3
"""
Update or create a lead outcome (outcome loop: contacted, proposal_sent, closed, etc.).

Usage:
    python scripts/update_outcome.py --lead-id 123 --status won --closed 1 --value 7500 --service implants --notes "Closed after audit call"
    python scripts/update_outcome.py --lead-id 456 --status contacted --contacted 1
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

from pipeline.db import init_db, upsert_lead_outcome


def main():
    parser = argparse.ArgumentParser(description="Update lead outcome for outcome loop")
    parser.add_argument("--lead-id", type=int, required=True, help="Lead ID (from leads table)")
    parser.add_argument("--vertical", type=str, default=None, help="Vertical (e.g. dentist)")
    parser.add_argument("--agency-type", type=str, default=None, help="Agency type (seo, marketing)")
    parser.add_argument("--status", type=str, default=None, help="Status: new | contacted | qualified | won | lost")
    parser.add_argument("--contacted", type=int, default=None, choices=(0, 1), help="1 if contacted")
    parser.add_argument("--proposal-sent", type=int, default=None, choices=(0, 1), help="1 if proposal sent")
    parser.add_argument("--closed", type=int, default=None, choices=(0, 1), help="1 if closed")
    parser.add_argument("--value", type=float, default=None, dest="close_value_usd", help="Close value in USD")
    parser.add_argument("--service", type=str, default=None, dest="service_sold", help="Service sold (e.g. implants)")
    parser.add_argument("--notes", type=str, default=None, help="Notes")
    args = parser.parse_args()

    init_db()
    upsert_lead_outcome(
        lead_id=args.lead_id,
        vertical=args.vertical,
        agency_type=args.agency_type,
        contacted=bool(args.contacted) if args.contacted is not None else None,
        proposal_sent=bool(args.proposal_sent) if args.proposal_sent is not None else None,
        closed=bool(args.closed) if args.closed is not None else None,
        close_value_usd=args.close_value_usd,
        service_sold=args.service_sold,
        status=args.status,
        notes=args.notes,
    )
    print(f"Updated outcome for lead_id={args.lead_id}")


if __name__ == "__main__":
    main()

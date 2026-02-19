#!/usr/bin/env python3
"""
Render Revenue Intelligence Brief HTML from pipeline output JSON.

Usage:
  python scripts/render_brief.py [path/to/results.json] [lead_index]
  python scripts/render_brief.py output/test_small_results_dentist.json 0
  python scripts/render_brief.py output/test_small_results_dentist.json  # all leads
"""

import json
import sys
from pathlib import Path

# Import renderer only (avoid pulling in pipeline deps like requests)
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
# Load module by path so pipeline.__init__ is not run
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "revenue_brief_renderer", _root / "pipeline" / "revenue_brief_renderer.py"
)
_renderer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_renderer)
build_revenue_brief_view_model = _renderer.build_revenue_brief_view_model
render_revenue_brief_html = _renderer.render_revenue_brief_html


def main() -> None:
    data_path = Path(__file__).resolve().parent.parent / "output" / "test_small_results_dentist.json"
    lead_index = None
    if len(sys.argv) > 1:
        data_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        lead_index = int(sys.argv[2])

    text = data_path.read_text(encoding="utf-8")
    data = json.loads(text)
    leads = data.get("leads") or []
    if not leads:
        print("No leads in JSON.")
        sys.exit(1)

    indices = [lead_index] if lead_index is not None else list(range(len(leads)))
    out_dir = data_path.parent / "briefs"
    out_dir.mkdir(exist_ok=True)

    for i in indices:
        if i < 0 or i >= len(leads):
            continue
        lead = leads[i]
        name = (lead.get("name") or f"lead_{i}").replace("/", "-")[:60]
        html = render_revenue_brief_html(lead, title=f"Revenue Intelligence Brief — {name}")
        out_path = out_dir / f"brief_{i}_{name.replace(' ', '_')}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()

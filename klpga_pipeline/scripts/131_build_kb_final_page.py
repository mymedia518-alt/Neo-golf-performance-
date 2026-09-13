#!/usr/bin/env python3
"""Build the real public FINAL page for KB 2026090003 from the V3
operator-supplied official-screenshot evidence (positions 1-39) and
write it to docs/tournaments/2026/2026090003/final/index.html.

Never claims a complete 70-player field -- see final_real_page.py's
own scope_label. Does not touch the immutable R3 forecast snapshot or
final_truth.py's official write-once slot."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.final_partial_evidence_validator import biggest_movers, run_extended_comparison  # noqa: E402
from klpga.neo_win.final_real_page import render_final_real_page  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402


def main() -> None:
    context = load_tournament_context("2026090003")
    evidence_path = ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    if any(r["review_required"] or r["player_id"] is None for r in evidence["confirmed_records"]):
        raise SystemExit("refusing to build FINAL page: evidence still has review_required/unmatched rows")

    comparison = run_extended_comparison(context, evidence)
    overestimated, underestimated = biggest_movers(comparison, n=5)

    html = render_final_real_page(
        tournament_name=context.tournament_name,
        game_code=context.game_code,
        date_range=context.display_date_range,
        evidence=evidence,
        comparison=comparison,
        overestimated=overestimated,
        underestimated=underestimated,
    )

    out_path = REPO_ROOT / "docs" / context.url_base.strip("/") / "final" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({"written": str(out_path), "positions_confirmed_gapless_through": evidence["positions_confirmed_gapless_through"]}))


if __name__ == "__main__":
    main()

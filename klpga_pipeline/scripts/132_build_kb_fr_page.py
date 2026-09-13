#!/usr/bin/env python3
"""KB금융 골든라이프 챔피언십 FR BUILD: build the real public FR page
(pure results, zero model analysis) from the same V3
operator-supplied-official-screenshot evidence FINAL already uses, and
write it to docs/tournaments/2026/2026090003/fr/index.html.

Hard-stops (never fabricates, never silently continues) unless ALL of:
  - exactly 39 confirmed records, positions_confirmed_gapless_through == 39
  - review_required_count == 0, unmatched_count == 0 (per the evidence
    file's own summary fields)
  - every confirmed record: player_id is not None, review_required is False
  - every confirmed record's own round arithmetic is internally
    consistent: r1+r2+r3+r4_strokes == final_total_strokes, and
    final_total_strokes - (par_per_round * 4) == final_to_par

Also verifies (read-only, never modifies) that the frozen POST-R3
forecast artifact remains byte-identical to its known-good fingerprint
-- FR construction must never recompute or touch any R3 forecast."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.fr_real_page import render_fr_real_page  # noqa: E402
from klpga.tournament_context import load_tournament_context  # noqa: E402

EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
EXPECTED_CONFIRMED_COUNT = 39


def _verify_r3_freeze_fingerprint() -> None:
    path = ROOT / "content" / "website_v2" / "2026090003_POST_R3_FINAL_FORECAST.json"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != EXPECTED_R3_FORECAST_SHA256:
        raise SystemExit(
            f"refusing to build FR page: frozen POST-R3 forecast fingerprint changed "
            f"(expected {EXPECTED_R3_FORECAST_SHA256}, got {actual}) -- FR must never "
            "recompute or modify the R3 forecast"
        )


def _verify_evidence_coverage(evidence: dict) -> None:
    records = evidence.get("confirmed_records") or []
    problems = []
    if len(records) != EXPECTED_CONFIRMED_COUNT:
        problems.append(f"expected {EXPECTED_CONFIRMED_COUNT} confirmed records, found {len(records)}")
    if evidence.get("positions_confirmed_gapless_through") != EXPECTED_CONFIRMED_COUNT:
        problems.append(f"positions_confirmed_gapless_through != {EXPECTED_CONFIRMED_COUNT}")
    if evidence.get("review_required_count") != 0:
        problems.append("review_required_count != 0")
    if evidence.get("unmatched_count") != 0:
        problems.append("unmatched_count != 0")

    par_per_round = evidence.get("par_per_round")
    if par_per_round is None:
        problems.append("evidence has no par_per_round -- cannot verify round arithmetic")

    for r in records:
        label = f"{r.get('final_rank')} {r.get('player_name')}"
        if r.get("player_id") is None:
            problems.append(f"{label}: player_id is None (unmatched identity)")
        if r.get("review_required"):
            problems.append(f"{label}: review_required is True")
        rounds = [r.get("r1_strokes"), r.get("r2_strokes"), r.get("r3_strokes"), r.get("r4_strokes")]
        if any(v is None for v in rounds):
            problems.append(f"{label}: missing round stroke value(s) {rounds} -- cannot render without fabricating")
            continue
        total = sum(float(v) for v in rounds)
        if abs(total - r["final_total_strokes"]) > 1e-6:
            problems.append(f"{label}: R1-FR sum {total} != final_total_strokes {r['final_total_strokes']}")
        if par_per_round is not None:
            expected_to_par = r["final_total_strokes"] - par_per_round * 4
            if expected_to_par != r["final_to_par"]:
                problems.append(f"{label}: expected to-par {expected_to_par} != evidence final_to_par {r['final_to_par']}")

    if problems:
        raise SystemExit("refusing to build FR page: evidence coverage/arithmetic problems:\n" + "\n".join(f"  - {p}" for p in problems))


def main() -> None:
    _verify_r3_freeze_fingerprint()

    context = load_tournament_context("2026090003")
    evidence_path = ROOT / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    _verify_evidence_coverage(evidence)

    html = render_fr_real_page(
        tournament_name=context.tournament_name,
        game_code=context.game_code,
        date_range=context.display_date_range,
        evidence=evidence,
    )

    out_path = REPO_ROOT / "docs" / context.url_base.strip("/") / "fr" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({
        "written": str(out_path),
        "confirmed_records": len(evidence["confirmed_records"]),
        "positions_confirmed_gapless_through": evidence["positions_confirmed_gapless_through"],
        "r3_forecast_fingerprint_verified": True,
    }))


if __name__ == "__main__":
    main()

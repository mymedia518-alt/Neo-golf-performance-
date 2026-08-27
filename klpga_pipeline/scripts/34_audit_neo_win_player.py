"""NEO GOLF BETA #001 — player diagnostic audit. Read-only against an
ALREADY-FROZEN neo_win_predictions/ snapshot and the real DB — never
reruns inference and calls it equivalent, never modifies the frozen
artifact, never changes any probability. See src/klpga/neo_win/audit.py
for the full method (identity trace, 2026 season reconstruction from
DB-stored results only, exact frozen-feature reconstruction, refit-
and-verify contribution decomposition, official-metric exclusion
audit, recent-form audit, full TOP10 sanity sweep, rule-based verdict).

Usage (defaults match the Seo Gyo-rim vs Park Hyun-kyung BETA #001 audit):
    python scripts/34_audit_neo_win_player.py --db data/klpga.sqlite \\
        --predictions-dir neo_win_predictions --prediction-id 001 --game-code 2026080001

Fails loudly (not silently) if the named frozen snapshot does not
exist yet — this audit only ever inspects an ALREADY-frozen prediction.
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.archive import archive_paths, read_neo_win_snapshot  # noqa: E402
from klpga.neo_win.audit import (  # noqa: E402
    audit_2026_season,
    audit_official_metrics_for_player,
    audit_player_identity,
    audit_recent_form,
    audit_top10,
    check_win_feature_representation,
    classify_verdict,
    decompose_contribution,
    frozen_player_features,
    largest_differences,
    recompute_and_verify_fit,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "beta001"


def _pct(p) -> str:
    return "—" if p is None else f"{p * 100:.3f}%"


def _resolve_player(conn, identity: dict, snapshot, player_label: str):
    """A player audited by NAME may have 0 or >1 player_master ids —
    for the frozen-snapshot lookup we need the SPECIFIC player_code the
    snapshot actually used. Prefer a code that's both in identity's
    known ids AND present in the snapshot; SKIP+LOG (return None) if
    ambiguous or absent, never guess."""
    candidate_ids = set(identity["all_identifiers"])
    frozen_codes = {e.player_code for e in snapshot.predictions}
    matches = candidate_ids & frozen_codes
    if len(matches) != 1:
        print(f"[SKIP] could not uniquely resolve {player_label} to one frozen-field player_code "
              f"(candidates={sorted(candidate_ids)}, in_frozen_field={sorted(candidate_ids & frozen_codes)})")
        return None
    return next(iter(matches))


def run_audit(conn: sqlite3.Connection, snapshot, player_a_name: str, player_b_name: str) -> dict:
    win_treatment = check_win_feature_representation()

    identity_a = audit_player_identity(conn, player_a_name, snapshot.game_code)
    identity_b = audit_player_identity(conn, player_b_name, snapshot.game_code)

    code_a = _resolve_player(conn, identity_a, snapshot, player_a_name)
    code_b = _resolve_player(conn, identity_b, snapshot, player_b_name)

    season_a = audit_2026_season(conn, code_a) if code_a else None
    season_b = audit_2026_season(conn, code_b) if code_b else None

    frozen_a = frozen_player_features(snapshot, code_a) if code_a else None
    frozen_b = frozen_player_features(snapshot, code_b) if code_b else None

    verify = recompute_and_verify_fit(conn, snapshot)

    contrib_a = decompose_contribution(verify["fitted"], verify["field_rows_by_code"][code_a]) if code_a else []
    contrib_b = decompose_contribution(verify["fitted"], verify["field_rows_by_code"][code_b]) if code_b else []
    top_diffs = largest_differences(contrib_a, contrib_b) if (contrib_a and contrib_b) else []

    prior_season = verify["field_rows_by_code"].get(code_a, {}).get("target_season")
    prior_season = (prior_season - 1) if prior_season is not None else None
    official_a = audit_official_metrics_for_player(conn, code_a, prior_season) if (code_a and prior_season) else {}
    official_b = audit_official_metrics_for_player(conn, code_b, prior_season) if (code_b and prior_season) else {}

    from datetime import date
    cutoff_obj = date.fromisoformat(snapshot.cutoff_date)
    recent_form_a = audit_recent_form(conn, code_a, cutoff_obj) if code_a else []
    recent_form_b = audit_recent_form(conn, code_b, cutoff_obj) if code_b else []

    top10_flags = audit_top10(conn, snapshot)

    verdict = classify_verdict(
        identity_a=identity_a, identity_b=identity_b, verify=verify,
        top_diffs=top_diffs, official_a=official_a, official_b=official_b,
    )

    return {
        "win_treatment": win_treatment,
        "identity_a": identity_a, "identity_b": identity_b,
        "code_a": code_a, "code_b": code_b,
        "season_a": season_a, "season_b": season_b,
        "frozen_a": frozen_a, "frozen_b": frozen_b,
        "verify": verify,
        "contrib_a": contrib_a, "contrib_b": contrib_b, "top_diffs": top_diffs,
        "official_a": official_a, "official_b": official_b,
        "recent_form_a": recent_form_a, "recent_form_b": recent_form_b,
        "top10_flags": top10_flags,
        "verdict": verdict,
    }


def print_console_report(result: dict, snapshot, player_a_name: str, player_b_name: str) -> None:
    frozen_a, frozen_b = result["frozen_a"], result["frozen_b"]
    season_a = result["season_a"]

    print("=== SEO GYO-RIM AUDIT ===")
    print()
    print(f"Identity: {result['identity_a']['status']} — ids={result['identity_a']['all_identifiers']}")
    print(f"2026 starts: {season_a['starts_2026'] if season_a else '—'}")
    print(f"2026 DB-confirmed wins: {season_a['database_confirmed_wins'] if season_a else '—'}")
    print(f"Frozen WIN %: {_pct(frozen_a.win_probability) if frozen_a else '—'}")
    print(f"Frozen rank: {frozen_a.rank if frozen_a else '—'}")
    print()
    print("=== PARK vs SEO ===")
    print()
    print(f"Park: {_pct(frozen_b.win_probability) if frozen_b else '—'} (rank {frozen_b.rank if frozen_b else '—'})")
    print(f"Seo: {_pct(frozen_a.win_probability) if frozen_a else '—'} (rank {frozen_a.rank if frozen_a else '—'})")
    for i, d in enumerate(result["top_diffs"], start=1):
        print(f"Largest difference #{i}: {d['feature']} (Δ={d['difference']})")
    print()
    print("=== WIN TREATMENT ===")
    print()
    print(f"Win feature: {result['win_treatment']['win_feature']}")
    print(f"How wins enter model: {result['win_treatment']['how_wins_enter_model']}")
    print()
    print("=== OFFICIAL METRICS ===")
    print()
    print(f"Park usable: {result['official_b'].get('rows_usable_clean', '—')}")
    print(f"Seo usable: {result['official_a'].get('rows_usable_clean', '—')}")
    top_feature = result["top_diffs"][0]["feature"] if result["top_diffs"] else None
    effect = "materially involved" if (top_feature and "official_metric" in top_feature) else "not the primary driver"
    print(f"Effect: {effect}")
    print()
    print("=== VERDICT ===")
    print()
    print(f"Primary cause: {result['verdict']['verdict']}")
    for e in result["verdict"]["evidence"]:
        print(f"Evidence: {e}")
    print()
    print("=== BETA #001 INTEGRITY ===")
    print()
    print("Frozen artifact modified: NO")
    print("Probability modified: NO")
    print()
    print("=== RECOMMENDED NEXT ACTION ===")
    print()
    v = result["verdict"]["verdict"]
    if v == "IDENTITY_MAPPING_ERROR":
        print("Fix klpga.neo_win.identity_resolution's match for the affected player_code(s) before trusting "
              "any official-metric feature for them; do not touch BETA #001 — freeze a BETA #001-C once fixed.")
    elif v == "OFFICIAL_METRIC_EXCLUSION_EFFECT":
        print("Investigate whether the excluded official metric can be safely un-flagged for this specific "
              "identity/season before considering it for a BETA #002 feature change.")
    elif v == "FEATURE_ENGINEERING_PROBLEM":
        print("Evaluate whether neo_consistency_stddev (or the involved official-metric slot) should be "
              "walk-forward promotion-gated against a no-consistency baseline before BETA #002.")
    elif v == "OTHER_CONFIRMED_CAUSE":
        print("Investigate the specific recompute mismatch listed above before trusting this frozen snapshot "
              "for any further analysis.")
    else:
        print("No corrective action needed — the gap is explained by already-validated, existing features. "
              "Consider this expected model behavior, not a bug.")


def write_markdown_report(result: dict, snapshot, player_a_name: str, player_b_name: str, path: Path) -> None:
    lines = [
        "# NEO GOLF BETA #001 — Seo Gyo-rim Diagnostic Audit",
        "",
        f"- Frozen snapshot: `{snapshot.prediction_id}` / `{snapshot.game_code}` / cutoff `{snapshot.cutoff_date}`",
        "",
        "## Step 1 — Identity",
        "",
        f"- {player_a_name}: `{result['identity_a']}`",
        f"- {player_b_name}: `{result['identity_b']}`",
        "",
        "## Step 2 — 2026 season (DB-confirmed)",
        "",
        f"- {player_a_name}: `{result['season_a']}`",
        f"- {player_b_name}: `{result['season_b']}`",
        "",
        "## Step 3/4 — Frozen features and contribution decomposition",
        "",
        f"- Recompute matches frozen exactly: {result['verify']['matches_frozen_exactly']}",
        f"- Mismatches: {result['verify']['mismatches']}",
        f"- {player_a_name} contributions: `{result['contrib_a']}`",
        f"- {player_b_name} contributions: `{result['contrib_b']}`",
        f"- Largest differences: `{result['top_diffs']}`",
        "",
        "## Step 5 — Win treatment",
        "",
        f"`{result['win_treatment']}`",
        "",
        "## Step 6 — Official metrics",
        "",
        f"- {player_a_name}: `{result['official_a']}`",
        f"- {player_b_name}: `{result['official_b']}`",
        "",
        "## Step 7 — Recent form (last 10 starts before cutoff)",
        "",
        f"- {player_a_name}: `{result['recent_form_a']}`",
        f"- {player_b_name}: `{result['recent_form_b']}`",
        "",
        "## Step 9 — Verdict",
        "",
        f"Primary cause: **{result['verdict']['verdict']}**",
    ] + [f"- {e}" for e in result["verdict"]["evidence"]] + [
        "",
        "## BETA #001 integrity",
        "",
        "Frozen artifact modified: NO. Probability modified: NO.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_top10_csv(result: dict, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "player_code", "player_name", "win_probability", "warnings", "flag"])
        writer.writeheader()
        for row in result["top10_flags"]:
            writer.writerow({**row, "warnings": ";".join(row["warnings"])})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--predictions-dir", default=str(ROOT / "neo_win_predictions"))
    parser.add_argument("--prediction-id", default="001")
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--cutoff-date", required=True, help="Used only to resolve the snapshot's archive path.")
    parser.add_argument("--player-a-name", default="서교림", help="Default: Seo Gyo-rim")
    parser.add_argument("--player-b-name", default="박현경", help="Default: Park Hyun-kyung")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.")
        return 3

    json_path, _csv_path = archive_paths(Path(args.predictions_dir), args.prediction_id, args.game_code, args.cutoff_date)
    if not json_path.exists():
        print(f"ERROR: frozen snapshot not found at {json_path}. This audit only inspects an ALREADY-frozen "
              "prediction — run scripts/33_predict_neo_win.py --freeze first.")
        return 5

    snapshot = read_neo_win_snapshot(json_path)

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        result = run_audit(conn, snapshot, args.player_a_name, args.player_b_name)
    finally:
        conn.close()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "BETA001_SEOGYORIM_AUDIT.md"
    csv_path = output_dir / "BETA001_TOP10_AUDIT.csv"
    write_markdown_report(result, snapshot, args.player_a_name, args.player_b_name, md_path)
    write_top10_csv(result, csv_path)

    print_console_report(result, snapshot, args.player_a_name, args.player_b_name)
    print()
    print(f"Wrote: {md_path}")
    print(f"Wrote: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

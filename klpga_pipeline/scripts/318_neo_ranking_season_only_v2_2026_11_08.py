"""Re-run the SEASON_ONLY_V2 NEO ranking formula (NOT the V1_FROZEN
formula scripts/317 used) on the same expanded candidate pool,
through Daebo HausD Championship (2026-11-08).

Formula source (quoted verbatim from the artifact, unmodified):
  klpga_pipeline/content/website_v2/research/NEO_RANKING_2026_SEASON_ONLY_V2.json
  -> "method": {
       "recency_half_life_days": 365,
       "shrinkage_prior_rounds": 32,
       "score_formula": "recency-weighted SG mean x effective rounds / (effective rounds + 32)",
       "formal_threshold_rounds": 40,
       "provisional_threshold_rounds": "20-39",
       "round_count_definition": "completed SG round records aggregated across events",
     }
This is a COMPLETELY DIFFERENT formula from NEO_RANKING_V1_FROZEN.json
(which scripts/317 used for both of its cohorts): V1_FROZEN is a
cohort z-score composite of tournament-level totals with a 10-EVENT
eligibility floor and no recency half-life at all; this one is a
single recency-weighted ROUND-level mean with a 365-day half-life and
a 32-round shrinkage prior, eligible at 40+ ROUNDS (not events).
Neither formula is merged with the other anywhere in this script.

Per-round dates: every tournament's own sg_official_history round
rows already carry one representative date per tournament for ALL of
its rounds (confirmed directly -- 2026070001's R1/R2/R3/R4 rows are
all dated 2026-08-02, its own closing date), not a true per-round
calendar date. This script follows that exact, already-established
convention for the 3 tournaments it adds that don't have
sg_official_history rows (SOIL, Iceberg, Daebo): one date per
tournament (its own closing date), applied to every round within it.

Approval status of this formula: NOT gated. It does not appear
anywhere in NEO_RANKING_PUBLICATION_GATE_DECISION.json (which only
evaluates V1/V2A/V2B); grep across the whole repo confirms zero
references to "SEASON_ONLY" outside its own research/ directory. It
has never been submitted to, or evaluated by, the formal 11-gate
review. It is not "approved" in any stronger sense than V1 is -- there
is simply no record of it having been reviewed at all.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

HALF_LIFE_DAYS = 365
SHRINKAGE_PRIOR_ROUNDS = 32
FORMAL_THRESHOLD = 40
PROVISIONAL_MIN = 20
CUTOFF = date(2026, 11, 8)

ADDED_ROUND_FILES = [
    # (game_code, path, tournament_close_date)
    ("2026100001", CONTENT / "SOIL_2026100001_R1_SG_OFFICIAL_V1.json", "2026-10-29"),
    ("2026100001", CONTENT / "SOIL_2026100001_R2_SG_OFFICIAL_V1.json", "2026-10-30"),
    ("2026100001", CONTENT / "SOIL_2026100001_R3_SG_OFFICIAL_V1.json", "2026-10-31"),
    ("2026100001", CONTENT / "SOIL_2026100001_FR_SG_OFFICIAL_V1.json", "2026-11-01"),
    ("2026100003", CONTENT / "ICEBERG_2026100003_R1_SG_OFFICIAL_V1.json", "2026-10-18"),
    ("2026100003", CONTENT / "ICEBERG_2026100003_R2_SG_OFFICIAL_V1.json", "2026-10-18"),
    ("2026110001", CONTENT / "DAEBO_2026110001_R1_SG_OFFICIAL_V1.json", "2026-11-06"),
    ("2026110001", CONTENT / "DAEBO_2026110001_R2_SG_OFFICIAL_V1.json", "2026-11-07"),
    ("2026110001", CONTENT / "DAEBO_2026110001_FR_SG_OFFICIAL_V1.json", "2026-11-08"),
]


def load_round_rows() -> list[dict]:
    rows = []
    for path in sorted(CONTENT.glob("sg_official_history/*/RECORDS.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        for r in records:
            if r.get("scope") != "single_round" or r.get("season") != 2026:
                continue
            rows.append({
                "player_id": str(r["player_id"]), "player_name": r.get("player_name") or r.get("player"),
                "total": float(r["total"]), "game_code": str(r["game_code"]), "date": r["date"],
            })
    for game_code, path, close_date in ADDED_ROUND_FILES:
        doc = json.loads(path.read_text(encoding="utf-8"))
        for r in doc["records"]:
            rows.append({
                "player_id": str(r["player_id"]), "player_name": r["player_name"],
                "total": float(r["total"]), "game_code": game_code, "date": close_date,
            })
    return rows


def main() -> None:
    rows = load_round_rows()
    by_player: dict[str, list[dict]] = {}
    for r in rows:
        by_player.setdefault(r["player_id"], []).append(r)

    names = {}
    for r in rows:
        names.setdefault(r["player_id"], r["player_name"])

    results = []
    for pid, prows in by_player.items():
        weighted_sum = 0.0
        total_weight = 0.0
        events = set()
        for r in prows:
            age_days = (CUTOFF - date.fromisoformat(r["date"])).days
            weight = 2.0 ** (-age_days / HALF_LIFE_DAYS)
            weighted_sum += weight * r["total"]
            total_weight += weight
            events.add(r["game_code"])
        rounds_count = len(prows)
        recency_mean = weighted_sum / total_weight if total_weight else 0.0
        effective_rounds = total_weight
        score = recency_mean * effective_rounds / (effective_rounds + SHRINKAGE_PRIOR_ROUNDS)
        if rounds_count >= FORMAL_THRESHOLD:
            status = "FORMAL"
        elif rounds_count >= PROVISIONAL_MIN:
            status = "PROVISIONAL"
        else:
            status = "BELOW_THRESHOLD"
        results.append({
            "player_id": pid, "player_name": names.get(pid, "?"), "score": round(score, 6),
            "recency_weighted_sg_mean": round(recency_mean, 6), "rounds": rounds_count,
            "events": len(events), "effective_rounds": round(effective_rounds, 6), "status": status,
        })

    formal = sorted([r for r in results if r["status"] == "FORMAL"], key=lambda r: -r["score"])
    provisional = sorted([r for r in results if r["status"] == "PROVISIONAL"], key=lambda r: -r["score"])
    below = [r for r in results if r["status"] == "BELOW_THRESHOLD"]

    for rank, r in enumerate(formal, 1):
        r["display_order"] = rank
    for rank, r in enumerate(provisional, len(formal) + 1):
        r["display_order"] = rank

    displayed = (formal + provisional[:12])[:120]

    out = {
        "schema_version": "NEO_RANKING_SEASON_ONLY_V2_2026_11_08",
        "formula_source": "klpga_pipeline/content/website_v2/research/NEO_RANKING_2026_SEASON_ONLY_V2.json (method block, unmodified)",
        "approval_status": "NOT GATED -- absent from NEO_RANKING_PUBLICATION_GATE_DECISION.json entirely; never formally reviewed.",
        "as_of": "2026-11-08",
        "half_life_days": HALF_LIFE_DAYS, "shrinkage_prior_rounds": SHRINKAGE_PRIOR_ROUNDS,
        "formal_threshold_rounds": FORMAL_THRESHOLD, "provisional_threshold_rounds": f"{PROVISIONAL_MIN}-{FORMAL_THRESHOLD - 1}",
        "total_players_with_any_sg": len(results),
        "formal_count": len(formal), "provisional_count": len(provisional), "below_threshold_count": len(below),
        "displayed_count": len(displayed),
        "players": displayed,
    }
    out_path = CONTENT / "NEO_RANKING_SEASON_ONLY_V2_2026_11_08.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(out_path), "formal_count": len(formal), "provisional_count": len(provisional),
        "top10": [(r["display_order"], r["player_name"], r["score"], r["rounds"]) for r in displayed[:10]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

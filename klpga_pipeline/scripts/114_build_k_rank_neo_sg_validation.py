"""Build KRANK_SG_NEO_VALIDATION.json -- NEO SITE V5 Mission 5.

Prepares the three-way K-Ranking / KLPGA-observed-SG / NEO-Ranking
comparison architecture. Computes the REAL two-way comparison available
today (K-Rank vs SG, both real data already in
OK_OPEN_2026_CURRENT_PLAYER_MASTER.json) using the reusable primitives
in src/klpga/validation/ranking_stats.py, and leaves every NEO-Ranking
-side output as null/None with an explicit "BLOCKED_..." status --
NEVER a numeric NEO Rank value -- until LIVE_PROBABILITY_MODEL_STATUS
(see home_ranking.py's FORMULA_STATE) is actually "VALIDATED". Once
NEO Ranking publishes, the neo_rank field on
ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json records stops being null and this
script's k_rank_vs_neo/sg_vs_neo sections activate using the exact same
ranking_stats functions already proven against k_rank_vs_sg below --
no new comparison logic needs writing then, only new data.

future 5R/10R/20R SG predictive performance: also left as a documented,
not-yet-computed slot (requires point-in-time backtest data across
multiple future rounds this script does not have access to) -- the
existing src/klpga/backtest/walk_forward.py module is the intended
future data source for this section; wiring it in is out of this
script's scope today.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.validation import ranking_stats as rs  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"
CURRENT_MASTER_PATH = CONTENT / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json"
OUT_PATH = CONTENT / "KRANK_SG_NEO_VALIDATION.json"

NEO_RANKING_PUBLICATION_STATUS = "BLOCKED_FORMULA_NOT_APPROVED"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build() -> dict:
    master = json.loads(CURRENT_MASTER_PATH.read_text(encoding="utf-8"))
    k_rank = {str(r["player_id"]): r["official_klpga_rank"] for r in master["records"] if r.get("official_klpga_rank") is not None}
    sg_rank = {str(r["player_id"]): r["sg_total_rank"] for r in master["records"] if r.get("sg_total_rank") is not None}
    # neo_rank: intentionally never populated from any file -- every
    # record's neo_pre_rank in this source is null (BLOCKED_FORMULA_
    # NOT_APPROVED), so there is nothing to read even by mistake.
    neo_rank: dict[str, float] = {}

    k_vs_sg = {
        "spearman": rs.spearman_rank_correlation(k_rank, sg_rank),
        "top10_overlap": rs.topn_overlap(k_rank, sg_rank, n=10, ascending_a=True, ascending_b=True),
        "top20_overlap": rs.topn_overlap(k_rank, sg_rank, n=20, ascending_a=True, ascending_b=True),
        "top50_overlap": rs.topn_overlap(k_rank, sg_rank, n=50, ascending_a=True, ascending_b=True),
        "largest_divergences": rs.largest_divergences(k_rank, sg_rank, ascending_a=True, ascending_b=True, top_k=10),
    }

    blocked = {
        "status": NEO_RANKING_PUBLICATION_STATUS,
        "spearman": None, "top10_overlap": None, "top20_overlap": None,
        "top50_overlap": None, "largest_divergences": None,
    }

    doc = {
        "schema_version": "neo_krank_sg_neo_validation_v1",
        "generated_at": now(),
        "source": {
            "artifact": "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json",
            "k_rank_field": "official_klpga_rank",
            "sg_field": "sg_total_rank (recent5 cumulative SG mean rank, see that artifact's own provenance)",
            "population": "OK Open 2026 entrants only (120) -- not yet the full active-tour universe",
        },
        "k_rank_vs_sg": k_vs_sg,
        "k_rank_vs_neo": dict(blocked),
        "sg_vs_neo": dict(blocked),
        "neo_ranking_publication_status": NEO_RANKING_PUBLICATION_STATUS,
        "future_predictive_performance": {
            "future_5r_sg": {"status": "NOT_YET_COMPUTED", "intended_source": "src/klpga/backtest/walk_forward.py"},
            "future_10r_sg": {"status": "NOT_YET_COMPUTED", "intended_source": "src/klpga/backtest/walk_forward.py"},
            "future_20r_sg": {"status": "NOT_YET_COMPUTED", "intended_source": "src/klpga/backtest/walk_forward.py"},
        },
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "k_vs_sg_n": k_vs_sg["spearman"]["n"], "k_vs_sg_rho": k_vs_sg["spearman"]["rho"],
        "neo_status": NEO_RANKING_PUBLICATION_STATUS,
    }, ensure_ascii=False))
    return doc


if __name__ == "__main__":
    build()

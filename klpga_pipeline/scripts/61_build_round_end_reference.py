"""Build reference round-end analytics from normalized official records."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.website_v2.round_end import breakaway_timeline, field_relative_hole_value, compare_player_rounds

def main() -> int:
    source = ROOT / "content/website_v2/kg_2026080001_official.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    players = ["\ub178\uc2b9\ud76c", "\ubc15\ud61c\uc900", "\uc2e0\ub2e4\uc778", "\uc720\uc544\ud604"]
    ids = {"9113": players[0], "9788": players[1], "9135": players[2], "10821": players[3]}
    holes = [dict(row, player=ids.get(str(row.get("player_id")), row.get("player"))) for row in data["holes"]]
    timeline = breakaway_timeline(holes, players=players, target_player="\uc2e0\ub2e4\uc778", round_number=4)
    field_values = field_relative_hole_value(data["holes"], "9135", range(3, 8))
    out = {"game_code":"2026080001", "round":4, "scope":"official exact scorecards; reference validation",
           "players":players, "target_player":"\uc2e0\ub2e4\uc778", "timeline":timeline,
           "field_relative_hole_value_holes_3_7":field_values,
           "separation_source": compare_player_rounds(holes, "\uc2e0\ub2e4\uc778", "\ubc15\ud61c\uc900", 4),
           "provenance":"KLPGA public playerDetail responses normalized by 60_collect_kg_official_analytics.py",
           "interpretation":"descriptive only; no causal inference"}
    dest = ROOT / "content/website_v2/kg_2026080001_round_end_reference.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(dest)
    return 0
if __name__ == "__main__": raise SystemExit(main())

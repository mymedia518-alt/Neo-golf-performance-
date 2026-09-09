"""Build the evidence-driven Tier-2 field-domain gate for an explicit
tournament (klpga.tournament_context)."""
from pathlib import Path
import argparse, json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.neo_win.tier2_publication_gate import write_gate
from klpga.tournament_context import load_tournament_context

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-code", default=None, help="omit for the operationally-active tournament (default, unchanged historical behavior)")
    args = ap.parse_args()
    result = write_gate(load_tournament_context(args.game_code))
    print(json.dumps({"overall_state": result["overall_state"], "domains": {d["domain"]: d["state"] for d in result["domains"]}}, ensure_ascii=False))

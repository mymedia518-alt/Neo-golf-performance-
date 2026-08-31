"""Build the evidence-driven Tier-2 field-domain gate."""
from pathlib import Path
import json, sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.neo_win.tier2_publication_gate import write_gate

if __name__ == "__main__":
    result = write_gate(ROOT / "content" / "website_v2")
    print(json.dumps({"overall_state": result["overall_state"], "domains": {d["domain"]: d["state"] for d in result["domains"]}}, ensure_ascii=False))

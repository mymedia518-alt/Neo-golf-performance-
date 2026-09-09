"""Audit current KLPGA Data Center player profiles for the frozen field
of the active tournament (klpga.tournament_context)."""
from __future__ import annotations
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_tournament_context
from klpga.kranking_week import resolve_ranking_week
from klpga.kranking_profile import URL as PROFILE_URL, collect_profile

CANONICAL_RANKING = "https://k-rankings.klpga.co.kr/kranking.jsp"
# Two known control-case player IDs, checked on every run as a parser
# sanity control -- not tournament entrants, fixed regardless of which
# tournament is active.
CONTROL_PLAYER_IDS = ("11134", "10725")

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def main(game_code: str | None = None):
    context = load_tournament_context(game_code)
    entry_path = context.artifact_path("entry_snapshot")
    _, ranking_week_label, ranking_week_korean = resolve_ranking_week(context.start_date)
    entries=json.loads(entry_path.read_text(encoding="utf-8"))["entries"]
    s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","Referer":CANONICAL_RANKING,"Accept-Language":"ko-KR,ko;q=0.9"})
    # The session warm-up itself is not the actual per-player evidence
    # (klpga.kranking_profile.collect_profile already retries and fails
    # closed to ACCESS_FAILURE per player, never crashing the batch) --
    # a failure here must not abort the whole audit before any
    # per-player attempt is even made.
    try:
        s.get(CANONICAL_RANKING,timeout=30).raise_for_status()
    except requests.exceptions.RequestException:
        pass
    records=[]
    for i,e in enumerate(entries,1):
        records.append(collect_profile(e["player_id"], s, ranking_week_label, ranking_week_korean))
        if i%20==0: print(f"profiles {i}/{len(entries)}",flush=True)
        time.sleep(.12)
    controls=[collect_profile(pid, s, ranking_week_label, ranking_week_korean) for pid in CONTROL_PLAYER_IDS]
    out={"schema_version":"neo_klpga_datacenter_profile_audit_v1","game_code":context.game_code,"source_surface":"KLPGA Data Center · K-RANKING | PLAYER PROFILE","official_source":CANONICAL_RANKING,"profile_source":PROFILE_URL,"ranking_week":ranking_week_label,"retrieved_at":now(),"entry_count":len(records),"records":records,"control_cases":controls,"coverage":{"name":sum(bool(r["current_player_name"]) for r in records),"k_ranking":sum(r["current_k_ranking"] is not None for r in records),"team":sum(bool(r["current_team"]) for r in records),"ranking_points":sum(r["ranking_points"] is not None for r in records),"total_points":sum(r["total_points"] is not None for r in records),"events_played":sum(r["events_played"] is not None for r in records),"parse_failures":sum(r["parse_state"]!="PASS" for r in records),"official_blank_team":sum(r["team_state"]=="OFFICIAL_BLANK" for r in records)}}
    context.artifact_path("data_center_profile_audit").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(out["coverage"],ensure_ascii=False)); return 0

def _cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-code", default=None, help="omit for the operationally-active tournament (default, unchanged historical behavior)")
    args = ap.parse_args()
    return main(args.game_code)

if __name__=="__main__": raise SystemExit(_cli())

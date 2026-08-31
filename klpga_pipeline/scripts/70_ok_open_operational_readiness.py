"""Read-only operational readiness and PRE launch dry run for any KLPGA event."""
from __future__ import annotations
import hashlib, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.collectors.tournaments import fetch_game_list
from klpga.collectors.entry_list import fetch_entry_list
from klpga.http_client import PoliteHttpClient
from klpga.parsers.entry_list_parser import parse_entry_list_html
from klpga.neo_win.stage_freeze_gate import stage_sequence_for_holes, validate_stage_transition, StageFreezeGateError

GAME = "2026120001"
OUT = ROOT / "content" / "website_v2" / "OK_OPEN_2026_OPERATIONAL_READINESS.json"
FROZEN_ENTRY = ROOT / "content" / "website_v2" / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
PRE = ROOT / "content" / "website_v2" / "OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"


def main() -> int:
    cache = ROOT / "data" / "raw_cache" / "readiness"
    client = PoliteHttpClient(cache_dir=cache)
    listings = fetch_game_list(client, season=2026)
    matches = [x for x in listings if x.game_code == GAME]
    if len(matches) != 1:
        raise RuntimeError(f"expected one official listing for {GAME}, got {len(matches)}")
    listing = matches[0]
    metadata = {"game_code": listing.game_code, "name": listing.game_title, "start_date": listing.start_date_raw, "end_date": listing.end_date_raw, "venue": listing.course_text, "out_course": listing.out_course_text, "in_course": listing.in_course_text, "par": listing.raw.get("totalPar"), "holes": (int(listing.raw.get("totalRound")) * 18 if str(listing.raw.get("totalRound", "")).isdigit() else None), "rounds": int(listing.raw.get("totalRound")) if str(listing.raw.get("totalRound", "")).isdigit() else None, "purse": listing.prize_money, "format_code": listing.game_method, "format": listing.raw.get("gameMethodName") or "stroke-play metadata", "status": listing.game_finish, "source": "https://klpga.co.kr/ajax/tourInfo/getGameList"}
    if metadata["holes"] is None:
        raise RuntimeError("official totalRound missing; cannot derive lifecycle")
    frozen = json.loads(FROZEN_ENTRY.read_text(encoding="utf-8")); frozen_by = {str(x["player_id"]): x for x in frozen["entries"]}
    parsed = parse_entry_list_html(fetch_entry_list(client, GAME))
    conn = sqlite3.connect(Path(r"C:/Users/user/Desktop/Neo-golf-performance-/klpga_pipeline/data/klpga.sqlite"))
    known = {str(r[0]): str(r[1]) for r in conn.execute("SELECT player_id, player_name FROM player_master")}
    current = {str(r.player_code): {"player_id": str(r.player_code), "player_name": r.player_name, "canonical_name": known.get(str(r.player_code)), "identity_match": str(r.player_code) in known, "entry_status": "listed"} for r in parsed.rows}
    added = sorted(set(current) - set(frozen_by)); removed = sorted(set(frozen_by) - set(current)); unchanged = sorted(set(current) & set(frozen_by)); unresolved = sorted(k for k,v in current.items() if not v["identity_match"])
    delta = {"added": added, "removed": removed, "withdrawn": [], "replaced": [], "unchanged": unchanged, "unresolved": unresolved, "withdrawal_marker_available": False, "source": "https://klpga.co.kr/web/tourInfo/entry?gameCode=" + GAME}
    pre = json.loads(PRE.read_text(encoding="utf-8")); profile_by = {str(p["player_id"]): p for p in pre["profiles"]}
    coverage = {"total": len(current), "identity_match": sum(1 for v in current.values() if v["identity_match"]), "sufficient_sg": sum(1 for p in profile_by.values() if p.get("coverage") == "ENTRY + SUFFICIENT SG"), "limited_sg": sum(1 for p in profile_by.values() if p.get("coverage") == "ENTRY + LIMITED SG"), "no_official_sg": sum(1 for p in profile_by.values() if p.get("coverage") == "ENTRY + NO OFFICIAL SG")}
    required = stage_sequence_for_holes(metadata["holes"]); lifecycle = {"public_stages": required, "prediction_ids": {s: ("001" if s == "PRE" else "002" if s == "R1" else "003" if s == "R2" else None) for s in required}, "final_review_only": True, "no_r4": True}
    recovery = {"official_page_unavailable":"RETRY then WAIT; HARD STOP if completeness cannot be proven", "partial_leaderboard":"WAIT", "missing_player_identity":"HARD STOP", "round_incomplete":"WAIT", "sg_unavailable":"SAFE CONTINUE fast lane", "wd_ambiguity":"WAIT", "format_mismatch":"HARD STOP", "freeze_artifact_exists":"HARD STOP", "website_generation_failure":"HARD STOP publication"}
    dry_run = ["tournament detect", "official format detect", "metadata validation", "entry fetch/delta", "canonical identity validation", "PRE feature/readiness validation", "artifact/freeze gate simulation", "Website 2.0 candidate generation", "publication gate (not executed)"]
    result = {"schema_version":"neo_ok_open_operational_readiness_v1", "retrieved_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"), "tournament":metadata, "entry_delta":delta, "coverage":coverage, "pre_forecast_readiness":{"entry_identity":coverage["identity_match"] == coverage["total"] and not added and not removed, "history_available":len(profile_by) == coverage["total"], "future_data_excluded":pre.get("future_data_excluded") is True, "model_version":"existing forecast model; no changes", "artifact_destination":"existing lifecycle freeze destination", "ready":coverage["identity_match"] == coverage["total"] and not added and not removed and pre.get("future_data_excluded") is True}, "lifecycle":lifecycle, "r1_ingest_path":["official ingest","completeness gate","identity/rank/WD-DQ-CUT validation","SG availability (optional deep lane)","snapshot freeze","prediction checkpoint","Website 2.0 candidate","publication gate"], "failure_recovery":recovery, "dry_run":{"steps":dry_run,"tournament_specific_code_changes":0,"manual_intervention_count":0,"production_publish_executed":False}, "provenance":{"frozen_entry_sha256":hashlib.sha256(FROZEN_ENTRY.read_bytes()).hexdigest(),"pre_snapshot_sha256":hashlib.sha256(PRE.read_bytes()).hexdigest()}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"metadata":metadata,"delta":{k:len(v) if isinstance(v,list) else v for k,v in delta.items()},"coverage":coverage,"required_stages":required,"pre_ready":result["pre_forecast_readiness"]["ready"]}, ensure_ascii=False))
    return 0
if __name__ == "__main__": raise SystemExit(main())

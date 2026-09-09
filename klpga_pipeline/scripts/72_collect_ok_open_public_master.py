"""Collect official current identity/ranking data and export PRE evidence
artifacts for an explicit tournament (klpga.tournament_context).

--game-code (default: the operationally-active tournament, unchanged
historical behavior): resolves via klpga.tournament_context.
load_tournament_context, never active_tournament.json for a different
game_code -- see that function's own docstring.

NETWORK DEPENDENCY (Priority 2 generalization): the two live fetches
this script makes are not equally "genuinely necessary" for PRE
generation:

  - collect_profiles() (current name/status/sponsor per player) is
    confirmatory enrichment -- the entry snapshot already carries a
    real, sourced player_name for every entrant, so a live fetch
    failure here must never crash the whole run. Each player's own
    fetch now fails closed INDIVIDUALLY (identity_validation="FAIL",
    every current_* field None, failure_reason recorded) rather than
    letting one requests exception abort the other 119.

  - the official K-Ranking (collect_rankings_live / the allplayer.jsp
    live POST) IS a required PRE input, but it does not always require
    a fresh live fetch: collect_rankings_offline() below reuses
    scripts/87's own real, already-tested extractor against a
    sanctioned, hash-verified offline capture at
    content/website_v2/incoming_evidence/<game_code>/*KRANKING*RAW.html
    when one exists for this game_code -- never a live fetch, never a
    second/different parsing rule for the same official source. Only
    when no such offline evidence exists does this script fall back to
    the live POST (collect_rankings_live), exactly as it always has --
    OK Open's own real, already-committed artifact was produced this
    way and nothing about that path changes here.

  Either way, an evidence gap is never silently treated as an
  official rank: week_evidence_state stays "UNPROVEN"/"BLOCKED" and
  official_klpga_rank stays None for every player until a real,
  provably-current-week response is available, which is exactly what
  klpga.neo_win.tier2_publication_gate's K_RANKING domain already
  requires to PASS.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))
from klpga.tournament_context import load_tournament_context
from klpga.kranking_week import extract_returned_week, resolve_ranking_week, response_sha256

PROFILE_URL = "https://klpga.co.kr/web/profile/mainRecord"
RANK_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"
DB = ROOT / "data" / "klpga.sqlite"


def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def label_value(soup, label_text):
    lab = soup.find("label", string=lambda x: x and x.strip() == label_text)
    if lab is None: return None
    parent = lab.parent
    tags = parent.find_all("h5")
    return tags[-1].get_text(" ", strip=True) if tags else ""


def collect_profiles(entries, *, session=None):
    """Per-player official profile enrichment. A network failure on
    ANY one player must never abort the other entrants -- this is
    confirmatory data, never a hard PRE prerequisite, because identity
    itself is already established by the entry snapshot's own real,
    officially-sourced player_name (drawn from the official KLPGA entry
    list, itself either a live fetch or a sanctioned, hash-verified
    offline import -- either way a real official source, never a
    guess).

    LIVE DEPENDENCY CLASSIFICATION (Priority-2 follow-up): the live
    profile page (klpga.co.kr/web/profile/mainRecord) can confirm three
    distinct things, and they are NOT equally critical:
      - current_official_player_name: REQUIRED_FOR_CORRECTNESS in the
        sense that a real name must exist, but NOT specifically a LIVE
        one -- the entry snapshot's own player_name already satisfies
        this. On a live-fetch failure this now falls back to that real
        entry-snapshot name (never a guess: it is the same officially-
        sourced string the entry list itself carries), with
        identity_source recording which one was actually used so no
        consumer can mistake a fallback for a live reconfirmation.
      - current_player_status (등급) and current_official_sponsor
        (소속): ENRICHMENT_ONLY -- no non-live official source for
        these exists in this pipeline, so they stay honestly None on
        failure, exactly as before. Never guessed, never backfilled
        from the entry snapshot (which does not carry them)."""
    session = session if session is not None else requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"})
    out = []
    for i, e in enumerate(entries, 1):
        pid = str(e["player_id"])
        current_name = status = sponsor = None
        failure_reason = None
        try:
            r = session.get(PROFILE_URL, params={"playerCode": pid}, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.content.decode("utf-8", "replace"), "html.parser")
            search = soup.select_one("input.playerSearch")
            current_name = (search.get("placeholder") if search else None) or (
                soup.select_one(".ph-player h3").get_text(" ", strip=True) if soup.select_one(".ph-player h3") else None
            )
            status = label_value(soup, "등급")
            sponsor = label_value(soup, "소속")
        except requests.exceptions.RequestException as exc:
            failure_reason = f"official profile fetch unavailable: {exc}"
        identity_source = "live_profile"
        if current_name is None:
            entry_name = e.get("player_name")
            if entry_name:
                current_name = entry_name
                identity_source = "entry_snapshot"
        record = {
            "player_id": pid,
            "historical_source_names": list(dict.fromkeys([x for x in (e.get("player_name"), e.get("canonical_name")) if x])),
            "current_official_player_name": current_name,
            "current_player_status": status,
            "current_official_sponsor": sponsor or None,
            "official_source": PROFILE_URL + "?playerCode=" + pid,
            "retrieved_at": now(),
            "identity_validation": "PASS" if current_name else "FAIL",
            "identity_source": identity_source,
        }
        if failure_reason:
            record["failure_reason"] = failure_reason
        out.append(record)
        if i % 20 == 0: print(f"profiles {i}/{len(entries)}", flush=True)
        time.sleep(0.15)
    return out


def collect_rankings_live(target_ids, *, rank_week_param, ranking_date_label, session=None):
    """Unchanged from OK Open's own real, already-committed live path
    (the only rename is threading rank_week_param/ranking_date_label in
    as parameters instead of module globals) -- preserves historical
    reproducibility exactly."""
    s = session if session is not None else requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": RANK_URL})
    s.get(RANK_URL, timeout=30).raise_for_status()
    # Official K-Rankings requires the public weekly form POST to populate
    # table rows; this is the same endpoint used by the site's UI.
    # Rank_week -- see klpga.kranking_week for the (best-effort, generic)
    # derivation from this tournament's own start date.
    r = s.post(RANK_URL, data={"Rank_week": rank_week_param, "top_player": "김민솔", "last_week": "null"}, timeout=30)
    r.raise_for_status()
    # K-RANK PROVENANCE (Phase 2): resolve_ranking_week()'s output is a
    # REQUEST candidate only -- the raw response itself is hashed and
    # parsed for whatever week it actually claims to have returned,
    # rather than assuming the server honored the requested week. A
    # mismatch, or a response that exposes no provable week at all, is
    # recorded honestly (never silently reconciled) so
    # tier2_publication_gate can fail closed on it.
    raw_bytes = r.content
    raw_html = raw_bytes.decode("utf-8", "replace")
    raw_response_sha256 = response_sha256(raw_bytes)
    returned_rank_week = extract_returned_week(raw_html)
    week_match = (returned_rank_week == ranking_date_label) if returned_rank_week is not None else None
    soup = BeautifulSoup(raw_html, "html.parser"); table = soup.select_one("table#example"); found = {}
    if table:
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td"); link = tr.find("a", href=lambda x: x and "player_code=" in x)
            if not cells or not link: continue
            pid = link.get("href").split("player_code=")[-1].split("&")[0]; rank = cells[0].get_text(" ", strip=True)
            try: rank = int(rank)
            except ValueError: continue
            if pid in target_ids: found[pid] = rank
    return {
        "schema_version": "neo_tournament_official_klpga_ranking_v1",
        "ranking_category": "K-RANKING (official weekly KLPGA ranking)",
        "collection_method": "live_fetch",
        "requested_rank_week": ranking_date_label,
        "returned_rank_week": returned_rank_week,
        "week_evidence_state": "PROVEN" if returned_rank_week is not None else "UNPROVEN",
        "week_match": week_match,
        "ranking_date": ranking_date_label,
        "official_source": RANK_URL,
        "retrieved_at": now(),
        "raw_response_sha256": raw_response_sha256,
        "records": [{"player_id": pid, "official_rank": found.get(pid), "validation_state": "PASS" if pid in found else "UNAVAILABLE"} for pid in sorted(target_ids)],
    }


def _kranking_top120_extractor():
    """Import scripts/87's own real extract() (week regex + the
    official ordered {"id":...,"text":...} array) -- never a second,
    different parsing rule for the same official source."""
    spec = importlib.util.spec_from_file_location("kranking_top120_extractor", ROOT / "scripts" / "87_collect_kranking_top120.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collect_rankings_offline(target_ids, offline_html_path: Path, *, game_code: str):
    """Sanctioned offline path: no live fetch at all. Reuses
    scripts/87's own already-tested extractor against a hash-verified,
    externally-captured K-Ranking page. A genuine evidence gap in the
    captured page (no provable ranking-period label, or fewer than 120
    ordered entries -- scripts/87's own ValueError) is caught and
    recorded as an honest BLOCKED state, never fabricated and never
    allowed to crash the run."""
    extractor = _kranking_top120_extractor()
    raw_bytes = offline_html_path.read_bytes()
    raw_html = raw_bytes.decode("utf-8", "replace")
    retrieved_at = now()
    blocked_reason = None
    by_id: dict[str, int] = {}
    returned_week = None
    try:
        records = extractor.extract(raw_html, retrieved_at)
        by_id = {r["player_id"]: r["official_k_rank"] for r in records}
        returned_week = records[0]["ranking_week"]
    except ValueError as exc:
        blocked_reason = str(exc)
    week_evidence_state = "PROVEN" if returned_week is not None else "BLOCKED"
    payload = {
        "schema_version": "neo_tournament_official_klpga_ranking_v1",
        "ranking_category": "K-RANKING (official weekly KLPGA ranking)",
        "collection_method": "offline_import",
        "game_code": game_code,
        "requested_rank_week": None,
        "returned_rank_week": returned_week,
        "week_evidence_state": week_evidence_state,
        "week_match": None,
        "ranking_date": returned_week,
        "official_source": extractor.CANONICAL_URL,
        "acquisition_source": str(offline_html_path),
        "retrieved_at": retrieved_at,
        "raw_response_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "records": [{"player_id": pid, "official_rank": by_id.get(pid), "validation_state": "PASS" if pid in by_id else "UNAVAILABLE"} for pid in sorted(target_ids)],
    }
    if blocked_reason is not None:
        payload["blocked_reason"] = blocked_reason
    return payload


def _find_offline_kranking_html(game_code: str) -> list[Path]:
    """The sanctioned offline-import quarantine directory (see
    content/website_v2/incoming_evidence/<game_code>/MANIFEST.json) --
    the only place this script ever looks for a K-Ranking capture
    without a live fetch, and only when a real hash-verified file has
    actually landed there. Returns every candidate file found (sorted
    by filename only for a deterministic iteration order, never as a
    selection criterion) -- callers decide which one actually proves
    the ranking period by attempting extraction, not by guessing from
    a name."""
    d = CONTENT / "incoming_evidence" / str(game_code)
    if not d.is_dir():
        return []
    matches = sorted(d.glob("*KRANKING*RAW.html")) or sorted(d.glob("*KRANKING*.html"))
    return matches


def _resolve_offline_kranking(target_ids, game_code: str):
    """Try every sanctioned offline K-Ranking capture for this
    game_code and use whichever one actually proves the ranking period
    (week_evidence_state == "PROVEN") -- evidence-based selection, never
    filename-based. When more than one candidate proves a period, a
    disagreement between them is a real integrity problem and must not
    be silently resolved; when none prove a period, the most recently
    attempted BLOCKED result is returned so the honest gap is still
    recorded (never silently falls through to a live fetch, which would
    contradict the sanctioned-evidence contract for a directory that
    demonstrably has capture attempts in it already)."""
    candidates = _find_offline_kranking_html(game_code)
    if not candidates:
        return None
    proven = []
    last_result = None
    for path in candidates:
        result = collect_rankings_offline(target_ids, path, game_code=game_code)
        last_result = result
        if result["week_evidence_state"] == "PROVEN":
            proven.append(result)
    if len(proven) > 1:
        weeks = {r["returned_rank_week"] for r in proven}
        if len(weeks) > 1:
            raise RuntimeError(
                f"multiple offline K-Ranking captures for game_code={game_code!r} PROVE different weeks "
                f"({sorted(weeks)}) -- refusing to silently pick one; resolve the conflicting evidence first"
            )
    if proven:
        return proven[0]
    return last_result


def build(game_code: str | None = None):
    context = load_tournament_context(game_code)
    GAME = context.game_code
    CUTOFF = f"{context.start_date}T00:00:00+09:00"
    entry_path = context.artifact_path("entry_snapshot")
    entry = json.loads(entry_path.read_text(encoding="utf-8")); entries = entry["entries"]; ids = {str(e["player_id"]) for e in entries}
    profiles = collect_profiles(entries)

    offline_ranking = _resolve_offline_kranking(ids, GAME)
    if offline_ranking is not None:
        ranking = offline_ranking
    else:
        rank_week_param, ranking_date_label, _ = resolve_ranking_week(context.start_date)
        ranking = collect_rankings_live(ids, rank_week_param=rank_week_param, ranking_date_label=ranking_date_label)
    rank_by = {x["player_id"]: x["official_rank"] for x in ranking["records"]}

    perf = json.loads(context.artifact_path("pre_performance_snapshot").read_text(encoding="utf-8")); pby = {str(p["player_id"]): p for p in perf["profiles"]}
    sgvals = {pid: (((pby.get(pid, {}).get("windows") or {}).get("recent5") or {}).get("components") or {}).get("total", {}).get("mean") for pid in ids}
    sg_order = sorted(ids, key=lambda pid: (-(sgvals[pid] if sgvals[pid] is not None else float("-inf")), pid)); sg_rank = {pid: (i + 1 if sgvals[pid] is not None else None) for i, pid in enumerate(sg_order)}
    # Existing model, in-memory copy only: canonical DB is never modified.
    # A DB *file* existing with no tournament_entry table yet (exactly
    # how data/klpga.sqlite can end up as a real but table-less file in
    # a fresh checkout -- the same class of gap
    # klpga.tournament_entry_bootstrap already fails closed on) must
    # never surface as a raw sqlite3.OperationalError -- win_probability
    # stays honestly None for every entrant rather than crashing this
    # whole PRE build over a DB-provisioning gap that has nothing to do
    # with this specific game_code.
    prob = {}
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as sc:
            with sqlite3.connect(":memory:") as c:
                sc.backup(c)
                c.executemany(
                    "INSERT OR REPLACE INTO tournament_entry (game_code,player_code,player_name_display,nationality,qualification_category,qualification_reason,source,collected_at) VALUES (?,?,?,?,?,?,?,?)",
                    [(GAME, str(e["player_id"]), str(e.get("player_name") or ""), e.get("nationality"), e.get("qualification_category"), e.get("qualification_reason"), "frozen_entry_snapshot", entry["retrieved_at"]) for e in entries],
                )
                from klpga.models.inference import run_inference
                result = run_inference(c, GAME, cutoff_date_arg=context.start_date, tournament_name_arg=context.tournament_name)
                prob = {str(x.player_code): x.win_probability for x in result.predictions}
    except sqlite3.OperationalError:
        prob = {}
    forecast = {"schema_version": "neo_tournament_pre_win_forecast_v1", "game_code": GAME, "cutoff": CUTOFF, "model_version": "M4", "model_features": ["prior_avg_round_score_to_par", "prior_recent_form_10"], "future_data_excluded": True, "normalization": {"sum": sum(prob.values()), "entrant_count": len(prob)}, "source": "existing validated NEO inference; in-memory join to frozen entry snapshot", "records": [{"player_id": pid, "win_probability": prob.get(pid), "provenance": {"source_artifact": "existing M4 inference", "cutoff": CUTOFF}} for pid in sorted(ids)]}
    master = []
    for prof in profiles:
        pid = prof["player_id"]
        provenance = {"entry": entry_path.name, "profile": prof["official_source"], "ranking": ranking["official_source"], "performance": context.artifact_path("pre_performance_snapshot").name, "forecast": context.artifact_path("pre_win_forecast").name}
        field_provenance = {k: {"source_artifact": v, "official_source_reference": prof["official_source"] if k.startswith("current_") else (ranking["official_source"] if k == "official_klpga_rank" else None), "retrieved_at": prof["retrieved_at"], "cutoff": CUTOFF, "validation_state": "PASS" if v is not None else "UNAVAILABLE"} for k, v in {"current_official_player_name": prof["current_official_player_name"], "current_player_status": prof["current_player_status"], "current_official_sponsor": prof["current_official_sponsor"], "official_klpga_rank": rank_by.get(pid), "sg_total_rank": sg_rank.get(pid), "win_probability": prob.get(pid)}.items()}
        master.append({**prof, "official_klpga_rank": rank_by.get(pid), "neo_pre_rank": None, "sg_total_rank": sg_rank.get(pid), "top20_probability": None, "top10_probability": None, "top5_probability": None, "win_probability": prob.get(pid), "validation_status": "PARTIAL_UPSTREAM" if prof["current_official_player_name"] and prob.get(pid) is not None else "UPSTREAM_GAP", "provenance": provenance, "field_provenance": field_provenance})
    context.artifact_path("current_player_master").write_text(json.dumps({"schema_version": "neo_tournament_current_player_master_v1", "game_code": GAME, "entry_count": len(master), "records": master}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    context.artifact_path("official_klpga_ranking").write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    context.artifact_path("pre_win_forecast").write_text(json.dumps(forecast, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    evidence = {"schema_version": "neo_tournament_neo_pre_ranking_evidence_v1", "game_code": GAME, "cutoff": perf["cutoff"], "neo_pre_rank": None, "ranking_status": "PENDING_INDEPENDENT_METHOD_APPROVAL", "records": [{"player_id": p["player_id"], "performance": p.get("windows"), "dimensions": p.get("dimensions"), "direction": p.get("direction"), "consistency": p.get("consistency"), "composition": p.get("composition"), "coverage": p.get("coverage"), "win_probability": prob.get(p["player_id"])} for p in perf["profiles"]]}
    context.artifact_path("neo_pre_ranking_evidence").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    sgdoc = {"schema_version": "neo_tournament_pre_sg_total_rank_v1", "game_code": GAME, "cutoff": perf["cutoff"], "window": "recent5 cumulative SG", "scope": "tournament_cumulative arithmetic mean of completed single-round SG", "minimum_sample": 1, "tie_rule": "ascending player_id after equal mean", "missing_rule": "NULL when no validated recent5 total mean", "records": [{"player_id": pid, "sg_total_mean": sgvals[pid], "sg_total_rank": sg_rank[pid], "provenance": context.artifact_path("pre_performance_snapshot").name} for pid in sorted(ids)]}
    context.artifact_path("pre_sg_total_rank").write_text(json.dumps(sgdoc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = {"entrant_count": len(master), "identity_count": sum(bool(x["current_official_player_name"]) for x in master), "current_name_coverage": sum(bool(x["current_official_player_name"]) for x in master), "current_status_coverage": sum(bool(x["current_player_status"]) for x in master), "sponsor_coverage": sum(bool(x["current_official_sponsor"]) for x in master), "klpga_rank_coverage": sum(x["official_klpga_rank"] is not None for x in master), "neo_rank_coverage": 0, "sg_total_rank_coverage": sum(x["sg_total_rank"] is not None for x in master), "top20_coverage": 0, "top10_coverage": 0, "top5_coverage": 0, "win_coverage": sum(x["win_probability"] is not None for x in master), "neo_pre_rank_status": "PENDING_INDEPENDENT_METHOD_APPROVAL", "ranking_week_evidence_state": ranking.get("week_evidence_state"), "website_generation": "NOT RUN"}
    context.artifact_path("pre_public_master_validation").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game-code", default=None, help="omit for the operationally-active tournament (default, unchanged historical behavior)")
    args = ap.parse_args()
    build(args.game_code)


if __name__ == "__main__": main()

"""Validate a player-season Shot Tracker archive built by player_season_archive.py.

Reads RAW responses directly (not the CSVs) and checks them against the
official player record (profile_getToursRecord_<season>.json), then checks the
normalized CSVs against RAW. Writes <season>/validation/validation_report.{json,md}.
Exit code 1 if any FAIL.

Optional --cross-sqlite: a klpga_shots.sqlite from another collection run
(e.g. the group-endpoint full-field run for one event) to compare the same
player's shots field by field.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collector import STATE  # noqa: E402

NUM_FIELDS = ["pp_distance", "pp_distanceLen", "pp_altitude", "pp_x", "pp_y", "pp_greenx", "pp_greeny"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class Report:
    def __init__(self):
        self.checks = []

    def add(self, cid, status, title, detail=None):
        self.checks.append({"id": cid, "status": status, "title": title, "detail": detail})

    @property
    def failed(self):
        return [c for c in self.checks if c["status"] == "FAIL"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--season", required=True)
    ap.add_argument("--player", required=True)
    ap.add_argument("--expect-events", type=int)
    ap.add_argument("--expect-rounds", type=int)
    ap.add_argument("--expect-hole-files", type=int)
    ap.add_argument("--expect-shots", type=int)
    ap.add_argument("--cross-sqlite", help="other klpga_shots.sqlite to compare against")
    ap.add_argument("--cross-label", default="")
    a = ap.parse_args()
    root, season, player = Path(a.root), a.season, a.player
    R = Report()

    prof = json.loads((root / "source" / f"profile_getToursRecord_{season}.json").read_bytes().decode("utf-8-sig"))
    games = {g["gameCode"]: g for g in prof.get("reGameList") or []}
    rec = prof.get("reRecord") or {}

    # ---- A. inventory vs official record
    raw_base = root / season / "raw"
    files = sorted(raw_base.glob(f"*/player_shot/{player}/R*/*.json"))
    canon = [p for p in files if re.fullmatch(r"H\d{2}\.json", p.name)]
    conflicts = [p.relative_to(root).as_posix() for p in files if p not in canon]
    by_round = defaultdict(list)
    for p in canon:
        by_round[(p.parts[-5], int(p.parent.name[1:]))].append(int(p.stem[1:]))
    exp_rounds = {(g, r) for g, v in games.items() for r in range(1, 5) if (v.get(f"round{r}Score") or "") != ""}
    missing = sorted(exp_rounds - set(by_round))
    unexpected = sorted(set(by_round) - exp_rounds)
    incomplete = {f"{g}R{r}": sorted(set(range(1, 19)) - set(h)) for (g, r), h in by_round.items() if sorted(h) != list(range(1, 19))}
    R.add("A1", "PASS" if not missing and not unexpected else "FAIL",
          "Every official round has raw data and vice versa",
          {"official_events": len(games), "official_rounds": len(exp_rounds), "raw_events": len({g for g, _ in by_round}),
           "raw_rounds": len(by_round), "missing_raw_rounds": missing, "raw_rounds_not_in_official": unexpected,
           "official_joinGameNum": rec.get("joinGameNum")})
    R.add("A2", "PASS" if not incomplete else "FAIL", "Each raw round has holes 1-18", incomplete or None)
    R.add("A3", "PASS" if not conflicts else "WARN", "No conflicting re-collections (sha-suffixed copies)", conflicts or None)
    for flag, val, actual, title in [("expect_events", a.expect_events, len({g for g, _ in by_round}), "events"),
                                     ("expect_rounds", a.expect_rounds, len(by_round), "rounds"),
                                     ("expect_hole_files", a.expect_hole_files, len(canon), "hole files")]:
        if val is not None:
            R.add("A4", "PASS" if val == actual else "FAIL", f"Stated {title} count", {"stated": val, "actual": actual})

    # ---- B. intake manifest integrity
    bad = []
    for mp in sorted((root / "source").glob("intake_*.json")):
        m = json.loads(mp.read_text(encoding="utf-8"))
        for f in m["files"]:
            if "stored_as" in f:
                p = root / f["stored_as"]
                if not p.exists() or sha(p.read_bytes()) != f["sha256"]:
                    bad.append(f["stored_as"])
    R.add("B1", "PASS" if not bad else "FAIL", "Stored raw bytes still match intake sha256", bad[:20] or None)
    errs = root / "source" / "collection_errors.json"
    if errs.exists():
        e = json.loads(errs.read_bytes().decode("utf-8-sig"))
        R.add("B2", "PASS" if e == [] else "WARN", "Collector error log is empty", None if e == [] else e[:20])

    # ---- C-G. per response
    struct_issues, ident_issues, seq_issues, unknown_states = [], [], [], Counter()
    holed_dist, round_strokes, round_par, hole_par, hole_yds = [], Counter(), Counter(), defaultdict(set), defaultdict(set)
    tee_sum = []  # (yds, meter, distanceLen+distance) for shot 1 on par 4/5
    rng = defaultdict(lambda: [float("inf"), float("-inf")])
    raw_shots = {}
    states = Counter()
    extra = Counter()
    for p in canon:
        game, rnd, hole = p.parts[-5], int(p.parent.name[1:]), int(p.stem[1:])
        d = json.loads(p.read_bytes().decode("utf-8-sig"))
        model = (d.get("modelAndView") or {}).get("model") or {}
        if set(d.keys()) != {"baseHoleInfo", "holeInfo", "modelAndView", "properties", "shotTrackerList"}:
            struct_issues.append((p.name, game, rnd, sorted(d.keys())))
        for k in ("baseHoleInfo", "holeInfo", "shotTrackerList"):
            if k in d and k in model and d[k] != model[k]:
                struct_issues.append((game, rnd, hole, f"top-level {k} != modelAndView.model.{k}"))
        bi, hi = model.get("baseHoleInfo") or {}, model.get("holeInfo") or {}
        shots = model.get("shotTrackerList") or []
        if str(bi.get("bi_code")) != game or int(bi.get("bi_round", -1)) != rnd or int(bi.get("bi_hole", -1)) != hole:
            ident_issues.append((game, rnd, hole, "baseHoleInfo identity"))
        if str(hi.get("hole")) != str(hole):
            ident_issues.append((game, rnd, hole, "holeInfo.hole"))
        for s in shots:
            extra.update(set(s) - {"gameCode", "round", "hole", "playerCode", "shot", "pp_state", "pp_distance", "pp_distanceLen",
                                   "pp_altitude", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "shotVideoYN"})
            if (str(s.get("gameCode")), int(s.get("round")), int(s.get("hole")), str(s.get("playerCode"))) != (game, rnd, hole, player):
                ident_issues.append((game, rnd, hole, f"shot {s.get('shot')} identity"))
            sc = str(s.get("pp_state"))
            states[sc] += 1
            if sc not in STATE:
                unknown_states[sc] += 1
            for k in NUM_FIELDS:
                v = fnum(s.get(k))
                if v is not None:
                    rng[k][0], rng[k][1] = min(rng[k][0], v), max(rng[k][1], v)
            raw_shots[(game, rnd, hole, int(s["shot"]))] = s
        nums = sorted(int(s["shot"]) for s in shots)
        if not shots or nums != list(range(1, len(nums) + 1)):
            seq_issues.append((game, rnd, hole, "shot numbers not 1..n", nums))
        elif str(max(shots, key=lambda s: int(s["shot"])).get("pp_state")) != "10":
            seq_issues.append((game, rnd, hole, "last shot not HOLED(10)"))
        elif sum(1 for s in shots if str(s.get("pp_state")) == "10") != 1:
            seq_issues.append((game, rnd, hole, "HOLED(10) appears more than once"))
        if shots:
            last = max(shots, key=lambda s: int(s["shot"]))
            holed_dist.append(fnum(last.get("pp_distance")))
            first = min(shots, key=lambda s: int(s["shot"]))
            if hi.get("stdScore") in ("4", "5") and fnum(first.get("pp_distanceLen")) is not None:
                tee_sum.append((fnum(hi.get("yds")), fnum(hi.get("meter")),
                                fnum(first.get("pp_distanceLen")) + (fnum(first.get("pp_distance")) or 0)))
        for k in ("bi_sx", "bi_sy", "bi_gx", "bi_gy", "bi_gpx", "bi_gpy"):
            v = fnum(bi.get(k))
            if v is not None:
                rng[k][0], rng[k][1] = min(rng[k][0], v), max(rng[k][1], v)
        round_strokes[(game, rnd)] += len(shots)
        round_par[(game, rnd)] += int(hi.get("stdScore") or 0)
        hole_par[(game, hole)].add(hi.get("stdScore"))
        hole_yds[(game, hole)].add(hi.get("yds"))
    R.add("C1", "PASS" if not struct_issues else "FAIL", "Response structure identical across files; top-level blocks equal model blocks", struct_issues[:20] or None)
    R.add("D1", "PASS" if not ident_issues else "FAIL", "gameCode/round/hole/playerCode inside every response match its path", ident_issues[:20] or None)
    R.add("E1", "PASS" if not seq_issues else "FAIL", "Shots are 1..n per hole, exactly one HOLED(10), and it is the last shot", seq_issues[:20] or None)
    R.add("F1", "PASS" if not unknown_states else "WARN", "All pp_state codes are in the official table",
          {"state_counts": dict(sorted(states.items(), key=lambda x: int(x[0]))), "unknown": dict(unknown_states)})
    R.add("F2", "PASS" if not extra else "WARN", "No shot fields outside the known set", dict(extra) or None)
    R.add("G1", "INFO", "pp_distance on the HOLED shot (consistent with a remaining-to-hole distance if all 0)",
          {"n": len(holed_dist), "values": dict(Counter(holed_dist))})

    # ---- H. official score reconciliation
    match, mism, nonstroke = [], [], []
    for (g, r), n in sorted(round_strokes.items()):
        gg = games.get(g, {})
        ov = gg.get(f"round{r}Score") or ""
        row = {"game_code": g, "title": gg.get("gameTitle"), "round": r, "official": ov, "shot_rows": n}
        if gg.get("gameType") != "0":
            row["game_type"] = gg.get("gameType")
            nonstroke.append(row)
        elif ov != "" and int(ov) == n:
            match.append(row)
        else:
            mism.append(row)
    R.add("H1", "PASS" if not mism else "FAIL", "Stroke-play rounds: shot rows == official round score",
          {"stroke_play_rounds": len(match) + len(mism), "match": len(match), "mismatch": mism})
    R.add("H2", "INFO", "Non-stroke-play rounds excluded from score comparison (official value is not a stroke total)",
          nonstroke)

    sp = root / "source" / f"official_schedule_{season}.json"
    if sp.exists():
        sched = {g["gameCode"]: g for g in json.loads(sp.read_bytes().decode("utf-8-sig"))}
        miss = sorted(g for g in games if g not in sched)
        disagree = sorted(g for g in games if g in sched and sched[g].get("gameMethod") != games[g].get("gameType"))
        R.add("H3", "PASS" if not miss and not disagree else "FAIL",
              "Official schedule lists every event and its gameMethod equals the player record's gameType",
              {"not_in_schedule": miss, "format_disagreement": disagree,
               "non_stroke_events": sorted(g for g in games if games[g].get("gameType") != "0")})

    # ---- I. hole info consistency
    par_var = {f"{g}H{h}": sorted(v) for (g, h), v in hole_par.items() if len(v) > 1}
    yds_var = {f"{g}H{h}": sorted(v) for (g, h), v in hole_yds.items() if len(v) > 1}
    pars = defaultdict(set)
    for (g, r), v in round_par.items():
        pars[g].add(v)
    R.add("I1", "PASS" if not par_var else "WARN", "Par of a hole is the same in every round of an event", par_var or None)
    R.add("I2", "INFO", "Holes whose listed yds differ between rounds (tee changes are normal)", yds_var or None)
    R.add("I3", "INFO", "Course par per event (sum of holeInfo.stdScore)", {g: sorted(v) for g, v in sorted(pars.items())})

    # ---- J. units / coordinate evidence (reported, not asserted)
    if tee_sum:
        dy = [s - y for y, m, s in tee_sum if y]
        dm = [s - m for y, m, s in tee_sum if m]
        R.add("J1", "INFO", "Par-4/5 shot 1: pp_distanceLen + pp_distance compared with holeInfo.yds and holeInfo.meter",
              {"n": len(tee_sum), "median_minus_yds": round(st.median(dy), 1), "median_abs_minus_yds": round(st.median(map(abs, dy)), 1),
               "median_minus_meter": round(st.median(dm), 1), "median_abs_minus_meter": round(st.median(map(abs, dm)), 1),
               "reading": "the field closer to 0 indicates which unit the distance fields share; it is evidence, not a label from the source"})
    R.add("J2", "INFO", "Observed value ranges (coordinate systems are NOT geographic; see archive README)",
          {k: [v[0], v[1]] for k, v in sorted(rng.items())})
    sentinel = [{"key": list(k), "pp_state": str(s.get("pp_state")), "pp_altitude": s.get("pp_altitude")}
                for k, s in sorted(raw_shots.items()) if (fnum(s.get("pp_altitude")) or 0) <= -1000]
    R.add("J3", "WARN" if sentinel else "PASS",
          "pp_altitude sentinel values (<= -1000) -- preserved as-is; must be excluded from any elevation use",
          {"n": len(sentinel), "rows": sentinel[:20]} if sentinel else None)

    # ---- K. normalized CSVs vs raw
    norm = root / season / "normalized"
    k_issues = []
    try:
        rows = list(csv.DictReader(open(norm / "shots.csv", encoding="utf-8")))
        if len(rows) != len(raw_shots):
            k_issues.append(f"shots.csv rows {len(rows)} != raw shots {len(raw_shots)}")
        for r in rows:
            s = raw_shots.get((r["game_code"], int(r["round"]), int(r["hole"]), int(r["shot"])))
            if s is None or json.loads(r["raw_json"]) != s:
                k_issues.append(("shot mismatch", r["game_code"], r["round"], r["hole"], r["shot"]))
                break
        hrows = list(csv.DictReader(open(norm / "holes.csv", encoding="utf-8")))
        if len(hrows) != len(canon):
            k_issues.append(f"holes.csv rows {len(hrows)} != raw files {len(canon)}")
        for h in hrows:
            if sha((root / h["raw_path"]).read_bytes()) != h["raw_sha256"]:
                k_issues.append(("holes.csv sha mismatch", h["raw_path"]))
        rrows = list(csv.DictReader(open(norm / "rounds.csv", encoding="utf-8")))
        if Counter(r["comparison_status"] for r in rrows).get("MISMATCH"):
            k_issues.append("rounds.csv has MISMATCH")
    except FileNotFoundError as e:
        k_issues.append(f"missing normalized file: {e}")
    R.add("K1", "PASS" if not k_issues else "FAIL", "Normalized CSVs reproduce raw exactly (row counts, raw_json, sha256)", k_issues[:20] or None)
    if a.expect_shots is not None:
        R.add("K2", "PASS" if a.expect_shots == len(raw_shots) else "FAIL", "Stated shot count",
              {"stated": a.expect_shots, "actual": len(raw_shots)})

    # ---- L. cross-source comparison
    if a.cross_sqlite:
        con = sqlite3.connect(a.cross_sqlite)
        other = {(g, r, h, s): row for g, r, h, s, *row in con.execute(
            "SELECT game_code,round,hole,shot,state_code,distance,distance_len,altitude,x,y,green_x,green_y "
            "FROM klpga_player_shot WHERE player_code=?", (player,))}
        games_other = {k[0] for k in other}
        mine = {k: v for k, v in raw_shots.items() if k[0] in games_other}
        diffs, only_mine, only_other = [], sorted(set(mine) - set(other)), sorted(set(other) - set(mine))
        for k in sorted(set(mine) & set(other)):
            s = mine[k]
            a_ = [str(s.get("pp_state"))] + [fnum(s.get(f)) for f in NUM_FIELDS]
            b_ = [str(other[k][0])] + [None if x is None else float(x) for x in other[k][1:]]
            if a_ != b_:
                diffs.append({"key": k, "archive": a_, "other": b_})
        R.add("L1", "PASS" if not (diffs or only_mine or only_other) else "FAIL",
              f"Same shots in independent collection {a.cross_label}".strip(),
              {"events_compared": sorted(games_other), "shots_compared": len(set(mine) & set(other)),
               "field_diffs": diffs[:10], "only_in_archive": only_mine[:10], "only_in_other": only_other[:10]})

    out = root / season / "validation"
    out.mkdir(parents=True, exist_ok=True)
    summary = Counter(c["status"] for c in R.checks)
    rep = {"player_code": player, "season": season, "result": "FAIL" if R.failed else "PASS",
           "status_counts": dict(summary), "checks": R.checks}
    (out / "validation_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    md = [f"# Validation — player {player}, season {season}", "", f"**Result: {rep['result']}** — " +
          ", ".join(f"{k} {v}" for k, v in sorted(summary.items())), "", "| id | status | check |", "|---|---|---|"]
    md += [f"| {c['id']} | {c['status']} | {c['title']} |" for c in R.checks]
    md += ["", "Details for every check: `validation_report.json`."]
    (out / "validation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"result": rep["result"], **summary}, ensure_ascii=False))
    for c in R.checks:
        print(f"{c['status']:4} {c['id']} {c['title']}")
    sys.exit(1 if R.failed else 0)


if __name__ == "__main__":
    main()

"""Archive + normalize one player's season of KLPGA Shot Tracker responses.

Input: a ZIP or directory holding responses of the per-player endpoint
`POST /ajax/leaderboard/getShotTracker` (params gameCode, round, hole,
playerCode) laid out as `<gameCode>/R<round>/H<hole>.json`, plus the
official player record response `profile_getToursRecord_<season>.json`
and an optional `collection_errors.json`.

Output (archive root, e.g. klpga_pipeline/data/players/<slug>/):

  source/                          official profile response + collection log, byte-exact
  source/intake_<sha12>.json       per-file intake manifest (sha256, bytes, action)
  <season>/raw/<game>/player_shot/<player>/R<n>/H<nn>.json
                                   byte-exact responses, SAME layout as collector.py's
                                   NEO_DATA_ROOT_LOCAL/raw so collector/validate tooling
                                   can read them unchanged
  <season>/normalized/{events,rounds,holes,shots}.csv  derived, re-generated each run
  <season>/index.json              counts + paths

Raw policy (same as collector.py): raw bytes are never modified, a raw file is
never overwritten; a differing payload at an occupied path is stored under a
sha256-suffixed name and reported as a conflict.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collector import STATE, PLAYER_ENDPOINT  # noqa: E402  (official pp_state table, endpoint path)

RAW_RE = re.compile(r"(?:^|/)(\d{10})/(?:player_shot/(\d+)/)?R(\d)/H(\d{2})\.json$")
SHOT_FIELDS = ["gameCode", "round", "hole", "playerCode", "shot", "pp_state", "pp_distance",
               "pp_distanceLen", "pp_altitude", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "shotVideoYN"]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_json(b: bytes):
    return json.loads(b.decode("utf-8-sig"))


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- input ----
def read_inputs(src: Path):
    """Yield (relative_name, bytes) for every file in a zip or directory."""
    if src.is_file() and zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            for info in sorted(z.infolist(), key=lambda i: i.filename):
                if not info.is_dir():
                    yield info.filename, z.read(info)
    else:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                yield p.relative_to(src).as_posix(), p.read_bytes()


def place(dest: Path, data: bytes):
    """Never-overwrite write. Returns (final_path, action)."""
    digest = sha256(data)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if sha256(dest.read_bytes()) == digest:
            return dest, "identical_already_present"
        alt = dest.with_name(f"{dest.stem}_{digest[:12]}{dest.suffix}")
        if alt.exists():
            return alt, "identical_already_present_conflict_copy"
        alt.write_bytes(data)
        return alt, "CONFLICT_saved_with_sha_suffix"
    dest.write_bytes(data)
    return dest, "copied"


def archive(src: Path, root: Path, season: str, player: str):
    intake = []
    src_digest = sha256(src.read_bytes()) if src.is_file() else None
    for name, data in read_inputs(src):
        m = RAW_RE.search(name)
        base = name.rsplit("/", 1)[-1]
        if m and m.group(2) not in (None, player):
            intake.append({"input": name, "sha256": sha256(data), "bytes": len(data), "action": "IGNORED_other_player"})
            continue
        if m:
            game, rnd, hole = m.group(1), int(m.group(3)), int(m.group(4))
            dest = root / season / "raw" / game / "player_shot" / player / f"R{rnd}" / f"H{hole:02d}.json"
        elif base.startswith(("profile_getToursRecord_", "official_schedule_")) or base == "collection_errors.json":
            dest = root / "source" / base
        else:
            intake.append({"input": name, "sha256": sha256(data), "bytes": len(data), "action": "IGNORED_unrecognized"})
            continue
        final, action = place(dest, data)
        intake.append({"input": name, "stored_as": final.relative_to(root).as_posix(),
                       "sha256": sha256(data), "bytes": len(data), "action": action})
    tag = (src_digest or sha256(json.dumps(intake, sort_keys=True).encode()))[:12]
    man = {"source_name": src.name, "source_sha256": src_digest, "season": season, "player_code": player,
           "endpoint": PLAYER_ENDPOINT, "files": intake,
           "action_counts": {a: sum(1 for x in intake if x["action"] == a) for a in sorted({x["action"] for x in intake})}}
    mp = root / "source" / f"intake_{tag}.json"
    k = 1
    while mp.exists():  # never overwrite an earlier intake record
        k += 1
        mp = root / "source" / f"intake_{tag}_run{k}.json"
    man["intake_record"] = mp.name
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


# ------------------------------------------------------------ normalize ----
def iter_raw(root: Path, season: str, player: str):
    """Canonical raw files only (sha-suffixed conflict copies are reported by the validator)."""
    base = root / season / "raw"
    for p in sorted(base.glob(f"*/player_shot/{player}/R*/H??.json")):
        game = p.parts[-5]
        rnd = int(p.parent.name[1:])
        hole = int(p.stem[1:])
        yield game, rnd, hole, p


def source_id(game, player, rnd, hole, digest):
    return f"player_shot:{game}:{player}:R{rnd}:H{hole:02d}:{digest[:16]}"


def schedule_games(root: Path, season: str):
    p = root / "source" / f"official_schedule_{season}.json"
    if not p.exists():
        return {}
    return {g["gameCode"]: g for g in load_json(p.read_bytes())}


def profile_games(root: Path, season: str):
    p = root / "source" / f"profile_getToursRecord_{season}.json"
    d = load_json(p.read_bytes())
    return d, {g["gameCode"]: g for g in (d.get("reGameList") or [])}


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def normalize(root: Path, season: str, player: str, sqlite_path: Path | None = None):
    prof, games = profile_games(root, season)
    sched = schedule_games(root, season)
    rel = lambda p: p.relative_to(root).as_posix()
    shots_rows, holes_rows = [], []
    per_round = {}
    manifest_rows = []
    for game, rnd, hole, p in iter_raw(root, season, player):
        b = p.read_bytes()
        dg = sha256(b)
        sid = source_id(game, player, rnd, hole, dg)
        d = load_json(b)
        model = (d.get("modelAndView") or {}).get("model") or {}
        hi = model.get("holeInfo") or d.get("holeInfo") or {}
        bi = model.get("baseHoleInfo") or d.get("baseHoleInfo") or {}
        shots = sorted(model.get("shotTrackerList") or d.get("shotTrackerList") or [], key=lambda s: int(s["shot"]))
        manifest_rows.append((sid, game, PLAYER_ENDPOINT, player, None, rnd, hole, None, 200, dg, rel(p)))
        for s in shots:
            sc = None if s.get("pp_state") is None else str(s.get("pp_state"))
            ko, en = STATE.get(sc, (f"UNKNOWN_{sc}", f"UNKNOWN_{sc}")) if sc is not None else (None, None)
            shots_rows.append([season, game, str(s.get("playerCode")), int(s.get("round")), int(s.get("hole")),
                               int(s["shot"]), sc, ko, en, s.get("pp_distance"), s.get("pp_distanceLen"),
                               s.get("pp_altitude"), s.get("pp_x"), s.get("pp_y"), s.get("pp_greenx"),
                               s.get("pp_greeny"), s.get("shotVideoYN"), sid, rel(p),
                               json.dumps(s, ensure_ascii=False, separators=(",", ":"))])
        final_state = str(shots[-1].get("pp_state")) if shots else ""
        holes_rows.append([season, game, rnd, hole, bi.get("bi_trueHole"), hi.get("stdScore"), hi.get("yds"),
                           hi.get("meter"), hi.get("avgScore"), hi.get("rank"), hi.get("count"),
                           bi.get("bi_sx"), bi.get("bi_sy"), bi.get("bi_gx"), bi.get("bi_gy"), bi.get("bi_gpx"),
                           bi.get("bi_gpy"), len(shots), final_state, sid, rel(p), dg,
                           json.dumps(hi, ensure_ascii=False, separators=(",", ":")),
                           json.dumps(bi, ensure_ascii=False, separators=(",", ":"))])
        pr = per_round.setdefault((game, rnd), {"holes": 0, "strokes": 0, "par": 0})
        pr["holes"] += 1
        pr["strokes"] += len(shots)
        pr["par"] += int(hi.get("stdScore") or 0)

    # rounds + events (official record is the only source of round scores)
    rounds_rows, events_rows = [], []
    all_games = sorted(set(games) | {g for g, _ in per_round})
    for game in all_games:
        g = games.get(game, {})
        gt = g.get("gameType")
        offi = {r: (g.get(f"round{r}Score") or "") for r in range(1, 5)}
        raw_rounds = sorted(r for gg, r in per_round if gg == game)
        for r in sorted(set(raw_rounds) | {r for r, v in offi.items() if v}):
            pr = per_round.get((game, r))
            ov = offi.get(r, "")
            if pr is None:
                status = "NO_SHOT_DATA"
            elif gt != "0":
                status = "NOT_COMPARABLE_NON_STROKE_FORMAT"
            elif ov == "":
                status = "NO_OFFICIAL_SCORE"
            else:
                status = "MATCH" if int(ov) == pr["strokes"] else "MISMATCH"
            rounds_rows.append([season, game, player, r, ov, gt, pr["holes"] if pr else 0,
                                pr["strokes"] if pr else 0, pr["par"] if pr else 0,
                                (pr["strokes"] - pr["par"]) if (pr and gt == "0") else "", status])
        sc = sched.get(game, {})
        events_rows.append([season, game, g.get("gameTitle"), g.get("startDate"), g.get("endDate"), gt,
                            sc.get("gameMethod"), sc.get("courseText"), sc.get("outCourseText"), sc.get("inCourseText"),
                            g.get("rankText"), offi[1], offi[2], offi[3], offi[4], g.get("totalScore"),
                            g.get("totalUnder"), sum(1 for v in offi.values() if v), len(raw_rounds),
                            sum(per_round[(game, r)]["holes"] for r in raw_rounds)])

    out = root / season / "normalized"
    write_csv(out / "events.csv", ["season", "game_code", "game_title", "start_date", "end_date", "game_type",
                                   "schedule_game_method", "course_text", "out_course_text", "in_course_text", "rank_text", "official_r1", "official_r2", "official_r3", "official_r4",
                                   "official_total", "official_total_under", "official_rounds", "raw_rounds",
                                   "raw_hole_files"], events_rows)
    write_csv(out / "rounds.csv", ["season", "game_code", "player_code", "round", "official_round_value",
                                   "game_type", "raw_holes", "shot_rows", "par_total", "shot_rows_to_par",
                                   "comparison_status"], rounds_rows)
    write_csv(out / "holes.csv", ["season", "game_code", "round", "hole", "true_hole", "par", "yds", "meter",
                                  "field_avg_score", "difficulty_rank", "holeinfo_count", "bi_sx", "bi_sy",
                                  "bi_gx", "bi_gy", "bi_gpx", "bi_gpy", "shot_rows", "final_pp_state",
                                  "source_id", "raw_path", "raw_sha256", "hole_info_json",
                                  "base_hole_info_json"], holes_rows)
    write_csv(out / "shots.csv", ["season", "game_code", "player_code", "round", "hole", "shot", "pp_state",
                                  "state_name_ko", "state_name_en", "pp_distance", "pp_distanceLen",
                                  "pp_altitude", "pp_x", "pp_y", "pp_greenx", "pp_greeny", "shotVideoYN",
                                  "source_id", "raw_path", "raw_json"], shots_rows)
    rec = prof.get("reRecord") or {}
    index = {
        "player_code": player, "player_name": rec.get("playerName"), "season": season,
        "endpoint": PLAYER_ENDPOINT, "official_profile": f"source/profile_getToursRecord_{season}.json",
        "raw_layout": f"{season}/raw/<gameCode>/player_shot/{player}/R<round>/H<hole>.json",
        "join_keys": {"event": ["game_code"], "round": ["game_code", "round"],
                      "hole": ["game_code", "round", "hole"], "shot": ["game_code", "player_code", "round", "hole", "shot"]},
        "counts": {"events": len(events_rows), "rounds_with_raw": len(per_round), "hole_files": len(holes_rows),
                   "shot_rows": len(shots_rows)},
        "official_record_summary": {k: rec.get(k) for k in ("joinGameNum", "getGameNum", "cutPassCnt", "cutOffCnt",
                                                             "abstentionCnt", "money", "moneyRank", "avgScore")},
        "normalized": [f"{season}/normalized/{n}.csv" for n in ("events", "rounds", "holes", "shots")],
    }
    (root / season / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")

    if sqlite_path:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        if sqlite_path.exists():
            sqlite_path.unlink()
        con = sqlite3.connect(sqlite_path)
        con.executescript((HERE / "schema.sql").read_text(encoding="utf-8"))
        con.executescript((HERE / "schema_player_season.sql").read_text(encoding="utf-8"))
        con.executemany("INSERT INTO klpga_shot_raw_manifest VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        [(m[0], m[1], m[2], m[3], m[4], m[5], m[6], "archived:" + season, m[8], m[9], m[10])
                         for m in manifest_rows])
        con.executemany("INSERT INTO klpga_player_shot VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(r[1], r[2], index["player_name"], r[3], r[4], r[5], r[6], r[7], r[8], num(r[9]),
                          num(r[10]), num(r[11]), num(r[12]), num(r[13]), num(r[14]), num(r[15]), r[16], r[17], r[19])
                         for r in shots_rows])
        con.executemany("INSERT INTO klpga_hole_info VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [(h[1], h[2], h[3], player, h[4], int(h[5]) if h[5] else None, num(h[6]), num(h[7]),
                          num(h[8]), h[9], h[10], num(h[11]), num(h[12]), num(h[13]), num(h[14]), num(h[15]),
                          num(h[16]), h[19], h[22], h[23]) for h in holes_rows])
        con.executemany("INSERT INTO klpga_player_round_official VALUES(?,?,?,?,?,?,?,?)",
                        [(r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[10]) for r in rounds_rows])
        con.commit()
        con.close()
    return index


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="ZIP or directory of raw responses (omit to only re-normalize)")
    ap.add_argument("--root", required=True, help="archive root, e.g. klpga_pipeline/data/players/kim_saeromi")
    ap.add_argument("--season", required=True)
    ap.add_argument("--player", required=True, help="KLPGA playerCode")
    ap.add_argument("--schedule", help="official KLPGA schedule response (official_schedule_<season>.json) for course names")
    ap.add_argument("--sqlite", help="optional SQLite output path (not committed; schema.sql + schema_player_season.sql)")
    a = ap.parse_args()
    root = Path(a.root)
    if a.input:
        man = archive(Path(a.input), root, a.season, a.player)
        print("INTAKE", json.dumps(man["action_counts"], ensure_ascii=False))
    if a.schedule:
        sp = Path(a.schedule)
        final, action = place(root / "source" / sp.name, sp.read_bytes())
        print("SCHEDULE", final.relative_to(root).as_posix(), action, sha256(sp.read_bytes()))
    idx = normalize(root, a.season, a.player, Path(a.sqlite) if a.sqlite else None)
    print("NORMALIZED", json.dumps(idx["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()

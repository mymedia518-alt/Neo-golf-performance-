"""Synthetic-fixture tests for player_season_archive.py / validate_player_season.py.

Run: python -m pytest neo_klpga_shot_source/tests -q
"""
import csv
import json
import subprocess
import sys
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC))
import player_season_archive as psa  # noqa: E402

GAME, PLAYER, SEASON = "2099010001", "1234", "2099"


def hole_response(rnd, hole, n_shots, par=4):
    shots = []
    for i in range(1, n_shots + 1):
        last = i == n_shots
        shots.append({"pp_greeny": "1", "pp_greenx": "2", "playerCode": PLAYER, "shotVideoYN": "N",
                      "pp_x": str(10 + i), "pp_y": str(20 + i), "shot": i, "hole": hole,
                      "pp_distance": "0.0" if last else str(100 - i), "round": rnd,
                      "pp_state": "10" if last else "1", "pp_distanceLen": "50.0", "pp_altitude": "0.0",
                      "gameCode": GAME})
    bi = {"bi_hole": hole, "bi_gpy": "1", "bi_sy": "2", "bi_gpx": "3", "bi_sx": "4", "bi_gy": "5",
          "bi_code": GAME, "bi_round": rnd, "bi_trueHole": str(hole), "bi_gx": "6"}
    hi = {"hole": str(hole), "stdScore": str(par), "avgScore": "4.1", "meter": "350", "count": 1, "rank": 1, "yds": "383"}
    return {"baseHoleInfo": bi, "holeInfo": hi, "shotTrackerList": shots, "properties": {},
            "modelAndView": {"view": None, "model": {"baseHoleInfo": bi, "holeInfo": hi, "shotTrackerList": shots},
                             "status": None, "empty": False, "viewName": None, "modelMap": {}, "reference": False}}


def build_zip(tmp, round_scores):
    z = tmp / "in.zip"
    profile = {"reRecord": {"playerName": "테스트", "joinGameNum": "1"},
               "reGameList": [{"gameCode": GAME, "gameTitle": "T", "gameType": "0", "startDate": "20990101",
                               "endDate": "20990104", "rankText": "1",
                               **{f"round{r}Score": str(round_scores.get(r, "")) for r in range(1, 5)}}]}
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("x/profile_getToursRecord_2099.json", json.dumps(profile, ensure_ascii=False))
        zf.writestr("x/collection_errors.json", "[]")
        for rnd, score in round_scores.items():
            per = [4] * 18
            per[0] += score - 72
            for h in range(1, 19):
                zf.writestr(f"x/{GAME}/R{rnd}/H{h:02d}.json", json.dumps(hole_response(rnd, h, per[h - 1])))
    return z


def run_validate(root):
    return subprocess.run([sys.executable, str(SRC / "validate_player_season.py"), "--root", str(root),
                           "--season", SEASON, "--player", PLAYER], capture_output=True, text=True)


def test_archive_normalize_validate_pass(tmp_path):
    z = build_zip(tmp_path, {1: 70, 2: 73})
    root = tmp_path / "arch"
    man = psa.archive(z, root, SEASON, PLAYER)
    assert man["action_counts"] == {"copied": 38}
    idx = psa.normalize(root, SEASON, PLAYER, tmp_path / "t.sqlite")
    assert idx["counts"] == {"events": 1, "rounds_with_raw": 2, "hole_files": 36, "shot_rows": 143}
    rounds = list(csv.DictReader(open(root / SEASON / "normalized" / "rounds.csv", encoding="utf-8")))
    assert {r["comparison_status"] for r in rounds} == {"MATCH"}
    r = run_validate(root)
    assert r.returncode == 0, r.stdout + r.stderr


def test_rearchive_is_idempotent_and_never_overwrites(tmp_path):
    z = build_zip(tmp_path, {1: 70})
    root = tmp_path / "arch"
    psa.archive(z, root, SEASON, PLAYER)
    again = psa.archive(z, root, SEASON, PLAYER)
    assert again["action_counts"] == {"identical_already_present": 20}
    target = root / SEASON / "raw" / GAME / "player_shot" / PLAYER / "R1" / "H01.json"
    original = target.read_bytes()
    z2 = tmp_path / "changed.zip"
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr(f"x/{GAME}/R1/H01.json", json.dumps(hole_response(1, 1, 5)))
    m = psa.archive(z2, root, SEASON, PLAYER)
    assert m["action_counts"] == {"CONFLICT_saved_with_sha_suffix": 1}
    assert target.read_bytes() == original  # canonical file untouched


def test_accepts_collector_layout_and_skips_other_players(tmp_path):
    src = tmp_path / "NEO_DATA_ROOT_LOCAL" / "raw"
    for player in (PLAYER, "9999"):
        p = src / GAME / "player_shot" / player / "R1" / "H01.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(hole_response(1, 1, 4)))
    man = psa.archive(src, tmp_path / "arch", SEASON, PLAYER)
    assert man["action_counts"] == {"IGNORED_other_player": 1, "copied": 1}


def test_score_mismatch_fails_validation(tmp_path):
    z = build_zip(tmp_path, {1: 70})
    root = tmp_path / "arch"
    psa.archive(z, root, SEASON, PLAYER)
    prof = root / "source" / "profile_getToursRecord_2099.json"
    d = json.loads(prof.read_text(encoding="utf-8"))
    d["reGameList"][0]["round1Score"] = "71"  # official says 71, shots say 70
    prof.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    psa.normalize(root, SEASON, PLAYER)
    r = run_validate(root)
    assert r.returncode == 1 and "FAIL H1" in r.stdout

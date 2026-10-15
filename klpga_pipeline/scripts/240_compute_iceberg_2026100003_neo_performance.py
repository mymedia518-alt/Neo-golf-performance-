"""Compute NEO 경기력 (NEO performance band) for every official entrant of
아이스버그골프·서울신문 오픈 (game_code 2026100003) and reflect it into the
existing PRE data structure (2026100003_ENTRY_KRANKING_JOIN.json, built by
scripts/237 and already consumed by scripts/238's PRE page).

Reuses, unmodified, the SAME NEO 경기력 formula already live on this branch
for the current real tournament -- klpga.neo_win.hitejinro_player_metrics.
load_current_form_by_id() / neo_band_by_id() (0.35/0.25/0.25/-0.10 weighted
z-score over recent_5_sg/recent_10_sg/long_term_sg/volatility, quintile-
banded, documented in docs/NEO_RANKING_V1_REDTEAM_BACKTEST.md). No new
model, no estimated/fabricated value: a player whose own committed
content/website_v2/knowledge_engine/player_intelligence/<id>/latest.json
is missing or has any null current_form field is honestly left without a
band, with the specific reason recorded per player (no document at all vs.
which field(s) are null).

Tournament format: this build makes NO Stableford/round-count/cut-rule
claim anywhere (same as scripts/238's own page) -- this script only adds
NEO 경기력 fields; round format and cut status are handled, and reported
on, separately per the operator's own instruction.

Field added to each of the 108 records in 2026100003_ENTRY_KRANKING_JOIN.json:
  neo_performance_band            : one of 최상위/상위/중위/하위/최하위, or null
  neo_performance_score           : the real raw weighted z-score composite, or null
  neo_performance_as_of           : that player's own current_form document's
                                     _meta.generated_at (the real date the
                                     underlying data was last computed) -- never
                                     today's date, never fabricated
  neo_performance_metrics_used    : ["recent_5_sg","recent_10_sg","long_term_sg","volatility"]
                                     when banded, else []
  neo_performance_missing_reason  : null when banded, else one of
                                     "NO_DOCUMENT" (no player_intelligence/<id>/latest.json)
                                     or "INCOMPLETE_CURRENT_FORM: missing <fields>"
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.hitejinro_player_metrics import (  # noqa: E402
    NEO_BAND_FEATURES,
    NEO_BAND_WEIGHTS,
    PLAYER_INTELLIGENCE_DIR,
    load_current_form_by_id,
    neo_band_by_id,
)

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"


def _missing_reason(pid: str) -> str:
    path = PLAYER_INTELLIGENCE_DIR / pid / "latest.json"
    if not path.is_file():
        return "NO_DOCUMENT"
    doc = json.loads(path.read_text(encoding="utf-8"))
    cf = doc.get("current_form") or {}
    nulls = [f for f in NEO_BAND_FEATURES if cf.get(f) is None]
    return f"INCOMPLETE_CURRENT_FORM: missing {nulls}"


def _as_of(pid: str) -> str | None:
    path = PLAYER_INTELLIGENCE_DIR / pid / "latest.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return (doc.get("_meta") or {}).get("generated_at")


def _independent_arithmetic_check(current_form_by_id: dict[str, dict], band_by_id: dict[str, tuple[str, float]]) -> list[str]:
    """Re-derives the exact same weighted z-score composite from raw
    current_form inputs via a second, independent code path (not calling
    neo_band_by_id again) and compares it to that function's own output
    for every banded player -- proves the persisted value is the real,
    correctly-computed composite, not a silently corrupted or
    independently-drifted number."""
    problems = []
    means = {f: statistics.mean(cf[f] for cf in current_form_by_id.values()) for f in NEO_BAND_FEATURES}
    stdevs = {f: statistics.pstdev(cf[f] for cf in current_form_by_id.values()) or 1.0 for f in NEO_BAND_FEATURES}
    for pid, cf in current_form_by_id.items():
        recomputed = sum(NEO_BAND_WEIGHTS[f] * ((cf[f] - means[f]) / stdevs[f]) for f in NEO_BAND_FEATURES)
        _, published = band_by_id[pid]
        if abs(recomputed - published) > 1e-9:
            problems.append(f"{pid}: independently recomputed {recomputed!r} != published {published!r}")
    return problems


def main() -> None:
    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    records = join["records"]
    assert len(records) == 108, f"expected exactly 108 official entries, found {len(records)}"

    ids = [r["player_code"] for r in records]
    assert len(set(ids)) == len(ids), "duplicate player_code in ENTRY_KRANKING_JOIN records"

    current_form_by_id = load_current_form_by_id(ids)
    band_by_id = neo_band_by_id(current_form_by_id)

    arithmetic_problems = _independent_arithmetic_check(current_form_by_id, band_by_id)

    banded = 0
    missing = 0
    missing_detail = []
    for r in records:
        pid = r["player_code"]
        if pid in band_by_id:
            label, score = band_by_id[pid]
            r["neo_performance_band"] = label
            r["neo_performance_score"] = round(score, 6)
            r["neo_performance_as_of"] = _as_of(pid)
            r["neo_performance_metrics_used"] = list(NEO_BAND_FEATURES)
            r["neo_performance_missing_reason"] = None
            banded += 1
        else:
            reason = _missing_reason(pid)
            r["neo_performance_band"] = None
            r["neo_performance_score"] = None
            r["neo_performance_as_of"] = _as_of(pid)
            r["neo_performance_metrics_used"] = []
            r["neo_performance_missing_reason"] = reason
            missing += 1
            missing_detail.append({"player_code": pid, "player_name": r["player_name"], "reason": reason})

    assert banded + missing == 108

    join["neo_performance_computed_at"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    join["neo_performance_source"] = (
        "klpga.neo_win.hitejinro_player_metrics.load_current_form_by_id/neo_band_by_id "
        "(same formula already live for the current real tournament; 0.35/0.25/0.25/-0.10 "
        "weighted z-score over recent_5_sg/recent_10_sg/long_term_sg/volatility, quintile-banded "
        "across this tournament's own 108-player field). No new model, no estimated values."
    )
    JOIN_PATH.write_text(json.dumps(join, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    overall_pass = (
        len(records) == 108
        and len(set(ids)) == 108
        and banded + missing == 108
        and not arithmetic_problems
    )

    report = {
        "game_code": GAME_CODE,
        "field_size_check": {"expected": 108, "actual": len(records), "pass": len(records) == 108},
        "duplicate_check": {"duplicate_count": len(ids) - len(set(ids)), "pass": len(set(ids)) == len(ids)},
        "coverage_check": {"banded": banded, "missing": missing, "total": banded + missing, "pass": banded + missing == 108},
        "arithmetic_check": {"problems": arithmetic_problems, "pass": not arithmetic_problems},
        "missing_detail": missing_detail,
        "overall": "PASS" if overall_pass else "FAIL",
        "written": str(JOIN_PATH),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

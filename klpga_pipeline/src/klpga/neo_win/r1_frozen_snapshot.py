"""BETA #001 R1 -> R2 evaluation pipeline, Section A: the frozen R1
INPUT CONTRACT this whole evaluation is built on.

======================================================================
NEVER RECALCULATED — READ-ONLY AGAINST EVERY REAL FROZEN FILE
======================================================================
Every function here only READS an already-frozen artifact; nothing in
this module opens a frozen prediction file for writing, and nothing
here re-derives a WIN%/MAKE CUT% value. The source-discovery order
below matches `scripts/42_record_tournament_history.py`'s own
established "prefer #001-C" convention exactly, extended with one
additional, MORE authoritative tier on top (the already-hash-verified
`neo_tournament_history/<game_code>/R1.json` record, if one has already
been recorded via that script) and one additional, LESS authoritative
fallback tier at the bottom (`outputs/beta001_r1/BETA001_R1_FULL.csv`,
scripts/35's own plain CSV export, kept only as a last resort since it
carries no leakage/provenance metadata of its own):

  1. TOURNAMENT_HISTORY_R1  — neo_tournament_history/<game_code>/R1.json
                               (klpga.neo_win.tournament_history's own
                               effective record; already SHA256-verified
                               against its source by scripts/42).
  2. RAW_NEO_WIN_001_C_R1_JSON — neo_win_predictions/*/neo_win_001-C-R1_<game_code>.json
  3. RAW_NEO_WIN_001_R1_JSON   — neo_win_predictions/*/neo_win_001-R1_<game_code>.json
                               (legacy prediction_id, same file family
                               klpga.neo_win.round_update_archive writes).
  4. OUTPUTS_BETA001_R1_FULL_CSV — outputs/beta001_r1/BETA001_R1_FULL.csv

If NONE of the four exist, this module reports SOURCE_NONE — it never
fabricates a predictions.csv from the published HTML alone. The public
docs/index.html / docs/tournaments/.../r1/index.html table has no
player_code column, and player_name is never a safe join key on its
own (project-wide identity rule) — so the published HTML is usable
ONLY as a secondary sanity check (rank/score/WIN%/CUT% agreement)
against a real, player_code-keyed source that was already found by one
of the four tiers above, never as a source of identity by itself.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.neo_win.tournament_history import (
    STAGE_R1,
    STATUS_HISTORICAL_SNAPSHOT_MISSING,
    read_effective_history_stage,
)

SOURCE_TOURNAMENT_HISTORY = "TOURNAMENT_HISTORY_R1"
SOURCE_RAW_R1_C = "RAW_NEO_WIN_001_C_R1_JSON"
SOURCE_RAW_R1_LEGACY = "RAW_NEO_WIN_001_R1_JSON"
SOURCE_CSV_FALLBACK = "OUTPUTS_BETA001_R1_FULL_CSV"
SOURCE_NONE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class PlayerR1Frozen:
    tournament_id: str
    player_code: str
    player_name: str
    r1_actual_rank: Optional[int]
    r1_actual_score_to_par: Optional[float]
    r1_win_probability_pct: Optional[float]
    r1_make_cut_probability_pct: Optional[float]
    model_version: str
    prediction_generated_at: str


def _find_one(root: Path, game_code: str, name_prefix: str) -> Optional[Path]:
    """Same glob convention as scripts/42_record_tournament_history.py's
    own `_find_one` (duplicated intentionally rather than imported: that
    script has no importable module surface, only a `main()` CLI)."""
    if not root.exists():
        return None
    matches = sorted(root.glob(f"*/{name_prefix}_{game_code}.json"))
    return matches[0] if matches else None


def locate_frozen_r1_source(
    game_code: str,
    *,
    history_dir: Path,
    predictions_dir: Path,
    outputs_csv_path: Path,
) -> tuple[str, Optional[Path]]:
    """Real-file discovery only, in the module docstring's documented
    tier order. Never fabricates a path — a missing tier simply falls
    through to the next; SOURCE_NONE + None means all four were
    genuinely absent."""
    history_path = Path(history_dir) / game_code / f"{STAGE_R1}.json"
    if history_path.exists():
        effective = read_effective_history_stage(Path(history_dir), game_code, STAGE_R1)
        if effective is not None and effective.status != STATUS_HISTORICAL_SNAPSHOT_MISSING:
            return SOURCE_TOURNAMENT_HISTORY, history_path

    r1_c_path = _find_one(Path(predictions_dir), game_code, "neo_win_001-C-R1")
    if r1_c_path is not None:
        return SOURCE_RAW_R1_C, r1_c_path

    r1_legacy_path = _find_one(Path(predictions_dir), game_code, "neo_win_001-R1")
    if r1_legacy_path is not None:
        return SOURCE_RAW_R1_LEGACY, r1_legacy_path

    if Path(outputs_csv_path).exists():
        return SOURCE_CSV_FALLBACK, Path(outputs_csv_path)

    return SOURCE_NONE, None


def _load_from_tournament_history(history_dir: Path, game_code: str) -> list[PlayerR1Frozen]:
    effective = read_effective_history_stage(Path(history_dir), game_code, STAGE_R1)
    if effective is None:
        return []
    return [
        PlayerR1Frozen(
            tournament_id=game_code,
            player_code=e.player_code,
            player_name=e.player_name,
            r1_actual_rank=e.position,
            r1_actual_score_to_par=e.score_to_par,
            r1_win_probability_pct=e.win_pct,
            r1_make_cut_probability_pct=e.make_cut_pct,
            model_version=effective.source_model_version,
            prediction_generated_at=effective.source_generated_at_utc,
        )
        for e in effective.entrants
    ]


def _load_from_raw_round_update_json(path: Path, game_code: str) -> list[PlayerR1Frozen]:
    """`path` is a klpga.neo_win.round_update_archive.RoundUpdateSnapshot's
    own JSON file (that module has no dedicated reader — this reads the
    same, already-documented, stable shape its own `snapshot_to_dict`
    produces, same convention klpga.neo_win.tournament_history.
    history_entry_from_round_update_dict already uses)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        PlayerR1Frozen(
            tournament_id=game_code,
            player_code=p["player_code"],
            player_name=p["player_name"],
            r1_actual_rank=p.get("r1_position"),
            r1_actual_score_to_par=p.get("r1_score_to_par"),
            r1_win_probability_pct=p.get("post_r1_win_pct"),
            r1_make_cut_probability_pct=p.get("post_r1_make_cut_pct"),
            model_version=data.get("prediction_id", "unknown"),
            prediction_generated_at=data.get("created_at_utc", ""),
        )
        for p in data.get("predictions", [])
    ]


def _to_float(value: str) -> Optional[float]:
    value = value.strip()
    return float(value) if value != "" else None


def _load_from_csv(path: Path, game_code: str) -> list[PlayerR1Frozen]:
    """`path` is scripts/35_predict_neo_win_post_r1.py's own
    BETA001_R1_FULL.csv output — has no explicit model_version/
    generated_at columns of its own, so both are reported as
    "unknown"/"" (never guessed) rather than borrowed from elsewhere."""
    rows: list[PlayerR1Frozen] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                PlayerR1Frozen(
                    tournament_id=game_code,
                    player_code=row["player_code"],
                    player_name=row["player_name"],
                    r1_actual_rank=int(row["r1_position"]) if row.get("r1_position") else None,
                    r1_actual_score_to_par=_to_float(row["r1_score_to_par"]) if row.get("r1_score_to_par") is not None else None,
                    r1_win_probability_pct=_to_float(row["post_r1_win_pct"]) if row.get("post_r1_win_pct") is not None else None,
                    r1_make_cut_probability_pct=_to_float(row["post_r1_make_cut_pct"]) if row.get("post_r1_make_cut_pct") is not None else None,
                    model_version="unknown",
                    prediction_generated_at="",
                )
            )
    return rows


def load_frozen_r1_snapshot(
    game_code: str,
    *,
    history_dir: Path,
    predictions_dir: Path,
    outputs_csv_path: Path,
) -> tuple[list[PlayerR1Frozen], dict]:
    """Returns (rows, provenance). `provenance["source"]` is one of the
    SOURCE_* constants; `provenance["source_path"]` is the real file
    read (or None for SOURCE_NONE). `rows` is [] iff SOURCE_NONE — an
    empty frozen snapshot is never silently treated as "0 players"; the
    caller must check `provenance["source"]` first."""
    source, path = locate_frozen_r1_source(
        game_code, history_dir=history_dir, predictions_dir=predictions_dir, outputs_csv_path=outputs_csv_path
    )
    if source == SOURCE_TOURNAMENT_HISTORY:
        rows = _load_from_tournament_history(history_dir, game_code)
    elif source == SOURCE_RAW_R1_C or source == SOURCE_RAW_R1_LEGACY:
        rows = _load_from_raw_round_update_json(path, game_code)
    elif source == SOURCE_CSV_FALLBACK:
        rows = _load_from_csv(path, game_code)
    else:
        rows = []
    return rows, {"source": source, "source_path": str(path) if path else None, "n_players": len(rows)}


# ----------------------------------------------------------------
# predictions.csv writer — idempotent (identical re-write is a no-op),
# refuses to silently overwrite a materially different existing file.
# ----------------------------------------------------------------

_CSV_FIELDNAMES: tuple[str, ...] = (
    "tournament_id", "player_code", "player_name", "r1_actual_rank", "r1_actual_score_to_par",
    "r1_win_probability_pct", "r1_make_cut_probability_pct", "model_version", "prediction_generated_at",
)


def _row_to_csv_dict(r: PlayerR1Frozen) -> dict:
    return {
        "tournament_id": r.tournament_id,
        "player_code": r.player_code,
        "player_name": r.player_name,
        "r1_actual_rank": "" if r.r1_actual_rank is None else r.r1_actual_rank,
        "r1_actual_score_to_par": "" if r.r1_actual_score_to_par is None else r.r1_actual_score_to_par,
        "r1_win_probability_pct": "" if r.r1_win_probability_pct is None else r.r1_win_probability_pct,
        "r1_make_cut_probability_pct": "" if r.r1_make_cut_probability_pct is None else r.r1_make_cut_probability_pct,
        "model_version": r.model_version,
        "prediction_generated_at": r.prediction_generated_at,
    }


def write_r1_predictions_csv(rows: list[PlayerR1Frozen], out_path: Path) -> str:
    """Writes `out_path` (creating parent directories as needed). If
    `out_path` already exists, the new content is compared byte-for-byte
    against the old before writing anything: identical content is a
    silent no-op ("NO_CHANGE"); different content raises — this is a
    frozen input contract, never silently replaced with a different
    snapshot. Returns one of "WRITTEN" / "NO_CHANGE"."""
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(_row_to_csv_dict(r))
    new_content = buf.getvalue()

    out_path = Path(out_path)
    if out_path.exists():
        existing = out_path.read_text(encoding="utf-8")
        if existing == new_content:
            return "NO_CHANGE"
        raise ValueError(
            f"{out_path} already exists with DIFFERENT content — refusing to overwrite a frozen R1 input "
            "contract. Delete it explicitly first if you intend to replace it with a new snapshot."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_content, encoding="utf-8")
    return "WRITTEN"


# ----------------------------------------------------------------
# Published-HTML cross-check — sanity validation ONLY, never an
# identity source. Matches by rank (the HTML's only stable row key),
# never by name.
# ----------------------------------------------------------------

_HTML_ROW_RE = re.compile(
    r'<tr><td class="c-pos">(\d+)</td><td class="c-name">([^<]*)</td>'
    r'<td class="c-score">([^<]*)</td><td class="c-pct">([^<]*)</td>'
    r'<td class="c-pct">([^<]*)</td></tr>'
)


def _parse_score_to_par(text: str) -> Optional[float]:
    text = text.strip()
    if text == "E":
        return 0.0
    if text == "":
        return None
    return float(text)


def _parse_pct(text: str) -> Optional[float]:
    text = text.strip().rstrip("%")
    return float(text) if text != "" else None


def parse_published_r1_html(html_text: str) -> list[dict]:
    """Extracts {rank, player_name, score_to_par, win_pct, make_cut_pct}
    per row from the published docs/index.html R1 table markup. Returns
    [] if the expected `<tr><td class="c-pos">...` pattern is not
    found at all (a real structural mismatch — never silently ignored
    by the caller, who must check for an empty result)."""
    rows = []
    for m in _HTML_ROW_RE.finditer(html_text):
        rank_text, name, score_text, win_text, cut_text = m.groups()
        rows.append(
            {
                "rank": int(rank_text),
                "player_name": name,
                "score_to_par": _parse_score_to_par(score_text),
                "win_pct": _parse_pct(win_text),
                "make_cut_pct": _parse_pct(cut_text),
            }
        )
    return rows


def validate_rows_against_published_html(
    rows: list[PlayerR1Frozen], html_rows: list[dict], *, tolerance_pct: float = 0.01
) -> dict:
    """Cross-checks each frozen row against the published HTML row at
    the SAME rank (never by name). Reports every mismatch explicitly;
    never silently accepts a discrepancy. `mismatches` is [] only if
    every rank present in both sides agrees on name/score/WIN%/CUT%
    within `tolerance_pct`."""
    by_rank_html = {r["rank"]: r for r in html_rows}
    by_rank_frozen = {r.r1_actual_rank: r for r in rows if r.r1_actual_rank is not None}

    mismatches = []
    for rank, h in by_rank_html.items():
        f = by_rank_frozen.get(rank)
        if f is None:
            mismatches.append({"rank": rank, "reason": "PRESENT_IN_HTML_MISSING_FROM_FROZEN_SOURCE"})
            continue
        if f.player_name != h["player_name"]:
            mismatches.append({"rank": rank, "reason": "NAME_MISMATCH", "frozen": f.player_name, "html": h["player_name"]})
            continue
        for field_name, frozen_value, html_value in (
            ("score_to_par", f.r1_actual_score_to_par, h["score_to_par"]),
            ("win_pct", f.r1_win_probability_pct, h["win_pct"]),
            ("make_cut_pct", f.r1_make_cut_probability_pct, h["make_cut_pct"]),
        ):
            if frozen_value is None or html_value is None:
                if frozen_value != html_value:
                    mismatches.append({"rank": rank, "reason": f"{field_name.upper()}_NULL_MISMATCH", "frozen": frozen_value, "html": html_value})
                continue
            if abs(frozen_value - html_value) > tolerance_pct:
                mismatches.append({"rank": rank, "reason": f"{field_name.upper()}_VALUE_MISMATCH", "frozen": frozen_value, "html": html_value})

    ranks_only_in_frozen = sorted(set(by_rank_frozen) - set(by_rank_html))
    return {
        "n_html_rows": len(html_rows),
        "n_frozen_rows": len(rows),
        "n_ranks_compared": len(by_rank_html),
        "mismatches": mismatches,
        "ranks_only_in_frozen_source": ranks_only_in_frozen,
        "valid": len(mismatches) == 0,
    }

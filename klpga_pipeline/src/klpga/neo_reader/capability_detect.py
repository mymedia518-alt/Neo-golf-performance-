"""Content-based capability detection for archived raw/<game_code>/*
files -- classification by what an existing parser can ACTUALLY
consume, never by filename. A file named "leaderboard.html" whose real
bytes match the confirmed roundLeaderboard fragment shape is
"parser_exists" because parse_round_leaderboard_html genuinely parses
it, not "parser_missing" because its name isn't "round_leaderboard_
r<n>.html" -- and a file that merely LOOKS like it should hold
tournament info but fails every real parser's actual contract is
honestly "parser_missing", regardless of its name.

Shared by neo_reader.sync.run_sync_offline (finding each stage's real
input file, so it never hard-requires one specific archive_raw
filename) and neo_reader.cli export-raw (the MANIFEST.json
classification) -- the exact same probe, so the two call sites can
never disagree about what a given file's bytes actually are.

Every probe here calls the SAME parser function the online path
already calls, unchanged. None of them loosen or reimplement a
parser's own contract to make a borderline file "count" -- a probe
reports a match only when the real parser genuinely returns real rows
against this exact content."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Optional

_KRANKING_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "87_collect_kranking_top120.py"
_kranking_module = None


def _load_kranking_script_module():
    global _kranking_module
    if _kranking_module is None:
        spec = importlib.util.spec_from_file_location("kranking_top120_script_probe", _KRANKING_SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _kranking_module = module
    return _kranking_module


def probe_tournament_info(text: str) -> Optional[str]:
    try:
        entry = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(entry, dict) or not entry.get("gameCode"):
        return None
    return f"parses as a getGameList JSON entry (gameCode={entry.get('gameCode')!r})"


def probe_entry_list(text: str) -> Optional[str]:
    from klpga.parsers.entry_list_parser import parse_entry_list_html
    try:
        result = parse_entry_list_html(text)
    except Exception:  # noqa: BLE001 -- any parse failure means "not a match", never a crash here
        return None
    if not result.rows:
        return None
    return f"parses as entry-list HTML ({len(result.rows)} real rows)"


def probe_leaderboard(text: str) -> Optional[str]:
    """parse_round_leaderboard_html's row selector is `[data-rank]` --
    broader than "this is definitely a leaderboard page" (a K-Ranking
    table also uses data-rank on its own rows, real bug found
    2026-09-30: that made this probe false-positive-match K-Ranking's
    full-table HTML). A real leaderboard row also always carries a
    real player identity (_playerCode/_playerName via the detail tag);
    requiring at least one row to have BOTH is the same distinction
    the parser's own PlayerRoundRow contract already draws -- not a
    new, separate rule invented for this probe."""
    from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html
    try:
        rows = parse_round_leaderboard_html(text, game_code="_probe_", round_number=1)
    except Exception:  # noqa: BLE001
        return None
    real_rows = [r for r in rows if r.player_code and r.player_name]
    if not real_rows:
        return None
    return f"parses as round-leaderboard HTML ({len(real_rows)} real player rows)"


def probe_grouping(text: str) -> Optional[str]:
    from klpga.parsers.group_page_parser import parse_round_grouping
    for rnd in (1, 2, 3, 4):
        try:
            rows = parse_round_grouping(text, rnd)
        except ValueError:
            continue
        if rows:
            return f"parses as group-page HTML (round {rnd}: {len(rows)} real players)"
    return None


def probe_kranking_full_table(text: str) -> Optional[str]:
    module = _load_kranking_script_module()
    try:
        rows = module.extract_full_table(text)
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    return f"parses as K-Ranking full-table HTML ({len(rows)} real rows)"


def probe_kranking_period(text: str) -> Optional[str]:
    module = _load_kranking_script_module()
    try:
        week, rows = module.extract_period_top10(text)
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    return f"parses as K-Ranking period/TOP10 HTML (week={week!r}, {len(rows)} rows)"


# Ordered (stage_name, status, probe) -- first real match wins. Order
# matters only in the pathological case where one file's content
# happens to satisfy two probes; tournament_info (strict JSON) and
# entry_list/leaderboard/grouping (each requiring a specific real
# table/attribute shape) essentially never collide in practice.
_PROBES = (
    ("tournament_info", "parser_exists", probe_tournament_info),
    ("entry_list", "parser_exists", probe_entry_list),
    ("leaderboard", "parser_exists", probe_leaderboard),
    ("grouping", "adapter_exists", probe_grouping),
    ("kranking", "parser_exists", probe_kranking_full_table),
    ("kranking", "parser_exists", probe_kranking_period),
)


def classify_file_by_content(path: Path) -> dict:
    """{"status": "parser_exists"|"adapter_exists"|"parser_missing",
    "stage_name": str|None, "detail": str}. Reads the file's real bytes
    and tries every probe above in order; the first real match wins.
    Never inspects the filename."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return {"status": "parser_missing", "stage_name": None, "detail": f"could not read as UTF-8 text: {exc}"}

    for stage_name, status, probe in _PROBES:
        detail = probe(text)
        if detail is not None:
            return {"status": status, "stage_name": stage_name, "detail": detail}

    return {
        "status": "parser_missing", "stage_name": None,
        "detail": "no existing parser's real contract (tournament_info/entry_list/leaderboard/grouping/kranking) matched this content",
    }


def find_capture_by_capability(raw_root: Path, game_code: str, probe) -> Optional[Path]:
    """Scans every real file under raw/<game_code>/ (RAW_MANIFEST_V1.json
    excluded -- that's archive_raw's own bookkeeping, never page
    content) and returns the first whose content the given probe
    actually accepts. Used as the capability-based fallback when a
    stage's canonical archive_raw filename isn't present, so a
    differently-named capture of the exact same real data is still
    found -- never rejected on filename alone."""
    game_dir = raw_root / game_code
    if not game_dir.is_dir():
        return None
    for p in sorted(game_dir.iterdir()):
        if not p.is_file() or p.name == "RAW_MANIFEST_V1.json":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if probe(text) is not None:
            return p
    return None

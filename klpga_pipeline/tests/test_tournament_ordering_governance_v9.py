"""MISSION V9 (2026-09-25): Tournament Ordering Governance.

"Do not make this a repository-wide import rule. Instead classify
every module into exactly one of three roles."

  1. Chronology Consumer -- renders tournament history to users.
     MUST import and use klpga.tournament_ordering. CI fails otherwise.
  2. Chronology Producer -- collects, reconciles, exports or stores
     tournament data. No requirement to use tournament_ordering.py.
  3. Algorithm -- ranking, walk-forward, Monte Carlo, Expected Strokes,
     simulations, backtests. May use their own ordering, but every
     local ordering must carry a one-line comment explaining why
     tournament_ordering.py is intentionally not used. CI fails if
     that justification comment is missing.

See klpga_pipeline/docs/NEO_TOURNAMENT_ORDERING_GOVERNANCE_V1.md for
the full module classification report, the role directory listing,
and the migration plan this test's CONSUMER_FILES/ALGORITHM_FILES
sets implement.

Detection heuristic (documented limitation, same class of limitation
any real static-analysis CI guard has): a "chronology-relevant sort"
is any single physical line containing `.sort(` or `sorted(` together
with one of game_code/season/end_date/start_date/effective_date on
that SAME line. A sort call split across multiple lines is not
detected -- every real site this mission found and fixed is a single
physical line (confirmed by grep against the whole src/scripts tree
before this test was written), so this has zero false negatives
today; a future multi-line sort would need this heuristic extended,
not a reason to weaken the rule.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SORT_CALL_RE = re.compile(r"\.sort\(|sorted\(")
_CHRONOLOGY_KEY_RE = re.compile(r"game_code|season|end_date|start_date|effective_date")
_ALGORITHM_MARKER_RE = re.compile(r"ALGORITHM ORDERING \(MISSION V9\)")
_IMPORT_RE = re.compile(r"from klpga\.tournament_ordering import|from klpga import tournament_ordering|import klpga\.tournament_ordering")

# The canonical utility itself -- exempt from both rules (it IS the
# shared implementation every other module routes through).
_UTILITY_FILE = "src/klpga/tournament_ordering.py"

# Role 1 -- CHRONOLOGY CONSUMER: renders a player's tournament history
# to an end-facing page. Explicit files (today's real set) plus glob
# patterns so a FUTURE builder/report module for a new player is
# covered automatically without editing this test.
CONSUMER_FILES = {
    "src/klpga/knowledge_engine/knowledge_engine.py",
    "src/klpga/website_v2/tournament_chronology.py",
    "scripts/build_10097_player_history.py",
    "scripts/build_10097_player_intelligence_report.py",
    "scripts/build_10097_master_player_analysis.py",
    "scripts/build_9431_player_intelligence_report.py",
    "scripts/build_9431_master_player_analysis.py",
}
CONSUMER_GLOBS = [
    "scripts/build_*_player_history.py",
    "scripts/build_*_player_intelligence_report.py",
    "scripts/build_*_master_player_analysis.py",
]
CONSUMER_NAME_FRAGMENTS_IN_WEBSITE_V2 = (
    "player_history", "player_intelligence", "tournament_chronology", "tournament_history",
)

# Role 3 -- ALGORITHM: ranking, walk-forward, Monte Carlo, Expected
# Strokes, simulations, backtests. Explicit files/dirs (today's real
# set); any NEW file under these same directories is covered
# automatically.
ALGORITHM_DIRS = (
    "src/klpga/neo_win/",
    "src/klpga/backtest/",
    "src/klpga/models/",
)
ALGORITHM_FILES = {
    "src/klpga/website_v2/neo_ranking_v2a.py",
    "src/klpga/website_v2/neo_ranking_v2b.py",
    "src/klpga/website_v2/neo_ranking_backtest.py",
    "src/klpga/website_v2/home_ranking.py",
    "src/klpga/analytics/sg_performance.py",
    "scripts/82_build_corrected_sg_total_rank.py",
}

# Role 2 -- CHRONOLOGY PRODUCER (no requirement): everything else,
# including src/klpga/collectors/, src/klpga/discovery/,
# tournament_discovery.py/tournament_pre_state.py/tournament_runtime.py,
# scripts/reconcile_*.py, and the ~100 numbered per-tournament
# collection/freeze/forecast pipeline scripts (scripts/NN_*.py). Not
# enumerated here -- absence from CONSUMER/ALGORITHM above IS the
# Producer classification, by design (this is what "do not make this
# a repository-wide import rule" means in code: only two roles ever
# carry a requirement).


def _relpath(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def _is_consumer(relpath: str) -> bool:
    if relpath in CONSUMER_FILES:
        return True
    import fnmatch
    if any(fnmatch.fnmatch(relpath, g) for g in CONSUMER_GLOBS):
        return True
    if relpath.startswith("src/klpga/website_v2/") and relpath not in ALGORITHM_FILES:
        name = Path(relpath).name
        if any(frag in name for frag in CONSUMER_NAME_FRAGMENTS_IN_WEBSITE_V2):
            return True
    return False


def _is_algorithm(relpath: str) -> bool:
    if relpath in ALGORITHM_FILES:
        return True
    return any(relpath.startswith(d) for d in ALGORITHM_DIRS)


def _all_py_files() -> list[Path]:
    files = []
    for base in (ROOT / "src", ROOT / "scripts"):
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            files.append(p)
    return files


def _chronology_sort_lines(text: str) -> list[tuple[int, str]]:
    hits = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _SORT_CALL_RE.search(line) and _CHRONOLOGY_KEY_RE.search(line):
            hits.append((i, line))
    return hits


def _has_marker_nearby(lines: list[str], line_no: int, *, window: int = 8) -> bool:
    start = max(0, line_no - 1 - window)
    context = "\n".join(lines[start:line_no])
    return bool(_ALGORITHM_MARKER_RE.search(context))


def test_every_consumer_module_with_a_chronology_sort_imports_the_shared_utility():
    violations = []
    for path in _all_py_files():
        relpath = _relpath(path)
        if relpath == _UTILITY_FILE or not _is_consumer(relpath):
            continue
        text = path.read_text(encoding="utf-8")
        hits = _chronology_sort_lines(text)
        if not hits:
            continue
        if not _IMPORT_RE.search(text):
            violations.append(
                f"{relpath}: {len(hits)} chronology-relevant sort(s) "
                f"(first at line {hits[0][0]}: {hits[0][1].strip()!r}) but no "
                f"import of klpga.tournament_ordering"
            )
    assert not violations, (
        "Chronology Consumer module(s) implement their own tournament ordering "
        "instead of importing klpga/tournament_ordering.py:\n" + "\n".join(violations)
    )


def test_every_algorithm_module_with_a_chronology_sort_has_a_justification_comment():
    violations = []
    for path in _all_py_files():
        relpath = _relpath(path)
        if relpath == _UTILITY_FILE or not _is_algorithm(relpath):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for line_no, line in _chronology_sort_lines(text):
            if not _has_marker_nearby(lines, line_no):
                violations.append(f"{relpath}:{line_no}: {line.strip()!r} has no nearby 'ALGORITHM ORDERING (MISSION V9)' comment")
    assert not violations, (
        "Algorithm module(s) implement their own tournament-adjacent ordering "
        "without the required one-line justification comment:\n" + "\n".join(violations)
    )


def test_consumer_and_algorithm_classifications_never_overlap():
    """A module must never be both -- otherwise the two CI rules could
    silently contradict each other."""
    overlap = (CONSUMER_FILES | set()) & ALGORITHM_FILES
    assert not overlap, f"file(s) classified as both Consumer and Algorithm: {overlap}"
    for f in ALGORITHM_FILES:
        assert not _is_consumer(f), f"{f} is in ALGORITHM_FILES but also matches the Consumer glob/name rules"


def test_the_canonical_utility_module_itself_is_exempt_from_both_rules():
    path = ROOT / _UTILITY_FILE
    assert path.exists()
    assert not _is_consumer(_UTILITY_FILE)
    assert not _is_algorithm(_UTILITY_FILE)


def test_known_consumer_files_are_still_real_files_on_disk():
    """Guards the classification list itself against drift (a renamed
    or deleted file silently falling out of enforcement)."""
    for relpath in CONSUMER_FILES:
        assert (ROOT / relpath).exists(), f"classified Consumer file no longer exists: {relpath}"


def test_known_algorithm_files_are_still_real_files_on_disk():
    for relpath in ALGORITHM_FILES:
        assert (ROOT / relpath).exists(), f"classified Algorithm file no longer exists: {relpath}"

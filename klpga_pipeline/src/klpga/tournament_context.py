"""Single source of truth for "which tournament, identified only by its
game_code, is the pipeline currently operating on".

Every operational script that used to hardcode a game_code / tournament
name / date range / site path / stage list resolves it from here
instead. Two layers:

  1. config/active_tournament.json -- validated lifecycle identity
     (game_code, tournament_name, season, start_date, end_date,
     final_round_number). Already generic (see
     klpga.tournament_discovery); this module never invents or infers
     any of these fields, only reads them.
  2. content/website_v2/TOURNAMENT_SITE_REGISTRY.json -- presentation
     fields that have no reliable official-metadata source and so must
     be explicitly recorded, once, per game_code: a site URL path
     segment (renaming it would break live links to an in-progress
     tournament) and the stage-state snapshot filename. The stage list
     itself is also recorded explicitly here rather than derived from
     final_round_number, because it is not currently a clean function
     of round count on the live site (OK Savings Bank Open, a 3-round
     event, still serves a distinct /r3/ live-round page alongside a
     separate /final/ wrap-up page -- collapsing that to a formula
     risked silently disagreeing with what is actually served).

Resolution is keyed by active_tournament.json's game_code, so removing
tournament hardcoding reduces to: point active_tournament.json at a new
game_code (klpga.tournament_discovery.refresh_active_config), add one
registry entry for its site path/filenames/stage list, and every
operational script downstream picks it up automatically -- no new
per-tournament Python constants.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TOURNAMENT_PATH = _ROOT / "config" / "active_tournament.json"
SITE_REGISTRY_PATH = _ROOT / "content" / "website_v2" / "TOURNAMENT_SITE_REGISTRY.json"
CONTENT_DIR = _ROOT / "content" / "website_v2"

# QA HARD STOP remediation (test/build isolation): every build script's
# own OUTPUT/OUT constant used to hardcode `_ROOT / "candidate" / <name>`
# directly -- the real, git-tracked directory -- so any test that called
# a real build() function (most of this suite's integration tests do,
# deliberately, to verify actual generated HTML rather than a mock)
# wrote real files into the tracked repository tree, leaving `git
# status` dirty after every test run with nothing but a fresh
# neo-build-id/neo-build-source-commit provenance stamp (see
# global_navigation.inject_build_provenance) -- never a real content
# change, but a real repository-hygiene defect regardless.
#
# tests/conftest.py's pytest_configure hook sets
# KLPGA_CANDIDATE_ROOT_OVERRIDE to a fresh, process-unique temp
# directory (tempfile.mkdtemp()) before test collection begins, i.e.
# before any script module below is ever imported -- every build
# script now resolves its own OUTPUT/OUT through candidate_dir() below
# instead of hardcoding the real path directly, so EVERY test run is
# isolated with zero per-test-file changes required, and a real
# `python scripts/NN_....py` invocation outside pytest (where this
# env var is never set) is completely unaffected.
CANDIDATE_ROOT = Path(os.environ["KLPGA_CANDIDATE_ROOT_OVERRIDE"]) if os.environ.get("KLPGA_CANDIDATE_ROOT_OVERRIDE") else _ROOT / "candidate"


def candidate_dir(name: str) -> Path:
    """Resolve one named build-output directory (e.g.
    "neo-data-home-top120") under CANDIDATE_ROOT -- the real tracked
    candidate/ tree by default, or a session-scoped temp directory
    under pytest (see CANDIDATE_ROOT above). A test that needs its OWN
    fully isolated, per-test copy (e.g. to assert on a synthetic
    fixture without touching what other tests in the same session
    built) still overrides the module's OUTPUT/OUT attribute directly
    after import, exactly as before -- this only fixes the default."""
    return CANDIDATE_ROOT / name


class TournamentContextError(RuntimeError):
    """active_tournament.json or its site-registry entry is missing or
    malformed. Fail closed -- never guess a tournament's identity."""


@dataclass(frozen=True)
class TournamentContext:
    game_code: str
    tournament_name: str
    season: int
    start_date: str
    end_date: str
    final_round_number: int
    current_round_number: int
    url_base: str
    stage_state_filename: str
    stage_order: tuple[str, ...]
    venue: str | None = None
    holes: int | None = None
    format: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    def artifact_path(self, artifact_type: str, *, ext: str = "json") -> Path:
        """Generic artifact-path contract (NEO TOURNAMENT PIPELINE Phase
        2, item 1): resolve `content/website_v2/<file>` for a named
        artifact_type ("entry_snapshot", "r1_live_snapshot", ...).

        1. If this tournament's registry entry has an explicit
           `artifacts[artifact_type]` mapping, use it verbatim -- this is
           how every one of OK Open's real, already-committed filenames
           (OK_OPEN_2026_R1_LIVE_SNAPSHOT.json etc.) stays byte-for-byte
           unchanged: a compatibility mapping, never a rename.
        2. Otherwise, generate `<game_code>_<ARTIFACT_TYPE>.<ext>` --
           this is what makes a brand-new tournament work with zero new
           registry entries: the next game_code automatically gets
           sensible, collision-free paths from identity alone. `ext`
           (default "json") only affects this generic fallback -- a
           human-readable report artifact_type can pass ext="md" so a
           brand-new tournament's fallback name still has the right
           extension; a mapped, already-committed filename always wins
           regardless of `ext`.

        Never guesses which artifact a caller means -- artifact_type is
        an explicit string the caller supplies, this function only ever
        resolves it to a Path, it does not invent artifact_types.
        """
        filename = self.artifacts.get(artifact_type)
        if filename is None:
            filename = f"{self.game_code}_{artifact_type.upper()}.{ext}"
        return CONTENT_DIR / filename

    @property
    def display_date_range(self) -> str:
        """"YYYY.MM.DD — MM.DD", the format every current page already
        renders -- derived from start/end date, never stored redundantly."""
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        return f"{start:%Y.%m.%d} — {end:%m.%d}"

    @property
    def stage_labels(self) -> dict[str, str]:
        """Generic stage-key -> Korean label map. Mechanical for every
        key in stage_order: "pre"->사전 분석 PRE, "final"->FINAL,
        "rN"->"RN" -- this rule already matches every stage label on the
        live site, so it is safe to derive rather than also register."""
        labels: dict[str, str] = {}
        for key in self.stage_order:
            if key == "pre":
                labels[key] = "사전 분석 PRE"
            elif key == "final":
                labels[key] = "FINAL"
            elif key.startswith("r") and key[1:].isdigit():
                labels[key] = key.upper()
            else:
                labels[key] = key.upper()
        return labels


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise TournamentContextError(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise TournamentContextError(f"invalid JSON in {path}: {exc}") from exc


def resolve_context(identity: dict, registry: dict) -> TournamentContext:
    """Pure resolution: identity (the shape of active_tournament.json)
    + registry (the shape of TOURNAMENT_SITE_REGISTRY.json's
    "tournaments" mapping) -> TournamentContext. No file I/O, so this is
    what both the real loader and a dry-run against a different
    game_code (e.g. in a test, or scripts/dry_run_tournament_context.py)
    call -- the resolution logic itself never changes based on which
    game_code is being resolved."""
    game_code = str(identity["game_code"])
    entry = registry.get(game_code)
    if entry is None:
        raise TournamentContextError(
            f"no TOURNAMENT_SITE_REGISTRY.json entry for game_code={game_code!r} -- "
            "add {url_base, stage_state_filename, stage_order} for this tournament "
            "before operating on it"
        )

    return TournamentContext(
        game_code=game_code,
        tournament_name=str(identity["tournament_name"]),
        season=int(identity["season"]),
        start_date=str(identity["start_date"]),
        end_date=str(identity["end_date"]),
        final_round_number=int(identity["final_round_number"]),
        current_round_number=int(identity["current_round_number"]),
        url_base=str(entry["url_base"]),
        stage_state_filename=str(entry["stage_state_filename"]),
        stage_order=tuple(entry["stage_order"]),
        venue=entry.get("venue"),
        holes=entry.get("holes"),
        format=entry.get("format"),
        artifacts=dict(entry.get("artifacts") or {}),
    )


def ensure_site_registry_entry(identity: dict, *, dry_run: bool = False) -> dict:
    """PRE BOOTSTRAP (NEO TOURNAMENT PIPELINE Phase 4): runtime data
    generation, not a source edit. resolve_context() hard-requires a
    TOURNAMENT_SITE_REGISTRY.json entry (url_base/stage_state_filename/
    stage_order) for any game_code before it can build a
    TournamentContext at all. For a brand-new game_code that has none
    yet, add a minimal, purely-structural entry so the rest of the
    pipeline can run with zero source edits -- never touches an
    existing entry (OK Open's and KG Ladies Open's real, hand-curated
    entries, including their live site URLs, stay exactly as committed).

    Nothing here is a fabricated tournament FACT: url_base and
    stage_state_filename are internal naming derived from game_code
    (never a guessed human-readable slug that could collide with, or
    misrepresent, a real site path), and stage_order is a mechanical
    ["pre", "r1".."rN", "final"] derived from the already-confirmed
    final_round_number. No `artifacts` mapping is written, so every
    artifact_type falls back to TournamentContext.artifact_path()'s
    generic `<game_code>_<ARTIFACT_TYPE>.<ext>` naming.

    Returns the full {game_code: entry} tournaments mapping -- callers
    should build their TournamentContext from THIS return value, not a
    separate re-read of SITE_REGISTRY_PATH, so dry_run=True (Phase 5
    item 12, DRY-RUN IMMUTABILITY) can preview a brand-new game_code's
    context without ever writing the registry file.
    """
    game_code = str(identity["game_code"])
    if SITE_REGISTRY_PATH.is_file():
        raw = _load_json(SITE_REGISTRY_PATH)
    else:
        raw = {"schema_version": 1, "tournaments": {}}
    tournaments = raw.setdefault("tournaments", {})
    if game_code not in tournaments:
        final_round_number = int(identity["final_round_number"])
        tournaments[game_code] = {
            "url_base": f"/tournaments/{identity['season']}/{game_code}/",
            "stage_state_filename": f"{game_code}_STAGE_STATE.json",
            "stage_order": ["pre", *[f"r{n}" for n in range(1, final_round_number + 1)], "final"],
        }
        if not dry_run:
            SITE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
            SITE_REGISTRY_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return tournaments


def load_active_tournament_context() -> TournamentContext:
    """Resolve the currently-active tournament's full context from disk.
    Raises TournamentContextError (never returns a partial/guessed
    context) if active_tournament.json or its matching site-registry
    entry is missing."""
    active = _load_json(ACTIVE_TOURNAMENT_PATH)
    registry = _load_json(SITE_REGISTRY_PATH).get("tournaments", {})
    return resolve_context(active, registry)


def _load_context_from_schedule_and_registry(game_code: str) -> TournamentContext:
    """Resolve a TournamentContext for a game_code that is NOT the one
    operationally active in active_tournament.json (e.g. a tournament
    whose PRE-stage evidence is being assembled ahead of its own
    window opening, without disturbing which tournament the live-
    polling scripts are currently targeting). Identity is built ONLY
    from real, already-sourced artifacts -- never active_tournament.json
    (reserved for the one tournament actually being live-polled) and
    never a guess:

      - content/website_v2/OFFICIAL_KLPGA_SCHEDULE.json (the
        authoritative calendar -- klpga.website_v2.official_schedule)
        supplies tournament_name/start_date/end_date, exactly the same
        source klpga.website_v2.tournament_chronology already treats as
        the only trustworthy calendar identity.
      - TOURNAMENT_SITE_REGISTRY.json's own stage_order (already
        real, either hand-curated or written by
        ensure_site_registry_entry from a confirmed final_round_number)
        supplies final_round_number, mechanically counted rather than
        re-asked for.
      - season is the real start_date's own year (never invented --
        this is the same rule ensure_site_registry_entry itself already
        applies when it first bootstraps an identity dict).
      - current_round_number is 0: this path is only ever used for a
        tournament that is not the operationally active one, so it has
        by definition not yet had any round evidence collected through
        the live lifecycle machinery.

    Fails closed (TournamentContextError) if either source has no entry
    for game_code -- never fabricates a date, name, or round count."""
    from klpga.website_v2.official_schedule import load_official_schedule

    registry = _load_json(SITE_REGISTRY_PATH).get("tournaments", {})
    reg_entry = registry.get(str(game_code))
    if reg_entry is None:
        raise TournamentContextError(
            f"no TOURNAMENT_SITE_REGISTRY.json entry for game_code={game_code!r} -- "
            "add {url_base, stage_state_filename, stage_order} for this tournament "
            "before operating on it"
        )
    schedule_path = CONTENT_DIR / "OFFICIAL_KLPGA_SCHEDULE.json"
    schedule = {entry.game_code: entry for entry in load_official_schedule(schedule_path)}
    schedule_entry = schedule.get(str(game_code))
    if schedule_entry is None:
        raise TournamentContextError(
            f"no OFFICIAL_KLPGA_SCHEDULE.json entry for game_code={game_code!r} -- "
            "real official tournament_name/start_date/end_date are required, never fabricated"
        )
    stage_order = reg_entry.get("stage_order") or []
    final_round_number = sum(1 for stage in stage_order if stage.startswith("r") and stage[1:].isdigit())
    if final_round_number == 0:
        raise TournamentContextError(
            f"TOURNAMENT_SITE_REGISTRY.json entry for game_code={game_code!r} has no r<N> "
            "stages in stage_order -- final_round_number cannot be derived"
        )
    identity = {
        "game_code": str(game_code),
        "tournament_name": schedule_entry.tournament_name,
        "season": int(schedule_entry.start_date[:4]),
        "start_date": schedule_entry.start_date,
        "end_date": schedule_entry.end_date,
        "final_round_number": final_round_number,
        "current_round_number": 0,
    }
    return resolve_context(identity, registry)


def load_tournament_context(game_code: str | None = None) -> TournamentContext:
    """The generic entry point every PRE-upstream script should call
    instead of load_active_tournament_context() directly.

    game_code=None (default): identical to load_active_tournament_context()
    -- every existing caller/test that never passes a game_code keeps
    its exact current behavior (reads active_tournament.json), so this
    is a purely additive capability, never a behavior change for OK
    Open's already-validated live path.

    game_code given and it equals active_tournament.json's own
    game_code: same as above -- the validated lifecycle record IS this
    tournament's identity, so it is used (not re-derived from the
    schedule) even though a game_code was supplied explicitly.

    game_code given and it differs (or there is no active_tournament.json
    yet): resolved from the official schedule + site registry via
    _load_context_from_schedule_and_registry -- never touches
    active_tournament.json, so a PRE-stage script pointed at a new
    tournament never risks flipping which tournament is operationally
    "active" for the live-polling scripts. Fails closed if either
    source lacks a real entry for game_code."""
    if game_code is None:
        return load_active_tournament_context()
    try:
        active = _load_json(ACTIVE_TOURNAMENT_PATH)
    except TournamentContextError:
        active = None
    if active is not None and str(active.get("game_code")) == str(game_code):
        registry = _load_json(SITE_REGISTRY_PATH).get("tournaments", {})
        return resolve_context(active, registry)
    return _load_context_from_schedule_and_registry(game_code)

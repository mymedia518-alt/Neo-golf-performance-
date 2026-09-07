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
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TOURNAMENT_PATH = _ROOT / "config" / "active_tournament.json"
SITE_REGISTRY_PATH = _ROOT / "content" / "website_v2" / "TOURNAMENT_SITE_REGISTRY.json"
CONTENT_DIR = _ROOT / "content" / "website_v2"


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

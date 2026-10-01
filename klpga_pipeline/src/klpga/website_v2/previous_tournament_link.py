"""The single, shared "이전 대회" (previous tournament) link resolver --
every tournament page (PRE, R1, R2, R3, FR/FINAL; HOME inherits it for
free since it mirrors whichever stage page is currently live) must call
this, never reimplement its own.

BUG FIX (2026-10-01, real finding): the first version of this (written
directly inside 190_build_hitejinro_pre_page.py) hardcoded
f"{url_base}pre/" -- always linking "이전 대회" to the previous
tournament's OWN PRE page, even once that tournament had long since
finished and published a real FINAL page (Hana/2026090002: completed
2026-09-20, docs/tournaments/2026/2026090002/final/index.html exists
with the real winner and 4-round leaderboard). A visitor following
"이전 대회" wants that tournament's actual result, not its own old
pre-tournament forecast.

Extracted here (2026-10-01) so every stage page -- not just PRE --
resolves the SAME link the SAME way: checked in priority order,
real-page-on-disk only (same "evidence must exist" discipline as
klpga.website_v2.hana_home_stage_router.hana_current_stage()), never
guesses a stage whose page was never actually published."""
from __future__ import annotations

from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # klpga_pipeline/
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"

STAGE_PRIORITY = ("final", "r3", "r2", "r1", "pre")


def latest_published_stage_url(url_base: str, *, repo_root: Path = REPO_ROOT) -> str:
    """url_base (e.g. "/tournaments/2026/2026090002/") -> the real,
    on-disk-verified URL of that tournament's most advanced published
    stage. Falls back to "pre/" only if nothing more advanced was ever
    published -- never invents a stage page that doesn't exist."""
    docs_root = repo_root / "docs"
    for stage in STAGE_PRIORITY:
        candidate = docs_root / url_base.strip("/") / stage / "index.html"
        if candidate.is_file():
            return f"{url_base}{stage}/"
    return f"{url_base}pre/"


def resolve_previous_tournament_link(*, as_of: date | None = None, repo_root: Path = REPO_ROOT) -> tuple[str, str] | None:
    """(tournament_name, url) for the real, date-resolved previous
    tournament's most advanced REAL published stage, or None if no
    previous tournament exists yet -- never a hardcoded literal."""
    import json

    from klpga.website_v2.official_schedule import load_official_schedule
    from klpga.website_v2.tournament_chronology import resolve_tournament_chronology

    schedule = load_official_schedule(CONTENT / "OFFICIAL_KLPGA_SCHEDULE.json")
    registry = json.loads((CONTENT / "TOURNAMENT_SITE_REGISTRY.json").read_text(encoding="utf-8"))["tournaments"]
    chronology = resolve_tournament_chronology(schedule, registry, as_of=as_of or date.today())
    last = chronology.get("last")
    if last is None:
        return None
    return last.tournament_name, latest_published_stage_url(last.url_base, repo_root=repo_root)


def previous_tournament_meta_html(*, as_of: date | None = None, repo_root: Path = REPO_ROOT) -> str:
    """Ready-to-splice <p class='meta'> snippet for a page's hero
    section, or "" if no previous tournament exists yet -- the exact
    same markup pattern on every page that calls this, so there is
    only ever one place this HTML is written."""
    import html

    previous = resolve_previous_tournament_link(as_of=as_of, repo_root=repo_root)
    if previous is None:
        return ""
    name, url = previous
    return f"<p class='meta'>이전 대회 <a href='{html.escape(url)}'>{html.escape(name)}</a></p>"

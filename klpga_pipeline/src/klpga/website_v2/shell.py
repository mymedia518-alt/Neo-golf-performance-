"""Deterministic, content-neutral HTML shell for NEO Website v2."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable

STAGES = ("overview", "pre", "r1", "r2", "r3", "final")
STAGE_LABELS = {
    "overview": "OVERVIEW",
    "pre": "PRE",
    "r1": "R1",
    "r2": "R2",
    "r3": "R3",
    "final": "FINAL",
}
GLOBAL_NAV = (
    ("home", "HOME", "/"),
    ("tournaments", "TOURNAMENTS", "/tournaments/"),
    ("deep-dive", "DEEP DIVE", "/deep-dive/"),
    ("about", "ABOUT NEO", "/about/"),
)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@dataclass(frozen=True)
class TournamentMetadata:
    tournament_id: str
    slug: str
    display_name: str
    beta_number: str
    year: int
    status: str
    latest_published_stage: str
    published_stages: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: dict) -> "TournamentMetadata":
        required = {
            "tournament_id", "slug", "display_name", "beta_number", "year",
            "status", "latest_published_stage", "published_stages",
        }
        missing = required - set(data)
        if missing:
            raise ValueError(f"missing tournament metadata: {sorted(missing)}")
        published = tuple(str(stage).lower() for stage in data["published_stages"])
        latest = str(data["latest_published_stage"]).lower()
        unknown = (set(published) | {latest}) - set(STAGES)
        if unknown:
            raise ValueError(f"unknown tournament stages: {sorted(unknown)}")
        if latest not in published:
            raise ValueError("latest_published_stage must be in published_stages")
        return cls(
            tournament_id=str(data["tournament_id"]),
            slug=str(data["slug"]),
            display_name=str(data["display_name"]),
            beta_number=str(data["beta_number"]),
            year=int(data["year"]),
            status=str(data["status"]),
            latest_published_stage=latest,
            published_stages=published,
        )

    @property
    def base_url(self) -> str:
        return f"/tournaments/{self.year}/{self.slug}/"

    def stage_url(self, stage: str) -> str:
        return self.base_url if stage == "overview" else f"{self.base_url}{stage}/"


def _global_header(active_section: str) -> str:
    links = []
    for key, label, url in GLOBAL_NAV:
        current = ' aria-current="page"' if key == active_section else ""
        links.append(f'<a class="global-nav__link" href="{url}"{current}>{label}</a>')
    return (
        '<header class="site-header">'
        '<div class="site-header__inner">'
        '<a class="wordmark" href="/" aria-label="NEO Golf Data home">NEO GOLF DATA</a>'
        '<nav class="global-nav" aria-label="Primary">' + "".join(links) + "</nav>"
        '</div></header>'
    )


def _tournament_header(meta: TournamentMetadata, current_stage: str) -> str:
    items = []
    published = set(meta.published_stages)
    for stage in STAGES:
        label = STAGE_LABELS[stage]
        active = stage == current_stage
        if stage in published:
            current = ' aria-current="page"' if active else ""
            item = f'<a class="stage-nav__link" href="{meta.stage_url(stage)}"{current}>{label}</a>'
        else:
            current = ' aria-current="page"' if active else ""
            item = f'<span class="stage-nav__disabled" aria-disabled="true"{current}>{label}</span>'
        items.append(f'<li class="stage-nav__item">{item}</li>')
    return (
        '<section class="tournament-context" aria-labelledby="tournament-name">'
        f'<p class="tournament-context__eyebrow">Tournament</p>'
        f'<h1 id="tournament-name"><a href="{meta.base_url}">{escape(meta.display_name)}</a></h1>'
        f'<p class="tournament-context__meta">BETA #{escape(meta.beta_number)}'
        f' <span aria-hidden="true">·</span> {meta.year}'
        f' <span aria-hidden="true">·</span> {escape(meta.status.upper())}</p>'
        '<nav class="stage-nav" aria-label="Tournament stages" data-stage-nav>'
        '<ol class="stage-nav__list">' + "".join(items) + '</ol></nav>'
        '</section>'
    )


def _footer() -> str:
    return (
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p><strong>NEO GOLF DATA</strong> · Forecasts separated from official results.</p>'
        '<nav aria-label="Footer"><a href="/">Home</a><a href="/tournaments/">Tournaments</a>'
        '<a href="/deep-dive/">Deep Dive</a><a href="/about/">About NEO</a></nav>'
        '<p><a href="/about/#methodology">Methodology &amp; evidence</a></p>'
        '</div></footer>'
    )


def render_page(
    *,
    title: str,
    active_section: str,
    body_html: str,
    tournament: TournamentMetadata | None = None,
    current_stage: str | None = None,
) -> str:
    if tournament is not None and current_stage not in STAGES:
        raise ValueError(f"current_stage must be one of {STAGES}")
    tournament_html = _tournament_header(tournament, current_stage) if tournament else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{escape(title)} · NEO GOLF DATA</title>'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<script src="/assets/neo-site.js" defer></script></head><body>'
        f'{_global_header(active_section)}<main id="main-content">{tournament_html}{body_html}</main>'
        f'{_footer()}</body></html>'
    )


def _fixture_notice(label: str) -> str:
    return (
        '<aside class="fixture-notice" role="note"><strong>PHASE 1 FIXTURE</strong>'
        f'<span>{escape(label)} demonstrates shell structure only. It is not historical prediction evidence.</span></aside>'
    )


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def build_preview_site(metadata_path: Path, output_root: Path) -> tuple[Path, ...]:
    data = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    meta = TournamentMetadata.from_dict(data)
    output_root = Path(output_root)
    written: list[Path] = []
    home_body = _fixture_notice("HOME") + (
        '<section class="page-intro"><p class="kicker">Golf intelligence, structured</p>'
        '<h1>One clear route through every tournament.</h1>'
        '<p>Fixture content for navigation and presentation testing.</p>'
        '<a class="text-link" href="/tournaments/">Browse tournaments</a></section>'
    )
    written.append(_write(output_root / "index.html", render_page(
        title="Home fixture", active_section="home", body_html=home_body,
    )))
    tournament_index = _fixture_notice("TOURNAMENTS") + (
        '<section class="page-intro"><p class="kicker">Tournament fixtures</p>'
        f'<h1>Preview tournaments</h1><p><a class="text-link" href="{meta.base_url}">'
        f'{escape(meta.display_name)} · BETA #{escape(meta.beta_number)}</a></p></section>'
    )
    written.append(_write(output_root / "tournaments" / "index.html", render_page(
        title="Tournaments fixture", active_section="tournaments", body_html=tournament_index,
    )))
    for stage in STAGES:
        label = STAGE_LABELS[stage]
        body = _fixture_notice(label) + (
            '<section class="stage-placeholder">'
            f'<p class="kicker">{label}</p><h2>{label} shell preview</h2>'
            '<p>Content migration is intentionally deferred. This page proves shared navigation and layout.</p>'
            '</section>'
        )
        relative = Path("tournaments") / str(meta.year) / meta.slug
        if stage != "overview":
            relative /= stage
        written.append(_write(output_root / relative / "index.html", render_page(
            title=f"{meta.display_name} {label} fixture",
            active_section="tournaments",
            body_html=body,
            tournament=meta,
            current_stage=stage,
        )))
    for section, heading in (("deep-dive", "Deep Dive"), ("about", "About NEO")):
        body = _fixture_notice(heading.upper()) + (
            f'<section class="page-intro"><p class="kicker">{heading}</p><h1>{heading} shell preview</h1>'
            '<p>Detailed content is outside PHASE 1.</p></section>'
        )
        written.append(_write(output_root / section / "index.html", render_page(
            title=f"{heading} fixture", active_section=section, body_html=body,
        )))
    assets = output_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("neo-site.css", "neo-site.js"):
        destination = assets / name
        shutil.copyfile(STATIC_DIR / name, destination)
        written.append(destination)
    return tuple(written)

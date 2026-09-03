"""Deterministic, content-neutral HTML shell for NEO GOLF DATA."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

from klpga.website_v2.global_navigation import NAVIGATION_MARKER, inject_global_navigation

STAGES = ("overview", "pre", "r1", "r2", "r3", "final")
STAGE_LABELS = {"overview": "개요", "pre": "PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}
GLOBAL_NAV = (
    ("home", "홈", "/"),
    ("tournaments", "대회", "/tournaments/"),
    ("deep-dive", "딥다이브", "/deep-dive/"),
    ("about", "소개", "/about/"),
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
        required = {"tournament_id", "slug", "display_name", "beta_number", "year", "status", "latest_published_stage", "published_stages"}
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
        return cls(str(data["tournament_id"]), str(data["slug"]), str(data["display_name"]), str(data["beta_number"]), int(data["year"]), str(data["status"]), latest, published)

    @property
    def base_url(self) -> str:
        return f"/tournaments/{self.year}/{self.slug}/"

    def stage_url(self, stage: str) -> str:
        return self.base_url if stage == "overview" else f"{self.base_url}{stage}/"


def _global_header() -> str:
    # Deliberately a bare, marked placeholder: inject_global_navigation()
    # (see global_navigation.py) always replaces any NAVIGATION_MARKER
    # header with the one canonical, active-section-aware header, on
    # every build. No page defines its own header content -- that's the
    # whole point, after a stale-header drift bug (fixed in v3 Phase 3)
    # let a generator's own copy of the header silently fall out of sync
    # with the real one.
    return f'<header {NAVIGATION_MARKER}></header>'


def breadcrumb_html(display_name: str, base_url: str | None, current_stage_label: str) -> str:
    # UX spec 3: a user must be able to tell "which tournament, which
    # point in time" from the page title alone -- a compact breadcrumb
    # ahead of the tournament name/status block, not buried in prose.
    # Shared by every tournament page (KG via _tournament_header below,
    # OK Open directly -- see scripts/84) so no generator invents its own.
    # Exactly one crumb is ever "here" (aria-current="page") -- the
    # deepest one. The tournament name is a real link back to its
    # overview page whenever a stage crumb follows it AND that overview
    # page actually exists (base_url given) -- KG has one; OK Open does
    # not (its PRE page IS the tournament's only "overview"-shaped
    # route), so base_url=None renders it as plain, non-clickable text
    # instead of a link to a route that would 404.
    crumbs: list[tuple[str | None, str]] = [('/', '홈'), ('/tournaments/', '대회')]
    if current_stage_label:
        crumbs.append((base_url, display_name)); crumbs.append((None, current_stage_label))
    else:
        crumbs.append((None, display_name))
    last_index = len(crumbs) - 1
    parts = []
    for index, (url, label) in enumerate(crumbs):
        if url:
            parts.append(f'<a href="{url}">{escape(label)}</a>')
        elif index == last_index:
            parts.append(f'<span aria-current="page">{escape(label)}</span>')
        else:
            parts.append(f'<span>{escape(label)}</span>')
    return '<nav class="breadcrumb" aria-label="현재 위치">' + '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'.join(parts) + '</nav>'


def stage_nav_html(items: list[tuple[str, str | None, bool]]) -> str:
    """items: (label, url or None if the stage isn't real/published yet, is_current)."""
    parts = []
    for label, url, active in items:
        current = ' aria-current="page"' if active else ""
        if url:
            parts.append(f'<li class="stage-nav__item"><a class="stage-nav__link" href="{url}"{current}>{label}</a></li>')
        else:
            parts.append(f'<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true"{current}>{label}</span></li>')
    return '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">' + "".join(parts) + '</ol></nav>'


def tournament_context_html(*, display_name: str, base_url: str, year: int, status: str,
                             current_stage_label: str, stage_items: list[tuple[str, str | None, bool]]) -> str:
    """The one canonical tournament breadcrumb + title + status + stage-nav
    block, used by every tournament page (KG and OK Open alike) -- see
    UX spec sections 3/9/10/16 ("각 generator가 자기 UI를 만들지 않는다")."""
    state = "대회 종료" if status.lower() == "complete" else escape(status)
    return ('<section class="tournament-context" aria-labelledby="tournament-name">'
            + breadcrumb_html(display_name, base_url, current_stage_label) +
            '<p class="tournament-context__eyebrow">KLPGA 대회</p>'
            f'<h1 id="tournament-name"><a href="{base_url}">{escape(display_name)}</a></h1>'
            f'<p class="tournament-context__meta">{year} <span aria-hidden="true">·</span> {state}</p>'
            + stage_nav_html(stage_items) + '</section>')


def _tournament_header(meta: TournamentMetadata, current_stage: str) -> str:
    published = set(meta.published_stages)
    stage_items = [
        (STAGE_LABELS[stage], meta.stage_url(stage) if stage in published else None, stage == current_stage)
        for stage in STAGES
    ]
    current_label = STAGE_LABELS.get(current_stage, "") if current_stage != "overview" else ""
    return tournament_context_html(display_name=meta.display_name, base_url=meta.base_url, year=meta.year,
                                    status=meta.status, current_stage_label=current_label, stage_items=stage_items)


def _footer() -> str:
    footer_links = "".join(f'<a href="{url}">{label}</a>' for _key, label, url in GLOBAL_NAV)
    return ('<footer class="site-footer"><div class="site-footer__inner">'
            '<p>예측은 결과가 나온 뒤 수정하지 않습니다.</p>'
            f'<nav aria-label="하단 메뉴">{footer_links}</nav>'
            '<p><a href="/about/#methodology">방법론 / 원본 기록</a></p></div></footer>')


def render_page(*, title: str, active_section: str, body_html: str, tournament: TournamentMetadata | None = None,
                current_stage: str | None = None, lang: str = "ko") -> str:
    if tournament is not None and current_stage not in STAGES:
        raise ValueError(f"current_stage must be one of {STAGES}")
    tournament_html = _tournament_header(tournament, current_stage) if tournament else ""
    html = (f'<!doctype html><html lang="{escape(lang)}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(title)} · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css">'
            '<script src="/assets/neo-site.js" defer></script></head><body>'
            f'{_global_header()}<main id="main-content">{tournament_html}{body_html}</main>{_footer()}</body></html>')
    # Fill in the marked-but-empty header immediately, at the source --
    # every render_page() caller gets the one real canonical header, not
    # a placeholder that depends on some later build step remembering to
    # post-process this page (idempotent: safe if a caller's own
    # pipeline also runs inject_global_navigation() again afterward).
    return inject_global_navigation(html, active_section=active_section)


def _fixture_notice(label: str) -> str:
    return f'<aside class="fixture-notice" role="note"><strong>구조 검증용 자료</strong><span>{escape(label)} 화면 구조만 확인하며 실제 예측 기록이 아닙니다.</span></aside>'


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8", newline="\n"); return path


def build_preview_site(metadata_path: Path, output_root: Path) -> tuple[Path, ...]:
    meta = TournamentMetadata.from_dict(json.loads(Path(metadata_path).read_text(encoding="utf-8")))
    output_root = Path(output_root); written = []
    home = _fixture_notice("홈") + f'<section class="page-intro"><p class="kicker">NEO GOLF DATA</p><h1>대회 데이터 구조 검증</h1><a class="text-link" href="/tournaments/">대회 보기</a></section>'
    written.append(_write(output_root/"index.html", render_page(title="홈", active_section="home", body_html=home)))
    index = _fixture_notice("대회") + f'<section class="page-intro"><h1>대회</h1><a href="{meta.base_url}">{escape(meta.display_name)}</a></section>'
    written.append(_write(output_root/"tournaments"/"index.html", render_page(title="대회", active_section="tournaments", body_html=index)))
    for stage in STAGES:
        body = _fixture_notice(STAGE_LABELS[stage]) + f'<section class="stage-placeholder"><h2>{STAGE_LABELS[stage]} 화면</h2></section>'
        relative = Path("tournaments")/str(meta.year)/meta.slug/(stage if stage != "overview" else "")
        written.append(_write(output_root/relative/"index.html", render_page(title=STAGE_LABELS[stage], active_section="tournaments", body_html=body, tournament=meta, current_stage=stage)))
    destinations = (("predictions", "예측 기록"), ("deep-dive", "DEEP DIVE"), ("about", "NEO 소개"))
    for section, heading in destinations:
        written.append(_write(output_root/section/"index.html", render_page(title=heading, active_section=section, body_html=_fixture_notice(heading)+f'<section class="page-intro"><h1>{heading}</h1></section>')))
    assets=output_root/"assets"; assets.mkdir(parents=True,exist_ok=True)
    for name in ("neo-site.css","neo-site.js"):
        destination=assets/name; shutil.copyfile(STATIC_DIR/name,destination); written.append(destination)
    return tuple(written)

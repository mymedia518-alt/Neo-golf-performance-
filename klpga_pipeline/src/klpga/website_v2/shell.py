"""Deterministic, content-neutral HTML shell for NEO GOLF DATA."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

STAGES = ("overview", "pre", "r1", "r2", "r3", "final")
STAGE_LABELS = {"overview": "개요", "pre": "PRE", "r1": "R1", "r2": "R2", "r3": "R3", "final": "FINAL"}
GLOBAL_NAV = (
    ("home", "홈", "/"),
    ("tournaments", "대회", "/tournaments/"),
    ("predictions", "예측 기록", "/predictions/"),
    ("deep-dive", "DEEP DIVE", "/deep-dive/"),
    ("about", "NEO 소개", "/about/"),
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


def _global_header(active_section: str) -> str:
    links = []
    for key, label, url in GLOBAL_NAV:
        current = ' aria-current="page"' if key == active_section else ""
        links.append(f'<a class="global-nav__link" href="{url}"{current}>{label}</a>')
    return ('<header class="site-header"><div class="site-header__inner">'
            '<a class="wordmark" href="/" aria-label="NEO GOLF DATA 홈">NEO GOLF DATA</a>'
            '<nav class="global-nav" aria-label="주요 메뉴">' + "".join(links) + '</nav></div></header>')


def _tournament_header(meta: TournamentMetadata, current_stage: str) -> str:
    items = []
    for stage in STAGES:
        label = STAGE_LABELS[stage]; active = stage == current_stage
        if stage in set(meta.published_stages):
            current = ' aria-current="page"' if active else ""
            item = f'<a class="stage-nav__link" href="{meta.stage_url(stage)}"{current}>{label}</a>'
        else:
            current = ' aria-current="page"' if active else ""
            item = f'<span class="stage-nav__disabled" aria-disabled="true"{current}>{label}</span>'
        items.append(f'<li class="stage-nav__item">{item}</li>')
    state = "대회 종료" if meta.status.lower() == "complete" else escape(meta.status)
    return ('<section class="tournament-context" aria-labelledby="tournament-name">'
            '<p class="tournament-context__eyebrow">KLPGA 대회</p>'
            f'<h1 id="tournament-name"><a href="{meta.base_url}">{escape(meta.display_name)}</a></h1>'
            f'<p class="tournament-context__meta">{meta.year} <span aria-hidden="true">·</span> {state}</p>'
            '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">' + "".join(items) + '</ol></nav></section>')


def _footer() -> str:
    return ('<footer class="site-footer"><div class="site-footer__inner">'
            '<p><strong>NEO GOLF DATA</strong> · 예측은 결과가 나온 뒤 수정하지 않습니다.</p>'
            '<nav aria-label="하단 메뉴"><a href="/">홈</a><a href="/tournaments/">대회</a><a href="/predictions/">예측 기록</a>'
            '<a href="/deep-dive/">DEEP DIVE</a><a href="/about/">NEO 소개</a></nav>'
            '<p><a href="/about/#methodology">방법론 / 원본 기록</a></p></div></footer>')


def render_page(*, title: str, active_section: str, body_html: str, tournament: TournamentMetadata | None = None,
                current_stage: str | None = None, lang: str = "ko") -> str:
    if tournament is not None and current_stage not in STAGES:
        raise ValueError(f"current_stage must be one of {STAGES}")
    tournament_html = _tournament_header(tournament, current_stage) if tournament else ""
    return (f'<!doctype html><html lang="{escape(lang)}"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(title)} · NEO GOLF DATA</title><link rel="stylesheet" href="/assets/neo-site.css">'
            '<script src="/assets/neo-site.js" defer></script></head><body>'
            f'{_global_header(active_section)}<main id="main-content">{tournament_html}{body_html}</main>{_footer()}</body></html>')


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

"""PUBLIC UI Phase 8: renders HOME's three tournament cards (지난 대회
/ 이번 대회 / 다음 대회) from klpga.website_v2.tournament_chronology's
resolved facts. Pure string rendering -- no file I/O, no data
resolution -- so it stays trivially testable against synthetic facts
without needing a real registry or TournamentContext.

Never infers a missing fact: every field is either the real curated
value or the public em dash "—". The three-card structure itself is
immutable -- always exactly three cards, in this order, even when
"last"/"next" resolve to nothing yet (a brand-new season with no
completed or scheduled future tournament recorded)."""
from __future__ import annotations

from html import escape

from klpga.website_v2.tournament_chronology import TournamentCardFacts

DASH = "—"


def _field(value: str | None) -> str:
    return escape(value) if value else DASH


def _card(kind: str, kicker: str, facts: TournamentCardFacts | None, *, fields: tuple[tuple[str, str], ...]) -> str:
    """fields: ((label, attr_name), ...) -- which TournamentCardFacts
    attributes this card shows, in order, after name/dates/venue.

    PRODUCT RECOVERY V1 REDESIGN: the card is now a compact single line
    (kicker + name + dates) by default -- venue and the kind-specific
    extra fact (우승/디펜딩 챔피언 etc.) move into a native <details>
    disclosure so a visitor can still reach them, but they cost zero
    vertical space until opened. All the same facts are still real DOM
    text (never removed), so this is a genuine layout change, not a
    content cut -- see neo-site.css's .t-tournament-card__details rules
    for the compact-strip visual this produces."""
    if facts is None or not facts.tournament_name:
        rows = "".join(f'<div class="t-tournament-card__row"><dt>{label}</dt><dd>{DASH}</dd></div>' for label, _ in fields)
        return (
            f'<article class="t-tournament-card" data-tournament-card="{kind}">'
            f'<p class="t-tournament-card__kicker">{escape(kicker)}</p>'
            f'<p class="t-tournament-card__name">{DASH}</p>'
            f'<p class="t-tournament-card__dates">{DASH}</p>'
            f'<details class="t-tournament-card__details"><summary>자세히</summary>'
            f'<div class="t-tournament-card__row"><dt>코스</dt><dd>{DASH}</dd></div>'
            f"{rows}"
            f"</details></article>"
        )
    extra_rows = "".join(
        f'<div class="t-tournament-card__row"><dt>{label}</dt><dd>{_field(getattr(facts, attr))}</dd></div>'
        for label, attr in fields
    )
    name_html = f'<a href="{escape(facts.url_base)}">{escape(facts.tournament_name)}</a>' if facts.url_base else escape(facts.tournament_name)
    return (
        f'<article class="t-tournament-card" data-tournament-card="{kind}" data-game-code="{escape(facts.game_code)}">'
        f'<p class="t-tournament-card__kicker">{escape(kicker)}</p>'
        f'<p class="t-tournament-card__name">{name_html}</p>'
        f'<p class="t-tournament-card__dates">{_field(facts.date_range_display)}</p>'
        f'<details class="t-tournament-card__details"><summary>자세히</summary>'
        f'<div class="t-tournament-card__row"><dt>코스</dt><dd>{_field(facts.venue)}</dd></div>'
        f"{extra_rows}"
        f"</details></article>"
    )


def render_tournament_cards_html(chronology: dict[str, TournamentCardFacts | None]) -> str:
    """chronology: the dict returned by
    tournament_chronology.resolve_tournament_chronology() /
    build_home_tournament_chronology() -- keys "last"/"current"/"next"."""
    last_card = _card("last", "지난 대회", chronology.get("last"), fields=(("우승", "winner"), ("우승 스코어", "winning_score")))
    current_card = _card("current", "이번 대회", chronology.get("current"), fields=(("디펜딩 챔피언", "defending_champion"), ("디펜딩 챔피언 스코어", "defending_champion_score")))
    next_card = _card("next", "다음 대회", chronology.get("next"), fields=(("디펜딩 챔피언", "defending_champion"), ("디펜딩 챔피언 스코어", "defending_champion_score")))
    return f'<section class="t-tournament-cards" aria-label="대회 일정">{last_card}{current_card}{next_card}</section>'

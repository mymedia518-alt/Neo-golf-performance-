"""PUBLIC UI immutable sponsor rule (Phase 8 correction, FAIL 2).

One shared place for the rule every public player-name rendering path
must follow: a verified official sponsor renders directly under the
player's name; an unverified or unknown one is omitted entirely. Never
a guess, never a placeholder, no page-specific exception.

Callers keep their own already-established CSS class names (HOME/
RANKING uses player-name/player-sponsor, OK Open's stage tables use
player/sponsor) -- this module centralizes the RULE (the verification
gate, and "no sponsor line at all" vs "invented placeholder"), not a
single fixed markup shape.
"""
from __future__ import annotations

from html import escape


def verified_sponsor(record: dict) -> str | None:
    """The real sponsor for one player-master record, or None if it
    must not be shown -- either no sponsor was recorded, or the
    record's own identity was never confirmed against the official
    source (identity_validation != "PASS"). Centralizing this gate
    means a future data refresh that introduces an unconfirmed record
    can never silently leak an unverified sponsor by skipping it."""
    if record.get("identity_validation") != "PASS":
        return None
    sponsor = record.get("current_official_sponsor")
    return sponsor if sponsor else None


def render_player_identity(
    name,
    sponsor: str | None,
    *,
    name_class: str = "player-name",
    sponsor_class: str = "player-sponsor",
    quote: str = '"',
) -> str:
    """The one shared player-name(+sponsor) markup. `sponsor` must
    already be the real, verified value (or None/falsy) -- this
    function never invents one: a falsy sponsor simply omits the
    sub-line entirely, never a placeholder dash or "확인 중" text.

    `quote`: the HTML attribute-quote character, matching whichever
    convention the calling page's OWN surrounding markup already uses
    (double for HOME/RANKING, single for OK Open's stage tables) --
    purely cosmetic (CSS/JS never see the quote character), kept
    consistent per caller so existing byte-level fixtures don't churn."""
    q = quote
    name_html = f"<span class={q}{name_class}{q}>{escape(str(name) if name is not None else '—')}</span>"
    if not sponsor:
        return name_html
    return name_html + f"<span class={q}{sponsor_class}{q}>{escape(str(sponsor))}</span>"

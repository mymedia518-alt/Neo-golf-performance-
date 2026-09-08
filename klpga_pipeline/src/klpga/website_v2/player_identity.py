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

import re
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


# PUBLIC UI correction (GLOBAL SPONSOR RULE): tags whose bare text
# content is a genuine identity DISPLAY -- a leaderboard cell, a card
# heading, a result caption. Deliberately excludes <button>, <option>,
# <title>, <script>, and attribute values: a clickable control's label
# or an SVG/meta title string is not the "player name, sponsor
# directly below it" presentation this rule targets, and rewriting one
# would corrupt its accessible name or a JS handler that reads it.
_IDENTITY_DISPLAY_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "b", "strong", "dd", "li", "span"})
_OPEN_TAG_NAME_RE = re.compile(r"<\s*([a-zA-Z0-9]+)")
_TAG_AND_TEXT_RE = re.compile(r"(<[^>]+>)([^<>]*)(?=<)")
_ALREADY_WRAPPED_MARKERS = ('class="player-name"', "class='player-name'", 'class="player"', "class='player'")


def normalize_player_sponsor_mentions(html: str, sponsor_by_name: dict[str, str]) -> str:
    """Promotion-time normalization for already-generated (frozen/
    legacy) HTML that shows a bare player name with no sponsor markup
    at all -- e.g. a completed tournament's archived pages, built by
    code this pipeline no longer regenerates. Wraps only an EXACT,
    bare name match inside an identity-display tag (see
    _IDENTITY_DISPLAY_TAGS) with the same render_player_identity()
    markup used everywhere else, using `sponsor_by_name` (built from
    the same official, identity-validated player master as every other
    sponsor lookup in this pipeline -- see verified_sponsor()).

    This changes only the PROMOTED HTML text in memory; it never
    touches the frozen source (migration.py, candidate/website-v2/)
    that produced it, so historical source truth is untouched. A name
    with no entry in `sponsor_by_name` (no verified evidence) is left
    exactly as-is -- still blank, per the rule, never guessed."""
    if not sponsor_by_name:
        return html

    def repl(match: re.Match) -> str:
        open_tag, text = match.group(1), match.group(2)
        name = text.strip()
        if text != name or name not in sponsor_by_name:
            return match.group(0)
        tag_name_match = _OPEN_TAG_NAME_RE.match(open_tag)
        if not tag_name_match or tag_name_match.group(1).lower() not in _IDENTITY_DISPLAY_TAGS:
            return match.group(0)
        if any(marker in open_tag for marker in _ALREADY_WRAPPED_MARKERS):
            return match.group(0)  # already carries the shared markup -- never double-wrap
        return open_tag + render_player_identity(name, sponsor_by_name[name])

    return _TAG_AND_TEXT_RE.sub(repl, html)

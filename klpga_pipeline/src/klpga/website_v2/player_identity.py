"""PUBLIC UI immutable sponsor rule (Red Team remediation, FAIL A).

One shared place for the rule every public player-identity display
must follow: a player-name slot, plus a sponsor slot directly
underneath it, ALWAYS BOTH PRESENT. If a verified official sponsor
exists, the sponsor slot shows it. If none exists, the sponsor slot
stays structurally present but visually empty -- never "미확인",
"확인 중", "—", or any other guessed/placeholder text.

Callers keep their own already-established CSS class names (HOME/
RANKING uses player-name/player-sponsor, OK Open's stage tables use
player/sponsor) -- this module centralizes the RULE (the verification
gate, and "always both slots, empty rather than invented" contract),
not a single fixed markup shape.
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
    """The one shared player-name + sponsor markup. Both slots are
    ALWAYS emitted -- the sponsor slot is empty (no text content) when
    `sponsor` is falsy, never a placeholder dash or "확인 중" text, and
    never omitted entirely (the structural slot must exist so a future
    verified sponsor can appear with no markup change).

    `quote`: the HTML attribute-quote character, matching whichever
    convention the calling page's OWN surrounding markup already uses
    (double for HOME/RANKING, single for OK Open's stage tables) --
    purely cosmetic (CSS/JS never see the quote character), kept
    consistent per caller so existing byte-level fixtures don't churn."""
    q = quote
    name_html = f"<span class={q}{name_class}{q}>{escape(str(name) if name is not None else '—')}</span>"
    sponsor_text = escape(str(sponsor)) if sponsor else ""
    return name_html + f"<span class={q}{sponsor_class}{q}>{sponsor_text}</span>"


# PUBLIC UI correction (GLOBAL SPONSOR RULE): tags whose bare text
# content is a genuine identity DISPLAY -- a leaderboard cell, a card
# heading, a result caption. Deliberately excludes <button>, <option>,
# <title>, <script>, and attribute values: a clickable control's label
# or an SVG/meta title string is not the "player name, sponsor
# directly below it" presentation this rule targets, and rewriting one
# in place would corrupt its accessible name or a JS handler that
# reads it -- see _BUTTON_TEXT_RE below for that case instead (an
# adjacent slot outside the control, never inside it).
_IDENTITY_DISPLAY_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "b", "strong", "dd", "li", "span"})
_OPEN_TAG_NAME_RE = re.compile(r"<\s*([a-zA-Z0-9]+)")
_TAG_AND_TEXT_RE = re.compile(r"(<[^>]+>)([^<>]*)(?=<)")
_ALREADY_WRAPPED_MARKERS = ('class="player-name"', "class='player-name'", 'class="player"', "class='player'")
_BUTTON_TEXT_RE = re.compile(r"(<button\b[^>]*>)([^<>]*)(</button>)(?!<span class=\"player-sponsor\">)")
# PUBLIC UI correction (FAIL A regression): a name span that already
# carries the right CSS class (so _ALREADY_WRAPPED_MARKERS below would
# treat it as "done") can still be INCOMPLETE -- e.g. an
# orphaned/legacy page that predates the sponsor-slot convention and
# has no active generator rewriting it, rendering only
# <span class='player'>NAME</span> with no sponsor sibling at all.
# This pass runs first and repairs exactly that case (a name span NOT
# already immediately followed by its sponsor sibling) by appending
# the missing sponsor slot, so the later _ALREADY_WRAPPED_MARKERS
# check only ever short-circuits on genuinely complete markup.
_NAME_SPAN_RE = re.compile(
    r"<span class=(['\"])(player-name|player)\1>([^<>]*)</span>"
    r"(?!<span class=(?:\"player-sponsor\"|'player-sponsor'|\"sponsor\"|'sponsor'))"
)
_NAME_TO_SPONSOR_CLASS = {"player-name": "player-sponsor", "player": "sponsor"}


def normalize_player_sponsor_mentions(html: str, sponsor_by_name: dict[str, str], known_names=None) -> str:
    """Promotion-time normalization for already-generated (frozen/
    legacy, or orphaned/no-longer-regenerated) HTML that shows a bare
    player name with no sponsor slot at all. Wraps an EXACT, bare name
    match inside an identity-display tag (see _IDENTITY_DISPLAY_TAGS)
    with the same render_player_identity() markup used everywhere
    else -- both slots always present, sponsor filled from
    `sponsor_by_name` when known, otherwise left structurally empty.

    `known_names`: the broader "this bare text is a real player name"
    roster (defaults to sponsor_by_name's own keys when omitted) --
    kept separate from `sponsor_by_name` because a genuine player with
    no verified sponsor still needs the two-slot structure applied,
    never skipped just because no sponsor evidence exists for them.

    A player identity whose visible text sits inside a <button> (a
    clickable card trigger, say) is never rewritten in place -- an
    adjacent sponsor slot is appended immediately outside the control
    instead, preserving its accessible name/label and any JS handler
    that reads its exact text.

    This changes only the PROMOTED HTML text in memory; it never
    touches the frozen source (migration.py, player_card.py,
    candidate/website-v2/) that produced it, so historical source
    truth is untouched. A name with no entry in `known_names` at all
    is left exactly as-is -- this function never guesses what counts
    as a player name from unrelated text."""
    known = known_names if known_names is not None else set(sponsor_by_name)
    if not known:
        return html

    def name_span_repl(match: re.Match) -> str:
        quote, class_name, text = match.group(1), match.group(2), match.group(3)
        name = text.strip()
        if text != name or name not in known:
            return match.group(0)
        sponsor_class = _NAME_TO_SPONSOR_CLASS[class_name]
        sponsor = sponsor_by_name.get(name)
        sponsor_text = escape(sponsor) if sponsor else ""
        return match.group(0) + f"<span class={quote}{sponsor_class}{quote}>{sponsor_text}</span>"

    html = _NAME_SPAN_RE.sub(name_span_repl, html)

    def button_repl(match: re.Match) -> str:
        open_tag, text, close_tag = match.group(1), match.group(2), match.group(3)
        name = text.strip()
        if text != name or name not in known:
            return match.group(0)
        sponsor = sponsor_by_name.get(name)
        sponsor_text = escape(sponsor) if sponsor else ""
        return f'{open_tag}{text}{close_tag}<span class="player-sponsor">{sponsor_text}</span>'

    html = _BUTTON_TEXT_RE.sub(button_repl, html)

    def repl(match: re.Match) -> str:
        open_tag, text = match.group(1), match.group(2)
        name = text.strip()
        if text != name or name not in known:
            return match.group(0)
        tag_name_match = _OPEN_TAG_NAME_RE.match(open_tag)
        if not tag_name_match or tag_name_match.group(1).lower() not in _IDENTITY_DISPLAY_TAGS:
            return match.group(0)
        if any(marker in open_tag for marker in _ALREADY_WRAPPED_MARKERS):
            return match.group(0)  # already carries the shared markup -- never double-wrap
        return open_tag + render_player_identity(name, sponsor_by_name.get(name))

    return _TAG_AND_TEXT_RE.sub(repl, html)

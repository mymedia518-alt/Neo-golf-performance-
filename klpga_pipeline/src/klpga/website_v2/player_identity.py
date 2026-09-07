"""Shared Player Identity rendering contract -- NEO SITE V5 permanent
public-site invariant.

Rule: ANY public page that displays a player's name MUST display that
player's verified official sponsor directly below the player's name.
This module is the ONE place that markup is produced, so every page
(HOME/PLAYERS, RANKING, TOURNAMENTS, PRE, R1, R2, R3, R4, FINAL, DEEP
DIVE, NEO LAB, and any future public player-display component) renders
the identical structure instead of duplicating page-specific markup.

Canonical rendering contract:
    PLAYER NAME
    OFFICIAL SPONSOR

- If the official sponsor is unavailable, unidentified, or the player
  identity is unresolved: the sponsor slot renders BLANK (empty text
  content). It is never omitted from the DOM -- the slot element is
  always present so layout never shifts between a row with a known
  sponsor and a row without one.
- The sponsor is never inferred, guessed, or defaulted. A caller must
  pass the real, already-resolved value (or None/""); this module adds
  one more layer of protection by also blanking a fixed list of known
  placeholder strings ("unknown", "미확인", "-", "N/A", ...) in case one
  slips in from an upstream source, so no placeholder-looking text can
  ever render in the sponsor slot through this function.
"""
from __future__ import annotations

from html import escape

PLAYER_IDENTITY_CONTAINER_CLASS = "neo-player-identity"
PLAYER_IDENTITY_NAME_CLASS = "neo-player-identity__name"
PLAYER_IDENTITY_SPONSOR_CLASS = "neo-player-identity__sponsor"

# Defensive blank-list: none of these may ever render as sponsor text,
# even if a caller passes one by mistake. This is a guard, not the
# primary contract -- the primary contract is "callers only ever pass a
# real, verified value or None/''".
_PLACEHOLDER_SPONSOR_VALUES = {
    "unknown", "Unknown", "UNKNOWN",
    "미확인", "확인불가", "확인 불가",
    "n/a", "N/A", "na", "NA",
    "-", "--", "—", "–",
    "none", "None", "NONE",
    "null", "NULL",
    "tbd", "TBD",
}


def resolve_sponsor_text(official_sponsor: str | None) -> str:
    """Normalize a raw sponsor value into what may actually be rendered.

    Returns "" (blank) for None, whitespace-only strings, and any known
    placeholder string. Returns the trimmed real value otherwise. Never
    raises on unexpected input -- an unresolved identity must degrade to
    blank, not to an exception that could crash a page build.
    """
    if official_sponsor is None:
        return ""
    text = str(official_sponsor).strip()
    if not text or text in _PLACEHOLDER_SPONSOR_VALUES:
        return ""
    return text


def render_player_identity(
    player_name: str | None,
    official_sponsor: str | None,
    *,
    tag: str = "span",
    name_class: str = PLAYER_IDENTITY_NAME_CLASS,
    sponsor_class: str = PLAYER_IDENTITY_SPONSOR_CLASS,
    container_class: str | None = PLAYER_IDENTITY_CONTAINER_CLASS,
) -> str:
    """Render the canonical PLAYER NAME / OFFICIAL SPONSOR block.

    `player_name` missing/None renders as an em dash inside the name
    slot (identity itself unresolved -- distinct from "name known, sponsor
    unknown"). `official_sponsor` is run through resolve_sponsor_text()
    so the slot is blank rather than a placeholder when unavailable, but
    the sponsor element itself is ALWAYS emitted (structural presence).

    `container_class=None` omits the wrapping element (for callers that
    already provide their own row/cell container and only want the two
    inner slots) -- name and sponsor are still emitted as two elements
    of the same shape, never merged into a single text node, so the
    per-slot CSS/test contract stays identical either way.
    """
    name_text = escape(str(player_name)) if player_name not in (None, "") else "—"
    sponsor_text = escape(resolve_sponsor_text(official_sponsor))
    name_html = f'<{tag} class="{name_class}">{name_text}</{tag}>'
    sponsor_html = f'<{tag} class="{sponsor_class}">{sponsor_text}</{tag}>'
    inner = name_html + sponsor_html
    if container_class is None:
        return inner
    return f'<{tag} class="{container_class}">{inner}</{tag}>'

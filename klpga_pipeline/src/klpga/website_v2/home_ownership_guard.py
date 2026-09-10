"""P0-4 HOME ownership guard: the production root `docs/index.html`
may only ever be written by its single declared owner.

Smallest-safe implementation (per NEO WEBSITE V3 PHASE 1, P0-4): a
single marker + two checks, not the full multi-module contract drafted
in HOME_OWNERSHIP_GUARD_CONTRACT_v1.md. An unclaimed docs/index.html
(no marker at all) is claimable by any recognized owner; once claimed,
any other writer is a hard stop unless an explicit, code-reviewed
transfer is declared (see allow_transfer_from below).

OWNER SUPERSESSION (NEO PUBLIC SITE -- OWNER UI/ROUTING FINAL PATCH):
root HOME was TOP120_OWNER's alone (the K-Ranking x NEO Ranking page)
until this owner-approved decision temporarily withdrew that page from
public release and made the current tournament's latest approved stage
the root HOME instead -- see scripts/109_build_kb_r1_page.py's
write_root_home(). TOP120_OWNER's own build/promotion path (scripts
86/88/94) is untouched and still the sole legitimate writer for
CURRENT_TOURNAMENT_OWNER to itself supersede, if a future owner
decision reverses this one."""
from __future__ import annotations

from pathlib import Path

OWNER_META_NAME = "neo-home-owner"
TOP120_OWNER = "top120-v1"
# The current tournament's latest-approved-stage HOME mirror (see the
# module docstring's OWNER SUPERSESSION note). Not a replacement for
# TOP120_OWNER -- a second, equally legitimate owner identity, active
# only while root HOME points at the current tournament instead of the
# K-Ranking/NEO Ranking page.
CURRENT_TOURNAMENT_OWNER = "current-tournament-v1"
_RECOGNIZED_OWNERS = (TOP120_OWNER, CURRENT_TOURNAMENT_OWNER)


class HomeOwnershipError(Exception):
    """Raised when a non-owning writer attempts to write the production HOME."""


def extract_owner(html: str) -> str | None:
    marker = f'<meta name="{OWNER_META_NAME}" content="'
    start = html.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = html.find('"', start)
    if end == -1:
        return None
    return html[start:end]


def embed_owner(html: str, owner: str) -> str:
    tag = f'<meta name="{OWNER_META_NAME}" content="{owner}">'
    if "<head>" in html:
        return html.replace("<head>", f"<head>{tag}", 1)
    if "<head " in html:
        idx = html.index("<head ")
        close = html.index(">", idx) + 1
        return html[:close] + tag + html[close:]
    return tag + html


def assert_home_write_allowed(
    target_path: Path, writer_owner: str, *, repo_root: Path, allow_transfer_from: str | None = None
) -> None:
    """Hard stop: raises HomeOwnershipError if target_path resolves to
    the canonical production HOME (<repo_root>/docs/index.html) and
    writer_owner is not a recognized owner, or the file is already
    claimed by a DIFFERENT owner. Any other target path is always
    allowed by this guard (it only protects the one file).

    allow_transfer_from: when set, an existing owner exactly equal to
    this value is accepted as a deliberate, one-directional, code-
    reviewed ownership transfer TO writer_owner (see the module
    docstring's OWNER SUPERSESSION note) -- never a general bypass:
    any other existing owner still hard-stops."""
    canonical_home = (repo_root / "docs" / "index.html").resolve()
    resolved_target = target_path.resolve()
    if resolved_target != canonical_home:
        return
    if writer_owner not in _RECOGNIZED_OWNERS:
        raise HomeOwnershipError(
            f"HOME OWNERSHIP GUARD: refusing to write {resolved_target} "
            f"as writer '{writer_owner}' -- only {_RECOGNIZED_OWNERS} may own "
            "the production root HOME."
        )
    if canonical_home.exists():
        existing_owner = extract_owner(canonical_home.read_text(encoding="utf-8"))
        if existing_owner is not None and existing_owner != writer_owner and existing_owner != allow_transfer_from:
            raise HomeOwnershipError(
                f"HOME OWNERSHIP GUARD: {canonical_home} is already owned by "
                f"'{existing_owner}', refusing overwrite by '{writer_owner}'."
            )


def validate_top120_population(dataset: dict) -> None:
    """Hard stop: raises ValueError unless the dataset's records are
    exactly the 120-player K-Ranking population with ranks 1..120,
    no gaps, no duplicates. Called against two legitimately different
    dataset shapes: scripts/88's own in-memory pre-trim dataset (key
    "records", full internal fields, validated before the public file
    is written) and the final written neo-top120-evaluation.json (key
    "players", the public-boundary-trimmed shape scripts/94 validates
    post-promotion). Checking "players" first then falling back to
    "records" handles both without weakening either -- each dict only
    ever has one of the two keys."""
    records = dataset.get("players", dataset.get("records", []))
    if len(records) != 120:
        raise ValueError(f"TOP120 population must be exactly 120 records, found {len(records)}")
    ranks = sorted(r["official_k_rank"] for r in records)
    if ranks != list(range(1, 121)):
        raise ValueError("TOP120 K-Ranking must be exactly 1..120 with no gaps or duplicates")

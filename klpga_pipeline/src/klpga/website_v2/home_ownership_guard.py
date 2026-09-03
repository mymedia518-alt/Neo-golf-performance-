"""P0-4 HOME ownership guard: the production root `docs/index.html`
may only ever be written by the TOP120 canonical HOME publisher.

Smallest-safe implementation (per NEO WEBSITE V3 PHASE 1, P0-4): a
single marker + two checks, not the full multi-module contract drafted
in HOME_OWNERSHIP_GUARD_CONTRACT_v1.md. An unclaimed docs/index.html
(no marker at all -- the real, confirmed state of production today) is
claimable by the TOP120 publisher; once claimed, any other writer is a
hard stop.
"""
from __future__ import annotations

from pathlib import Path

OWNER_META_NAME = "neo-home-owner"
TOP120_OWNER = "top120-v1"


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


def assert_home_write_allowed(target_path: Path, writer_owner: str, *, repo_root: Path) -> None:
    """Hard stop: raises HomeOwnershipError if target_path resolves to
    the canonical production HOME (<repo_root>/docs/index.html) and
    writer_owner is not the TOP120 publisher. Any other target path is
    always allowed by this guard (it only protects the one file)."""
    canonical_home = (repo_root / "docs" / "index.html").resolve()
    resolved_target = target_path.resolve()
    if resolved_target != canonical_home:
        return
    if writer_owner != TOP120_OWNER:
        raise HomeOwnershipError(
            f"HOME OWNERSHIP GUARD: refusing to write {resolved_target} "
            f"as writer '{writer_owner}' -- only '{TOP120_OWNER}' may own "
            "the production root HOME."
        )
    if canonical_home.exists():
        existing_owner = extract_owner(canonical_home.read_text(encoding="utf-8"))
        if existing_owner is not None and existing_owner != writer_owner:
            raise HomeOwnershipError(
                f"HOME OWNERSHIP GUARD: {canonical_home} is already owned by "
                f"'{existing_owner}', refusing overwrite by '{writer_owner}'."
            )


def validate_top120_population(dataset: dict) -> None:
    """Hard stop: raises ValueError unless the dataset's records are
    exactly the 120-player K-Ranking population with ranks 1..120,
    no gaps, no duplicates."""
    records = dataset.get("records", [])
    if len(records) != 120:
        raise ValueError(f"TOP120 population must be exactly 120 records, found {len(records)}")
    ranks = sorted(r["official_k_rank"] for r in records)
    if ranks != list(range(1, 121)):
        raise ValueError("TOP120 K-Ranking must be exactly 1..120 with no gaps or duplicates")

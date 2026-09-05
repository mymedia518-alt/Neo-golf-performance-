"""Generic factual-only tournament HTML candidate builder."""

from __future__ import annotations

from html import escape
from pathlib import Path
from hashlib import sha256

from klpga.tournament_factual_publication import (
    FrozenFactualRef,
    FactualPublicationBlocked,
    validate_publication_candidate,
    verify_factual_snapshot,
)


class FactualSiteBlocked(RuntimeError):
    pass


def _text(value) -> str:
    if value is None:
        return ""
    return escape(str(value))


def render_factual_html(
    *,
    tournament_name: str,
    candidate: dict,
    ref: FrozenFactualRef,
) -> str:
    validate_publication_candidate(candidate, ref)
    payload = verify_factual_snapshot(ref)

    if not tournament_name.strip():
        raise FactualSiteBlocked("tournament_name required")

    rows = []

    for player in payload["players"]:
        status = str(player.get("status") or "").upper()

        # Factual-only policy: no probability/model columns exist here.
        rows.append(
            "<tr>"
            f"<td>{_text(player.get('rank_display'))}</td>"
            f"<td>{_text(player.get('player_name'))}</td>"
            f"<td>{_text(player.get('today_under_par_display'))}</td>"
            f"<td>{_text(player.get('holes_completed_display'))}</td>"
            f"<td>{_text(player.get('total_under_par_display'))}</td>"
            f"<td>{_text(status)}</td>"
            "</tr>"
        )

    title = escape(tournament_name)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="neo-publication-mode" content="factual-only">
<meta name="neo-game-code" content="{escape(ref.game_code)}">
<meta name="neo-round-number" content="{ref.round_number}">
<meta name="neo-factual-sha256" content="{ref.sha256}">
<title>{title} | NEO GOLF DATA</title>
<style>
body{{font-family:Arial,"Noto Sans KR",sans-serif;margin:0;background:#fff;color:#111}}
main{{max-width:1100px;margin:auto;padding:24px}}
h1{{font-size:24px;margin:0 0 8px}}
.meta{{font-size:13px;color:#666;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px 8px;border-bottom:1px solid #ddd;text-align:left}}
th{{font-size:13px}}
td{{font-size:14px}}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<div class="meta">Round {ref.round_number} ? ?? ?? ???</div>
<table>
<thead>
<tr>
<th>??</th>
<th>??</th>
<th>??</th>
<th>?? ?</th>
<th>??</th>
<th>??</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</main>
</body>
</html>
"""


def validate_factual_html(
    html: str,
    *,
    ref: FrozenFactualRef,
    expected_rows: int,
) -> None:
    required = [
        'content="factual-only"',
        f'content="{ref.game_code}"',
        f'content="{ref.round_number}"',
        f'content="{ref.sha256}"',
    ]

    for token in required:
        if token not in html:
            raise FactualSiteBlocked(
                f"candidate HTML missing binding: {token}"
            )

    forbidden = [
        "win_pct",
        "top5_pct",
        "top10_pct",
        "top20_pct",
        "make_cut_pct",
        "Top 5",
        "Top 10",
        "Top 20",
    ]

    for token in forbidden:
        if token in html:
            raise FactualSiteBlocked(
                f"model field leaked into factual HTML: {token}"
            )

    if html.count("<tr>") - 1 != expected_rows:
        raise FactualSiteBlocked(
            "HTML player row count mismatch"
        )


def build_factual_site_candidate(
    *,
    tournament_name: str,
    candidate: dict,
    ref: FrozenFactualRef,
    output_root: Path,
) -> Path:
    payload = verify_factual_snapshot(ref)

    html = render_factual_html(
        tournament_name=tournament_name,
        candidate=candidate,
        ref=ref,
    )

    validate_factual_html(
        html,
        ref=ref,
        expected_rows=payload["row_count"],
    )

    target = (
        Path(output_root)
        / ref.game_code
        / f"round-{ref.round_number}"
        / "index.html"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    # Candidate area only. This module has no production docs/ ownership.
    target.write_text(html, encoding="utf-8", newline="\n")

    reread = target.read_text(encoding="utf-8")

    validate_factual_html(
        reread,
        ref=ref,
        expected_rows=payload["row_count"],
    )

    return target


def candidate_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()

"""BETA #001 POST-R3 homepage preview — pure logic (no I/O). Joins
three already-loaded sources by `player_code`:

  1. DB-verified R1-R3 official data (current rank, round-3 score,
     54-hole cumulative total, per-player status) -- the caller reads
     this from the real DB; this module never queries it itself.
  2. The frozen STAGE_R3 `klpga.neo_win.tournament_history.
     HistoryEntrant` tuple (WIN/TOP5/TOP10/TOP20%) -- used EXACTLY as
     frozen, never recomputed here.
  3. `R2_R3_RECOVERY_COMPARISON.csv` rows (the R2->R3 WIN change) --
     used exactly as already computed by `scripts/recover_r2_frozen_
     forecast_and_compare_r3.py`, never recomputed here.

Never fabricates a value a source doesn't have; every validation
function reports mismatches/violations, never silently corrects them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STATUS_ACTIVE = "ACTIVE"
_NON_ADVANCING_STATUSES = {"CUT", "WD", "DQ", "DNS", "UNKNOWN", "COLLECTION_MISSING"}


@dataclass(frozen=True)
class PreviewRow:
    player_code: str
    player_name: str
    status: str
    current_rank: Optional[int]
    current_rank_display: str  # always "T{rank}" (e.g. "T1", "T23") or "unavailable" -- display only
    r3_round_score_to_par: Optional[float]  # round 3 alone, real DB round_to_par
    cumulative_score_to_par: Optional[float]
    win_pct: Optional[float]
    top5_pct: Optional[float]
    top10_pct: Optional[float]
    top20_pct: Optional[float]
    r2_to_r3_win_change_pct: Optional[float]


@dataclass(frozen=True)
class DbPlayerRow:
    player_code: str
    player_name: str
    status: str  # one of STATUS_ACTIVE / _NON_ADVANCING_STATUSES
    r3_round_score_to_par: Optional[float] = None  # round 3 alone, real DB round_to_par
    cumulative_score_to_par: Optional[float] = None  # r1+r2+r3, only when status == ACTIVE and all three real


def compute_current_ranks(db_rows: list[DbPlayerRow]) -> dict[str, int]:
    """Standard competition ranking (1224 style) by ascending
    cumulative_score_to_par among ACTIVE players only: players tied on
    score share the same rank number, and the next distinct score skips
    ahead by the number of players tied at the rank above it (e.g.
    -9, -9, -4 -> 1, 1, 3). This is the real, DB-sourced official
    current rank -- no probability or model value is involved. Display
    formatting (every position shown with a "T" prefix, e.g. "T1",
    "T23") is applied at render time only, see `current_rank_display`
    in `build_preview_rows`."""
    active_with_score = sorted(
        (r for r in db_rows if r.status == STATUS_ACTIVE and r.cumulative_score_to_par is not None),
        key=lambda r: r.cumulative_score_to_par,
    )
    ranks: dict[str, int] = {}
    prev_score: Optional[float] = None
    prev_rank = 0
    for i, r in enumerate(active_with_score, start=1):
        rank = prev_rank if (prev_score is not None and r.cumulative_score_to_par == prev_score) else i
        ranks[r.player_code] = rank
        prev_score, prev_rank = r.cumulative_score_to_par, rank
    return ranks


def build_preview_rows(
    db_rows: list[DbPlayerRow],
    stage_r3_entrants_by_code: dict,
    recovery_change_by_code: dict[str, Optional[float]],
) -> tuple[list[PreviewRow], list[str]]:
    """Returns (rows, warnings). `rows` covers every DB player (ACTIVE
    and non-advancing alike) -- the caller decides how to render each
    status group; ACTIVE and non-advancing rows must never be
    interleaved in the win-probability table (see module docstring)."""
    ranks = compute_current_ranks(db_rows)
    warnings: list[str] = []
    rows: list[PreviewRow] = []

    for db_row in db_rows:
        entrant = stage_r3_entrants_by_code.get(db_row.player_code)
        win_pct = top5 = top10 = top20 = None
        if db_row.status == STATUS_ACTIVE:
            if entrant is None:
                warnings.append(
                    f"{db_row.player_code} ({db_row.player_name}): ACTIVE in DB but absent from STAGE_R3 entrants entirely"
                )
            else:
                win_pct, top5, top10, top20 = entrant.win_pct, entrant.top5_pct, entrant.top10_pct, entrant.top20_pct
                if win_pct is None:
                    warnings.append(f"{db_row.player_code} ({db_row.player_name}): ACTIVE but STAGE_R3 win_pct is None (unavailable)")

        change = recovery_change_by_code.get(db_row.player_code)
        if db_row.status == STATUS_ACTIVE and db_row.player_code not in recovery_change_by_code:
            warnings.append(f"{db_row.player_code} ({db_row.player_name}): ACTIVE but absent from R2_R3_RECOVERY_COMPARISON.csv")

        rank = ranks.get(db_row.player_code)
        rank_display = "unavailable" if rank is None else f"T{rank}"

        rows.append(
            PreviewRow(
                player_code=db_row.player_code, player_name=db_row.player_name, status=db_row.status,
                current_rank=rank, current_rank_display=rank_display,
                r3_round_score_to_par=db_row.r3_round_score_to_par,
                cumulative_score_to_par=db_row.cumulative_score_to_par,
                win_pct=win_pct, top5_pct=top5, top10_pct=top10, top20_pct=top20,
                r2_to_r3_win_change_pct=change,
            )
        )
    return rows, warnings


def sort_active_rows_by_rank_then_win(rows: list[PreviewRow]) -> list[PreviewRow]:
    """Presentation ordering only -- no field value is changed. Primary:
    official current rank ascending (unavailable ranks sort last).
    Secondary: among players sharing the same current rank, WIN%
    descending. Used identically by the HTML table and the console
    TOP-10 summary so both show the same order."""
    return sorted(
        (r for r in rows if r.status == STATUS_ACTIVE),
        key=lambda r: (
            r.current_rank if r.current_rank is not None else float("inf"),
            -(r.win_pct if r.win_pct is not None else -1.0),
        ),
    )


# ---------------------------------------------------------------
# NEO DEEP DIVE teaser selection -- pure selection over already-frozen
# fields (current_rank, cumulative_score_to_par, win_pct). Nothing is
# recomputed, estimated, or interpreted; each function either finds a
# real pattern already present in the data or returns nothing.
# ---------------------------------------------------------------


def select_tied_leaders(rows: list[PreviewRow]) -> list[PreviewRow]:
    """ACTIVE players sharing current_rank == 1, WIN% descending.
    Returns [] unless there are at least 2 (a genuine tie) -- with a
    single outright leader there is no "공동선두" (tied lead) story."""
    leaders = [r for r in sort_active_rows_by_rank_then_win(rows) if r.current_rank == 1]
    return leaders if len(leaders) >= 2 else []


def select_one_stroke_back_inversion(rows: list[PreviewRow]) -> Optional[tuple[PreviewRow, PreviewRow]]:
    """Finds a real (candidate, leader) pair already present in the
    frozen values where candidate is exactly one stroke behind a
    current_rank==1 leader (candidate.cumulative_score_to_par ==
    leader.cumulative_score_to_par + 1) yet candidate.win_pct >
    leader.win_pct -- a genuine numeric rank/WIN-probability inversion.
    Returns None when no such pair exists. Among multiple qualifying
    pairs, picks the one with the SMALLEST WIN% margin (the closest,
    most directly comparable pair); ties broken by player_code for
    determinism. No value is computed or altered -- pure selection."""
    active = sort_active_rows_by_rank_then_win(rows)
    leaders = [r for r in active if r.current_rank == 1 and r.win_pct is not None and r.cumulative_score_to_par is not None]
    if not leaders:
        return None
    candidates = [
        r for r in active
        if r.current_rank is not None and r.current_rank > 1
        and r.win_pct is not None and r.cumulative_score_to_par is not None
    ]
    pairs = [
        (cand.win_pct - leader.win_pct, cand.player_code, leader.player_code, cand, leader)
        for cand in candidates
        for leader in leaders
        if cand.cumulative_score_to_par == leader.cumulative_score_to_par + 1 and cand.win_pct > leader.win_pct
    ]
    if not pairs:
        return None
    pairs.sort(key=lambda t: (t[0], t[1], t[2]))
    _, _, _, cand, leader = pairs[0]
    return cand, leader


# ---------------------------------------------------------------
# Validation — every check reports, never corrects
# ---------------------------------------------------------------


def check_duplicate_player_codes(codes: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    for c in codes:
        seen[c] = seen.get(c, 0) + 1
    return sorted(c for c, n in seen.items() if n > 1)


def check_win_sum(rows: list[PreviewRow], *, tolerance: float = 0.1) -> tuple[float, bool]:
    active_wins = [r.win_pct for r in rows if r.status == STATUS_ACTIVE and r.win_pct is not None]
    total = round(sum(active_wins), 4)
    return total, abs(total - 100.0) <= tolerance


def check_probability_invariants(rows: list[PreviewRow]) -> list[str]:
    violations = []
    for r in rows:
        if r.status != STATUS_ACTIVE:
            continue
        values = (r.win_pct, r.top5_pct, r.top10_pct, r.top20_pct)
        if any(v is None for v in values):
            continue
        win, top5, top10, top20 = values
        if not (0.0 <= win <= top5 <= top10 <= top20 <= 100.0):
            violations.append(
                f"{r.player_code} ({r.player_name}): win={win} top5={top5} top10={top10} top20={top20} "
                "violates 0<=WIN<=TOP5<=TOP10<=TOP20<=100"
            )
    return violations


def reconcile_codes(label_a: str, codes_a: set, label_b: str, codes_b: set) -> dict:
    return {
        "matched": sorted(codes_a & codes_b),
        f"{label_a}_only": sorted(codes_a - codes_b),
        f"{label_b}_only": sorted(codes_b - codes_a),
    }


def format_win_change(value: Optional[float]) -> str:
    if value is None:
        return "unavailable"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%p"


def _fmt_pct(value: Optional[float]) -> str:
    return "unavailable" if value is None else f"{value:.2f}%"


def _fmt_score(value: Optional[float]) -> str:
    if value is None:
        return "unavailable"
    if value == 0:
        return "E"
    return f"+{value:g}" if value > 0 else f"{value:g}"


_NON_ADVANCING_LABEL_KO = {
    "CUT": "컷 탈락", "WD": "기권 (WD)", "DQ": "실격 (DQ)", "DNS": "불참 (DNS)",
    "UNKNOWN": "상태 미확인", "COLLECTION_MISSING": "데이터 누락",
}

# Reuses docs/index.html's own CSS tokens/table/header/footer styles verbatim
# (the real production page's current design) -- the real production file
# itself is never read or written by this module; this is a static copy of
# its <style> block, embedded here for the preview only.
_PREVIEW_CSS = """
  :root {
    --bg: #dde5f3; --bg-alt: #cfdaef; --card-bg: #ffffff; --border: #b8c6e2;
    --text: #16213e; --text-dim: #5b6b85; --accent: #0f9488; --accent-blue: #2f5fd9;
    --pill-bg: #dff5f0; --pill-text: #0b7d6f; --row-alt: #eaf0fa;
    --warn-bg: #fdf1e0; --warn-text: #a65b12;
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px 18px 72px; background: var(--bg); color: var(--text); font-family: "Noto Sans KR", sans-serif; }
  header, main, section.forecast, section.non-advancing, section.deep-dive, footer { max-width: 980px; margin-left: auto; margin-right: auto; }
  header { margin-bottom: 28px; }
  .wordmark { --row: clamp(12px, 3vw, 16px); display: flex; align-items: center; gap: clamp(12px, 3.2vw, 20px); margin-bottom: 10px; }
  .wordmark-letters { display: flex; flex-direction: column; gap: calc(var(--row) * 0.15); flex-shrink: 0; }
  .letter-row { display: flex; align-items: baseline; gap: calc(var(--row) * 0.42); white-space: nowrap; }
  .letter { font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 1.15); line-height: 1; color: var(--accent); }
  .letter-word { font-family: "Big Shoulders Display", sans-serif; font-weight: 600; font-size: calc(var(--row) * 0.72); line-height: 1; letter-spacing: 0.04em; color: var(--text-dim); white-space: nowrap; }
  .wordmark-name { font-family: "Big Shoulders Display", sans-serif; font-weight: 800; font-size: calc(var(--row) * 3.75); line-height: 1; letter-spacing: 0.015em; color: var(--text); white-space: nowrap; }
  .meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
  .meta .tournament-name { font-size: clamp(14px, 3.5vw, 18px); color: var(--text-dim); }
  .status-pill { background: var(--pill-bg); color: var(--pill-text); font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; }
  .preview-banner { background: var(--warn-bg); color: var(--warn-text); font-size: 13px; font-weight: 700; padding: 10px 16px; border-radius: 10px; margin-bottom: 20px; }
  section.forecast h2 { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(18px, 4.5vw, 22px); margin: 24px 0 4px; }
  section.forecast .forecast-sub { color: var(--text-dim); font-size: 13px; margin: 0 0 16px; }
  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; background: var(--card-bg); box-shadow: 0 1px 3px rgba(22,33,62,0.08); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; min-width: 480px; }
  thead th { text-align: center; font-weight: 600; color: var(--text-dim); background: var(--bg-alt); padding: 5px 5px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  tbody td { text-align: center; padding: 3px 5px; border-bottom: 1px solid var(--border); font-family: "Roboto Mono", monospace; white-space: nowrap; }
  tbody td.c-name { font-family: "Noto Sans KR", sans-serif; }
  tbody tr:nth-child(even) { background: var(--row-alt); }
  tbody td.c-pct { color: var(--accent-blue); font-weight: 600; font-size: 12px; }
  tbody td.c-change-pos { color: var(--accent); font-weight: 700; }
  tbody td.c-change-neg { color: #b23a3a; font-weight: 700; }
  section.non-advancing { margin-top: 28px; }
  section.non-advancing summary { cursor: pointer; font-family: "Big Shoulders Display", sans-serif; font-size: 16px; color: var(--text-dim); list-style: none; }
  section.non-advancing summary::-webkit-details-marker { display: none; }
  section.non-advancing summary::before { content: "▸ "; }
  section.non-advancing details[open] summary::before { content: "▾ "; }
  .non-advancing-list { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
  .non-advancing-list li { background: var(--bg-alt); color: var(--text-dim); font-size: 12px; padding: 5px 12px; border-radius: 999px; }
  section.deep-dive { margin-top: 28px; padding: 18px 20px 20px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 1px 3px rgba(22,33,62,0.08); }
  section.deep-dive h2 { font-family: "Big Shoulders Display", sans-serif; font-size: clamp(16px, 4vw, 20px); letter-spacing: 0.04em; color: var(--accent); margin: 0 0 14px; }
  .deep-dive-card + .deep-dive-card { margin-top: 22px; padding-top: 22px; border-top: 1px solid var(--border); }
  .deep-dive-headline { font-weight: 700; font-size: 15px; margin: 0 0 12px; }
  .deep-dive-compare, .deep-dive-vs { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 10px; }
  .dd-vs-label { font-weight: 700; color: var(--text-dim); font-size: 12px; padding: 0 4px; }
  .deep-dive-player { flex: 1 1 130px; background: var(--bg-alt); border-radius: 8px; padding: 10px 12px; }
  .dd-name { font-family: "Noto Sans KR", sans-serif; font-weight: 700; font-size: 14px; margin-bottom: 2px; }
  .dd-rank { font-family: "Roboto Mono", monospace; font-size: 12px; color: var(--text-dim); margin-bottom: 4px; }
  .dd-win { font-family: "Roboto Mono", monospace; font-weight: 700; color: var(--accent-blue); font-size: 15px; }
  .deep-dive-desc { color: var(--text-dim); font-size: 13px; margin: 0; }
  .deep-dive-cta { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border); color: var(--text-dim); font-size: 13px; font-weight: 600; text-align: center; }
  footer { margin-top: 56px; padding-bottom: 8px; text-align: center; color: var(--text-dim); font-size: 11px; line-height: 1.7; }
  .footer-line { margin: 0; }
  .disclaimer { font-weight: 600; }
  @media (max-width: 480px) {
    .wordmark { flex-wrap: wrap; row-gap: 4px; }
    .wordmark-name { --row: 10px; white-space: normal; font-size: calc(var(--row) * 2.4); line-height: 1.05; }
  }
"""


def _dd_player_card(r: PreviewRow) -> str:
    return (
        '<div class="deep-dive-player">'
        f'<div class="dd-name">{r.player_name}</div>'
        f'<div class="dd-rank">{r.current_rank_display} / {_fmt_score(r.cumulative_score_to_par)}</div>'
        f'<div class="dd-win">WIN {_fmt_pct(r.win_pct)}</div>'
        "</div>"
    )


_DEEP_DIVE_COUNT_KO = {2: "두", 3: "세", 4: "네", 5: "다섯", 6: "여섯"}


def _render_deep_dive_section(rows: list[PreviewRow]) -> str:
    """Teaser only -- no model explanation, no new interpretation. Each
    card renders only when the real, already-frozen data supports its
    premise (see `select_tied_leaders` / `select_one_stroke_back_
    inversion`); otherwise that card (or the whole section) is omitted
    rather than fabricated. The CTA is inert text, never a fabricated
    link -- there is no detail page yet."""
    leaders = select_tied_leaders(rows)
    inversion = select_one_stroke_back_inversion(rows)

    cards = []
    if leaders:
        count_word = _DEEP_DIVE_COUNT_KO.get(len(leaders), str(len(leaders)))
        cards.append(
            '<div class="deep-dive-card">'
            '<p class="deep-dive-headline">같은 공동선두 '
            f'{_fmt_score(leaders[0].cumulative_score_to_par)}, 그런데 우승확률은 왜 다를까?</p>'
            f'<div class="deep-dive-compare">{"".join(_dd_player_card(r) for r in leaders)}</div>'
            f'<p class="deep-dive-desc">{count_word} 선수 모두 공동선두에서 최종라운드를 시작하지만 '
            'NEO가 계산한 우승확률은 서로 다릅니다.</p>'
            "</div>"
        )
    if inversion:
        cand, leader = inversion
        cards.append(
            '<div class="deep-dive-card">'
            '<p class="deep-dive-headline">한 타 뒤인데 우승확률은 더 높다</p>'
            f'<div class="deep-dive-vs">{_dd_player_card(cand)}<div class="dd-vs-label">VS</div>{_dd_player_card(leader)}</div>'
            '<p class="deep-dive-desc">현재 순위만으로는 설명되지 않는 차이입니다.</p>'
            "</div>"
        )

    if not cards:
        return ""

    return (
        '<section class="deep-dive">'
        "<h2>NEO DEEP DIVE</h2>"
        f'{"".join(cards)}'
        '<div class="deep-dive-cta" aria-disabled="true">왜 이런 차이가 날까? → NEO DEEP DIVE</div>'
        "</section>"
    )


def render_preview_html(
    rows: list[PreviewRow], *, tournament_name: str, game_code: str,
) -> str:
    """Pure string template -- no I/O. `rows` is sorted here by official
    current rank ascending, then WIN% descending within a tied rank
    (see `sort_active_rows_by_rank_then_win`); non-advancing rows are
    rendered in a SEPARATE section, never interleaved with ACTIVE rows."""
    active = sort_active_rows_by_rank_then_win(rows)
    non_advancing = [r for r in rows if r.status != STATUS_ACTIVE]

    table_rows = []
    for r in active:
        change = r.r2_to_r3_win_change_pct
        change_cls = "c-change-pos" if (change is not None and change > 0) else ("c-change-neg" if (change is not None and change < 0) else "")
        table_rows.append(
            f'<tr><td class="c-pos">{r.current_rank_display}</td>'
            f'<td class="c-name">{r.player_name}</td>'
            f'<td class="c-score">{_fmt_score(r.r3_round_score_to_par)}</td>'
            f'<td class="c-score">{_fmt_score(r.cumulative_score_to_par)}</td>'
            f'<td class="c-pct">{_fmt_pct(r.win_pct)}</td>'
            f'<td class="c-pct">{_fmt_pct(r.top5_pct)}</td>'
            f'<td class="c-pct">{_fmt_pct(r.top10_pct)}</td>'
            f'<td class="c-pct">{_fmt_pct(r.top20_pct)}</td>'
            f'<td class="{change_cls}">{format_win_change(change)}</td></tr>'
        )

    non_advancing_items = "".join(
        f'<li>{r.player_name} — {_NON_ADVANCING_LABEL_KO.get(r.status, r.status)}</li>' for r in non_advancing
    )

    deep_dive_html = _render_deep_dive_section(rows)

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEO POST-R3 Preview — {tournament_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;800&family=Noto+Sans+KR:wght@400;500;700&family=Roboto+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{_PREVIEW_CSS}</style>
</head>
<body>
<div class="preview-banner">PREVIEW ONLY — 배포 전 검토용, 실제 production 페이지가 아닙니다 (game_code: {game_code})</div>
<header>
  <div class="wordmark">
    <div class="wordmark-letters">
      <div class="letter-row"><span class="letter">N</span><span class="letter-word">NUMBER</span></div>
      <div class="letter-row"><span class="letter">E</span><span class="letter-word">EVIDENCE</span></div>
      <div class="letter-row"><span class="letter">O</span><span class="letter-word">ORACLE</span></div>
    </div>
    <div class="wordmark-name">TOURNAMENT PREDICTION</div>
  </div>
  <div class="meta">
    <span class="tournament-name">{tournament_name}</span>
    <span class="status-pill">POST-R3 / FINAL ROUND FORECAST</span>
  </div>
</header>

<main>
  <section class="forecast">
    <h2>3R 종료 후 우승 경쟁 예측</h2>
    <p class="forecast-sub">4R 시작 전 동결된 예측입니다. 이후 결과에 따라 수정하지 않습니다.</p>
    <p class="forecast-sub">현재 순위가 같아도 선수별 경기력 평가에 따라 우승확률은 다릅니다.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>현재 순위</th><th>선수</th><th>3R</th><th>합계</th>
            <th>WIN</th><th>TOP5</th><th>TOP10</th><th>TOP20</th>
            <th>R2→R3 WIN 변화</th>
          </tr>
        </thead>
        <tbody>
          {"".join(table_rows)}
        </tbody>
      </table>
    </div>
  </section>

  {deep_dive_html}

  <section class="non-advancing">
    <details>
      <summary>최종라운드 비진출 선수 {len(non_advancing)}명 보기</summary>
      <ul class="non-advancing-list">{non_advancing_items}</ul>
    </details>
  </section>
</main>

<footer>
  <div class="footer-line disclaimer">Probabilities represent NEO model estimates for the final tournament result after Round 4.</div>
  <div class="footer-line">&copy; 2026 NEO GOLF DATA. All Rights Reserved.</div>
</footer>
</body>
</html>
"""

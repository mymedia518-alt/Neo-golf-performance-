"""Build the OK Open PRE candidate from the canonical public master only."""
from __future__ import annotations

import datetime
import argparse
import html
import json
import hashlib
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.freshness_gate import STALE_NOTICE_MARKER, is_snapshot_stale  # noqa: E402
from klpga.website_v2.global_navigation import inject_global_navigation  # noqa: E402
from klpga.website_v2.shell import breadcrumb_html, stage_nav_html  # noqa: E402
from klpga.website_v2.player_identity import (  # noqa: E402
    cross_tournament_verified_sponsor_cache, render_player_identity,
    sponsor_with_cross_tournament_fallback,
)
from klpga.tournament_context import candidate_dir, load_active_tournament_context, load_tournament_context  # noqa: E402
from klpga.website_v2.tournament_state import OK_BASE, OK_DATE_RANGE, OK_DISPLAY_NAME, ok_open_available_stages  # noqa: E402

OUT = candidate_dir("website-v2-ok-open-pre")

# NEO TOURNAMENT PIPELINE: venue/holes/format have no home in
# tournament_state.py's existing constants -- resolved here from the
# shared context instead of this script's own hardcoded literal string.
_CONTEXT = load_active_tournament_context()
STAGE_STATE_PATH = ROOT / "content" / "website_v2" / _CONTEXT.stage_state_filename
MASTER = _CONTEXT.artifact_path("pre_public_master")
R1_LIVE_SNAPSHOT = _CONTEXT.artifact_path("r1_live_snapshot")
R2_LIVE_SNAPSHOT = _CONTEXT.artifact_path("r2_live_snapshot")
R1_FINAL_SNAPSHOT_DIR = _CONTEXT.artifact_path("r1_final_snapshots_dir")


def _bind_context(context) -> None:
    """Bind renderer inputs to one explicit tournament context."""
    global _CONTEXT, STAGE_STATE_PATH, MASTER, R1_LIVE_SNAPSHOT, R2_LIVE_SNAPSHOT, R1_FINAL_SNAPSHOT_DIR
    _CONTEXT = context
    STAGE_STATE_PATH = ROOT / "content" / "website_v2" / context.stage_state_filename
    MASTER = context.artifact_path("pre_public_master")
    R1_LIVE_SNAPSHOT = context.artifact_path("r1_live_snapshot")
    R2_LIVE_SNAPSHOT = context.artifact_path("r2_live_snapshot")
    R1_FINAL_SNAPSHOT_DIR = context.artifact_path("r1_final_snapshots_dir")

# P0 MODEL SAFETY PATCH -- LIVE PROBABILITY PUBLICATION BLOCK: the ONE
# gate every probability-derived R1 output must pass before rendering.
# A successfully executed simulation is not sufficient for publication
# -- only klpga.neo_win.r1_live_probability.LIVE_PROBABILITY_MODEL_STATUS
# == "VALIDATED" is. See that module for the full defect record.
MODEL_VALIDATED_FOR_PUBLICATION = False
MODEL_BLOCKED_NOTE = (
    "NEO 확률 지표(Cut%·Top20%·Top10%·Top5%·Win%·PRE 대비 Win Δ·NEO 예상 컷·NEO Movers)는 "
    "시뮬레이션 모델 점검(Red Team 검증)으로 검증 완료 전까지 비공개 처리됩니다. "
    "완료홀 기준 실제 스코어만 표시합니다."
)


def _pre_probability_publication_approved(context) -> bool:
    """Bind PRE visibility to the immutable V2 snapshot, never R1 LIVE state."""
    freeze_path = context.artifact_path("pre_5prob_v2_frozen")
    evaluation_path = ROOT / "content" / "website_v2" / "NEO_PRE_5PROB_V2_WALK_FORWARD.json"
    master_path = context.artifact_path("pre_public_master")
    if not all(path.is_file() for path in (freeze_path, evaluation_path, master_path)):
        return False
    try:
        freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        master = json.loads(master_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if (
        freeze.get("gameCode") != context.game_code
        or freeze.get("stage") != "PRE"
        or freeze.get("model_version") != "NEO_PRE_5PROB_V2"
        or freeze.get("official_field_count") != 120
        or evaluation.get("overall_frozen_win_gate_pass") is not True
        or freeze.get("source_hashes", {}).get("walk_forward_evaluation_sha256") != hashlib.sha256(evaluation_path.read_bytes()).hexdigest()
        or master.get("pre_probability_publication", {}).get("status") != "APPROVED"
    ):
        return False
    frozen_by = {str(row["playerCode"]): row for row in freeze.get("predictions", [])}
    public_records = master.get("records", [])
    if len(frozen_by) != 120 or len(public_records) != 120:
        return False
    probability_keys = ("cut_probability", "top20_probability", "top10_probability", "top5_probability", "win_probability")
    for record in public_records:
        frozen = frozen_by.get(str(record.get("player_id")))
        if frozen is None or any(record.get(key) != frozen.get(key) for key in probability_keys):
            return False
    return True


def _ok_stage_items(current: str) -> list[tuple[str, str | None, bool]]:
    # Same shared component KG uses (shell.stage_nav_html). Which stages
    # are real (not a disabled/fake link) comes from the single shared
    # tournament_state.ok_open_available_stages() -- the same function
    # HOME's tournament-day hero reads -- not a second, hand-duplicated
    # copy of this dict.
    real = ok_open_available_stages()
    return [
        (label.upper(), real.get(key), key == current)
        for key, label in (("pre", "PRE"), ("r1", "R1"), ("r2", "R2"), ("final", "FINAL"))
    ]


def _context_stage_items(current: str, *, historical_ok_mode: bool) -> list[tuple[str, str | None, bool]]:
    if historical_ok_mode:
        return _ok_stage_items(current)
    return [
        (
            _CONTEXT.stage_labels.get(key, key.upper()).upper(),
            f"{_CONTEXT.url_base}{key}/" if key == "pre" else None,
            key == current,
        )
        for key in _CONTEXT.stage_order
    ]

def _fmt_pct(v) -> str:
    # A NEO/model cell that could not be computed for this player (no
    # PRE baseline, no R1 score yet, etc.) renders as a plain empty
    # cell -- never "산출 불가", which reads as its own kind of computed
    # result ("we tried and failed") rather than "there is nothing to
    # show here".
    return "" if v is None else f"{v:.1f}%"


def _fmt_stroke(v) -> str:
    return "산출 불가" if v is None else f"{v:+.1f}"


# Generic status-aware rendering -- never a per-player-name special case.
#
# klpga.parsers.leaderboard_parser's confirmed data-rank="999" sentinel
# ("a player who does not complete a round" -- the source data cannot
# distinguish WD/DQ/other from this, and never guesses) is parsed as
# status="INCOMPLETE". This is the ONLY did-not-complete signal ever
# actually observed live so far.
#
# "WD"/"DQ" literal text values are also a defined (never yet observed
# live) possibility per that same parser's _STATUS_VALUES -- handled
# here defensively with the identical blank-cell treatment, so that IF
# KLPGA's endpoint ever does emit one, this renderer already does the
# right thing rather than leaking a raw enum string or a fabricated
# rank. CUT is deliberately excluded: a cut player has a real, valid
# completed score and rank (they simply won't play the remaining
# rounds), so their row must never be blanked.
#
# Every one of these labels is honest about what is and is not known --
# the raw "999" sentinel (status="INCOMPLETE") gets NO status label at
# all, just "—" like the row's other unknown cells: the source itself
# never says WD or DQ, so printing a Korean sentence in that cell would
# only dress up a guess as a fact. "WD"/"DQ" are shown as literal text
# only when the source itself literally reports that exact word, never
# inferred from a player's name, holes-completed count, or any other
# signal.
_UNRESOLVED_STATUSES = {"INCOMPLETE", "WD", "DQ"}
# PUBLIC UI Phase 8 correction (Red Team FAIL C): "ACTIVE" is this
# module's own internal completion sentinel (see the FINAL-mode row
# mapping above) -- never a public-facing word. Mapped to its honest
# Korean label here so it never leaks into the rendered 상태 cell.
_STATUS_LABELS = {"WD": "WD", "DQ": "DQ", "ACTIVE": "완료"}


def _r1_row_html(r: dict, sponsor_by_id: dict, prob_cells) -> str:
    """One player's R1 table row. A row whose status is did-not-complete
    (_UNRESOLVED_STATUSES -- the confirmed "999" rank sentinel, or a
    literal WD/DQ status) leaves 순위/현재스코어/오늘스코어/선두와 타수차
    completely EMPTY (never a fabricated "999"-as-rank, never "—", never
    three separately repeated "산출 불가" cells) -- an empty cell reads
    as "not applicable", a dash or a Korean sentence both read as "we
    computed something". The 상태 cell itself is also empty when all the
    source gives us is the raw 999 sentinel (status="INCOMPLETE") --
    there is no honest word for "player stopped playing for an unknown
    reason", so the row shows only what is actually known (name, holes
    completed) and nothing else. "WD"/"DQ" are shown as literal text
    only on a row whose status IS literally that word."""
    status = r.get("status")
    unresolved = status in _UNRESOLVED_STATUSES
    rank_cell = "" if unresolved else html.escape(str(r.get("rank_display") or ""))
    total_cell = "" if unresolved else html.escape(str(r.get("total_under_par_display") or ""))
    today_cell = "" if unresolved else _fmt_stroke(r.get("today_under_par"))
    gap_cell = "" if unresolved else _fmt_stroke(r.get("gap_to_leader"))
    if status == "INCOMPLETE":
        status_cell = ""
    else:
        status_cell = html.escape(_STATUS_LABELS.get(status, status or "진행중"))
    return (
        f"<tr><td>{rank_cell}</td>"
        f"<th scope='row'>{_player_identity_cell(r.get('player_name'), sponsor_by_id.get(str(r.get('player_id') or '')))}</th>"
        f"<td>{total_cell}</td>"
        f"<td>{html.escape(str(r.get('holes_completed') or ''))}</td>"
        f"<td>{today_cell}</td>"
        f"<td>{gap_cell}</td>"
        f"{prob_cells(r)}"
        f"<td>{status_cell}</td></tr>"
    )


def _fmt_delta_pct(current, pre_fraction) -> str:
    """current: 0..100 or None. pre_fraction: 0..1 or None (OK Open's
    PRE model explicitly left top5/top10/top20 unsupported for most
    players -- a missing PRE baseline means the delta genuinely cannot
    be computed, never defaulted to 0)."""
    if current is None or pre_fraction is None:
        return ""
    return f"{current - pre_fraction * 100:+.1f}%p"


def _player_identity_cell(name, sponsor) -> str:
    """The ONE shared player-identity cell markup -- name (existing
    emphasis/weight) plus a sponsor slot directly underneath, ALWAYS
    present structurally even when empty (never omitted, never a
    guessed value or placeholder dash -- see render_player_identity's
    own docstring). Reused by every OK Open stage table that renders
    player rows (PRE today; R1 below; any future R2/R3/FINAL row
    renderer should call this too) so affiliation handling never
    diverges by stage.

    PUBLIC UI Phase 8 correction (FAIL 2) / PRODUCT RECOVERY V1
    (design-system consolidation, phase 1): delegates to the one
    shared player-identity rule (src/klpga/website_v2/player_identity.py)
    and now also its default CSS classes (player-name/player-sponsor,
    the same ones neo-site.css already styles for HOME/RANKING) --
    this page's previously separate .player/.sponsor rules are removed
    from its own CSS block below in favor of the shared ones."""
    return render_player_identity(
        name if name is not None else "—", sponsor, quote="'",
    )


def _mover_line(entry: dict, *, kind: str, sponsor_by_id: dict) -> str:
    # PUBLIC UI Phase 8 correction (FAIL A): every public player mention,
    # including this movers/highlights list, uses the one shared
    # identity cell (name slot + sponsor slot, always both present) --
    # never a bare name span.
    name_raw = entry.get("player_name") or "—"
    identity = _player_identity_cell(name_raw, sponsor_by_id.get(str(entry.get("player_id") or "")))
    if kind == "pct":
        return f"<li>{identity}<span class='delta'>{entry.get('delta', 0):+.1f}%p</span></li>"
    if kind == "cut_band":
        return f"<li>{identity}<span class='delta'>현재 컷 통과 {entry.get('current_value', 0):.1f}%</span></li>"
    if kind == "strokes":
        return f"<li>{identity}<span class='delta'>{entry.get('delta', 0):+.1f}타</span></li>"
    return f"<li>{identity}</li>"


def _movers_list(entries: list, *, kind: str, empty_note: str, sponsor_by_id: dict) -> str:
    if not entries:
        return f"<p class='note'>{html.escape(empty_note)}</p>"
    return f"<ul class='mover-list'>{''.join(_mover_line(e, kind=kind, sponsor_by_id=sponsor_by_id) for e in entries)}</ul>"


def _r2_live_leaderboard_section(nav: str, sponsor_by_id: dict) -> str | None:
    if not R2_LIVE_SNAPSHOT.is_file():
        return None

    snapshot = json.loads(
        R2_LIVE_SNAPSHOT.read_text(encoding="utf-8")
    )

    table = snapshot.get("player_table") or []

    if not table:
        return None

    rows = []

    for r in table:
        status = str(
            r.get("status") or "ACTIVE"
        ).upper()

        unresolved = status == "INCOMPLETE"

        def esc(value):
            return html.escape(
                str(value or "")
            )

        rank = (
            ""
            if unresolved
            else esc(r.get("rank_display"))
        )

        today = (
            ""
            if unresolved
            else esc(
                r.get(
                    "today_under_par_display"
                )
            )
        )

        total = (
            ""
            if unresolved
            else esc(
                r.get(
                    "total_under_par_display"
                )
            )
        )

        holes = esc(
            r.get(
                "holes_completed_display"
            )
        )

        status_cell = (
            ""
            if status in {
                "ACTIVE",
                "INCOMPLETE"
            }
            else html.escape(status)
        )

        player = _player_identity_cell(
            r.get("player_name"),
            sponsor_by_id.get(
                str(
                    r.get("player_id")
                    or ""
                )
            ),
        )

        rows.append(
            f"<tr>"
            f"<td>{rank}</td>"
            f"<th scope='row'>{player}</th>"
            f"<td>{today}</td>"
            f"<td>{holes}</td>"
            f"<td>{total}</td>"
            f"<td>{status_cell}</td>"
            f"</tr>"
        )

    collected = html.escape(
        str(
            snapshot.get(
                "collected_at"
            ) or ""
        )
    )

    # ASCII Python source? ????
    # ????? ??? ??? Unicode ??
    title = (
        "\u0032\uB77C\uC6B4\uB4DC "
        "\uACF5\uC2DD "
        "\uB9AC\uB354\uBCF4\uB4DC"
    )

    note = (
        "KLPGA "
        "\uACF5\uC2DD R2 "
        "\uB370\uC774\uD130"
    )

    blocked = (
        "\uD655\uB960/\uC608\uCE21 "
        "\uC9C0\uD45C "
        "\uBE44\uACF5\uAC1C"
    )

    heads = [
        "\uC21C\uC704",
        "\uC120\uC218",
        "R2",
        "\uC644\uB8CC\uD640",
        "\uD569\uACC4",
        "\uC0C1\uD0DC",
    ]

    return (
        '<section class="panel">'
        '<p class="eyebrow">'
        'R2 &middot; LIVE'
        '</p>'
        f'<h1>{title}</h1>'
        f'<p class="note">'
        f'{note} &middot; '
        f'{collected} &middot; '
        f'{blocked}'
        f'</p>'
        f'{nav}'
        '<div class="table-wrap">'
        '<table class="data">'
        '<thead><tr>'
        + "".join(
            f"<th>{x}</th>"
            for x in heads
        )
        + '</tr></thead>'
        '<tbody>'
        + "".join(rows)
        + '</tbody>'
        '</table>'
        '</div>'
        '</section>'
    )


def _r1_live_leaderboard_section(nav: str, sponsor_by_id: dict) -> str | None:
    """R1 ACTIVE MODE: render the real, official leaderboard rows a
    validated scripts/96 cycle collected, PLUS the same cycle's
    klpga.neo_win.r1_live_probability Monte Carlo output (Cut/Top20/
    Top10/Top5/Win probabilities, an explicit cut-line DISTRIBUTION
    rather than one asserted number, and NEO Movers vs the frozen PRE
    baseline). Every probability that could not be computed for a
    player (missing R1 score, or no PRE baseline to compare against)
    renders as a plain empty cell, never "산출 불가" and never a guessed
    value. Returns None (falls back to the "no official data yet"
    placeholder in the caller) when no snapshot that passed its safety
    gate exists yet.

    `sponsor_by_id`: player_id -> current_official_sponsor (or None),
    resolved by the caller from the canonical PRE public master (the
    R1 live snapshot itself carries no sponsor field). Looked up by
    player_id only -- never falls back to name matching, so an
    unresolved identity never silently inherits the wrong player's
    affiliation."""
    final_mode = False
    final_rows = []
    if STAGE_STATE_PATH.is_file():
        try:
            final_mode = bool(json.loads(STAGE_STATE_PATH.read_text(encoding="utf-8")).get("r1_complete"))
        except (OSError, ValueError):
            final_mode = False
    if final_mode and R1_FINAL_SNAPSHOT_DIR.is_dir():
        # Generic glob (Phase 5 item 2): R1_FINAL_SNAPSHOT_DIR is already
        # this tournament's own registry-mapped directory (isolation
        # comes from the directory, never from an OK-Open-specific
        # filename prefix inside it).
        candidates = sorted(R1_FINAL_SNAPSHOT_DIR.glob("*_FINAL_*.json"))
        if candidates:
            final_doc = json.loads(candidates[-1].read_text(encoding="utf-8"))
            live_names = {}
            if R1_LIVE_SNAPSHOT.is_file():
                live_doc = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
                live_names = {str(r.get("player_id")): r.get("player_name") for r in (live_doc.get("player_table") or [])}
            # QA REMEDIATION (post-fbb69de): _r1_row_html reads rank_display/
            # total_under_par_display/today_under_par/gap_to_leader -- none
            # of which this final-mode mapping used to set, so every
            # completed player's real, known score silently rendered as a
            # blank cell (or a misleading "산출 불가") instead of their
            # actual final score. today_under_par equals the round's own
            # total here (FINAL is a single-round reconciliation, so
            # "today" and "total" are the same number); gap_to_leader is
            # computed against the lowest real final_score among rows that
            # actually completed, exactly like the live-cycle leader/gap
            # logic below (never guessed for WD/DQ/no-score rows).
            leader_score = min(
                (row.get("final_score") for row in (final_doc.get("rows") or [])
                 if row.get("final_score") is not None),
                default=None,
            )
            for row in final_doc.get("rows") or []:
                pid = str(row.get("player_id") or "")
                status = row.get("official_status") or ("ACTIVE" if row.get("final_score") is not None else "INCOMPLETE")
                score = row.get("final_score")
                final_rows.append({
                    "player_id": pid, "player_name": live_names.get(pid) or row.get("player_name") or pid,
                    "total_under_par": score, "total_under_par_display": None if score is None else str(score),
                    "holes_completed": 18 if status == "ACTIVE" else None,
                    "today_under_par": score,
                    "gap_to_leader": None if score is None or leader_score is None else score - leader_score,
                    "status": status, "rank": row.get("rank_display") or "",
                    "rank_display": row.get("rank_display") or "",
                })
    if final_rows:
        snapshot = {"rows": final_rows, "player_table": final_rows, "collected_at": final_doc.get("collected_at"), "final_mode": True}
    elif not R1_LIVE_SNAPSHOT.is_file():
        return None
    else:
        snapshot = json.loads(R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    table = snapshot.get("player_table") or []
    if not table:
        return None

    collected_at_iso = snapshot.get("collected_at")
    collected_at = html.escape(str(collected_at_iso or ""))
    leader = table[0] if table and table[0].get("total_under_par") is not None else None
    # Tied leaders: table is already sorted ascending by total_under_par
    # (see script 96's _build_player_table), so every row sharing
    # leader's score is also in the lead -- never arbitrarily show only
    # the first name when players are tied.
    tied_leaders = [r.get("player_name") for r in table if leader is not None and r.get("total_under_par") == leader.get("total_under_par")]
    leader_display = ", ".join(html.escape(str(n)) for n in tied_leaders) if tied_leaders else "산출 불가"
    # P0 STALE-DATA INCIDENT REMEDIATION: a snapshot older than the
    # freshness threshold (klpga.website_v2.freshness_gate) must never
    # imply the normal 30-minute live cadence is still current -- an
    # honest "collection delayed" notice replaces it instead. The
    # underlying scores/holes/probabilities themselves are NEVER
    # altered here; this only changes what the page says about their
    # freshness. scripts/94's promotion gate hard-stops if this notice
    # is ever missing from a stale build.
    now = datetime.datetime.now(datetime.timezone.utc)
    stale = is_snapshot_stale(collected_at_iso, now)
    live_cadence_note = STALE_NOTICE_MARKER if stale else "라이브 업데이트 주기 30분"
    # P0 MODEL SAFETY PATCH: cutline (an expected-cut-line DISTRIBUTION
    # from the same blocked Monte Carlo simulation) is a probability
    # output exactly like Cut%/Win% below -- gated identically. Omitted
    # entirely while blocked, never shown as "산출 불가" (that would
    # read as "not yet computed", not "withheld").
    cutline = snapshot.get("expected_cut_distribution")
    cutline_text = (
        f"{cutline['p10']:+.1f} ~ {cutline['p90']:+.1f} (중앙값 {cutline['p50']:+.1f})" if cutline else "산출 불가"
    )
    cutline_stat = (
        f"<div><span class='label'>NEO 예상 컷 (분포)</span><strong>{html.escape(cutline_text)}</strong></div>"
        if MODEL_VALIDATED_FOR_PUBLICATION
        else ""
    )

    movers = snapshot.get("neo_movers") or {}
    # P0 MODEL SAFETY PATCH: EVERY NEO Movers list traces to the same
    # blocked simulation -- win_pct_risers/fallers and
    # cut_pct_droppers_vs_band all read probabilities computed by
    # simulate_r1_live(build_r1_sim_inputs(...)). "기대 이상/이하"
    # (beat_expectation/missed_expectation) were already hidden by an
    # earlier, narrower fix (the SG-baseline conversion specifically);
    # this patch additionally withholds the three that fix left visible,
    # since none of them has an independent, unaffected calculation --
    # so the entire "NEO Movers" section has nothing left to publish
    # and is omitted outright rather than rendered empty. The
    # underlying compute_neo_movers() output and this snapshot's own
    # neo_movers data are UNCHANGED; only the public HTML presentation
    # is withheld. Restore per-list once LIVE_PROBABILITY_MODEL_STATUS
    # is "VALIDATED" -- do not re-derive or duplicate the logic elsewhere.
    movers_section = ""
    if MODEL_VALIDATED_FOR_PUBLICATION:
        movers_html = (
            f"<div class='mover-grid'>"
            f"<div><h3>Win% 상승</h3>{_movers_list(movers.get('win_pct_risers') or [], kind='pct', empty_note='PRE 우승확률이 있는 선수 중 상승한 선수가 없습니다.', sponsor_by_id=sponsor_by_id)}</div>"
            f"<div><h3>Win% 하락</h3>{_movers_list(movers.get('win_pct_fallers') or [], kind='pct', empty_note='PRE 우승확률이 있는 선수 중 하락한 선수가 없습니다.', sponsor_by_id=sponsor_by_id)}</div>"
            f"<div><h3>컷 통과 위험 (PRE 상위권 기준)</h3>{_movers_list(movers.get('cut_pct_droppers_vs_band') or [], kind='cut_band', empty_note='PRE 상위권 선수 중 컷 통과 위험이 확인된 선수가 없습니다.', sponsor_by_id=sponsor_by_id)}</div>"
            f"</div>"
        )
        movers_section = f"<section class='panel'><h2>NEO Movers · PRE 대비 변화</h2>{movers_html}</section>"

    def _prob_cells(r: dict) -> str:
        # P0 MODEL SAFETY PATCH: Cut%/Top20%/Top10%/Top5%/Win%/"PRE 대비
        # Win Δ" all derive from the same blocked simulation (Win Δ
        # additionally depends on win_pct itself) -- omitted as columns
        # entirely while blocked, never rendered as 0% or "산출 불가"
        # (both would misrepresent "withheld pending model validation"
        # as "computed but empty/unavailable").
        if not MODEL_VALIDATED_FOR_PUBLICATION:
            return ""
        return (
            f"<td>{_fmt_pct(r.get('cut_pct'))}</td>"
            f"<td>{_fmt_pct(r.get('top20_pct'))}</td>"
            f"<td>{_fmt_pct(r.get('top10_pct'))}</td>"
            f"<td>{_fmt_pct(r.get('top5_pct'))}</td>"
            f"<td>{_fmt_pct(r.get('win_pct'))}</td>"
            f"<td>{_fmt_delta_pct(r.get('win_pct'), r.get('pre_win_probability'))}</td>"
        )

    body_rows = "".join(_r1_row_html(r, sponsor_by_id, _prob_cells) for r in table)

    summary = (
        f"<section class='panel r1-live-summary' aria-label='R1 라이브 요약'>"
        f"<p class='eyebrow'>R1 · 공식 진행 중 데이터</p><h1>R1 라이브 서머리</h1>"
        f"<p class='note'>마지막 성공 업데이트(UTC): {collected_at} · {live_cadence_note}</p>"
        f"<div class='r1-live-summary__grid'>"
        f"<div><span class='label'>현재 선두</span><strong>{leader_display}</strong></div>"
        f"{cutline_stat}"
        f"</div></section>"
    )

    prob_headers = (
        "<th>Cut%</th><th>Top20%</th><th>Top10%</th><th>Top5%</th><th>Win%</th><th>PRE 대비 Win Δ</th>"
        if MODEL_VALIDATED_FOR_PUBLICATION
        else ""
    )
    # The long "비공개 처리됩니다" explanatory notice (MODEL_BLOCKED_NOTE)
    # is deliberately not rendered on the page while blocked -- the
    # absent probability columns already say everything there is to say;
    # a paragraph of prose next to them added length without adding
    # information. MODEL_BLOCKED_NOTE itself stays defined (still used
    # by tests asserting the blocked state carries a real, documented
    # rationale even when it is not shown to the public).
    help_text = (
        "Cut/Top20/Top10/Top5/Win 확률은 실제 R1 스코어(확정)와 각 선수의 PRE 성과 데이터를 결합한 몬테카를로 시뮬레이션 추정치입니다. "
        "R1 스코어가 아직 없는 선수는 해당 확률 칸이 비어 있습니다. 예상 컷은 항상 범위(분포)로만 제공되며 단일 확정값으로 제시하지 않습니다."
        if MODEL_VALIDATED_FOR_PUBLICATION
        else ""
    )
    help_section = f"<div class='help'>{help_text}</div>" if help_text else ""
    table_section = (
        f"<section class='panel' id='r1'><h2>R1 선수별 현황</h2>{nav}"
        f"<div class='table-wrap'><table class='data'><thead><tr>"
        f"<th>순위</th><th>선수</th><th>현재스코어</th><th>완료홀</th><th>오늘스코어</th><th>선두와 타수차</th>"
        f"{prob_headers}<th>상태</th>"
        f"</tr></thead><tbody>{body_rows}</tbody></table></div>"
        f"{help_section}</section>"
    )

    return summary + table_section + movers_section


BANDS = {
    "VERY_HIGH": "최상위",
    "HIGH": "상위",
    "TYPICAL": "중위",
    "LOW": "하위",
    "VERY_LOW": "최하위",
    "INSUFFICIENT_EVIDENCE": "데이터 부족",
}

# PRODUCT RECOVERY V1: the recovered PRE contract includes a full
# tournament outcome probability distribution (CUT/TOP20/TOP10/TOP5/
# WIN) -- but MODEL_VALIDATED_FOR_PUBLICATION (same gate the R1 live
# table below already enforces -- P0 MODEL SAFETY PATCH) means NONE of
# it may render publicly on PRE either, WIN included, no exception,
# until that gate flips (a separate, independently Red-Team-reviewed
# model change -- never decided here). This single ordered list is the
# only place the PRE renderer needs to touch once that happens: every
# entry's own value is already real (win_probability) or an honest
# None (cut/top20/top10/top5 -- see scripts/72's own placeholders),
# never fabricated either way.
_PROBABILITY_COLUMNS = (
    ("cut_probability", "컷 통과확률"),
    ("top20_probability", "TOP20"),
    ("top10_probability", "TOP10"),
    ("top5_probability", "TOP5"),
    ("win_probability", "우승확률"),
)

CSS = """
:root{--ink:#17202a;--muted:#65717d;--line:#dfe5ea;--accent:#0c6b68;--accent-soft:#e2f2f0;--soft:#f4f7f7;--band-1:#0c6b68;--band-2:#3f9188;--band-3:#8a97a3;--band-4:#c98a3a;--band-5:#b1503f}
*{box-sizing:border-box}body{margin:0;color:var(--ink);font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;background:#fff;line-height:1.45}main{max-width:min(96vw,1680px);margin:auto;padding:22px clamp(1rem,2.5vw,2.5rem)}h1{font-size:clamp(26px,2.6vw,38px);margin:8px 0 6px;letter-spacing:-.03em;word-break:keep-all;overflow-wrap:normal}h2{font-size:20px;margin:0 0 6px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;color:var(--accent);text-transform:uppercase}.meta,.note{color:var(--muted);font-size:14px}
/* PRODUCT RECOVERY V1 (real redesign, not content gating): the
   tournament header is now compact -- a slim single row, not a tall
   hero block -- so the player leaderboard is the dominant first-screen
   content, matching HOME's own "player-first" contract. */
.hero{padding:14px 0 12px;display:flex;justify-content:space-between;gap:24px;align-items:center;flex-wrap:wrap}
.hero h1{font-size:clamp(20px,2.2vw,28px);margin:2px 0}
.hero .meta{margin:2px 0 0}
.status{font-size:13px;color:var(--accent);border:1px solid #acd0cc;border-radius:999px;padding:5px 11px}
.panel{border:1px solid var(--line);border-radius:14px;background:#fff;padding:20px}
.table-wrap{overflow-x:auto}.data{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}.data th,.data td{padding:11px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-size:14px}.data th:first-child,.data td:first-child{text-align:left}.data tbody tr:hover{background:var(--soft)}.band{display:inline-block;padding:3px 7px;border-radius:999px;background:#edf4f3;color:#245c58;font-size:12px}.win{font-weight:800;color:var(--accent)}.checkpoint{display:flex;align-items:baseline;gap:10px;border-left:3px solid var(--accent);padding:10px 14px;background:var(--soft);margin-top:12px}.checkpoint .note{margin:0}.metric{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;flex-shrink:0}.help{margin-top:22px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:760px){main{padding:18px 16px}.hero{padding-top:16px}.status{display:inline-block;margin-top:8px}.panel{padding:14px}.data{min-width:700px}.table-wrap:after{content:"↔ 표를 옆으로 밀어 더 많은 열 보기";display:block;color:var(--muted);font-size:12px;padding-top:8px}.data th,.data td{padding:10px 8px}}
/* MOBILE_CONTAINMENT */
.grid > *,.panel{min-width:0}.table-wrap{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden}
/* Public table is centered; numeric columns retain tabular numerals. */
.data th,.data td{text-align:center}.data th:first-child,.data td:first-child{text-align:center}.player-name,.player-sponsor{text-align:center}
.info-control{border:0;background:transparent;color:var(--accent);font:inherit;font-weight:700;cursor:pointer;padding:2px 4px}
/* OWNER UI FIX (NEO 경기력 tooltip overflow): position:fixed instead of
   position:absolute -- the popover no longer needs (or is affected by)
   any positioned ancestor, so it can never widen or overlap the table's
   own column layout (the reported "extends across adjacent columns /
   overlaps SG Total" defect) and is never clipped by .table-wrap's
   overflow-x/overflow-y containment. JS (below) sets left/top from the
   trigger button's real viewport position; max-width is clamped to the
   viewport so it can never overflow off-screen either. */
.info-popover{display:none;position:fixed;z-index:20;max-width:min(260px,calc(100vw - 2rem));padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:0 4px 14px #17202a1a;color:var(--ink);font-size:13px;font-weight:400;line-height:1.5;text-align:left;white-space:normal;overflow-wrap:break-word;word-break:keep-all}
.info-popover.is-open{display:block}
@media(max-width:760px){.info-popover{left:16px!important;right:16px!important;top:112px!important;width:auto;max-width:none}}
/* PRODUCT RECOVERY V1 REDESIGN -- KB PRE leaderboard: replaces the
   rejected two-column grid + "우승 가능성 변화" shell aside entirely.
   The player table is now the sole, full-width panel: a real
   golf-leaderboard visual (sticky header, zebra rows, K-Ranking
   emphasized as a bold figure, NEO 경기력 rendered as a color-coded
   pill by band, 최근 5R SG emphasized) -- not the same bordered
   right-aligned data table with new copy pasted in. */
.leaderboard-panel{padding:14px 16px 8px}
.leaderboard-head{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:.5rem;margin-bottom:10px}
.leaderboard-head h2{margin:0}
.leaderboard-head .note{margin:0}
/* OWNER VISUAL REVIEW FAIL, item 3 (KB PRE DESKTOP): the leaderboard
   was too narrow for the available desktop viewport -- fixed at the
   container level (main{max-width} above, now min(96vw,1680px) instead
   of a fixed 1240px) so the table itself has real room to use, plus a
   tighter vertical rhythm per row (padding 12px -> 8px/10px) that packs
   substantially more of the 120-player field into one screen without
   touching font-size -- density from layout, not from shrinking text. */
.leaderboard-table{width:100%;border-collapse:separate;border-spacing:0;font-variant-numeric:tabular-nums}
.leaderboard-table thead th{position:sticky;top:0;padding:9px 14px;background:var(--soft);color:var(--muted);font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;white-space:normal;border-bottom:2px solid var(--line);text-align:center}
.leaderboard-table tbody td,.leaderboard-table tbody th{padding:8px 14px;border-bottom:1px solid var(--line);white-space:normal;text-align:center;font-size:14px}
.leaderboard-table tbody tr:nth-child(even){background:#fafcfc}
.leaderboard-table tbody tr:hover{background:var(--accent-soft)}
.leaderboard-table tbody th[scope=row]{text-align:left;min-width:11rem}
.leaderboard-table .player-name{font-size:15px;font-weight:800}
.leaderboard-table .player-sponsor{font-size:12px}
.leaderboard-table tbody td:nth-child(2){font-weight:800;color:var(--accent);font-size:15px}
.leaderboard-table tbody td:nth-child(4){font-weight:800;color:var(--ink)}
.band[aria-label="NEO 경기력 최상위"]{background:var(--band-1);color:#fff}
.band[aria-label="NEO 경기력 상위"]{background:var(--band-2);color:#fff}
.band[aria-label="NEO 경기력 중위"]{background:#eef1f3;color:var(--band-3)}
.band[aria-label="NEO 경기력 하위"]{background:#fbeee0;color:var(--band-4)}
.band[aria-label="NEO 경기력 최하위"]{background:#f7e4e1;color:var(--band-5)}
.band[aria-label="NEO 경기력 데이터 부족"]{background:#f1f2f4;color:#9aa5af;border:1px dashed #cbd3da}
.leaderboard-panel .table-wrap:after{content:none}
@media(max-width:760px){
/* OWNER VISUAL REVIEW FAIL, item 4 (KB PRE MOBILE): the first card
   transformation worked (no horizontal scroll) but each card ran ~174px
   tall -- three stacked label/value rows for K-Ranking/NEO 경기력/최근
   5R SG. Redesigned as ONE compact metric row: player identity stays a
   full-width header line at the top for fast scanning, then the three
   metric <td>s become side-by-side stat cells sharing a single row
   (flex-wrap forces the wrap point after the full-width <th>, so no
   markup change was needed -- purely a layout change) instead of three
   separate label:value lines. Brings a card down to roughly 100-110px.
   Still zero horizontal scrolling. */
.leaderboard-table{min-width:0}
.leaderboard-table,.leaderboard-table thead,.leaderboard-table tbody{display:block;width:100%}
.leaderboard-table thead{position:absolute;left:-9999px;top:-9999px}
/* OWNER FOLLOW-UP (mobile NEO 경기력 info accessibility): the info
   trigger lives inside thead th.band-head, which the rule above moves
   off-screen along with the rest of the (redundant on mobile -- each
   card already repeats every label via ::before) header row. Rather
   than restoring the whole header or duplicating the button/popover
   markup, give this ONE <th> (and only this one -- its siblings stay
   off-screen with the rest of thead) its own position:fixed: fixed
   positioning always escapes an ancestor's own position/offset (thead
   being position:absolute;left:-9999px does not drag a
   position:fixed descendant along with it, since none of the
   ancestors here set transform/filter/perspective/will-change to
   create a competing containing block), so it renders as a small
   floating pill at a real on-screen location while thead itself stays
   exactly as off-screen as before. Same DOM node, same button, same
   #neo-info popover, same JS -- nothing is duplicated. */
.leaderboard-table thead th.band-head{position:fixed;top:76px;left:auto;right:16px;z-index:15;display:inline-flex;align-items:center;gap:4px;width:auto;max-width:calc(100vw - 32px);padding:6px 10px;background:#fff;border:1px solid var(--line);border-radius:999px;box-shadow:0 2px 8px #17202a1a;color:var(--ink);font-size:12px;font-weight:800;text-transform:none;letter-spacing:normal;white-space:nowrap}
/* MOBILE HOTFIX 20260911 (KB current-page audit): the previous mobile
   card packed every metric <td> into ONE flex row with flex:1 1 0 --
   with 7-8 metric columns (PRE's K-RANKING/NEO 경기력/최근5R SG/4-5
   probabilities, or a round-result page's 합계/1R/5 probabilities) that
   shrank each cell to ~35-40px, which forced both the long Korean/
   English labels ("KLPGA K-RANKING") and the probability values
   ("88.75%") to hard-wrap one glyph per line inside the cell -- the
   real root cause of the reported "숫자 겹침"/label collapse, not
   something overflow:hidden could ever fix. A CSS Grid with
   auto-fit/minmax now gives every metric cell a real minimum width
   (84px) and WRAPS extra columns onto additional grid rows inside the
   same card instead of over-shrinking them -- still zero horizontal
   scroll, still one player = one card, just as many rows per card as
   the metric count actually needs. */
.leaderboard-table tbody tr{display:grid;grid-template-columns:repeat(auto-fit,minmax(84px,1fr));gap:4px;margin-bottom:8px;border:1px solid var(--line);border-radius:12px;padding:8px 10px 6px;background:#fff}
.leaderboard-table tbody th[scope=row]{grid-column:1/-1;display:block;border-bottom:1px solid var(--line);padding:2px 0 6px;margin-bottom:2px;min-width:0;text-align:left}
.leaderboard-table tbody td{min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;border:0;background:var(--soft);border-radius:8px;padding:4px 4px;text-align:center}
.leaderboard-table tbody td::before{content:attr(data-label);color:var(--muted);font-size:9px;font-weight:700;line-height:1.2;text-align:center}
.leaderboard-table tbody td:nth-child(2){font-size:14px}
}
/* MOBILE HOTFIX 20260911 -- round-result leaderboards (R1/R2/R3/FINAL:
   순위+선수+합계+해당라운드 스코어+5개 확률, in that fixed DOM order)
   opt into this scoped layout via the leaderboard-table--rank-result
   modifier class (added only by the round-result page builder -- PRE's
   own leaderboard-table markup never carries this class, so PRE keeps
   the generic auto-fit card above untouched). 순위/선수명/합계 read
   first on one visual line (rank+name left, total score right), 해당
   라운드 스코어 sits under 합계, and the 5 probability cells form their
   own full-width 5-column row below -- matching the required public
   leaderboard reading order (순위 -> 선수 -> 핵심 스코어 -> 스폰서 ->
   보조 데이터), with sponsor rendered by player_identity.py directly
   under the player name inside the same <th> (untouched invariant).
   Both compound classes are on the same <table> element, so this rule
   (2 classes) always outranks the generic 1-class rule above -- no
   source-order dependency. */
.leaderboard-table.leaderboard-table--rank-result tbody tr{grid-template-columns:repeat(5,1fr);grid-template-rows:auto auto;align-items:center;column-gap:6px;row-gap:4px}
.leaderboard-table.leaderboard-table--rank-result tbody td:nth-child(1){grid-column:1;grid-row:1/3;background:transparent;font-size:16px;font-weight:800}
.leaderboard-table.leaderboard-table--rank-result tbody th[scope=row]{grid-column:2/5;grid-row:1/3;border-bottom:0;padding:0;margin:0}
.leaderboard-table.leaderboard-table--rank-result tbody td:nth-child(3){grid-column:5;grid-row:1;background:transparent;font-size:16px;font-weight:800;color:var(--ink)}
.leaderboard-table.leaderboard-table--rank-result tbody td:nth-child(4){grid-column:5;grid-row:2;background:transparent;font-size:12px;color:var(--muted)}
.leaderboard-table.leaderboard-table--rank-result tbody td:nth-child(n+5){grid-row:3;background:var(--soft)}

/* R1 ACTIVE MODE: live summary + movers, scoped to this OK Open page's own CSS -- never touches the shared neo-site.css. */
.r1-live-summary__grid{display:flex;flex-wrap:wrap;gap:20px;margin-top:14px}.r1-live-summary__grid .label{display:block;color:var(--muted);font-size:12px}.r1-live-summary__grid strong{font-size:16px}
.mover-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.mover-grid h3{font-size:13px;color:var(--muted);margin:0 0 6px}
.mover-list{list-style:none;margin:0;padding:0}.mover-list li{display:flex;justify-content:space-between;gap:10px;padding:4px 0;border-bottom:1px solid var(--line);font-size:13px}.mover-list .delta{font-variant-numeric:tabular-nums;font-weight:700;color:var(--accent)}
"""

def pct(value):
    # DECIMAL DISPLAY CONTRACT (mobile hotfix 20260911): every rendered
    # percentage is formatted to exactly 1 decimal place at this render
    # boundary only -- the underlying prediction JSON keeps its full
    # stored precision untouched.
    return "—" if value is None else f"{float(value)*100:.1f}%"
def value(value):
    return "—" if value is None else html.escape(str(value))

def build(game_code: str | None = None) -> Path:
    global MODEL_VALIDATED_FOR_PUBLICATION
    _bind_context(load_tournament_context(game_code))
    MODEL_VALIDATED_FOR_PUBLICATION = _pre_probability_publication_approved(_CONTEXT)
    historical_ok_mode = _CONTEXT.url_base == OK_BASE
    display_name = _CONTEXT.tournament_name
    date_range = _CONTEXT.display_date_range
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    # Bind provenance to the bytes consumed in this run. The master may be a
    # freshly generated, intentionally uncommitted artifact.
    source_bytes = MASTER.read_bytes()
    master_sha = hashlib.sha256(source_bytes).hexdigest().upper()
    records = list(master["records"])
    # Expected field size (Phase 5 item 2): the tournament's own frozen
    # entry count, never a hardcoded literal -- a different tournament
    # has a different official field size.
    entry = json.loads(_CONTEXT.artifact_path("entry_snapshot").read_text(encoding="utf-8"))
    expected_field_size = int(entry["player_count"])
    if len(records) != expected_field_size:
        raise ValueError(f"canonical master must contain {expected_field_size} records (per entry_snapshot), got {len(records)}")
    # Neutral, reproducible display order: official K-RANKING, then canonical ID.
    records.sort(key=lambda r: (r.get("official_klpga_rank") is None, r.get("official_klpga_rank") or 10**9, str(r["player_id"])))
    # Single canonical player_id -> official sponsor/affiliation lookup,
    # shared by every stage table below (PRE uses it directly off each
    # record; R1's snapshot carries no sponsor field of its own, so it
    # joins through this same dict by player_id).
    # PUBLIC UI Phase 8 correction (FAIL 2): verified_sponsor() gates on
    # identity_validation == "PASS" -- today's master is 120/120 PASS,
    # but the gate must be explicit so a future refresh can never leak
    # a sponsor for a record whose identity was never confirmed.
    #
    # OWNER DECISION (sponsor population is not optional): when THIS
    # tournament's own collection never actually attempted enrichment
    # for a player (verified_sponsor(r) is None AND the record's own
    # failure_reason says enrichment was never requested), fall back to
    # an already-verified sponsor cached from another tournament's own
    # independent, PASS-gated, official-source-backed collection for
    # the SAME player_id -- see player_identity.py's six-point gate.
    # Never overwrites a genuine "checked, none" result on this record.
    _sponsor_cache = cross_tournament_verified_sponsor_cache(
        exclude_paths={_CONTEXT.artifact_path("current_player_master")}
    )
    sponsor_by_id = {str(r.get("player_id")): sponsor_with_cross_tournament_fallback(r, _sponsor_cache) for r in records}
    # PRODUCT RECOVERY V1: real K-Ranking week reference for the compact
    # PRE summary line -- read from the same official ranking artifact
    # already used to join official_klpga_rank per record, never a
    # separately guessed value. Omitted (not invented) if unavailable.
    ranking_week = None
    ranking_path = _CONTEXT.artifact_path("official_klpga_ranking")
    if ranking_path.is_file():
        try:
            ranking_week = json.loads(ranking_path.read_text(encoding="utf-8")).get("ranking_date")
        except (OSError, json.JSONDecodeError):
            ranking_week = None
    pre_summary = f"참가 {len(records)} · K-Ranking {ranking_week} · PRE" if ranking_week else f"참가 {len(records)} · PRE"
    prob_header_cells = "".join(f"<th>{label}</th>" for _, label in _PROBABILITY_COLUMNS) if MODEL_VALIDATED_FOR_PUBLICATION else ""
    rows = []
    for r in records:
        name = r.get("current_official_player_name")
        sponsor = sponsor_by_id.get(str(r.get("player_id")))
        enum = r.get("neo_performance_band")
        band = BANDS.get(enum, "데이터 부족")
        accessible = {"VERY_HIGH":"최상위", "HIGH":"상위", "TYPICAL":"중위", "LOW":"하위", "VERY_LOW":"최하위", "INSUFFICIENT_EVIDENCE":"데이터 부족"}.get(enum, "데이터 부족")
        # PRODUCT RECOVERY V1: the tournament outcome probability
        # distribution (CUT/TOP20/TOP10/TOP5/WIN) is only ever rendered
        # while MODEL_VALIDATED_FOR_PUBLICATION is True -- WIN has
        # no exception, even though it is the one member of the set
        # with a real computed value today. See _PROBABILITY_COLUMNS.
        prob_cells = "".join(f"<td class='win' data-label='{esc_label}'>{pct(r.get(key))}</td>" for key, esc_label in _PROBABILITY_COLUMNS) if MODEL_VALIDATED_FOR_PUBLICATION else ""
        rows.append(
            f"<tr><th scope='row'>{_player_identity_cell(name, sponsor)}</th>"
            f"<td data-label='KLPGA K-RANKING'>{value(r.get('official_klpga_rank'))}</td>"
            f"<td data-label='NEO 경기력'><span class='band' role='img' aria-label='NEO 경기력 {html.escape(accessible)}'>{html.escape(band)}</span></td>"
            f"<td data-label='최근 5R SG'>{value(r.get('sg_total_rank'))}</td>{prob_cells}</tr>"
        )
    # base_url=None: OK Open has no distinct "overview" route the way KG
    # does (its PRE page IS the tournament's landing page) -- linking the
    # breadcrumb's tournament-name crumb to a route that doesn't exist
    # would 404, so it renders as plain text instead (see breadcrumb_html).
    breadcrumb = breadcrumb_html(display_name, None, "PRE")
    stage_nav = stage_nav_html(_context_stage_items("pre", historical_ok_mode=historical_ok_mode))
    # PRODUCT RECOVERY V1 REDESIGN: the compact single-row hero
    # (.hero, restyled -- see CSS above) replaces the tall two-line
    # block, and the rejected two-column .grid + "우승 가능성 변화"
    # .aside.evolution shell is gone outright -- the player leaderboard
    # is now the page's one, full-width panel. The withheld-model state
    # is already fully communicated by the absent probability columns,
    # exactly as R1's help text below already does for the live table.
    html_doc = f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NEO GOLF DATA · {OK_DISPLAY_NAME}</title><link rel=\"stylesheet\" href=\"/assets/neo-site.css\"><link rel=\"stylesheet\" href=\"assets/neo.css\"></head><body><header data-neo-global-navigation></header><main>{breadcrumb}<section class=\"hero\" id=\"tournament\"><div><p class=\"eyebrow\">다음 대회 · PRE</p><h1>{OK_DISPLAY_NAME}</h1><p class=\"meta\">{OK_DATE_RANGE} · {_CONTEXT.venue} · {_CONTEXT.holes}홀 {_CONTEXT.format}</p></div><strong class=\"status\">예측 확정 전</strong></section>{stage_nav}<section class=\"panel leaderboard-panel\" id=\"pre\"><div class=\"leaderboard-head\"><h2>PRE 참가 선수 <small>{len(records)}명</small></h2><p class=\"note\">{pre_summary}</p></div><div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr><th>선수</th><th>KLPGA K-RANKING</th><th>NEO 경기력 구간</th><th>최근 5R SG</th>{prob_header_cells}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section></main></body></html>"""
    old_meta = f"{OK_DATE_RANGE} · {_CONTEXT.venue} · {_CONTEXT.holes}홀 {_CONTEXT.format}"
    meta_bits = [date_range]
    if _CONTEXT.venue:
        meta_bits.append(str(_CONTEXT.venue))
    if _CONTEXT.holes:
        meta_bits.append(f"{_CONTEXT.holes}홀")
    if _CONTEXT.format:
        meta_bits.append(str(_CONTEXT.format))
    html_doc = html_doc.replace(OK_DISPLAY_NAME, display_name).replace(old_meta, " · ".join(meta_bits))
    html_doc = html_doc.replace("다음 대회 · PRE", "PRE 분석").replace("예측 확정 전", "PRE")
    html_doc = html_doc.replace("NEO 경기력 구간", "NEO 경기력 ⓘ")
    # Generic route (Phase 5 item 2): _CONTEXT.url_base, never a
    # hardcoded literal tournament path segment.
    _relative_base = _CONTEXT.url_base.lstrip("/")
    html_doc = html_doc.replace(f'href="{_relative_base}', f'href="{_CONTEXT.url_base}')
    html_doc = html_doc.replace('<a href="#pre">예측 기록</a>', f'<a href="{_CONTEXT.url_base}pre/">예측 기록</a>')
    html_doc = html_doc.replace("<th>NEO 경기력 ⓘ</th>", "<th class='band-head'>NEO 경기력 <button type='button' class='info-control' aria-label='NEO 경기력 설명' aria-expanded='false' aria-controls='neo-info'>ⓘ</button><span id='neo-info' class='info-popover' role='tooltip' tabindex='-1'>최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다.</span></th>")
    html_doc = html_doc.replace("지금의 경기력", "최근 경기력")
    # OWNER UI FIX (NEO 경기력 tooltip overflow): .info-popover is
    # position:fixed (see CSS above), so it needs its viewport
    # left/top computed from the trigger button's real position rather
    # than relying on CSS static-position guesswork -- that guesswork
    # was the root cause of the popover extending across neighboring
    # columns / overlapping SG Total. Closes on scroll/resize (its
    # fixed coordinates would otherwise drift away from the button)
    # in addition to the pre-existing ESC/outside-click close.
    html_doc = html_doc.replace("</body></html>", "<script>(function(){const b=document.querySelector('.info-control'),p=document.getElementById('neo-info');if(!b||!p)return;function close(){p.classList.remove('is-open');b.setAttribute('aria-expanded','false')}function place(){if(window.innerWidth<=760)return;const r=b.getBoundingClientRect();let left=Math.min(r.left,window.innerWidth-p.offsetWidth-16);left=Math.max(16,left);p.style.left=left+'px';p.style.top=(r.bottom+6)+'px'}b.addEventListener('click',function(){const open=p.classList.toggle('is-open');b.setAttribute('aria-expanded',String(open));if(open){place();p.focus()}});document.addEventListener('keydown',function(e){if(e.key==='Escape'&&p.classList.contains('is-open'))close()});document.addEventListener('click',function(e){if(!b.contains(e.target)&&!p.contains(e.target))close()});window.addEventListener('scroll',close,true);window.addEventListener('resize',close)})();</script></body></html>")
    # OUT is one shared candidate directory that every tournament's
    # build() call writes into (script 86/HOME reads OK Open's own
    # already-published route subtree straight out of it as a
    # prerequisite -- see that script's ok_source/ok_route). A full
    # `shutil.rmtree(OUT)` here would destroy every OTHER tournament's
    # already-built route the moment this generalized build() runs for
    # a different game_code, which is a real cross-tournament data-loss
    # bug now that build() is no longer OK-Open-only. Only this call's
    # OWN top-level landing content and its OWN route subtree are
    # rebuilt; any other tournament's `tournaments/<year>/<slug>/`
    # subtree already present under OUT is left untouched.
    route_root = OUT / Path(_CONTEXT.url_base.strip("/"))
    if OUT.exists():
        for name in ("assets", "index.html", "pre", "about", "data"):
            target = OUT / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        if route_root.exists():
            shutil.rmtree(route_root)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "assets" / "neo.css").write_text(CSS, encoding="utf-8")
    html_doc = inject_global_navigation(html_doc, active_section="tournaments")
    (OUT / "index.html").write_text(html_doc, encoding="utf-8")
    (OUT / "pre").mkdir()
    (OUT / "pre" / "index.html").write_text(html_doc.replace('href="assets/neo.css"','href="../assets/neo.css"'), encoding="utf-8")
    route = route_root / "pre"
    route.mkdir(parents=True)
    route_html = html_doc.replace('href="assets/neo.css"', 'href="../../../../assets/neo.css"')
    (route / "index.html").write_text(route_html, encoding="utf-8")
    stage_keys = ("r1", "r2", "final") if historical_ok_mode else ()
    for stage in stage_keys:
        stage_dir = route_root / stage
        stage_dir.mkdir(parents=True)
        crumb = breadcrumb_html(display_name, None, stage.upper())
        nav = stage_nav_html(_context_stage_items(stage, historical_ok_mode=historical_ok_mode))
        # R1 ACTIVE MODE: once scripts/96_ok_open_r1_active_cycle.py has
        # collected and safety-gated a real official R1 snapshot, this
        # page shows it -- a plain leaderboard table (rank/player/thru/
        # to-par/status), never a probability or prediction, since no
        # R1 win-probability model has been built or validated in this
        # codebase. Absent the snapshot (every stage before that, and
        # r2/final until their own live pipelines exist), the honest
        # "no official data yet" placeholder is unchanged.
        body = (_r1_live_leaderboard_section(nav, sponsor_by_id) if stage == "r1" else _r2_live_leaderboard_section(nav, sponsor_by_id) if stage == "r2" else None)
        if body is None:
            body = (f'<section class="panel"><p class="eyebrow">{stage.upper()} · 아직 시작 전</p>'
                     f'<h1>공식 {stage.upper()} 데이터가 아직 없습니다.</h1><p class="note">공식 단계 산출물이 생성되면 이 화면에서 확인할 수 있습니다. 현재는 예측값이나 결과를 만들지 않습니다.</p>{nav}</section>')
        stage_doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                     f'<title>NEO GOLF DATA · {stage.upper()}</title>'
                     f'<link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../assets/neo.css"></head>'
                     f'<body><header data-neo-global-navigation></header><main>{crumb}{body}</main></body></html>')
        (stage_dir / "index.html").write_text(inject_global_navigation(stage_doc, active_section="tournaments"), encoding="utf-8")
    about = """<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>NEO GOLF DATA · NEO 소개</title><link rel=\"stylesheet\" href=\"../assets/neo.css\"></head><body><header data-neo-global-navigation></header><main><section class=\"panel about\" id=\"about\"><p class=\"eyebrow\">NEO 소개</p><h1>결과만으로는 보이지 않는 경기력을 데이터에서 봅니다.</h1><p>NEO GOLF DATA는 KLPGA 공식 경기 기록을 바탕으로 선수들의 경기 데이터를 동일한 기준으로 측정하고 비교합니다.</p><p>우승, TOP10, 상금, K-RANKING은 선수가 쌓아온 중요한 결과입니다. NEO는 여기에 또 하나의 관점을 더합니다.</p><p>최근 공식 경기 데이터를 비교해 출전 선수들 사이에서 관측된 경기력의 상대적 위치를 보여줍니다.</p><p>이것은 선수의 가치나 미래 성적에 대한 등급이 아닙니다. 골프의 결과에는 큰 변동성이 있으며 높은 경기력 위치가 우승이나 TOP10을 보장하지 않습니다.</p><p>NEO는 분석 시점에 사용할 수 있었던 데이터를 보존하고, 실제 결과와 비교하며 분석 방법을 계속 검증합니다.</p></section></main></body></html>"""
    (OUT / "about").mkdir()
    (OUT / "about" / "index.html").write_text(inject_global_navigation(about), encoding="utf-8")
    manifest = {"tournament": display_name, "game_code": _CONTEXT.game_code, "stage": "PRE", "entry_count": len(records), "public_columns": ["선수", "KLPGA K-RANKING", "NEO 경기력 ⓘ", "최근 5R SG", *([label for _, label in _PROBABILITY_COLUMNS] if MODEL_VALIDATED_FOR_PUBLICATION else [])], "probability_distribution_publication_status": "APPROVED" if MODEL_VALIDATED_FOR_PUBLICATION else "BLOCKED"}
    (OUT / "data").mkdir()
    (OUT / "data" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_evidence = {
        "schema_version": "neo_tournament_pre_website_build_evidence_v1",
        "game_code": _CONTEXT.game_code,
        "source_master": MASTER.name,
        "source_master_sha256": master_sha.lower(),
        "entry_count": len(records),
        "route": f"{_CONTEXT.url_base}pre/",
    }
    _CONTEXT.artifact_path("pre_website_build_evidence").write_text(
        json.dumps(build_evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    for generated in OUT.rglob("*"):
        if generated.is_file() and generated.suffix.lower() in {".html", ".css", ".js", ".json"}:
            generated.write_text(generated.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    return OUT

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-code", default=None)
    args = parser.parse_args()
    print(build(args.game_code))

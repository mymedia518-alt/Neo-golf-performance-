"""Shared round-page (R1/R2/R3/FR) renderer for the HITE JINRO
Championship (game_code 2026100005) -- imported only by this
tournament's own scripts/196-199_build_hitejinro_r*.py wrappers, never
by another tournament's builder (this repo's own established
self-contained-per-tournament convention is about never sharing a
builder ACROSS tournaments; sharing logic across one tournament's own
four near-identical round stages is exactly what
klpga.website_v2.player_link/home_ownership_guard/round_score_format
already do site-wide).

Reads real leaderboard rows from normalized/2026100005/LEADERBOARD.json
(NEO Sync stage="results" output -- see klpga.neo_reader.sync). Renders
real rank/player identity/round scores, plus the SAME real NEO 경기력
band and M4 probabilities (컷 통과율/TOP20/TOP10/TOP5/우승확률) PRE
already shows for the identical player -- both now read through
klpga.neo_win.hitejinro_player_metrics, the one shared source for
both (2026-10-01 fix: this module used to hardcode 데이터 부족 for
every row here unconditionally, even once the warehouse and M4 model
were both real and PRE was already displaying them for the same 107
players -- there was never a reason a round page should know less
than PRE about a player who has already played). A player absent from
either source (current_form incomplete, or M4 marks them
DATA_INSUFFICIENT/missing) still renders 데이터 부족 for that one
column, per-player, never a whole-field fallback.

FAILS CLOSED: raises FileNotFoundError with a precise message if
LEADERBOARD.json does not exist yet (true right now -- no round has
been played; NEO Sync's stage="results" collection itself raises for
exactly this reason, "an expected state pre-tournament", per that
module's own docstring) -- never renders an empty or fabricated table.
"""
from __future__ import annotations

import json
from html import escape as _esc
from pathlib import Path

from klpga.neo_win.hitejinro_player_metrics import (
    load_current_form_by_id,
    load_m4_by_id,
    neo_band_by_id,
    pct,
)
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache
from klpga.website_v2.player_link import linked_player_name_cell
from klpga.website_v2.previous_tournament_link import previous_tournament_meta_html
from klpga.website_v2.round_score_format import format_to_par

GAME_CODE = "2026100005"
_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_FLAG_ASSETS = {p.stem for p in (_REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

STAGE_LABELS = {1: ("r1", "R1"), 2: ("r2", "R2"), 3: ("r3", "R3"), 4: ("fr", "FR")}

# The real status enum hitejinro_round_pipeline.parse_leaderboard() writes
# (2026-10-02 status-model mission) -- every display decision below reads
# a record's own "status" value against these, never the legacy withdrawn/
# disqualified/missed_cut booleans directly (those stay on the record
# purely for other, external consumers' backward compatibility).
STATUS_R1_CUT = "R1_CUT"
STATUS_R2_CUT = "R2_CUT"
STATUS_WD = "WD"
STATUS_DQ = "DQ"
STATUS_DNS = "DNS"
_CUT_STATUSES = {STATUS_R1_CUT, STATUS_R2_CUT}

# 2026-10-02 "R2 Renderer 재설계" mission (status enum unchanged --
# operator's own words: "문제는 status enum이 아니다. 문제는
# Renderer다"): R2_CUT and R1_CUT are NOT the same UI.
#
# R2_CUT real players DID complete R2 -- klpga.co.kr's own real
# convention for a standard 36-hole-style cut (confirmed against
# Hana's already-published R2 page) keeps their real rank/total and
# just adds a small "CUT" badge next to the name, same row position
# their real score earns them. They merge straight into the one
# ranked list, on every round page -- never their own section.
#
# R1_CUT (and WD/DQ) never played the round that would have produced
# a real rank at all, so there is no "real position" to keep them in
# -- they get pulled into their own, separate, rank-less section
# below the ranked table instead. That section is built ONLY on the
# R2 page (operator: "R3·FR 페이지에서는 CUT 섹션을 생성하지 않는다")
# -- on R3/FR, these same players (if `played` still includes them at
# all) fall back into the one flat list with their existing
# status-replaces-rank/total cell, just with no divider around them.
_INLINE_RANKED_STATUSES = {STATUS_R2_CUT}
# DNS (did not start) never has a real rank either, same as R1_CUT/
# WD/DQ -- 2026-10-02 "공식 DOM 그대로 파싱" mission added it as its
# own real status (hitejinro_round_pipeline._status_state), so it
# needs the same sectioned treatment here.
#
# 2026-10-03 mission: R2_CUT now ALSO gets pulled into its own R2-page
# section (divider text "CUT", same as R1_CUT's own section since the
# same-day "섹션 제목 단순화" mission), per operator instruction -- the
# R2 page is
# "R2 종료 시점의 최종 상태를 보여주는 페이지" and must show every real
# outcome decided by then, R2_CUT included (derived from a real,
# confirmed R3 field list -- hitejinro_round_pipeline.
# derive_r2_cut_from_confirmed_r3_field -- never Set Difference against
# R3 RESULTS). This only changes which GROUP a R2_CUT row is pulled
# into on the R2 page; _INLINE_RANKED_STATUSES below (unchanged) still
# keeps its real rank/total + badge inside that section, and R3/FR
# still never section it (same "CUT 섹션을 생성하지 않는다" rule,
# untouched -- use_sections is still round_number==2 only).
_SECTIONED_STATUSES = (STATUS_R1_CUT, STATUS_R2_CUT, STATUS_WD, STATUS_DQ, STATUS_DNS)


def _status_family(status: str | None) -> str | None:
    """R1_CUT and R2_CUT both read as the generic "CUT" display family --
    status_round (read separately by _status_display_label) is what
    actually distinguishes which round a cut applies to, not this
    function. Returns None for an active player (status is None)."""
    if status in _CUT_STATUSES:
        return "CUT"
    if status in (STATUS_WD, STATUS_DQ, STATUS_DNS):
        return status
    return None


def _load_nationality_by_id(content_root: Path) -> dict[str, str]:
    """{player_id: nationality} from the real official entry/K-ranking
    join (same source scripts/190's PRE page already uses for the
    identical flag feature) -- empty dict (no flags rendered) if the
    file doesn't exist yet, never a guessed nationality."""
    path = content_root / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
    if not path.is_file():
        return {}
    records = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    return {r["player_code"]: r["nationality"] for r in records if r.get("nationality")}


ROUND_COL_LABELS = {1: "R1", 2: "R2", 3: "R3", 4: "FR"}


def _advancement_summary(records: list[dict]) -> dict | None:
    """Real cut line + counts, computed fresh from each record's own
    real status enum (R1_CUT/R2_CUT/WD/DQ/None, written by
    hitejinro_round_pipeline.parse_leaderboard from real per-player
    WD/DQ/CUT text -- never hardcoded here or anywhere upstream).
    Returns None if no cut has happened yet in this tournament (no
    R1_CUT/R2_CUT record exists) -- e.g. still true for PRE/R1 pages,
    which render no CUT LINE banner at all rather than a zero/empty one.

    cut_line_score is the worst (highest) real r1_score among players
    who were NOT cut after R1 (status != R1_CUT) -- i.e. the real R1
    threshold this tournament's own cut actually landed on, re-derived
    from the field every time this is called, never a remembered
    constant. 2026-10-03 fix: this used to read "status is None"
    specifically, which silently meant "survived R1" ONLY until the
    same day R2_CUT started being derived too -- once a real R2_CUT
    population exists, "status is None" means "survived R1 AND R2",
    a narrower set whose own max r1_score is no longer the real R1
    cutline (it would silently drop to whatever R1 score the worst
    REMAINING active player has, understating the real R1 threshold).
    R2_CUT players still carry a real r1_score from before they were
    ever cut, so they belong in this R1-only calculation same as an
    active player does."""
    cut = [r for r in records if r.get("status") in _CUT_STATUSES]
    if not cut:
        return None
    withdrawn = [r for r in records if r.get("status") == STATUS_WD]
    disqualified = [r for r in records if r.get("status") == STATUS_DQ]
    dns = [r for r in records if r.get("status") == STATUS_DNS]
    advanced = [r for r in records if r.get("status") is None]
    survived_r1 = [r for r in records if r.get("status") != STATUS_R1_CUT]
    advancing_r1_scores = [r["r1_score"] for r in survived_r1 if r.get("r1_score") is not None]
    return {
        "cut_line_score": max(advancing_r1_scores) if advancing_r1_scores else None,
        "advanced_count": len(advanced),
        "cut_count": len(cut),
        "withdrawn_count": len(withdrawn),
        "disqualified_count": len(disqualified),
        "dns_count": len(dns),
    }


# 2026-10-02 "CUT UI 재설계" mission: "R1 CUT"/"R2 CUT" read as two
# nearly-identical codes a user has to decode -- and worse, the label
# text named the round the player LAST COMPLETED (status_round), while
# it physically sits in the NEXT column (_first_missed_round), so e.g.
# 조하리's "R1 CUT" literally appeared inside the R2 column -- a second,
# independent source of confusion on top of the R1-vs-R2 ambiguity
# itself. Replaced with plain-language outcomes, each written to make
# sense specifically in the column it occupies (R1_CUT always lands in
# the R2 column; R2_CUT always lands in the R3 column -- see
# _first_missed_round): "2R 미출전" read inside the R2 column states
# the real fact about THAT column directly (this player did not play
# round 2); "3R 탈락" read inside the R3 column does the same for a
# player cut after round 2. No round-number mismatch left to parse.
_CUT_COLUMN_LABEL = {
    STATUS_R1_CUT: "2R 미출전",
    STATUS_R2_CUT: "3R 탈락",
}


def _status_display_label(status: str, record: dict) -> str:
    """Display text for the one round column _first_missed_round
    identifies. CUT states get the plain-language _CUT_COLUMN_LABEL
    text (self-explanatory in the column they sit in, never just
    restating a round number). WD/DQ keep the existing "R{n} WD"/
    "R{n} DQ" qualifier -- real evidence (2026-10-02 R2 운영 수정
    mission) showed those two are not ambiguous the way CUT is, so
    this mission's redesign is scoped to CUT only."""
    raw_status = record.get("status")
    if raw_status in _CUT_COLUMN_LABEL:
        return _CUT_COLUMN_LABEL[raw_status]
    status_round = record.get("status_round")
    return f"R{status_round} {status}" if status_round is not None else status


def _first_missed_round(record: dict) -> int:
    """The first round column (1-4) this player has no real score for
    -- where the qualified status label belongs, once and only once
    (a bare status previously repeated in every later round column
    too, e.g. 마다솜 showing "WD" in both her R1 and R2 columns).
    status_round IS the last round this player really completed
    (parse_leaderboard's own real-score-derived field, 0 if none) --
    the next column is where they first couldn't play."""
    return (record.get("status_round") or 0) + 1


def load_leaderboard(content_root: Path) -> dict:
    path = content_root / f"{GAME_CODE}_LEADERBOARD.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"no {path} yet -- run NEO Sync with --stage results after the relevant round has real "
            "official data (see klpga.neo_reader.sync's own 'stage=\"results\"... never attempted "
            "implicitly' rule). This page cannot be built before that."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _render_row_html(
    r: dict, *, round_number: int, in_progress: dict[str, dict] | None,
    rank_counts: dict[int, int], band_by_id: dict, m4_by_id: dict,
    nationality_by_id: dict[str, str], sponsor_cache: dict[str, str],
    show_hole_progress: bool,
) -> str:
    """One player's <tr> -- extracted unchanged from render_round_page's
    own former single flat loop (2026-10-02 "Renderer가 라운드별 CUT
    그룹을 생성" mission) so it can be called once per group (NORMAL,
    each real CUT status, WD/DQ) instead of once per row in one mixed
    list. Every per-row rule below (rank/total cell fallback, status
    label placement, probability-cell suppression) is unchanged."""
    pid = str(r["player_id"])
    raw_status = r.get("status")
    status = _status_family(raw_status)
    # 2026-10-02 "R2 Renderer 재설계" mission: R2_CUT keeps its REAL
    # rank/total -- it DID complete the round that earns one, same as
    # 하나금융's own R2 page for a standard cut (confirmed against its
    # real published page). rank_total_status is the value that
    # REPLACES rank/total below; None here means "never replace, this
    # player has a real rank" -- exactly a normal (status=None)
    # player's own behavior, reused as-is for R2_CUT.
    rank_total_status = None if raw_status in _INLINE_RANKED_STATUSES else status
    finish_position_numeric = r.get("finish_position_numeric")
    if r.get("finish_position") is None:
        # klpga.co.kr's own real convention (confirmed against R2's
        # raw capture): a WD/DQ/R1_CUT player's rank cell shows that
        # literal status, never a bare "-" -- only a player with no
        # status at all (or a real rank, like R2_CUT) falls back to "-".
        rank_cell = rank_total_status or "-"
    elif rank_counts.get(finish_position_numeric, 0) > 1:
        # 2+ players share this rank -- "T{rank}" (tied), matching
        # klpga.co.kr's own real convention (confirmed against
        # Hana's already-published PRE/R1/R2 pages, which all use
        # this same "T" prefix, never a bare number for a shared rank).
        rank_cell = _esc(f"T{r['finish_position']}")
    else:
        rank_cell = _esc(str(r["finish_position"]))
    total_cell = rank_total_status or (format_to_par(r["score_to_par"]) if r.get("score_to_par") is not None else "-")
    # Always render all 4 real rounds (R1/R2/R3/FR), never just the
    # rounds played so far -- a round this tournament hasn't reached
    # yet (k > round_number) shows "-" for every player regardless
    # of status, and automatically starts showing real scores the
    # next time this same function builds that later round's page
    # (no special-casing per round needed). klpga.co.kr's own real
    # convention (confirmed against R2's raw capture for WD player
    # 고지우/CUT player 이소영, both of whom keep their real completed
    # R1 score shown even on their WD/CUT row): a real completed
    # score always wins over the status text; status only fills a
    # cell for a round that has happened (k <= round_number) but
    # genuinely has no real score of its own for this player.
    round_cells = []
    for k in (1, 2, 3, 4):
        real_score = r.get(f"r{k}_score")
        # 2026-10-03 fix: a player already carrying a REAL persisted
        # status from BEFORE round_number even started (e.g. R2_CUT
        # going into the R3 START page) must show that status's own
        # label in its first-missed-round column even when in_progress
        # is given and that column IS round_number -- in_progress's
        # per-player data only covers players who are actually part of
        # THIS round's field; a status-bearing player's correct
        # explanation is their own real status, not in_progress's
        # generic "live is None -> '-'" fallback (confirmed bug: 41
        # real R2_CUT players on the R3 START page were showing a bare
        # "-" in the R3 column instead of "3R 탈락").
        if k <= round_number and status and k == _first_missed_round(r):
            cell = _status_display_label(status, r)
        elif in_progress is not None and k == round_number:
            # round_number has no real score of its own yet -- show
            # ONLY what in_progress's real per-player state carries,
            # never fall back to real_score (that's the PREVIOUS
            # round's own completed score, not this one's).
            live = in_progress.get(pid)
            if live is None:
                cell = "-"
            elif live["excluded"]:
                cell = _esc(live["status_text"] or "제외")
            elif live["score"] is not None:
                cell = str(live["score"])
            elif live["hole"] is not None and show_hole_progress:
                cell = f"{live['hole']}H"
            else:
                cell = "-"
        elif real_score is not None:
            # the raw stroke count for that round (e.g. 68), never a
            # to-par differential -- format_to_par is only for an
            # already-relative-to-par value (score_to_par above).
            cell = str(real_score)
        elif k <= round_number and status:
            # A round this player couldn't play, but NOT their own
            # first-missed-round column (that's handled above) -- e.g.
            # the R4/FR columns for someone cut after R2. Operational
            # fix (2026-10-02): the status label appears ONLY once, in
            # the first column it actually explains, qualified with
            # WHICH round the real cut/WD/DQ applies to
            # (_status_display_label) -- never repeated in every later
            # column as if that later round itself produced the outcome.
            cell = "-"
        else:
            cell = "-"
        round_cells.append(f"<td data-label='{ROUND_COL_LABELS[k]}'>{cell}</td>")
    country_code = nationality_by_id.get(pid)
    flag_cell = (
        f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
        f"style='display:inline;vertical-align:middle;margin-right:4px'>"
        if country_code in _FLAG_ASSETS else ""
    )
    sponsor_text = _esc(sponsor_cache.get(pid, ""))
    name_cell = (
        f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(r['player_name'])}</span>"
        f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    )
    name_cell = linked_player_name_cell(pid, name_cell)
    if raw_status in _INLINE_RANKED_STATUSES:
        # Real rank/total already kept above -- the only remaining
        # signal this player is out is this small inline badge next to
        # their name, exactly 하나금융's own R2 page convention (badge
        # outside the player-name link, never inside it).
        name_cell += "<span class='status-badge'>CUT</span>"

    if round_number == 1 and pid in band_by_id:
        label, score = band_by_id[pid]
        band_cell = (
            f"<span class='band' role='img' aria-label='NEO 경기력 {label}' "
            f"data-neo-score='{score:.2f}'>{label}</span>"
        )
    else:
        band_cell = _NOWRAP

    if status:
        # Hana (2026090002) R2's own real, already-published rendering
        # rule (confirmed against its real page's own markup -- every
        # CUT player's TOP20/TOP10/TOP5/우승 cell is literally
        # <td class='metric-empty'>—</td>, never a stale/meaningless
        # percentage for someone already out of contention): real
        # is_cut/is_wd signal (this row's own status, read above from
        # the real status enum, _status_family(r.get("status")) --
        # never hardcoded) suppresses every probability cell the same
        # way, regardless
        # of whether M4 happens to have a number for this player.
        cut_cell = top20_cell = top10_cell = top5_cell = win_cell = "—"
        metric_class = "win metric-empty"
    elif pid in m4_by_id:
        m4 = m4_by_id[pid]
        cut_cell = pct(m4["cut_probability"])
        top20_cell = pct(m4["top20_probability"])
        top10_cell = pct(m4["top10_probability"])
        top5_cell = pct(m4["top5_probability"])
        win_cell = pct(m4["win_probability"])
        metric_class = "win"
    else:
        cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP
        metric_class = "win"

    band_td = f"<td data-label='NEO 경기력'>{band_cell}</td>" if round_number == 1 else ""
    return (
        f"<tr><td data-label='순위'>{rank_cell}</td>"
        f"<th scope='row' style='white-space:nowrap;text-align:left'>{name_cell}</th>"
        f"<td data-label='합계'>{total_cell}</td>"
        + "".join(round_cells) +
        f"{band_td}"
        f"<td class='{metric_class}' data-label='컷 통과확률'>{cut_cell}</td>"
        f"<td class='{metric_class}' data-label='TOP20'>{top20_cell}</td>"
        f"<td class='{metric_class}' data-label='TOP10'>{top10_cell}</td>"
        f"<td class='{metric_class}' data-label='TOP5'>{top5_cell}</td>"
        f"<td class='{metric_class}' data-label='우승확률'>{win_cell}</td></tr>"
    )


def render_round_page(
    round_number: int, *, tournament_name: str, date_range: str, content_root: Path,
    in_progress: dict[str, dict] | None = None, show_hole_progress: bool = True,
) -> str:
    """in_progress (optional): {player_id: {"excluded", "status_text",
    "score", "hole"}} from klpga.neo_win.hitejinro_round_pipeline.
    parse_in_progress_state() -- an "R2 START"-type render for a round
    that has not yet produced a single real completed score. When
    given, the roster/ranking/total this renders is round_number-1's
    already-completed field (its own real finish_position, "R1 종료
    기준 그대로 사용" -- round_number itself has no real standings of
    its own yet to re-sort by), and round_number's own column shows
    ONLY in_progress's real per-player state: excluded players' real
    status text (WD/CUT/...), a real completed score once a player
    finishes, a real in-progress hole number ("{hole}H") once
    show_hole_progress is True AND that player has genuinely started,
    or "-" for anyone not yet confirmed started -- never a fabricated
    score or a guessed "진행 중"/"대기" label.

    show_hole_progress (operator call, 2026-10-01): the hole-number
    display is correct and ready whenever a capture genuinely shows
    per-player in-course progress, but the operator judged the FIRST
    such capture too close to this round's own start to treat as the
    real signal to switch on -- so this build keeps every still-active
    player's cell at "-" regardless of a real `hole` value, while a
    real completed `score` (rule 6's other, later case) still renders
    immediately, automatically, the moment one appears in any future
    capture -- no code change needed for that. Passing True (the
    default, used by every other round/caller) switches hole-number
    display back on."""
    if round_number not in STAGE_LABELS:
        raise ValueError(f"round_number must be 1-4, got {round_number}")
    stage_key, stage_label = STAGE_LABELS[round_number]

    board = load_leaderboard(content_root)
    records = board["records"]
    if in_progress is not None:
        score_field = f"r{round_number - 1}_score"
    else:
        score_field = f"r{round_number}_score"
    played = [
        r for r in records
        if r.get(score_field) is not None or r.get("status") is not None
    ]
    if not played:
        raise FileNotFoundError(
            f"LEADERBOARD.json exists but no row has a real {score_field} yet -- round {round_number} "
            "has not actually been played/collected. Never renders a round page with zero real scores."
        )
    played.sort(key=lambda r: (r.get("finish_position_numeric") is None, r.get("finish_position_numeric", 10**9)))

    rank_counts: dict[int, int] = {}
    for r in played:
        n = r.get("finish_position_numeric")
        if n is not None:
            rank_counts[n] = rank_counts.get(n, 0) + 1

    if in_progress is not None:
        # Operator rule (2026-10-01): a player already excluded before
        # this round starts (real WD/CUT/... per in_progress) is not
        # part of this round's field -- drop the row entirely instead
        # of listing it with a status cell. Applied only AFTER
        # rank_counts so every remaining player's previous-round rank
        # (incl. a "T" tie shared with an excluded player) is unchanged.
        played = [r for r in played if not (in_progress.get(str(r["player_id"])) or {}).get("excluded")]

    if round_number >= 3:
        # 2026-10-03 explicit operator instruction ("R3/FR에서는 R2 CUT
        # 선수는 경기하지 않는다"): unlike R1_CUT/WD/DQ/DNS (which still
        # fall back into the flat list with their own status-replaces-
        # rank/total cell on R3/FR), R2_CUT players are dropped from
        # these pages entirely -- they are not part of this round's
        # real field at all (confirmed: the real R3 leaderboard capture
        # itself never lists them, not even with CUT text). Applied
        # after rank_counts for the same reason as the in_progress
        # exclusion above.
        played = [r for r in played if r.get("status") != STATUS_R2_CUT]

    nationality_by_id = _load_nationality_by_id(content_root)
    sponsor_cache = cross_tournament_verified_sponsor_cache()

    all_ids = [str(r["player_id"]) for r in played]
    current_form_by_id = load_current_form_by_id(all_ids)
    band_by_id = neo_band_by_id(current_form_by_id)
    m4_by_id = load_m4_by_id()

    total_cols = 3 + 4 + (1 if round_number == 1 else 0) + 5

    # 2026-10-02 "R2 Renderer 재설계" mission, extended 2026-10-03.
    # Real evidence this tournament has: R1_CUT (조하리/이수민/이소영,
    # 3명), WD (고지우/황정미/마다솜, 3명), R2_CUT (derived from a real
    # confirmed R3 field list -- hitejinro_round_pipeline.
    # derive_r2_cut_from_confirmed_r3_field -- 41명). Sectioning (each
    # status's own rank-less-or-real-rank group, pulled out of the main
    # ranked table) applies ONLY on round_number == 2
    # (_SECTIONED_STATUSES: R1_CUT/R2_CUT/WD/DQ/DNS). R2_CUT's own
    # section keeps its real rank/total + inline badge
    # (_INLINE_RANKED_STATUSES, unchanged) since those players DID
    # complete R2; only its GROUPING moved. On R3/FR ("CUT 섹션을
    # 생성하지 않는다"), every one of these statuses falls back into
    # the one flat list instead, with their existing status-replaces-
    # rank/total (or, for R2_CUT, real-rank+badge) cell -- just with no
    # divider/header around them.
    use_sections = round_number == 2
    inline_rows = [
        r for r in played
        if not (use_sections and r.get("status") in _SECTIONED_STATUSES)
    ]
    row_kwargs = dict(
        round_number=round_number, in_progress=in_progress, rank_counts=rank_counts,
        band_by_id=band_by_id, m4_by_id=m4_by_id, nationality_by_id=nationality_by_id,
        sponsor_cache=sponsor_cache, show_hole_progress=show_hole_progress,
    )
    # 2026-10-02 "EVIDENCE INSUFFICIENT" mission: the "R2 컷 통과"
    # group label (added by an earlier mission this same day) asserted
    # a fact with no real evidence behind it -- no KLPGA page anywhere
    # in this tournament's raw evidence displays a "본선 진출자"/cut-
    # pass counter or label for this population (confirmed by exhaustive
    # search). Until real R3 evidence settles what this population
    # actually is, status=None renders as a plain ranked list ONLY --
    # no group name, no header, same as every other real status this
    # tournament has never fabricated a label for.
    rows_html = [_render_row_html(r, **row_kwargs) for r in inline_rows]

    if use_sections:
        # 2026-10-03 "섹션 제목 단순화" mission: both cut sections' user-
        # facing DIVIDER TEXT simplifies to plain "CUT" (dropping "R2
        # 미출전"/"R3 미출전" and the R1 cutline-score suffix) -- the
        # internal status enum (R1_CUT/R2_CUT) is untouched, and each
        # row's own cell text (rank/total "CUT", per-cell "2R 미출전"/
        # "3R 탈락" labels, the inline CUT badge) is untouched too; only
        # these two divider headers' wording changed. Order also
        # flipped per explicit instruction: R2_CUT's section now comes
        # BEFORE R1_CUT's (① 일반 순위 ② CUT/R2_CUT ③ CUT/R1_CUT ④ WD).
        r2_cut_group = [r for r in played if r.get("status") == STATUS_R2_CUT]
        if r2_cut_group:
            header = f"CUT · {len(r2_cut_group)}명"
            rows_html.append(f"<tr class='cut-divider'><td colspan='{total_cols}'>{_esc(header)}</td></tr>")
            rows_html.extend(_render_row_html(r, **row_kwargs) for r in r2_cut_group)

        r1_cut_group = [r for r in played if r.get("status") == STATUS_R1_CUT]
        if r1_cut_group:
            header = f"CUT · {len(r1_cut_group)}명"
            rows_html.append(f"<tr class='cut-divider'><td colspan='{total_cols}'>{_esc(header)}</td></tr>")
            rows_html.extend(_render_row_html(r, **row_kwargs) for r in r1_cut_group)

        for section_status, section_label in ((STATUS_WD, "WD"), (STATUS_DQ, "DQ"), (STATUS_DNS, "DNS")):
            group = [r for r in played if r.get("status") == section_status]
            if not group:
                continue
            header = f"{section_label} · {len(group)}명"
            rows_html.append(f"<tr class='cut-divider'><td colspan='{total_cols}'>{_esc(header)}</td></tr>")
            rows_html.extend(_render_row_html(r, **row_kwargs) for r in group)

    stage_nav_items = []
    for n, (key, label) in [(0, ("pre", "사전 분석 PRE"))] + [(n, STAGE_LABELS[n]) for n in (1, 2, 3, 4)]:
        display_label = "사전 분석 PRE" if key == "pre" else label
        if key == "pre" or n < round_number:
            href = f"/tournaments/2026/{GAME_CODE}/{key}/"
            cur = " aria-current='page'" if key == stage_key else ""
            stage_nav_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='{href}'{cur}>{display_label}</a></li>")
        elif key == stage_key:
            stage_nav_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/{key}/' aria-current='page'>{display_label}</a></li>")
        else:
            stage_nav_items.append(f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>{display_label}</span></li>")

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(tournament_name)} {stage_label}</title>'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css"></head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/{stage_key}/" class="is-active" aria-current="page">대회</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(tournament_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span aria-current="page">{stage_label}</span></nav>'
        f'<section class="hero" id="tournament"><div><p class="eyebrow">{stage_label} 업데이트</p>'
        f'<h1>{_esc(tournament_name)}</h1><p class="meta">{_esc(date_range)}</p>'
        f'{previous_tournament_meta_html()}</div></section>'
    )
    stage_nav = f"<nav class='stage-nav' aria-label='대회 단계' data-stage-nav><ol class='stage-nav__list'>{''.join(stage_nav_items)}</ol></nav>"
    # 2026-10-02 "상단 상태 배너 삭제" mission: every top-of-table banner
    # this renderer ever showed (R2's "R2 종료 · R1 컷 확정 · CUT · WD"/
    # "3R 진출 {n}명", R3+'s "실제 {round} 출전 선수 {n}명") is removed --
    # the real CUT/WD/DQ/DNS facts already render as their own in-table
    # SECTION headers (see use_sections below); a second, separate
    # summary line above the table was redundant with those and the
    # operator asked for the table to start directly under the title on
    # every round page, not just R2's.
    table_section = (
        f"<section class='panel leaderboard-panel' id='{stage_key}'>"
        f"<div class='leaderboard-head'><h2>{stage_label} 결과 <small>{len(played)}명</small></h2></div>"
        "<div class='table-wrap'><table class='data leaderboard-table leaderboard-table--hitejinro'><thead><tr>"
        "<th>순위</th><th>선수</th><th>합계</th>"
        + "".join(f"<th>{ROUND_COL_LABELS[k]}</th>" for k in (1, 2, 3, 4))
        + ("<th>NEO 경기력</th>" if round_number == 1 else "")
        + "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )
    footer = (
        '</main>'
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/{stage_key}/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )
    return header + stage_nav + table_section + footer


def render_r3_neo_verification_html(v: dict) -> str:
    """② NEO 검증 (2026-10-03 mission): real pre-R3 M4 predictions vs
    the real R3 outcome -- hitejinro_round_pipeline.build_r3_neo_
    verification's own real, directly-computed numbers only. Never a
    narrative guess at WHY a prediction missed; only the real score/
    rank facts (operator: "예측 실패 원인" means the real data showing
    the miss, not a fabricated explanation)."""
    cp = v["cut_prediction"]
    wc = v["win_candidate"]

    topn_rows = "".join(
        f"<tr><td>TOP{n}</td><td>{d['hit']}/{d['total']}</td>"
        f"<td>{round(100 * d['hit'] / d['total'], 1)}%</td></tr>"
        for n, d in v["topn_hitrates"].items()
    )

    real_wp = wc["real_leader_pre_r3_win_probability"]
    real_wp_text = f"{real_wp * 100:.2f}%" if real_wp is not None else "데이터 부족"
    win_html = (
        f"<p>실제 R3 종료 선두: <b>{_esc(wc['real_leader']['player_name'])}</b> "
        f"({format_to_par(wc['real_leader']['score_to_par'])}) -- R2 종료 시점 사전 우승확률 {real_wp_text}</p>"
        f"<p>사전 우승확률 1위: <b>{_esc(wc['predicted_leader']['player_name'])}</b> "
        f"({wc['predicted_leader']['pre_r3_win_probability'] * 100:.2f}%) -- "
        f"실제 R3 결과: {_esc(wc['predicted_leader_real_status'] or ('순위 ' + str(wc['predicted_leader_real_rank'])))}</p>"
    )

    def _rank_rows(items: list[dict]) -> str:
        return "".join(
            f"<tr><td>{_esc(c['player_name'])}</td><td>{c['r2_rank']}</td><td>{c['r3_rank']}</td>"
            f"<td>{'+' if c['change'] > 0 else ''}{c['change']}</td></tr>"
            for c in items
        )

    return (
        "<section class='panel' id='neo-verification'>"
        "<h2>NEO 검증 -- 예측을 공개하고 실제 결과로 검증한다</h2>"
        f"<p class='meta'>R2 종료 시점 NEO 사전 예측(M4 모델, {v['population_count']}명 대상) vs 실제 R3 결과 비교</p>"
        "<h3>컷 예측 검증</h3>"
        f"<p>{cp['correct']}/{cp['total']}명 정확 ({cp['accuracy_pct']}%) -- "
        "R2 종료 시점 컷 통과확률 50% 이상을 '통과 예측'으로 판정</p>"
        "<h3>TOP20 / TOP10 / TOP5 적중률</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>구간</th><th>적중</th><th>적중률</th></tr></thead>"
        f"<tbody>{topn_rows}</tbody></table></div>"
        "<h3>우승후보 적중 여부</h3>"
        f"{win_html}"
        "<h3>순위 변동 -- 상승 TOP5</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>선수</th><th>R2 순위</th><th>R3 순위</th><th>변동</th></tr></thead>"
        f"<tbody>{_rank_rows(v['risers'])}</tbody></table></div>"
        "<h3>순위 변동 -- 하락 TOP5</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>선수</th><th>R2 순위</th><th>R3 순위</th><th>변동</th></tr></thead>"
        f"<tbody>{_rank_rows(v['fallers'])}</tbody></table></div>"
        "<h3>예측 실패 원인 (실제 데이터)</h3>"
        f"<p>사전 우승확률 1위 {_esc(wc['predicted_leader']['player_name'])}는 실제 R3 종료 시점 "
        f"{_esc(wc['predicted_leader_real_status'] or ('순위 ' + str(wc['predicted_leader_real_rank'])))}에 그쳤고, "
        f"실제 선두 {_esc(wc['real_leader']['player_name'])}의 사전 우승확률은 {real_wp_text}에 불과했다 -- "
        "두 수치 모두 R2 종료 시점 M4 모델의 실제 출력값이며, 사후 재구성이 아니다.</p>"
        "</section>"
    )


def render_r3_sg_intelligence_html(d: dict) -> str:
    """SG 분석 (Player Intelligence): hitejinro_round_pipeline.build_r3_
    sg_intelligence's real, parsed Strokes Gained rows -- Total/OTT/
    APP/ARG/PUTT per player, this round's own real official SG table,
    nothing estimated."""
    leader = d["sg_leader"]
    rows_html = "".join(
        f"<tr><td>{r['sg_rank']}</td><td>{_esc(r['official_display_name'])}</td>"
        f"<td>{r['r3_rank'] if r['r3_rank'] is not None else '-'}</td>"
        f"<td>{r['total']:+.2f}</td><td>{r['off_the_tee']:+.2f}</td>"
        f"<td>{r['approach']:+.2f}</td><td>{r['around_green']:+.2f}</td>"
        f"<td>{r['putting']:+.2f}</td></tr>"
        for r in d["rows"]
    )
    return (
        "<section class='panel' id='sg-intelligence'>"
        "<h2>SG 분석 (Strokes Gained)</h2>"
        f"<p class='meta'>R3 공식 Strokes Gained, {d['population_count']}명 -- 라운드 자체 SG(단일 라운드 기준)</p>"
        + (f"<p>R3 SG 1위: <b>{_esc(leader['official_display_name'])}</b> (Total {leader['total']:+.2f})</p>" if leader else "")
        + "<div class='table-wrap'><table class='data'><thead><tr>"
        "<th>SG순위</th><th>선수</th><th>R3순위</th><th>Total</th><th>OTT</th><th>APP</th><th>ARG</th><th>PUTT</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table></div>"
        "</section>"
    )


def render_r3_course_analysis_html(d: dict) -> str:
    """코스 분석: hitejinro_round_pipeline.build_r3_course_analysis's
    real per-hole R3 field averages (collect_current_round_evidence.py's
    real scorecards.json, 61명 전원)."""
    def _hole_rows(items: list[dict]) -> str:
        return "".join(
            f"<tr><td>{h['hole']}</td><td>Par {h['par']}</td><td>{h['avg_to_par']:+.2f}</td>"
            f"<td>{h['better_than_par']}/{h['player_count']}</td></tr>"
            for h in items
        )

    return (
        "<section class='panel' id='course-analysis'>"
        "<h2>코스 분석</h2>"
        f"<p class='meta'>R3 전체 {d['field_player_count']}명 실제 홀별 스코어 -- 평균 {d['field_avg_to_par_per_round']:+.2f}타/라운드</p>"
        "<h3>가장 어려운 홀 TOP3</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>홀</th><th>파</th><th>평균 스코어</th><th>버디 이상</th></tr></thead>"
        f"<tbody>{_hole_rows(d['hardest_holes'])}</tbody></table></div>"
        "<h3>가장 쉬운 홀 TOP3</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>홀</th><th>파</th><th>평균 스코어</th><th>버디 이상</th></tr></thead>"
        f"<tbody>{_hole_rows(d['easiest_holes'])}</tbody></table></div>"
        "</section>"
    )


def render_r3_r4_preview_html(d: dict) -> str:
    """R4 Preview: real R3 standings + real round-over-round SG momentum
    only (hitejinro_round_pipeline.build_r3_r4_preview) -- explicitly
    NOT a recomputed win-probability model; the static pre-tournament
    M4 snapshot is never recalculated mid-event, and this section does
    not pretend otherwise."""
    def _lb_rows(items: list[dict]) -> str:
        return "".join(
            f"<tr><td>{r['rank']}</td><td>{_esc(r['player_name'])}</td><td>{format_to_par(r['score_to_par'])}</td></tr>"
            for r in items
        )

    def _momentum_rows(items: list[dict]) -> str:
        return "".join(
            f"<tr><td>{_esc(r['player_name'])}</td><td>{r['r2_total']:+.2f}</td>"
            f"<td>{r['r3_total']:+.2f}</td><td>{r['change_r2_to_r3']:+.2f}</td></tr>"
            for r in items
        )

    return (
        "<section class='panel' id='r4-preview'>"
        "<h2>R4 Preview</h2>"
        "<p class='meta'>※ 사전 모델(M4)은 재계산하지 않음 -- 아래는 R3 종료 시점 real 순위와 "
        "라운드별 real SG 변화만을 보여주는 참고 지표이며, 새로운 우승확률 모델이 아니다.</p>"
        "<h3>R3 종료 순위 TOP5</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>순위</th><th>선수</th><th>스코어</th></tr></thead>"
        f"<tbody>{_lb_rows(d['leaderboard_top5'])}</tbody></table></div>"
        "<h3>SG 상승 모멘텀 TOP5 (R2 → R3)</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>선수</th><th>R2 SG</th><th>R3 SG</th><th>변화</th></tr></thead>"
        f"<tbody>{_momentum_rows(d['sg_momentum_rising'])}</tbody></table></div>"
        "<h3>SG 하락 모멘텀 TOP5 (R2 → R3)</h3>"
        "<div class='table-wrap'><table class='data'><thead><tr><th>선수</th><th>R2 SG</th><th>R3 SG</th><th>변화</th></tr></thead>"
        f"<tbody>{_momentum_rows(d['sg_momentum_falling'])}</tbody></table></div>"
        "</section>"
    )

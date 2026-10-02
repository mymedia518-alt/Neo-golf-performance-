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
_SECTIONED_STATUSES = (STATUS_R1_CUT, STATUS_WD, STATUS_DQ, STATUS_DNS)


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
    whose status is None (not cut/withdrawn/disqualified) -- i.e. the
    real threshold this tournament's own cut actually landed on,
    re-derived from the field every time this is called, never a
    remembered constant."""
    cut = [r for r in records if r.get("status") in _CUT_STATUSES]
    if not cut:
        return None
    withdrawn = [r for r in records if r.get("status") == STATUS_WD]
    disqualified = [r for r in records if r.get("status") == STATUS_DQ]
    dns = [r for r in records if r.get("status") == STATUS_DNS]
    advanced = [r for r in records if r.get("status") is None]
    advancing_r1_scores = [r["r1_score"] for r in advanced if r.get("r1_score") is not None]
    return {
        "cut_line_score": max(advancing_r1_scores) if advancing_r1_scores else None,
        "advanced_count": len(advanced),
        "cut_count": len(cut),
        "withdrawn_count": len(withdrawn),
        "disqualified_count": len(disqualified),
        "dns_count": len(dns),
    }


def _round_participation_count(
    round_number: int, records: list[dict], in_progress: dict[str, dict] | None,
) -> int | None:
    """Real count of players actually in THIS round's own field --
    never advanced_count (that's R2's cut-survivor count, a different
    real quantity that stays frozen at whatever R2 decided; R3/FR each
    need their OWN round's real participation, which can differ, e.g.
    a further real WD between rounds).

    During an in-progress capture ("R3 START"-type render), counted
    straight from in_progress's own real per-player state -- excluded
    players (real WD/DQ/CUT during this round) don't count. Once the
    round has genuinely completed and parse_leaderboard has re-parsed
    real r{round_number}_score values into records, counted from those
    instead. Returns None (never a fabricated/zero placeholder) if
    this round has no real data of either kind yet."""
    if in_progress is not None:
        count = len([v for v in in_progress.values() if not v.get("excluded")])
        return count if count > 0 else None
    score_field = f"r{round_number}_score"
    count = len([r for r in records if r.get(score_field) is not None])
    return count if count > 0 else None


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
        if in_progress is not None and k == round_number:
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
        elif k <= round_number and status and k == _first_missed_round(r):
            # Operational fix (2026-10-02): show the status label
            # ONLY in the first round column this player actually
            # couldn't play, qualified with WHICH round the real
            # cut/WD/DQ applies to (_status_display_label) -- a bare
            # "CUT" repeated in every later round column read, in
            # the R2 column specifically, as if round 2 itself
            # produced that outcome. Real evidence this session:
            # 조하리/이수민/이소영 never played R2 at all; their
            # real cut was decided on R1's score alone.
            cell = _status_display_label(status, r)
        elif k <= round_number and status:
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

    nationality_by_id = _load_nationality_by_id(content_root)
    sponsor_cache = cross_tournament_verified_sponsor_cache()

    all_ids = [str(r["player_id"]) for r in played]
    current_form_by_id = load_current_form_by_id(all_ids)
    band_by_id = neo_band_by_id(current_form_by_id)
    m4_by_id = load_m4_by_id()

    summary = _advancement_summary(records)
    total_cols = 3 + 4 + (1 if round_number == 1 else 0) + 5

    # 2026-10-02 "R2 Renderer 재설계" mission. Real evidence this
    # tournament has today: R1_CUT (조하리/이수민/이소영, real, 3명),
    # WD (고지우/황정미/마다솜, real, 3명), R2_CUT (none yet -- real
    # count is 0, so its section is correctly ABSENT below, never an
    # empty placeholder). Sectioning (its own rank-less group, pulled
    # out of the ranked table) applies ONLY on round_number == 2, and
    # ONLY to the 4 statuses with no real rank of their own
    # (_SECTIONED_STATUSES: R1_CUT/WD/DQ/DNS). R2_CUT never sections --
    # it keeps a real rank (see _render_row_html) and merges straight
    # into the one ranked list on every round page. On R3/FR
    # ("CUT 섹션을 생성하지 않는다"), R1_CUT/WD/DQ/DNS fall back into
    # that same flat list too, with their existing status-replaces-
    # rank/total cell -- just with no divider/header around them.
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
    # 2026-10-02 "Renderer만 수정" mission: status=None was rendered
    # with NO header at all (just the top of the table) while every
    # other status got its own labeled section -- an asymmetry the
    # operator flagged directly ("status=None을 ACTIVE로 렌더링하지
    # 말고... 'R2 컷 통과' 그룹으로 렌더링한다"). Every real status
    # value now gets an explicit, equally-labeled group on the R2 page,
    # 하나금융 R2와 동일한 구조: status=None -> "R2 컷 통과". Count is
    # real active players only (status is None) -- never includes an
    # inline-ranked R2_CUT row that happens to share this same list
    # (none exist today; structurally impossible on R2's own page
    # anyway, since R2_CUT is only ever assigned once a LATER round's
    # evidence is parsed).
    if use_sections:
        active_count = len([r for r in played if r.get("status") is None])
        header = f"R2 컷 통과 · {active_count}명"
        rows_html = [f"<tr class='cut-divider'><td colspan='{total_cols}'>{_esc(header)}</td></tr>"]
    else:
        rows_html = []
    rows_html.extend(_render_row_html(r, **row_kwargs) for r in inline_rows)

    if use_sections:
        r1_cut_group = [r for r in played if r.get("status") == STATUS_R1_CUT]
        if r1_cut_group:
            # The real R1 cut-line score (summary's own real
            # computation, unchanged) is meaningful context for this
            # one section -- no equivalent score exists for WD/DQ.
            # "R2 미출전" (not "R1 미출전"): matches the already-shipped
            # per-cell label text ("2R 미출전") exactly -- states the
            # real fact directly (didn't enter ROUND 2), never
            # ambiguous with "didn't play R1 itself" the way "R1
            # 미출전" could be misread.
            header = "R2 미출전"
            if summary is not None and summary["cut_line_score"] is not None:
                header += f" — {summary['cut_line_score']}타 이하 통과"
            header += f" · {len(r1_cut_group)}명"
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
    # R2's own top banner (2026-10-02 "advanced_count 표시 금지" mission):
    # never shows "컷 통과 {advanced_count}명" or a guessed 3R headcount.
    # Once R3 genuinely has real data of its own (_round_participation_count
    # reading real r3_score values -- never in_progress here, that param
    # is round_number's OWN live state, not a later round's), show ONLY
    # the real "3R 진출 {n}명" fact. Until then, show only what R2's own
    # completion genuinely established: R2 종료 / CUT 확정 / real CUT and
    # WD (and DQ, if any) counts -- no CUT LINE score, no advanced_count,
    # no estimate of who tees off in R3.
    cut_line_html = ""
    if round_number == 2 and summary is not None:
        real_r3_participation = _round_participation_count(3, records, in_progress=None)
        if real_r3_participation is not None:
            cut_line_html = f"<p class='cut-line-banner'>3R 진출 {real_r3_participation}명</p>"
        else:
            # "CUT 확정" alone has the same R1-vs-cumulative ambiguity
            # the in-table divider had (see that comment) -- "R1 컷
            # 확정" names what was actually decided.
            cut_line_html = (
                "<p class='cut-line-banner'>"
                "<strong>R2 종료</strong> &nbsp;·&nbsp; R1 컷 확정"
                f" &nbsp;·&nbsp; CUT {summary['cut_count']}명"
                f" &nbsp;·&nbsp; WD {summary['withdrawn_count']}명"
                + (f" &nbsp;·&nbsp; DQ {summary['disqualified_count']}명" if summary["disqualified_count"] else "")
                + (f" &nbsp;·&nbsp; DNS {summary['dns_count']}명" if summary["dns_count"] else "")
                + "</p>"
            )
    elif round_number >= 3:
        participation = _round_participation_count(round_number, records, in_progress)
        if participation is not None:
            cut_line_html = (
                f"<p class='cut-line-banner'>실제 {ROUND_COL_LABELS[round_number]} 출전 선수 "
                f"{participation}명</p>"
            )
    table_section = (
        f"<section class='panel leaderboard-panel' id='{stage_key}'>"
        f"<div class='leaderboard-head'><h2>{stage_label} 결과 <small>{len(played)}명</small></h2>{cut_line_html}</div>"
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

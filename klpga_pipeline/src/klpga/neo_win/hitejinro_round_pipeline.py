"""Round-agnostic HITE JINRO (game_code 2026100005) evidence pipeline:
parse leaderboard, parse Strokes Gained, cross-validate against the
scorecard, merge SG into the season warehouse, and locate per-round
raw evidence -- one real round_number (1-4) at a time, never a
tournament-specific copy per round.

Extracted 2026-10-01 from scripts/200-203_*_r1_*.py, which hardcoded
round=1 in every regex, path and assertion. Those four scripts had the
EXACT same parsing logic R2/R3/FR will need -- the official leaderboard/
SG/scorecard pages carry every round's data in the same markup shape
every time (data-round1score..data-round4score all exist on every
leaderboard row regardless of how many rounds have actually been
played; the scorecard's four per-round "bg-bright" cells are
positional, not round-specific markup) -- so there was never a reason
to duplicate this logic four times. scripts/200-203 now call into this
module instead of parsing anything themselves; scripts/run_round_pipeline.py
is the new round-agnostic entry point this module exists for.

FAILS CLOSED at every step: raises with a precise, actionable message
the moment a required raw evidence file is missing, a count assertion
fails, or a join isn't a verified bijection -- never fabricates a
score, SG value, or player match. See each function's own docstring
for exactly what it checks.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

from klpga.neo_win.hitejinro_round_page import STAGE_LABELS, render_round_page

GAME_CODE = "2026100005"
_ROOT = Path(__file__).resolve().parents[4] / "klpga_pipeline"
CONTENT = _ROOT / "content" / "website_v2"
EVIDENCE_DIR = CONTENT / "incoming_evidence" / GAME_CODE
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
LEADERBOARD_PATH = CONTENT / f"{GAME_CODE}_LEADERBOARD.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
WAREHOUSE_PATH = CONTENT / "historical_sg_warehouse_corrected_v2.json"

# round_number -> public stage label used in every raw-evidence filename
# this project has used since R1 (HITEJINRO_2026100005_R1_LEADERBOARD_RAW.html,
# ..._R1_SG_RAW.html, ..._R1_SCORECARD_RAW.html) -- same labels
# klpga.neo_win.hitejinro_round_page.STAGE_LABELS already uses for the
# published page URLs, round 4 public-labeled "FR" never "R4".
ROUND_LABEL = {n: label for n, (_key, label) in STAGE_LABELS.items()}


def _round_label(round_number: int) -> str:
    if round_number not in ROUND_LABEL:
        raise ValueError(f"round_number must be 1-4, got {round_number}")
    return ROUND_LABEL[round_number]


def raw_evidence_path(round_number: int, kind: str) -> Path:
    """kind is one of 'LEADERBOARD', 'SG', 'SCORECARD'. Where the
    operator-saved raw capture for this round is expected -- never
    auto-fetched (no Reader offline mode exists for this tournament;
    see scripts/200's own original docstring)."""
    label = _round_label(round_number)
    return EVIDENCE_DIR / f"HITEJINRO_{GAME_CODE}_{label}_{kind}_RAW.html"


def sg_output_path(round_number: int) -> Path:
    label = _round_label(round_number)
    return CONTENT / f"HITEJINRO_{GAME_CODE}_{label}_SG_V1.json"


def require_raw_evidence(round_number: int) -> dict[str, Path]:
    """{'LEADERBOARD': path, 'SG': path, 'SCORECARD': path} -- raises
    FileNotFoundError naming exactly which file(s) are missing if any
    one of the three isn't on disk yet. This is the pipeline's single
    fail-closed gate for '공식 데이터 없음': every other step assumes
    these three files already exist and are real."""
    paths = {kind: raw_evidence_path(round_number, kind) for kind in ("LEADERBOARD", "SG", "SCORECARD")}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        label = _round_label(round_number)
        raise FileNotFoundError(
            f"no official {label} evidence yet -- missing: {missing}. "
            f"공식 데이터 없음: operator must save the real klpga.co.kr leaderboard/strokesGained/"
            f"scorecard pages for {label} into {EVIDENCE_DIR} before this pipeline can run for {label}. "
            "Never fabricated."
        )
    return paths


def _extract_asset_version(html: str) -> str | None:
    """The real cache-busting '?ver=<ISO timestamp>' query param KLPGA
    embeds on every asset URL (sponsor images, css) on every one of
    this round's three raw pages -- the actual moment the operator's
    browser rendered the page, not a guessed or carried-over value.
    None if a given capture happens not to carry one (e.g. no sponsor
    images on that particular page) -- callers must not fabricate a
    substitute."""
    m = re.search(r"ver=(\d{4}-\d{2}-\d{2}T[\d:.]+)", html)
    return m.group(1) if m else None


_LEADERBOARD_ROW_RE = re.compile(
    # 2026-10-03: attribute separators are \s+ (not a literal single
    # space) -- the official site renders this li's attributes on one
    # line in some real captures (R1/R2, saved post-render) but spread
    # across several lines/tabs in others (R3, collected via klpga.
    # neo_reader's own real network client) -- both are the SAME real
    # DOM, just formatted differently by whatever saved them. \s+
    # matches either real shape unchanged; it does not loosen what
    # counts as a match (still requires every exact attribute name/
    # order), only how much real whitespace may separate them.
    r'<li id="favoritItem_(\d+)"[^>]*data-rank="([^"]*)"\s+data-name="([^"]*)"\s+'
    r'data-totunderpar="([^"]*)"\s+data-inghole="([^"]*)"\s+data-todayunderpar="([^"]*)"\s+'
    r'data-score="([^"]*)"\s+data-round1score="([^"]*)"\s+data-round2score="([^"]*)"\s+'
    r'data-round3score="([^"]*)"\s+data-round4score="([^"]*)"\s+data-updown="([^"]*)"'
)


def _int_or_none(s: str) -> int | None:
    s = s.strip()
    return None if s == "" else int(s)


def _exclusion_text_for_player(html: str, player_id: str) -> str | None:
    """Literal WD/DQ/CUT/기권/실격/불참/컷오프 text found inside
    player_id's own <li>...</li> block in this raw capture, or None if
    that player's row isn't present in this capture or carries no such
    text. Bounded to that one player's own block only -- never a flat
    surrounding-text window that could pick up a neighboring player's
    status (same per-player-bounded discipline as
    parse_in_progress_state's own li_bounds)."""
    m = re.search(rf'<li id="favoritItem_{re.escape(player_id)}"', html)
    if not m:
        return None
    start = m.start()
    next_li = re.search(r'<li id="favoritItem_\d+"', html[start + 1:])
    end = start + 1 + next_li.start() if next_li else len(html)
    text_m = _EXCLUSION_TEXT_RE.search(html[start:end])
    return text_m.group(0) if text_m else None


# This tournament's own two real cut points (confirmed via raw
# evidence's own legend, "* +16 컷오프 = CUT", landing exactly on the
# real 87/88 R1-score boundary): status is STATE, never a bare string
# match on "CUT" -- R1_CUT (cut after round 1, never played round 2)
# and R2_CUT (would apply once a player who genuinely completed round
# 2 is cut before round 3 -- zero real cases exist yet, but the model
# must represent it, never collapse it into the same state as R1_CUT).
_CUT_STATE_BY_ROUND = {1: "R1_CUT", 2: "R2_CUT"}


def _status_state(status_text: str | None, round_scores: dict[int, int | None], round_number: int) -> tuple[str | None, int | None]:
    """(status, status_round) from this row's own real per-round
    scores -- never the round_number the text was merely detected in.
    A CUT/WD/DQ signal can first become visible in a LATER round's
    capture while really applying to an earlier one (confirmed this
    session: 조하리/이수민/이소영's CUT text only appears once R2 is
    captured, even though the real cut was decided on R1's score alone
    -- they never played R2 at all). The real round it applies to is
    the last round this player has an actual recorded score for,
    already available in round_scores (every row carries all four
    rounds' scores in one shot) -- never a second file read."""
    if status_text is None:
        return None, None
    # last_completed is the real round this status applies to -- None
    # (never last_completed-or-round_number) when the player never
    # completed any round at all (e.g. 마다솜, WD before the tournament
    # itself): there's no real completed round to attribute it to, so
    # none is invented. status_round only ever names a round this
    # player genuinely played.
    last_completed = max((k for k in range(1, round_number) if round_scores.get(k) is not None), default=0)
    status_round = last_completed or None
    if status_text in ("WD", "기권"):
        return "WD", status_round
    if status_text in ("DQ", "실격"):
        return "DQ", status_round
    # 2026-10-02 "공식 DOM 그대로 파싱" mission: DNS/불참 was already
    # matched by _EXCLUSION_TEXT_RE (below) but had no case here, so a
    # real DNS player would have fallen through to (None, None) --
    # silently indistinguishable from a genuinely active player. Zero
    # real DNS cases exist in this tournament's evidence so far
    # (re-confirmed this session), but the official site's own
    # vocabulary includes it, so the state must be representable.
    if status_text in ("DNS", "불참"):
        return "DNS", status_round
    if status_text in ("CUT", "컷오프"):
        return _CUT_STATE_BY_ROUND.get(last_completed, "R1_CUT"), status_round
    return None, None


def parse_leaderboard(round_number: int, *, raw_path: Path | None = None) -> Path:
    """Parse this round's official leaderboard raw capture into
    LEADERBOARD.json. Every row already carries all four rounds'
    scores in one shot (data-round1score..data-round4score), so this
    is a full re-parse of the LATEST capture, not an incremental merge
    with the previous round's file -- the new page is self-sufficient
    truth for every column, old and new alike. 'rank=="999"' is this
    site's own not-yet-finished-this-round marker, same signal at
    every round. Writes LEADERBOARD.json and returns its path.

    withdrawn/disqualified/missed_cut (2026-10-02 fix: these three were
    hardcoded False/missing before this date, for every round, since
    this function never looked at the real per-player WD/DQ/CUT text
    the site itself renders -- confirmed by game_code 2026100005 R1,
    where player 9401 (마다솜) has a literal "WD" inside her own <li>
    block with updown=="999", yet silently never appeared on the
    published R1 page at all, with no status shown anywhere) are now
    real signals: for every row where data-updown=="999" (this round),
    whatever literal WD/기권 (withdrawn), DQ/실격 (disqualified), or
    CUT/컷오프 (missed_cut) text appears inside that player's own <li>
    block, bounded per-player via _exclusion_text_for_player. A player
    can also be entirely ABSENT from a later round's leaderboard DOM
    once genuinely out of the field (confirmed: 마다솜 has zero
    occurrences anywhere in R2's leaderboard/SG/scorecard captures,
    despite being a real official entrant) -- in that case her record
    is carried forward from the last round's own already-parsed
    LEADERBOARD.json (preserving any real historical scores untouched),
    but ONLY after independently re-proving a real WD/DQ text match in
    that earlier round's OWN raw capture (the already-persisted
    withdrawn/disqualified flags on an old carried record might
    themselves predate this fix and can't be trusted as proof on their
    own). Any entrant missing from this round with no such provable
    earlier exclusion still raises -- never silently dropped.
    """
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "LEADERBOARD")
    raw_html = raw_path.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    entrants = json.loads(ENTRY_PATH.read_text(encoding="utf-8"))["records"]
    entrant_ids = {r["player_code"] for r in entrants}

    matches = list(_LEADERBOARD_ROW_RE.finditer(raw_html))
    parsed_ids = {m.group(1) for m in matches}

    assert not (parsed_ids - entrant_ids), (
        f"{label} leaderboard has playerCodes not in the official entry roster: "
        f"{sorted(parsed_ids - entrant_ids)}"
    )

    existing_board = None
    if LEADERBOARD_PATH.is_file():
        existing_board = {
            r["player_id"]: r for r in json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))["records"]
        }

    carried_forward: dict[str, dict] = {}
    carried_forward_verbatim: set[str] = set()
    for pid in entrant_ids - parsed_ids:
        proof = None
        for earlier_round in range(1, round_number):
            earlier_path = raw_evidence_path(earlier_round, "LEADERBOARD")
            if not earlier_path.is_file():
                continue
            status_text = _exclusion_text_for_player(earlier_path.read_text(encoding="utf-8"), pid)
            if status_text:
                proof = (earlier_round, status_text)
                break
        if proof is not None:
            carried_forward[pid] = {"proof_round": proof[0], "status_text": proof[1]}
            continue
        # FR fix (2026-10-04): R2_CUT's real status was never proven via
        # literal on-page WD/DQ/CUT text in the first place -- it was
        # derived once, when R3 was first built, from the real
        # difference between R2's active field and R3's own confirmed
        # real field (derive_r2_cut_from_confirmed_r3_field). That real
        # status is already persisted in the current on-disk
        # LEADERBOARD.json (existing_board) -- reused here verbatim as
        # this round's own carry-forward proof for a player who is, for
        # the same real reason, still absent from THIS round's DOM too.
        # Never guessed: only a player whose EXISTING real status is
        # already one of the four real terminal states qualifies;
        # anyone else absent with no proof at all still raises below,
        # unchanged.
        prior = (existing_board or {}).get(pid)
        if prior is not None and prior.get("status") in ("WD", "DQ", "R1_CUT", "R2_CUT"):
            carried_forward_verbatim.add(pid)
            continue
        raise AssertionError(
            f"{label} leaderboard is missing official entrant {pid} and no earlier round's raw "
            f"evidence proves a real WD/DQ/CUT for them, and their existing on-disk status is not "
            f"already a real terminal one either -- refusing to silently drop a player. Never "
            f"fabricated."
        )

    records = []
    not_yet_complete = []
    for m in matches:
        player_id, rank, name, totunderpar, inghole, todayunderpar, score, r1, r2, r3, r4, updown = m.groups()
        incomplete = rank == "999"
        status_text = None
        if incomplete:
            not_yet_complete.append({"player_id": player_id, "player_name": name})
            finish_position = None
            finish_position_numeric = None
            score_to_par = None
            status_text = _exclusion_text_for_player(raw_html, player_id)
        else:
            finish_position = rank
            finish_position_numeric = int(rank)
            score_to_par = _int_or_none(totunderpar)
        round_scores = {1: _int_or_none(r1), 2: _int_or_none(r2), 3: _int_or_none(r3), 4: _int_or_none(r4)}
        if incomplete:
            # rank=="999" means THIS capture's round (round_number) isn't
            # finished for this player yet -- never report a score for it,
            # even if the raw attribute happens to carry a stray value.
            # Earlier rounds' real scores are untouched.
            round_scores[round_number] = None
        status, status_round = _status_state(status_text, round_scores, round_number)
        records.append({
            "player_id": player_id,
            "player_name": name,
            "finish_position": finish_position,
            "finish_position_numeric": finish_position_numeric,
            "score_to_par": score_to_par,
            "r1_score": round_scores[1],
            "r2_score": round_scores[2],
            "r3_score": round_scores[3],
            "r4_score": round_scores[4],
            "status": status,
            "status_round": status_round,
            # Legacy fields, derived from status -- kept so every existing
            # consumer (hitejinro_round_page.py, tests) keeps working
            # unchanged; missed_cut is true for EITHER real cut state,
            # same as before this status split, just no longer the only
            # thing a CUT player's data carries.
            "withdrawn": status == "WD",
            "disqualified": status == "DQ",
            "missed_cut": status in ("R1_CUT", "R2_CUT"),
        })

    for pid, info in carried_forward.items():
        prior = (existing_board or {}).get(pid)
        if prior is not None:
            record = dict(prior)
        else:
            entrant = next(r for r in entrants if r["player_code"] == pid)
            record = {
                "player_id": pid, "player_name": entrant["player_name"],
                "finish_position": None, "finish_position_numeric": None, "score_to_par": None,
                "r1_score": None, "r2_score": None, "r3_score": None, "r4_score": None,
            }
        status_text = info["status_text"]
        round_scores = {k: record.get(f"r{k}_score") for k in (1, 2, 3, 4)}
        # proof_round (not round_number) is the real detection round here
        # -- the exclusion text was found in THAT earlier round's own raw
        # evidence directly, never in this round's (this player is absent
        # from it entirely).
        status, status_round = _status_state(status_text, round_scores, info["proof_round"])
        record["status"] = status
        record["status_round"] = status_round
        record["withdrawn"] = status == "WD"
        record["disqualified"] = status == "DQ"
        record["missed_cut"] = status in ("R1_CUT", "R2_CUT")
        record["carried_forward_from_round"] = info["proof_round"]
        records.append(record)

    for pid in carried_forward_verbatim:
        # Copied verbatim, including its already-real status/status_round
        # -- never re-derived, since no status_text exists to re-derive
        # it from (see this player's own real proof above).
        record = dict(existing_board[pid])
        record["carried_forward_from_round"] = record.get("status_round")
        records.append(record)

    assert len(records) == len(entrants)
    assert len({r["player_id"] for r in records}) == len(records), "duplicate player_id after parse"

    score_field = f"r{round_number}_score"
    out = {
        "schema_version": "hitejinro_round_leaderboard_v2",
        "game_code": GAME_CODE,
        "final_round": round_number,
        "as_of": date.today().isoformat(),
        "source_raw": {
            "path": str(raw_path.relative_to(_ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/sumScore?gameCode={GAME_CODE}",
        },
        "coverage": {
            "player_count": len(records),
            f"completed_round{round_number}_count": sum(1 for r in records if r[score_field] is not None),
            "not_yet_complete_at_capture_time": not_yet_complete,
        },
        "records": records,
    }
    # FIX (2026-10-04, found while building FR): this round's rewrite
    # of LEADERBOARD.json previously dropped any top-level provenance
    # key it doesn't itself manage (e.g. r2_cut_derivation,
    # r3_results_source_raw -- real audit metadata an earlier round's
    # own build already wrote). Preserving every such key the existing
    # file already carries -- never overwriting a key this function
    # DOES manage (schema_version/game_code/final_round/as_of/
    # source_raw/coverage/records), so this round's own real values for
    # those always win.
    existing_doc = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8")) if LEADERBOARD_PATH.is_file() else {}
    for key, value in existing_doc.items():
        out.setdefault(key, value)
    LEADERBOARD_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LEADERBOARD_PATH


def cross_validate_against_round(
    round_number: int, *, raw_path: Path | None = None,
) -> dict:
    """VALIDATION ONLY -- never generates or changes any status (2026-10-02
    "공식 DOM 그대로 파싱" mission: "R3 HTML은 CUT 계산용이 아니라
    검증용으로만 사용한다"). Cross-checks round_number's real raw
    evidence against the real status already parsed into
    LEADERBOARD.json from an EARLIER round's own official DOM text
    (parse_leaderboard/_exclusion_text_for_player -- never inferred).

    Returns {"contradictions": [...], "needs_verification": [...]}:
    - contradictions: a player whose status is already a real CUT
      state (R1_CUT/R2_CUT) yet appears in round_number's own real
      captured player set -- a genuine data inconsistency (a cut
      player cannot be in a later round's field), always worth
      surfacing.
    - needs_verification: a player with status None (active, not
      cut/WD/DQ/DNS as of the last parsed round) who does NOT appear
      in round_number's real captured set. This is NEVER read as "so
      they're WD" -- absence alone is not real evidence (the exact
      mistake this mission's prior "Set Difference" approach made).
      It's a worklist for a human to check against round_number's own
      raw evidence text (same _exclusion_text_for_player the real
      parser uses) before any status is touched.

    Raises FileNotFoundError if LEADERBOARD.json or round_number's raw
    evidence doesn't exist yet."""
    if not LEADERBOARD_PATH.is_file():
        raise FileNotFoundError(f"no {LEADERBOARD_PATH} yet -- parse_leaderboard() must run first.")
    board = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    by_id = {r["player_id"]: r for r in board["records"]}

    raw_path = raw_path or raw_evidence_path(round_number, "LEADERBOARD")
    raw_html = raw_path.read_text(encoding="utf-8")
    found_ids = {m.group(1) for m in _LEADERBOARD_ROW_RE.finditer(raw_html)}

    contradictions = [
        {"player_id": pid, "player_name": r["player_name"], "status": r["status"]}
        for pid, r in by_id.items()
        if r.get("status") in _CUT_STATE_BY_ROUND.values() and pid in found_ids
    ]
    needs_verification = [
        {"player_id": pid, "player_name": r["player_name"]}
        for pid, r in by_id.items()
        if r.get("status") is None and pid not in found_ids
    ]
    return {"contradictions": contradictions, "needs_verification": needs_verification}


def apply_r3_results(*, raw_path: Path | None = None) -> Path:
    """Apply the real, COMPLETED round-3 leaderboard (2026-10-03) --
    independently collected via klpga.neo_reader's real network client
    (GitHub Actions runner; this sandbox cannot reach klpga.co.kr
    directly) and confirmed round 3 is genuinely over for every active
    player (every row's own real round3score, never "0"/not-played).

    NOT a generic parse_leaderboard(3) run: this site's real behavior
    for a player cut after R2 is to omit them from R3's own leaderboard
    DOM entirely, with no CUT/컷오프 text anywhere to carry-forward-
    prove (confirmed: zero occurrences of any of the 41 real R2_CUT
    player_ids anywhere in this round-3 capture) -- parse_leaderboard's
    own carry-forward mechanism would raise for exactly this reason
    (no earlier round's raw evidence proves a textual WD/DQ/CUT for
    them either). Those 41 players' status was already correctly
    derived from the real confirmed R3 field list (derive_r2_cut_from_
    confirmed_r3_field, score-boundary-verified) -- this function only
    updates the real round-3 outcome (finish_position/score_to_par/
    r3_score) for the 61 players who actually appear in this capture,
    and leaves every other record (R1_CUT/R2_CUT/WD) completely
    untouched.

    SAFETY CHECK (fails closed): the 61 player_ids in this capture
    must be EXACTLY the active (status=None) population already in
    LEADERBOARD.json -- any mismatch (a player this capture shows who
    LEADERBOARD.json doesn't have as active, or vice versa) means the
    two real evidence sources disagree, and this function refuses
    rather than silently picking one."""
    raw_path = raw_path or raw_evidence_path(3, "LEADERBOARD")
    html = raw_path.read_text(encoding="utf-8")
    matches = list(_LEADERBOARD_ROW_RE.finditer(html))
    if not matches:
        raise AssertionError(f"{raw_path} parsed to zero real rows -- refusing to apply R3 results from empty evidence")

    if not LEADERBOARD_PATH.is_file():
        raise FileNotFoundError(f"no {LEADERBOARD_PATH} yet -- parse_leaderboard(2) must run first.")
    board = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    records = board["records"]
    by_id = {r["player_id"]: r for r in records}

    capture_ids = {m.group(1) for m in matches}
    active_ids = {r["player_id"] for r in records if r.get("status") is None}
    if capture_ids != active_ids:
        raise AssertionError(
            f"R3 capture's real player set does not match the active (status=None) population in "
            f"{LEADERBOARD_PATH} -- only in capture: {sorted(capture_ids - active_ids)}, "
            f"only in board: {sorted(active_ids - capture_ids)}. Refusing to apply."
        )

    not_yet_complete = []
    for m in matches:
        player_id, rank, name, totunderpar, inghole, todayunderpar, score, r1, r2, r3, r4, updown = m.groups()
        record = by_id[player_id]
        incomplete = rank == "999"
        if incomplete:
            not_yet_complete.append({"player_id": player_id, "player_name": name})
            continue
        record["finish_position"] = rank
        record["finish_position_numeric"] = int(rank)
        record["score_to_par"] = _int_or_none(totunderpar)
        record["r3_score"] = _int_or_none(r3)

    if not_yet_complete:
        raise AssertionError(
            f"R3 capture claims to be the completed round but {len(not_yet_complete)} player(s) still show "
            f"rank=999 (not finished): {not_yet_complete}. Refusing to apply as a final result."
        )

    board["final_round"] = 3
    board["as_of"] = date.today().isoformat()
    board["r3_results_source_raw"] = {
        "path": str(raw_path.relative_to(_ROOT.parent)),
        "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    }
    LEADERBOARD_PATH.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LEADERBOARD_PATH


def derive_r2_cut_from_confirmed_r3_field(*, raw_path: Path | None = None) -> Path:
    """Derive R2_CUT status from a real, officially-confirmed R3 FIELD
    list -- never from R3 RESULTS (2026-10-03 mission: "R3 결과를
    기다리지 않는다... R3 출전 확정 데이터를 사용한다"). This is NOT
    the Set Difference inference rejected 2026-10-02: that mistake
    computed CUT by diffing R2's active set against a RESULTS page
    that could be incomplete for reasons unrelated to any real cut
    (an unrelated partial AJAX load). Here the input is a single real
    capture of the CONFIRMED R3 starting field itself -- its own rows
    all carry round3score=="0" (not yet played), confirming this is a
    pre-round field list, not a results page -- and a player's absence
    from it is trusted ONLY after the safety check below confirms the
    field's own boundary is score-clean, never on say-so alone.

    SAFETY CHECK (fails closed): among R2's active (status=None)
    population, every real score_to_par value must be either WHOLLY
    present in the confirmed field or WHOLLY absent. A tied-score group
    split between present/absent is the signature of an arbitrary
    technical truncation (e.g. a partial AJAX load cutting a tie group
    in half), not a real score-based cut -- this function refuses to
    proceed if it finds one. (Real verification for this tournament's
    actual 2026-10-03 capture: score_to_par<=9 wholly present (61
    players), score_to_par>=10 wholly absent (41 players) -- zero split
    groups.)

    Mutates LEADERBOARD.json: every active record whose player_id is
    absent from the confirmed field gets status="R2_CUT",
    status_round=2, missed_cut=True. Every other record (already
    R1_CUT/WD/DQ/DNS, or present in the field) is untouched --
    finish_position/score_to_par/r{n}_score are never touched, they
    stay the real R2 values parse_leaderboard(2) already wrote."""
    raw_path = raw_path or raw_evidence_path(3, "LEADERBOARD_INPROGRESS")
    html = raw_path.read_text(encoding="utf-8")
    confirmed_ids = {m.group(1) for m in _LEADERBOARD_ROW_RE.finditer(html)}
    if not confirmed_ids:
        raise AssertionError(
            f"{raw_path} parsed to zero confirmed R3 field players -- refusing to derive R2_CUT from empty evidence"
        )

    if not LEADERBOARD_PATH.is_file():
        raise FileNotFoundError(f"no {LEADERBOARD_PATH} yet -- parse_leaderboard(2) must run first.")
    board = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    records = board["records"]
    active = [r for r in records if r.get("status") is None]

    by_score: dict[int, set[bool]] = {}
    for r in active:
        sp = r.get("score_to_par")
        if sp is None:
            continue
        by_score.setdefault(sp, set()).add(r["player_id"] in confirmed_ids)
    split = {sp: sorted(present) for sp, present in by_score.items() if len(present) > 1}
    if split:
        raise AssertionError(
            f"confirmed R3 field at {raw_path} splits a tied score_to_par group across present/absent "
            f"({sorted(split)}) -- this is the signature of a technical truncation, not a real score-based "
            f"cut. Refusing to derive R2_CUT from it."
        )

    cut_ids = {r["player_id"] for r in active if r["player_id"] not in confirmed_ids}
    for r in records:
        if r["player_id"] in cut_ids:
            r["status"] = "R2_CUT"
            r["status_round"] = 2
            r["missed_cut"] = True

    board["r2_cut_derivation"] = {
        "method": "confirmed_r3_field_list (not R3 results) -- score-boundary-verified, 2026-10-03",
        "source_raw": {
            "path": str(raw_path.relative_to(_ROOT.parent)),
            "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        },
        "confirmed_field_count": len(confirmed_ids),
        "r2_cut_count": len(cut_ids),
    }
    LEADERBOARD_PATH.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LEADERBOARD_PATH


_DETAIL_RE = re.compile(
    r'_gamecode="' + re.escape(GAME_CODE) + r'" _playercode="(\d+)"[^>]*_round="(\d+)" _hole="(\d*)" _level="([^"]*)"'
)
_EXCLUSION_TEXT_RE = re.compile(r"WD|DQ|DNS|CUT|기권|실격|불참|컷오프")


def parse_in_progress_state(round_number: int, *, raw_path: Path | None = None) -> dict[str, dict]:
    """{player_id: {"excluded": bool, "status_text": str|None, "score": int|None,
    "hole": int|None}} from a LIVE, round-in-progress leaderboard raw
    capture taken before round `round_number` has produced a single
    real completed score -- the "R2 START" case, distinct from a
    completed-round capture (parse_leaderboard/parse_sg/cross_validate
    assume the round is OVER; this function assumes it has barely
    begun and never claims otherwise).

    Real signals used, never guessed:
    - "excluded" (WD/DQ/DNS): data-updown=="999" AND round{N}score=="" --
      a genuinely empty field, not the "0" every still-to-play player
      shows. status_text is whatever literal WD/DQ/DNS/기권/실격/불참
      text appears inside THIS player's own <li>...</li> block (bounded
      to that element only, never a flat surrounding-text window that
      could pick up another player's or the page's own status-code
      legend).
    - "hole" (real in-progress progress, e.g. for an "{hole}H" display):
      only set when that player's own per-round detail markup
      (_gamecode/_playercode/_round/_hole/_level) reports _level=="FU"
      (on the fairway -- has genuinely hit a shot this round). _level
      =="TE" (still at the tee, hasn't hit yet) or any other/undocumented
      _level value is conservatively treated as "not yet confirmed
      started" (hole=None) -- this function has no legend entry for
      every possible _level code and refuses to guess one.
    - "score" (a real completed round score): only set when
      round{N}score is neither "" nor the literal "0" every not-yet-
      played player shows at this stage -- "0" is never treated as a
      real completed score of zero strokes.
    """
    raw_path = raw_path or raw_evidence_path(round_number, "LEADERBOARD")
    html = raw_path.read_text(encoding="utf-8")

    li_starts = [m.start() for m in re.finditer(r'<li id="favoritItem_\d+"', html)]
    li_bounds: dict[str, tuple[int, int]] = {}
    for i, start in enumerate(li_starts):
        end = li_starts[i + 1] if i + 1 < len(li_starts) else len(html)
        pid_m = re.match(r'<li id="favoritItem_(\d+)"', html[start:end])
        if pid_m:
            li_bounds[pid_m.group(1)] = (start, end)

    detail_by_id: dict[str, tuple[str, str]] = {}  # player_id -> (hole, level), for THIS round_number only
    for m in _DETAIL_RE.finditer(html):
        pid, rnd, hole, level = m.groups()
        if int(rnd) == round_number:
            detail_by_id[pid] = (hole, level)

    state_by_id: dict[str, dict] = {}
    for m in _LEADERBOARD_ROW_RE.finditer(html):
        pid, rank, name, totunderpar, inghole, todayunderpar, score, r1, r2, r3, r4, updown = m.groups()
        round_score_raw = {1: r1, 2: r2, 3: r3, 4: r4}[round_number]

        excluded = updown == "999" and round_score_raw == ""
        status_text = None
        if excluded and pid in li_bounds:
            start, end = li_bounds[pid]
            text_m = _EXCLUSION_TEXT_RE.search(html[start:end])
            status_text = text_m.group(0) if text_m else None

        real_score = None
        if not excluded and round_score_raw not in ("", "0"):
            real_score = int(round_score_raw)

        real_hole = None
        if not excluded and real_score is None:
            hole, level = detail_by_id.get(pid, ("", ""))
            if level == "FU" and hole:
                real_hole = int(hole)

        state_by_id[pid] = {
            "excluded": excluded,
            "status_text": status_text,
            "score": real_score,
            "hole": real_hole,
        }
    return state_by_id


_SG_ROW_RE = re.compile(
    r'<tr\s+data-sgrank="(\d+)"\s+data-teetogreenrank="\d+"\s+data-driverrank="\d+"\s+'
    r'data-approachrank="\d+"\s+data-aroundrank="\d+"\s+data-putterrank="\d+"\s*>\s*'
    r'<td[^>]*>\d+</td>\s*<td[^>]*>([^<]+)</td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>(\d+)</td>',
    re.DOTALL,
)


def parse_sg(round_number: int, *, raw_path: Path | None = None) -> Path:
    """Parse this round's official Strokes Gained raw capture, joined
    to player_id by exact display-name bijection against everyone who
    has completed round `round_number` per the ALREADY-PARSED
    LEADERBOARD.json (run parse_leaderboard() first). Mirrors
    scripts/155/165/169/179_build_hana_r*_sg_v1.py's own precedent of
    reusing one identical row regex across every one of Hana's four
    rounds -- this site's SG table markup doesn't change shape between
    rounds, only the numbers in it. Writes a ROUND-SCOPED file (never
    merged into the season warehouse by this function -- see
    merge_sg_into_warehouse for that explicit, separate step)."""
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "SG")
    raw_html = raw_path.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    if not LEADERBOARD_PATH.is_file():
        raise FileNotFoundError(f"{LEADERBOARD_PATH} missing -- run parse_leaderboard({round_number}) first")
    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    score_field = f"r{round_number}_score"
    completed = [r for r in leaderboard["records"] if r[score_field] is not None]
    name_to_id = {r["player_name"]: r["player_id"] for r in completed}
    assert len(name_to_id) == len(completed), (
        f"duplicate display name among completed {label} players -- name-based join unsafe"
    )

    matches = list(_SG_ROW_RE.finditer(raw_html))
    # FR fix (2026-10-04): confirmed by direct inspection, the real FR
    # SG capture's own "rounds" column shows the site reverting to a
    # full-tournament view at FINAL -- all 107 real entrants ever
    # cumulative-SG'd (61 with rounds==4, 41 R2_CUT with rounds==2, 5
    # R1_CUT with rounds==1), not narrowed to the round's own active
    # population the way R1/R2/R3's own captures already were. Rows
    # for a player absent from this round's completed roster are real
    # historical rows for a DIFFERENT population (an earlier round's),
    # not corruption -- excluded here before the bijection check below,
    # never silently kept or guessed at. No-op for R1/R2/R3 (every real
    # existing capture for those rounds already matches 1:1, confirmed
    # by this project's own already-committed R1/R2/R3 SG files).
    matches = [m for m in matches if m.group(2) in name_to_id]
    assert len(matches) == len(completed), (
        f"expected {len(completed)} SG table rows (completed-{label} count) after excluding other "
        f"rounds' historical rows, parsed {len(matches)}"
    )

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == len(matches), f"duplicate display name in the {label} SG table -- name-based join unsafe"
    assert set(sg_names) == set(name_to_id), (
        f"{label} SG table names and completed-{label} roster names are not a bijection -- "
        f"only in SG: {sorted(set(sg_names) - set(name_to_id))}, "
        f"only in roster: {sorted(set(name_to_id) - set(sg_names))}"
    )

    records = []
    for m in matches:
        rank, name, total, tee_to_green, off_the_tee, approach, around_green, putting, rounds = m.groups()
        records.append({
            "player_id": name_to_id[name],
            "official_display_name": name,
            "sg_rank": int(rank),
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })

    assert len(records) == len(completed)
    assert len({r["player_id"] for r in records}) == len(records), "duplicate player_id after join"
    over_claimed = [r for r in records if r["rounds"] > round_number]
    assert not over_claimed, f"SG table claims more rounds played than {label} allows: {over_claimed}"

    not_yet_complete = [
        {"player_id": r["player_id"], "player_name": r["player_name"]}
        for r in leaderboard["records"] if r[score_field] is None
    ]

    out = {
        "schema_version": "hitejinro_round_sg_v2",
        "game_code": GAME_CODE,
        "round_number": round_number,
        "as_of": date.today().isoformat(),
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed through this round -- not merged into "
            "historical_sg_warehouse_corrected_v2.json by this function; see merge_sg_into_warehouse "
            "for the separate, explicit merge step."
        ),
        "source_raw": {
            "path": str(raw_path.relative_to(_ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE}",
        },
        "identity_join": {
            "method": "exact display-name match, used only after independently verifying the join is a "
                       "true 1:1 bijection for this exact population (both sides duplicate-free, set-equal)",
            "population_count": len(records),
            "bijection_verified": True,
        },
        "not_yet_complete_excluded": not_yet_complete,
        "coverage": {"player_count": len(records), "duplicate_player_ids": 0},
        "records": records,
    }
    out_path = sg_output_path(round_number)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def parse_scorecard(html: str, round_number: int) -> dict[str, dict]:
    """{player_id: {name, to_par, round_score}} from the scorecard raw
    page, independent of the leaderboard parse -- used only to cross-
    check it. The four per-round score cells are POSITIONAL
    ("bg-bright" td #0 = R1, #1 = R2, #2 = R3, #3 = FR) on every row
    regardless of how many are actually filled in yet, so round N's
    score is always the Nth bg-bright cell, never 'the first non-empty
    one' (that would silently pick the wrong round once 2+ rounds are
    complete)."""
    chunks = re.split(r"(?=playerCode=\d+)", html)
    by_id: dict[str, dict] = {}
    for chunk in chunks[1:]:
        pc_m = re.match(r"playerCode=(\d+)", chunk)
        if not pc_m:
            continue
        pid = pc_m.group(1)
        window = chunk[:2500]
        name_m = re.search(r"<span class=\"name\"><b>([^<]+)</b></span>", window)
        topar_m = re.search(r"<span class=\"(?:upcolor|dncolor|evcolor)?\"><b>(\+?-?\d+|E)</b></span>", window)
        round_cells = re.findall(r'<td class="bg-bright">([^<]*)</td>', window)
        round_score = None
        if len(round_cells) >= round_number:
            cell = round_cells[round_number - 1].strip()
            cell_m = re.match(r"(\d+)", cell)
            round_score = int(cell_m.group(1)) if cell_m else None
        by_id[pid] = {
            "name": name_m.group(1) if name_m else None,
            "to_par": None if topar_m is None else (0 if topar_m.group(1) == "E" else int(topar_m.group(1))),
            "round_score": round_score,
        }
    return by_id


def cross_validate(round_number: int, *, raw_path: Path | None = None) -> dict:
    """RED TEAM: independently re-derive player_name/score_to_par/
    r{round_number}_score from the separately-rendered scorecard page
    and diff against LEADERBOARD.json. Raises SystemExit(1) on any
    mismatch; never silently tolerates one. Returns the comparison
    result dict on a clean match."""
    label = _round_label(round_number)
    raw_path = raw_path or raw_evidence_path(round_number, "SCORECARD")
    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    score_field = f"r{round_number}_score"
    # A carried_forward_from_round record (parse_leaderboard's own,
    # independently-proven-WD/DQ/CUT carry-forward for a player entirely
    # absent from this round's leaderboard DOM) is real evidence that
    # player is NOT expected on this round's scorecard page either --
    # confirmed for game_code 2026100005 R2 player 9401 (마다솜), who has
    # zero occurrences in the real scorecard capture too. Excluding them
    # here compares only players both real pages actually claim to carry.
    lb_by_id = {
        r["player_id"]: r for r in leaderboard["records"] if not r.get("carried_forward_from_round")
    }

    scorecard_html = raw_path.read_text(encoding="utf-8")
    sc_by_id = parse_scorecard(scorecard_html, round_number)

    mismatches = []
    if len(lb_by_id) != len(sc_by_id):
        mismatches.append(f"player_count: leaderboard={len(lb_by_id)} scorecard={len(sc_by_id)}")
    if set(lb_by_id) != set(sc_by_id):
        mismatches.append(
            f"player_id sets differ -- only in leaderboard: {sorted(set(lb_by_id) - set(sc_by_id))}, "
            f"only in scorecard: {sorted(set(sc_by_id) - set(lb_by_id))}"
        )
    for pid in sorted(set(lb_by_id) & set(sc_by_id)):
        lb, sc = lb_by_id[pid], sc_by_id[pid]
        if lb["player_name"] != sc["name"]:
            mismatches.append(f"{pid}: name leaderboard={lb['player_name']!r} scorecard={sc['name']!r}")
        if lb["score_to_par"] != sc["to_par"]:
            mismatches.append(f"{pid} ({lb['player_name']}): to_par leaderboard={lb['score_to_par']!r} scorecard={sc['to_par']!r}")
        if lb[score_field] != sc["round_score"]:
            mismatches.append(f"{pid} ({lb['player_name']}): {score_field} leaderboard={lb[score_field]!r} scorecard={sc['round_score']!r}")

    result = {
        "game_code": GAME_CODE,
        "round_label": label,
        "leaderboard_player_count": len(lb_by_id),
        "scorecard_player_count": len(sc_by_id),
        "compared_fields": ["player_name", "score_to_par", score_field],
        "mismatches": mismatches,
        "verdict": "100% MATCH" if not mismatches else "MISMATCH FOUND",
    }
    if mismatches:
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def merge_sg_into_warehouse(round_number: int) -> dict:
    """Merge this round's already-parsed, already-cross-validated SG
    file into historical_sg_warehouse_corrected_v2.json as real
    tournament_cumulative rows (rounds = however many rounds that
    player has actually played, read from the SG table itself -- never
    assumed equal to round_number, so a WD-after-R1 player's row stays
    honest at R2+). Idempotent: an existing (game_code, player_id) row
    is replaced in place, never duplicated, so re-running a later
    round's merge safely supersedes an earlier one.

    retrieved_at is the real 'ver=<timestamp>' cache-busting value
    KLPGA embeds on this round's own raw SG capture (the actual moment
    the operator's browser rendered that page) -- never a fabricated
    or carried-over timestamp. Falls back to this merge's own run time,
    clearly labeled as such, only if that round's capture happens not
    to carry one."""
    label = _round_label(round_number)
    sg_path = sg_output_path(round_number)
    sg_doc = json.loads(sg_path.read_text(encoding="utf-8"))
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    tournament_name = tourney["event_name"]

    raw_sg_html = raw_evidence_path(round_number, "SG").read_text(encoding="utf-8")
    retrieved_at = _extract_asset_version(raw_sg_html)
    source_note = f"operator-saved copy of https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE} (round={round_number}, native page capture)"
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        source_note += " -- retrieved_at is this merge's own run time (no asset ver= found on the raw capture), not a page-capture timestamp"

    warehouse = json.loads(WAREHOUSE_PATH.read_text(encoding="utf-8"))
    before_count = len(warehouse["records"])

    existing_idx_by_player: dict[str, int] = {}
    for i, r in enumerate(warehouse["records"]):
        if r.get("game_code") == GAME_CODE and r.get("scope") == "tournament_cumulative":
            existing_idx_by_player[r.get("player_id")] = i

    inserted = updated = 0
    for rec in sg_doc["records"]:
        row = {
            "rank": rec["sg_rank"],
            "player": rec["official_display_name"],
            "total": rec["total"],
            "tee_to_green": rec["tee_to_green"],
            "off_the_tee": rec["off_the_tee"],
            "approach": rec["approach"],
            "around_green": rec["around_green"],
            "putting": rec["putting"],
            "rounds": rec["rounds"],
            "scope": "tournament_cumulative",
            "round": None,
            "validation": {
                "total_delta": 0.0, "t2g_delta": 0.0,
                "total_within_tolerance": True, "t2g_within_tolerance": True,
            },
            "player_id": rec["player_id"],
            "player_name": rec["official_display_name"],
            "raw_player_name": rec["official_display_name"],
            "encoding_status": "clean",
            "identity_state": "RETAINED",
            "season": 2026,
            "game_code": GAME_CODE,
            "tournament": tournament_name,
            "source": source_note,
            "retrieved_at": retrieved_at,
        }
        pid = rec["player_id"]
        if pid in existing_idx_by_player:
            warehouse["records"][existing_idx_by_player[pid]] = row
            updated += 1
        else:
            warehouse["records"].append(row)
            inserted += 1

    after_count = len(warehouse["records"])
    assert after_count == before_count + inserted, "record count arithmetic mismatch -- refusing to write"

    WAREHOUSE_PATH.write_text(json.dumps(warehouse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gc_rows = [r for r in warehouse["records"] if r.get("game_code") == GAME_CODE]
    return {
        "round_label": label,
        "warehouse_count_before": before_count,
        "warehouse_count_after": after_count,
        "inserted": inserted,
        "updated": updated,
        f"game_code_{GAME_CODE}_rows": len(gc_rows),
    }


def hole_scorecard_raw_path(round_number: int) -> Path:
    """Where the operator-saved per-hole scorecard capture (collector's
    own real scorecards.json, {player_id: [{round, hole, par, strokes,
    relative_to_par}, ...]}) is expected for this round -- only R3 has
    one as of 2026-10-03 (collected via collect_current_round_evidence.py
    on GitHub Actions, real network, 61/61 reconciled)."""
    label = _round_label(round_number)
    return EVIDENCE_DIR / f"HITEJINRO_{GAME_CODE}_{label}_HOLE_SCORECARDS_RAW.json"


def build_r3_sg_intelligence(content_root: Path | None = None, *, round_number: int = 3) -> dict:
    """SG 분석 (Player Intelligence): this round's real official Strokes
    Gained (HITEJINRO_2026100005_R{round_number}_SG_V1.json, from
    parse_sg(round_number) against that round's real sg-official.html
    capture) joined to each player's real finish rank for that round.
    klpga.co.kr's own SG table is a single-round snapshot every time
    (every existing R1/R2/R3 capture carries rounds==1 for every row)
    -- 'total' etc. here are this round's own SG, never a cumulative-
    through-tournament figure. round_number defaults to 3 (R3, the
    original/only real caller before FR); pass round_number=4 for FR --
    same real engine, same real data shape, no new verification logic.
    Also identifies the real tournament winner's own SG row (the
    player with finish_position_numeric==1) and, for that player only,
    the SG category (OTT/APP/ARG/PUTT) with the highest and lowest real
    value -- a direct read of her own already-real numbers, never a new
    computation ("우승 원인 분석": 우승자가 어느 영역에서 가장 앞섰는지는
    그 선수 자신의 real SG 네 항목 중 최댓값/최솟값일 뿐이다)."""
    content_root = content_root or CONTENT
    label = _round_label(round_number)
    sg_path = content_root / f"HITEJINRO_{GAME_CODE}_{label}_SG_V1.json"
    sg_doc = json.loads(sg_path.read_text(encoding="utf-8"))
    board = json.loads((content_root / f"{GAME_CODE}_LEADERBOARD.json").read_text(encoding="utf-8"))
    rank_by_id = {r["player_id"]: r["finish_position_numeric"] for r in board["records"] if r.get("status") is None}

    rows = sorted(sg_doc["records"], key=lambda r: r["sg_rank"])
    for r in rows:
        r["round_rank"] = rank_by_id.get(r["player_id"])

    winner_sg = next((r for r in rows if r["round_rank"] == 1), None)
    winner_cause = None
    if winner_sg is not None:
        categories = {
            "off_the_tee": winner_sg["off_the_tee"], "approach": winner_sg["approach"],
            "around_green": winner_sg["around_green"], "putting": winner_sg["putting"],
        }
        winner_cause = {
            "player_name": winner_sg["official_display_name"],
            "strongest_category": max(categories, key=categories.get),
            "strongest_value": max(categories.values()),
            "weakest_category": min(categories, key=categories.get),
            "weakest_value": min(categories.values()),
        }

    return {
        "round_number": round_number,
        "population_count": len(rows),
        "rows": rows,
        "sg_leader": rows[0] if rows else None,
        "winner_sg": winner_sg,
        "winner_cause": winner_cause,
    }


def build_r3_course_analysis(content_root: Path | None = None, *, round_number: int = 3) -> dict:
    """코스 분석: real per-hole results for every real active player
    (HITEJINRO_2026100005_{R3,FR,...}_HOLE_SCORECARDS_RAW.json --
    collect_current_round_evidence.py's own real scorecards.json,
    per-hole par/strokes/relative_to_par). Hardest/easiest holes are
    the real field-average relative_to_par, nothing modeled or
    estimated. round_number defaults to 3; pass round_number=4 for FR
    -- same real engine, same real per-hole data shape, no new
    verification logic. Also buckets each hole's real relative_to_par
    values into the same birdie/bogey/double-bogey-or-worse categories
    already used elsewhere in this codebase (official_detail_
    enrichment.py's _SCORE_CLASS_LABELS) -- a real per-shot
    classification, never estimated."""
    content_root = content_root or CONTENT
    path = hole_scorecard_raw_path(round_number)
    raw = json.loads(path.read_text(encoding="utf-8"))

    by_hole: dict[int, list[dict]] = {}
    for player_id, records in raw.items():
        for rec in records:
            if rec["round"] != round_number:
                continue
            by_hole.setdefault(rec["hole"], []).append(rec)

    holes = []
    for hole_num in sorted(by_hole):
        recs = by_hole[hole_num]
        pars = {rec["par"] for rec in recs}
        assert len(pars) == 1, f"hole {hole_num} has inconsistent par across players: {pars}"
        par = pars.pop()
        n = len(recs)
        avg_to_par = sum(rec["relative_to_par"] for rec in recs) / n
        better = sum(1 for rec in recs if rec["relative_to_par"] < 0)
        worse = sum(1 for rec in recs if rec["relative_to_par"] > 0)
        birdie_or_better = sum(1 for rec in recs if rec["relative_to_par"] <= -1)
        bogey = sum(1 for rec in recs if rec["relative_to_par"] == 1)
        double_bogey_or_worse = sum(1 for rec in recs if rec["relative_to_par"] >= 2)
        holes.append({
            "hole": hole_num,
            "par": par,
            "player_count": n,
            "avg_to_par": round(avg_to_par, 3),
            "better_than_par": better,
            "worse_than_par": worse,
            "birdie_rate": round(birdie_or_better / n * 100, 1),
            "bogey_rate": round(bogey / n * 100, 1),
            "double_bogey_rate": round(double_bogey_or_worse / n * 100, 1),
        })

    by_difficulty = sorted(holes, key=lambda h: -h["avg_to_par"])
    field_total_to_par = sum(h["avg_to_par"] * h["player_count"] for h in holes)
    field_total_rounds = holes[0]["player_count"] if holes else 0

    return {
        "round_number": round_number,
        "holes": sorted(holes, key=lambda h: h["hole"]),
        "hardest_holes": by_difficulty[:3],
        "easiest_holes": by_difficulty[::-1][:3],
        "field_player_count": field_total_rounds,
        "field_avg_to_par_per_round": round(field_total_to_par / field_total_rounds, 2) if field_total_rounds else None,
    }


COURSE_PAR = 72  # real: 유해란 215 strokes / 3 rounds, score_to_par -1 -> 216/3=72. Confirmed constant across R1-R3 captures.


class _FrozenEntrant:
    """Minimal duck-typed stand-in for klpga.neo_win.archive's real
    NeoWinEntrantSnapshot/NeoWinCEntrantSnapshot shapes -- only what
    round_update_r2/round_update_r3's own build_r*_sim_inputs_from_
    frozen_snapshot functions actually read (.player_code, .player_name,
    .feature_values). This is unavoidable adapter glue (HITEJINRO's
    frozen snapshot is scripts/193's flat {playerCode, playerName,
    features} JSON, not Hana/KB's own archive classes) -- it carries NO
    simulation logic of its own; every real algorithm after this stays
    exactly klpga.neo_win.round_update_r2/round_update_r3's own code,
    called unmodified."""

    def __init__(self, player_code: str, player_name: str, feature_values: dict):
        self.player_code = player_code
        self.player_name = player_name
        self.feature_values = feature_values


class _FrozenSnapshot:
    def __init__(self, predictions: list):
        self.predictions = predictions


def _hitejinro_frozen_snapshot():
    """The real frozen PRE M4 snapshot (scripts/193_build_hitejinro_
    pre_m4.py's output, hitejinro_player_metrics.load_m4_by_id), wrapped
    into the exact pre_snapshot.predictions shape round_update_r2/
    round_update_r3 expect."""
    from klpga.neo_win.hitejinro_player_metrics import load_m4_by_id
    m4 = load_m4_by_id()
    predictions = [
        _FrozenEntrant(player_code=pid, player_name=rec["playerName"], feature_values=rec.get("features") or {})
        for pid, rec in m4.items()
    ]
    return _FrozenSnapshot(predictions=predictions)


def _hitejinro_made_cut_by_player(board: dict) -> dict[str, bool | None]:
    """Real, known made-cut fact as of HITEJINRO's own real cut (after
    R2, same single-cut shape round_update_r2/r3 assume) -- True for a
    real active player, False for a real, confirmed R2_CUT player, and
    None (genuinely unknown/not applicable -- R1_CUT/WD/DQ/DNS) for
    everyone else; those are excluded from simulation anyway via their
    real missing r2_score, never via a guessed made_cut value."""
    made_cut: dict[str, bool | None] = {}
    for r in board["records"]:
        pid = str(r["player_id"])
        status = r.get("status")
        if status is None:
            made_cut[pid] = True
        elif status == "R2_CUT":
            made_cut[pid] = False
        else:
            made_cut[pid] = None
    return made_cut


def build_hitejinro_post_r2_forecast(content_root: Path | None = None, *, n_simulations: int = 60000, seed: int = 20261001) -> dict:
    """하나금융과 동일한 Pipeline (NEO Verification Spec, 2026-10-03
    재지시: "비교 기준은 하나금융그룹 챔피언십이다... 새로운 로직을
    만들지 않는다"): 하나금융 scripts/159_build_hana_r2_forecast.py가
    실제로 호출하는 klpga.neo_win.round_update_r2.build_r2_sim_inputs_
    from_frozen_snapshot / simulate_post_round2를 그대로 import해서
    호출한다 -- 알고리즘을 다시 구현하지 않는다.

    하나금융 scripts/166_hana_post_r3_candidate_freeze.py가 추가로
    적용하는 real-SG-회귀계수 보정 단계는 이식하지 않는다: 그 계수는
    klpga.neo_win.current_sg_walk_forward의 실제 walk-forward 적합이
    필요하고, 이는 data/klpga.sqlite의 player_round가 이 환경에서 0행
    (재확인: current_sg_walk_forward.build_eligible_rows()가 실제
    historical_sg_warehouse.json 29,812행을 읽고도 eligible_rows=0을
    반환함)이라 하나금융 자신도 이 환경에서는 재현 불가능한 real
    제약이다 -- 날조하지 않고 PRE-only 베이스라인(하나금융 159 단계와
    동일)만 생성한다."""
    from klpga.neo_win.round_update_r2 import build_r2_sim_inputs_from_frozen_snapshot, simulate_post_round2

    content_root = content_root or CONTENT
    board = json.loads((content_root / f"{GAME_CODE}_LEADERBOARD.json").read_text(encoding="utf-8"))
    pre_snapshot = _hitejinro_frozen_snapshot()

    r1_scores = {str(r["player_id"]): r["r1_score"] - COURSE_PAR for r in board["records"] if r.get("r1_score") is not None}
    r2_scores = {str(r["player_id"]): r["r2_score"] - COURSE_PAR for r in board["records"] if r.get("r2_score") is not None}
    made_cut_by_player = _hitejinro_made_cut_by_player(board)

    sim_inputs, missing = build_r2_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores, r2_scores, made_cut_by_player)
    rng = random.Random(seed)
    result = simulate_post_round2(sim_inputs, remaining_rounds=2, n_simulations=n_simulations, rng=rng)

    records = []
    for inp in sim_inputs:
        if inp.player_code not in result:
            continue
        s = result[inp.player_code]
        records.append({
            "player_id": inp.player_code, "player_name": inp.player_name,
            "win_probability": s["win_pct"] / 100, "top5_probability": s["top5_pct"] / 100,
            "top10_probability": s["top10_pct"] / 100, "top20_probability": s["top20_pct"] / 100,
        })
    return {
        "artifact": "hitejinro_post_r2_final_forecast", "source_round": 2, "remaining_rounds": 2,
        "n_simulations": n_simulations, "seed": seed, "missing_players": missing,
        "simulation_engine": "klpga.neo_win.round_update_r2.simulate_post_round2 (same real call Hana's scripts/159 makes)",
        "sg_adjustment": "not applied -- real walk-forward fit unavailable in this environment (see docstring)",
        "records": records,
    }


def build_hitejinro_post_r3_forecast(content_root: Path | None = None, *, n_simulations: int = 60000, seed: int = 20261001) -> dict:
    """하나금융 scripts/170_hana_post_r4_final_forecast.py가 실제로
    호출하는 klpga.neo_win.round_update_r3.build_r3_sim_inputs_from_
    frozen_snapshot / simulate_post_round3를 그대로 호출한다. 하나금융
    170은 166의 SG-보정 expected를 그대로 재사용하지만(R3 자체의 새
    SG 항은 추가하지 않음), 이 환경에서는 166에 해당하는 SG-보정
    단계 자체가 real 데이터 제약으로 생성되지 않으므로(build_hitejinro_
    post_r2_forecast 참고) 동일한 PRE-only expected/spread를 그대로
    다시 사용한다 -- 하나금융의 '보정 없는 재사용' 원칙과 동일하게,
    이 함수도 R3 자체 SG로 새 항을 만들지 않는다."""
    from klpga.neo_win.round_update_r3 import build_r3_sim_inputs_from_frozen_snapshot, simulate_post_round3

    content_root = content_root or CONTENT
    board = json.loads((content_root / f"{GAME_CODE}_LEADERBOARD.json").read_text(encoding="utf-8"))
    pre_snapshot = _hitejinro_frozen_snapshot()

    r1_scores = {str(r["player_id"]): r["r1_score"] - COURSE_PAR for r in board["records"] if r.get("r1_score") is not None}
    r2_scores = {str(r["player_id"]): r["r2_score"] - COURSE_PAR for r in board["records"] if r.get("r2_score") is not None}
    r3_scores = {str(r["player_id"]): r["r3_score"] - COURSE_PAR for r in board["records"] if r.get("r3_score") is not None}
    made_cut_by_player = _hitejinro_made_cut_by_player(board)

    sim_inputs, missing = build_r3_sim_inputs_from_frozen_snapshot(pre_snapshot, r1_scores, r2_scores, r3_scores, made_cut_by_player)
    rng = random.Random(seed)
    result = simulate_post_round3(sim_inputs, n_simulations=n_simulations, rng=rng)

    records = []
    for inp in sim_inputs:
        if inp.player_code not in result or inp.made_cut is not True:
            continue
        s = result[inp.player_code]
        records.append({
            "player_id": inp.player_code, "player_name": inp.player_name,
            "win_probability": s["win_pct"] / 100, "top5_probability": s["top5_pct"] / 100,
            "top10_probability": s["top10_pct"] / 100, "top20_probability": s["top20_pct"] / 100,
        })
    return {
        "artifact": "hitejinro_post_r4_final_preview", "source_round": 3, "remaining_rounds": 1,
        "n_simulations": n_simulations, "seed": seed, "missing_players": missing,
        "simulation_engine": "klpga.neo_win.round_update_r3.simulate_post_round3 (same real call Hana's scripts/170 makes)",
        "sg_adjustment": "not applied -- real walk-forward fit unavailable in this environment (see build_hitejinro_post_r2_forecast)",
        "records": records,
    }


def post_r1_forecast_path(content_root: Path | None = None) -> Path:
    return (content_root or CONTENT) / f"HITEJINRO_{GAME_CODE}_POST_R1_FORECAST.json"


def post_r2_forecast_path(content_root: Path | None = None) -> Path:
    return (content_root or CONTENT) / f"HITEJINRO_{GAME_CODE}_POST_R2_FORECAST.json"


def post_r3_forecast_path(content_root: Path | None = None) -> Path:
    return (content_root or CONTENT) / f"HITEJINRO_{GAME_CODE}_POST_R3_FORECAST.json"


def write_post_r1_forecast(content_root: Path | None = None) -> Path:
    """R1's own dedicated, persisted forecast file -- so R1's page reads
    ONLY this one file, never the raw PRE path directly (NEO Verification
    Spec, 2026-10-03: "R1 페이지는 POST_R1_FORECAST만 읽는다"). Confirmed
    by exhaustive investigation: Hana has no round_update_r1/post_r1_
    forecast module anywhere in this repository -- round_update_r2
    itself REQUIRES real R1+R2 known scores as input, so it structurally
    cannot produce an R1-only forecast. R1's real forecast is therefore
    the frozen PRE M4 model itself (scripts/193_build_hitejinro_pre_m4.py),
    persisted here UNCHANGED under its own R1-specific filename -- never
    a new model, just this round's own copy of the one real forecast
    that exists before R2 happens."""
    from klpga.neo_win.hitejinro_player_metrics import M4_CANDIDATE_PATH, load_m4_by_id
    content_root = content_root or CONTENT
    m4 = load_m4_by_id()
    records = [
        {
            "player_id": pid, "player_name": rec["playerName"],
            "win_probability": rec["win_probability"], "top5_probability": rec["top5_probability"],
            "top10_probability": rec["top10_probability"], "top20_probability": rec["top20_probability"],
            "cut_probability": rec["cut_probability"],
        }
        for pid, rec in m4.items()
    ]
    out = {
        "artifact": "hitejinro_post_r1_forecast", "game_code": GAME_CODE, "source_round": 1,
        "source_model": "frozen PRE M4 -- no round_update_r1 module exists in this codebase (confirmed 2026-10-03); see this function's own docstring",
        "source_file": str(M4_CANDIDATE_PATH.relative_to(_ROOT.parent)),
        "records": records,
    }
    path = post_r1_forecast_path(content_root)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_post_r2_forecast(content_root: Path | None = None, **kwargs) -> Path:
    """Persists build_hitejinro_post_r2_forecast's real output (klpga.
    neo_win.round_update_r2.simulate_post_round2, the same real engine
    Hana's scripts/159 uses) to its own dedicated file -- R2's page
    reads ONLY this file."""
    content_root = content_root or CONTENT
    doc = build_hitejinro_post_r2_forecast(content_root=content_root, **kwargs)
    path = post_r2_forecast_path(content_root)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_post_r3_forecast(content_root: Path | None = None, **kwargs) -> Path:
    """Persists build_hitejinro_post_r3_forecast's real output (klpga.
    neo_win.round_update_r3.simulate_post_round3, the same real engine
    Hana's scripts/170 uses) to its own dedicated file -- R3's page
    reads ONLY this file."""
    content_root = content_root or CONTENT
    doc = build_hitejinro_post_r3_forecast(content_root=content_root, **kwargs)
    path = post_r3_forecast_path(content_root)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_post_r1_forecast(content_root: Path | None = None) -> dict:
    return json.loads(post_r1_forecast_path(content_root).read_text(encoding="utf-8"))


def load_post_r2_forecast(content_root: Path | None = None) -> dict:
    return json.loads(post_r2_forecast_path(content_root).read_text(encoding="utf-8"))


def load_post_r3_forecast(content_root: Path | None = None) -> dict:
    return json.loads(post_r3_forecast_path(content_root).read_text(encoding="utf-8"))


def _hitejinro_confirmed_outcome(round_number: int, *, content_root: Path | None = None) -> list[dict]:
    """Real end-of-round standing in the {"player_id", "player_name",
    "final_rank", "position_from", "position_to"} shape klpga.neo_win.
    final_partial_evidence_validator.compare_forecast_to_outcome/
    topk_set_comparison already expect (same real shape KB's own
    operator-confirmed FINAL evidence uses). Round 3 reads LEADERBOARD.
    json's own finish_position_numeric (the real field R3's page itself
    shows); R1/R2 re-parse their own raw leaderboard captures directly
    (same _LEADERBOARD_ROW_RE technique this module already uses for R2's
    real rank elsewhere)."""
    content_root = content_root or CONTENT
    if round_number in (3, 4):
        # FR (round 4) reads LEADERBOARD.json exactly like R3 -- same
        # real finish_position_numeric field, same status is None
        # filter (parse_leaderboard(4) populates it identically to
        # parse_leaderboard(3), just for the tournament's terminal
        # round instead of an intermediate one).
        board = json.loads((content_root / f"{GAME_CODE}_LEADERBOARD.json").read_text(encoding="utf-8"))
        return [
            {
                "player_id": str(r["player_id"]), "player_name": r["player_name"],
                "final_rank": str(r["finish_position_numeric"]),
                "position_from": r["finish_position_numeric"], "position_to": r["finish_position_numeric"],
            }
            for r in board["records"] if r.get("status") is None
        ]
    html = raw_evidence_path(round_number, "LEADERBOARD").read_text(encoding="utf-8")
    records = []
    for m in _LEADERBOARD_ROW_RE.finditer(html):
        pid, rank, name = m.group(1), m.group(2), m.group(3)
        if rank == "999":
            continue
        rank_int = int(rank)
        records.append({
            "player_id": pid, "player_name": name,
            "final_rank": rank, "position_from": rank_int, "position_to": rank_int,
        })
    return records


def _forecast_records_to_by_id(records: list[dict]) -> dict[str, dict]:
    """Reshapes build_hitejinro_post_r2_forecast/post_r3_forecast's own
    real records into the same {"neo_final_rank", "win_pct",
    "player_name"} shape."""
    ordered = sorted(records, key=lambda r: -r["win_probability"])
    return {
        r["player_id"]: {"neo_final_rank": i, "win_pct": r["win_probability"] * 100, "player_name": r["player_name"]}
        for i, r in enumerate(ordered, 1)
    }


def build_hitejinro_round_verification(round_number: int, *, content_root: Path | None = None):
    """NEO Verification Spec (2026-10-03, "final_real_page.py의 검증
    구조를 분석해 공통 Verification Engine으로 분리하고, R1~R3에서도
    현재 라운드 기준으로 호출한다"): calls klpga.neo_win.final_partial_
    evidence_validator.compare_forecast_to_outcome -- the exact engine
    extracted from KB's own real FINAL verification (topk_set_
    comparison's Top20/Top10/Top5 set precision/recall, winner-hit/
    log-loss/Brier/reciprocal-rank, rank_delta/biggest_movers) -- with
    each round's own real, NON-LEAKING forecast-vs-outcome pair instead
    of R3-forecast-vs-FINAL:
      - R1/R2: the static PRE M4 forecast (no later forecast exists
        before these rounds in Hana's own real architecture either,
        confirmed by direct investigation -- round_update_r2 itself
        requires real R1+R2 scores as its known-round input, so it
        cannot predict R2 without already knowing R2) vs that round's
        real end-of-round standing.
      - R3: the real post-R2 forecast (klpga.neo_win.round_update_r2.
        simulate_post_round2, built from real R1+R2 only -- never
        leaks R3's own score) vs R3's real standing. Exactly mirrors
        KB's own R3-forecast-vs-FINAL pattern, one stage earlier.
      - FR: the real post-R3 forecast (klpga.neo_win.round_update_r3.
        simulate_post_round3, built from real R1+R2+R3 only -- never
        leaks FR's own score) vs FR's real final standing. This is
        hitejinro's own exact analogue of KB's actual FINAL verification
        (KB's real FINAL closure compared its post-R3 forecast to its
        real FINAL result via this same compare_forecast_to_outcome
        engine -- see scripts/130_kb_2026090003_extended_final_
        comparison.py)."""
    content_root = content_root or CONTENT
    from klpga.neo_win.final_partial_evidence_validator import compare_forecast_to_outcome

    confirmed = _hitejinro_confirmed_outcome(round_number, content_root=content_root)
    # Reads the persisted POST_R1/POST_R2/POST_R3_FORECAST.json files
    # (never recomputes inline) -- the prior stage's file in every
    # case, since verifying round N against a forecast that already
    # KNOWS round N's own real score would be circular/leaking: R1/R2
    # both check against POST_R1_FORECAST (the only real forecast that
    # exists before R2 happens), R3 checks against POST_R2_FORECAST,
    # FR checks against POST_R3_FORECAST.
    if round_number in (1, 2):
        forecast_by_id = _forecast_records_to_by_id(load_post_r1_forecast(content_root)["records"])
    elif round_number == 3:
        forecast_by_id = _forecast_records_to_by_id(load_post_r2_forecast(content_root)["records"])
    else:
        forecast_by_id = _forecast_records_to_by_id(load_post_r3_forecast(content_root)["records"])

    # A real player absent from the forecast (e.g. DATA_INSUFFICIENT,
    # excluded from load_m4_by_id's PASS-only filter) cannot be scored
    # against a prediction that doesn't exist for them -- excluded here,
    # same "missing, never guessed" convention this codebase already
    # applies everywhere else (round_update_r2's own missing_r2_players).
    # topk_set_comparison's own _positions_gapless_through check already
    # and correctly reports supported=False for any k a resulting gap
    # affects -- never silently patched over.
    confirmed = [r for r in confirmed if r["player_id"] in forecast_by_id]

    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    return compare_forecast_to_outcome(
        forecast_by_id, confirmed,
        target_event_id=GAME_CODE, target_game_code=GAME_CODE, target_start_date=tourney["start_date"],
    )


def build_round_page(round_number: int, *, include_internal: bool = False) -> Path:
    """Render and write this round's public page (docs/tournaments/
    2026/{GAME_CODE}/{r1,r2,r3,fr}/index.html) via the one shared
    renderer, klpga.neo_win.hitejinro_round_page.render_round_page --
    extracted from scripts/196-199_build_hitejinro_r*_page.py, which
    each duplicated the same five lines (load TOURNAMENT_INFO, format
    date_range, render, write) differing only in round_number and
    output path. Those four scripts now call this function instead
    (always with the default include_internal=False, the real public
    build).

    PUBLIC/INTERNAL SPLIT (2026-10-03, "R3 페이지는 공개 페이지다...
    R3 리더보드까지만 출력한다... 데이터와 JSON은 그대로 유지하고 공개
    HTML에서만 숨긴다"): the real leaderboard table (this function's
    own render_round_page call) is ALWAYS public, unchanged. The NEO
    Verification section (build_hitejinro_round_verification -- the
    same engine klpga.neo_win.final_real_page/final_partial_evidence_
    validator already use for KB's FINAL page) is only spliced in when
    include_internal=True -- never written to docs/ (the deployed,
    public tree) by the real public build path. Nothing is deleted:
    every build_hitejinro_* function, every POST_R{n}_FORECAST.json
    file, still exists and still computes/persists the real data
    exactly as before; only the PUBLIC HTML assembly stops including
    it by default. See build_hitejinro_internal_report (scripts/
    operator-only entry point) for the include_internal=True path."""
    stage_key, _label = STAGE_LABELS[round_number]
    repo_root = _ROOT.parent
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    if round_number == 1:
        write_post_r1_forecast(content_root=CONTENT)
    elif round_number == 2:
        write_post_r2_forecast(content_root=CONTENT)
    elif round_number == 3:
        write_post_r3_forecast(content_root=CONTENT)
    html = render_round_page(
        round_number, tournament_name=tourney["event_name"], date_range=date_range, content_root=CONTENT,
    )
    # 2026-10-03: operator-supplied homepage video, same real component
    # Hana's own FINAL page already uses (klpga.neo_win.final_real_page.
    # render_final_video_section, reused unmodified) -- spliced right
    # after stage-nav, before the leaderboard panel, same position
    # Hana's page places it. Public content (not internal analytics),
    # so always included regardless of include_internal. HOME mirrors
    # this page's <main> verbatim (scripts/192), so the video reaches
    # the home screen too. 2026-10-04: FR gets its own, separate video
    # asset/path (neo-golf-data-fr.mp4) -- never overwrites R3's own
    # already-published neo-golf-data-home.mp4, so R3's own page keeps
    # showing its own real video unchanged.
    _ROUND_VIDEO_ASSET = {3: "neo-golf-data-home.mp4", 4: "neo-golf-data-fr.mp4"}
    if round_number in _ROUND_VIDEO_ASSET:
        video_path = _ROOT.parent / "docs" / "assets" / "tournaments" / GAME_CODE / _ROUND_VIDEO_ASSET[round_number]
        if video_path.is_file():
            from klpga.neo_win.final_real_page import render_final_video_section
            video_html = render_final_video_section(
                video_src=f"/assets/tournaments/{GAME_CODE}/{_ROUND_VIDEO_ASSET[round_number]}",
                caption="NEO GOLF DATA",
            )
            assert "</ol></nav><section class='panel leaderboard-panel'" in html
            html = html.replace(
                "</ol></nav><section class='panel leaderboard-panel'",
                "</ol></nav>" + video_html + "<section class='panel leaderboard-panel'",
            )
    if include_internal and round_number in (1, 2, 3, 4):
        from klpga.neo_win.hitejinro_round_page import render_hitejinro_verification_html
        verification = build_hitejinro_round_verification(round_number)
        assert "</main>" in html
        html = html.replace("</main>", render_hitejinro_verification_html(round_number, verification) + "</main>")
    if include_internal and round_number == 4:
        # FR/FINAL closure policy (2026-10-04, this tournament's own
        # analogue of KB 2026090003's real public FINAL-page NEO
        # verification, scripts/130-131_kb_2026090003_*): unlike R1-R3
        # (2026-10-03 PUBLIC/INTERNAL SPLIT, still unchanged -- these
        # stay internal-only), the terminal FR stage also gets SG 분석
        # + 코스 분석 spliced into the PUBLIC page, same real functions/
        # markup R3's own internal report already used. No new
        # verification method, only a different stage's own public/
        # internal default (set by run_round_pipeline.py's caller, not
        # here).
        from klpga.neo_win.hitejinro_round_page import render_r3_course_analysis_html, render_r3_sg_intelligence_html
        sg_html = render_r3_sg_intelligence_html(build_r3_sg_intelligence(round_number=4))
        course_html = render_r3_course_analysis_html(build_r3_course_analysis(round_number=4))
        html = html.replace("</main>", sg_html + course_html + "</main>")
    out_path = repo_root / "docs" / "tournaments" / "2026" / GAME_CODE / stage_key / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path


def build_r3_results_page(*, include_internal: bool = False) -> Path:
    """R3's own PUBLIC page: build_round_page(3, include_internal=
    include_internal) -- the real leaderboard table, always public,
    unchanged. PUBLIC/INTERNAL SPLIT (2026-10-03, "R3 페이지는 공개
    페이지다. R3 리더보드 아래의 모든 내부 자료를 숨긴다... R3
    리더보드까지만 출력한다... 내부 자료는 삭제하지 않는다. Renderer에서
    비공개 처리하고, 운영자 모드에서만 출력 가능하도록 유지한다"): SG
    분석/코스 분석 (and, via build_round_page, NEO 검증) are only
    spliced in when include_internal=True -- the real public build
    (scripts, this function's own default) never writes them to
    docs/. Nothing is deleted: build_r3_sg_intelligence/build_r3_
    course_analysis/build_hitejinro_round_verification and every
    POST_R{n}_FORECAST.json file still compute and persist the exact
    same real data; only whether the PUBLIC HTML includes them changed.
    See build_hitejinro_internal_report for the operator-only
    include_internal=True entry point (writes to internal_output/,
    never to docs/)."""
    out_path = build_round_page(3, include_internal=include_internal)
    if not include_internal:
        return out_path

    from klpga.neo_win.hitejinro_round_page import (
        render_r3_course_analysis_html,
        render_r3_sg_intelligence_html,
    )

    html = out_path.read_text(encoding="utf-8")
    sections_html = (
        render_r3_sg_intelligence_html(build_r3_sg_intelligence())
        + render_r3_course_analysis_html(build_r3_course_analysis())
    )
    assert "</main>" in html
    html = html.replace("</main>", sections_html + "</main>")
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path


def build_hitejinro_internal_report(round_number: int = 3, *, out_dir: Path | None = None) -> Path:
    """Operator/Admin-only entry point (2026-10-03 PUBLIC/INTERNAL
    SPLIT): the FULL internal page (real leaderboard + NEO 검증 + SG
    분석 + 코스 분석, round_number 3's complete set) rendered to a
    file OUTSIDE docs/ (internal_output/, gitignored-equivalent --
    never deployed, never linked from the public site) so an operator
    can inspect every internal section without it ever reaching the
    live, public GitHub Pages build. Reuses every real build_* function
    unchanged -- this is assembly only, never a new computation."""
    from klpga.neo_win.hitejinro_round_page import (
        render_hitejinro_verification_html,
        render_r3_course_analysis_html,
        render_r3_sg_intelligence_html,
    )

    out_dir = out_dir or (_ROOT / "internal_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    stage_key, _label = STAGE_LABELS[round_number]
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    if round_number == 1:
        write_post_r1_forecast(content_root=CONTENT)
    elif round_number == 2:
        write_post_r2_forecast(content_root=CONTENT)
    elif round_number == 3:
        write_post_r3_forecast(content_root=CONTENT)
    html = render_round_page(
        round_number, tournament_name=tourney["event_name"], date_range=date_range, content_root=CONTENT,
    )
    sections_html = render_hitejinro_verification_html(round_number, build_hitejinro_round_verification(round_number))
    if round_number == 3:
        sections_html += (
            render_r3_sg_intelligence_html(build_r3_sg_intelligence())
            + render_r3_course_analysis_html(build_r3_course_analysis())
        )
    assert "</main>" in html
    html = html.replace("</main>", sections_html + "</main>")

    out_path = out_dir / f"{GAME_CODE}_{stage_key}_internal.html"
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path


def build_in_progress_round_page(
    round_number: int, *, raw_path: Path | None = None, show_hole_progress: bool = True,
) -> Path:
    """Render and write this round's public page from a LIVE, round-
    in-progress capture (the "R2 START" case) instead of a completed-
    round one -- parse_in_progress_state() supplies the real per-player
    state (excluded/hole/score), render_round_page's own in_progress
    parameter renders it using round_number-1's already-completed
    roster/ranking ("R1 종료 기준 그대로 사용"). Same output path as
    build_round_page(); once round_number genuinely finishes, re-run
    build_round_page(round_number) (after parse_leaderboard/parse_sg/
    cross_validate/merge_sg_into_warehouse) to replace this with the
    real completed-round page -- this function never claims a round is
    complete. show_hole_progress is passed straight through to
    render_round_page -- see that function's own docstring."""
    stage_key, _label = STAGE_LABELS[round_number]
    repo_root = _ROOT.parent
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    start, end = tourney["start_date"], tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    state = parse_in_progress_state(round_number, raw_path=raw_path)
    html = render_round_page(
        round_number, tournament_name=tourney["event_name"], date_range=date_range, content_root=CONTENT,
        in_progress=state, show_hole_progress=show_hole_progress,
    )
    out_path = repo_root / "docs" / "tournaments" / "2026" / GAME_CODE / stage_key / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8", newline="\n")
    return out_path

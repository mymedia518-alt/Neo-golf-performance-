"""Tests for klpga.discovery.identity_key_audit — Round 10 continued
(the "canonical metric identity vs HTTP request identity" audit), plus
Round 11 continued's `CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED` addition.
Mostly offline against synthetic taxonomy/raw-response fixtures; a few
tests near the end additionally pin against the REAL evidence
transferred into `docs/discovery/raw_samples/` this round (the first
real KLPGA raw responses this repo has ever had) for the strongest
possible regression pin."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.identity_key_audit import (
    CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED,
    CATEGORY_CONTAINER_CHILD,
    CATEGORY_EMPTY_SHARED_RESPONSE,
    CATEGORY_EXACT_DUPLICATE,
    CATEGORY_INSUFFICIENT_EVIDENCE,
    CATEGORY_MULTI_METRIC_CONFIRMED,
    CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW,
    CATEGORY_UNRESOLVED,
    _extract_menu_name,
    _resolve_via_compound_menu_title,
    audit_identity_key_collisions,
    derive_request_identity_key,
)

REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


def _leaf(menu1, menu2, menu3, leaf_level, label):
    return {
        "menu1": menu1,
        "menu1_label": menu1,
        "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3,
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else ""),
    }


def _table_response_html(column_labels: list[str]) -> str:
    """A minimal real-shape response with N labeled columns via the
    table_header fallback layer — one data row, record/record1.../
    record<N-2> fields (first two <th> are rank/name, unused by the
    parser's record_fields discovery)."""
    ths = "".join(f"<th>{label}</th>" for label in column_labels)
    record_attrs = " ".join(
        f'data-record{"" if i == 0 else i}="{i + 1}"' for i in range(len(column_labels) - 2)
    )
    tds = "".join(f"<td>{i}</td>" for i in range(len(column_labels)))
    return f"""
    <table>
      <thead><tr>{ths}</tr></thead>
      <tbody><tr data-rank="1" data-name="테스트" {record_attrs}>{tds}</tr></tbody>
    </table>
    """


def _empty_response_html() -> str:
    return "<html><body><table><thead><tr><th></th></tr></thead><tbody></tbody></table></body></html>"


def test_derive_request_identity_key_menu3_level():
    entry = {"menu1": "Tee", "menu2": "Tee01", "menu3": "010101", "leaf_level": "menu3"}
    assert derive_request_identity_key(entry) == "Tee::Tee01::010101"


def test_derive_request_identity_key_menu2_level_omits_menu3():
    entry = {"menu1": "Sg", "menu2": "Total", "menu3": None, "leaf_level": "menu2"}
    assert derive_request_identity_key(entry) == "Sg::Total"


def test_non_colliding_identities_are_excluded_from_the_audit(tmp_path):
    taxonomy = {"leaves": [_leaf("Sg", "Total", None, "menu2", "SG : 전체")]}
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert audits == []


def test_near_duplicate_labels_classified_as_exact_duplicate_without_needing_a_raw_sample(tmp_path):
    """Whitespace/case-only label differences — checked BEFORE any
    raw-response lookup, so this must classify correctly even when no
    raw sample exists at all."""
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt01", "040101", "menu3", "1퍼트 성공률"),
            _leaf("Putt", "Putt01", "040101", "menu3", "1퍼트  성공률"),  # double space
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].category == CATEGORY_EXACT_DUPLICATE
    assert audits[0].request_identity_key == "Putt::Putt01::040101"


def test_no_raw_sample_classified_as_insufficient_evidence(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].category == CATEGORY_INSUFFICIENT_EVIDENCE
    # Round 10 diagnostic follow-up: raw_sample_path is now the EXPECTED
    # (not-yet-existing) path, so scripts/31's MISSING_EVIDENCE_IDENTITIES
    # section can print it directly without re-deriving it.
    expected_path = tmp_path / "Tee__Tee01__010101__2025.html"
    assert audits[0].raw_sample_path == str(expected_path)
    assert not expected_path.exists()


def test_empty_saved_response_classified_as_empty_shared_response(tmp_path):
    """The confirmed Sg::All shape: a saved response exists but has
    zero rows and no labeled columns."""
    taxonomy = {
        "leaves": [
            _leaf("Sg", "All", None, "menu2", "Strokes Gained"),
            _leaf("Sg", "All", None, "menu2", "전체"),
        ]
    }
    (tmp_path / "Sg__All__2025.html").write_text(_empty_response_html(), encoding="utf-8")
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].category == CATEGORY_EMPTY_SHARED_RESPONSE


def test_all_labels_matched_classified_as_multi_metric_confirmed(tmp_path):
    """The confirmed Around::Around04::030306 shape: every canonical
    label mapped to this identity matches a distinct response column."""
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around04", "030306", "menu3", "평균 남은 거리"),
            _leaf("Around", "Around04", "030306", "menu3", "전체 남은 거리"),
            _leaf("Around", "Around04", "030306", "menu3", "스크램블링수"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 남은 거리", "전체 남은 거리", "스크램블링수"])
    (tmp_path / "Around__Around04__030306__2025.html").write_text(html, encoding="utf-8")
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_MULTI_METRIC_CONFIRMED
    assert set(a.matched_labels) == {"평균 남은 거리", "전체 남은 거리", "스크램블링수"}
    assert a.unmatched_labels == []


def test_no_labels_matched_classified_as_unresolved(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee02", "010102", "menu3", "완전히 다른 라벨 A"),
            _leaf("Tee", "Tee02", "010102", "menu3", "완전히 다른 라벨 B"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "무관한 컬럼1", "무관한 컬럼2"])
    (tmp_path / "Tee__Tee02__010102__2025.html").write_text(html, encoding="utf-8")
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].category == CATEGORY_UNRESOLVED
    assert audits[0].matched_labels == []


def test_some_labels_matched_classified_as_partial_match_needs_review(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt02", "040201", "menu3", "성공률"),
            _leaf("Putt", "Putt02", "040201", "menu3", "퍼팅"),  # generic/parent-looking label
        ]
    }
    html = _table_response_html(["순위", "선수명", "성공률"])
    (tmp_path / "Putt__Putt02__040201__2025.html").write_text(html, encoding="utf-8")
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW
    assert a.matched_labels == ["성공률"]
    assert a.unmatched_labels == ["퍼팅"]


def test_multiple_independent_groups_classified_independently(tmp_path):
    """Two separate colliding groups in the same taxonomy — each
    audited on its own evidence, never conflated."""
    taxonomy = {
        "leaves": [
            _leaf("Sg", "All", None, "menu2", "Strokes Gained"),
            _leaf("Sg", "All", None, "menu2", "전체"),
            _leaf("Around", "Around04", "030306", "menu3", "평균 남은 거리"),
            _leaf("Around", "Around04", "030306", "menu3", "스크램블링수"),
        ]
    }
    (tmp_path / "Sg__All__2025.html").write_text(_empty_response_html(), encoding="utf-8")
    html = _table_response_html(["순위", "선수명", "평균 남은 거리", "스크램블링수"])
    (tmp_path / "Around__Around04__030306__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    by_key = {a.request_identity_key: a for a in audits}
    assert len(audits) == 2
    assert by_key["Sg::All"].category == CATEGORY_EMPTY_SHARED_RESPONSE
    assert by_key["Around::Around04::030306"].category == CATEGORY_MULTI_METRIC_CONFIRMED


# ---------------------------------------------------------------
# Real evidence, pasted directly by the user (docs/KLPGA_OFFICIAL_
# DATA_MAP.md's Round 10 section): the FIRST version of this matcher
# (exact-normalized-equality only) misclassified BOTH of these real
# groups as D_UNRESOLVED, because response column labels carry a
# trailing "(yds)"/"(%)" annotation the taxonomy labels don't, and
# because short generic family labels ("티샷", "퍼팅") don't equal any
# single column's full text. These tests pin the corrected behavior
# against the exact real label text reported.
# ---------------------------------------------------------------


def test_real_tee_evidence_partial_match_one_genuinely_unmatched_label(tmp_path):
    """Real evidence for Tee::Tee01::010101. "평균 티샷 거리" matches
    "평균 티샷 거리(yds)" once the trailing unit annotation is
    stripped; "티샷" is a container-candidate (substring-matches all
    3 columns); "Par4,5 티샷 비율" has NO textual relationship to
    "Par4,5 티샷 횟수" (differs in its final word, rate vs count) and
    must stay genuinely unresolved rather than be silently matched."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
            _leaf("Tee", "Tee01", "010101", "menu3", "티샷"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)", "티샷 거리 총 합(yds)", "Par4,5 티샷 횟수"])
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW
    assert a.matched_labels == ["평균 티샷 거리"]
    assert a.container_candidate_labels == ["티샷"]
    assert a.unmatched_labels == ["Par4,5 티샷 비율"]


def test_real_putt_evidence_container_child_fully_resolved(tmp_path):
    """Real evidence for Putt::Putt01::040101. "1퍼트 성공률" matches
    "성공률(%)" via substring after stripping "(%)"; "퍼팅" is a
    container-candidate (substring of "퍼팅 시도 홀 수", 2 chars,
    below the minimum confirmed-match length). Both labels resolve —
    one confirmed match plus one container/generic label — so the
    WHOLE group classifies as B, not left as partial."""
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt01", "040101", "menu3", "1퍼트 성공률"),
            _leaf("Putt", "Putt01", "040101", "menu3", "퍼팅"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "성공률(%)", "1퍼트 성공 홀 수", "퍼팅 시도 홀 수"])
    (tmp_path / "Putt__Putt01__040101__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_CONTAINER_CHILD
    assert a.matched_labels == ["1퍼트 성공률"]
    assert a.container_candidate_labels == ["퍼팅"]
    assert a.unmatched_labels == []


def test_trailing_unit_annotation_alone_yields_exact_match_after_normalization(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee09", "010901", "menu3", "평균 드라이브 거리"),
            _leaf("Tee", "Tee09", "010901", "menu3", "장타율"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 드라이브 거리(yds)", "장타율(%)"])
    (tmp_path / "Tee__Tee09__010901__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].category == CATEGORY_MULTI_METRIC_CONFIRMED
    assert set(audits[0].matched_labels) == {"평균 드라이브 거리", "장타율"}


def test_match_details_record_the_specific_response_column_and_method(tmp_path):
    """Round 10 diagnostic follow-up: a confirmed match must record
    WHICH response column it resolved against and HOW (exact vs
    substring) — not just that some match occurred — so scripts/31's
    diagnostic output can print "label -> column [method]" directly
    from already-loaded evidence."""
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt01", "040101", "menu3", "1퍼트 성공률"),
            _leaf("Putt", "Putt01", "040101", "menu3", "퍼팅"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "성공률(%)", "1퍼트 성공 홀 수", "퍼팅 시도 홀 수"])
    (tmp_path / "Putt__Putt01__040101__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    details = audits[0].match_details
    assert len(details) == 1
    assert details[0].taxonomy_label == "1퍼트 성공률"
    assert details[0].response_column == "성공률(%)"
    assert details[0].method == "substring"


def test_real_putt02_evidence_internal_whitespace_difference_now_matches(tmp_path):
    """Real evidence for Putt::Putt02::040201: the taxonomy label
    "평균 퍼트수" (no internal space) and the response column
    "평균 퍼트 수" (with an internal space before "수") are the SAME
    label written with inconsistent Korean compound-noun spacing —
    previously classified D_UNRESOLVED because the old normalizer only
    collapsed repeated whitespace, never removed it. Must now resolve
    as an exact match once all whitespace is stripped."""
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt02", "040201", "menu3", "평균 퍼트수"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 퍼트 수"])
    (tmp_path / "Putt__Putt02__040201__2025.html").write_text(html, encoding="utf-8")

    # A single-label "group" isn't a collision by itself; pair it with
    # an unrelated second label so the identity still qualifies as a
    # collision group and we can observe the specific label's outcome.
    taxonomy["leaves"].append(_leaf("Putt", "Putt02", "040201", "menu3", "완전히 무관한 라벨"))

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert "평균 퍼트수" in a.matched_labels
    detail = next(d for d in a.match_details if d.taxonomy_label == "평균 퍼트수")
    assert detail.response_column == "평균 퍼트 수"
    assert detail.method == "exact"


def test_whitespace_normalization_does_not_merge_different_meaning_words(tmp_path):
    """The same fix must NOT resolve Tee::Tee01::010101's real
    "Par4,5 티샷 비율" (rate) vs "Par4,5 티샷 횟수" (count) case — they
    differ by an actual character (비율 vs 횟수), not by whitespace, so
    removing whitespace must leave them exactly as unrelated as
    before."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        ]
    }
    html = _table_response_html(["순위", "선수명", "평균 티샷 거리(yds)", "Par4,5 티샷 횟수"])
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    assert audits[0].unmatched_labels == ["Par4,5 티샷 비율"]


# ---------------------------------------------------------------
# CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED (Round 11 continued) —
# discovered from the first real, bulk raw-evidence set this project
# has ever had: `var menuName = "...";` in a real response is, for 13
# of the 15 previously-unresolved groups, EXACTLY two of that group's
# own taxonomy labels joined by " - ". See the category's own
# docstring in identity_key_audit.py for the full real-evidence log.
# ---------------------------------------------------------------


def test_extract_menu_name_finds_the_top_level_var():
    html = '<script>var menuName = "그린 적중 시 남은 거리 - 평균 남은 거리";</script>'
    assert _extract_menu_name(html) == "그린 적중 시 남은 거리 - 평균 남은 거리"


def test_extract_menu_name_returns_none_when_absent():
    assert _extract_menu_name("<html><body>no menu name here</body></html>") is None


def test_resolve_via_compound_menu_title_pairs_unmatched_with_matched_label():
    still_unmatched, confirmed, pairs = _resolve_via_compound_menu_title(
        unmatched=["그린 적중 시 남은 거리"],
        all_labels=["그린 적중 시 남은 거리", "평균 남은 거리"],
        menu_name="그린 적중 시 남은 거리 - 평균 남은 거리",
    )
    assert still_unmatched == []
    assert confirmed == ["그린 적중 시 남은 거리"]
    assert pairs == [("그린 적중 시 남은 거리", "평균 남은 거리")]


def test_resolve_via_compound_menu_title_pairs_two_mutually_unmatched_labels():
    """The real Around::Around05::030401 shape: BOTH labels are
    unmatched against any response column, but menuName is exactly
    those two labels joined by " - " — they resolve against EACH
    OTHER, not against some third, already-matched label."""
    still_unmatched, confirmed, pairs = _resolve_via_compound_menu_title(
        unmatched=["그린 주변 샷 후 남은 거리", "60야드 미만"],
        all_labels=["그린 주변 샷 후 남은 거리", "60야드 미만"],
        menu_name="그린 주변 샷 후 남은 거리 - 60야드 미만",
    )
    assert still_unmatched == []
    assert set(confirmed) == {"그린 주변 샷 후 남은 거리", "60야드 미만"}
    assert set(pairs) == {("그린 주변 샷 후 남은 거리", "60야드 미만"), ("60야드 미만", "그린 주변 샷 후 남은 거리")}


def test_resolve_via_compound_menu_title_leaves_unrelated_label_unmatched():
    """The real Around::Around01::030101 shape: menuName exists but
    does NOT contain the unmatched label at all — must not force a
    match that isn't there."""
    still_unmatched, confirmed, pairs = _resolve_via_compound_menu_title(
        unmatched=["그린주변"],
        all_labels=["그린주변", "샌드 세이브율"],
        menu_name="샌드 세이브율 - 샌드 세이브율",
    )
    assert still_unmatched == ["그린주변"]
    assert confirmed == []
    assert pairs == []


def test_resolve_via_compound_menu_title_no_menu_name_leaves_unchanged():
    still_unmatched, confirmed, pairs = _resolve_via_compound_menu_title(
        unmatched=["아무 라벨"], all_labels=["아무 라벨", "다른 라벨"], menu_name=None
    )
    assert still_unmatched == ["아무 라벨"]
    assert confirmed == []
    assert pairs == []


def _table_response_html_with_menu_name(column_labels: list[str], menu_name: str) -> str:
    ths = "".join(f"<th>{label}</th>" for label in column_labels)
    record_attrs = " ".join(
        f'data-record{"" if i == 0 else i}="{i + 1}"' for i in range(len(column_labels) - 2)
    )
    tds = "".join(f"<td>{i}</td>" for i in range(len(column_labels)))
    return f"""
    <script>var menuName = "{menu_name}";</script>
    <table>
      <thead><tr>{ths}</tr></thead>
      <tbody><tr data-rank="1" data-name="테스트" {record_attrs}>{tds}</tr></tbody>
    </table>
    """


def test_compound_menu_title_confirmed_classification_synthetic(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Approach", "Approach02", "020201", "menu3", "그린 적중 시 남은 거리"),
            _leaf("Approach", "Approach02", "020201", "menu3", "평균 남은 거리"),
        ]
    }
    html = _table_response_html_with_menu_name(
        ["순위", "선수명", "평균 남은 거리(yds)", "전체 남은 거리(yds)"],
        "그린 적중 시 남은 거리 - 평균 남은 거리",
    )
    (tmp_path / "Approach__Approach02__020201__2025.html").write_text(html, encoding="utf-8")

    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED
    assert a.unmatched_labels == []
    assert a.compound_title_confirmed_labels == ["그린 적중 시 남은 거리"]
    assert a.compound_title_pairs == [("그린 적중 시 남은 거리", "평균 남은 거리")]


def test_real_approach02_evidence_resolves_via_compound_menu_title():
    """Pinned to the REAL Approach::Approach02::020201 raw response —
    the exact case that surfaced this category: previously
    PARTIAL_MATCH_NEEDS_REVIEW (only "평균 남은 거리" matched a response
    column), now resolved because the response's own real menuName is
    literally "그린 적중 시 남은 거리 - 평균 남은 거리"."""
    taxonomy = {
        "leaves": [
            _leaf("Approach", "Approach02", "020201", "menu3", "그린 적중 시 남은 거리"),
            _leaf("Approach", "Approach02", "020201", "menu3", "평균 남은 거리"),
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED
    assert a.compound_title_confirmed_labels == ["그린 적중 시 남은 거리"]


def test_real_around05_evidence_both_labels_resolve_via_compound_menu_title():
    """Pinned to the REAL Around::Around05::030401 raw response — the
    one group that was D_UNRESOLVED_REQUEST_IDENTITY_COLLISION (NEITHER
    label matched any response column) before this round; now resolved
    since both labels together form the real menuName."""
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around05", "030401", "menu3", "그린 주변 샷 후 남은 거리"),
            _leaf("Around", "Around05", "030401", "menu3", "60야드 미만"),
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED
    assert set(a.compound_title_confirmed_labels) == {"그린 주변 샷 후 남은 거리", "60야드 미만"}


def test_real_around01_evidence_remains_genuinely_unresolved():
    """Negative pin: proves this round's fix does NOT force every
    remaining group to resolve. Around::Around01::030101's real
    menuName is "샌드 세이브율 - 샌드 세이브율" — it never mentions the
    unmatched label "그린주변" at all, so this must stay
    PARTIAL_MATCH_NEEDS_REVIEW, exactly as the real audit output shows."""
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around01", "030101", "menu3", "그린주변"),
            _leaf("Around", "Around01", "030101", "menu3", "샌드 세이브율"),
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_PARTIAL_MATCH_NEEDS_REVIEW
    assert a.unmatched_labels == ["그린주변"]
    assert a.compound_title_confirmed_labels == []


def test_compound_title_priority_over_container_child_when_a_compound_title_label_present():
    """The real Tee::Tee01::010101 shape: 3 labels — "평균 티샷 거리"
    matches a response column, "티샷" is a container-candidate, and
    "Par4,5 티샷 비율" resolves via the compound-menuName mechanism
    (paired with "평균 티샷 거리"). The overall group category reflects
    the compound-title resolution."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "Par4,5 티샷 비율"),
            _leaf("Tee", "Tee01", "010101", "menu3", "티샷"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        ]
    }
    audits = audit_identity_key_collisions(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert len(audits) == 1
    a = audits[0]
    assert a.category == CATEGORY_COMPOUND_MENU_TITLE_CONFIRMED
    assert a.matched_labels == ["평균 티샷 거리"]
    assert a.container_candidate_labels == ["티샷"]
    assert a.compound_title_confirmed_labels == ["Par4,5 티샷 비율"]
    assert a.unmatched_labels == []

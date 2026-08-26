"""Tests for src/klpga/discovery/identity_mapping.py. Mostly offline
against synthetic fixtures; a few tests pin against the REAL,
committed docs/discovery/ evidence for the strongest regression pin."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.identity_mapping import (
    STATUS_COMPOUND_TITLE_COLUMN_UNCONFIRMED,
    STATUS_CONTAINER_LABEL,
    STATUS_EMPTY_RESPONSE,
    STATUS_MAPPED,
    STATUS_NEEDS_REVIEW,
    STATUS_PENDING_EVIDENCE,
    build_identity_metric_mapping,
)

REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
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


def _table_response_html_with_menu_name(column_labels: list[str], menu_name: str = "") -> str:
    ths = "".join(f"<th>{label}</th>" for label in column_labels)
    record_attrs = " ".join(
        f'data-record{"" if i == 0 else i}="{i + 1}"' for i in range(len(column_labels) - 2)
    )
    tds = "".join(f"<td>{i}</td>" for i in range(len(column_labels)))
    menu_script = f'<script>var menuName = "{menu_name}";</script>' if menu_name else ""
    return f"""
    {menu_script}
    <table>
      <thead><tr>{ths}</tr></thead>
      <tbody><tr data-rank="1" data-name="테스트" {record_attrs}>{tds}</tr></tbody>
    </table>
    """


def test_non_colliding_identity_no_evidence_is_pending(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee99", "010999", "menu3", "아무 라벨")]}
    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 1
    assert records[0].status == STATUS_PENDING_EVIDENCE
    assert records[0].field_name is None


def test_non_colliding_identity_exact_match_is_mapped(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee99", "010999", "menu3", "평균 드라이브 거리")]}
    html = _table_response_html_with_menu_name(["순위", "선수명", "평균 드라이브 거리(yds)"])
    (tmp_path / "Tee__Tee99__010999__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 1
    r = records[0]
    assert r.status == STATUS_MAPPED
    assert r.field_name == "record"
    assert r.response_column_label == "평균 드라이브 거리(yds)"
    assert r.match_method == "exact"


def test_non_colliding_identity_no_relationship_needs_review(tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee99", "010999", "menu3", "완전히 무관한 라벨")]}
    html = _table_response_html_with_menu_name(["순위", "선수명", "평균 드라이브 거리(yds)"])
    (tmp_path / "Tee__Tee99__010999__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert records[0].status == STATUS_NEEDS_REVIEW
    assert records[0].field_name is None


def test_colliding_group_compound_title_with_matched_partner_is_mapped(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Approach", "Approach99", "020999", "menu3", "그린 적중 시 남은 거리"),
            _leaf("Approach", "Approach99", "020999", "menu3", "평균 남은 거리"),
        ]
    }
    html = _table_response_html_with_menu_name(
        ["순위", "선수명", "평균 남은 거리(yds)", "전체 남은 거리(yds)"],
        menu_name="그린 적중 시 남은 거리 - 평균 남은 거리",
    )
    (tmp_path / "Approach__Approach99__020999__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 2
    by_label = {r.label: r for r in records}

    generic = by_label["평균 남은 거리"]
    assert generic.status == STATUS_MAPPED
    assert generic.field_name == "record"
    assert generic.match_method == "exact"

    context = by_label["그린 적중 시 남은 거리"]
    assert context.status == STATUS_MAPPED
    assert context.field_name == "record"  # SAME field as its paired label
    assert context.match_method == "compound_menu_title"
    assert context.paired_with_label == "평균 남은 거리"


def test_colliding_group_compound_title_both_unmatched_is_column_unconfirmed(tmp_path):
    """The real Around::Around05::030401 shape: both labels resolve
    against EACH OTHER via menuName, but neither independently matches
    a response column — must NOT guess which column carries the
    value."""
    taxonomy = {
        "leaves": [
            _leaf("Around", "Around99", "030999", "menu3", "그린 주변 샷 후 남은 거리"),
            _leaf("Around", "Around99", "030999", "menu3", "60야드 미만"),
        ]
    }
    html = _table_response_html_with_menu_name(
        ["순위", "선수명", "평균 남은 거리(yds)", "전체 남은 거리(yds)"],
        menu_name="그린 주변 샷 후 남은 거리 - 60야드 미만",
    )
    (tmp_path / "Around__Around99__030999__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 2
    for r in records:
        assert r.status == STATUS_COMPOUND_TITLE_COLUMN_UNCONFIRMED
        assert r.field_name is None


def test_colliding_group_container_label_is_unmapped_container(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Putt", "Putt99", "040999", "menu3", "1퍼트 성공률"),
            _leaf("Putt", "Putt99", "040999", "menu3", "퍼팅"),
        ]
    }
    html = _table_response_html_with_menu_name(["순위", "선수명", "성공률(%)", "1퍼트 성공 홀 수", "퍼팅 시도 홀 수"])
    (tmp_path / "Putt__Putt99__040999__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    by_label = {r.label: r for r in records}
    assert by_label["1퍼트 성공률"].status == STATUS_MAPPED
    assert by_label["퍼팅"].status == STATUS_CONTAINER_LABEL
    assert by_label["퍼팅"].field_name is None


def test_empty_shared_response_is_unmapped_empty(tmp_path):
    taxonomy = {
        "leaves": [
            _leaf("Sg", "All", None, "menu2", "Strokes Gained"),
            _leaf("Sg", "All", None, "menu2", "전체"),
        ]
    }
    (tmp_path / "Sg__All__2025.html").write_text(
        "<html><body><table><thead><tr><th></th></tr></thead><tbody></tbody></table></body></html>",
        encoding="utf-8",
    )
    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 2
    assert all(r.status == STATUS_EMPTY_RESPONSE for r in records)


def test_mixed_batch_scales_across_multiple_identities(tmp_path):
    """Never hardcodes a total — proves the function scales across an
    arbitrary mix of statuses in one call."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),  # will be mapped
            _leaf("Tee", "Tee02", "010102", "menu3", "평균 티샷 거리2"),  # no evidence -> pending
        ]
    }
    html = _table_response_html_with_menu_name(["순위", "선수명", "평균 티샷 거리(yds)"])
    (tmp_path / "Tee__Tee01__010101__2025.html").write_text(html, encoding="utf-8")

    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=tmp_path, season="2025")
    assert len(records) == 2
    statuses = {r.identity_key: r.status for r in records}
    assert statuses["Tee::Tee01::010101"] == STATUS_MAPPED
    assert statuses["Tee::Tee02::010102"] == STATUS_PENDING_EVIDENCE


# ---------------------------------------------------------------
# Real-evidence integration pin
# ---------------------------------------------------------------


def test_real_taxonomy_and_evidence_produces_one_record_per_canonical_entry():
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    # 281 canonical entries as of the Round 11 rebuild — read fresh from
    # the real taxonomy via build_canonical_plan inside the function
    # under test, not hardcoded here independently of that.
    from klpga.discovery.canonical_plan import build_canonical_plan

    counts, _plan = build_canonical_plan(taxonomy)
    assert len(records) == counts.canonical_requestable_metric_count

    # Every record has a real identity_key/label — nothing fabricated.
    assert all(r.identity_key and r.label is not None for r in records)

    # At least the real evidence-backed identities resolve to MAPPED —
    # spot-check one exact real case rather than a hardcoded count,
    # since evidence coverage will grow over time.
    approach02 = [r for r in records if r.identity_key == "Approach::Approach02::020201"]
    assert len(approach02) == 2
    by_label = {r.label: r for r in approach02}
    assert by_label["평균 남은 거리"].status == STATUS_MAPPED
    assert by_label["평균 남은 거리"].field_name == "record"
    assert by_label["그린 적중 시 남은 거리"].status == STATUS_MAPPED
    assert by_label["그린 적중 시 남은 거리"].match_method == "compound_menu_title"


def test_real_around05_evidence_stays_column_unconfirmed():
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    around05 = [r for r in records if r.identity_key == "Around::Around05::030401"]
    assert len(around05) == 2
    assert all(r.status == STATUS_COMPOUND_TITLE_COLUMN_UNCONFIRMED for r in around05)
    assert all(r.field_name is None for r in around05)


def test_real_around01_evidence_stays_needs_review():
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    records = build_identity_metric_mapping(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    around01 = [r for r in records if r.identity_key == "Around::Around01::030101" and r.label == "그린주변"]
    assert len(around01) == 1
    assert around01[0].status == STATUS_NEEDS_REVIEW
    assert around01[0].field_name is None

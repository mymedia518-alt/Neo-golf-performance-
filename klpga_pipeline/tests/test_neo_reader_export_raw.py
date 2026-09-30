"""Tests for `python -m klpga.neo_reader.cli export-raw` -- no network,
fully automatic: classifies every archived raw/<game_code>/* capture
(parser_exists / adapter_exists / parser_missing, purely from the
filenames archive_raw itself writes), runs every parser/adapter that
exists immediately (reusing run_sync_offline unchanged), and bundles
raw HTML + MANIFEST.json + a parser_samples/ copy of only the
parser-missing files. The person running it never chooses which files
matter -- the tool decides."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from klpga.neo_reader import cli

GAME_CODE = "2026100005"
FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]
ENTRY_LIST_HTML = (FIXTURES / "entry_list_sample.html").read_text(encoding="utf-8")
KRANKING_EVIDENCE = ROOT / "content" / "website_v2" / "incoming_evidence" / "2026090003"
KRANKING_PERIOD_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_PERIOD_EVIDENCE_RAW.html").read_text(encoding="utf-8")
KRANKING_FULL_HTML = (KRANKING_EVIDENCE / "KLPGA_KRANKING_2026_W36_RAW.html").read_text(encoding="utf-8")
GROUP_PAGE_HTML = (FIXTURES / "group_page_sample.html").read_text(encoding="utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _args(**overrides) -> _Args:
    # skip_run=True by default -- these tests mostly cover classification
    # and bundling, not the parser-run pathway (which has its own
    # dedicated real-fixture tests below).
    base = dict(game_code=GAME_CODE, raw_root=None, only=None, out=None, zip=False, season=None, skip_run=True)
    base.update(overrides)
    return _Args(**base)


@pytest.fixture()
def raw_game_dir(tmp_path):
    game_dir = tmp_path / "raw" / GAME_CODE
    game_dir.mkdir(parents=True)
    # Non-ASCII, non-UTF8-clean-looking bytes on purpose -- proves this
    # is a byte copy, never a text read/re-encode.
    (game_dir / "course.html").write_bytes("<html>코스 정보 \ufeff</html>".encode("utf-8"))
    (game_dir / "history_record.html").write_bytes("<html>역대 기록</html>".encode("utf-8"))
    (game_dir / "pin_placement.html").write_bytes(b"<html>\x00binary-ish bytes\xff</html>")
    (game_dir / "entry_list.html").write_text(ENTRY_LIST_HTML, encoding="utf-8")
    (game_dir / "RAW_MANIFEST_V1.json").write_text("{}", encoding="utf-8")  # archive_raw bookkeeping, never exported as page content
    return tmp_path / "raw"


def test_export_raw_directory_mode_copies_every_file_byte_for_byte(raw_game_dir, tmp_path):
    out = tmp_path / "out"
    code = cli.cmd_export_raw(_args(raw_root=str(raw_game_dir), out=str(out)))
    assert code == 0

    game_dir = raw_game_dir / GAME_CODE
    for name in ("course.html", "history_record.html", "pin_placement.html", "entry_list.html"):
        original = (game_dir / name).read_bytes()
        exported = (out / "raw" / name).read_bytes()
        assert _sha256(exported) == _sha256(original), f"{name} was not copied byte-for-byte"
    # archive_raw's own bookkeeping file is never exported as page content
    assert not (out / "raw" / "RAW_MANIFEST_V1.json").exists()


def test_export_raw_classifies_every_file_automatically_in_the_manifest(raw_game_dir, tmp_path):
    out = tmp_path / "out"
    code = cli.cmd_export_raw(_args(raw_root=str(raw_game_dir), out=str(out)))
    assert code == 0

    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    by_name = {e["filename"]: e for e in manifest["files"]}

    assert by_name["entry_list.html"]["parser_status"] == "parser_exists"
    assert by_name["entry_list.html"]["stage_name"] == "entry_list"
    assert by_name["course.html"]["parser_status"] == "parser_missing"
    assert by_name["history_record.html"]["parser_status"] == "parser_missing"
    assert by_name["pin_placement.html"]["parser_status"] == "parser_missing"

    assert set(manifest["parser_missing_files"]) == {"course.html", "history_record.html", "pin_placement.html"}

    # every entry has a real sha256 matching the actual bytes on disk
    game_dir = raw_game_dir / GAME_CODE
    for name, entry in by_name.items():
        assert entry["sha256"] == _sha256((game_dir / name).read_bytes())
        assert entry["size_bytes"] == (game_dir / name).stat().st_size


def test_export_raw_auto_copies_only_parser_missing_files_into_parser_samples(raw_game_dir, tmp_path):
    """Requirement: the tool decides, never the person. Every
    parser_missing file must land in parser_samples/ with no flag
    needed; a parser_exists file (entry_list.html) must NOT."""
    out = tmp_path / "out"
    code = cli.cmd_export_raw(_args(raw_root=str(raw_game_dir), out=str(out)))
    assert code == 0

    sample_names = {p.name for p in (out / "parser_samples").iterdir()}
    assert sample_names == {"course.html", "history_record.html", "pin_placement.html"}
    assert not (out / "parser_samples" / "entry_list.html").exists()

    # parser_samples/ content is byte-identical to raw/ -- never re-derived
    for name in sample_names:
        assert (out / "parser_samples" / name).read_bytes() == (out / "raw" / name).read_bytes()


def test_export_raw_only_filters_and_reports_missing_names(raw_game_dir, tmp_path, capsys):
    out = tmp_path / "out"
    code = cli.cmd_export_raw(_args(
        raw_root=str(raw_game_dir), out=str(out),
        only="course.html,history_record.html,pin_placement.html,not_a_real_file.html",
    ))
    assert code == 0
    captured = capsys.readouterr()
    assert "not_a_real_file.html" in captured.out

    exported_names = {p.name for p in (out / "raw").iterdir()}
    assert exported_names == {"course.html", "history_record.html", "pin_placement.html"}
    # entry_list.html was NOT requested -- must not appear, proving --only
    # actually filters rather than exporting everything regardless.
    assert "entry_list.html" not in exported_names


def test_export_raw_zip_mode_preserves_bytes_and_layout(raw_game_dir, tmp_path):
    zip_path = tmp_path / "bundle.zip"
    code = cli.cmd_export_raw(_args(raw_root=str(raw_game_dir), out=str(zip_path), zip=True))
    assert code == 0
    assert zip_path.exists()

    game_dir = raw_game_dir / GAME_CODE
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert "raw/course.html" in names
        assert "parser_samples/course.html" in names
        assert "MANIFEST.json" in names
        assert "raw/entry_list.html" in names
        assert "parser_samples/entry_list.html" not in names  # parser exists -- not a sample
        assert zf.read("raw/pin_placement.html") == (game_dir / "pin_placement.html").read_bytes()

        manifest = json.loads(zf.read("MANIFEST.json"))
        assert set(manifest["parser_missing_files"]) == {"course.html", "history_record.html", "pin_placement.html"}


def test_export_raw_fails_closed_when_game_dir_does_not_exist(tmp_path, capsys):
    empty_raw_root = tmp_path / "raw"
    code = cli.cmd_export_raw(_args(raw_root=str(empty_raw_root)))
    assert code != 0
    assert "does not exist" in capsys.readouterr().err


def test_export_raw_fails_closed_when_requested_files_are_entirely_absent(raw_game_dir, tmp_path, capsys):
    """This is the exact real-world case: course/history_record/
    pin_placement requested but raw/<game_code>/ only has files this
    pipeline's own sync already produces (e.g. entry_list.html) --
    must report clearly what's missing AND what's actually there,
    never silently produce an empty/partial bundle."""
    game_dir = raw_game_dir / GAME_CODE
    for stray in ("course.html", "history_record.html", "pin_placement.html"):
        (game_dir / stray).unlink()

    code = cli.cmd_export_raw(_args(raw_root=str(raw_game_dir), only="course.html,history_record.html,pin_placement.html"))
    assert code != 0
    err = capsys.readouterr().err
    assert "course.html" in err
    assert "entry_list.html" in err  # names what DOES exist there


def test_export_raw_default_raw_root_resolves_through_ops_paths(monkeypatch, tmp_path):
    """No --raw-root given -- must resolve via klpga.ops.paths.raw_root
    (NEO_DATA_ROOT-aware), not a hardcoded klpga_pipeline/raw, so this
    tool finds the same D:\\NEO_DATA_ROOT\\raw\\<game_code> a production
    machine's sync --offline run already reads from."""
    monkeypatch.setenv("NEO_DATA_ROOT", str(tmp_path / "simulated_neo_data_root"))
    game_dir = tmp_path / "simulated_neo_data_root" / "raw" / GAME_CODE
    game_dir.mkdir(parents=True)
    (game_dir / "course.html").write_bytes(b"<html>real capture</html>")

    out = tmp_path / "out"
    code = cli.cmd_export_raw(_args(out=str(out)))  # raw_root=None -> must resolve via NEO_DATA_ROOT
    assert code == 0
    assert (out / "raw" / "course.html").read_bytes() == b"<html>real capture</html>"


# ---------------------------------------------------------------------
# "run it immediately" -- real fixtures, skip_run=False (the default),
# proving export-raw actually executes the known parsers/adapter and
# records the outcome in MANIFEST.json, not just copies bytes.
# ---------------------------------------------------------------------

GAME_LIST_ENTRY = {
    "gameCode": GAME_CODE,
    "gameTitle": "제26회 하이트진로 챔피언십",
    "gameEngTitle": "26th Hite Jinro Championship",
    "tourType": "RE",
    "courseText": "테스트GC",
    "courseEngText": "Test GC",
    "outCourseText": "아웃",
    "inCourseText": "인",
    "startDate": "20261001",
    "endDate": "20261004",
    "gameFinish": "",
    "prizeMoney": "1000000000",
    "winnerCode": None,
    "winnerName": None,
    "gameMethod": "0",
}


@pytest.fixture()
def real_raw_game_dir(tmp_path):
    game_dir = tmp_path / "raw" / GAME_CODE
    game_dir.mkdir(parents=True)
    (game_dir / "game_list.json").write_text(json.dumps(GAME_LIST_ENTRY, ensure_ascii=False, indent=2), encoding="utf-8")
    (game_dir / "entry_list.html").write_text(ENTRY_LIST_HTML, encoding="utf-8")
    (game_dir / "kranking_period.html").write_text(KRANKING_PERIOD_HTML, encoding="utf-8")
    (game_dir / "kranking_full_table.html").write_text(KRANKING_FULL_HTML, encoding="utf-8")
    (game_dir / "grouping.html").write_text(GROUP_PAGE_HTML, encoding="utf-8")
    (game_dir / "course.html").write_bytes(b"<html>no parser exists for this yet</html>")
    return tmp_path / "raw"


def test_export_raw_runs_known_parsers_immediately_and_records_outcome(real_raw_game_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NEO_DATA_ROOT", str(tmp_path / "neo_data_root"))
    # Isolate content_root/reports_root (not NEO_DATA_ROOT-resolved --
    # see cli._default_paths) so this test never writes into the real
    # repo's content/website_v2/ directory for a real gameCode.
    monkeypatch.setattr(cli, "PIPELINE_ROOT", tmp_path / "isolated_pipeline_root")
    out = tmp_path / "out"

    code = cli.cmd_export_raw(_args(raw_root=str(real_raw_game_dir), out=str(out), season=2026, skip_run=False))
    assert code == 0

    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    by_name = {e["filename"]: e for e in manifest["files"]}

    assert by_name["entry_list.html"]["run_status"] == "success"
    assert by_name["kranking_period.html"]["run_status"] == "success"
    assert by_name["kranking_full_table.html"]["run_status"] == "success"
    assert by_name["grouping.html"]["run_status"] == "success"
    assert by_name["game_list.json"]["run_status"] == "success"
    # parser_missing files are never run -- no such stage exists
    assert by_name["course.html"]["run_status"] is None

    # real normalized output was actually produced -- "run it immediately"
    # means real execution, not just a manifest label.
    normalized_dir = tmp_path / "neo_data_root" / "normalized" / GAME_CODE
    assert (normalized_dir / "TOURNAMENT_INFO.json").exists()
    assert (normalized_dir / "ENTRY_SNAPSHOT.json").exists()
    assert (normalized_dir / "KRANKING_TOP120.json").exists()
    assert (normalized_dir / "GROUPING.json").exists()


def test_export_raw_skip_run_never_executes_a_parser(real_raw_game_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("NEO_DATA_ROOT", str(tmp_path / "neo_data_root"))
    monkeypatch.setattr(cli, "PIPELINE_ROOT", tmp_path / "isolated_pipeline_root")
    out = tmp_path / "out"

    code = cli.cmd_export_raw(_args(raw_root=str(real_raw_game_dir), out=str(out), skip_run=True))
    assert code == 0

    manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert all(e["run_status"] is None for e in manifest["files"])
    assert not (tmp_path / "neo_data_root" / "normalized" / GAME_CODE).exists()

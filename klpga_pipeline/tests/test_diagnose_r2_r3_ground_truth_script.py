"""Tests for scripts/diagnose_r2_r3_ground_truth.py's GROUND TRUTH
CHECK B (the real group-page fetch and parse).

Regression coverage for the confirmed real-Windows bug: a real fetch
failure for the group-page endpoint used to be caught by a broad
`except Exception`, logged as a WARNING, and the script would then
continue on to print "R3 not collected" and exit 0 — so
raw_group_page.html was silently never written and nothing signaled
that the fetch had actually failed. The fix removes that swallow:
a real fetch failure (or a failed file write) now aborts the whole
run with a non-zero exit code and a FATAL message, and a successful
fetch always creates the output directory, writes the complete
response body, and prints the real HTTP status, byte size, and
absolute saved path.

Also covers the follow-up wiring: a successful fetch is now parsed by
default via klpga.parsers.group_page_parser.parse_round_grouping, and
a parse failure (e.g. Round 3 not published yet) aborts loudly the
same way a fetch failure does — never silently falling back to an
empty "not collected" Round 3 dataset.

No real network access: `fetch_group_page_html`, `parse_round_grouping`,
and `collect_all_rounds_for_game` are monkeypatched.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.parsers.group_page_parser import GroupingRow
from klpga.parsers.leaderboard_parser import PlayerRoundRow

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_r2_r3_ground_truth.py"
GAME_CODE = "2026080001"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "diagnose_r2_r3_ground_truth_script")


def _row(code, name, round_number, *, round2=None, total_strokes=None, rank=1):
    return PlayerRoundRow(
        game_code=GAME_CODE, player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=str(rank), rank=rank, tie_flag=False, status=None,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=None,
        total_strokes=total_strokes, holes_completed="18",
        round1_score=None, round2_score=round2, round3_score=None, round4_score=None,
    )


def _run(module, tmp_path, argv_extra=()):
    output_dir = tmp_path / "out"
    argv = [
        "diagnose_r2_r3_ground_truth.py",
        "--game-code", GAME_CODE,
        "--cache-dir", str(tmp_path / "cache"),
        "--output-dir", str(output_dir),
        *argv_extra,
    ]
    with patch("sys.argv", argv):
        exit_code = module.main()
    return exit_code, output_dir


def test_successful_group_page_fetch_writes_file_and_prints_status_size_path(module, tmp_path, capsys):
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>real group page</html>")):
            with patch.object(module, "parse_round_grouping", return_value=[]):
                exit_code, output_dir = _run(module, tmp_path)

    assert exit_code == 0
    out_path = output_dir / "raw_group_page.html"
    assert out_path.is_file()
    assert out_path.read_text(encoding="utf-8") == "<html>real group page</html>"

    captured = capsys.readouterr().out
    assert "HTTP 200" in captured
    assert str(out_path.resolve()) in captured
    assert f"{len('<html>real group page</html>'.encode('utf-8'))} bytes" in captured


def test_successful_fetch_and_parse_classifies_the_real_r3_row_as_made_cut(module, tmp_path):
    """End-to-end wiring: a parsed Round 3 grouping row flows through
    to final_ground_truth_status = MADE_CUT_CONFIRMED in the written
    comparison table."""
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]
    parsed = [GroupingRow(player_code="p1", player_name="Player One", starting_tee="1", tee_time="09:10", group=None)]

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>real group page</html>")):
            with patch.object(module, "parse_round_grouping", return_value=parsed) as fake_parse:
                exit_code, output_dir = _run(module, tmp_path)

    assert exit_code == 0
    fake_parse.assert_called_once()
    assert fake_parse.call_args.kwargs["round_number"] == module.ROUND_NUMBER_FOR_CHECK_B

    comparison_csv = (output_dir / "comparison_table.csv").read_text(encoding="utf-8")
    assert "p1" in comparison_csv
    assert "MADE_CUT_CONFIRMED" in comparison_csv


def test_group_page_parse_failure_aborts_loudly_instead_of_silently_continuing(module, tmp_path, capsys):
    """Round 3 not published yet (or any real structure mismatch) must
    abort the run — never silently fall back to an empty Round 3
    dataset as if nothing had been collected."""
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>real group page</html>")):
            with patch.object(module, "parse_round_grouping", side_effect=ValueError("no tab-pane id='round-three'")):
                exit_code, output_dir = _run(module, tmp_path)

    assert exit_code != 0
    # the raw HTML was already written before parsing was attempted -- that evidence is preserved
    assert (output_dir / "raw_group_page.html").is_file()
    assert not (output_dir / "comparison_table.csv").exists()

    captured = capsys.readouterr().out
    assert "FATAL" in captured
    assert "no tab-pane id='round-three'" in captured
    assert "No group-page fetch/parse ran" not in captured


def test_r3_grouping_json_overrides_the_parsed_result(module, tmp_path, capsys):
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]
    override_path = tmp_path / "override.json"
    override_path.write_text(
        '[{"player_code": "p1", "player_name": "Player One", "group": null, "tee_time": "10:00", "starting_tee": "1"}]',
        encoding="utf-8",
    )

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", return_value=(200, "<html>real group page</html>")):
            with patch.object(module, "parse_round_grouping") as fake_parse:
                exit_code, output_dir = _run(module, tmp_path, argv_extra=["--r3-grouping-json", str(override_path)])

    assert exit_code == 0
    fake_parse.assert_not_called()  # the JSON override takes precedence, parsing is skipped entirely
    comparison_csv = (output_dir / "comparison_table.csv").read_text(encoding="utf-8")
    assert "MADE_CUT_CONFIRMED" in comparison_csv


def test_group_page_fetch_failure_aborts_loudly_instead_of_silently_continuing(module, tmp_path, capsys):
    """The exact regression: a real fetch failure must abort the run
    (non-zero exit, FATAL message) rather than being logged as a
    WARNING and silently falling through to 'R3 not collected'."""
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html", side_effect=ConnectionError("simulated real network failure")):
            exit_code, output_dir = _run(module, tmp_path)

    assert exit_code != 0
    assert not (output_dir / "raw_group_page.html").exists()

    captured = capsys.readouterr().out
    assert "FATAL" in captured
    assert "simulated real network failure" in captured
    # must NOT silently fall through to the old "not collected yet" happy path
    assert "No --r3-grouping-json supplied" not in captured


def test_skip_group_page_fetch_flag_still_skips_cleanly(module, tmp_path, capsys):
    round2_rows = [_row("p1", "Player One", 2, round2=68, total_strokes=140)]

    with patch.object(module, "collect_all_rounds_for_game", return_value={2: round2_rows, 1: []}):
        with patch.object(module, "fetch_group_page_html") as fake_fetch:
            exit_code, output_dir = _run(module, tmp_path, argv_extra=["--skip-group-page-fetch"])

    assert exit_code == 0
    fake_fetch.assert_not_called()
    assert not (output_dir / "raw_group_page.html").exists()
    assert "Skipped (--skip-group-page-fetch)" in capsys.readouterr().out

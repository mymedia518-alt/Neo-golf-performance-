"""2026-10-02 "Release Gate" mission: the single, fail-closed entry
point that must pass before any future build/commit/push for THIS
tournament (game_code 2026100005) proceeds. Ties together every check
a human found and fixed by hand this session into one checklist --
R1_CUT / R2_CUT / WD / DQ / DNS / HOME==현재 라운드 / Desktop / Mobile /
LIVE -- and refuses (non-zero exit, no partial credit) the instant any
one item fails. This is a tournament-specific gate, not a shared
builder -- a future tournament copies this file's pattern into its own
module, per this repo's "never share a builder ACROSS tournaments"
convention (see hitejinro_round_page.py's own module docstring).

Usage:
    python3 scripts/hitejinro_release_gate.py [--live-sha256 <hex>]

--live-sha256 is the real SHA256 of the ACTUAL deployed LIVE page
(https://neogolfdata.com/tournaments/2026/2026100005/r2/), fetched by
something with real internet access (this sandbox's own egress proxy
blocks neogolfdata.com directly -- confirmed 2026-10-02; the
established path is the live-capture-r2-oneoff.yml GitHub Actions
workflow). Omitting it does not skip the LIVE check -- it FAILS it,
printing exactly what command to run to supply it. This gate never
treats "didn't check" as "passed".
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_ROOT = REPO_ROOT / "klpga_pipeline"
LIVE_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026100005" / "r2" / "index.html"
LIVE_URL = "https://neogolfdata.com/tournaments/2026/2026100005/r2/"

# Each checklist item -> the real pytest node ids that must pass for it.
# Node ids point at the ACTUAL tests already written for this
# tournament (test_hitejinro_cut_status_model.py / test_hitejinro_
# release_gate.py) -- this gate never reimplements their assertions,
# only aggregates their pass/fail into one checklist.
CHECKLIST: dict[str, list[str]] = {
    "R1_CUT": [
        "tests/test_hitejinro_release_gate.py::test_r1_cut_threshold_is_grounded_in_real_course_par",
        "tests/test_hitejinro_cut_status_model.py::test_r1_cut_shows_as_2r_미출전_not_as_an_r1_vs_r2_code",
    ],
    "R2_CUT": [
        "tests/test_hitejinro_release_gate.py::test_no_silent_36_hole_cumulative_cut",
        "tests/test_hitejinro_cut_status_model.py::test_r2_cut_merges_inline_with_a_real_rank_and_a_badge",
    ],
    "WD": [
        "tests/test_hitejinro_cut_status_model.py::test_r2_sections_are_rendered_for_r1_cut_and_wd_only_not_active",
    ],
    "DQ": [
        "tests/test_hitejinro_cut_status_model.py::test_dq_section_renders_on_r2_page_when_a_real_dq_record_exists",
    ],
    "DNS": [
        "tests/test_hitejinro_cut_status_model.py::test_dns_text_produces_a_real_dns_status_not_silently_none",
        "tests/test_hitejinro_cut_status_model.py::test_dns_section_renders_on_r2_page_when_a_real_dns_record_exists",
    ],
    "HOME == 현재 라운드": [
        "tests/test_hitejinro_release_gate.py::test_home_mirrors_the_current_stage_page_exactly",
    ],
    "Set Difference 금지 / 상단 배너 삭제 / CSS wrap / 금지 라벨": [
        "tests/test_hitejinro_release_gate.py::test_set_difference_inference_never_comes_back",
        "tests/test_hitejinro_release_gate.py::test_css_wrap_fix_rule_is_present",
        "tests/test_hitejinro_release_gate.py::test_r2_컷_통과_label_never_reappears_without_real_evidence",
        "tests/test_hitejinro_cut_status_model.py::test_r2_top_banner_is_removed_entirely",
        "tests/test_hitejinro_cut_status_model.py::test_r2_banner_never_shows_advanced_count_and_uses_real_evidence_only",
    ],
}


def _run_pytest(node_ids: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *node_ids],
        cwd=PIPELINE_ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip().splitlines()[-1] if proc.stdout or proc.stderr else ""


def _check_desktop_mobile() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "scripts/hitejinro_playwright_gate.py"],
        cwd=PIPELINE_ROOT, capture_output=True, text=True,
    )
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-10:])
    return proc.returncode == 0, tail


def _check_live(live_sha256: str | None) -> tuple[bool, str]:
    if not LIVE_PAGE_PATH.is_file():
        return False, f"local page not built yet: {LIVE_PAGE_PATH}"
    local_sha256 = hashlib.sha256(LIVE_PAGE_PATH.read_bytes()).hexdigest()
    if live_sha256 is None:
        return False, (
            f"no --live-sha256 given -- fetch {LIVE_URL} with real internet access "
            f"(this sandbox cannot reach it directly) and re-run with "
            f"--live-sha256 <hex>. local sha256 is {local_sha256}."
        )
    if live_sha256.lower() != local_sha256:
        return False, f"MISMATCH -- live={live_sha256} local={local_sha256}"
    return True, f"MATCH -- {local_sha256}"


def main(argv: list[str]) -> int:
    live_sha256 = None
    if "--live-sha256" in argv:
        live_sha256 = argv[argv.index("--live-sha256") + 1]

    results: list[tuple[str, bool, str]] = []
    for label, node_ids in CHECKLIST.items():
        ok, detail = _run_pytest(node_ids)
        results.append((label, ok, detail))

    desktop_mobile_ok, desktop_mobile_detail = _check_desktop_mobile()
    results.append(("Desktop + Mobile (Playwright)", desktop_mobile_ok, desktop_mobile_detail))

    live_ok, live_detail = _check_live(live_sha256)
    results.append(("LIVE", live_ok, live_detail))

    print("=== HITEJINRO (2026100005) RELEASE GATE ===")
    all_ok = True
    for label, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {label}" + (f" -- {detail}" if detail else ""))
        all_ok = all_ok and ok

    print()
    if all_ok:
        print("RELEASE GATE: PASSED -- build/commit/push may proceed.")
        return 0
    print("RELEASE GATE: FAILED -- 빌드 금지 / Commit 금지 / Push 금지.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

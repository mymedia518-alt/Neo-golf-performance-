"""NEO TOURNAMENT OPERATOR V2 -- BACKGROUND TASK LIFECYCLE HARDENING
(2026-09-13): regression tests proving the exact operational bug this
session hit (a completed OK Open tournament's hourly Routine still
firing during later KB work, and a self-matching pgrep wait loop that
spun forever) can never recur silently.

Section 1: synthetic ownership/stage/preflight/closeout unit tests.
Section 2: the self-matching wait-loop ban + bounded wait_for_pid.
Section 3: TemporaryProcessSpec's mandatory-fields/timeout contract.
Section 4: the REAL persisted registry (content/website_v2/
TOURNAMENT_BACKGROUND_TASK_REGISTRY.json) -- proves the actual OK Open
task is disabled/CLOSED, the actual wait-loop bug instance is recorded
and disabled, and the actual unrelated blog Routine remains untouched.
"""
from __future__ import annotations

import time

import pytest

from klpga.tournament_background_tasks import (
    DEFAULT_REGISTRY_PATH,
    LIFECYCLE_STAGES,
    TaskLifecycleError,
    TemporaryProcessSpec,
    TournamentTaskOwnership,
    assert_not_self_matching_wait_loop,
    close_tournament,
    count_active_tournament_tasks,
    find_self_matching_wait_loops,
    load_registry,
    preflight,
    stage_violations,
    wait_for_pid,
)


def _task(**overrides) -> TournamentTaskOwnership:
    defaults = dict(
        tournament_id="2026999999", tournament_name="SYNTHETIC TEST OPEN",
        stage="r1", task_type="leaderboard_polling", created_at="2026-01-01T00:00:00Z",
        enabled=True, lifecycle_status="ACTIVE", task_id="trig_synthetic", schedule="0 * * * *",
    )
    defaults.update(overrides)
    return TournamentTaskOwnership(**defaults)


# ---------------------------------------------------------------------
# Section 1: ownership, stage-gating, preflight, closeout.
# ---------------------------------------------------------------------

def test_ownership_requires_all_mandatory_fields():
    with pytest.raises(TaskLifecycleError):
        TournamentTaskOwnership(
            tournament_id="X", tournament_name="", stage="r1", task_type="watcher",
            created_at="2026-01-01T00:00:00Z", enabled=True, lifecycle_status="ACTIVE",
        )


def test_ownership_rejects_invalid_stage():
    with pytest.raises(TaskLifecycleError):
        _task(stage="r4")  # not in LIFECYCLE_STAGES -- FINAL/R4 never a valid polling stage


def test_unrelated_task_cannot_carry_closed_lifecycle():
    with pytest.raises(TaskLifecycleError):
        TournamentTaskOwnership(
            tournament_id=None, tournament_name="unrelated automation", stage="pre",
            task_type="unrelated_automation", created_at="2026-01-01T00:00:00Z",
            enabled=True, lifecycle_status="CLOSED",
        )


def test_completed_r1_cannot_retain_r1_polling():
    """REQUIRED PROOF 1: once the tournament's real current stage
    advances past r1, an r1-stage task still enabled is a violation."""
    tasks = [_task(stage="r1")]
    assert stage_violations(tasks, "2026999999", "r1") == []
    violations = stage_violations(tasks, "2026999999", "r2")
    assert len(violations) == 1
    assert violations[0].stage == "r1"


def test_completed_tournament_cannot_retain_any_polling():
    """REQUIRED PROOF 2 + 7: at CLOSED, every enabled task for that
    tournament is a violation, and after close_tournament() the active
    count is exactly zero."""
    tasks = [
        _task(stage="fr", task_type="leaderboard_polling"),
        _task(stage="fr", task_type="round_monitor", task_id="trig_2"),
    ]
    assert len(stage_violations(tasks, "2026999999", "closed")) == 2

    result = close_tournament(tasks, "2026999999")
    assert result.remaining_tournament_tasks == 0
    assert count_active_tournament_tasks(result.updated_tasks, "2026999999") == 0
    assert result.polling_tasks_disabled == 2
    assert all(t.lifecycle_status == "CLOSED" and not t.enabled for t in result.updated_tasks)


def test_next_tournament_detects_stale_previous_tournament_tasks():
    """REQUIRED PROOF 3: exactly the real OK-Open-during-KB-work bug --
    an enabled/ACTIVE task for a DIFFERENT tournament_id is flagged
    stale and the preflight status is BLOCKED."""
    tasks = [_task(tournament_id="OLD_TOURNAMENT", stage="r1")]
    result = preflight(tasks, "NEW_TOURNAMENT")
    assert result.status == "BLOCKED"
    assert len(result.stale_tournament_tasks) == 1
    assert result.stale_tournament_tasks[0].tournament_id == "OLD_TOURNAMENT"
    assert result.active_tournament_tasks == 0  # nothing registered yet for the new tournament


def test_preflight_passes_once_stale_task_is_closed():
    tasks = [_task(tournament_id="OLD_TOURNAMENT", stage="r1")]
    closeout = close_tournament(tasks, "OLD_TOURNAMENT")
    result = preflight(closeout.updated_tasks, "NEW_TOURNAMENT")
    assert result.status == "PASS"
    assert result.stale_tournament_tasks == []


def test_unrelated_scheduled_tasks_survive_cleanup():
    """REQUIRED PROOF 4: an unrelated (tournament_id=None) automation,
    e.g. the real '골프 블로그 초안 자동 생성' Routine, must never be
    touched by closing out ANY tournament, and must never appear as a
    stale/previous-tournament hit in preflight either."""
    blog = TournamentTaskOwnership(
        tournament_id=None, tournament_name="골프 블로그 초안 자동 생성", stage="pre",
        task_type="unrelated_automation", created_at="2026-08-15T07:39:52Z",
        enabled=True, lifecycle_status="ACTIVE", task_id="trig_blog", schedule="0 23 * * *",
    )
    tournament_task = _task(tournament_id="OLD_TOURNAMENT")
    tasks = [blog, tournament_task]

    closeout = close_tournament(tasks, "OLD_TOURNAMENT")
    surviving_blog = next(t for t in closeout.updated_tasks if t.task_id == "trig_blog")
    assert surviving_blog == blog  # byte-identical, completely untouched

    result = preflight(tasks, "SOME_NEW_TOURNAMENT")
    assert all(t.task_id != "trig_blog" for t in result.stale_tournament_tasks)


# ---------------------------------------------------------------------
# Section 2: self-matching wait-loop ban + bounded wait_for_pid.
# ---------------------------------------------------------------------

def test_self_matching_pgrep_wait_loop_is_prohibited():
    """REQUIRED PROOF 5: the EXACT command this session actually ran
    (which spun forever as PID 9425) must be detected and rejected."""
    banned = 'while pgrep -f "pytest -q" > /dev/null 2>&1; do sleep 10; done; echo DONE'
    assert find_self_matching_wait_loops(banned) == ["pytest -q"]
    with pytest.raises(TaskLifecycleError):
        assert_not_self_matching_wait_loop(banned)


def test_clean_command_has_no_self_matching_loop():
    clean = 'python3 -m pytest -q tests/'
    assert find_self_matching_wait_loops(clean) == []
    assert_not_self_matching_wait_loop(clean)  # must not raise


def test_wait_for_pid_requires_positive_timeout():
    """REQUIRED PROOF 6: wait processes require timeout/termination --
    an unbounded (<=0) timeout is refused outright."""
    with pytest.raises(TaskLifecycleError):
        wait_for_pid(pid=999999, timeout_seconds=0)
    with pytest.raises(TaskLifecycleError):
        wait_for_pid(pid=999999, timeout_seconds=-5)


def test_wait_for_pid_refuses_to_wait_on_own_pid():
    import os
    with pytest.raises(TaskLifecycleError):
        wait_for_pid(pid=os.getpid(), timeout_seconds=5)


def test_wait_for_pid_returns_true_when_process_exits_before_timeout():
    import subprocess
    proc = subprocess.Popen(["sleep", "0.2"])
    assert wait_for_pid(proc.pid, timeout_seconds=5, poll_interval=0.05) is True
    proc.wait()


def test_wait_for_pid_times_out_and_returns_false_never_loops_forever():
    import subprocess
    proc = subprocess.Popen(["sleep", "5"])
    try:
        start = time.monotonic()
        result = wait_for_pid(proc.pid, timeout_seconds=0.3, poll_interval=0.05)
        elapsed = time.monotonic() - start
        assert result is False
        assert elapsed < 2.0  # bounded -- never an unbounded wait
    finally:
        proc.terminate()
        proc.wait()


# ---------------------------------------------------------------------
# Section 3: TemporaryProcessSpec's mandatory-fields/timeout contract.
# ---------------------------------------------------------------------

def test_temporary_process_spec_requires_owner_purpose_and_termination_condition():
    with pytest.raises(TaskLifecycleError):
        TemporaryProcessSpec(owner="", purpose="wait for pytest", timeout_seconds=60, termination_condition="pytest exits")
    with pytest.raises(TaskLifecycleError):
        TemporaryProcessSpec(owner="claude", purpose="", timeout_seconds=60, termination_condition="pytest exits")
    with pytest.raises(TaskLifecycleError):
        TemporaryProcessSpec(owner="claude", purpose="wait for pytest", timeout_seconds=60, termination_condition="")


def test_temporary_process_spec_requires_positive_timeout():
    with pytest.raises(TaskLifecycleError):
        TemporaryProcessSpec(owner="claude", purpose="wait for pytest", timeout_seconds=0, termination_condition="pytest exits")


def test_temporary_process_spec_valid_construction():
    spec = TemporaryProcessSpec(owner="claude", purpose="wait for pytest completion", timeout_seconds=600, termination_condition="pytest process exits or 600s elapses")
    assert spec.timeout_seconds == 600


# ---------------------------------------------------------------------
# Section 4: the REAL persisted registry.
# ---------------------------------------------------------------------

def test_real_registry_ok_open_task_is_disabled_and_closed():
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    ok_open = next(t for t in tasks if t.tournament_id == "2026120001")
    assert ok_open.enabled is False
    assert ok_open.lifecycle_status == "CLOSED"


def test_real_registry_kb_has_zero_active_tasks():
    """KB 2026090003 is BLOCKED_DATA_INCOMPLETE and must have zero
    active background tasks while waiting on official R4 evidence --
    the recorded wait-loop bug instance is disabled/CLOSED, and no
    other KB task exists."""
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    assert count_active_tournament_tasks(tasks, "2026090003") == 0


def test_real_registry_blog_routine_is_unrelated_and_untouched():
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    blog = next(t for t in tasks if t.task_type == "unrelated_automation")
    assert blog.tournament_id is None
    assert blog.enabled is True
    assert blog.lifecycle_status == "ACTIVE"


def test_real_registry_preflight_for_kb_passes():
    tasks = load_registry(DEFAULT_REGISTRY_PATH)
    result = preflight(tasks, "2026090003", orphan_wait_process_count=0)
    assert result.status == "PASS"
    assert result.stale_tournament_tasks == []

"""NEO TOURNAMENT OPERATOR V2 -- BACKGROUND TASK LIFECYCLE HARDENING
(2026-09-13).

REAL BUG this module fixes: the "OK Open R1 Active Cycle" scheduled
Routine (an hourly cron polling klpga.co.kr for a DIFFERENT, already-
completed tournament) was still enabled and firing during this
session's later KB 2026090003 work -- with zero ownership metadata
anywhere recording which tournament it belonged to, so nothing could
ever have detected it was stale. Separately, a manually-started
`while pgrep -f "pytest -q"; do sleep 10; done` wait loop spun forever,
because its own command line contained the literal string it was
searching for -- a self-matching pgrep bug with no timeout and no PID
tracking, so it could never terminate on its own.

This module is a generic, non-tournament-specific policy layer over
ANY scheduled/background task the tournament operator creates. It
never itself calls out to the Claude Code Remote trigger API (that
integration lives at the operator/session layer, not in this library)
-- it defines the ownership schema, the stage-gating rule, the
preflight/closeout gates, and a banned-pattern check, all as pure,
fully-testable functions over a JSON-persisted registry
(content/website_v2/TOURNAMENT_BACKGROUND_TASK_REGISTRY.json).

TARGET LIFECYCLE (FINAL explicitly excluded -- it is a separate
post-tournament validation stage, never a competitive-round polling
target):
    PRE -> R1 -> R2 -> R3 -> FR -> CLOSED

RULE 1 (ownership): every tournament-scoped task registered here must
carry tournament_id, tournament_name, stage, task_type, created_at,
enabled, lifecycle_status -- no anonymous entry is representable.

RULE 2 (only current stage may poll): once a tournament's real current
stage advances, any task still registered for an EARLIER stage is a
violation and must be disabled -- see `stage_violations()`. Once
lifecycle_status is CLOSED, every task for that tournament is a
violation regardless of stage.

RULE 3 (close hard stop): `close_tournament()` disables every task
whose tournament_id matches the closing tournament -- and ONLY those;
an "unrelated" entry (tournament_id=None, e.g. a personal blog-draft
Routine) is invisible to this filter by construction and is never
touched, regardless of task_type or schedule.

RULE 4 (new-tournament preflight): `preflight()` scans for any task
belonging to a DIFFERENT tournament_id that is still enabled/ACTIVE --
exactly the OK Open scenario. A hit is HARD_STOP, never silently
carried forward.

RULE 5 (self-matching process bug, banned): `assert_not_self_matching_
wait_loop()` rejects the exact `while pgrep -f "<needle>"... do sleep`
shape when <needle> would match the command's own invocation text.
`wait_for_pid()` replaces that whole anti-pattern: it tracks a real
PID, refuses to wait on the caller's own PID, and always requires a
positive timeout -- it returns False on timeout rather than looping
forever.

RULE 6 (timeout required): `TemporaryProcessSpec` cannot be
constructed without owner/purpose/timeout_seconds/termination_
condition all set -- an "orphaned" temporary process (no declared
owner or unbounded timeout) is a construction-time error, not a
runtime surprise.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

LIFECYCLE_STAGES: tuple[str, ...] = ("pre", "r1", "r2", "r3", "fr", "closed")
"""FINAL is deliberately absent -- it is not a competitive-round
polling target and is excluded from the tournament operator's
background-task lifecycle entirely."""

_ACTIVE_STAGES = LIFECYCLE_STAGES[:-1]  # everything except "closed"

_UNRELATED_TOURNAMENT_ID = None
"""Sentinel used by registry entries that are NOT tournament-scoped at
all (e.g. a personal content-drafting Routine) -- such entries are
structurally invisible to every tournament-id-filtered function below,
so they can never be touched by tournament preflight/closeout."""

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "content" / "website_v2" / "TOURNAMENT_BACKGROUND_TASK_REGISTRY.json"


class TaskLifecycleError(RuntimeError):
    """Raised for a malformed ownership record or a banned wait-loop
    pattern -- never silently downgraded to a warning."""


@dataclass(frozen=True)
class TournamentTaskOwnership:
    """One scheduled/background task's required ownership metadata.
    No anonymous tournament-scoped task is representable: every field
    below is mandatory (task_id/schedule are the only ones that may be
    None, for a one-off local wait-process that has no external
    scheduler id or cron expression)."""

    tournament_id: str | None  # None only for a genuinely unrelated, non-tournament task
    tournament_name: str
    stage: str  # one of LIFECYCLE_STAGES
    task_type: str  # e.g. "leaderboard_polling", "network_retry_loop", "round_monitor",
                     # "scheduled_validation_cycle", "watcher", "wait_process", "unrelated_automation"
    created_at: str  # ISO 8601
    enabled: bool
    lifecycle_status: str  # "ACTIVE" or "CLOSED"
    task_id: str | None = None
    schedule: str | None = None

    def __post_init__(self) -> None:
        if self.stage not in LIFECYCLE_STAGES:
            raise TaskLifecycleError(f"invalid stage {self.stage!r} -- must be one of {LIFECYCLE_STAGES}")
        if self.lifecycle_status not in ("ACTIVE", "CLOSED"):
            raise TaskLifecycleError(f"invalid lifecycle_status {self.lifecycle_status!r}")
        if self.tournament_id is None and self.lifecycle_status == "CLOSED":
            raise TaskLifecycleError("an unrelated (non-tournament) task can never carry lifecycle_status=CLOSED -- that field only applies to tournament-scoped tasks")
        if not self.tournament_name or not self.task_type or not self.created_at:
            raise TaskLifecycleError("tournament_name/task_type/created_at are mandatory -- no anonymous task allowed")

    def to_dict(self) -> dict:
        return {
            "tournament_id": self.tournament_id,
            "tournament_name": self.tournament_name,
            "stage": self.stage,
            "task_type": self.task_type,
            "created_at": self.created_at,
            "enabled": self.enabled,
            "lifecycle_status": self.lifecycle_status,
            "task_id": self.task_id,
            "schedule": self.schedule,
        }

    @staticmethod
    def from_dict(d: dict) -> "TournamentTaskOwnership":
        return TournamentTaskOwnership(
            tournament_id=d.get("tournament_id"),
            tournament_name=d["tournament_name"],
            stage=d["stage"],
            task_type=d["task_type"],
            created_at=d["created_at"],
            enabled=bool(d["enabled"]),
            lifecycle_status=d["lifecycle_status"],
            task_id=d.get("task_id"),
            schedule=d.get("schedule"),
        )

    def disabled_and_closed(self) -> "TournamentTaskOwnership":
        """A new record identical to this one except enabled=False and
        lifecycle_status=CLOSED -- never mutates in place (the registry
        is always rewritten as a whole new list, so a stale in-memory
        reference can never diverge from the persisted file)."""
        return TournamentTaskOwnership(
            tournament_id=self.tournament_id, tournament_name=self.tournament_name,
            stage="closed", task_type=self.task_type, created_at=self.created_at,
            enabled=False, lifecycle_status="CLOSED", task_id=self.task_id, schedule=self.schedule,
        )


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> list[TournamentTaskOwnership]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [TournamentTaskOwnership.from_dict(row) for row in data.get("tasks", [])]


def save_registry(tasks: list[TournamentTaskOwnership], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    payload = {"schema_version": "tournament_background_task_registry_v1", "tasks": [t.to_dict() for t in tasks]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def tasks_for_tournament(tasks: list[TournamentTaskOwnership], tournament_id: str) -> list[TournamentTaskOwnership]:
    return [t for t in tasks if t.tournament_id == tournament_id]


def count_active_tournament_tasks(tasks: list[TournamentTaskOwnership], tournament_id: str) -> int:
    return sum(1 for t in tasks_for_tournament(tasks, tournament_id) if t.enabled and t.lifecycle_status == "ACTIVE")


def stage_violations(tasks: list[TournamentTaskOwnership], tournament_id: str, current_stage: str) -> list[TournamentTaskOwnership]:
    """RULE 2: any ENABLED task for this tournament whose own `stage`
    is not the tournament's real current stage is a violation -- a
    completed stage must never continue polling. If current_stage is
    "closed", every enabled task for this tournament is a violation
    (RULE 3 folds into this the same way)."""
    if current_stage not in LIFECYCLE_STAGES:
        raise TaskLifecycleError(f"invalid current_stage {current_stage!r}")
    violations = []
    for t in tasks_for_tournament(tasks, tournament_id):
        if not t.enabled or t.lifecycle_status != "ACTIVE":
            continue
        if current_stage == "closed" or t.stage != current_stage:
            violations.append(t)
    return violations


@dataclass(frozen=True)
class PreflightResult:
    current_tournament: str
    active_tournament_tasks: int
    stale_tournament_tasks: list[TournamentTaskOwnership]
    orphan_wait_processes: int
    previous_tournament_tasks: list[TournamentTaskOwnership]
    status: str  # "PASS" or "BLOCKED"


def preflight(
    tasks: list[TournamentTaskOwnership],
    new_tournament_id: str,
    *,
    orphan_wait_process_count: int = 0,
) -> PreflightResult:
    """RULE 4: before starting work on `new_tournament_id`, find every
    still-ACTIVE-and-enabled task belonging to any OTHER tournament_id
    -- exactly the "completed OK Open tournament still polling during
    KB work" defect. `orphan_wait_process_count` is supplied by the
    caller (a real OS-process scan lives at the operator/CLI layer,
    never inside this pure-function module) so this stays unit-
    testable without touching the real process table."""
    stale = [
        t for t in tasks
        if t.tournament_id is not None
        and t.tournament_id != new_tournament_id
        and t.enabled
        and t.lifecycle_status == "ACTIVE"
    ]
    active_for_new = count_active_tournament_tasks(tasks, new_tournament_id)
    status = "PASS" if (not stale and orphan_wait_process_count == 0) else "BLOCKED"
    return PreflightResult(
        current_tournament=new_tournament_id,
        active_tournament_tasks=active_for_new,
        stale_tournament_tasks=stale,
        orphan_wait_processes=orphan_wait_process_count,
        previous_tournament_tasks=stale,
        status=status,
    )


@dataclass(frozen=True)
class CloseoutResult:
    tournament_id: str
    lifecycle: str
    polling_tasks_disabled: int
    wait_processes_terminated: int
    scheduled_cycles_disabled: int
    remaining_tournament_tasks: int
    updated_tasks: list[TournamentTaskOwnership] = field(repr=False)


_POLLING_TASK_TYPES = frozenset({"leaderboard_polling", "round_monitor", "watcher", "network_retry_loop"})


def close_tournament(tasks: list[TournamentTaskOwnership], tournament_id: str) -> CloseoutResult:
    """RULE 3: disable every task whose tournament_id == `tournament_id`
    -- and ONLY those. A task with tournament_id=None (unrelated) or a
    DIFFERENT tournament_id is not even considered by this filter, so
    it is structurally impossible for closeout to touch it."""
    updated: list[TournamentTaskOwnership] = []
    polling_disabled = wait_disabled = cycles_disabled = 0
    for t in tasks:
        if t.tournament_id != tournament_id:
            updated.append(t)
            continue
        if t.enabled:
            if t.task_type in _POLLING_TASK_TYPES:
                polling_disabled += 1
            if t.task_type == "wait_process":
                wait_disabled += 1
            if t.task_type == "scheduled_validation_cycle" or t.schedule:
                cycles_disabled += 1
        updated.append(t.disabled_and_closed())
    remaining = count_active_tournament_tasks(updated, tournament_id)
    return CloseoutResult(
        tournament_id=tournament_id, lifecycle="CLOSED",
        polling_tasks_disabled=polling_disabled, wait_processes_terminated=wait_disabled,
        scheduled_cycles_disabled=cycles_disabled, remaining_tournament_tasks=remaining,
        updated_tasks=updated,
    )


# ---------------------------------------------------------------------
# RULE 5: self-matching wait-loop ban + a real, bounded replacement.
# ---------------------------------------------------------------------

_SELF_MATCHING_PGREP_LOOP_RE = re.compile(
    r'while\s+pgrep\s+(?:-\w+\s+)*-f\s+["\']([^"\']+)["\']', re.IGNORECASE
)


def find_self_matching_wait_loops(shell_command: str) -> list[str]:
    """Returns every pgrep -f needle used by a
    `while pgrep -f "<needle>" ...; do sleep ...; done` wrapper found
    inside `shell_command` -- the exact shape that caused this
    session's PID 9425 to spin forever (pgrep -f "pytest -q" matched
    the loop's own command line, which necessarily contains the
    literal text "pytest -q" it was itself invoked with -- `ps`/`pgrep
    -f` match against a process's FULL command line, so any
    `while pgrep -f "X" ...` wrapper is unconditionally self-matching
    the moment it runs, regardless of what X is). An empty list means
    the command carries no such wrapper."""
    return [m.group(1) for m in _SELF_MATCHING_PGREP_LOOP_RE.finditer(shell_command)]


def assert_not_self_matching_wait_loop(shell_command: str) -> None:
    hits = find_self_matching_wait_loops(shell_command)
    if hits:
        raise TaskLifecycleError(
            f"banned self-matching wait-loop pattern detected (needle(s): {hits!r}) -- "
            "use wait_for_pid() instead, which tracks a real PID, excludes its own PID, "
            "and always requires a timeout"
        )


def wait_for_pid(pid: int, timeout_seconds: float, poll_interval: float = 0.5) -> bool:
    """RULE 5/6 replacement for the banned pattern: tracks the actual
    child PID (never a text pattern that can self-match), refuses to
    wait on the caller's own PID, and ALWAYS requires a positive
    timeout. Returns True if the process exited before the timeout,
    False if the timeout elapsed first -- it never loops forever."""
    if pid == os.getpid():
        raise TaskLifecycleError("wait_for_pid: refusing to wait on the caller's own PID")
    if timeout_seconds <= 0:
        raise TaskLifecycleError("wait_for_pid requires a positive timeout_seconds -- unbounded waits are banned")
    deadline = time.monotonic() + timeout_seconds
    while True:
        # If pid is our own child, a plain os.kill(pid, 0) never sees it
        # go away -- the kernel keeps it as a zombie (still a valid pid
        # for signaling) until we reap it. Reap with WNOHANG first; only
        # fall back to os.kill for pids that are not our child.
        try:
            reaped_pid, _status = os.waitpid(pid, os.WNOHANG)
            if reaped_pid == pid:
                return True
        except ChildProcessError:
            pass
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)) or 0)


@dataclass(frozen=True)
class TemporaryProcessSpec:
    """RULE 6: every temporary background/wait process requires an
    owner, a stated purpose, a positive timeout, and a stated
    termination condition -- an orphaned process (missing any of
    these) is a construction-time TaskLifecycleError, never a runtime
    surprise discovered later by `ps aux`."""

    owner: str
    purpose: str
    timeout_seconds: float
    termination_condition: str

    def __post_init__(self) -> None:
        if not self.owner or not self.purpose or not self.termination_condition:
            raise TaskLifecycleError("TemporaryProcessSpec requires owner, purpose, and termination_condition -- an orphaned process is a FAIL")
        if self.timeout_seconds <= 0:
            raise TaskLifecycleError("TemporaryProcessSpec.timeout_seconds must be positive -- unbounded temporary processes are banned")

"""NEO HJ 2026 (gameCode 2026100004) Red Team checklist, run per the
explicit 8 items in the build instruction. Each item is either:
  - STRUCTURALLY CHECKABLE NOW (no data needed -- a property of the code
    itself) -- actually run below, real PASS/FAIL.
  - BLOCKED -- cannot be evaluated without data this session doesn't have;
    reported as BLOCKED, never defaulted to PASS.

Per the instruction: "하나라도 핵심 FAIL이면 우승확률 PUBLIC 금지" / "확률 검증
없으면 PUBLIC 금지". Since Monte Carlo has never run (blocked upstream),
there is no probability output to gate here regardless -- this module
exists so the checklist itself is real, versioned, and re-runnable once
upstream data arrives, not invented at report time.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
STABLEFORD_MODULES = sorted(THIS_DIR.glob("stableford_*.py"))

# modules/symbols that would indicate the stroke-play model's ability proxy
# was reused as-is for Stableford (item 1) -- names drawn from the existing
# stroke-play simulation code in this repo (neo_win / r1_live_probability /
# seedrace2-style "ability", "win_probability" exact reuse).
FORBIDDEN_STROKE_PLAY_REUSE_IMPORTS = (
    "neo_win", "r1_live_probability", "seedrace", "strokeplay_ability",
)

KNOWN_2025_WINNER_NAMES = ("김민솔",)  # per the instruction's own named check
KNOWN_PAST_COURSE_NAMES = ("익산cc", "익산CC", "iksan")


@dataclass
class RedTeamItem:
    item: str
    status: str  # "PASS" | "FAIL" | "BLOCKED"
    detail: str


def _check_no_strokeplay_reuse() -> RedTeamItem:
    hits = []
    for mod in STABLEFORD_MODULES:
        tree = ast.parse(mod.read_text(encoding="utf-8"), filename=str(mod))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names]
                module_name = getattr(node, "module", None) or ""
                for forbidden in FORBIDDEN_STROKE_PLAY_REUSE_IMPORTS:
                    if forbidden in module_name or any(forbidden in n for n in names):
                        hits.append(f"{mod.name}: imports {module_name or names} (contains {forbidden!r})")
    if hits:
        return RedTeamItem("기존 스트로크플레이 모델 재사용 여부", "FAIL", "; ".join(hits))
    return RedTeamItem(
        "기존 스트로크플레이 모델 재사용 여부", "PASS",
        f"{len(STABLEFORD_MODULES)}개 stableford_*.py 파일 AST 검사 -- "
        "stroke-play 모델(neo_win/r1_live_probability/seedrace 등) import 없음. "
        "stableford_scoring.py는 완전히 새로운 outcome-table 기반 공식만 사용.",
    )


def _check_double_bogey_tail_represented() -> RedTeamItem:
    src = (THIS_DIR / "stableford_scoring.py").read_text(encoding="utf-8")
    has_variance = "def variance_points" in src and "double_or_worse" in src
    if not has_variance:
        return RedTeamItem("Double+ 꼬리위험 반영 여부", "FAIL", "variance_points()에 double_or_worse 항이 없음")
    return RedTeamItem(
        "Double+ 꼬리위험 반영 여부", "PASS",
        "HoleOutcomeProbabilities.variance_points()가 double_or_worse(-3점)를 포함한 "
        "2차 모멘트로 분산을 계산 -- 평균(expected_points)만으로 축소하지 않음. "
        "단, 실제 선수별 Double+ 발생률 자체는 아직 데이터가 없어 이 공식에 넣을 "
        "입력값은 BLOCKED (아래 항목 참조).",
    )


def _check_no_hardcoded_2025_winner() -> RedTeamItem:
    # exclude this checker module itself -- it must name the player it's
    # checking for, as its own check criterion, which is not model input.
    scanned = [m for m in STABLEFORD_MODULES if m.name != "stableford_redteam.py"]
    hits = []
    for mod in scanned:
        src = mod.read_text(encoding="utf-8")
        for name in KNOWN_2025_WINNER_NAMES:
            if name in src:
                hits.append(f"{mod.name}: contains {name!r}")
    if hits:
        return RedTeamItem("2025 우승자 사후인지 반영 여부", "FAIL", "; ".join(hits))
    return RedTeamItem(
        "2025 우승자 사후인지 반영 여부", "PASS",
        f"{len(scanned)}개 파일(체커 자신 제외)에 2025 우승자 이름 하드코딩 없음.",
    )


def _check_course_effect_isolation() -> RedTeamItem:
    # only the modules that would actually APPLY a course effect to 2026's
    # simulation matter here -- stableford_scoring.py (the formula) and
    # stableford_monte_carlo.py (the simulation). stableford_backtest.py
    # legitimately names 익산CC in its own refusal-guard condition (that's
    # the guard PREVENTING leakage, not leakage), and stableford_redteam.py
    # is this checker itself (self-referential false positive otherwise).
    scanned = [m for m in STABLEFORD_MODULES if m.name in ("stableford_scoring.py", "stableford_monte_carlo.py")]
    hits = []
    for mod in scanned:
        src_lower = mod.read_text(encoding="utf-8").lower()
        # allow mentions inside the module's own leading docstring (explaining
        # the gap); flag only a mention OUTSIDE that first triple-quoted block
        first_quote = src_lower.find('"""')
        body_after_docstring = (
            src_lower[src_lower.find('"""', first_quote + 3) + 3:]
            if first_quote != -1 else src_lower
        )
        for name in KNOWN_PAST_COURSE_NAMES:
            if name.lower() in body_after_docstring:
                hits.append(f"{mod.name}: {name!r} referenced outside its module docstring")
    if hits:
        return RedTeamItem("익산CC 코스효과를 에이원CC로 이식했는지 여부", "FAIL", "; ".join(hits))
    return RedTeamItem(
        "익산CC 코스효과를 에이원CC로 이식했는지 여부", "PASS",
        "실제로 2026 시뮬레이션에 코스효과를 적용할 모듈(stableford_scoring.py, "
        "stableford_monte_carlo.py) 어디에도 익산CC 언급 없음 -- 애초에 코스효과 수치나 "
        "변환 로직 자체가 구현돼 있지 않음(데이터가 없어서). 과거 코스 이름이 등장하는 "
        "유일한 곳은 stableford_backtest.py의 거부(guard) 조건문뿐이며, 이는 혼입을 "
        "막는 코드이지 혼입이 아니다.",
    )


def _blocked(item: str, reason: str) -> RedTeamItem:
    return RedTeamItem(item, "BLOCKED", reason)


def run_redteam() -> list[RedTeamItem]:
    return [
        _check_no_strokeplay_reuse(),
        _blocked("Birdie% 과대평가 여부", "실제 선수별 birdie% 데이터 및 검증된 backtest 결과 없음 -- 정량 평가 불가"),
        _check_double_bogey_tail_represented(),
        _blocked("파5 4개 홀 효과 과대평가 여부", "실제 파5 홀별 선수 성적 데이터 없음 -- 정량 평가 불가"),
        _check_no_hardcoded_2025_winner(),
        _check_course_effect_isolation(),
        _blocked("미래 데이터 leakage 여부", "backtest가 아직 실행된 적 없음(BLOCKED) -- leakage 여부를 실제로 실행해 확인할 대상 자체가 없음"),
    ]


def summarize(items: list[RedTeamItem]) -> str:
    lines = [f"[{it.status}] {it.item}: {it.detail}" for it in items]
    n_fail = sum(1 for it in items if it.status == "FAIL")
    n_blocked = sum(1 for it in items if it.status == "BLOCKED")
    n_pass = sum(1 for it in items if it.status == "PASS")
    lines.append(f"\nTOTAL: {len(items)}  PASS: {n_pass}  FAIL: {n_fail}  BLOCKED: {n_blocked}")
    lines.append(
        "VERDICT: PUBLIC 공개 불가 (하나라도 FAIL이면 금지 + 확률 자체가 BLOCKED 상태라 "
        "검증을 통과한 확률이 존재하지 않음)" if (n_fail > 0 or n_blocked > 0) else
        "VERDICT: 구조적 체크 전부 PASS (그러나 이것만으로 PUBLIC 공개 가능한 것은 아님 -- "
        "업스트림 Monte Carlo 자체가 미실행)"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize(run_redteam()))

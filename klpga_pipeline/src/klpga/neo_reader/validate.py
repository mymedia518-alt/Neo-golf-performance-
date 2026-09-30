"""Stage 4: validation. Real, checkable assertions against what stages
1-3 actually wrote for one gameCode -- never a rubber-stamp PASS. Every
check either passes against real data or is reported as a concrete
FAIL with the specific missing/inconsistent fact, matching this
project's "No PASS without evidence" standing rule."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationCheck:
    name: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    detail: str


@dataclass
class ValidationReport:
    game_code: str
    checks: list = field(default_factory=list)  # list[ValidationCheck]

    @property
    def overall(self) -> str:
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        if all(c.status == "SKIP" for c in self.checks):
            return "SKIP"
        return "PASS"

    def to_dict(self) -> dict:
        return {
            "game_code": self.game_code,
            "overall": self.overall,
            "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks],
        }


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sync(game_code: str, normalized_root: Path) -> ValidationReport:
    game_dir = normalized_root / game_code
    report = ValidationReport(game_code=game_code)

    info = _load_json(game_dir / "TOURNAMENT_INFO.json")
    if info is None:
        report.checks.append(ValidationCheck("tournament_info_present", "FAIL", "TOURNAMENT_INFO.json was not written"))
    else:
        missing = [k for k in ("game_code", "event_name", "end_date") if not info.get(k)]
        if missing:
            report.checks.append(ValidationCheck(
                "tournament_info_required_fields", "FAIL",
                f"required field(s) missing/empty: {missing}",
            ))
        else:
            report.checks.append(ValidationCheck(
                "tournament_info_required_fields", "PASS",
                f"event_name={info['event_name']!r} end_date={info['end_date']!r}",
            ))
        if info.get("game_code") != game_code:
            report.checks.append(ValidationCheck(
                "tournament_info_game_code_matches", "FAIL",
                f"TOURNAMENT_INFO.json game_code={info.get('game_code')!r} != requested {game_code!r}",
            ))
        else:
            report.checks.append(ValidationCheck("tournament_info_game_code_matches", "PASS", "game_code matches"))

    entry = _load_json(game_dir / "ENTRY_SNAPSHOT.json")
    if entry is None:
        report.checks.append(ValidationCheck("entry_list_present", "FAIL", "ENTRY_SNAPSHOT.json was not written"))
    else:
        parsed = entry.get("parsed_row_count", 0)
        unparsed = entry.get("unparsed_row_count", 0)
        if parsed == 0:
            report.checks.append(ValidationCheck("entry_list_nonempty", "FAIL", "0 entrants parsed"))
        else:
            report.checks.append(ValidationCheck("entry_list_nonempty", "PASS", f"{parsed} entrants parsed"))
        if unparsed > 0:
            report.checks.append(ValidationCheck(
                "entry_list_no_unparsed_rows", "FAIL",
                f"{unparsed} row(s) on the page could not be parsed -- see raw/{game_code}/entry_list.html",
            ))
        else:
            report.checks.append(ValidationCheck("entry_list_no_unparsed_rows", "PASS", "every row on the page parsed"))
        counts = entry.get("page_summary_counts") or {}
        page_total = counts.get("총 참가자")
        if page_total is not None and page_total != parsed:
            report.checks.append(ValidationCheck(
                "entry_list_matches_page_total", "FAIL",
                f"page reports 총 참가자={page_total} but {parsed} row(s) were parsed",
            ))
        elif page_total is not None:
            report.checks.append(ValidationCheck("entry_list_matches_page_total", "PASS", f"{parsed} == page's own 총 참가자"))
        else:
            report.checks.append(ValidationCheck("entry_list_matches_page_total", "SKIP", "page did not report a 총 참가자 count"))

    kranking = _load_json(game_dir / "KRANKING_TOP120.json")
    if kranking is None:
        report.checks.append(ValidationCheck("kranking_present", "SKIP", "KRANKING_TOP120.json was not written (see review report for why)"))
    else:
        crosscheck = kranking.get("crosscheck", {})
        if crosscheck.get("mismatched", 1) != 0:
            report.checks.append(ValidationCheck(
                "kranking_top10_crosscheck", "FAIL",
                f"{crosscheck.get('mismatched')} TOP10 row(s) disagree between the period page and the full-table page",
            ))
        else:
            report.checks.append(ValidationCheck("kranking_top10_crosscheck", "PASS", "TOP10 agrees between both official sources"))
        pop = kranking.get("full_population_count", 0)
        if pop < 120:
            report.checks.append(ValidationCheck("kranking_top120_population", "FAIL", f"only {pop} ranked players found, expected >=120"))
        else:
            report.checks.append(ValidationCheck("kranking_top120_population", "PASS", f"{pop} ranked players found"))

    return report

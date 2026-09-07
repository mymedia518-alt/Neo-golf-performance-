"""Independent fail-closed QA gate for the NEO GOLF DATA HOME V4 candidate.

This validator never builds or edits the candidate and never writes to docs/.
Its only write is the machine-readable QA report.

Usage:
    python klpga_pipeline/scripts/validate_home_v4.py
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
from typing import Any
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
DEFAULT_CANDIDATE = ROOT / "candidate" / "home-v4-data-terminal"
DEFAULT_REPORT = ROOT / "content" / "website_v2" / "NEO_HOME_V4_QA_REPORT.json"
TARGET_BRANCH = "candidate/neo-home-v4-data-terminal"
TARGET_COMMIT = "fbb69dea8d5b39e460e9df1ed0932ee5a79e958f"
PRODUCTION_REF = "origin/neo-website-v2"
QA_BRANCH = "tooling/neo-home-v4-qa"

DASH = "—"
REQUIRED_ROUTES = (
    "/", "/tournaments/", "/ranking/", "/deep-dive/", "/neo-lab/", "/about/",
)
NEO_HEADERS = (
    "NEO", "PERFORMANCE SG", "FORM", "VOL", "TREND", "EVENTS",
)
BLOCKED_METRICS = (
    "NEO RANK", "PERFORMANCE SG", "FORM", "VOLATILITY", "TREND", "EVENTS",
    "PROBABILITIES",
)
INTERNAL_MARKERS = (
    "BLOCKED_", "NOT_PRODUCTION", "HARD_STOP", "HARD FAIL", "TRACEBACK",
    "FORMULA_NOT_APPROVED", "PENDING_INDEPENDENT", "NOT_FITTED_OR_APPROVED",
)
HOME_INTERNAL_PATTERNS = (
    re.compile(r"\b1852\s+players?\b", re.I),
    re.compile(r"\bplayer\s+gap\b|\bunexplained\s+gap\b", re.I),
    re.compile(r"\bround(?:-count|\s+count|\s+mismatch|\s+disagreement)", re.I),
    re.compile(r"\bred[- ]team\b", re.I),
    re.compile(r"\b(?:temporal mapping|data leakage|no leakage detected)\b", re.I),
    re.compile(r"\b(?:formula not approved|marked unverified|unresolved disagreement)\b", re.I),
    re.compile(r"\b(?:diagnostic|audit)_[A-Z0-9_]+\b", re.I),
    re.compile(r"\b(?:BLOCKED|NOT_PRODUCTION|MISMATCH)_[A-Z0-9_]+\b", re.I),
)
BETTING_PATTERNS = (
    re.compile(r"\b(?:bet|betting|gambling|wager|sportsbook|odds)\b", re.I),
    re.compile(r"(?:베팅|배팅|도박|스포츠북)"),
)
NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?%?$")
MISSING_RANK_TOKENS = {"", "null", "none", DASH}


def _git(*args: str, cwd: Path = REPO, check: bool = True) -> str:
    run = subprocess.run(
        ["git", *args], cwd=cwd, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and run.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {run.stderr.strip()}")
    return run.stdout


def _target_for_url(root: Path, source: Path, url: str) -> Path | None:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or url.startswith(("mailto:", "tel:")):
        return None
    raw_path = unquote(parsed.path)
    if not raw_path:
        return source
    if raw_path.startswith("/"):
        relative = PurePosixPath(raw_path.lstrip("/"))
        target = root.joinpath(*relative.parts)
    else:
        relative = PurePosixPath(raw_path)
        target = source.parent.joinpath(*relative.parts)
    if raw_path.endswith("/"):
        target /= "index.html"
    elif target.is_dir():
        target /= "index.html"
    return target


def _text(value: Any) -> str:
    return str(value or "").strip()


@dataclass
class Gate:
    checks: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def add(self, check_id: str, status: str, summary: str, details: Any = None) -> None:
        item = {"id": check_id, "status": status, "summary": summary}
        if details not in (None, [], {}, ""):
            item["details"] = details
        self.checks.append(item)
        if status == "FAIL":
            self.failures.append(item)
        elif status == "NOT_READY":
            self.warnings.append(item)


class HomeV4Validator:
    def __init__(self, candidate: Path, *, production_ref: str = PRODUCTION_REF,
                 target_commit: str = TARGET_COMMIT, run_browser: bool = True) -> None:
        self.candidate = candidate.resolve()
        self.production_ref = production_ref
        self.target_commit = target_commit
        self.run_browser = run_browser
        self.gate = Gate()
        self.home_path = self.candidate / "index.html"
        self.home_html = self.home_path.read_text(encoding="utf-8")
        self.home = BeautifulSoup(self.home_html, "html.parser")
        self.css_path = self.candidate / "assets" / "home-v4.css"
        self.css = self.css_path.read_text(encoding="utf-8")

    def _candidate_immutability(self) -> tuple[bool, bool]:
        candidate_rel = self.candidate.relative_to(REPO).as_posix()
        candidate_changes = [x for x in _git(
            "diff", "--name-only", self.target_commit, "--", candidate_rel
        ).splitlines() if x]
        candidate_untracked = [x[3:] for x in _git(
            "status", "--porcelain", "--", candidate_rel
        ).splitlines() if x.startswith("?? ")]
        candidate_changes = sorted(set(candidate_changes + candidate_untracked))
        self.gate.add(
            "candidate_immutable", "PASS" if not candidate_changes else "FAIL",
            "Candidate tree is unchanged from the pinned target commit."
            if not candidate_changes else "Candidate tree was modified by or after the target commit.",
            candidate_changes[:30],
        )

        docs_changes = [x for x in _git(
            "diff", "--name-only", self.target_commit, "--", "docs"
        ).splitlines() if x]
        docs_untracked = [x[3:] for x in _git(
            "status", "--porcelain", "--", "docs"
        ).splitlines() if x.startswith("?? ")]
        production_touched = bool(docs_changes or docs_untracked)
        self.gate.add(
            "production_untouched", "FAIL" if production_touched else "PASS",
            "Production docs/ differs from the pinned QA starting commit."
            if production_touched else "Production docs/ was not modified by QA tooling.",
            sorted(set(docs_changes + docs_untracked))[:30],
        )
        return not candidate_changes, production_touched

    def _qa_change_scope(self) -> None:
        tracked = [x for x in _git(
            "diff", "--name-only", self.target_commit
        ).splitlines() if x]
        untracked = [x[3:] for x in _git("status", "--porcelain").splitlines()
                     if x.startswith("?? ")]
        runtime_prefixes = (".pytest_cache/", "klpga_pipeline/.qa-v4-pytest-")
        runtime_artifacts = sorted({path for path in untracked
                                    if path.startswith(runtime_prefixes)})
        changed = sorted({path for path in tracked + untracked
                          if not path.startswith(runtime_prefixes)})
        allowed = {
            "klpga_pipeline/scripts/validate_home_v4.py",
            "klpga_pipeline/tests/test_validate_home_v4.py",
            "klpga_pipeline/content/website_v2/NEO_HOME_V4_QA_REPORT.json",
        }
        unexpected = [path for path in changed if path not in allowed]
        branch = _git("branch", "--show-current").strip()
        issues = []
        if branch != QA_BRANCH:
            issues.append(f"current branch is {branch!r}; expected {QA_BRANCH!r}")
        if unexpected:
            issues.append(f"changes outside QA tooling/report scope: {unexpected}")
        self.gate.add(
            "qa_change_isolation", "FAIL" if issues else "PASS",
            "QA changes are isolated to the validator, its tests, and its report."
            if not issues else "QA branch or change-scope isolation failed.",
            {"branch": branch, "changed_files": changed,
             "ignored_test_runtime_artifacts": runtime_artifacts, "issues": issues},
        )

    def _target_isolation(self) -> dict[str, Any]:
        target_full = _git("rev-parse", f"{self.target_commit}^{{commit}}").strip()
        pushed_full = _git("rev-parse", f"origin/{TARGET_BRANCH}^{{commit}}").strip()
        target_changes = _git(
            "diff", "--name-only", f"{target_full}^", target_full
        ).splitlines()
        protected_patterns = (
            re.compile(r"^docs/"),
            re.compile(r"^klpga_pipeline/scripts/(?:104_|105_|106_|107_)"),
            re.compile(r"^klpga_pipeline/(?:content|data)/.*(?:NEO_RANKING|SG_WAREHOUSE|HISTORICAL)", re.I),
            re.compile(r"^klpga_pipeline/src/.*(?:ranking_v2|round_count_audit)", re.I),
        )
        protected_changes = [
            path for path in target_changes
            if any(pattern.search(path) for pattern in protected_patterns)
        ]
        issues = []
        if target_full != pushed_full:
            issues.append(
                f"pinned target {target_full} is not latest locally fetched pushed V4 {pushed_full}"
            )
        if protected_changes:
            issues.append(f"target commit changes protected production/research paths: {protected_changes}")
        result = {"pinned_sha": target_full, "pushed_sha": pushed_full,
                  "protected_changes": protected_changes, "issues": issues}
        self.gate.add(
            "target_and_research_isolation", "FAIL" if issues else "PASS",
            "Pinned SHA matches the fetched V4 branch and changes no production or Ranking V2 path."
            if not issues else "V4 target freshness or protected-path isolation failed.",
            result,
        )
        return result

    def _ranking_table(self) -> tuple[list[str], list[Any]]:
        tables = self.home.select("table.t-board")
        if len(tables) != 1:
            self.gate.add("ranking_semantics", "FAIL", "Expected exactly one ranking table.")
            return [], []
        table = tables[0]
        headers = [_text(x.get_text(" ", strip=True)) for x in table.select("thead th")]
        rows = table.select("tbody tr")
        issues: list[str] = []
        if headers != ["NEO", "PLAYER", "SPONSOR", "K-RANK", "PERFORMANCE SG",
                       "FORM", "VOL", "TREND", "EVENTS"]:
            issues.append(f"unexpected headers: {headers}")
        if not rows:
            issues.append("ranking table has no body rows")
        if any(x.get("scope") != "col" for x in table.select("thead th")):
            issues.append("every column header must use scope=col")
        for index, row in enumerate(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != len(headers):
                issues.append(f"row {index + 1} has {len(cells)} cells")
                break
            if len(row.find_all("th", recursive=False)) != 1 or row.find("th", recursive=False).get("scope") != "row":
                issues.append(f"row {index + 1} lacks one scope=row player header")
                break
        ids = [_text(x.get("id")) for x in self.home.select("[id]")]
        duplicates = sorted({x for x in ids if ids.count(x) > 1})
        if duplicates:
            issues.append(f"duplicate IDs: {duplicates[:10]}")
        self.gate.add(
            "ranking_semantics", "FAIL" if issues else "PASS",
            "Ranking table semantics failed." if issues else f"Ranking table has valid headers and {len(rows)} semantic rows.",
            issues,
        )
        return headers, rows

    def _neo_numeric_policy(self, headers: list[str], rows: list[Any]) -> dict[str, Any]:
        exposure: dict[str, dict[str, Any]] = {
            key: {"count": 0, "samples": []} for key in BLOCKED_METRICS
        }

        def record(metric: str, detail: dict[str, Any]) -> None:
            exposure[metric]["count"] += 1
            if len(exposure[metric]["samples"]) < 8:
                exposure[metric]["samples"].append(detail)

        if headers:
            index = {name: i for i, name in enumerate(headers)}
            for row in rows:
                cells = row.find_all(["th", "td"], recursive=False)
                player = _text(cells[index["PLAYER"]].get_text(" ", strip=True))
                table_fields = {
                    "NEO": "NEO RANK", "PERFORMANCE SG": "PERFORMANCE SG",
                    "FORM": "FORM", "VOL": "VOLATILITY", "TREND": "TREND",
                    "EVENTS": "EVENTS",
                }
                for column, metric in table_fields.items():
                    value = _text(cells[index[column]].get_text(" ", strip=True))
                    if value != DASH:
                        record(metric, {"surface": "desktop_table", "player": player, "value": value})
                    cell = cells[index[column]]
                    for attr in ("title", "aria-label", "data-value"):
                        value = _text(cell.get(attr))
                        if value and re.search(r"[+-]?\d+(?:\.\d+)?", value):
                            record(metric, {"surface": "cell_attribute", "player": player,
                                            "attribute": attr, "value": value})

        for mobile in self.home.select(".t-mobile-row"):
            player_node = mobile.select_one(".t-mobile-row__name")
            player = _text(player_node.get_text(" ", strip=True)) if player_node else "<MISSING>"
            rank_node = mobile.select_one(".t-mobile-row__rank")
            value = _text(rank_node.get_text(" ", strip=True)) if rank_node else "<MISSING>"
            if value != DASH:
                record("NEO RANK", {"surface": "mobile_list", "player": player, "value": value})

        inspector = self.home.select_one(".t-inspector")
        if inspector is None:
            record("NEO RANK", {"surface": "inspector", "reason": "inspector missing"})
        else:
            inspector_map = {
                "NEO RANK": "NEO RANK", "SG TOTAL": "PERFORMANCE SG",
                "SG OTT": "PERFORMANCE SG", "SG APP": "PERFORMANCE SG",
                "SG ARG": "PERFORMANCE SG", "SG PUTT": "PERFORMANCE SG",
                "SHORT": "FORM", "MID": "FORM", "LONG": "FORM",
                "VOLATILITY": "VOLATILITY", "TREND": "TREND", "EVENTS": "EVENTS",
                "CUT": "PROBABILITIES", "TOP20": "PROBABILITIES",
                "TOP10": "PROBABILITIES", "TOP5": "PROBABILITIES", "WIN": "PROBABILITIES",
            }
            for item in inspector.select(".t-inspector__row"):
                spans = item.find_all("span", recursive=False)
                if len(spans) != 2:
                    continue
                label = _text(spans[0].get_text(" ", strip=True)).upper()
                if label not in inspector_map:
                    continue
                value = _text(spans[1].get_text(" ", strip=True))
                if value != DASH:
                    record(inspector_map[label], {"surface": "player_inspector",
                                                  "label": label, "value": value})

        attr_metric_patterns = (
            (re.compile(r"(?:neo[-_]?rank|validation[-_]?score)", re.I), "NEO RANK"),
            (re.compile(r"(?:performance[-_]?sg|sg[-_]?(?:total|ott|app|arg|putt))", re.I), "PERFORMANCE SG"),
            (re.compile(r"(?:recent[-_]?form|recent[-_]?(?:5|10)[-_]?sg|form[-_]?(?:short|mid|long))", re.I), "FORM"),
            (re.compile(r"volatil", re.I), "VOLATILITY"),
            (re.compile(r"trend", re.I), "TREND"),
            (re.compile(r"(?:event[-_]?count|sample[-_]?count|events)", re.I), "EVENTS"),
            (re.compile(r"(?:probab|win[-_]?prob|top(?:5|10|20)[-_]?prob|cut[-_]?prob)", re.I), "PROBABILITIES"),
        )
        for tag in self.home.find_all(True):
            for attr, raw in tag.attrs.items():
                value = " ".join(raw) if isinstance(raw, list) else _text(raw)
                for pattern, metric in attr_metric_patterns:
                    if pattern.search(attr) and value not in MISSING_RANK_TOKENS:
                        record(metric, {"surface": "hidden_dom", "element": tag.name,
                                        "attribute": attr, "value": value})
                if attr in {"aria-label", "title"} and re.search(
                    r"(?:NEO\s*RANK|SG(?:\s+(?:TOTAL|OTT|APP|ARG|PUTT))?|FORM|VOLATILITY|TREND|EVENTS|TOP\s*(?:5|10|20)|WIN|CUT)",
                    value, re.I,
                ) and re.search(r"[+-]?\d+(?:\.\d+)?%?", value):
                    record("PROBABILITIES" if re.search(r"TOP|WIN|CUT", value, re.I)
                           else "PERFORMANCE SG", {"surface": "accessibility_attribute",
                                                   "attribute": attr, "value": value})

        json_key_policy = {
            "neo_rank": "NEO RANK",
            "neo_validation_rank": "NEO RANK",
            "validation_score": "NEO RANK",
            "performance_sg": "PERFORMANCE SG",
            "long_term_sg": "PERFORMANCE SG",
            "sg_total": "PERFORMANCE SG", "sg_ott": "PERFORMANCE SG",
            "sg_app": "PERFORMANCE SG", "sg_arg": "PERFORMANCE SG", "sg_putt": "PERFORMANCE SG",
            "recent_form": "FORM",
            "recent_5_sg": "FORM",
            "recent_10_sg": "FORM",
            "volatility": "VOLATILITY",
            "trend": "TREND",
            "events": "EVENTS",
            "event_count": "EVENTS",
            "sample_count": "EVENTS",
            "win_probability": "PROBABILITIES", "cut_probability": "PROBABILITIES",
            "top5_probability": "PROBABILITIES", "top10_probability": "PROBABILITIES",
            "top20_probability": "PROBABILITIES",
            "win": "PROBABILITIES", "cut": "PROBABILITIES",
            "top5": "PROBABILITIES", "top10": "PROBABILITIES", "top20": "PROBABILITIES",
        }

        def inspect_json(value: Any, source: str, path: str = "$") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}"
                    mapped = json_key_policy.get(str(key).casefold())
                    numeric_child = ((isinstance(child, (int, float)) and not isinstance(child, bool)) or
                                     (isinstance(child, str) and NUMERIC.fullmatch(child.strip()) is not None))
                    if mapped and numeric_child:
                        record(mapped, {"surface": "public_json", "file": source,
                                        "path": child_path, "value": child})
                    inspect_json(child, source, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    inspect_json(child, source, f"{path}[{index}]")

        for path in (self.candidate / "data").rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                record("NEO RANK", {"surface": "public_json",
                                    "file": path.relative_to(self.candidate).as_posix(),
                                    "parse_error": str(exc)})
                continue
            inspect_json(payload, path.relative_to(self.candidate).as_posix())

        js_path = self.candidate / "assets" / "home-v4.js"
        js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
        hardcoded = re.findall(
            r"(?:neoRank|performanceSg|recentForm|volatility|trend|events|winProbability|cutProbability|top(?:5|10|20)Probability)\s*[:=]\s*([+-]?\d+(?:\.\d+)?)",
            js, re.I,
        )
        for value in hardcoded:
            record("PROBABILITIES", {"surface": "javascript", "value": value})
        for value in re.findall(r"content\s*:\s*['\"]([^'\"]*\d[^'\"]*)['\"]", self.css, re.I):
            if re.search(r"(?:NEO|SG|FORM|VOL|TREND|EVENT|TOP|WIN|CUT)", value, re.I):
                record("PERFORMANCE SG", {"surface": "css_generated_content", "value": value})

        has_exposure = any(v["count"] for v in exposure.values())
        self.gate.add(
            "neo_numeric_exposure", "FAIL" if has_exposure else "PASS",
            "Unapproved NEO-derived values are exposed in public candidate artifacts."
            if has_exposure else "All blocked NEO-derived fields use em-dash placeholders.",
            exposure,
        )
        return exposure

    def _k_rank_policy(self, headers: list[str], rows: list[Any]) -> dict[str, Any]:
        population_path = ROOT / "content" / "website_v2" / "HOME_REGULAR_TOUR_PLAYER_MASTER.json"
        ranking_path = ROOT / "content" / "website_v2" / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
        issues: list[dict[str, Any]] = []
        try:
            population = json.loads(population_path.read_text(encoding="utf-8"))
            ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
            if not str(ranking.get("official_source", "")).startswith("https://k-rankings.klpga.co.kr/"):
                raise ValueError("official K-RANK source is not pinned to KLPGA")
            names: dict[str, str] = {}
            for item in population["records"]:
                key = item["player_name"].casefold()
                if key in names:
                    raise ValueError(f"ambiguous canonical name: {item['player_name']}")
                names[key] = str(item["player_id"])
            official = {str(x["player_id"]): int(x["official_rank"]) for x in ranking["records"]
                        if x.get("validation_state") == "PASS"}
            if headers:
                index = {name: i for i, name in enumerate(headers)}
                for row in rows:
                    cells = row.find_all(["th", "td"], recursive=False)
                    name = _text(cells[index["PLAYER"]].get_text(" ", strip=True))
                    displayed = _text(cells[index["K-RANK"]].get_text(" ", strip=True))
                    pid = names.get(name.casefold())
                    expected = official.get(pid or "")
                    if displayed != (str(expected) if expected is not None else DASH):
                        issues.append({"player": name, "displayed": displayed, "expected": expected or DASH})
                    sort_value = _text(row.get("data-k-rank"))
                    if expected is None:
                        if sort_value.casefold() not in {x.casefold() for x in MISSING_RANK_TOKENS}:
                            issues.append({"player": name, "attribute": "data-k-rank", "value": sort_value,
                                           "reason": "missing rank is encoded as a fabricated numeric value"})
                    elif sort_value != str(expected):
                        issues.append({"player": name, "attribute": "data-k-rank", "value": sort_value,
                                       "expected": expected})

                    display_attr = _text(row.get("data-k-rank-display"))
                    expected_display = str(expected) if expected is not None else DASH
                    if display_attr != expected_display:
                        issues.append({"player": name, "attribute": "data-k-rank-display",
                                       "value": display_attr, "expected": expected_display})

                mobile = self.home.select(".t-mobile-row")
                if len(mobile) != len(rows):
                    issues.append({"reason": "desktop/mobile K-RANK row count mismatch",
                                   "desktop": len(rows), "mobile": len(mobile)})
                for item in mobile:
                    name_node = item.select_one(".t-mobile-row__name")
                    name = _text(name_node.get_text(" ", strip=True)) if name_node else ""
                    pid = names.get(name.casefold())
                    expected = official.get(pid or "")
                    shown_node = item.select_one(".t-mobile-row__krank")
                    shown = _text(shown_node.get_text(" ", strip=True)) if shown_node else ""
                    if shown != (str(expected) if expected is not None else DASH):
                        issues.append({"player": name, "surface": "mobile", "displayed": shown,
                                       "expected": expected or DASH})
                    sort_value = _text(item.get("data-k-rank"))
                    if expected is None and sort_value.casefold() not in {
                        x.casefold() for x in MISSING_RANK_TOKENS
                    }:
                        issues.append({"player": name, "surface": "mobile",
                                       "attribute": "data-k-rank", "value": sort_value,
                                       "reason": "missing rank is encoded as a fabricated numeric value"})
                    elif expected is not None and sort_value != str(expected):
                        issues.append({"player": name, "surface": "mobile", "value": sort_value,
                                       "expected": expected})
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            issues.append({"source_error": str(exc)})
        result = {"status": "FAIL" if issues else "PASS", "violations": len(issues), "samples": issues[:12],
                  "official_source": "https://k-rankings.klpga.co.kr/allplayer.jsp"}
        self.gate.add(
            "official_k_rank", result["status"],
            f"K-RANK policy found {len(issues)} invalid displays or fabricated missing-rank values."
            if issues else "Displayed K-RANK values match the official artifact and missing ranks use null semantics.",
            result,
        )
        return result

    def _summary_provenance(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        summary_path = self.candidate / "data" / "home-v4-summary.json"
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload = {}
            issues.append({"field": "summary", "reason": f"summary JSON unavailable: {exc}"})

        cells: dict[str, dict[str, str]] = {}
        for cell in self.home.select(".t-summary__cell"):
            label_node = cell.select_one(".t-summary__label")
            value_node = cell.select_one(".t-summary__value")
            sub_node = cell.select_one(".t-summary__sub")
            label = _text(label_node.get_text(" ", strip=True)).upper() if label_node else ""
            cells[label] = {
                "value": _text(value_node.get_text(" ", strip=True)) if value_node else "",
                "description": _text(sub_node.get_text(" ", strip=True)) if sub_node else "",
            }

        coverage = cells.get("K-RANK COVERAGE")
        snapshot_link = cells.get("K-RANK SNAPSHOT LINK")
        coverage_detail: dict[str, Any] = {}
        if coverage is not None:
            ratio = re.fullmatch(r"(\d+)\s*/\s*(\d+)", coverage["value"])
            percent = re.search(r"(\d+(?:\.\d+)?)%", coverage["description"])
            if ratio is None:
                issues.append({"field": "K-RANK COVERAGE", "reason": "coverage must show numerator/denominator"})
            else:
                numerator, denominator = map(int, ratio.groups())
                coverage_detail.update({"numerator": numerator, "denominator": denominator})
                if numerator != payload.get("k_ranking_join_success") or denominator != payload.get("population_count"):
                    issues.append({"field": "K-RANK COVERAGE", "reason": "visible ratio differs from summary data",
                                   "visible": [numerator, denominator]})
                if percent is None or abs(float(percent.group(1)) - (100 * numerator / denominator)) > 0.11:
                    issues.append({"field": "K-RANK COVERAGE", "reason": "percentage is missing or ambiguous"})
            structured = payload.get("k_rank_coverage_provenance")
            if not isinstance(structured, dict):
                issues.append({"field": "K-RANK COVERAGE",
                               "reason": "structured denominator/source provenance is missing"})
            else:
                required = {"denominator_definition", "official_source", "snapshot_timestamp"}
                missing = sorted(required - set(structured))
                if missing or not str(structured.get("official_source", "")).startswith(
                    "https://k-rankings.klpga.co.kr/"
                ):
                    issues.append({"field": "K-RANK COVERAGE",
                                   "reason": "coverage provenance is incomplete or unofficial",
                                   "missing": missing})
            description = coverage["description"].casefold()
            if not any(word in description for word in ("denominator", "분모")):
                issues.append({"field": "K-RANK COVERAGE",
                               "reason": "visible copy does not define the coverage denominator"})
        elif snapshot_link is not None:
            value = snapshot_link["value"]
            description = snapshot_link["description"]
            if not value.isdigit() or int(value) != payload.get("k_ranking_join_success"):
                issues.append({"field": "K-RANK SNAPSHOT LINK",
                               "reason": "snapshot-link count differs from the verified join count"})
            ranking_path = ROOT / "content" / "website_v2" / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json"
            try:
                ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
                official_count = sum(1 for item in ranking["records"] if item.get("validation_state") == "PASS")
                if not value.isdigit() or int(value) != official_count:
                    issues.append({"field": "K-RANK SNAPSHOT LINK",
                                   "reason": "link count differs from the official validated snapshot",
                                   "official_count": official_count})
            except (OSError, KeyError, json.JSONDecodeError) as exc:
                issues.append({"field": "K-RANK SNAPSHOT LINK", "reason": f"official snapshot unavailable: {exc}"})
            if ("snapshot" not in description.casefold() and "스냅샷" not in description) or "%" in description:
                issues.append({"field": "K-RANK SNAPSHOT LINK",
                               "reason": "link count is presented as ambiguous coverage instead of a defined snapshot count"})
            coverage_detail = {"kind": "snapshot_link_count", "value": value,
                               "description": description}
        else:
            issues.append({"field": "K-RANK", "reason": "coverage or snapshot-link summary cell missing"})

        historical = (cells.get("HISTORICAL EVENTS") or cells.get("SG WAREHOUSE EVENTS")
                      or cells.get("NEO ARCHIVED EVENTS"))
        historical_detail: dict[str, Any] = {}
        if historical is None:
            issues.append({"field": "SG WAREHOUSE EVENTS", "reason": "scoped event-count cell missing"})
        else:
            historical_detail = historical
            historical_label = next(label for label in
                                    ("HISTORICAL EVENTS", "SG WAREHOUSE EVENTS", "NEO ARCHIVED EVENTS")
                                    if label in cells)
            description = historical["description"].casefold()
            if historical_label == "HISTORICAL EVENTS":
                issues.append({"field": historical_label,
                               "reason": "SG warehouse count is labeled as complete historical events"})
            if historical["value"] != DASH and not any(
                word in description for word in ("subset", "incomplete", "부분", "미완전")
            ):
                issues.append({"field": historical_label,
                               "reason": "visible copy does not state that SG warehouse events are a subset"})
            structured = payload.get("historical_event_provenance")
            if isinstance(payload.get("historical_events"), (int, float)) and not isinstance(structured, dict):
                issues.append({"field": historical_label,
                               "reason": "public JSON exposes an event count without scoped provenance"})
            elif isinstance(structured, dict) and (structured.get("complete_klpga_history") is not False or
                  not structured.get("source_artifact") or
                  "SG_WAREHOUSE" not in str(structured.get("coverage_scope", "")).upper()):
                issues.append({"field": historical_label,
                               "reason": "event provenance does not explicitly describe an incomplete SG warehouse scope"})

        result = {
            "status": "FAIL" if issues else "PASS",
            "violations": len(issues),
            "samples": issues[:20],
            "coverage": coverage_detail,
            "historical_event_display": historical_detail,
        }
        self.gate.add(
            "summary_provenance", result["status"],
            f"Summary provenance found {len(issues)} ambiguous or unsupported claims."
            if issues else "Summary coverage and event counts have explicit, scoped provenance.",
            result,
        )
        return result

    def _sponsor_policy(self, rows: list[Any], headers: list[str]) -> dict[str, Any]:
        verified_path = self.candidate / "data" / "home-v4-verified-sponsors.json"
        verified: dict[str, str] = {}
        source_error = None
        if verified_path.exists():
            try:
                payload = json.loads(verified_path.read_text(encoding="utf-8"))
                for item in payload["records"]:
                    if (item.get("validation_status") != "VERIFIED" or
                            not str(item.get("source_url", "")).startswith("https://klpga.co.kr/web/profile/")):
                        raise ValueError("sponsor record lacks VERIFIED official KLPGA profile provenance")
                    verified[str(item["player_name"]).casefold()] = str(item["sponsor"])
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                source_error = str(exc)
        violations = []
        blanks = 0
        if headers:
            index = {name: i for i, name in enumerate(headers)}
            for row in rows:
                cells = row.find_all(["th", "td"], recursive=False)
                player = _text(cells[index["PLAYER"]].get_text(" ", strip=True))
                sponsor = _text(cells[index["SPONSOR"]].get_text(" ", strip=True))
                if not sponsor:
                    blanks += 1
                elif source_error or verified.get(player.casefold()) != sponsor:
                    violations.append({"player": player, "sponsor": sponsor,
                                       "reason": source_error or "no matching VERIFIED KLPGA profile record"})
        result = {"status": "FAIL" if violations or source_error else "PASS", "blank_sponsors": blanks,
                  "verified_sponsors": len(verified), "violations": violations[:12],
                  "blank_policy": "ACCEPTED", "source_error": source_error}
        self.gate.add(
            "sponsor_policy", result["status"],
            "Unverified sponsor/affiliation text is exposed." if result["status"] == "FAIL"
            else f"Sponsor policy passed; {blanks} blank sponsor cells are accepted.", result,
        )
        return result

    def _photo_policy(self) -> dict[str, Any]:
        section = self.home.find(id="board-heading")
        section = section.find_parent("section") if section else None
        violations = []
        silhouettes = 0
        verified_photos = 0
        if section is None:
            violations.append({"reason": "ranking section missing"})
        else:
            silhouette_shapes = set()
            rows = section.select("table.t-board tbody tr")
            for index, row in enumerate(rows, start=1):
                avatar = row.select_one(".t-avatar")
                if avatar is None:
                    violations.append({"row": index, "reason": "player avatar/fallback missing"})
                elif avatar.find("svg"):
                    silhouettes += 1
                    silhouette_shapes.add(str(avatar.find("svg")))
                elif avatar.find("img") is None:
                    violations.append({"row": index, "reason": "avatar is neither a neutral silhouette nor a photo"})
            if len(silhouette_shapes) > 1:
                violations.append({"reason": "multiple player-specific SVG likenesses used instead of one neutral silhouette",
                                   "shape_count": len(silhouette_shapes)})
            for image in section.find_all("img"):
                src = _text(image.get("src"))
                if "klpga.co.kr" in src.casefold():
                    violations.append({"src": src, "reason": "KLPGA image hotlink forbidden"})
                    continue
                status = _text(image.get("data-photo-license-status") or
                               (image.parent.get("data-photo-license-status") if image.parent else ""))
                if status != "VERIFIED":
                    violations.append({"src": src, "reason": "photo_license_status is not VERIFIED"})
                else:
                    target = _target_for_url(self.candidate, self.home_path, src)
                    if target is None or not target.is_file():
                        violations.append({"src": src, "reason": "licensed photo is not a local candidate asset"})
                    else:
                        verified_photos += 1
            hotlinks = re.findall(r"https?://[^\"')\s>]*klpga\.co\.kr[^\"')\s>]*", self.home_html, re.I)
            for src in hotlinks:
                if not any(x.get("src") == src for x in violations):
                    violations.append({"src": src, "reason": "KLPGA image hotlink forbidden"})
            if re.search(r"\.t-avatar[^\{]*\{[^}]*background(?:-image)?\s*:\s*url\(", self.css, re.I | re.S):
                violations.append({"reason": "player likeness is injected through avatar CSS"})
        result = {"status": "FAIL" if violations else "PASS", "neutral_silhouettes": silhouettes,
                  "verified_photos": verified_photos, "violations": violations[:12],
                  "silhouette_fallback": "ACCEPTED"}
        self.gate.add(
            "photo_policy", result["status"],
            "Player photo policy violations found." if violations
            else f"Photo policy passed with {silhouettes} neutral silhouette instances.", result,
        )
        return result

    def _analytics_policy(self) -> dict[str, Any]:
        violations: list[dict[str, Any]] = []
        heading = self.home.find(id="analytics-heading")
        analytics = heading.find_parent("section") if heading else None
        inspector_chart = self.home.select_one(".t-inspector__chart")
        shells: list[tuple[str, Any]] = []
        if analytics is None:
            violations.append({"surface": "analytics", "reason": "analytics grid missing"})
        else:
            charts = analytics.select(".t-chart-cell")
            if not charts:
                violations.append({"surface": "analytics", "reason": "chart shells missing"})
            shells.extend((f"analytics[{index}]", chart) for index, chart in enumerate(charts, 1))
        if inspector_chart is None:
            violations.append({"surface": "player_inspector", "reason": "history chart shell missing"})
        else:
            shells.append(("player_inspector", inspector_chart.parent))

        for surface, shell in shells:
            if "데이터 검증 후 공개" not in shell.get_text(" ", strip=True):
                violations.append({"surface": surface, "reason": "approved empty-state text missing"})
            forbidden = shell.select(
                "polyline,path,polygon,[data-player-series],[data-series],[data-points],[data-sg-points]"
            )
            if forbidden:
                violations.append({"surface": surface, "reason": "fabricated series/points markup present",
                                   "elements": [node.name for node in forbidden[:8]]})
            for line in shell.find_all("line"):
                classes = set(line.get("class") or [])
                if not classes.intersection({"t-chart-axis", "t-chart-grid"}):
                    violations.append({"surface": surface, "reason": "unclassified numeric line series present"})
                    break
            circles = shell.find_all("circle")
            invalid_circles = [node for node in circles if "t-chart-pulse" not in (node.get("class") or [])]
            if invalid_circles or len(circles) > 1:
                violations.append({"surface": surface, "reason": "fabricated plotted points present"})

        js_path = self.candidate / "assets" / "home-v4.js"
        js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
        if re.search(r"(?:series|points|sgData|probabilityData)\s*[:=]\s*\[[^\]]*\d", js, re.I | re.S):
            violations.append({"surface": "javascript", "reason": "hard-coded analytic numeric series present"})

        result = {"status": "FAIL" if violations else "PASS", "violations": violations[:20],
                  "shells_checked": len(shells), "empty_state": "데이터 검증 후 공개"}
        self.gate.add(
            "analytics_policy", result["status"],
            "Analytics or inspector contains unapproved numeric series/points."
            if violations else f"{len(shells)} analytics/inspector shells contain no fabricated series.",
            result,
        )
        return result

    def _content_language(self) -> dict[str, Any]:
        public_files = [self.home_path]
        public_files.append(self.candidate / "data" / "home-v4-summary.json")
        public_files.extend(
            path for path in (self.candidate / "assets").glob("home-v4.*") if path.is_file()
        )
        blocker_hits: list[dict[str, Any]] = []
        betting_hits: list[dict[str, Any]] = []
        for path in public_files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            upper = text.upper()
            for marker in INTERNAL_MARKERS:
                if marker in upper:
                    blocker_hits.append({"file": path.relative_to(self.candidate).as_posix(), "marker": marker})
            if path.suffix.casefold() == ".html":
                visible = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
            elif path.suffix.casefold() in {".json", ".txt"}:
                visible = text
            else:
                visible = ""
            for pattern in BETTING_PATTERNS:
                found = pattern.search(visible)
                if found:
                    betting_hits.append({"file": path.relative_to(self.candidate).as_posix(), "text": found.group(0)})

        home_visible = self.home.get_text(" ", strip=True)
        detailed_hits = []
        for pattern in HOME_INTERNAL_PATTERNS:
            found = pattern.search(home_visible)
            if found:
                start = max(0, found.start() - 60)
                end = min(len(home_visible), found.end() + 100)
                detailed_hits.append({"pattern": pattern.pattern,
                                      "text": home_visible[start:end]})
        validation_heading = self.home.find(id="validation-heading")
        validation_section = validation_heading.find_parent("section") if validation_heading else None
        statuses = [] if validation_section is None else [
            _text(node.get_text(" ", strip=True)) for node in validation_section.select(".t-badge")
        ]
        invalid_states = sorted({state for state in statuses
                                 if state not in {"VALIDATING", "NOT PUBLISHED", "VERIFIED"}})
        if validation_section is None:
            detailed_hits.append({"reason": "public validation section missing"})
        if invalid_states:
            detailed_hits.append({"reason": "unsupported public validation state", "states": invalid_states})
        copy_result = {"status": "FAIL" if detailed_hits else "PASS",
                       "violations": detailed_hits[:20], "states": statuses,
                       "allowed_states": ["VALIDATING", "NOT PUBLISHED", "VERIFIED"]}
        self.gate.add(
            "public_home_copy", copy_result["status"],
            "HOME exposes engineering/audit implementation details."
            if detailed_hits else "HOME uses concise evidence-safe validation states.",
            copy_result,
        )
        self.gate.add(
            "internal_engineering_strings", "FAIL" if blocker_hits else "PASS",
            "Internal engineering blocker strings are publicly exposed." if blocker_hits
            else "No internal engineering blocker strings are exposed in HOME V4 public artifacts.", blocker_hits,
        )
        self.gate.add(
            "betting_language", "FAIL" if betting_hits else "PASS",
            "Betting/gambling language is exposed." if betting_hits else "No betting/gambling language found.",
            betting_hits,
        )
        return copy_result

    def _links_and_navigation(self) -> list[dict[str, Any]]:
        broken = []
        inherited = []
        for source in self.candidate.rglob("*.html"):
            soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
            for tag, attr in [(x, "href") for x in soup.find_all(href=True)] + [(x, "src") for x in soup.find_all(src=True)]:
                url = _text(tag.get(attr))
                parsed = urlsplit(url)
                if parsed.scheme in ("http", "https", "mailto", "tel") or parsed.netloc:
                    continue
                relative_source = source.relative_to(self.candidate).as_posix()
                item = {"source": relative_source, "url": url}
                if url.startswith("javascript:"):
                    item["reason"] = "javascript pseudo-link forbidden"
                    broken.append(item)
                    continue
                target = _target_for_url(self.candidate, source, url)
                if target is None or not target.is_file():
                    item["reason"] = "target missing"
                elif parsed.fragment:
                    target_soup = BeautifulSoup(target.read_text(encoding="utf-8"), "html.parser")
                    if target_soup.find(id=unquote(parsed.fragment)) is None:
                        item["reason"] = "fragment target missing"
                if "reason" in item:
                    production = subprocess.run(
                        ["git", "show", f"{self.production_ref}:docs/{relative_source}"],
                        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    if production.returncode == 0 and production.stdout == source.read_bytes():
                        item["classification"] = "inherited_from_production"
                        inherited.append(item)
                    else:
                        item["classification"] = "introduced_or_changed_by_home_v4"
                        broken.append(item)
        self.gate.add(
            "internal_links", "FAIL" if broken else "PASS",
            f"Found {len(broken)} broken internal links introduced by HOME V4." if broken
            else "HOME V4 introduced no broken internal links.",
            {"introduced": broken[:40], "inherited_from_production": inherited[:40]},
        )

        nav_hrefs = {_text(a.get("href")) for nav in self.home.find_all("nav") for a in nav.find_all("a")}
        nav_issues = []
        for route in REQUIRED_ROUTES:
            target = _target_for_url(self.candidate, self.home_path, route)
            if target is None or not target.is_file():
                nav_issues.append({"route": route, "reason": "route missing"})
            elif route not in nav_hrefs:
                nav_issues.append({"route": route, "reason": "not reachable from HOME navigation"})
        self.gate.add(
            "required_navigation", "FAIL" if nav_issues else "PASS",
            "Required navigation routes are missing or not linked from HOME navigation." if nav_issues
            else "All required routes exist and are reachable from HOME navigation.", nav_issues,
        )
        return broken

    def _css_accessibility(self) -> None:
        reduced_animation = bool(re.search(
            r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{.*?animation\s*:\s*none",
            self.css, re.I | re.S,
        ))
        reduced_transition = bool(re.search(
            r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{.*?transition\s*:\s*none",
            self.css, re.I | re.S,
        ))
        reduced = reduced_animation and reduced_transition
        self.gate.add(
            "reduced_motion", "PASS" if reduced else "FAIL",
            "prefers-reduced-motion disables chart animation and inspector transitions." if reduced
            else "Reduced-motion handling does not disable both animation and transitions.",
            {"animation_disabled": reduced_animation, "transition_disabled": reduced_transition},
        )
        focus = ":focus-visible" in self.css and bool(self.home.select("a[href],button,input,select"))
        toggle = self.home.select_one("button[data-t-nav-toggle][aria-controls][aria-expanded]")
        board_rows = self.home.select("table.t-board tbody tr")
        row_controls = all(row.get("tabindex") == "0" and row.get("role") == "button"
                           for row in board_rows)
        inspector = self.home.select_one("aside.t-inspector[aria-hidden][aria-label]")
        close = self.home.select_one("button[data-t-inspector-close][aria-label]")
        keyboard = focus and toggle is not None and bool(board_rows) and row_controls and inspector is not None and close is not None
        self.gate.add(
            "keyboard_focus", "PASS" if keyboard else "FAIL",
            "Focusable controls and visible focus styling are present." if keyboard
            else "Keyboard navigation/focus contract is incomplete.",
        )
        mobile_rows = self.home.select(".t-mobile-row")
        mobile_css = ("@media (max-width: 780px)" in self.css and
                      re.search(r"\.home-v4\s+\.t-mobile-list\s*\{\s*display\s*:\s*block", self.css) is not None and
                      re.search(r"\.home-v4\s+\.t-board-scroll\s*\{\s*display\s*:\s*none", self.css) is not None and
                      re.search(r"\.home-v4\s+\.t-inspector\s*\{\s*width\s*:\s*100vw", self.css) is not None)
        mobile_ok = bool(board_rows) and len(mobile_rows) == len(board_rows) and mobile_css
        self.gate.add(
            "mobile_ranking_markup", "PASS" if mobile_ok else "FAIL",
            f"Mobile list/board parity and full-width inspector verified for {len(board_rows)} players."
            if mobile_ok else "Mobile list, inspector, or responsive CSS is incomplete.",
            {"desktop_rows": len(board_rows), "mobile_rows": len(mobile_rows),
             "responsive_css": mobile_css},
        )

    def _historical_pages(self) -> list[dict[str, str]]:
        candidate_base = self.candidate / "tournaments"
        production_files = {
            x.removeprefix("docs/") for x in _git(
                "ls-tree", "-r", "--name-only", self.production_ref, "docs/tournaments"
            ).splitlines() if x.endswith(".html") and "/2026/" in x
        }
        candidate_files = {
            "tournaments/" + p.relative_to(candidate_base).as_posix()
            for p in candidate_base.rglob("*.html") if "/2026/" in "/" + p.relative_to(self.candidate).as_posix()
        }
        changed = []
        for relative in sorted(production_files | candidate_files):
            candidate_path = self.candidate / relative
            if relative not in production_files:
                changed.append({"path": relative, "reason": "candidate-only historical page"})
                continue
            if relative not in candidate_files:
                changed.append({"path": relative, "reason": "missing from candidate"})
                continue
            production = subprocess.run(
                ["git", "show", f"{self.production_ref}:docs/{relative}"], cwd=REPO,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if production.returncode or production.stdout != candidate_path.read_bytes():
                changed.append({"path": relative, "reason": "bytes differ from production"})
        self.gate.add(
            "historical_pages_preserved", "FAIL" if changed else "PASS",
            f"{len(changed)} historical tournament pages differ from {self.production_ref}."
            if changed else "Historical tournament pages are byte-identical to production.", changed,
        )
        return changed

    def _browser_checks(self) -> None:
        if not self.run_browser:
            self.gate.add("browser_rendering", "NOT_READY", "Browser execution explicitly disabled.")
            return
        server = None
        browser = None
        try:
            from playwright.sync_api import sync_playwright

            class QuietHandler(SimpleHTTPRequestHandler):
                def log_message(self, *_args):
                    return

            handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(self.candidate), **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            url = f"http://127.0.0.1:{server.server_port}/"
            with sync_playwright() as runtime:
                launch_errors = []
                for options in ({"channel": "msedge", "headless": True}, {"channel": "chrome", "headless": True}, {"headless": True}):
                    try:
                        browser = runtime.chromium.launch(**options)
                        break
                    except Exception as exc:
                        launch_errors.append(str(exc).splitlines()[0])
                if browser is None:
                    raise RuntimeError("; ".join(launch_errors))
                errors = []
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.goto(url, wait_until="domcontentloaded")
                desktop_visible = page.locator(".t-board-scroll").is_visible()
                cards_hidden = not page.locator(".t-mobile-list").is_visible()
                page.select_option("#t-sort", "k-rank")
                sort_state = page.eval_on_selector_all(
                    ".t-board tbody tr", "els => els.map(el => el.dataset.kRank || '')"
                )
                numeric_positions = [index for index, value in enumerate(sort_state)
                                     if value and value.casefold() not in {"null", "none", DASH.casefold()}]
                missing_positions = [index for index, value in enumerate(sort_state)
                                     if not value or value.casefold() in {"null", "none", DASH.casefold()}]
                missing_sorted_last = not missing_positions or not numeric_positions or min(missing_positions) > max(numeric_positions)
                page.set_viewport_size({"width": 390, "height": 844})
                cards_visible = page.locator(".t-mobile-list").is_visible()
                desktop_hidden = not page.locator(".t-board-scroll").is_visible()
                contained = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.locator("body").press("Tab")
                first_focus = page.evaluate("document.activeElement && document.activeElement.tagName")
                toggle = page.locator("[data-t-nav-toggle]")
                toggle.focus()
                toggle.press("Enter")
                toggled = toggle.get_attribute("aria-expanded") == "true"
                trigger = page.locator(".t-mobile-row").first
                trigger.focus()
                trigger.press("Enter")
                inspector = page.locator("[data-t-inspector]")
                inspector_open = inspector.get_attribute("aria-hidden") == "false" and inspector.is_visible()
                inspector_width = inspector.evaluate("el => el.getBoundingClientRect().width")
                inspector_name = _text(page.locator("[data-t-inspector-name]").text_content())
                inspector_values = page.eval_on_selector_all(
                    ".t-inspector__row",
                    "els => els.map(el => ({label: el.children[0]?.textContent.trim(), value: el.children[1]?.textContent.trim()}))",
                )
                metric_values_dash = all(item["value"] == DASH for item in inspector_values
                                         if item["label"] != "K-RANK")
                page.keyboard.press("Escape")
                inspector_closed = inspector.get_attribute("aria-hidden") == "true"
                focus_restored = page.evaluate("document.activeElement && document.activeElement.classList.contains('t-mobile-row')")
                reduced_context = browser.new_context(reduced_motion="reduce", viewport={"width": 390, "height": 844})
                reduced_page = reduced_context.new_page()
                reduced_page.goto(url, wait_until="domcontentloaded")
                animation = reduced_page.locator(".t-chart-pulse").evaluate("el => getComputedStyle(el).animationName")
                transition = reduced_page.locator(".t-inspector").evaluate("el => getComputedStyle(el).transitionDuration")
                reduced_context.close()
                details = {"desktop_table_visible": desktop_visible, "desktop_cards_hidden": cards_hidden,
                           "mobile_cards_visible": cards_visible, "mobile_table_hidden": desktop_hidden,
                           "mobile_contained": contained, "first_tab_focus": first_focus,
                           "nav_toggle_keyboard": toggled, "k_rank_missing_sorted_last": missing_sorted_last,
                           "mobile_inspector_open": inspector_open, "mobile_inspector_width": inspector_width,
                           "inspector_name_present": bool(inspector_name), "inspector_metrics_are_dash": metric_values_dash,
                           "inspector_escape_closes": inspector_closed, "focus_restored_to_trigger": focus_restored,
                           "reduced_animation_name": animation, "reduced_transition_duration": transition,
                           "page_errors": errors}
                ok = all((desktop_visible, cards_hidden, cards_visible, desktop_hidden, contained,
                          toggled, missing_sorted_last, inspector_open, inspector_width <= 390,
                          bool(inspector_name), metric_values_dash, inspector_closed, focus_restored))
                ok = ok and first_focus in {"A", "BUTTON"} and animation == "none" and transition in {"0s", "0ms"} and not errors
                self.gate.add(
                    "browser_rendering", "PASS" if ok else "FAIL",
                    "Desktop/mobile, keyboard and reduced-motion browser checks passed." if ok
                    else "One or more real browser checks failed.", details,
                )
                browser.close()
                browser = None
        except Exception as exc:
            self.gate.add("browser_rendering", "NOT_READY", "Browser QA could not run.", str(exc))
        finally:
            if browser is not None:
                browser.close()
            if server is not None:
                server.shutdown()

    def run(self) -> dict[str, Any]:
        full_target = _git("rev-parse", f"{self.target_commit}^{{commit}}").strip()
        candidate_clean, production_touched = self._candidate_immutability()
        self._qa_change_scope()
        isolation = self._target_isolation()
        headers, rows = self._ranking_table()
        exposure = self._neo_numeric_policy(headers, rows)
        k_rank_policy = self._k_rank_policy(headers, rows)
        summary_policy = self._summary_provenance()
        sponsor_policy = self._sponsor_policy(rows, headers)
        photo_policy = self._photo_policy()
        analytics_policy = self._analytics_policy()
        copy_policy = self._content_language()
        broken = self._links_and_navigation()
        self._css_accessibility()
        historical = self._historical_pages()
        self._browser_checks()
        statuses = {x["status"] for x in self.gate.checks}
        overall = "FAIL" if "FAIL" in statuses else "NOT_READY" if "NOT_READY" in statuses else "PASS"
        return {
            "schema_version": "neo_home_v4_independent_qa_v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "overall_status": overall,
            "target_branch": TARGET_BRANCH,
            "target_commit": full_target,
            "production_ref": self.production_ref,
            "checks": self.gate.checks,
            "failures": self.gate.failures,
            "warnings": self.gate.warnings,
            "production_touched": production_touched,
            "historical_pages_changed": historical,
            "neo_numeric_exposure": exposure,
            "broken_links": broken,
            "photo_policy": photo_policy,
            "sponsor_policy": sponsor_policy,
            "analytics_policy": analytics_policy,
            "summary_provenance": summary_policy,
            "public_home_copy": copy_policy,
            "official_k_rank_policy": k_rank_policy,
            "candidate_unchanged_from_target": candidate_clean,
            "ranking_v2_touched": bool(isolation["protected_changes"]),
            "production_sha": _git("rev-parse", f"{self.production_ref}^{{commit}}").strip(),
        }


def validate(candidate: Path = DEFAULT_CANDIDATE, *, production_ref: str = PRODUCTION_REF,
             target_commit: str = TARGET_COMMIT, run_browser: bool = True) -> dict[str, Any]:
    return HomeV4Validator(candidate, production_ref=production_ref,
                           target_commit=target_commit, run_browser=run_browser).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--production-ref", default=PRODUCTION_REF)
    parser.add_argument("--target-commit", default=TARGET_COMMIT)
    parser.add_argument("--no-browser", action="store_true", help="Record browser QA as NOT_READY")
    args = parser.parse_args(argv)
    if args.report.resolve().is_relative_to((REPO / "docs").resolve()):
        print("HARD FAIL: report path must not be inside production docs/", file=sys.stderr)
        return 2
    try:
        report = validate(args.candidate, production_ref=args.production_ref,
                          target_commit=args.target_commit, run_browser=not args.no_browser)
    except Exception as exc:
        report = {
            "schema_version": "neo_home_v4_independent_qa_v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "overall_status": "NOT_READY", "target_branch": TARGET_BRANCH,
            "target_commit": args.target_commit, "checks": [],
            "failures": [], "warnings": [{"id": "validator_runtime", "status": "NOT_READY", "summary": str(exc)}],
            "production_touched": False, "historical_pages_changed": [],
            "neo_numeric_exposure": {}, "broken_links": [], "photo_policy": {},
            "sponsor_policy": {}, "analytics_policy": {}, "summary_provenance": {},
            "public_home_copy": {}, "ranking_v2_touched": False,
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"overall_status": report["overall_status"],
                      "failures": len(report.get("failures", [])),
                      "warnings": len(report.get("warnings", [])),
                      "report": str(args.report)}, ensure_ascii=False))
    return 0 if report["overall_status"] == "PASS" else 1 if report["overall_status"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())

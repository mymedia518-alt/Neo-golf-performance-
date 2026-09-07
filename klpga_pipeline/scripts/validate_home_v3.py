"""Independent fail-closed QA gate for the NEO GOLF DATA HOME V3 candidate.

This validator never builds or edits the candidate and never writes to docs/.
Its only write is the machine-readable QA report.

Usage:
    python klpga_pipeline/scripts/validate_home_v3.py
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
DEFAULT_CANDIDATE = ROOT / "candidate" / "home-v3-shell"
DEFAULT_REPORT = ROOT / "content" / "website_v2" / "NEO_HOME_V3_QA_REPORT.json"
TARGET_BRANCH = "candidate/neo-home-v3-shell"
TARGET_COMMIT = "375bf9a"
PRODUCTION_REF = "origin/neo-website-v2"
QA_BRANCH = "tooling/neo-home-v3-qa"

DASH = "—"
REQUIRED_ROUTES = (
    "/", "/tournaments/", "/ranking/", "/deep-dive/", "/neo-lab/", "/about/",
)
NEO_HEADERS = (
    "NEO RANK", "PERFORMANCE SG", "RECENT FORM", "VOLATILITY", "TREND", "EVENTS",
)
INTERNAL_MARKERS = (
    "BLOCKED_", "NOT_APPROVED", "HARD_STOP", "HARD FAIL", "TRACEBACK",
    "SG WAREHOUSE", "FORMULA_NOT_APPROVED", "PENDING_INDEPENDENT",
    "NOT_PRODUCTION", "NOT_FITTED_OR_APPROVED",
)
BETTING_PATTERNS = (
    re.compile(r"\b(?:bet|betting|gambling|wager|sportsbook|odds)\b", re.I),
    re.compile(r"(?:베팅|배팅|도박|스포츠북)"),
)
NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?%?$")


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


class HomeV3Validator:
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
        self.css_path = self.candidate / "assets" / "home-v3.css"
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
        changed = sorted(set(tracked + untracked))
        allowed = {
            "klpga_pipeline/scripts/validate_home_v3.py",
            "klpga_pipeline/tests/test_validate_home_v3.py",
            "klpga_pipeline/content/website_v2/NEO_HOME_V3_QA_REPORT.json",
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
            {"branch": branch, "changed_files": changed, "issues": issues},
        )

    def _ranking_table(self) -> tuple[list[str], list[Any]]:
        tables = self.home.select("table.v3-rank-table")
        if len(tables) != 1:
            self.gate.add("ranking_semantics", "FAIL", "Expected exactly one ranking table.")
            return [], []
        table = tables[0]
        headers = [_text(x.get_text(" ", strip=True)) for x in table.select("thead th")]
        rows = table.select("tbody tr")
        issues: list[str] = []
        if headers != ["NEO RANK", "선수", "스폰서", "K-RANK", "PERFORMANCE SG",
                       "RECENT FORM", "VOLATILITY", "TREND", "EVENTS"]:
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
            key: {"count": 0, "samples": []} for key in NEO_HEADERS
        }
        if headers:
            index = {name: i for i, name in enumerate(headers)}
            for row in rows:
                cells = row.find_all(["th", "td"], recursive=False)
                player = _text(cells[index["선수"]].get_text(" ", strip=True))
                for name in NEO_HEADERS:
                    value = _text(cells[index[name]].get_text(" ", strip=True))
                    if value != DASH:
                        exposure[name]["count"] += 1
                        if len(exposure[name]["samples"]) < 5:
                            exposure[name]["samples"].append({"player": player, "value": value})
                for attr in ("data-recent-sg", "data-neo-rank", "data-performance-sg",
                             "data-volatility", "data-events"):
                    value = _text(row.get(attr))
                    if value and NUMERIC.fullmatch(value):
                        mapped = {"data-recent-sg": "RECENT FORM", "data-neo-rank": "NEO RANK",
                                  "data-performance-sg": "PERFORMANCE SG", "data-volatility": "VOLATILITY",
                                  "data-events": "EVENTS"}[attr]
                        exposure[mapped]["count"] += 1
                        if len(exposure[mapped]["samples"]) < 5:
                            exposure[mapped]["samples"].append({"player": player, "attribute": attr, "value": value})
                for cell_name in ("PERFORMANCE SG", "RECENT FORM", "VOLATILITY", "TREND", "EVENTS"):
                    cell = cells[index[cell_name]]
                    for attr in ("title", "aria-label", "data-value"):
                        value = _text(cell.get(attr))
                        if value and re.search(r"[+-]?\d+(?:\.\d+)?", value):
                            exposure[cell_name]["count"] += 1
                            if len(exposure[cell_name]["samples"]) < 5:
                                exposure[cell_name]["samples"].append({"player": player, "attribute": attr, "value": value})

        cards = self.home.select(".v3-rank-card")
        card_issues = []
        for card in cards:
            player = _text(card.select_one(".v3-rank-card__name").get_text(" ", strip=True))
            fields = {
                "NEO RANK": card.select_one(".v3-rank-card__rank"),
                "PERFORMANCE SG": card.select_one(".v3-rank-card__sg"),
            }
            more = {re.sub(r"\s+", " ", _text(span.get_text(" ", strip=True))).split(" ", 1)[0]: span.find("b")
                    for span in card.select(".v3-rank-card__more > span")}
            fields.update({"RECENT FORM": more.get("RECENT"), "VOLATILITY": more.get("VOL"),
                           "TREND": more.get("TREND"), "EVENTS": more.get("EVENTS")})
            for name, node in fields.items():
                value = _text(node.get_text(" ", strip=True)) if node else "<MISSING>"
                if value != DASH:
                    exposure[name]["count"] += 1
                    if len(exposure[name]["samples"]) < 5:
                        exposure[name]["samples"].append({"player": player, "mobile": value})
            attr_value = _text(card.get("data-recent-sg"))
            if attr_value and NUMERIC.fullmatch(attr_value):
                exposure["RECENT FORM"]["count"] += 1
                if len(exposure["RECENT FORM"]["samples"]) < 5:
                    exposure["RECENT FORM"]["samples"].append({"player": player, "mobile_attribute": attr_value})

        json_key_policy = {
            "neo_rank": "NEO RANK",
            "neo_validation_rank": "NEO RANK",
            "performance_sg": "PERFORMANCE SG",
            "long_term_sg": "PERFORMANCE SG",
            "recent_form": "RECENT FORM",
            "recent_5_sg": "RECENT FORM",
            "recent_10_sg": "RECENT FORM",
            "volatility": "VOLATILITY",
            "events": "EVENTS",
            "event_count": "EVENTS",
            "sample_count": "EVENTS",
        }

        def inspect_json(value: Any, source: str, path: str = "$") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}"
                    mapped = json_key_policy.get(str(key).casefold())
                    if mapped and isinstance(child, (int, float)) and not isinstance(child, bool):
                        exposure[mapped]["count"] += 1
                        if len(exposure[mapped]["samples"]) < 5:
                            exposure[mapped]["samples"].append(
                                {"public_json": source, "path": child_path, "value": child}
                            )
                    inspect_json(child, source, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    inspect_json(child, source, f"{path}[{index}]")

        for path in (self.candidate / "data").rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                exposure["NEO RANK"]["count"] += 1
                if len(exposure["NEO RANK"]["samples"]) < 5:
                    exposure["NEO RANK"]["samples"].append(
                        {"public_json": path.relative_to(self.candidate).as_posix(), "parse_error": str(exc)}
                    )
                continue
            inspect_json(payload, path.relative_to(self.candidate).as_posix())
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
                    name = _text(cells[index["선수"]].get_text(" ", strip=True))
                    displayed = _text(cells[index["K-RANK"]].get_text(" ", strip=True))
                    pid = names.get(name.casefold())
                    expected = official.get(pid or "")
                    if displayed != (str(expected) if expected is not None else DASH):
                        issues.append({"player": name, "displayed": displayed, "expected": expected or DASH})
                    sort_value = _text(row.get("data-k-rank"))
                    if expected is None:
                        if sort_value not in ("", DASH):
                            issues.append({"player": name, "attribute": "data-k-rank", "value": sort_value,
                                           "reason": "unofficial missing-value sentinel"})
                    elif sort_value != str(expected):
                        issues.append({"player": name, "attribute": "data-k-rank", "value": sort_value,
                                       "expected": expected})
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            issues.append({"source_error": str(exc)})
        result = {"status": "FAIL" if issues else "PASS", "violations": len(issues), "samples": issues[:12],
                  "official_source": "https://k-rankings.klpga.co.kr/allplayer.jsp"}
        self.gate.add(
            "official_k_rank", result["status"],
            f"K-RANK policy found {len(issues)} invalid display or hidden sentinel values."
            if issues else "Displayed K-RANK values match the validated official KLPGA artifact.",
            result,
        )
        return result

    def _sponsor_policy(self, rows: list[Any], headers: list[str]) -> dict[str, Any]:
        verified_path = self.candidate / "data" / "home-v3-verified-sponsors.json"
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
                player = _text(cells[index["선수"]].get_text(" ", strip=True))
                sponsor = _text(cells[index["스폰서"]].get_text(" ", strip=True))
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
        section = self.home.find(id="v3-ranking-heading")
        section = section.find_parent("section") if section else None
        violations = []
        silhouettes = 0
        verified_photos = 0
        if section is None:
            violations.append({"reason": "ranking section missing"})
        else:
            rows = section.select("table.v3-rank-table tbody tr")
            for index, row in enumerate(rows, start=1):
                avatar = row.select_one(".v3-avatar")
                if avatar is None:
                    violations.append({"row": index, "reason": "player avatar/fallback missing"})
                elif avatar.find("svg"):
                    silhouettes += 1
                elif avatar.find("img") is None:
                    violations.append({"row": index, "reason": "avatar is neither a neutral silhouette nor a photo"})
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
        result = {"status": "FAIL" if violations else "PASS", "neutral_silhouettes": silhouettes,
                  "verified_photos": verified_photos, "violations": violations[:12],
                  "silhouette_fallback": "ACCEPTED"}
        self.gate.add(
            "photo_policy", result["status"],
            "Player photo policy violations found." if violations
            else f"Photo policy passed with {silhouettes} neutral silhouette instances.", result,
        )
        return result

    def _race_policy(self) -> dict[str, Any]:
        heading = self.home.find(id="v3-race-heading")
        section = heading.find_parent("section") if heading else None
        violations = []
        if section is None:
            violations.append("Performance Race section missing")
        else:
            if "데이터 검증 후 공개" not in section.get_text(" ", strip=True):
                violations.append("required empty-state text missing")
            forbidden = section.select("polyline,path,polygon,[data-v3-race-series],[data-player-series]")
            if forbidden:
                violations.append(f"player/fabricated series markup present: {[x.name for x in forbidden[:8]]}")
            circles = [x for x in section.find_all("circle") if "v3-race-pulse" not in (x.get("class") or [])]
            if circles:
                violations.append("unexpected plotted point series present")
            if len(section.select("circle.v3-race-pulse")) > 1:
                violations.append("more than one decorative pulse point present")
        result = {"status": "FAIL" if violations else "PASS", "violations": violations,
                  "empty_state": "데이터 검증 후 공개"}
        self.gate.add(
            "performance_race_policy", result["status"],
            "Performance Race contains unapproved series or lacks its empty state." if violations
            else "Performance Race is an empty structural shell with approved text.", result,
        )
        return result

    def _content_language(self) -> None:
        public_files = [
            path for path in self.candidate.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".html", ".json", ".js", ".css", ".txt"}
        ]
        blocker_hits = []
        betting_hits = []
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
        self.gate.add(
            "internal_engineering_strings", "FAIL" if blocker_hits else "PASS",
            "Internal engineering blocker strings are publicly exposed." if blocker_hits
            else "No internal engineering blocker strings are exposed in HOME V3 public artifacts.", blocker_hits,
        )
        self.gate.add(
            "betting_language", "FAIL" if betting_hits else "PASS",
            "Betting/gambling language is exposed." if betting_hits else "No betting/gambling language found.",
            betting_hits,
        )

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
                        item["classification"] = "introduced_or_changed_by_home_v3"
                        broken.append(item)
        self.gate.add(
            "internal_links", "FAIL" if broken else "PASS",
            f"Found {len(broken)} broken internal links introduced by HOME V3." if broken
            else "HOME V3 introduced no broken internal links.",
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
        reduced = bool(re.search(
            r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{.*?animation\s*:\s*none",
            self.css, re.I | re.S,
        ))
        self.gate.add(
            "reduced_motion", "PASS" if reduced else "FAIL",
            "prefers-reduced-motion disables animation." if reduced
            else "Missing a reduced-motion media rule that disables animation.",
        )
        focus = ":focus-visible" in self.css and bool(self.home.select("a[href],button,input,select"))
        toggle = self.home.select_one("button[data-v3-nav-toggle][aria-controls][aria-expanded]")
        keyboard = focus and toggle is not None
        self.gate.add(
            "keyboard_focus", "PASS" if keyboard else "FAIL",
            "Focusable controls and visible focus styling are present." if keyboard
            else "Keyboard navigation/focus contract is incomplete.",
        )
        cards = self.home.select(".v3-rank-card")
        rows = self.home.select("table.v3-rank-table tbody tr")
        mobile_css = ("@media (max-width: 760px)" in self.css and
                      re.search(r"\.home-v3\s+\.v3-rank-cards\s*\{\s*display\s*:\s*block", self.css) is not None and
                      re.search(r"\.home-v3\s+[^\{]*v3-desktop-only\s*\{\s*display\s*:\s*none", self.css) is not None)
        mobile_ok = bool(rows) and len(cards) == len(rows) and mobile_css
        self.gate.add(
            "mobile_ranking_markup", "PASS" if mobile_ok else "FAIL",
            f"Mobile card/table parity verified for {len(rows)} players." if mobile_ok
            else "Mobile ranking markup or responsive CSS is incomplete.",
            {"desktop_rows": len(rows), "mobile_cards": len(cards)},
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
                desktop_visible = page.locator(".v3-desktop-only").is_visible()
                cards_hidden = not page.locator(".v3-rank-cards").is_visible()
                page.set_viewport_size({"width": 390, "height": 844})
                cards_visible = page.locator(".v3-rank-cards").is_visible()
                desktop_hidden = not page.locator(".v3-desktop-only").is_visible()
                contained = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.locator("body").press("Tab")
                first_focus = page.evaluate("document.activeElement && document.activeElement.tagName")
                toggle = page.locator("[data-v3-nav-toggle]")
                toggle.focus()
                toggle.press("Enter")
                toggled = toggle.get_attribute("aria-expanded") == "true"
                reduced_context = browser.new_context(reduced_motion="reduce", viewport={"width": 390, "height": 844})
                reduced_page = reduced_context.new_page()
                reduced_page.goto(url, wait_until="domcontentloaded")
                animation = reduced_page.locator(".v3-race-pulse").evaluate("el => getComputedStyle(el).animationName")
                reduced_context.close()
                details = {"desktop_table_visible": desktop_visible, "desktop_cards_hidden": cards_hidden,
                           "mobile_cards_visible": cards_visible, "mobile_table_hidden": desktop_hidden,
                           "mobile_contained": contained, "first_tab_focus": first_focus,
                           "nav_toggle_keyboard": toggled, "reduced_animation_name": animation,
                           "page_errors": errors}
                ok = all((desktop_visible, cards_hidden, cards_visible, desktop_hidden, contained, toggled)) and first_focus in {"A", "BUTTON"} and animation == "none" and not errors
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
        headers, rows = self._ranking_table()
        exposure = self._neo_numeric_policy(headers, rows)
        k_rank_policy = self._k_rank_policy(headers, rows)
        sponsor_policy = self._sponsor_policy(rows, headers)
        photo_policy = self._photo_policy()
        race_policy = self._race_policy()
        self._content_language()
        broken = self._links_and_navigation()
        self._css_accessibility()
        historical = self._historical_pages()
        self._browser_checks()
        statuses = {x["status"] for x in self.gate.checks}
        overall = "FAIL" if "FAIL" in statuses else "NOT_READY" if "NOT_READY" in statuses else "PASS"
        return {
            "schema_version": "neo_home_v3_independent_qa_v1",
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
            "performance_race_policy": race_policy,
            "official_k_rank_policy": k_rank_policy,
            "candidate_unchanged_from_target": candidate_clean,
        }


def validate(candidate: Path = DEFAULT_CANDIDATE, *, production_ref: str = PRODUCTION_REF,
             target_commit: str = TARGET_COMMIT, run_browser: bool = True) -> dict[str, Any]:
    return HomeV3Validator(candidate, production_ref=production_ref,
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
            "schema_version": "neo_home_v3_independent_qa_v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "overall_status": "NOT_READY", "target_branch": TARGET_BRANCH,
            "target_commit": args.target_commit, "checks": [],
            "failures": [], "warnings": [{"id": "validator_runtime", "status": "NOT_READY", "summary": str(exc)}],
            "production_touched": False, "historical_pages_changed": [],
            "neo_numeric_exposure": {}, "broken_links": [], "photo_policy": {},
            "sponsor_policy": {}, "performance_race_policy": {},
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

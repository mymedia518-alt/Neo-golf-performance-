"""Fail-closed guard for value-only updates to an explicitly frozen template.

Contracts must be reviewed independently of an update. This module never
creates a baseline from the candidate and never marks a model validated.
"""
from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import math
import re

from bs4 import BeautifulSoup


class ConstantIntegrityError(ValueError):
    pass


REQUIRED_FEATURES = {"sponsor", "sg", "win", "top5", "top10", "top20", "navigation"}
VARIABLE_FIELDS = {"rank", "total", "today", "completed_holes", "current_hole",
                   "snapshot_timestamp", "sg", "win", "top5", "top10", "top20"}
PROTECTED = "nav,header,style,script,link,thead,caption,label,.player,.sponsor"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ConstantIntegrityError(message)


class _Positions(HTMLParser):
    """Record source spans without serializing or rewriting the HTML."""

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0]
        self.lines.extend(m.end() for m in re.finditer("\n", text))
        self.nodes = []
        self.stack = []
        self.feed(text)
        require(not self.stack, "unclosed template element")

    def offset(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.offset()
        node = {"tag": tag, "start": start, "inner_start": start + len(self.get_starttag_text())}
        self.nodes.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        require(bool(self.stack) and self.stack[-1]["tag"] == tag, "ambiguous/malformed template nesting")
        self.stack.pop()["inner_end"] = self.offset()


def _spans(html, contract):
    soup = BeautifulSoup(html, "html.parser")
    tags = soup.find_all(True)
    positions = _Positions(html).nodes
    require(len(tags) == len(positions), "HTML parser structure mismatch")
    by_identity = {id(tag): node for tag, node in zip(tags, positions)}
    protected = {id(tag) for tag in soup.select(PROTECTED)}
    features = contract.get("features", {})
    require(REQUIRED_FEATURES <= features.keys(), "missing mandatory feature selectors in frozen contract")
    for feature in REQUIRED_FEATURES:
        require(bool(features[feature]) and bool(soup.select(features[feature])), f"missing CONSTANT area: {feature}")
    spans = []
    slots = contract.get("slots", [])
    require(bool(slots), "no approved VARIABLE slots")
    require(len({s["key"] for s in slots}) == len(slots), "duplicate VARIABLE slot key")
    for slot in slots:
        require(slot.get("field") in VARIABLE_FIELDS, "unapproved VARIABLE field")
        matches = soup.select(slot["selector"])
        require(len(matches) == 1, f"slot must identify exactly one element: {slot['key']}")
        tag = matches[0]
        require(not any(id(x) in protected for x in [tag, *tag.parents]), "CONSTANT identity/navigation/label cannot be a VARIABLE slot")
        node = by_identity[id(tag)]
        attr = slot.get("attribute")
        if attr:
            require(slot["field"] == "snapshot_timestamp" and attr in {"content", "datetime", "data-collected-at"}, "unapproved VARIABLE attribute")
            raw = html[node["start"]:node["inner_start"]]
            found = list(re.finditer(r'\s' + re.escape(attr) + r'\s*=\s*([\"\'])(.*?)\1', raw, re.S))
            require(len(found) == 1, "ambiguous/missing timestamp attribute")
            start, end = found[0].span(2)
            start += node["start"]
            end += node["start"]
        else:
            require(tag.find(True) is None and "inner_end" in node, "VARIABLE slot must contain only a leaf value")
            start, end = node["inner_start"], node["inner_end"]
            require("<" not in html[start:end], "VARIABLE slot includes markup/comment")
        spans.append((start, end, slot))
    spans.sort(key=lambda x: x[0])
    require(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), "overlapping VARIABLE slots")
    return spans


def _masked(html, contract):
    for start, end, slot in reversed(_spans(html, contract)):
        html = html[:start] + "{{VARIABLE:" + slot["key"] + "}}" + html[end:]
    return html


def _check_files(root, expected, label):
    require(bool(expected), f"missing pinned {label} hashes")
    root = Path(root).resolve()
    for relative, expected_hash in expected.items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root), f"{label} path escapes root")
        require(path.is_file() and digest(path.read_bytes()) == expected_hash, f"CONSTANT {label} changed: {relative}")


def validate_constants(*, template: bytes, candidate: bytes, contract: dict, asset_root: Path, model_root: Path):
    require(contract.get("schema_version") == 1, "unsupported CONSTANT contract")
    require(contract.get("baseline_commit"), "explicit normal baseline commit required")
    require(digest(template) == contract.get("template_sha256"), "frozen template hash mismatch")
    require(contract.get("model_version"), "pinned model version required")
    before, after = template.decode("utf-8"), candidate.decode("utf-8")
    before_mask = _masked(before, contract)
    require(before_mask == _masked(after, contract), "HARD FAIL: content outside approved VARIABLE slots changed")
    css = {tag.get("href", "").lstrip("/") for tag in BeautifulSoup(before, "html.parser").select('link[rel="stylesheet"]')}
    require(css and css <= contract.get("asset_files", {}).keys(), "every template stylesheet must be pinned")
    _check_files(asset_root, contract.get("asset_files"), "CSS/asset")
    _check_files(model_root, contract.get("model_files"), "calculation logic")
    return {"constant_integrity": "PASS", "masked_template_sha256": digest(before_mask.encode("utf-8"))}


def validate_snapshot_provenance(*, snapshot_bytes: bytes, snapshot: dict, model_result: dict, contract: dict):
    require(json.loads(snapshot_bytes) == snapshot, "parsed official snapshot differs from hashed bytes")
    require(model_result.get("validation_status") == "VALIDATED", "model result is not validated")
    require(model_result.get("model_version") == contract.get("model_version"), "model version changed")
    require(model_result.get("model_files") == contract.get("model_files"), "model provenance hashes differ from frozen calculation logic")
    require(model_result.get("input_snapshot_sha256") == digest(snapshot_bytes), "probability input is a different official snapshot")
    require(bool(snapshot.get("collected_at")) and model_result.get("input_snapshot_timestamp") == snapshot["collected_at"], "official/model snapshot timestamp mismatch")
    require(model_result.get("game_code") == snapshot.get("game_code") and model_result.get("round") == snapshot.get("round"), "probability input game/round mismatch")
    require(isinstance(model_result.get("n_simulations"), int) and model_result["n_simulations"] > 0, "missing Monte Carlo execution count")
    official = snapshot.get("player_table", [])
    ids = [str(x.get("player_code", x.get("player_id", ""))) for x in official]
    rows = model_result.get("records", [])
    result_ids = [str(x.get("player_id", "")) for x in rows]
    require(ids and all(ids) and len(ids) == len(set(ids)), "invalid official identities")
    require(set(ids) == set(result_ids) and len(result_ids) == len(set(result_ids)), "model/official field mismatch")
    for row in rows:
        values = [row.get(k) for k in ("win_pct", "top5_pct", "top10_pct", "top20_pct")]
        require(all(isinstance(v, (int, float)) and math.isfinite(v) for v in values), "missing/non-finite probability")
        require(0 <= values[0] <= values[1] <= values[2] <= values[3] <= 100, "probability range/order invalid")
    require(abs(sum(x["win_pct"] for x in rows) - 100) <= 0.0001, "win probability sum is not 100%")


def bind_snapshot_values(snapshot, result, contract):
    official = {str(x.get("player_code", x.get("player_id"))): x for x in snapshot["player_table"]}
    computed = {str(x["player_id"]): x for x in result["records"]}
    official_fields = {"rank": "rank_display", "total": "total_under_par_display",
                       "today": "today_under_par_display", "completed_holes": "holes_completed",
                       "current_hole": "raw_inghole"}
    computed_fields = {"sg": "sg", "win": "win_pct", "top5": "top5_pct",
                       "top10": "top10_pct", "top20": "top20_pct"}
    values = {}
    for slot in contract["slots"]:
        field = slot["field"]
        if field == "snapshot_timestamp":
            value = snapshot["collected_at"]
        else:
            pid = str(slot["player_id"])
            require(pid in official and pid in computed, "unmapped template player identity")
            source, key = ((official[pid], official_fields[field]) if field in official_fields
                           else (computed[pid], computed_fields[field]))
            require(key in source and source[key] is not None, f"missing computed/current value: {pid}/{field}")
            value = source[key]
        values[slot["key"]] = slot.get("format", "{}").format(value)
    return values


def inject_values(template: bytes, contract: dict, values: dict[str, str]) -> bytes:
    """Splice leaf values into original bytes; never render a replacement page."""
    html = template.decode("utf-8")
    require(digest(template) == contract.get("template_sha256"), "frozen template hash mismatch")
    spans = _spans(html, contract)
    require(values.keys() == {s[2]["key"] for s in spans}, "missing or extra VARIABLE values")
    for start, end, slot in reversed(spans):
        value = str(values[slot["key"]])
        pattern = r"[0-9TZ:+. -]+" if slot["field"] == "snapshot_timestamp" else r"(?:[+-]?\d+(?:\.\d+)?%?|T\d+|E|F)"
        require(re.fullmatch(pattern, value) is not None, f"non-value content in VARIABLE slot: {slot['key']}")
        html = html[:start] + value + html[end:]
    result = html.encode("utf-8")
    require(_masked(template.decode("utf-8"), contract) == _masked(html, contract), "HARD FAIL: injection modified CONSTANT content")
    return result


def validate_live_tree(*, candidate_root: Path, production_root: Path,
                       contract_path: Path, repository_root: Path):
    """Run before production mirroring; never infer a normal baseline.

    A manifest is mandatory once a current-round LIVE page exists. A legacy
    candidate cannot remove that route to opt out of this guard.
    """
    live_routes = [p.relative_to(production_root).as_posix()
                   for p in production_root.rglob("*.html")
                   if b"data-current-round=" in p.read_bytes()]
    if not live_routes and not contract_path.exists():
        return
    require(contract_path.is_file(), "HARD FAIL: reviewed immutable LIVE template/model contract is missing")
    contract = json.loads(contract_path.read_bytes())
    require(not (set(live_routes) - {contract["route"]}), "unprotected LIVE route outside frozen contract")

    def local_file(root, relative):
        root = root.resolve()
        path = (root / relative).resolve()
        require(path.is_relative_to(root) and path.is_file(), f"missing/unsafe contract file: {relative}")
        return path

    candidate = local_file(candidate_root, contract["route"])
    template = local_file(repository_root, contract["template_path"])
    snapshot_bytes = local_file(repository_root, contract["snapshot_path"]).read_bytes()
    snapshot = json.loads(snapshot_bytes)
    result = json.loads(local_file(repository_root, contract["model_result_path"]).read_bytes())
    validate_snapshot_provenance(snapshot_bytes=snapshot_bytes, snapshot=snapshot,
                                 model_result=result, contract=contract)
    validate_constants(template=template.read_bytes(), candidate=candidate.read_bytes(),
                       contract=contract, asset_root=candidate_root, model_root=repository_root)
    expected = inject_values(template.read_bytes(), contract, bind_snapshot_values(snapshot, result, contract))
    require(candidate.read_bytes() == expected, "HARD FAIL: HTML values do not match the current official/model snapshot")

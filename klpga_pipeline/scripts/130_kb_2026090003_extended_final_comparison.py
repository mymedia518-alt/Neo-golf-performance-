#!/usr/bin/env python3
"""Run the extended (positions 1-33 gapless) FINAL comparison for KB
2026090003 against the OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT evidence
and print the result as JSON."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.final_partial_evidence_validator import run_extended_comparison
from klpga.tournament_context import load_tournament_context


def _to_jsonable(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def main() -> None:
    context = load_tournament_context("2026090003")
    evidence_path = Path(__file__).resolve().parents[1] / "content" / "website_v2" / "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    result = run_extended_comparison(context, evidence)
    print(json.dumps(_to_jsonable(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

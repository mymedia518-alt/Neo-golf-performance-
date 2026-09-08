"""Inject current values into an explicitly frozen NEO LIVE template.

No baseline is inferred from today's production or from an arbitrary old page.
No forecasting formula or model-validation override exists in this command.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "klpga_pipeline" / "src"))

from klpga.website_v2.constant_integrity import (
    ConstantIntegrityError,
    bind_snapshot_values,
    inject_values,
    require,
    validate_constants,
    validate_snapshot_provenance,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--model-result", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    require(not args.output.resolve().is_relative_to((ROOT / "docs").resolve()), "builder cannot directly write production")
    require(args.output.resolve() != args.template.resolve(), "immutable template cannot be overwritten")
    snapshot_bytes = args.snapshot.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    result = json.loads(args.model_result.read_bytes())
    contract = json.loads(args.contract.read_bytes())
    template = args.template.read_bytes()
    validate_snapshot_provenance(snapshot_bytes=snapshot_bytes, snapshot=snapshot, model_result=result, contract=contract)
    candidate = inject_values(template, contract, bind_snapshot_values(snapshot, result, contract))
    validate_constants(template=template, candidate=candidate, contract=contract,
                       asset_root=args.asset_root, model_root=ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(candidate)
    print(f"CONSTANT_INTEGRITY_PASS: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (ConstantIntegrityError, OSError, KeyError, ValueError) as exc:
        print(f"HARD_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)

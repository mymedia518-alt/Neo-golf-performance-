"""Fail closed if protected NEO website forecast evidence has changed."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.evidence import EvidenceManifestError, load_and_verify_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evidence" / "beta001" / "manifest.json")
    args = parser.parse_args()
    try:
        verified = load_and_verify_manifest(args.manifest, REPO_ROOT)
    except EvidenceManifestError as exc:
        print(f"EVIDENCE VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 2
    for stage in ("PRE", "R1", "R2", "R3"):
        print(f"{stage}: PASS {verified[stage]}")
    print("FORECAST EVIDENCE VERIFIED: FINAL/RESULT remains separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

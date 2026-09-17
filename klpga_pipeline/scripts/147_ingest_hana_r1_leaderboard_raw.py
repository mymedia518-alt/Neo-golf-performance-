"""HANA R1 -- ingest the official Round 1 leaderboard capture as raw
evidence, verified byte-for-byte.

Source: operator-supplied HTML save of
  https://klpga.co.kr/web/leaderboard/leaderboard?gameCode=2026090002
(confirmed via the file's own `saved from url=` marker), captured after
Round 1 completed. This script only copies bytes and records a sha256
-- it does not parse or interpret the leaderboard (see
148_build_hana_r1_player_result.py for that).
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

SOURCE_PATH = Path("/root/.claude/uploads/bee7b372-e13f-52b9-816d-77030a003a04/77525182-1R_____.html")
DEST_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R1_LEADERBOARD_RAW_V1.html"


def main() -> None:
    assert SOURCE_PATH.is_file(), f"source not found: {SOURCE_PATH}"
    content = SOURCE_PATH.read_bytes()
    sha_before = hashlib.sha256(content).hexdigest()

    first_line = content.split(b"\n", 2)[1].decode("utf-8", errors="replace")
    assert "saved from url=" in first_line and "gameCode=2026090002" in first_line, (
        f"unexpected source marker, refusing to ingest: {first_line!r}"
    )

    assert not DEST_PATH.exists(), f"refusing to overwrite existing raw evidence file: {DEST_PATH}"
    DEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEST_PATH.write_bytes(content)

    sha_after = hashlib.sha256(DEST_PATH.read_bytes()).hexdigest()
    assert sha_before == sha_after, f"sha256 mismatch after write: before={sha_before} after={sha_after}"

    print(f"ingested: {DEST_PATH}")
    print(f"bytes: {len(content)}")
    print(f"sha256: {sha_after}")
    print(f"source marker: {first_line.strip()}")


if __name__ == "__main__":
    main()

"""Fail-closed atomic promotion for validated tournament candidates."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil
import tempfile


class PromotionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class PromotionResult:
    target: Path
    before_sha256: str | None
    after_sha256: str
    changed: bool


def file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def validate_candidate_for_promotion(
    candidate_path: Path,
    *,
    expected_game_code: str,
    expected_round_number: int,
    expected_factual_sha256: str,
) -> str:
    candidate_path = Path(candidate_path)

    if not candidate_path.is_file():
        raise PromotionBlocked("candidate missing")

    raw = candidate_path.read_bytes()

    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromotionBlocked("candidate is not valid UTF-8") from exc

    required = [
        'content="factual-only"',
        f'content="{expected_game_code}"',
        f'content="{expected_round_number}"',
        f'content="{expected_factual_sha256}"',
    ]

    for token in required:
        if token not in html:
            raise PromotionBlocked(
                f"candidate binding missing: {token}"
            )

    forbidden = [
        "win_pct",
        "top5_pct",
        "top10_pct",
        "top20_pct",
        "make_cut_pct",
    ]

    for token in forbidden:
        if token in html:
            raise PromotionBlocked(
                f"model content leaked into factual candidate: {token}"
            )

    # Mojibake / replacement-character hard gate.
    if "\ufffd" in html:
        raise PromotionBlocked("UTF-8 replacement character detected")

    return file_sha256(candidate_path)


def atomic_promote(
    candidate_path: Path,
    target_path: Path,
    *,
    expected_game_code: str,
    expected_round_number: int,
    expected_factual_sha256: str,
) -> PromotionResult:
    candidate_path = Path(candidate_path)
    target_path = Path(target_path)

    candidate_sha = validate_candidate_for_promotion(
        candidate_path,
        expected_game_code=expected_game_code,
        expected_round_number=expected_round_number,
        expected_factual_sha256=expected_factual_sha256,
    )

    before_sha = (
        file_sha256(target_path)
        if target_path.exists()
        else None
    )

    target_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=".neo-promote-",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)

    try:
        shutil.copyfile(candidate_path, temp_path)

        temp_sha = file_sha256(temp_path)
        if temp_sha != candidate_sha:
            raise PromotionBlocked(
                "temporary promotion copy SHA mismatch"
            )

        # os.replace is atomic on the same filesystem.
        os.replace(temp_path, target_path)

    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    after_sha = file_sha256(target_path)

    if after_sha != candidate_sha:
        raise PromotionBlocked(
            "post-promotion SHA mismatch"
        )

    return PromotionResult(
        target=target_path,
        before_sha256=before_sha,
        after_sha256=after_sha,
        changed=(before_sha != after_sha),
    )

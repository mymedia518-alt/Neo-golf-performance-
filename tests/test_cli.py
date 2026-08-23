"""Smoke tests: every CLI module imports cleanly and --help works."""
import subprocess
import sys


def _run(module: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True, text=True, timeout=30,
    )


def test_collect_help():
    result = _run("klpga.collect", "--help")
    assert result.returncode == 0
    assert "events" in result.stdout


def test_validate_help():
    result = _run("klpga.validate", "--help")
    assert result.returncode == 0


def test_export_help():
    result = _run("klpga.export", "--help")
    assert result.returncode == 0


def test_features_help():
    result = _run("klpga.features", "--help")
    assert result.returncode == 0


def test_predict_help():
    result = _run("klpga.predict", "--help")
    assert result.returncode == 0

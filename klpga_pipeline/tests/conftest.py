import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# QA HARD STOP remediation (test/build isolation): many tests deliberately
# call a real scripts/NN_....py build() function -- exercising the
# actual generated HTML rather than a mock -- and those build()
# functions write to their own module-level OUTPUT/OUT constant, which
# used to hardcode the real, git-tracked candidate/ directory. Running
# the suite therefore mutated tracked repository files every time (a
# fresh neo-build-id/neo-build-source-commit provenance stamp on every
# generated page, never real content -- see
# klpga.website_v2.global_navigation.inject_build_provenance -- but a
# real repository-hygiene defect regardless of how harmless the diff
# itself is).
#
# pytest_configure runs once per test session, before any test module
# (and therefore before any scripts/NN_....py the tests import) is
# collected -- setting KLPGA_CANDIDATE_ROOT_OVERRIDE here means every
# build script's own OUTPUT/OUT (resolved through
# klpga.tournament_context.candidate_dir(), not a hardcoded path)
# writes into this disposable temp directory instead, with zero
# per-test-file changes required. A real `python scripts/NN_....py`
# invocation outside pytest never sees this env var and is unaffected.
_CANDIDATE_ROOT_OVERRIDE = tempfile.mkdtemp(prefix="klpga-test-candidate-")


def pytest_configure(config):
    os.environ["KLPGA_CANDIDATE_ROOT_OVERRIDE"] = _CANDIDATE_ROOT_OVERRIDE


def pytest_unconfigure(config):
    os.environ.pop("KLPGA_CANDIDATE_ROOT_OVERRIDE", None)
    shutil.rmtree(_CANDIDATE_ROOT_OVERRIDE, ignore_errors=True)

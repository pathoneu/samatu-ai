"""Top-level conftest.

Why: tests import via `from main import app`, `from extractor.X import ...`,
`from api.Y import ...` — i.e. with the backend directory on sys.path.
When pytest is invoked with a specific test file (rather than discovering
from cwd), it doesn't add cwd to sys.path and the imports fail. This
conftest guarantees the backend directory is always on sys.path.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_experiment_envs(monkeypatch):
    """Hermeticity guard (2026-07-04): the accuracy-A/B experiment envs are
    behavior switches for the extraction pipeline. If the controller (or a
    developer shell) has one exported, ambient state would flip pipeline
    behavior mid-suite and fail default-path assertions.

    SAMATU_PDF_NATIVE is PINNED OFF (not merely cleared): since the B-3
    lock-in, native-PDF Pass-1 is the production default, but the suite's
    raster-path tests encode raster expectations — pinning =0 keeps their
    intent honest without touching each test. Native-mode tests opt in
    explicitly (monkeypatch.setenv SAMATU_PDF_NATIVE=1 / delenv for the
    default-ON gate test). The other experiment envs stay opt-in → cleared."""
    monkeypatch.setenv("SAMATU_PDF_NATIVE", "0")
    for env in ("SAMATU_ZOOM_AGENTIC", "SAMATU_VOTING_MODELS"):
        monkeypatch.delenv(env, raising=False)


def pytest_configure(config):
    """Register custom marks so pytest doesn't warn on first use.
    `integration` gates real-PDF / real-API tests; CI runs them via
    `pytest -m integration` separately from the fast unit suite."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that hit real PDFs or external services",
    )

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
    opt-in behavior switches for the extraction pipeline. If the controller
    (or a developer shell) has one exported, ambient state would flip
    pipeline behavior mid-suite and fail default-path assertions. Clear them
    for every test; experiment tests set them explicitly via monkeypatch."""
    for env in ("SAMATU_PDF_NATIVE", "SAMATU_ZOOM_AGENTIC",
                "SAMATU_VOTING_MODELS"):
        monkeypatch.delenv(env, raising=False)


def pytest_configure(config):
    """Register custom marks so pytest doesn't warn on first use.
    `integration` gates real-PDF / real-API tests; CI runs them via
    `pytest -m integration` separately from the fast unit suite."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that hit real PDFs or external services",
    )

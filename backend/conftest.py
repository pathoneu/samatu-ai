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
def _reset_rate_limiter():
    """Hermeticity: main._RATE_BUCKET is a module-global 60s sliding-window rate
    limiter keyed by client IP. Under TestClient every request comes from the same
    IP ("testclient"), so logins/registrations/log-error POSTs accumulate across
    tests and can trip the 30/min cap in a LATER test — an order-dependent 429
    flake (surfaced 2026-07-05 when the login-heavy admin-v2 suite pushed
    test_f2_session_invalidation over the edge). Clearing the bucket before each
    test makes every test start from an empty window. Rate-limit tests that need a
    FULL bucket fill it within their own body (range(N) POSTs), so a pre-test
    clear never weakens them — several already call this exact clear manually
    (test_f7_log_error_hardening, test_log_error_body_cap)."""
    try:
        import main
        main._RATE_BUCKET.clear()
    except Exception:
        pass  # main not importable in a pure-unit context → nothing to reset
    yield


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


@pytest.fixture(autouse=True)
def _reset_pdf_page_cache():
    """Hermeticity guard (2026-08-03): `extractor.pdf_page_cache` memoises the
    single pdfplumber parse, keyed on sha256(pdf_bytes).

    That key is exactly right in production — the same bytes always yield the
    same text — but it bleeds across tests, because tests inject fake
    documents by patching the shared `pdfplumber` module object while passing
    a stub like `b"x"` as the bytes. Two tests with different fake pages then
    collide on one cache key and the second silently reads the first one's
    pages. Clearing between tests keeps each test's fake document its own.
    """
    try:
        from extractor.pdf_page_cache import clear
    except Exception:
        yield
        return
    clear()
    yield
    clear()


@pytest.fixture
def lt_aperture_1m2(monkeypatch):
    """Pin the older LT opening rule (an opening of 1,0 m² or more is deducted) for tests written to check the
    MECHANICS of deducting a door or window. The `lt_rangovas` default became 3,0 m² on 2026-10-25 (rangovo
    taisyklė); `tests/test_rules_profile.py` covers the default itself."""
    import dataclasses
    from rules import conventions
    p = conventions.LT_RANGOVAS["aperture_no_deduct_max_m2"]
    monkeypatch.setitem(conventions.LT_RANGOVAS, "aperture_no_deduct_max_m2", dataclasses.replace(p, default=1.0))


@pytest.fixture(scope="module")
def lt_aperture_1m2_module():
    """`lt_aperture_1m2` for a module whose module-scoped fixtures compute the rooms once."""
    import dataclasses
    from rules import conventions
    p = conventions.LT_RANGOVAS["aperture_no_deduct_max_m2"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(conventions.LT_RANGOVAS, "aperture_no_deduct_max_m2", dataclasses.replace(p, default=1.0))
        yield


def pytest_configure(config):
    """Register custom marks so pytest doesn't warn on first use.
    `integration` marks real-PDF / real-API tests. Nothing deselects it: CI
    (.github/workflows/ci.yml) runs the whole suite in one pass, integration
    tests included, against whichever fixture PDFs are tracked. Locally,
    `-m "not integration"` leaves them out."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that hit real PDFs or external services",
    )

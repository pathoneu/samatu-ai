"""Credentials are not consent: dev and tests must never write to the live bucket.

`get_storage()` used to pick R2 the moment the four R2_* vars existed. They live
in `backend/.env`, so a developer's server and the entire test suite wrote into
the PRODUCTION bucket — on 2026-09-02/04 that put 35 test-seed objects into the
live `projects/` prefix, alongside real customers' drawings.

R2 now needs a second signal that this process is allowed to use the bucket:
ENV=production, or an explicit STORAGE_BACKEND=r2. This file is the env matrix.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage  # noqa: E402

R2_ENV = {
    "R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "ak",
    "R2_SECRET_ACCESS_KEY": "sk", "R2_BUCKET": "a-bucket",
}
_ALL = tuple(R2_ENV) + ("STORAGE_BACKEND", "ENV", "ENVIRONMENT",
                        "RAILWAY_ENVIRONMENT", "RENDER", "LOCAL_STORAGE_DIR",
                        "SAMATU_DATA_DIR")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in _ALL:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    yield
    storage.reset_storage_for_test()


def _env(monkeypatch, *, creds: bool, env: str | None = None,
         backend: str | None = None):
    if creds:
        for k, v in R2_ENV.items():
            monkeypatch.setenv(k, v)
    if env is not None:
        monkeypatch.setenv("ENV", env)
    if backend is not None:
        monkeypatch.setenv("STORAGE_BACKEND", backend)


# ── The matrix ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("creds, env, backend, want", [
    # No credentials → local, whatever anything else says.
    (False, None,         None,    "local"),
    (False, "production", None,    "local"),
    (False, None,         "r2",    "local"),   # cannot honour an impossible ask
    # Credentials present but no permission → LOCAL. This is the whole fix:
    # a dev box and the test suite carry these vars via backend/.env.
    (True,  None,         None,    "local"),
    (True,  "development", None,   "local"),
    (True,  "staging",    None,    "local"),
    (True,  "test",       None,    "local"),
    # …and the two ways to say yes.
    (True,  "production", None,    "r2"),
    (True,  None,         "r2",    "r2"),
    (True,  "development", "r2",   "r2"),
    # An explicit opt-out wins, even in production (the ERROR still fires).
    (True,  "production", "local", "local"),
    (True,  None,         "local", "local"),
    # An unrecognised value is not a permission.
    (True,  None,         "s3",    "local"),
    (True,  None,         "",      "local"),
])
def test_backend_selection_matrix(monkeypatch, creds, env, backend, want):
    _env(monkeypatch, creds=creds, env=env, backend=backend)
    assert storage.selected_backend_name() == want
    assert storage.r2_decision()[0] is (want == "r2")


def test_storage_backend_value_is_case_and_space_insensitive(monkeypatch):
    _env(monkeypatch, creds=True, backend="  R2  ")
    assert storage.selected_backend_name() == "r2"


def test_selected_name_agrees_with_the_object_actually_built(monkeypatch):
    _env(monkeypatch, creds=True)
    assert storage.selected_backend_name() == "local"
    assert storage.get_storage().name == "LocalDiskStorage"


def test_a_dev_box_with_full_credentials_writes_to_local_disk(monkeypatch,
                                                              tmp_path):
    """The regression itself: put() must land on disk, not in the bucket."""
    _env(monkeypatch, creds=True)
    storage.get_storage().put("projects/p1.pdf", b"%PDF-1.7 synthetic")
    written = list((tmp_path / "pdfs").rglob("*.pdf"))
    assert [p.name for p in written] == ["p1.pdf"]
    assert storage.get_storage().get("projects/p1.pdf") == b"%PDF-1.7 synthetic"


# ── The one-line "which backend and why" ─────────────────────────────────────
def _records(caplog):
    return [r for r in caplog.records if r.name == "samatu.storage"]


def test_deliberate_local_says_which_backend_and_why_at_info(monkeypatch,
                                                             caplog):
    _env(monkeypatch, creds=True)
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        storage.get_storage()
    rec = _records(caplog)
    assert len(rec) == 1, [r.getMessage() for r in rec]
    assert rec[0].levelno == logging.INFO
    msg = rec[0].getMessage()
    assert "LOCAL DISK" in msg
    assert "ENV=production" in msg and "STORAGE_BACKEND=r2" in msg


def test_missing_credentials_still_warn_and_name_them(monkeypatch, caplog):
    """A partial/absent R2 config is a real misconfiguration on a box that meant
    to have one, so it keeps the louder level and still names the gap."""
    _env(monkeypatch, creds=False)
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        storage.get_storage()
    rec = _records(caplog)
    assert rec[-1].levelno == logging.WARNING
    assert "R2_BUCKET" in rec[-1].getMessage()


def test_production_on_local_disk_is_still_an_error(monkeypatch, caplog):
    _env(monkeypatch, creds=True, env="production", backend="local")
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        assert storage.get_storage().name == "LocalDiskStorage"
    rec = _records(caplog)
    assert rec[-1].levelno == logging.ERROR
    assert "NOT durable" in rec[-1].getMessage()
    assert "STORAGE_BACKEND=local" in rec[-1].getMessage()


def test_r2_selection_logs_the_reason_it_was_allowed(monkeypatch, caplog):
    _env(monkeypatch, creds=True, backend="r2")
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        assert storage.get_storage().name == "R2Storage"
    rec = _records(caplog)
    assert rec[-1].levelno == logging.INFO
    msg = rec[-1].getMessage()
    assert "a-bucket" in msg and "STORAGE_BACKEND=r2" in msg


@pytest.mark.parametrize("env, backend, fragment", [
    (None, None, "credentials present but unused"),
    ("production", None, "ENV=production"),
    (None, "r2", "STORAGE_BACKEND=r2"),
    (None, "local", "STORAGE_BACKEND=local"),
])
def test_every_decision_explains_itself(monkeypatch, env, backend, fragment):
    _env(monkeypatch, creds=True, env=env, backend=backend)
    assert fragment in storage.r2_decision()[1]


def test_missing_var_names_appear_in_the_reason(monkeypatch):
    for k, v in R2_ENV.items():
        if k != "R2_BUCKET":
            monkeypatch.setenv(k, v)
    ok, why = storage.r2_decision()
    assert ok is False and "R2_BUCKET" in why


# ── A deploy is recognised the way the rest of the backend recognises it ────
@pytest.mark.parametrize("var, value, want", [
    ("ENV", "production", "r2"),
    ("ENV", "prod", "r2"),                       # main.py / auth.py accept both
    ("ENV", "Production ", "r2"),                # case and whitespace as elsewhere
    ("ENVIRONMENT", "production", "r2"),
    ("RAILWAY_ENVIRONMENT", "production", "r2"),  # what the Railway deploy sets
    ("RENDER", "true", "r2"),                    # what a Render deploy sets
    ("RAILWAY_ENVIRONMENT", "staging", "local"),  # a preview environment is not prod
    ("ENV", "development", "local"),
])
def test_every_production_signal_selects_r2_with_credentials(monkeypatch, var, value, want):
    """2026-09-15: the rule read `ENV == "production"` exactly. The Railway deploy
    does not necessarily set ENV, so with credentials present it would have
    fallen to the container's disk — every upload lost on the next deploy."""
    _env(monkeypatch, creds=True)
    monkeypatch.setenv(var, value)
    use_r2, why = storage.r2_decision()
    assert (use_r2, storage.selected_backend_name()) == (want == "r2", want)
    if want == "r2":
        assert why == f"{var}=production" or why == "RENDER=true"
    else:
        assert "credentials present but unused" in why


def test_a_production_signal_without_credentials_is_still_local(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    use_r2, why = storage.r2_decision()
    assert not use_r2 and storage.selected_backend_name() == "local"
    assert "missing" in why

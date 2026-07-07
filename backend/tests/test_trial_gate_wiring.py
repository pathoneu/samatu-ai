"""W3 Phase 5 (re-placed 2026-07-04) — trial gate WIRED into the project-CREATING
extraction, POST /extract-interior.

The free-trial company-code gate must run on the endpoint that CREATES (and
counts) a project — /extract-interior — before any extraction work, and its HTTP
rejections (403 company_code_required / 402 trial_used) must reach the client. A
free user without a company code gets 403; the same user with a consumed trial
gets 402; a fresh free trial is allowed; flag OFF ⇒ the gate never fires.

(Originally this exercised the gate through auth.require_billable_user. That was
the WRONG seam — corrections must not be trial-gated — so the paywall moved to
/extract-interior; this test moved with it. Corrections keeping spend-cap-only is
locked down in test_quota_gate_placement.py.)

ISOLATION: fresh temp DB per test; Vision fully mocked; the € spend cap patched
to a no-op so any 402/403 is the TRIAL/QUOTA gate, never a masked 429.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402 — import app before `import auth` (load_dotenv order)

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import extractor  # noqa: E402
import billing.trial as trial  # noqa: E402

_PW = "passw0rd123"
_COMPANY = "302536741"


def _isolate(tmp_path, monkeypatch, name="wiring.db"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _mock_vision(monkeypatch):
    monkeypatch.setattr(main, "_validate_pdf_upload",
                        lambda pdf_bytes, name="": {"page_count": 1})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(main, "_check_user_spend_cap", lambda user_id: None)
    monkeypatch.setattr(extractor, "extract_interior",
                        lambda pdf_bytes, overrides: {"rooms": [], "_meta": {}})


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _post_extract(client):
    return client.post(
        "/extract-interior",
        files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )


def test_extract_interior_403_free_user_no_company(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    db.create_user("a@b.lt", auth.hash_password(_PW), name="A")  # free, no company_code
    c = _login("a@b.lt")
    r = _post_extract(c)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "company_code_required"


def test_extract_interior_402_free_user_trial_used(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    user = db.create_user("c@d.lt", auth.hash_password(_PW), name="C")
    db.set_user_company(user["id"], _COMPANY)
    trial.consume_trial(_COMPANY, user_id=user["id"])  # company's trial already spent
    c = _login("c@d.lt")
    r = _post_extract(c)
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["error"] == "trial_used"


def test_extract_interior_allows_fresh_free_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    user = db.create_user("e@f.lt", auth.hash_password(_PW), name="E")
    db.set_user_company(user["id"], _COMPANY)
    c = _login("e@f.lt")
    r = _post_extract(c)  # fresh trial + free quota slot → must succeed
    assert r.status_code == 200, r.text
    assert r.json() == {"rooms": [], "_meta": {}}


def test_extract_interior_noop_when_flag_off(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _mock_vision(monkeypatch)
    db.create_user("g@h.lt", auth.hash_password(_PW), name="G")  # free, no company_code
    c = _login("g@h.lt")
    r = _post_extract(c)  # flag OFF ⇒ gate never fires
    assert r.status_code == 200, r.text
    assert r.json() == {"rooms": [], "_meta": {}}

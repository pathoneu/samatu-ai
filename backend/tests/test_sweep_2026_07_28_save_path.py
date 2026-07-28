"""2026-07-28 improvement sweep — the project SAVE path (F7 + F8).

F8 — LOST UPDATE. `PUT /api/projects/{id}` replaced the stored blob with zero
conflict detection, so the sweep reproduced this in two tabs:

    Tab A loads project, edits a price      Tab B loads the SAME project
                                            Tab B renames it and saves
    Tab A saves  →  Tab B's rename gone, or the reverse, silently either way.

The fix ships the DETECTION half only (no merge UI): the client echoes back the
`updated_at` it last saw as `base_updated_at`; the backend compares it to the
stored row INSIDE the write lock and answers 409 instead of overwriting.
Back-compat is load-bearing — a PUT with NO `base_updated_at` must behave
exactly as it did before (older clients, scripts, the demo-restore flow).

F7 — the PDF stream endpoint sent no validator, so the viewer re-downloaded the
whole drawing on every tab switch, and it called db.get_project (a full ~175 KB
blob parse) purely to answer "does this exist and is it mine?".
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import storage as _storage  # noqa: E402

_PW = "passw0rd123"
_PDF = b"%PDF-1.4\n" + b"sweep-2026-07-28 drawing bytes\n" * 40


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "sweep_save.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    # main.py load_dotenv()s the developer's .env, which carries REAL R2
    # credentials — without this the PDF tests below would read and write the
    # production bucket. Same guard as tests/test_storage.py.
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET", "SAMATU_DATA_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdf_store"))
    monkeypatch.setattr(_storage, "_instance", None)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("other@x.lt", auth.hash_password(_PW), name="Other")
    db.upsert_project("proj-A", {"name": "Projektas A", "tipas": "interjeras"},
                      user_id=owner["id"])
    yield {"owner_id": owner["id"]}
    monkeypatch.setattr(_storage, "_instance", None)


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


# ── F8: lost-update detection ────────────────────────────────────────────────

def test_f8_stale_base_updated_at_is_rejected_and_row_unchanged(env):
    c = _login("owner@x.lt")
    tab_a_saw = c.get("/api/projects/proj-A").json()["updated_at"]

    # db._now_iso() has ONE-SECOND granularity, so the detector cannot see two
    # writes that land inside the same wall-clock second (documented blind spot,
    # see test_f8_same_second_writes_are_a_known_blind_spot). Step over a second
    # boundary so this test exercises the real two-tab timeline.
    time.sleep(1.05)

    # Tab B saves first (no base — a legacy client, which must still work).
    assert c.put("/api/projects/proj-A",
                 json={"name": "Pervadinta B", "tipas": "interjeras"}).status_code == 200
    after_b = c.get("/api/projects/proj-A").json()
    assert after_b["name"] == "Pervadinta B"

    # Tab A now saves against the timestamp it loaded → must be refused.
    r = c.put("/api/projects/proj-A", json={
        "name": "Pervadinta A", "tipas": "interjeras",
        "base_updated_at": tab_a_saw,
    })
    assert r.status_code == 409, r.text
    assert r.json()["error"] == "conflict"
    assert r.json()["current_updated_at"] == after_b["updated_at"]

    # And B's work is still there — the whole point.
    still = c.get("/api/projects/proj-A").json()
    assert still["name"] == "Pervadinta B"
    assert still["updated_at"] == after_b["updated_at"]


def test_f8_same_second_writes_are_a_known_blind_spot(env):
    """HONEST LIMIT, asserted so it can never become a silent surprise.

    `updated_at` is written by db._now_iso() at one-second resolution. Two saves
    inside the same second therefore leave the stored timestamp looking
    unchanged and the second one goes through. Raising the resolution would mean
    mixing two formats in one column (existing rows keep "…:25Z" while new ones
    would read "…:25.123Z"), which breaks the lexicographic ORDER BY updated_at
    and the backup-merge comparison — a bigger regression than the hole it
    closes. The realistic two-tab case is seconds apart and IS caught (see the
    test above); this narrow window needs FOUR events (write, load, write, write)
    inside one second.
    """
    c = _login("owner@x.lt")
    seen = c.get("/api/projects/proj-A").json()["updated_at"]
    c.put("/api/projects/proj-A", json={"name": "kito lango irašas", "tipas": "interjeras"})
    r = c.put("/api/projects/proj-A",
              json={"name": "mano irašas", "tipas": "interjeras", "base_updated_at": seen})
    if c.get("/api/projects/proj-A").json()["updated_at"] == seen:
        assert r.status_code == 200      # same second → undetectable, documented
    else:
        assert r.status_code == 409      # crossed a second boundary → detected


def test_f8_fresh_base_updated_at_is_accepted(env):
    c = _login("owner@x.lt")
    current = c.get("/api/projects/proj-A").json()["updated_at"]
    r = c.put("/api/projects/proj-A", json={
        "name": "Šviežias", "tipas": "interjeras", "base_updated_at": current,
    })
    assert r.status_code == 200, r.text
    assert c.get("/api/projects/proj-A").json()["name"] == "Šviežias"


def test_f8_absent_base_updated_at_behaves_exactly_as_before(env):
    """BACK-COMPAT GATE. Scripts, the demo-restore full-blob PUT and any older
    tab send no base — they must never see a 409."""
    c = _login("owner@x.lt")
    for name in ("v1", "v2", "v3"):
        r = c.put("/api/projects/proj-A", json={"name": name, "tipas": "interjeras"})
        assert r.status_code == 200, r.text
    assert c.get("/api/projects/proj-A").json()["name"] == "v3"


def test_f8_base_updated_at_never_lands_in_the_stored_blob(env):
    """It is a protocol field, not project data."""
    c = _login("owner@x.lt")
    current = c.get("/api/projects/proj-A").json()["updated_at"]
    c.put("/api/projects/proj-A",
          json={"name": "X", "tipas": "interjeras", "base_updated_at": current})
    assert "base_updated_at" not in c.get("/api/projects/proj-A").json()


def test_f8_base_on_a_project_that_does_not_exist_yet_creates_it(env):
    c = _login("owner@x.lt")
    r = c.put("/api/projects/brand-new",
              json={"name": "Naujas", "tipas": "interjeras",
                    "base_updated_at": "2026-01-01T00:00:00Z"})
    assert r.status_code == 200, r.text


def test_f8_ownership_still_wins_over_conflict(env):
    """A cross-tenant write is a 403, not a 409 — the conflict check must not
    become an ownership oracle."""
    other = _login("other@x.lt")
    r = other.put("/api/projects/proj-A", json={
        "name": "Pavogta", "tipas": "interjeras",
        "base_updated_at": "1999-01-01T00:00:00Z",
    })
    assert r.status_code == 403, r.text


def test_f8_db_layer_raises_conflict_and_leaves_the_row_alone(env):
    db.upsert_project("proj-A", {"name": "Naujausias"}, user_id=env["owner_id"])
    with pytest.raises(db.ProjectConflictError):
        db.upsert_project("proj-A", {"name": "Sena"}, user_id=env["owner_id"],
                          base_updated_at="2020-01-01T00:00:00Z")
    assert db.get_project("proj-A")["name"] == "Naujausias"


# ── F7: PDF caching + cheap existence check ──────────────────────────────────

def _put_pdf(c: TestClient) -> None:
    r = c.post("/api/projects/proj-A/pdf",
               files={"pdf_file": ("d.pdf", _PDF, "application/pdf")})
    assert r.status_code == 200, r.text


def test_f7_pdf_get_sends_a_validator_and_a_private_cache_policy(env):
    c = _login("owner@x.lt")
    _put_pdf(c)
    r = c.get("/api/projects/proj-A/pdf")
    assert r.status_code == 200
    assert r.content == _PDF
    assert r.headers["Cache-Control"] == "private, max-age=3600"
    assert r.headers["ETag"].startswith('"')


def test_f7_conditional_get_returns_304_with_an_empty_body(env):
    c = _login("owner@x.lt")
    _put_pdf(c)
    etag = c.get("/api/projects/proj-A/pdf").headers["ETag"]
    r = c.get("/api/projects/proj-A/pdf", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["ETag"] == etag


def test_f7_etag_changes_when_the_drawing_is_replaced(env):
    c = _login("owner@x.lt")
    _put_pdf(c)
    first = c.get("/api/projects/proj-A/pdf").headers["ETag"]
    r = c.post("/api/projects/proj-A/pdf",
               files={"pdf_file": ("d.pdf", _PDF + b"\n% revised", "application/pdf")})
    assert r.status_code == 200
    second = c.get("/api/projects/proj-A/pdf").headers["ETag"]
    assert second != first
    # ...and the stale validator must NOT be honoured.
    assert c.get("/api/projects/proj-A/pdf",
                 headers={"If-None-Match": first}).status_code == 200


def test_f7_ownership_still_enforced_on_the_pdf_route(env):
    """project_exists() replaced get_project() — it must keep the same gate."""
    owner = _login("owner@x.lt")
    _put_pdf(owner)
    other = _login("other@x.lt")
    assert other.get("/api/projects/proj-A/pdf").status_code == 404
    # ...including the conditional path, so an ETag can't leak existence.
    etag = owner.get("/api/projects/proj-A/pdf").headers["ETag"]
    assert other.get("/api/projects/proj-A/pdf",
                     headers={"If-None-Match": etag}).status_code == 404


def test_f7_project_exists_matches_get_project_semantics(env):
    assert db.project_exists("proj-A") is True
    assert db.project_exists("proj-A", user_id=env["owner_id"]) is True
    assert db.project_exists("proj-A", user_id="somebody-else") is False
    assert db.project_exists("no-such-project") is False


def test_f7_missing_drawing_is_still_a_404_not_a_304(env):
    c = _login("owner@x.lt")
    r = c.get("/api/projects/proj-A/pdf", headers={"If-None-Match": '"anything"'})
    assert r.status_code == 404


# ── F4: gzip ─────────────────────────────────────────────────────────────────

def test_f4_large_json_is_gzipped_and_tiny_json_is_not(env):
    c = _login("owner@x.lt")
    # Make the blob comfortably larger than minimum_size=1024.
    db.upsert_project("proj-A", {
        "name": "Didelis", "tipas": "interjeras",
        "patalpos": [{"nr": i, "pavadinimas": f"Patalpa {i}", "plotas_m2": 12.34}
                     for i in range(60)],
    }, user_id=env["owner_id"])
    big = c.get("/api/projects/proj-A", headers={"Accept-Encoding": "gzip"})
    assert big.status_code == 200
    assert big.headers.get("content-encoding") == "gzip"
    # The payload must survive the round trip byte-for-byte.
    plain = c.get("/api/projects/proj-A", headers={"Accept-Encoding": "identity"})
    assert plain.headers.get("content-encoding") is None
    assert big.json() == plain.json()
    # The compressed response is chunked (the outer security-headers
    # BaseHTTPMiddleware streams it), so Content-Length is dropped rather than
    # rewritten — the size win is measured against a live server, not here.
    assert "content-length" not in big.headers

    # /health is skipped explicitly: `minimum_size` cannot fire in this app
    # (an inner BaseHTTPMiddleware streams every response, and starlette's size
    # check only runs on the single-chunk path), so without the skip a 25-byte
    # body would come back gzipped and BIGGER.
    tiny = c.get("/health", headers={"Accept-Encoding": "gzip"})
    assert tiny.headers.get("content-encoding") is None
    assert tiny.json()["status"] == "ok"


def test_f4_already_compressed_binaries_are_not_re_gzipped(env):
    """PDFs and .xlsx are compressed containers — gzip buys ~6-9% for real CPU
    (measured: 56 KB PDF, 1.09x, 0.7 ms → ~12 ms per MB on the viewer's hot
    path). The middleware skips those routes."""
    c = _login("owner@x.lt")
    _put_pdf(c)
    r = c.get("/api/projects/proj-A/pdf", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") is None
    assert r.content == _PDF

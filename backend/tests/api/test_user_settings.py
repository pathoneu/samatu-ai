"""Company details + logo stored per user on the server (audit 2026-09-29,
frontend-architecture-3).

They used to live only in the browser's `samatu_settings`, which the auth layer
purges at every login and logout on purpose — so every re-login silently took
the logo, IBAN and company codes out of his exports. GET/PUT /api/settings is
now the durable copy, always scoped to the SESSION's user.

Real accounts through /api/auth/register + /api/auth/login with auth switched
ON for this module. Invented values only.
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402  (must precede `import auth` so load_dotenv runs first)
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"
_A_SETTINGS = {
    "company_name": "UAB Pirmoji Įmonė",
    "vat_rate": 21,
    "imones_kodas": "300000001",
    "pvm_kodas": "LT100000000001",
    "iban": "LT000000000000000001",
    "adresas": "Pirmoji g. 1, Kaunas",
    "vadovas": "Vardenis Pavardenis",
    # Unknown keys are stored as given: the server does not interpret them.
    "kita": {"nested": [1, 2, 3], "tekstas": "ąčęėįšųūž"},
}


@pytest.fixture(scope="module")
def clients(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(db, "_DB_PATH", tmp_path_factory.mktemp("usrset") / "set.db")
        mp.setattr(auth, "AUTH_DISABLED", False)
        mp.setenv("SAMATU_ADMIN_EMAIL", "nobody@invalid.lt")  # neither user is admin
        db.init_schema()
        db._migrate_schema()
        main._RATE_BUCKET.clear()
        out = {}
        for who in ("a", "b"):
            c = TestClient(app)
            email = f"{who}-settings@x.lt"
            r = c.post("/api/auth/register", json={"email": email, "password": _PW})
            assert r.status_code == 200, r.text
            r = c.post("/api/auth/login", json={"email": email, "password": _PW})
            assert r.status_code == 200, r.text
            out[who] = (c, db.get_user_by_email(email))
        out["anon"] = (TestClient(app), None)
        yield out


@pytest.fixture(autouse=True)
def _fresh_rate_bucket():
    main._RATE_BUCKET.clear()
    yield
    main._RATE_BUCKET.clear()


def test_signed_out_is_401(clients):
    anon, _ = clients["anon"]
    assert anon.get("/api/settings").status_code == 401
    assert anon.put("/api/settings", json={"company_name": "X"}).status_code == 401


def test_round_trip_returns_what_was_stored(clients):
    a, _ = clients["a"]
    # A logo is stored as a data URL — about as large as the client lets it be
    # (a 500 KB file is ~670 KB once base64-encoded).
    logo = "data:image/png;base64," + ("A" * 680_000)
    payload = {**_A_SETTINGS, "company_logo": logo}
    r = a.put("/api/settings", json=payload)
    assert r.status_code == 200, r.text
    r = a.get("/api/settings")
    assert r.status_code == 200
    assert r.json() == payload


def test_new_user_gets_an_empty_object(clients):
    b, _ = clients["b"]
    # Fresh module DB: B has never saved anything.
    with db._conn() as c:
        c.execute("DELETE FROM user_settings WHERE user_id = ?", (clients["b"][1]["id"],))
    r = b.get("/api/settings")
    assert r.status_code == 200
    assert r.json() == {}


def test_other_user_never_sees_or_overwrites(clients):
    a, user_a = clients["a"]
    b, user_b = clients["b"]
    assert a.put("/api/settings", json=_A_SETTINGS).status_code == 200

    # B sees nothing of A's.
    body = b.get("/api/settings").text
    assert "Pirmoji" not in body and "300000001" not in body

    # B cannot aim a write at A: an owner in the body or the query is ignored,
    # the write lands on B's own row.
    r = b.put(f"/api/settings?user_id={user_a['id']}",
              json={"company_name": "UAB Antroji", "user_id": user_a["id"]})
    assert r.status_code == 200, r.text
    assert a.get("/api/settings").json() == _A_SETTINGS
    assert b.get("/api/settings").json() == {"company_name": "UAB Antroji",
                                            "user_id": user_a["id"]}
    with db._conn() as c:
        rows = {r["user_id"]: json.loads(r["data"])
                for r in c.execute("SELECT user_id, data FROM user_settings")}
    assert rows[user_a["id"]] == _A_SETTINGS
    assert rows[user_b["id"]]["company_name"] == "UAB Antroji"


def test_oversize_is_413_with_a_plain_lt_message(clients):
    a, _ = clients["a"]
    assert a.put("/api/settings", json=_A_SETTINGS).status_code == 200
    huge = {**_A_SETTINGS, "company_logo": "data:image/png;base64," + "A" * 1_700_000}
    r = a.put("/api/settings", json=huge)
    assert r.status_code == 413
    detail = r.json()["detail"]
    assert "logotip" in detail.lower()
    # Nothing was stored: the previous copy is intact.
    assert a.get("/api/settings").json() == _A_SETTINGS


@pytest.mark.parametrize("body", [
    json.dumps([1, 2, 3]),
    json.dumps("tekstas"),
    json.dumps(42),
    json.dumps(None),
    "{ne json",
    "",
])
def test_only_a_json_object_is_accepted(clients, body):
    a, _ = clients["a"]
    assert a.put("/api/settings", json=_A_SETTINGS).status_code == 200
    r = a.put("/api/settings", content=body.encode(),
              headers={"Content-Type": "application/json"})
    assert r.status_code == 400, (body, r.status_code, r.text)
    assert a.get("/api/settings").json() == _A_SETTINGS


def test_put_is_rate_limited(clients):
    a, _ = clients["a"]
    codes = [a.put("/api/settings", json={"company_name": f"UAB {i}"}).status_code
             for i in range(main._RATE_LIMIT_PER_MIN + 1)]
    assert codes[:-1] == [200] * main._RATE_LIMIT_PER_MIN
    assert codes[-1] == 429


def test_table_appears_on_an_existing_database(tmp_path, monkeypatch):
    """An old database (every table but this one, with rows in it) gains
    `user_settings` on start and keeps its data."""
    path = tmp_path / "old.db"
    monkeypatch.setattr(db, "_DB_PATH", path)
    db.init_schema()
    db._migrate_schema()
    with db._conn() as c:
        c.execute("DROP TABLE user_settings")
        c.execute("INSERT INTO app_state (key, value, updated_at) "
                  "VALUES ('senas', 'lieka', '2026-01-01T00:00:00Z')")
    with sqlite3.connect(path) as raw:
        names = {r[0] for r in raw.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "user_settings" not in names

    db.init_schema()
    db._migrate_schema()

    with sqlite3.connect(path) as raw:
        cols = {r[1] for r in raw.execute("PRAGMA table_info(user_settings)")}
        kept = raw.execute("SELECT value FROM app_state WHERE key = 'senas'").fetchone()
    assert {"user_id", "data", "updated_at"} <= cols
    assert kept == ("lieka",)
    db.put_user_settings("u-old", {"company_name": "UAB Sena"})
    assert db.get_user_settings("u-old") == {"company_name": "UAB Sena"}


# ── A stale second tab (2026-09-30) ──────────────────────────────────────────
# Tab 1 signs A out and B in; tab 2 still shows A's Settings page. When tab 2
# saves, the browser sends B's cookie — without a check A's company details
# landed on B's account. The page now says which account it was loaded for.

_FOR_USER = "X-Settings-For-User"


def test_save_for_another_account_is_refused_and_stores_nothing(clients):
    a, user_a = clients["a"]
    b, user_b = clients["b"]
    before = b.get("/api/settings").json()
    # B's cookie, a page that was loaded for A.
    r = b.put("/api/settings", json={**_A_SETTINGS, "company_name": "UAB Svetima"},
              headers={_FOR_USER: user_a["id"]})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "Perkraukite" in detail and "neišsaugoti" in detail
    assert b.get("/api/settings").json() == before
    assert db.get_user_settings(user_b["id"]) == before


def test_save_for_the_signed_in_account_goes_through(clients):
    b, user_b = clients["b"]
    payload = {"company_name": "UAB Antroji", "iban": "LT000000000000000002"}
    r = b.put("/api/settings", json=payload, headers={_FOR_USER: user_b["id"]})
    assert r.status_code == 200, r.text
    assert b.get("/api/settings").json() == payload


def test_save_without_the_page_account_still_works(clients):
    """Pages loaded before this change send no account; they keep working."""
    b, _ = clients["b"]
    payload = {"company_name": "UAB Antroji", "iban": "LT000000000000000003"}
    r = b.put("/api/settings", json=payload)
    assert r.status_code == 200, r.text
    assert b.get("/api/settings").json() == payload

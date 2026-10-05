"""The admin users CSV holds EVERY user; the on-screen directory stays at 200
a page (2026-10-05).

The export asked db.admin_list_users_paginated for limit=100000, which clamps
to 200, so the file silently stopped at 200 users. It now reads
db.admin_export_users (the same rows, columns and order, no cap). The directory
query also carries deleted_at itself, so admin_v2 no longer looks each switched
-off row up again (get_user_by_id per row) to find the tombstones. Same-second
signups are ordered by id, so paging never repeats or skips one.

Temp database. Only the admin gets a real password hash; the other accounts
are plain rows.
"""
import csv
import io

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _setup(tmp_path, monkeypatch, n_users: int) -> TestClient:
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "users_export.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    db.create_user("admin@x.lt", auth.hash_password(_PW), name="Admin", is_admin=True)
    for i in range(n_users):
        db.create_user(f"u{i:03d}@x.lt", "h", name=f"Vartotojas {i}")
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "admin@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _csv(r) -> tuple[list[str], list[list[str]]]:
    assert r.status_code == 200, r.text
    rows = list(csv.reader(io.StringIO(r.text)))
    return rows[0], rows[1:]


def test_250_users_make_250_csv_rows(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, 250)
    header, rows = _csv(c.get("/api/admin/v2/export/users.csv"))
    emails = [row[header.index("email")] for row in rows]
    assert len(rows) == 251                                  # the 250 + the admin
    assert len(set(emails)) == 251
    assert {f"u{i:03d}@x.lt" for i in range(250)} <= set(emails)


def test_the_export_keeps_the_search_and_has_no_cap_there_either(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, 250)
    _h, every = _csv(c.get("/api/admin/v2/export/users.csv", params={"search": "x.lt"}))
    assert len(every) == 251
    header, some = _csv(c.get("/api/admin/v2/export/users.csv", params={"search": "U24"}))
    assert {row[header.index("email")] for row in some} == {f"u24{i}@x.lt" for i in range(10)}


def test_the_screen_list_stays_clamped_to_200(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, 250)
    first = c.get("/api/admin/v2/users", params={"limit": 100000}).json()
    assert first["limit"] == 200 and len(first["rows"]) == 200 and first["total"] == 251
    second = c.get("/api/admin/v2/users", params={"limit": 100000, "page": 2}).json()
    assert len(second["rows"]) == 51
    ids = [row["id"] for row in first["rows"] + second["rows"]]
    assert len(set(ids)) == 251


def test_same_second_signups_page_without_repeats_or_gaps(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, 45)
    with db._conn() as conn:
        conn.execute("UPDATE users SET created_at = '2026-10-05T10:00:00+00:00'")
    paged = []
    for page in range(1, 6):
        body = c.get("/api/admin/v2/users", params={"limit": 10, "page": page}).json()
        paged += [row["id"] for row in body["rows"]]
    assert len(paged) == 46 and len(set(paged)) == 46
    assert paged == sorted(paged)                            # the tie goes by id
    header, rows = _csv(c.get("/api/admin/v2/export/users.csv"))
    assert [row[header.index("id")] for row in rows] == paged  # the file in the same order


def test_deleted_at_comes_with_the_rows_not_from_a_lookup_per_row(tmp_path, monkeypatch):
    c = _setup(tmp_path, monkeypatch, 3)
    gone = []
    for i in range(5):
        u = db.create_user(f"gone{i}@x.lt", "h", name="Išėjęs")
        assert db.delete_account(u["id"]) is not None
        gone.append(u["id"])
    paused = db.create_user("paused@x.lt", "h", name="Sustabdytas")
    db.set_user_active(paused["id"], False)

    looked_up = []
    real = db.get_user_by_id
    monkeypatch.setattr(db, "get_user_by_id", lambda uid: looked_up.append(uid) or real(uid))

    rows = {row["id"]: row for row in c.get("/api/admin/v2/users", params={"limit": 50}).json()["rows"]}
    header, csv_rows = _csv(c.get("/api/admin/v2/export/users.csv"))
    in_csv = {row[header.index("id")]: row[header.index("deleted_at")] for row in csv_rows}

    for uid in gone:
        tomb = real(uid)["deleted_at"]
        assert tomb and rows[uid]["deleted_at"] == tomb and in_csv[uid] == tomb
    assert rows[paused["id"]]["deleted_at"] is None and in_csv[paused["id"]] == ""
    assert all("deleted_at" in row for row in rows.values())
    # Only the signed-in admin is looked up (the session check), no listed row.
    admin_id = db.get_user_by_email("admin@x.lt")["id"]
    assert looked_up and set(looked_up) == {admin_id}, set(looked_up) - {admin_id}


def test_the_db_helpers_return_the_same_rows(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, 12)
    paged = db.admin_list_users_paginated(page=1, limit=200)
    exported = db.admin_export_users()
    assert paged["rows"] == exported
    assert set(exported[0]) >= {"id", "email", "deleted_at", "project_count", "total_spend_eur"}
    assert db.admin_export_users(search="u01") == db.admin_list_users_paginated(search="u01")["rows"]

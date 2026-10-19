"""Account deletion — POST /api/account/delete (2026-10-05).

There was no way to delete an account, while the privacy page and the terms say
there is. These tests pin what the route promises:

  * only the caller's own account, and only once he typed its email;
  * every project goes through the same path as his own project delete — the
    row, the drawing, every id-keyed side store and the held re-reads — against
    a local storage backend in a temp dir, never R2;
  * the account-level rows go (company details, extraction-job records, price
    lists, sąmata templates), the users row becomes a tombstone that can never
    sign in again (password or Google), every session dies, and the email is
    free to register again;
  * issued invoices and the billing and cost ledgers stay exactly as they were;
  * a refusal changes nothing: wrong confirmation, an admin, a read in flight
    and — billing on only — a paid plan or unused bought projects.

Real auth, a temp database and every file store re-rooted under tmp_path.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import page_raster_cache  # noqa: E402
import project_purge  # noqa: E402
import storage  # noqa: E402
from api import account, annotations, calibrate, evidence, exports_v2, legends  # noqa: E402
from extractor import cv_render_cache  # noqa: E402

_PW = "passw0rd123"
_OWNER = "owner@x.lt"
_OTHER = "other@x.lt"
_ADMIN = "admin@x.lt"
_COMPANY = "302536741"
_GOOGLE_SUB = "google-sub-owner"
_READ = {"patalpos": [{"nr": "1", "plotas_m2": 12.5}], "darbu_sarasas": []}
_OWN = ("own-1", "own-2")
# Kept through a deletion, row for row.
_KEPT_TABLES = ("invoices", "billing_usage", "usage_events", "consumed_trials",
                "admin_audit_log")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "account.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    storage.reset_storage_for_test()
    assert isinstance(storage.get_storage(), storage.LocalDiskStorage)
    roots = {}
    for mod, attr, name in ((annotations, "DATA_ROOT", "annotations"),
                            (calibrate, "CALIB_ROOT", "calibrations"),
                            (legends, "LEGENDS_DIR", "legends"),
                            (evidence, "CACHE_ROOT", "evidence_cache"),
                            (exports_v2, "PROJECTS_DIR", "projects"),
                            (cv_render_cache, "CACHE_DIR", "cv_cache")):
        (tmp_path / name).mkdir()
        monkeypatch.setattr(mod, attr, tmp_path / name)
        roots[name] = tmp_path / name
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()

    db.init_schema()
    db._migrate_schema()
    admin = db.create_user(_ADMIN, auth.hash_password(_PW), name="Admin", is_admin=True)
    owner = db.create_user(_OWNER, auth.hash_password(_PW), name="Rimas",
                           company_name="UAB Pirmoji")
    other = db.create_user(_OTHER, auth.hash_password(_PW), name="Kitas")
    db.link_google_to_user(owner["id"], _GOOGLE_SUB, "https://example.invalid/a.png")
    db.set_user_company(owner["id"], _COMPANY, pvm_code="LT100000000001")

    # Two projects of his — one in the bin, which is only a flag on the
    # project — and one of someone else's.
    db.upsert_project("own-1", {"name": "Pirmas"}, user_id=owner["id"])
    db.upsert_project("own-2", {"name": "Antras", "_archived": True,
                                "_archived_at": "2026-10-01T00:00:00Z"},
                      user_id=owner["id"])
    db.upsert_project("oth-1", {"name": "Svetimas"}, user_id=other["id"])
    files = {pid: _seed(pid, roots) for pid in ("own-1", "own-2", "oth-1")}
    for pid in ("own-1", "oth-1"):
        db.log_correction(pid, "patalpos.1.plotas_m2", 10, 12)
        db.save_extraction(pid, f"ex-{pid}", {"_meta": {}})

    db.put_user_settings(owner["id"], {"company_name": "UAB Pirmoji",
                                       "iban": "LT000000000000000001"})
    db.put_user_settings(other["id"], {"company_name": "UAB Kita"})
    db.upsert_price_list("pl-own", {"name": "Mano kainynas", "items": []}, owner["id"])
    db.upsert_price_list("pl-oth", {"name": "Kito kainynas", "items": []}, other["id"])
    db.upsert_samata_template("tpl-own", {"name": "Mano šablonas"}, owner["id"])
    db.upsert_assembly("as-own", {"name": "Mano rinkinys", "taikoma": {"aprasymas": "Darbas"},
                                  "komponentai": []}, owner["id"])
    db.upsert_assembly("as-oth", {"name": "Kito rinkinys", "taikoma": {"aprasymas": "Darbas"},
                                  "komponentai": []}, other["id"])
    db.create_extraction_job("run-own", owner["id"], "boot-1", kind="reread",
                             project_id="own-1", filename="pirmas.pdf")
    assert db.finish_extraction_job("run-own", "done", result=_READ)
    db.create_extraction_job("run-oth", other["id"], "boot-1", kind="new",
                             filename="kitas.pdf")
    assert db.finish_extraction_job("run-oth", "done")

    # Issued invoice (its PDF in storage too), billing + cost ledgers, trial marker.
    storage.get_storage().put(storage.invoice_key("inv-own"), b"%PDF-1.4 invoice")
    db.insert_invoice("inv-own", owner["id"], "PATHON-2026-000001", "be_pvm", 49.0,
                      storage.invoice_key("inv-own"))
    db.record_billing_usage(owner["id"], kind="extract", project_id="own-1")
    db.record_usage(owner["id"], {"_meta": {"input_tokens": 1000, "output_tokens": 100}},
                    "extract-interior")
    assert db.consume_trial(_COMPANY, owner["id"])

    yield SimpleNamespace(owner=owner, other=other, admin=admin, files=files)
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()
    storage.reset_storage_for_test()


def _seed(pid: str, roots: dict) -> dict:
    """One file in every store the per-project purge cleans, written the way
    the app writes it."""
    pdf = f"%PDF-1.4 drawing {pid}".encode()
    storage.get_storage().put(storage.pdf_key(pid), pdf)
    page_raster_cache.store_pdf(pid, pdf)
    paths = {
        "annotations": roots["annotations"] / f"{pid}.json",
        "calibrations": roots["calibrations"] / f"{pid}.json",
        "legends": roots["legends"] / f"{pid}.json",
        "evidence": roots["evidence_cache"] / pid / "crop.png",
        "exports": roots["projects"] / pid / "lines.json",
        "cv": roots["cv_cache"] / f"{cv_render_cache.cache_key(pdf, 0, 200)}.png",
    }
    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    return paths


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _rows(table: str, where: str = "", args: tuple = ()) -> list[dict]:
    with db._conn() as c:
        return [dict(r) for r in c.execute(
            f"SELECT * FROM {table} {where} ORDER BY rowid", args)]


def _whole_db() -> dict:
    with db._conn() as c:
        tables = [r["name"] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: _rows(t) for t in tables}


def _pdf_stored(pid: str) -> bool:
    return storage.get_storage().exists(storage.pdf_key(pid))


def _all_files_there(env, pids) -> bool:
    return all(p.exists() for pid in pids for p in env.files[pid].values()) and all(
        _pdf_stored(pid) for pid in pids)


def _delete(client: TestClient, confirm=_OWNER):
    return client.post("/api/account/delete", json={"confirm": confirm})


# ── the deletion itself ──────────────────────────────────────────────────────

def test_owner_deletes_his_account(env, monkeypatch):
    purged, storage_deletes = [], []
    real_purge = project_purge.purge_project_files
    monkeypatch.setattr(project_purge, "purge_project_files",
                        lambda pid: purged.append(pid) or real_purge(pid))
    backend = storage.get_storage()
    real_delete = backend.delete
    monkeypatch.setattr(backend, "delete",
                        lambda key: storage_deletes.append(key) or real_delete(key))
    kept_before = {t: _rows(t) for t in _KEPT_TABLES}
    other_db_before = {
        "project": db.get_project("oth-1"),
        "settings": db.get_user_settings(env.other["id"]),
        "price_lists": db.list_price_lists(env.other["id"]),
        "job": _rows("extraction_jobs", "WHERE id = 'run-oth'"),
        "user": db.get_user_by_id(env.other["id"]),
    }
    owner = _login(_OWNER)
    sv_before = db.get_user_by_id(env.owner["id"])["session_version"]

    # Case and surrounding spaces do not matter, the address does.
    r = _delete(owner, confirm=f"  {_OWNER.upper()} ")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted_projects": 2}
    cookie = r.headers.get("set-cookie", "")
    assert cookie.startswith(f"{auth.SESSION_COOKIE}=null;") and "1970" in cookie

    # Every project of his went through the per-project path, the bin included.
    assert sorted(purged) == sorted(_OWN)
    for pid in _OWN:
        assert db.get_project(pid) is None
        assert storage.pdf_key(pid) in storage_deletes
        assert not _pdf_stored(pid)
        assert page_raster_cache.get_pdf(pid) is None
        for name, p in env.files[pid].items():
            assert not p.exists(), f"{name} of {pid} survived the account deletion"
    # What that path takes with the row (ON DELETE CASCADE): the correction log
    # and the extraction archive of those projects.
    assert _rows("corrections", "WHERE project_id = 'own-1'") == []
    assert _rows("extractions", "WHERE project_id = 'own-1'") == []

    # Account-level rows are gone; the held re-read went with its job row.
    uid = env.owner["id"]
    assert db.get_user_settings(uid) == {}
    assert db.list_price_lists(uid) == []
    assert db.list_samata_templates(uid) == []
    assert _rows("extraction_jobs", "WHERE user_id = ?", (uid,)) == []

    # The tombstone: nothing left that identifies him, and it cannot sign in.
    t = db.get_user_by_id(uid)
    assert t["email"] == f"deleted-{uid}@deleted.invalid"
    assert t["password_hash"] == "!deleted"
    for col in ("name", "company_name", "google_sub", "avatar_url",
                "company_code", "pvm_code"):
        assert t[col] is None, col
    assert t["is_active"] == 0 and t["is_admin"] == 0
    assert t["deleted_at"]
    assert t["session_version"] == sv_before + 1
    assert not auth.verify_password(_PW, t["password_hash"])

    # Invoices (and the invoice PDF), billing and cost ledgers, the trial marker
    # and the admin log: untouched, still pointing at his id.
    assert {tbl: _rows(tbl) for tbl in _KEPT_TABLES} == kept_before
    assert _rows("invoices")[0]["user_id"] == uid
    assert storage.get_storage().exists(storage.invoice_key("inv-own"))

    # The other account is exactly as it was.
    assert _all_files_there(env, ["oth-1"])
    assert page_raster_cache.get_pdf("oth-1") is not None
    assert _rows("corrections", "WHERE project_id = 'oth-1'") != []
    assert _rows("extractions", "WHERE project_id = 'oth-1'") != []
    assert {
        "project": db.get_project("oth-1"),
        "settings": db.get_user_settings(env.other["id"]),
        "price_lists": db.list_price_lists(env.other["id"]),
        "job": _rows("extraction_jobs", "WHERE id = 'run-oth'"),
        "user": db.get_user_by_id(env.other["id"]),
    } == other_db_before


def test_every_session_of_his_dies(env):
    phone, laptop = _login(_OWNER), _login(_OWNER)
    stolen = laptop.cookies.get(auth.SESSION_COOKIE)
    assert _delete(phone).status_code == 200
    replay = TestClient(app)
    replay.cookies.set(auth.SESSION_COOKIE, stolen)
    for c in (phone, laptop, replay):
        assert c.get("/api/auth/me").status_code == 401
        assert c.get("/api/projects").status_code == 401
        assert c.put("/api/projects/own-1", json={"name": "atgal"}).status_code == 401
    assert db.get_project("own-1") is None


def test_tombstone_cannot_sign_in_and_the_email_registers_again(env):
    assert _delete(_login(_OWNER)).status_code == 200
    placeholder = db.deleted_email_for(env.owner["id"])
    for email in (_OWNER, placeholder):
        r = TestClient(app).post("/api/auth/login", json={"email": email, "password": _PW})
        assert r.status_code == 401, email

    fresh = TestClient(app)
    r = fresh.post("/api/auth/register", json={"email": _OWNER, "password": _PW})
    assert r.status_code == 200, r.text
    new_id = r.json()["user"]["id"]
    assert new_id != env.owner["id"]
    assert fresh.get("/api/projects").json()["projects"] == []
    for pid in _OWN:
        assert fresh.get(f"/api/projects/{pid}").status_code == 404
    assert db.get_user_by_id(env.owner["id"])["deleted_at"]  # the tombstone stays


def _fake_google(monkeypatch, sub: str, email: str):
    import httpx

    class _Resp:
        def __init__(self, body):
            self.status_code, self._body, self.text = 200, body, ""

        def json(self):
            return self._body

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            return _Resp({"access_token": "tok"})

        async def get(self, *a, **k):
            return _Resp({"sub": sub, "email": email, "email_verified": True, "name": "Rimas"})

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr(main, "GOOGLE_OAUTH_ENABLED", True)
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(main, "GOOGLE_CLIENT_SECRET", "csec")


def _google_sign_in() -> TestClient:
    c = TestClient(app, follow_redirects=False)
    start = c.get("/api/auth/google")
    state = re.search(r"state=([^&]+)", start.headers["location"]).group(1)
    r = c.get("/api/auth/google/callback", params={"state": state, "code": "x"})
    assert r.status_code == 302 and r.headers["location"] == "/", r.headers.get("location")
    return c


def test_google_sign_in_never_reaches_the_tombstone(env, monkeypatch):
    _fake_google(monkeypatch, _GOOGLE_SUB, _OWNER)
    # Before: the Google account IS his account (otherwise the check below
    # would prove nothing).
    assert _google_sign_in().get("/api/auth/me").json()["user"]["id"] == env.owner["id"]

    assert _delete(_login(_OWNER)).status_code == 200
    me = _google_sign_in().get("/api/auth/me").json()["user"]
    assert me["id"] != env.owner["id"], "the same Google account signed back into the tombstone"
    assert me["email"] == _OWNER
    assert db.get_user_by_google_sub(_GOOGLE_SUB)["id"] == me["id"]
    t = db.get_user_by_id(env.owner["id"])
    assert t["google_sub"] is None and t["is_active"] == 0


# ── refusals change nothing ──────────────────────────────────────────────────

@pytest.mark.parametrize("body", [
    {"confirm": _OTHER},          # someone else's account cannot be named
    {"confirm": "owner@x.l"},
    {"confirm": ""},
    {"confirm": 12},
    {},
    None,
])
def test_wrong_confirmation_is_400_and_deletes_nothing(env, body):
    owner = _login(_OWNER)
    before = _whole_db()
    if body is None:
        r = owner.post("/api/account/delete")
    else:
        r = owner.post("/api/account/delete", json=body)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == account._MISMATCH_LT
    assert "set-cookie" not in r.headers
    assert _whole_db() == before
    assert _all_files_there(env, ["own-1", "own-2", "oth-1"])
    assert owner.get("/api/auth/me").status_code == 200


def test_admin_account_is_refused(env):
    admin = _login(_ADMIN)
    before = _whole_db()
    r = _delete(admin, confirm=_ADMIN)
    assert r.status_code == 403
    assert r.json()["detail"] == account._ADMIN_LT
    assert _whole_db() == before
    assert admin.get("/api/auth/me").status_code == 200


def test_signed_out_is_401(env):
    r = _delete(TestClient(app))
    assert r.status_code == 401
    assert db.get_user_by_id(env.owner["id"])["deleted_at"] is None


def test_a_running_read_blocks_the_deletion_until_it_ends(env):
    owner = _login(_OWNER)
    db.create_extraction_job("run-live", env.owner["id"], "boot-1", kind="new",
                             filename="naujas.pdf")
    before = _whole_db()
    r = _delete(owner)
    assert r.status_code == 409
    assert r.json()["detail"] == account._READING_LT
    assert _whole_db() == before
    assert _all_files_there(env, list(_OWN))

    assert db.finish_extraction_job("run-live", "done")
    assert _delete(owner).status_code == 200


def test_a_running_row_from_hours_ago_does_not_block(env):
    """A record that never got its ending is not a read in flight."""
    db.create_extraction_job("run-stuck", env.owner["id"], "boot-1", kind="new")
    with db._conn() as c:
        c.execute("UPDATE extraction_jobs SET started_at = '2026-01-01T00:00:00Z' "
                  "WHERE id = 'run-stuck'")
    assert not db.user_has_running_extraction(env.owner["id"])
    assert _delete(_login(_OWNER)).status_code == 200


def test_rate_limited_like_the_other_account_routes(env, monkeypatch):
    monkeypatch.setattr(main, "_RATE_LIMIT_PER_MIN", 2)
    owner = _login(_OWNER)
    assert _delete(owner, confirm="nera@x.lt").status_code == 400
    assert _delete(owner, confirm="nera@x.lt").status_code == 400
    assert _delete(owner).status_code == 429
    assert db.get_user_by_id(env.owner["id"])["deleted_at"] is None


# ── billing: only when it is on ──────────────────────────────────────────────

@pytest.mark.parametrize("status", ["active", "past_due"])
def test_billing_on_a_paid_plan_blocks(env, monkeypatch, status):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    db.set_user_plan(env.owner["id"], plan="pro", plan_status=status,
                     stripe_subscription_id="sub_1")
    owner = _login(_OWNER)
    before = _whole_db()
    r = _delete(owner)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert "„Pro“" in detail and "solutions@pathon.eu" in detail
    assert _whole_db() == before


def test_billing_on_unused_bought_projects_block(env, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    db.grant_oneoff_credit(env.owner["id"])
    db.grant_oneoff_credit(env.owner["id"])
    owner = _login(_OWNER)
    before = _whole_db()
    r = _delete(owner)
    assert r.status_code == 409
    assert "nepanaudotų projektų: 2" in r.json()["detail"]
    assert _whole_db() == before


def test_billing_on_a_cancelled_plan_does_not_block(env, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    db.set_user_plan(env.owner["id"], plan="pro", plan_status="canceled")
    r = _delete(_login(_OWNER))
    assert r.status_code == 200, r.text
    # The Stripe mirror stays on the tombstone for the kept invoices.
    assert db.get_user_by_id(env.owner["id"])["plan"] == "pro"


def test_billing_off_reads_no_billing_state(env, monkeypatch):
    """Flag off: the billing check returns before reading anything — a paid
    plan or credits on the row change nothing (they cannot be bought while off)."""
    db.set_user_plan(env.owner["id"], plan="pro", plan_status="active")
    db.grant_oneoff_credit(env.owner["id"])

    def _no_read(*a, **k):
        raise AssertionError("billing state read with billing off")
    monkeypatch.setattr(db, "credits_balance", _no_read)
    assert account._billing_blocker(db.get_user_by_id(env.owner["id"])) is None
    assert _delete(_login(_OWNER)).status_code == 200


# ── failures and races ───────────────────────────────────────────────────────

def test_storage_failure_still_deletes_the_account(env, monkeypatch):
    def boom(_key):
        raise storage.StorageError("R2 unavailable")
    monkeypatch.setattr(storage.get_storage(), "delete", boom)
    r = _delete(_login(_OWNER))
    assert r.status_code == 200, r.text
    for pid in _OWN:
        assert db.get_project(pid) is None                    # not resurrected
        for name, p in env.files[pid].items():                # the other stores still go
            assert not p.exists(), f"{name} survived a storage failure"
    assert db.get_user_by_id(env.owner["id"])["deleted_at"]


def test_a_failure_before_the_tombstone_leaves_a_live_account(env, monkeypatch):
    def boom(_uid):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(db, "delete_account", boom)
    owner = _login(_OWNER)
    r = _delete(owner)
    assert r.status_code == 500
    assert r.json()["detail"] == account._FAILED_LT
    assert owner.get("/api/auth/me").status_code == 200       # he can retry
    assert db.get_user_by_id(env.owner["id"])["deleted_at"] is None


def test_retry_after_a_failed_tombstone_completes(env, monkeypatch):
    real = db.delete_account
    calls = []

    def flaky(uid):
        calls.append(uid)
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        return real(uid)
    monkeypatch.setattr(db, "delete_account", flaky)
    owner = _login(_OWNER)
    assert _delete(owner).status_code == 500
    r = _delete(owner)
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted_projects": 0}    # the first try already took them
    assert db.get_user_by_id(env.owner["id"])["deleted_at"]


def test_a_save_landing_mid_deletion_is_swept(env, monkeypatch):
    """Another open tab's save can re-create a project after the first pass;
    the sweep after the tombstone removes it with the same path."""
    real = db.delete_account

    def with_racing_save(uid):
        db.upsert_project("raced", {"name": "Iš kito lango"}, user_id=uid)
        storage.get_storage().put(storage.pdf_key("raced"), b"%PDF-1.4 raced")
        return real(uid)
    monkeypatch.setattr(db, "delete_account", with_racing_save)
    r = _delete(_login(_OWNER))
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted_projects": 3}
    assert db.get_project("raced") is None
    assert not _pdf_stored("raced")


def test_a_deleted_account_gets_no_new_project(env):
    assert _delete(_login(_OWNER)).status_code == 200
    with pytest.raises(PermissionError):
        db.upsert_project("late", {"name": "Per vėlai"}, user_id=env.owner["id"])
    assert db.get_project("late") is None
    # Live accounts are untouched by that guard.
    db.upsert_project("oth-2", {"name": "Naujas"}, user_id=env.other["id"])
    assert db.get_project("oth-2")["user_id"] == env.other["id"]


def test_delete_account_helper_runs_once(env):
    uid = env.owner["id"]
    first = db.delete_account(uid)
    assert first == {"user_settings": 1, "extraction_jobs": 1, "price_lists": 1,
                     "samata_templates": 1, "assemblies": 1, "email_tokens": 0}
    tomb = db.get_user_by_id(uid)
    assert db.delete_account(uid) is None
    assert db.get_user_by_id(uid) == tomb
    assert db.delete_account("no-such-user") is None


def test_a_squatted_placeholder_does_not_block_the_tombstone(env):
    uid = env.owner["id"]
    db.create_user(db.deleted_email_for(uid), auth.hash_password(_PW))
    assert db.delete_account(uid) is not None
    email = db.get_user_by_id(uid)["email"]
    assert email.startswith(f"deleted-{uid}-") and email.endswith("@deleted.invalid")


def test_migration_adds_deleted_at_to_an_old_users_table(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                   password_hash TEXT NOT NULL, name TEXT, company_name TEXT,
                   is_admin INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1,
                   created_at TEXT NOT NULL, last_login_at TEXT)""")
    old.commit()
    old.close()
    monkeypatch.setattr(db, "_DB_PATH", path)
    db.init_schema()
    db._migrate_schema()
    with db._conn() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
    assert "deleted_at" in cols

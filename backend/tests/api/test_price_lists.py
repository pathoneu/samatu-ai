"""Kainynai — xlsx parsing + owner-scoped CRUD (Task 5, 2026-09-02).

Every workbook here is built in-process with openpyxl from INVENTED position
names — no contractor file, no client data, nothing that could leak into the
repo.
"""

from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import api.price_lists as pl_mod            # noqa: E402
import auth as _auth                        # noqa: E402
import db as _db                            # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _wb_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Kainos"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


STANDARD_ROWS = [
    ["UAB Pavyzdys — kainynas 2026", None, None, None],
    [None, None, None, None],
    ["Skyrius", "Aprašymas", "Vnt.", "Kaina, EUR"],
    ["Dažymas", "Sienų dažymas (2 sluoksniai)", "m²", "7,50"],
    ["Dažymas", "Lubų dažymas", "m²", 6.2],
    [None, "Grindjuosčių montavimas", "m", "4,10"],
    [None, None, None, None],
    ["Klaida", "", None, "9"],                 # no description → skipped
    ["Klaida", "Pozicija be kainos", "m²", None],  # no price → skipped
]


# ── parser ───────────────────────────────────────────────────────────────────

def test_parses_lt_headers_commas_and_offset_header_row():
    out = pl_mod.parse_xlsx_items(_wb_bytes(STANDARD_ROWS))
    assert out["header_row"] == 3
    assert out["sheet"] == "Kainos"
    assert out["skipped_rows"] == 2
    assert [i["aprasymas"] for i in out["items"]] == [
        "Sienų dažymas (2 sluoksniai)",
        "Lubų dažymas",
        "Grindjuosčių montavimas",
    ]
    # LT decimal comma AND a native numeric cell both land as floats.
    assert out["items"][0]["kaina"] == pytest.approx(7.5)
    assert out["items"][1]["kaina"] == pytest.approx(6.2)
    # Missing skyrius falls back to the same default the CSV parser uses.
    assert out["items"][2]["skyrius"] == "Kiti darbai"
    assert out["items"][0]["mato_vnt"] == "m²"


def test_item_shape_matches_the_csv_parser_exactly():
    out = pl_mod.parse_xlsx_items(_wb_bytes(STANDARD_ROWS))
    for item in out["items"]:
        assert set(item) == {"skyrius", "aprasymas", "mato_vnt", "kaina"}


def test_header_vocabulary_tolerates_case_and_missing_diacritics():
    rows = [
        ["KATEGORIJA", "PAVADINIMAS", "MATAS", "PRICE"],
        ["Grindys", "Laminato klojimas", "m2", "11,90"],
    ]
    out = pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert out["header_row"] == 1
    assert out["items"] == [{
        "skyrius": "Grindys",
        "aprasymas": "Laminato klojimas",
        "mato_vnt": "m2",
        "kaina": 11.9,
    }]


def test_thousands_separator_and_currency_symbol():
    rows = [
        ["Aprašymas", "Kaina"],
        ["Pastolių nuoma", "1 250,75 €"],
        ["Konteinerio išvežimas", "1.250,75"],
    ]
    out = pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert [i["kaina"] for i in out["items"]] == [
        pytest.approx(1250.75), pytest.approx(1250.75)]


def test_missing_header_is_a_400_not_a_crash():
    rows = [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"], ["i", "j"], ["k", "l"]]
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert exc.value.status_code == 400
    assert "antraštės" in exc.value.detail


def test_header_below_the_scan_window_is_rejected():
    """A header on row 6 is out of the documented 5-row window — better a clear
    Lithuanian error than a silent zero-row import."""
    rows = [[None]] * 5 + [["Aprašymas", "Kaina"], ["Sienų dažymas", "7,5"]]
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert exc.value.status_code == 400


def test_no_usable_rows_is_a_400():
    rows = [["Aprašymas", "Kaina"], [None, None]]
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert exc.value.status_code == 400


def test_garbage_bytes_are_a_400():
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(b"this is not a workbook")
    assert exc.value.status_code == 400


# ── endpoints ────────────────────────────────────────────────────────────────

USER_A = {"id": "pl-test-user-a", "email": "a@example.test", "is_admin": False}
USER_B = {"id": "pl-test-user-b", "email": "b@example.test", "is_admin": False}


@pytest.fixture()
def as_user(monkeypatch):
    """Client factory. Identity travels PER REQUEST in a test header, not in a
    module-level patch — with a pinned patch, creating client B silently
    re-identified client A and an ownership test could pass for the wrong
    reason."""
    app = FastAPI()
    app.include_router(pl_mod.router)
    known = {u["id"]: u for u in (USER_A, USER_B)}

    def _resolve(request):
        uid = request.headers.get("x-test-user")
        if uid not in known:
            raise HTTPException(status_code=401, detail="Reikia prisijungti")
        return dict(known[uid])

    monkeypatch.setattr(_auth, "require_user", _resolve)

    def _make(user: dict) -> TestClient:
        return TestClient(app, headers={"x-test-user": user["id"]})

    return _make


@pytest.fixture(autouse=True)
def _clean_price_lists():
    yield
    with _db._conn() as c:
        c.execute("DELETE FROM price_lists WHERE user_id IN (?, ?)",
                  (USER_A["id"], USER_B["id"]))


def test_upload_requires_auth():
    """The router must not be reachable without a session."""
    app = FastAPI()
    app.include_router(pl_mod.router)
    with pytest.MonkeyPatch.context() as mp:
        def _reject(request):
            raise HTTPException(status_code=401, detail="Reikia prisijungti")
        mp.setattr(_auth, "require_user", _reject)
        client = TestClient(app)
        assert client.get("/api/price-lists").status_code == 401
        r = client.post("/api/price-lists/parse-xlsx",
                        files={"file": ("k.xlsx", _wb_bytes(STANDARD_ROWS))})
        assert r.status_code == 401


def test_parse_endpoint_is_rate_limited(as_user, monkeypatch):
    """Parsing a workbook is CPU work behind a login — the size caps alone do
    not stop one account from looping it."""
    seen = []
    import main
    monkeypatch.setattr(main, "_check_rate_limit",
                        lambda ip, endpoint: seen.append(endpoint))
    client = as_user(USER_A)
    client.post("/api/price-lists/parse-xlsx",
                files={"file": ("k.xlsx", _wb_bytes(STANDARD_ROWS))})
    assert seen == ["price-lists-parse-xlsx"]


def test_parse_endpoint_round_trip(as_user):
    client = as_user(USER_A)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("kainynas.xlsx", _wb_bytes(STANDARD_ROWS))})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 3
    assert body["skipped_rows"] == 2


def test_legacy_xls_gets_a_useful_lithuanian_error(as_user):
    client = as_user(USER_A)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("senas.xls", b"\xd0\xcf\x11\xe0not-a-zip")})
    assert r.status_code == 400
    assert ".xlsx" in r.json()["detail"]


def test_non_zip_upload_is_rejected(as_user):
    client = as_user(USER_A)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", b"plain text, not a workbook")})
    assert r.status_code == 400


def test_empty_upload_is_rejected(as_user):
    client = as_user(USER_A)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", b"")})
    assert r.status_code == 400


def test_oversized_upload_is_rejected(as_user):
    client = as_user(USER_A)
    blob = b"PK" + b"0" * (pl_mod.MAX_UPLOAD_BYTES + 1)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", blob)})
    assert r.status_code == 413


def test_crud_round_trip(as_user):
    client = as_user(USER_A)
    pid = str(uuid.uuid4())
    payload = {"name": "Mano kainynas", "company_name": "UAB Bandymas",
               "items": [{"skyrius": "Dažymas", "aprasymas": "Sienų dažymas",
                          "mato_vnt": "m²", "kaina": 7.5}]}
    r = client.put(f"/api/price-lists/{pid}", json=payload)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["total_items"] == 1
    assert saved["created_date"] == saved["created_at"]

    listed = client.get("/api/price-lists").json()["price_lists"]
    assert [p["id"] for p in listed] == [pid]

    r = client.delete(f"/api/price-lists/{pid}")
    assert r.status_code == 200
    assert client.get("/api/price-lists").json()["price_lists"] == []
    assert client.delete(f"/api/price-lists/{pid}").status_code == 404


def test_bad_id_is_rejected(as_user):
    client = as_user(USER_A)
    r = client.put("/api/price-lists/../../etc/passwd", json={"name": "x"})
    assert r.status_code in (400, 404)
    r = client.put("/api/price-lists/not-a-uuid", json={"name": "x"})
    assert r.status_code == 400


def test_items_must_be_a_list(as_user):
    client = as_user(USER_A)
    r = client.put(f"/api/price-lists/{uuid.uuid4()}",
                   json={"name": "x", "items": {"nope": 1}})
    assert r.status_code == 400


def test_one_default_per_user(as_user):
    client = as_user(USER_A)
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    client.put(f"/api/price-lists/{first}", json={"name": "A", "is_default": True})
    client.put(f"/api/price-lists/{second}", json={"name": "B", "is_default": True})
    lists = {p["id"]: p for p in client.get("/api/price-lists").json()["price_lists"]}
    assert lists[second]["is_default"] is True
    assert lists[first]["is_default"] is False


def test_other_users_lists_are_invisible_and_unwritable(as_user):
    a = as_user(USER_A)
    pid = str(uuid.uuid4())
    a.put(f"/api/price-lists/{pid}", json={"name": "A slaptas", "items": []})

    b = as_user(USER_B)
    assert b.get("/api/price-lists").json()["price_lists"] == []
    # Overwriting someone else's list is a 403, not a silent takeover.
    assert b.put(f"/api/price-lists/{pid}", json={"name": "Pavogta"}).status_code == 403
    # Deleting is a 404 — we never confirm that the id exists.
    assert b.delete(f"/api/price-lists/{pid}").status_code == 404
    # …and A still owns it, unmodified.
    assert a.get("/api/price-lists").json()["price_lists"][0]["name"] == "A slaptas"


def test_default_flag_is_scoped_to_the_owner(as_user):
    """B making his list default must not clear A's default."""
    a = as_user(USER_A)
    a_id = str(uuid.uuid4())
    a.put(f"/api/price-lists/{a_id}", json={"name": "A", "is_default": True})

    b = as_user(USER_B)
    b.put(f"/api/price-lists/{uuid.uuid4()}", json={"name": "B", "is_default": True})

    assert a.get("/api/price-lists").json()["price_lists"][0]["is_default"] is True


# ── db layer ─────────────────────────────────────────────────────────────────

def test_admins_get_no_cross_user_access(as_user):
    """There is no admin view of kainynai — an admin session must see and touch
    only its own, so the list/delete pair can never drift into an IDOR."""
    a = as_user(USER_A)
    pid = str(uuid.uuid4())
    a.put(f"/api/price-lists/{pid}", json={"name": "A privatus", "items": []})

    admin = {"id": "pl-test-admin", "email": "admin@example.test", "is_admin": True}
    app = FastAPI()
    app.include_router(pl_mod.router)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_auth, "require_user", lambda request: dict(admin))
        client = TestClient(app)
        assert client.get("/api/price-lists").json()["price_lists"] == []
        assert client.delete(f"/api/price-lists/{pid}").status_code == 404
    assert a.get("/api/price-lists").json()["price_lists"][0]["name"] == "A privatus"


def test_null_owner_rows_cannot_be_hijacked():
    """The 2026-06-19 write-barrier lesson, applied to price lists: an
    owner-less row must not be writable by any logged-in user."""
    pid = str(uuid.uuid4())
    _db.upsert_price_list(pid, {"name": "Orphan", "items": []}, user_id=None)
    with pytest.raises(PermissionError):
        _db.upsert_price_list(pid, {"name": "Hijacked"}, user_id=USER_A["id"])
    assert _db.get_price_list(pid)["name"] == "Orphan"
    _db.delete_price_list(pid)


def test_corrupt_items_blob_does_not_read_as_empty():
    pid = str(uuid.uuid4())
    _db.upsert_price_list(pid, {"name": "Sugadintas", "items": []}, user_id=None)
    with _db._conn() as c:
        c.execute("UPDATE price_lists SET items = ? WHERE id = ?", ("{not json", pid))
    row = _db.get_price_list(pid)
    assert row["_items_corrupt"] is True
    assert row["items"] == []
    _db.delete_price_list(pid)

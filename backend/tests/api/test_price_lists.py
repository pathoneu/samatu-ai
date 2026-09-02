"""Kainynai — xlsx parsing + owner-scoped CRUD (Task 5, 2026-09-02).

Every workbook here is built in-process with openpyxl from INVENTED position
names — no contractor file, no client data, nothing that could leak into the
repo.
"""

from __future__ import annotations

import io
import json
import sys
import time
import uuid
import zipfile
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


def _rebuild_zip(source: bytes, replace: dict[str, bytes],
                 extra: dict[str, bytes] | None = None) -> bytes:
    """Copy a workbook zip, swapping/adding named members.

    Used to build the hostile workbooks below. They are assembled IN-TEST from
    invented content — there is no fixture file to check in and nothing that
    could carry a contractor's data.
    """
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zo:
        for name in zin.namelist():
            zo.writestr(name, replace.get(name, zin.read(name)))
        for name, blob in (extra or {}).items():
            if name not in zin.namelist():
                zo.writestr(name, blob)
    return out.getvalue()


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


# ── resource exhaustion (F3, 2026-09-02 review) ──────────────────────────────
#
# Every fixture above is a well-formed openpyxl Workbook, which is exactly the
# input that never hurts us. These four are the hostile shapes: the upload cap
# bounds the ZIP, not what comes out of it, and the sheet's own `<dimension>`
# used to decide how much work we did per row.

def _sharedstrings_bomb(declared_mb: int = 64) -> bytes:
    """A workbook whose xl/sharedStrings.xml deflates to hundreds of MB.

    Measured before the fix: a 647 KB upload of this shape returned HTTP 200 in
    8.7 s having added ~580 MB of RSS. openpyxl does not stream that member.
    """
    payload = (b'<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats'
               b'.org/spreadsheetml/2006/main" count="1" uniqueCount="1">'
               b'<si><t>' + b"A" * (declared_mb * 1024 * 1024) + b'</t></si></sst>')
    return _rebuild_zip(_wb_bytes(STANDARD_ROWS),
                        {"xl/sharedStrings.xml": payload},
                        {"xl/sharedStrings.xml": payload})


def test_a_decompression_bomb_is_refused_before_it_is_decompressed():
    blob = _sharedstrings_bomb()
    # Small enough to sail past every earlier guard: PK magic, well under the
    # 5 MB upload cap, and only a handful of rows so MAX_ROWS never fires.
    assert blob[:2] == b"PK"
    assert len(blob) < pl_mod.MAX_UPLOAD_BYTES

    t0 = time.perf_counter()
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(blob)
    elapsed = time.perf_counter() - t0

    assert exc.value.status_code == 413
    assert "per daug vietos" in exc.value.detail          # Lithuanian, actionable
    # The point of reading the central directory is that the refusal costs
    # nothing. A second here would mean we decompressed something.
    assert elapsed < 1.0, f"took {elapsed:.2f}s — the budget check decompressed"


def test_a_zip_with_absurdly_many_members_is_refused():
    extra = {f"xl/pad/{i}.xml": b"<x/>" for i in range(pl_mod.MAX_ZIP_MEMBERS + 20)}
    blob = _rebuild_zip(_wb_bytes(STANDARD_ROWS), {}, extra)
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(blob)
    assert exc.value.status_code == 413


_FORGED_SHEET = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    # 16384 columns × 1048576 rows, declared by the uploader.
    '<dimension ref="A1:XFD1048576"/><sheetData>'
    '<row r="1"><c r="A1" t="inlineStr"><is><t>Aprašymas</t></is></c>'
    '<c r="B1" t="inlineStr"><is><t>Kaina</t></is></c></row>'
    '<row r="2"><c r="A2" t="inlineStr"><is><t>Sienų dažymas</t></is></c>'
    '<c r="B2"><v>7.5</v></c></row>'
    # One real row at the very bottom: openpyxl fills the gap with an empty row
    # per index, each as wide as the declared dimension.
    '<row r="1048576"><c r="A1048576"><v>1</v></c></row>'
    '</sheetData></worksheet>'
).encode()


def test_a_forged_sheet_dimension_cannot_buy_cpu_time():
    """4.8 KB of upload bought 4.8 s of CPU before the row cap fired, because
    every padded row was sized from the file's own `<dimension>`."""
    blob = _rebuild_zip(_wb_bytes(STANDARD_ROWS),
                        {"xl/worksheets/sheet1.xml": _FORGED_SHEET})
    t0 = time.perf_counter()
    with pytest.raises(HTTPException) as exc:
        pl_mod.parse_xlsx_items(blob)
    elapsed = time.perf_counter() - t0
    assert exc.value.status_code == 413
    assert elapsed < 1.0, f"took {elapsed:.2f}s — the dimension still sizes the work"


def test_an_honest_wide_sheet_still_reads_its_first_columns():
    """The column cap must bound work, not truncate a real kainynas: the four
    columns we look for are always at the left edge."""
    rows = [["Skyrius", "Aprašymas", "Vnt.", "Kaina"] + [f"pastaba {i}" for i in range(20)],
            ["Dažymas", "Sienų dažymas", "m²", "7,50"] + ["x"] * 20]
    out = pl_mod.parse_xlsx_items(_wb_bytes(rows))
    assert out["items"] == [{"skyrius": "Dažymas", "aprasymas": "Sienų dažymas",
                             "mato_vnt": "m²", "kaina": 7.5}]


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


def test_parse_endpoint_is_rate_limited(as_user):
    """Parsing a workbook is CPU work behind a login — the size caps alone do
    not stop one account from looping it.

    Assert the OUTCOME, not a label: the previous version of this test only
    checked that a string reached a stubbed limiter, which would still pass if
    the bucket never filled. Fill it for real and demand the 429.
    """
    import main
    client = as_user(USER_A)
    # An empty part is refused before any parsing work, which keeps this loop
    # cheap while still consuming a bucket slot per request — and proves the
    # limiter runs BEFORE the body is touched.
    for i in range(main._RATE_LIMIT_PER_MIN):
        r = client.post("/api/price-lists/parse-xlsx",
                        files={"file": ("k.xlsx", b"")})
        assert r.status_code == 400, f"request {i + 1}: {r.status_code}"
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", _wb_bytes(STANDARD_ROWS))})
    assert r.status_code == 429
    assert "Per daug užklausų" in r.json()["detail"]


def test_the_limiter_keys_on_the_hop_the_caller_cannot_forge(monkeypatch):
    """Production runs uvicorn with --forwarded-allow-ips='*', so
    `request.client.host` IS the leftmost X-Forwarded-For value — the caller
    writes it, and rotating it empties the bucket every request. The key must
    come from the RIGHTMOST hop, appended by our own proxy."""
    import main
    seen: list[str] = []
    monkeypatch.setattr(main, "_check_rate_limit",
                        lambda key, endpoint: seen.append(key))

    app = FastAPI()
    app.include_router(pl_mod.router)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_auth, "require_user", lambda request: dict(USER_A))
        client = TestClient(app)
        client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", b"")},
                    headers={"x-forwarded-for": "203.0.113.7, 10.0.0.9"})
    assert seen == ["10.0.0.9"], seen


def test_cv_tools_limiter_shares_the_same_key(monkeypatch):
    """api/cv_tools carried the identical `request.client.host` bug and is the
    file the price-list code was copied from — fix both or the next copy
    reintroduces it."""
    import main
    import api.cv_tools as cv_mod
    seen: list[str] = []
    monkeypatch.setattr(main, "_check_rate_limit",
                        lambda key, endpoint: seen.append(key))

    class _Req:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.9"}
        client = type("C", (), {"host": "203.0.113.7"})()

    cv_mod._rate_limit(_Req(), "magic-wand")
    assert seen == ["10.0.0.9"], seen


def test_the_bomb_is_refused_over_HTTP_with_a_lithuanian_message(as_user):
    client = as_user(USER_A)
    r = client.post("/api/price-lists/parse-xlsx",
                    files={"file": ("k.xlsx", _sharedstrings_bomb())})
    assert r.status_code == 413
    assert "per daug vietos" in r.json()["detail"]


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


# ── bounded request bodies (F6, 2026-09-02 review) ───────────────────────────

def test_an_oversize_upload_is_refused_on_its_declared_length(as_user):
    """`await file.read()` used to materialise the whole part and only THEN
    compare it to the cap. Content-Length is checked first now."""
    client = as_user(USER_A)
    blob = b"PK" + b"0" * (pl_mod.MAX_UPLOAD_BYTES + 1)
    r = client.post("/api/price-lists/parse-xlsx", files={"file": ("k.xlsx", blob)})
    assert r.status_code == 413
    assert "per didelis" in r.json()["detail"]


def test_an_oversize_upload_is_refused_without_a_content_length(as_user):
    """Chunked / spoofed Content-Length: the stream-level guard has to hold on
    its own, or the header check is the only check."""
    client = as_user(USER_A)
    blob = b"PK" + b"0" * (pl_mod.MAX_UPLOAD_BYTES + 1)

    def _chunks():
        yield (b'--b\r\nContent-Disposition: form-data; name="file"; '
               b'filename="k.xlsx"\r\nContent-Type: application/octet-stream'
               b"\r\n\r\n")
        yield blob
        yield b"\r\n--b--\r\n"

    r = client.post("/api/price-lists/parse-xlsx", content=_chunks(),
                    headers={"content-type": "multipart/form-data; boundary=b"})
    assert r.status_code == 413


def test_a_put_body_over_the_cap_is_refused_before_it_is_parsed(as_user):
    """`payload: dict = Body(...)` parsed every byte before MAX_ITEMS_PER_LIST
    could fire, so the count cap bounded nothing that mattered."""
    client = as_user(USER_A)
    body = b'{"name":"x","items":[' + b'{"aprasymas":"a","kaina":1},' * 700_000 + b'{}]}'
    assert len(body) > pl_mod.MAX_PUT_BODY_BYTES
    r = client.put(f"/api/price-lists/{uuid.uuid4()}", content=body,
                   headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_too_many_items_is_refused(as_user):
    """MAX_ITEMS_PER_LIST had zero coverage."""
    client = as_user(USER_A)
    items = [{"aprasymas": f"Darbas {i}", "kaina": 1.0}
             for i in range(pl_mod.MAX_ITEMS_PER_LIST + 1)]
    r = client.put(f"/api/price-lists/{uuid.uuid4()}",
                   json={"name": "Didelis", "items": items})
    assert r.status_code == 413
    assert "per daug eilučių" in r.json()["detail"]

    # One under the cap is accepted, so the limit is a limit and not a wall.
    r = client.put(f"/api/price-lists/{uuid.uuid4()}",
                   json={"name": "Ribinis", "items": items[:10]})
    assert r.status_code == 200


def test_a_single_item_cannot_be_unbounded(as_user):
    """The count cap says nothing about the SIZE of a row: one item carrying a
    multi-megabyte aprašymas walked past it, got json.dumps'd into SQLite under
    the global write lock, and came back on every list read."""
    client = as_user(USER_A)
    pid = str(uuid.uuid4())
    r = client.put(f"/api/price-lists/{pid}", json={
        "name": "N" * 5_000,
        "company_name": "C" * 5_000,
        "items": [{"skyrius": "S" * 5_000, "aprasymas": "A" * 500_000,
                   "mato_vnt": "m" * 5_000, "kaina": 7.5}],
    })
    assert r.status_code == 200, r.text
    saved = r.json()
    item = saved["items"][0]
    assert len(item["aprasymas"]) == 400          # same cap the xlsx importer uses
    assert len(item["skyrius"]) == 200
    assert len(item["mato_vnt"]) == 32
    assert item["kaina"] == 7.5                   # the real value survives
    assert len(saved["name"]) == 200
    assert len(saved["company_name"]) == 200


def test_an_unknown_item_field_survives_but_is_bounded(as_user):
    """`applyPriceList.unitOf` still reads a legacy `vnt`, so dropping fields we
    do not recognise would quietly un-unit an old list."""
    client = as_user(USER_A)
    pid = str(uuid.uuid4())
    r = client.put(f"/api/price-lists/{pid}", json={
        "name": "Senas",
        "items": [{"aprasymas": "Sienų dažymas", "kaina": 7.5, "vnt": "m²",
                   "pastaba": "P" * 5_000}],
    })
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["vnt"] == "m²"
    assert len(item["pastaba"]) == pl_mod.MAX_ITEM_VALUE_LEN


@pytest.mark.parametrize("items,expected", [
    ([["not", "a", "dict"]], 400),
    ([{"aprasymas": {"nested": "object"}}], 400),
    ([{"aprasymas": ["nested", "list"]}], 400),
    ([{f"k{i}": "v" for i in range(pl_mod.MAX_ITEM_KEYS + 1)}], 400),
])
def test_malformed_items_are_refused(as_user, items, expected):
    client = as_user(USER_A)
    r = client.put(f"/api/price-lists/{uuid.uuid4()}",
                   json={"name": "x", "items": items})
    assert r.status_code == expected


def test_a_non_finite_price_never_reaches_the_stored_json(as_user):
    """Python's json parser accepts bare NaN/Infinity and json.dumps writes them
    straight back — invalid JSON that no browser can read back."""
    client = as_user(USER_A)
    pid = str(uuid.uuid4())
    r = client.put(f"/api/price-lists/{pid}",
                   content=b'{"name":"x","items":[{"aprasymas":"a","kaina":NaN}]}',
                   headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["kaina"] is None
    with _db._conn() as c:
        raw = c.execute("SELECT items FROM price_lists WHERE id = ?", (pid,)).fetchone()[0]
    assert "NaN" not in raw
    json.loads(raw)          # strict-mode parse, as a browser would


def test_a_malformed_json_body_is_a_400_not_a_500(as_user):
    client = as_user(USER_A)
    r = client.put(f"/api/price-lists/{uuid.uuid4()}", content=b"{not json",
                   headers={"content-type": "application/json"})
    assert r.status_code == 400


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
    # Overwriting someone else's list is refused, and refused as a 404: a 403
    # would confirm the id exists, and the message must never carry db.py's
    # English "User X does not own price list Y". DELETE has always 404'd for
    # that reason — the pair stays symmetric. (F13b, 2026-09-02 review.)
    r = b.put(f"/api/price-lists/{pid}", json={"name": "Pavogta"})
    assert r.status_code == 404
    assert r.json()["detail"] == "Kainynas nerastas"
    assert USER_A["id"] not in r.text and "does not own" not in r.text
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

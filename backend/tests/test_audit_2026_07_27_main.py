"""Audit 2026-07-27 — the verified main.py findings, one test group per item.

Every test here first pins the OLD broken behavior in its docstring (it was
reproduced before the fix) and then asserts the fixed behavior. Nothing in this
file makes a network call; Claude/Vision/extractor entry points are stubbed.

DB isolation follows the house idiom (test_export_auth / test_entitlements):
monkeypatch db._DB_PATH to a tmp file, then init_schema() + _migrate_schema().
"""
import asyncio
import io
import re

import pytest
import pdfplumber
from fastapi.testclient import TestClient

# main BEFORE auth — main.py's load_dotenv() must populate SAMATU_AUTH_DISABLED
# before auth.py freezes its module-level AUTH_DISABLED (see test_export_auth).
import main  # noqa: E402
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _hermetic_db(tmp_path, monkeypatch):
    """Every test in this file gets its OWN sqlite file.

    Without this, endpoints behind _billable_user write `reserve:` rows into the
    shared dev DB (backend/data/samatu.db) and burn the 20/hour extract cap, so
    a later run of THIS suite — or of test_recompute_quantities — 429s. Isolate
    once, autouse, so no test here can ever touch the real DB.
    """
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "audit20260727.db")
    db.init_schema()
    db._migrate_schema()
    # With the dev auth bypass on, every authed route acts as this user; the
    # upsert ownership barrier rejects writes to a NULL-owner row, so projects
    # created by these tests must be owned by it.
    auth._ensure_dev_user()
    yield


def _no_billing_side_effects(monkeypatch):
    """Neutralize the spend-cap reservation so a test never records usage."""
    monkeypatch.setattr(main, "_billable_user",
                        lambda request: {"id": auth._DEV_USER_ID,
                                         "is_admin": True})


class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "plan.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()


# ══════════════════════════════════════════════════════════════════════════
# 1 — POST /api/projects/{id}/material-specs
# ══════════════════════════════════════════════════════════════════════════
# OLD: `data = project.get("data") or {}` — but db.get_project FLATTENS the
# JSON blob onto the row dict, so "data" never exists → rooms was always []
# → every call 404'd "Room X not found". And the save wrote {**project,
# "data": data}, nesting a copy of the blob under a "data" key inside itself.

_SPEC_PROJECT = {
    "name": "Specs projektas",
    "tipas": "interjeras",
    "patalpos": [{"nr": "02", "pavadinimas": "Vonia", "paskirtis": "vonia",
                  "plotas_m2": 6.4}],
    "puslapiai": [{"nr": 3, "tipas": "wall_elevation",
                   "pavadinimas": "Vonios išklotinė"}],
}


def _stub_specs(monkeypatch, result=None):
    import extractor.material_specs as ms
    monkeypatch.setattr(
        ms, "extract_room_material_specs",
        lambda pdf_bytes, pages, room_name: result or {"paint": "RAL 9010"})


def test_material_specs_finds_an_existing_room_and_saves_without_nesting(
        tmp_path, monkeypatch):
    _stub_specs(monkeypatch)
    db.upsert_project("p-specs", dict(_SPEC_PROJECT), user_id=auth._DEV_USER_ID)

    r = client.post("/api/projects/p-specs/material-specs",
                    data={"room_nr": "02"},
                    files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["paint"] == "RAL 9010"

    saved = db.get_project("p-specs")
    # No self-nesting wrapper, and the specs landed on the blob itself.
    assert "data" not in saved
    assert saved["_material_specs"]["02"]["paint"] == "RAL 9010"
    # The rest of the blob survived the write.
    assert saved["patalpos"][0]["nr"] == "02"


def test_material_specs_second_call_is_served_from_cache(tmp_path, monkeypatch):
    _stub_specs(monkeypatch)
    db.upsert_project("p-specs2", dict(_SPEC_PROJECT), user_id=auth._DEV_USER_ID)
    args = dict(data={"room_nr": "02"},
                files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert client.post("/api/projects/p-specs2/material-specs", **args).status_code == 200
    r2 = client.post("/api/projects/p-specs2/material-specs", **args)
    assert r2.status_code == 200
    assert r2.json().get("_cached") is True   # proves the save+read round-tripped


def test_material_specs_unknown_room_still_404s(tmp_path, monkeypatch):
    _stub_specs(monkeypatch)
    db.upsert_project("p-specs3", dict(_SPEC_PROJECT), user_id=auth._DEV_USER_ID)
    r = client.post("/api/projects/p-specs3/material-specs",
                    data={"room_nr": "99"},
                    files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 2 + 3 — PUT /api/auth/profile
# ══════════════════════════════════════════════════════════════════════════
# OLD (2): returned db.get_user_by_id() verbatim → password_hash (bcrypt digest),
#          google_sub, stripe_customer_id and session_version in the response.
# OLD (3): `UPDATE users SET name = ?, company_name = ?` ran unconditionally with
#          the payload's None defaults, so a company_code-only PUT wiped both.

_PW = "passw0rd123"


def _real_auth_client(tmp_path, monkeypatch, email):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def test_profile_update_never_leaks_password_hash_or_billing_ids(
        tmp_path, monkeypatch):
    c = _real_auth_client(tmp_path, monkeypatch, "leak@test.lt")
    r = c.put("/api/auth/profile", json={"name": "Jonas"})
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    for leaked in ("password_hash", "google_sub", "stripe_customer_id",
                   "session_version"):
        assert leaked not in user, f"{leaked} leaked in profile response"
    assert user["name"] == "Jonas"          # the update still works


def test_partial_profile_update_does_not_wipe_name_or_company(
        tmp_path, monkeypatch):
    c = _real_auth_client(tmp_path, monkeypatch, "partial@test.lt")
    r = c.put("/api/auth/profile",
              json={"name": "Jonas", "company_name": "UAB Statyba"})
    assert r.status_code == 200, r.text

    # company_code-only update — must not clear name / company_name
    r2 = c.put("/api/auth/profile", json={"company_code": "123456789"})
    assert r2.status_code == 200, r2.text
    u = r2.json()["user"]
    assert u["name"] == "Jonas"
    assert u["company_name"] == "UAB Statyba"
    assert u["company_code"] == "123456789"


# ══════════════════════════════════════════════════════════════════════════
# 4 — /generate-pdf section subtotals vs the grand total
# ══════════════════════════════════════════════════════════════════════════
# OLD: `_section_sum += suma_val` summed RAW floats and only for suma_val > 0,
# while the grand total is round-then-sum over ALL rows. Sub-cent line values
# drifted, and negative (credit) lines were silently excluded from the section
# subtotal — so Σ(printed "Skyriaus suma") ≠ printed "Suma be PVM".

_LT_NUM = re.compile(r"(-?[\d ]+,\d{2})")


def _lt_to_float(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _pdf_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as d:
        return "\n".join((pg.extract_text() or "") for pg in d.pages)


def _mixed_rows_payload():
    """Two sections: sub-cent sumas (rounding drift) + one negative credit line."""
    rows = []
    for i in range(5):
        rows.append({"nr": f"1.{i}", "aprasymas": f"Darbas A{i}", "mato_vnt": "m²",
                     "kiekis": 1, "kaina": 10.005, "suma": 10.005,
                     "skyrius": "APDAILA"})
    for i in range(4):
        rows.append({"nr": f"2.{i}", "aprasymas": f"Darbas B{i}", "mato_vnt": "m²",
                     "kiekis": 1, "kaina": 3.334, "suma": 3.334,
                     "skyrius": "GRINDYS"})
    rows.append({"nr": "2.9", "aprasymas": "Nuolaida", "mato_vnt": "vnt.",
                 "kiekis": 1, "kaina": -12.5, "suma": -12.5, "skyrius": "GRINDYS"})
    return {"projektas": "Subtotal test", "tipas": "kz", "eilutes": rows}


def test_pdf_section_subtotals_sum_to_the_printed_grand_total():
    r = client.post("/generate-pdf", json=_mixed_rows_payload())
    assert r.status_code == 200, r.text
    txt = _pdf_text(r.content)

    subtotals = [_lt_to_float(m) for line in txt.splitlines()
                 if "Skyriaus suma" in line for m in _LT_NUM.findall(line)]
    assert len(subtotals) == 2, f"expected 2 section subtotals, got {subtotals}\n{txt}"

    grand_line = next(l for l in txt.splitlines() if "Suma be PVM" in l)
    grand = _lt_to_float(_LT_NUM.findall(grand_line)[0])

    assert round(sum(subtotals), 2) == grand, (
        f"Σ(sections)={sum(subtotals)} != printed grand total {grand}")


def test_pdf_negative_credit_line_is_counted_in_its_section():
    """The -12.50 credit must pull the GRINDYS subtotal DOWN, not be ignored."""
    r = client.post("/generate-pdf", json=_mixed_rows_payload())
    txt = _pdf_text(r.content)
    subtotals = [_lt_to_float(m) for line in txt.splitlines()
                 if "Skyriaus suma" in line for m in _LT_NUM.findall(line)]
    # GRINDYS = 4 × 3.33 − 12.50 = 0.82  (old code printed 13.32: credit dropped)
    assert subtotals[1] == pytest.approx(0.82, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════
# 5 — /recompute-interior degrades honestly
# ══════════════════════════════════════════════════════════════════════════
# OLD: a room whose calc threw kept its OLD numbers (`recalc = {}`) and a
# pozicijos-build failure returned `"pozicijos": []`, both with status "ok" and
# nothing but a server log — the UI showed stale/empty data as freshly computed.

_GOOD_ROOM = {"nr": "01", "pavadinimas": "Vonia", "paskirtis": "vonia",
              "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.5}


def _recompute(rooms, monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "u1"})
    payload = main.RecomputePayload(patalpos=rooms, bendras_plotas_m2=8.0)
    return asyncio.run(main.recompute_interior(payload=payload,
                                               request=_FakeRequest()))


def test_recompute_reports_failed_rooms_and_pozicijos_build(monkeypatch):
    bad = dict(_GOOD_ROOM)
    bad["elementai"] = 5          # an int where a list is expected → calc throws
    out = _recompute([bad], monkeypatch)

    assert out["status"] == "ok"                    # frontend contract unchanged
    failures = out["_recompute_failures"]
    assert failures["rooms"] == ["01"]
    assert failures["pozicijos_build"] is True

    msgs = [w["message"] for w in out["lt_sanity"]["warnings"]
            if w.get("field") == "recompute"]
    assert any("Nepavyko perskaičiuoti patalpų" in m for m in msgs)
    assert any("pozicij" in m for m in msgs)
    # the banner counter must see them
    assert out["lt_sanity"]["summary"]["warnings_count"] >= 2


def test_recompute_non_numeric_geometry_no_longer_500s_the_request(monkeypatch):
    """A dict where a float belongs used to pass the per-room guard and then
    blow up downstream in _recompute_santrauka → calc_totals → float(dict),
    500ing the WHOLE request — the very thing that guard exists to prevent."""
    bad = dict(_GOOD_ROOM)
    bad["plotas_m2"] = {"oops": 1}
    out = _recompute([bad, {**_GOOD_ROOM, "nr": "02"}], monkeypatch)

    assert out["status"] == "ok"
    assert out["_recompute_failures"]["rooms"] == ["01"]
    assert len(out["patalpos"]) == 2          # the healthy room survives
    msgs = [w["message"] for w in out["lt_sanity"]["warnings"]
            if w.get("field") == "recompute"]
    assert any("01" in m for m in msgs)


def test_recompute_clean_payload_carries_no_failure_marker(monkeypatch):
    out = _recompute([dict(_GOOD_ROOM)], monkeypatch)
    assert out["status"] == "ok"
    assert "_recompute_failures" not in out
    assert not [w for w in out["lt_sanity"]["warnings"]
                if w.get("field") == "recompute"]


# ══════════════════════════════════════════════════════════════════════════
# 6 — _parse_qty
# ══════════════════════════════════════════════════════════════════════════
# OLD: thousands separators (regular space / NBSP / narrow NBSP) were never
# stripped, so '1 234,56' → float('1 234.56') → ValueError → None → the KŽ row
# was DROPPED. And `v if v > 0` turned a legitimate 0 quantity into None, which
# the table path also treats as "no quantity" → row dropped.

@pytest.mark.parametrize("raw,expected", [
    ("17,90", 17.9),
    ("1", 1.0),
    ("1 234,56", 1234.56),          # ASCII space
    ("1 234,56", 1234.56),     # NBSP — what pdfplumber usually yields
    ("2 500,00", 2500.0),      # narrow NBSP
    ("0", 0.0),
    ("0,00", 0.0),
    ("-5", None),
    ("---", None),
    ("--", None),
    ("-", None),
    ("", None),
    (None, None),
    ("abc", None),
])
def test_parse_qty(raw, expected):
    assert main._parse_qty(raw) == expected


def test_zero_quantity_row_survives_the_table_path():
    """The table path drops a row when _parse_qty returns None — a genuine 0
    must therefore come back as 0.0 (a row), not None (a dropped row)."""
    v = main._parse_qty("0,00")
    assert v is not None and v == 0.0


# ══════════════════════════════════════════════════════════════════════════
# 7 — the 4 construction endpoints must not flatten HTTPException into 200
# ══════════════════════════════════════════════════════════════════════════
# OLD: `except Exception as e: return {"error": ...}` swallowed the 400/413
# raised by _validate_pdf_upload, so an invalid or oversized upload came back
# as HTTP 200 with an error STRING — no client could branch on it.

@pytest.mark.parametrize("route", [
    "/extract-facade", "/extract-roof", "/extract-earthworks", "/extract-concrete",
])
def test_construction_endpoints_return_a_real_4xx_on_a_bad_upload(route, monkeypatch):
    _no_billing_side_effects(monkeypatch)
    r = client.post(route, files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 200,
                                           "image/png")})
    assert r.status_code == 400, f"{route} returned {r.status_code}: {r.text[:200]}"
    assert "PDF" in r.json()["detail"]


@pytest.mark.parametrize("route", [
    "/extract-facade", "/extract-roof", "/extract-earthworks", "/extract-concrete",
])
def test_construction_endpoints_do_not_echo_exception_internals(route, monkeypatch):
    """A crash inside the handler must return the generic LT message, never
    `Nenumatyta klaida: {type(e).__name__}: {e}` — which leaked pdfminer /
    library internals (and any path in them) verbatim to the client."""
    _no_billing_side_effects(monkeypatch)
    monkeypatch.setattr(main, "_validate_pdf_upload",
                        lambda b, n: {"page_count": 1})

    r = client.post(route, files={"file": ("x.pdf", b"%PDF-1.4 fake" + b"0" * 200,
                                           "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body == {"error": "Nenumatyta klaida apdorojant PDF. "
                             "Bandykite dar kartą."}, body


# ══════════════════════════════════════════════════════════════════════════
# 8 — /extract must not return a silently partial KŽ
# ══════════════════════════════════════════════════════════════════════════
# OLD: `except Exception: continue` per Claude window. An API outage produced a
# 200 with a partial (or empty) eilutes list and no signal whatsoever.

_ROW = {"nr": "1.1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
        "kiekis": 10, "skyrius": "APDAILA"}


def _patch_extract_path2(monkeypatch, call_claude):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "u1"})
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 2})
    monkeypatch.setattr(main, "_extract_kz_direct", lambda b: None)  # force path 2
    monkeypatch.setattr(main, "_pdf_to_chunks", lambda b: (
        "Testas", [{"text": "chunk one text", "pages": "1-1"},
                   {"text": "chunk two text", "pages": "2-2"}]))
    monkeypatch.setattr(main, "_call_claude", call_claude)


def test_extract_502s_when_every_claude_window_fails(monkeypatch):
    def _always_fail(prompt):
        raise RuntimeError("anthropic 529 overloaded")
    _patch_extract_path2(monkeypatch, _always_fail)

    r = client.post("/extract", files={"file": ("kz.pdf", b"%PDF-1.4 fake",
                                                "application/pdf")})
    assert r.status_code == 502, r.text
    assert r.json()["detail"] == "AI tarnyba laikinai nepasiekiama — bandykite dar kartą"


def test_extract_reports_failed_windows_when_only_some_fail(monkeypatch):
    calls = {"n": 0}

    def _fail_first(prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("anthropic 529 overloaded")
        import json as _json
        return _json.dumps([_ROW])
    _patch_extract_path2(monkeypatch, _fail_first)

    r = client.post("/extract", files={"file": ("kz.pdf", b"%PDF-1.4 fake",
                                                "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["failed_windows"] == 1
    assert body["meta"]["windows_total"] == 2
    assert len(body["eilutes"]) >= 1     # the surviving window's rows are kept


def test_extract_reports_zero_failed_windows_on_a_clean_run(monkeypatch):
    import json as _json
    _patch_extract_path2(monkeypatch, lambda prompt: _json.dumps([_ROW]))
    r = client.post("/extract", files={"file": ("kz.pdf", b"%PDF-1.4 fake",
                                                "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["meta"]["failed_windows"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 9 — /extract-interior-stream billing parity with its non-stream twin
# ══════════════════════════════════════════════════════════════════════════
# OLD: db.record_extract_and_maybe_consume_credit() was called UNGUARDED, so the
# stream endpoint wrote billing_usage rows with BILLING_ENABLED off (proven in
# the live DB), and it never consumed the company trial.

def _drain_stream(**kw):
    """Run the stream endpoint and consume the whole SSE body."""
    async def _run():
        resp = await main.extract_interior_stream_endpoint(**kw)
        return b"".join([chunk async for chunk in resp.body_iterator])
    return asyncio.run(_run())


def _patch_stream_pipeline(monkeypatch, user_id="u1"):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": user_id})
    monkeypatch.setattr(main, "_check_user_quota", lambda uid: None)
    monkeypatch.setattr(main, "_check_trial_gate", lambda uid: None)
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(main, "_client_key", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 1})
    import extractor

    def _fake_stream(pdf_bytes, overrides):
        yield {"event": "started"}
        yield {"event": "done", "result": {"status": "ok", "patalpos": []}}
    monkeypatch.setattr(extractor, "extract_interior_stream", _fake_stream)


def _billing_rows(user_id, kind="extract"):
    with db._conn() as c:
        return c.execute(
            "SELECT COUNT(*) AS n FROM billing_usage WHERE user_id = ? AND kind = ?",
            (user_id, kind)).fetchone()["n"]


def test_stream_writes_no_billing_row_when_the_flag_is_off(tmp_path, monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _patch_stream_pipeline(monkeypatch, "su1")
    body = _drain_stream(request=_FakeRequest(),
                         files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None)
    assert b'"event": "done"' in body
    assert _billing_rows("su1") == 0


def test_stream_writes_exactly_one_billing_row_when_the_flag_is_on(
        tmp_path, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _patch_stream_pipeline(monkeypatch, "su2")
    _drain_stream(request=_FakeRequest(),
                  files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None)
    assert _billing_rows("su2") == 1


def test_stream_consumes_the_company_trial_like_the_non_stream_twin(
        tmp_path, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    from billing.trial import trial_available
    with db._conn() as c:
        c.execute("INSERT INTO users (id, email, password_hash, plan, is_active, "
                  "company_code, created_at) VALUES (?,?,?,?,?,?,?)",
                  ("su3", "su3@test.lt", "", "free", 1, "987654321", db._now_iso()))
    assert trial_available("987654321") is True

    _patch_stream_pipeline(monkeypatch, "su3")
    _drain_stream(request=_FakeRequest(),
                  files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None)
    assert trial_available("987654321") is False   # trial now consumed


def test_stream_error_event_does_not_echo_the_exception(tmp_path, monkeypatch):
    """Item 15 — the SSE error event used to carry str(exc) verbatim."""
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _patch_stream_pipeline(monkeypatch, "su4")
    import extractor

    def _boom_stream(pdf_bytes, overrides):
        yield {"event": "started"}
        raise RuntimeError("SecretInternalDetail /var/lib/x")
    monkeypatch.setattr(extractor, "extract_interior_stream", _boom_stream)

    body = _drain_stream(request=_FakeRequest(),
                         files=[_FakeUpload(b"%PDF-1.4 fake")],
                         rules_override=None).decode("utf-8")
    assert '"event": "error"' in body
    assert "SecretInternalDetail" not in body
    assert "RuntimeError" not in body
    assert "Nenumatyta klaida" in body


# ══════════════════════════════════════════════════════════════════════════
# 10 — Google OAuth callback failures must not render raw JSON in a browser
# ══════════════════════════════════════════════════════════════════════════
# OLD: raise HTTPException(400, "Invalid OAuth state") inside a TOP-LEVEL
# NAVIGATION → the user saw {"detail": "Invalid OAuth state"} in the address bar
# with no way back into the app.

@pytest.mark.parametrize("params,code", [
    ({"state": "garbage", "code": "abc"}, "invalid_state"),
    ({"state": "", "code": "abc"}, "invalid_state"),
])
def test_oauth_callback_redirects_instead_of_returning_json(monkeypatch, params, code):
    monkeypatch.setattr(main, "GOOGLE_OAUTH_ENABLED", True)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/api/auth/google/callback", params=params)
    assert r.status_code == 302, r.text
    assert r.headers["location"] == f"/login?oauth_error={code}"
    assert "detail" not in r.text


def test_oauth_callback_missing_code_redirects(monkeypatch):
    """State must match first, so drive the session through /api/auth/google."""
    monkeypatch.setattr(main, "GOOGLE_OAUTH_ENABLED", True)
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(main, "GOOGLE_CLIENT_SECRET", "csec")
    c = TestClient(app, follow_redirects=False)
    start = c.get("/api/auth/google")
    state = re.search(r"state=([^&]+)", start.headers["location"]).group(1)
    r = c.get("/api/auth/google/callback", params={"state": state})
    assert r.status_code == 302
    assert r.headers["location"] == "/login?oauth_error=missing_code"


# ══════════════════════════════════════════════════════════════════════════
# 11 — GET /api/share/{token} is an ALLOW-list
# ══════════════════════════════════════════════════════════════════════════
# OLD: a deny-list of ~10 popped keys — every field not on that list (pdf_name,
# measurements, warnings/_lt_warnings/lt_sanity, per-room pastabos, marker_pct,
# polygon_source, …) shipped to any holder of the public link.

_SHARE_BLOB = {
    "name": "Bendrinamas projektas",
    "company_name": "UAB Statyba",
    "tipas": "interjeras",
    "vat_rate": 21,
    "vat_mode": None,
    "archetipas": "standart",
    "bendras_plotas_m2": 42.0,
    # ── fields that MUST NOT be shared ──
    "pdf_name": "Klientas_Berzu24_KAINOS.pdf",
    "measurements": [{"type": "area", "value": 12.3}],
    "warnings": [{"level": "ERROR", "message": "vidinis"}],
    "_lt_warnings": [{"level": "WARN", "message": "vidinis"}],
    "lt_sanity": {"warnings": [{"message": "vidinis"}], "summary": {}},
    "santrauka": {"dazymo_plotas_total": 419.92},
    "_overrides": {"q_level": "Q3"},
    "_meta": {"cost_eur": 1.23},
    "puslapiai": [{"nr": 1, "tipas": "floor_plan"}],
    "annotations": [{"note": "vidinė pastaba"}],
    "patalpos": [{
        "nr": "01", "pavadinimas": "Vonia", "paskirtis": "vonia",
        "plotas_m2": 6.4, "lubu_aukstis_m": 2.5,
        # room-level internals
        "pastabos": "klientas dar nesumokėjo",
        "marker_pct": [0.5, 0.5], "polygon_pct": [[0, 0], [1, 1]],
        "polygon_source": "corrected", "calculation_trace": {"x": 1},
        "bbox_pct": [0, 0, 1, 1], "_zoom": {"applied": True},
    }],
    "darbu_sarasas": [{
        "eil_nr": "1.1", "aprasymas": "Sienų dažymas", "kiekis": 10,
        "mato_vnt": "m²", "kaina": 5.0, "suma": 50.0, "skyrius": "APDAILA",
        "kategorija": "apdaila", "vnt": "m²",
        "savikaina": 2.0, "_internal_note": "marža 60%",
    }],
}


def _shared_payload(tmp_path, monkeypatch):
    db.upsert_project("p-share", dict(_SHARE_BLOB), user_id=auth._DEV_USER_ID)
    token = "share-token-audit-20260727"
    db.set_share_token("p-share", token)
    r = client.get(f"/api/share/{token}")
    assert r.status_code == 200, r.text
    return r.json()


def test_shared_payload_leaks_no_internal_project_fields(tmp_path, monkeypatch):
    body = _shared_payload(tmp_path, monkeypatch)
    data = body["data"]
    for k in ("pdf_name", "measurements", "warnings", "_lt_warnings", "lt_sanity",
              "santrauka", "_overrides", "_meta", "puslapiai", "annotations",
              "user_id"):
        assert k not in data, f"{k} leaked into the public share payload"
    # and nothing internal survives at the top level either
    blob = str(body)
    assert "Klientas_Berzu24_KAINOS.pdf" not in blob
    assert "klientas dar nesumokėjo" not in blob
    assert "marža 60%" not in blob


def test_shared_rooms_and_rows_are_field_reduced(tmp_path, monkeypatch):
    data = _shared_payload(tmp_path, monkeypatch)["data"]
    room = data["patalpos"][0]
    assert set(room) == {"nr", "pavadinimas", "paskirtis", "plotas_m2",
                         "lubu_aukstis_m"}
    row = data["darbu_sarasas"][0]
    assert "savikaina" not in row and "_internal_note" not in row


def test_shared_payload_keeps_everything_SharedProject_jsx_renders(
        tmp_path, monkeypatch):
    """Field-coverage assertion against frontend/src/pages/SharedProject.jsx."""
    body = _shared_payload(tmp_path, monkeypatch)
    # top level: p.name, p.company_name, p.vat_mode, p.archetipas, p.vat_rate
    for k in ("name", "company_name", "vat_mode", "archetipas", "vat_rate",
              "tipas", "bendras_plotas_m2", "created_at", "id", "shared", "data"):
        assert k in body, f"SharedProject.jsx reads {k}"
    data = body["data"]
    # data.patalpos || data.v8_rooms ; data.darbu_sarasas
    for k in ("patalpos", "v8_rooms", "darbu_sarasas"):
        assert k in data
    room = data["patalpos"][0]
    for k in ("nr", "pavadinimas", "paskirtis", "plotas_m2", "lubu_aukstis_m"):
        assert k in room, f"SharedProject.jsx renders room.{k}"
    row = data["darbu_sarasas"][0]
    # d.eil_nr, d.aprasymas, d.kiekis, d.mato_vnt || d.vnt, d.kaina,
    # d.skyrius || d.kategorija
    for k in ("eil_nr", "aprasymas", "kiekis", "mato_vnt", "vnt", "kaina",
              "skyrius", "kategorija"):
        assert k in row, f"SharedProject.jsx renders row.{k}"


# ══════════════════════════════════════════════════════════════════════════
# 12 — roof pitch + concrete column depth
# ══════════════════════════════════════════════════════════════════════════
# OLD (roof): `float(roof_data.get("pitch_degrees") or 30)` — a correctly-read
# FLAT roof (0°) fell back to 30° and inflated the area by ×1.155, with nothing
# telling the user a default had been used.
# OLD (concrete): `cd = (c.get("depth_mm") or cw) / 1000` — cw is ALREADY in
# metres, so a square column was divided by 1000 twice (1000× too small).

def test_roof_flat_zero_pitch_is_honoured_not_defaulted():
    q = main._calculate_roof_quantities({"pitch_degrees": 0,
                                         "plan_length_mm": 10000,
                                         "plan_width_mm": 8000})
    assert q["slope_factor"] == 1.0
    assert q["kampas_laipsniais"] == 0.0
    assert q["pitch_fallback"] is False
    assert q["tikrasis_plotas_m2"] == q["plano_plotas_m2"]


def test_roof_missing_pitch_falls_back_to_30_and_flags_it():
    q = main._calculate_roof_quantities({"plan_length_mm": 10000,
                                         "plan_width_mm": 8000})
    assert q["kampas_laipsniais"] == 30.0
    assert q["pitch_fallback"] is True
    assert q["slope_factor"] == pytest.approx(1.155, abs=0.001)


def test_roof_absurd_pitch_is_clamped():
    """cos(90°) ≈ 0 → the slope factor would explode toward infinity."""
    q = main._calculate_roof_quantities({"pitch_degrees": 90})
    assert q["kampas_laipsniais"] == 60.0
    assert q["slope_factor"] == pytest.approx(2.0, abs=0.001)


def test_concrete_square_column_without_depth_uses_width_squared():
    q = main._calculate_concrete_quantities(
        {"columns": [{"width_mm": 400, "height_mm": 3000, "count": 1}]})
    assert q["betono_turis_m3"] == pytest.approx(0.4 * 0.4 * 3.0, abs=0.001)
    assert q["klojiniai_m2"] == pytest.approx(2 * (0.4 + 0.4) * 3.0, abs=0.1)


def test_concrete_column_with_explicit_depth_is_unchanged():
    q = main._calculate_concrete_quantities(
        {"columns": [{"width_mm": 400, "depth_mm": 500, "height_mm": 3000,
                      "count": 1}]})
    assert q["betono_turis_m3"] == pytest.approx(0.4 * 0.5 * 3.0, abs=0.001)


# ══════════════════════════════════════════════════════════════════════════
# 13 — chat context truncation honesty
# ══════════════════════════════════════════════════════════════════════════
# OLD: rooms[:50] / pozicijos[:100] / darbai[:100] / warnings[:30] were silent,
# while the system prompt instructs the assistant to "sum across rooms".

def test_chat_context_flags_truncated_lists():
    project = {
        "name": "Didelis",
        "patalpos": [{"nr": str(i)} for i in range(60)],
        "pozicijos": [{"aprasymas": f"p{i}"} for i in range(120)],
        "lt_sanity": {"warnings": [{"message": f"w{i}"} for i in range(40)]},
    }
    ctx = main._build_chat_context(project)
    tr = ctx["_truncated"]
    assert tr["rooms"] == 10
    assert tr["pozicijos"] == 20
    assert tr["darbai"] == 20      # darbai mirrors pozicijos when absent
    assert tr["warnings"] == 10
    assert len(ctx["patalpos"]) == 50
    assert len(ctx["pozicijos"]) == 100


def test_chat_context_small_project_has_no_truncation_marker():
    project = {
        "name": "Mažas",
        "patalpos": [{"nr": str(i)} for i in range(5)],
        "pozicijos": [{"aprasymas": f"p{i}"} for i in range(20)],
    }
    ctx = main._build_chat_context(project)
    assert "_truncated" not in ctx


def test_chat_system_prompt_instructs_partial_data_disclosure():
    assert "_truncated" in main._CHAT_SYSTEM_PROMPT
    assert "IŠ DALIES" in main._CHAT_SYSTEM_PROMPT


# ══════════════════════════════════════════════════════════════════════════
# 14 — /generate-excel Patalpos sheet vs an LT comma-decimal height
# ══════════════════════════════════════════════════════════════════════════
# OLD: f"{float(h_m):.2f} m" on lubu_aukstis_m='2,8' → ValueError → HTTP 500,
# i.e. the whole Excel export died on one legacy room.

def _excel_patalpos_heights(content: bytes):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content))
    ws = wb["Patalpos"]
    return [ws.cell(row=r, column=4).value for r in range(3, ws.max_row + 1)]


def _excel_payload(height):
    return {
        "projektas": "Excel test",
        "eilutes": [{"nr": "1", "aprasymas": "Dažymas", "mato_vnt": "m²",
                     "kiekis": 1, "kaina": 1, "suma": 1, "skyrius": "APDAILA"}],
        "patalpos": [{"nr": "01", "pavadinimas": "Vonia", "plotas_m2": 6.4,
                      "lubu_aukstis_m": height}],
    }


def test_excel_survives_lt_comma_decimal_ceiling_height():
    r = client.post("/generate-excel", json=_excel_payload("2,8"))
    assert r.status_code == 200, r.text[:300]
    assert _excel_patalpos_heights(r.content) == ["2.80 m"]


def test_excel_unparseable_height_falls_back_to_the_default():
    r = client.post("/generate-excel", json=_excel_payload("labai aukštai"))
    assert r.status_code == 200, r.text[:300]
    assert _excel_patalpos_heights(r.content) == ["2.80 m"]


def test_excel_numeric_height_is_unchanged():
    r = client.post("/generate-excel", json=_excel_payload(3.4))
    assert r.status_code == 200
    assert _excel_patalpos_heights(r.content) == ["3.40 m"]


# ══════════════════════════════════════════════════════════════════════════
# 15 — raw str(exc) echoed to clients
# ══════════════════════════════════════════════════════════════════════════
# (the SSE case is covered above in test_stream_error_event_does_not_echo…)

def test_detect_scale_hint_does_not_echo_pdf_library_internals(monkeypatch):
    """OLD: `except Exception as e: return {"found": False, "error": str(e)}` —
    pdfminer messages ("No /Root object!") and file paths went to the client."""
    def _boom(*a, **kw):
        raise RuntimeError("PdfminerException: No /Root object! /var/lib/secret")
    monkeypatch.setattr(main.pdfplumber, "open", _boom)

    r = client.post("/detect-scale-hint",
                    json={"pdf_b64": "JVBERi0xLjQgZmFrZQ=="})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["found"] is False
    assert "PdfminerException" not in body["error"]
    assert "/var/lib/secret" not in body["error"]
    assert "RuntimeError" not in body["error"]
    assert "mastel" in body["error"].lower()


def test_click_to_fill_render_failure_does_not_echo_internals(
        tmp_path, monkeypatch):
    db.upsert_project("p-ctf", {"name": "CTF"}, user_id=auth._DEV_USER_ID)
    monkeypatch.setattr(main, "_billable_user",
                        lambda request: {"id": "u1", "is_admin": True})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)

    import page_raster_cache as _cache

    def _boom(*a, **kw):
        raise RuntimeError("poppler crashed at /var/lib/secret")
    monkeypatch.setattr(_cache, "render_grayscale_from_bytes", _boom)

    r = client.post("/api/click-to-fill", data={
        "project_id": "p-ctf", "page_nr": 1,
        "click_x_pct": 0.5, "click_y_pct": 0.5,
    }, files={"pdf_file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 500
    detail = r.json()["detail"]
    assert "poppler" not in detail and "/var/lib/secret" not in detail
    assert "PDF" in detail


def test_detect_room_polygons_render_failure_does_not_echo_internals(
        tmp_path, monkeypatch):
    """Sibling of the click-to-fill site — same `page render failed: {e}` echo."""
    db.upsert_project("p-drp", {"name": "DRP"}, user_id=auth._DEV_USER_ID)
    monkeypatch.setattr(main, "_billable_user",
                        lambda request: {"id": "u1", "is_admin": True})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)

    import page_raster_cache as _cache

    def _boom(*a, **kw):
        raise RuntimeError("poppler crashed at /var/lib/secret")
    monkeypatch.setattr(_cache, "render_grayscale_from_bytes", _boom)

    r = client.post("/api/projects/p-drp/detect-room-polygons", data={
        "page_nr": 1, "rooms_json": '[{"nr": "01", "plotas_m2": 6.4}]',
    }, files={"pdf_file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 500, r.text[:200]
    detail = r.json()["detail"]
    assert "poppler" not in detail and "/var/lib/secret" not in detail
    assert "PDF" in detail

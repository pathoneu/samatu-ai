"""`POST /api/projects/{id}/rooms/{nr}/outline-at` — a room gets its wall-exact outline from
ONE click inside it, and its walls are read again right away.

Founder, after the first real Patikra run (2026-09-17): „labai sunku suprasti, kur ką pataisyti
galima", „perimetras kai kur labai neteisingas". A room without an outline showed WHY and a blank
perimeter — and nothing on the sheet could fix it. The server only READS here too: it answers with
the room's geometry keys and saves nothing; the sheet patches the room and recomputes on the one
path every other edit takes.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

_PW = "passw0rd123"


def _pct(x_m: float, y_m: float) -> tuple[float, float]:
    return (60 + x_m * PT_PER_M) / 595.2756, (80 + y_m * PT_PER_M) / 841.8898


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "room_outline.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _blob(**room1):
    """Room 01 has NO place on the plan (its badge is not drawn) — the lane cannot outline it."""
    r1 = {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 13.9, **room1}
    r2 = {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 12.3}
    return {"name": "P", "tipas": "interjeras", "patalpos": [r1, r2],
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}}


def _plan() -> bytes:
    sheet = two_rooms()
    sheet.badges = [("2", 5.7, 1.5)]                      # only room 2's number is printed
    return build_plan([sheet])


def _store(project_id="p1", *, user_id=None, blob=None, pdf=True):
    db.upsert_project(project_id, blob or _blob(), user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _plan())


def _click(client, x_m, y_m, nr="01", page=1, project_id="p1"):
    x, y = _pct(x_m, y_m)
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/outline-at", json={"page": page, "x_pct": x, "y_pct": y})


def test_one_click_outlines_the_room_and_reads_its_walls(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = copy.deepcopy(db.get_project("p1"))
    r = _click(TestClient(app), 2.0, 2.5)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok"
    room = out["room"]
    assert room["polygon_source"] == "corrected" and len(room["polygon_pct"]) >= 4
    assert room["_konturas"]["page"] == 1 and room["_konturas"]["saltinis"] == "parodyta"
    assert abs(room["_konturas"]["plotas_m2"] - 12.0) < 0.3 and room["_konturas"]["plotas_nesutampa"] is False
    # the walls were read again: every wall of this room carries its written length
    assert room["perimetras_m"] == 14.0 and room["perimetras_saltinis"] == "matmenu_eilutes"
    assert len(room["_sienos"]) == 4 and room["_perimetras_suma"]["sutampa"] is True
    assert [a["i"] for a in room["_angos_sienose"]["angos"]] == ["02"]
    # only geometry comes back — never a quantity, a name or anything else of the room
    assert "plotas_m2" not in room and "pavadinimas" not in room and "walls_paintable_m2" not in room
    # the neighbour's door now leads to a NAMED room
    assert sorted(a["i"] for a in out["kitu_angos"]["02"]["angos"]) == ["01", "laukas"]
    # …and nothing was saved
    after = db.get_project("p1")
    assert after["patalpos"] == before["patalpos"] and after.get("_meta") == before.get("_meta")


def test_a_perimeter_he_typed_stays_his(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(perimetras_m=15.5, perimetras_saltinis="user_override"))
    room = _click(TestClient(app), 2.0, 2.5).json()["room"]
    assert room["polygon_source"] == "corrected"
    assert room["perimetras_m"] == 15.5 and room["perimetras_saltinis"] == "user_override"


def test_what_a_click_may_not_do_is_said_not_raised(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    taken = _click(c, 5.5, 1.0).json()                     # inside room 02, which the lane outlines from its badge
    assert taken == {"status": "taken", "nr": "02"}
    assert _click(c, -2.0, 1.0).json() == {"status": "outside"}


def test_bad_requests(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    assert c.post("/api/projects/p1/rooms/01/outline-at", json={"page": 1, "x_pct": 1.4, "y_pct": 0.5}).status_code == 422
    assert c.post("/api/projects/p1/rooms/01/outline-at", json={"page": 0, "x_pct": 0.4, "y_pct": 0.5}).status_code == 422
    assert c.post("/api/projects/p1/rooms/01/outline-at", json={"page": 9, "x_pct": 0.4, "y_pct": 0.5}).status_code == 400
    assert _click(c, 2.0, 2.5, nr="77").status_code == 404
    assert _click(c, 2.0, 2.5, project_id="nope").status_code == 404


def test_a_project_without_its_drawing_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    r = _click(TestClient(app), 2.0, 2.5)
    assert r.status_code == 404 and "brėžinio saugykloje nėra" in r.json()["detail"]


def test_anonymous_and_strangers(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    _store(user_id=owner["id"])
    c = TestClient(app)
    assert _click(c, 2.0, 2.5).status_code == 401
    assert c.post("/api/auth/login", json={"email": "thief@x.lt", "password": _PW}).status_code == 200
    assert _click(c, 2.0, 2.5).status_code == 404


@pytest.mark.parametrize("bad", ["..%2F..%2Fetc", "a b"])
def test_a_strange_project_id_is_rejected(tmp_path, monkeypatch, bad):
    _isolate(tmp_path, monkeypatch)
    x, y = _pct(2.0, 2.5)
    r = TestClient(app).post(f"/api/projects/{bad}/rooms/01/outline-at", json={"page": 1, "x_pct": x, "y_pct": y})
    assert r.status_code in (400, 404)


# ── the perimeter fact says whose outline it is ──────────────────────────────

def _perimeter_fact(**konturas):
    from extractor.room_facts import build_room_facts
    ring = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]
    room = {"nr": "01", "puslapio_nr": 1, "plotas_m2": 4.48, "polygon_pct": ring, "polygon_source": "corrected",
            "perimetras_m": 6.85, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 6.85, "kontrole_m": 6.77, "sutampa": True, "lapai": [1], "eilutes": ["600", "996"]},
            "_sienos": [], "_konturas": {"page": 1, "plotas_m2": 2.86, "plotas_uzrasas_m2": 4.48, **konturas}}
    return next(f for f in build_room_facts({"patalpos": [room]}, "01")["facts"] if f["key"] == "perimetras")


def test_an_outline_he_pointed_at_is_said_and_its_area_is_compared_with_the_table():
    f = _perimeter_fact(saltinis="parodyta", paklaida=0.3616)
    assert f["status"] == "read"
    assert f["sentence"].endswith("Patalpą brėžinyje parodėte patys: kontūro plotas 2,86 m², lentelėje užrašyta 4,48 m².")
    agrees = _perimeter_fact(saltinis="parodyta", paklaida=0.02)
    assert agrees["sentence"].endswith("Patalpą brėžinyje parodėte patys.")
    traced = _perimeter_fact(saltinis="vektoriniai_konturai", paklaida=0.3616)
    assert "parodėte" not in traced["sentence"]

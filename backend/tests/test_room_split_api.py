"""`POST /api/projects/{id}/rooms/{nr}/split-space` — two rooms no wall separates get their own outlines
from ONE line a person draws, and their walls are read right away.

A kitchen and a living room are usually the biggest rooms of a flat. The geometry lane says honestly that
no wall separates them and gives each an ESTIMATE — the shared walls by floor area; on the check sheet
that was two blank perimeters with nothing to do about them. The server only READS: both rooms' geometry
keys come back, nothing is saved, and the boundary itself is never a wall.
"""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

_PW = "passw0rd123"


def _pct(x_m: float, y_m: float) -> dict:
    return {"x_pct": (60 + x_m * PT_PER_M) / 595.2756, "y_pct": (80 + y_m * PT_PER_M) / 841.8898}


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "room_split.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _blob():
    rooms = [{"nr": "01", "pavadinimas": "Virtuvė", "plotas_m2": 12.3, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 13.9},
             {"nr": "02", "pavadinimas": "Svetainė", "plotas_m2": 9.3, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 12.3}]
    return {"name": "P", "tipas": "interjeras", "patalpos": rooms, "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}}


def _plan() -> bytes:
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if abs(w[0] - 4.2) > 0.01]              # no partition: one space
    sheet.dims = [d for d in sheet.dims if not (abs(d[1] - d[3]) < 1e-6 and 3.9 < d[1] < 4.7)]   # …and no strings along it
    return build_plan([sheet])


def _store(project_id="p1", *, user_id=None, pdf=True):
    db.upsert_project(project_id, _blob(), user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _plan())


def _split(client, x_m=4.3, nr="01", project_id="p1"):
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/split-space",
                       json={"page": 1, "a": _pct(x_m, 0.1), "b": _pct(x_m, 3.3)})


def test_one_line_gives_both_rooms_their_outlines_and_walls(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = copy.deepcopy(db.get_project("p1"))
    r = _split(TestClient(app))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and set(out["rooms"]) == {"01", "02"}
    one, two = out["rooms"]["01"], out["rooms"]["02"]
    for room in (one, two):
        assert room["polygon_source"] == "corrected" and room["_konturas"]["saltinis"] == "padalinta"
        assert len(room["_konturas"]["menamos"]) == 1 and room["_atvira_erdve"] is None
        assert "plotas_m2" not in room and "pavadinimas" not in room
    assert abs(one["_konturas"]["plotas_m2"] - 12.3) < 0.3 and abs(two["_konturas"]["plotas_m2"] - 9.3) < 0.3
    # the walls were read again — three real walls each, the boundary is not one of them
    assert len(one["_sienos"]) == 3 and len(two["_sienos"]) == 3
    assert one["perimetras_m"] < 13.0 and two["perimetras_m"] < 10.5
    after = db.get_project("p1")
    assert after["patalpos"] == before["patalpos"] and after.get("_meta") == before.get("_meta")


def test_a_line_that_does_not_divide_is_said_not_raised(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    assert _split(TestClient(app), x_m=6.9).json() == {"status": "bad_line"}


def test_a_room_that_shares_no_space_has_nothing_to_divide(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob())
    storage.get_storage().put(storage.pdf_key("p1"), build_plan([two_rooms()]))     # WITH the partition
    assert _split(TestClient(app)).json() == {"status": "not_shared"}


def test_bad_requests_and_strangers(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    _store(user_id=owner["id"])
    c = TestClient(app)
    assert _split(c).status_code == 401
    assert c.post("/api/auth/login", json={"email": "thief@x.lt", "password": _PW}).status_code == 200
    assert _split(c).status_code == 404
    assert c.post("/api/auth/logout").status_code in (200, 204)
    assert c.post("/api/auth/login", json={"email": "owner@x.lt", "password": _PW}).status_code == 200
    assert _split(c, nr="77").status_code == 404
    bad = c.post("/api/projects/p1/rooms/01/split-space", json={"page": 1, "a": {"x_pct": 1.5, "y_pct": 0.2}, "b": _pct(4.3, 3.3)})
    assert bad.status_code == 422


# ── the perimeter fact of a divided room ─────────────────────────────────────

def _perimeter_fact(**konturas):
    from extractor.room_facts import build_room_facts
    ring = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]
    room = {"nr": "04", "puslapio_nr": 1, "plotas_m2": 26.31, "polygon_pct": ring, "polygon_source": "corrected",
            "perimetras_m": 18.39, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 18.39, "kontrole_m": 18.4, "sutampa": True, "lapai": [1], "eilutes": ["4100", "3000"]},
            "_sienos": [], "_konturas": {"page": 1, "plotas_m2": 26.61, "plotas_uzrasas_m2": 26.31, "paklaida": 0.0113,
                                         "menamos": [[[0.4, 0.2], [0.4, 0.35]]], "su": ["05"], "saltinis": "padalinta", **konturas}}
    return next(f for f in build_room_facts({"patalpos": [room]}, "04")["facts"] if f["key"] == "perimetras")


def test_a_divided_room_says_the_boundary_is_not_a_wall_and_draws_it():
    f = _perimeter_fact()
    assert f["status"] == "read"
    assert f["sentence"].endswith("Bendrą erdvę su patalpa 05 padalijote patys — riba tarp jų menama (sienos ten nėra), "
                                  "į perimetrą neįskaičiuota.")
    assert f["outline"]["menamos"] == [[[0.4, 0.2], [0.4, 0.35]]]
    off = _perimeter_fact(paklaida=0.21, plotas_m2=31.9)
    assert "kontūro plotas 31,90 m², lentelėje užrašyta 26,31 m²" in off["sentence"]


def test_a_divided_room_whose_walls_could_not_all_be_added_still_says_whose_boundary_it_is():
    f = _perimeter_fact()
    from extractor.room_facts import build_room_facts
    ring = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]
    room = {"nr": "04", "puslapio_nr": 1, "plotas_m2": 26.31, "polygon_pct": ring, "polygon_source": "corrected",
            "perimetras_m": 18.41, "perimetras_saltinis": "konturo_ivertis", "_perimetras_ivertis_m": 18.41,
            "_perimetras_ivertis_saltinis": "konturas", "_perimetras_priezastis": "1 iš 9 sienų be matmens",
            "_konturas": {"page": 1, "plotas_m2": 26.61, "plotas_uzrasas_m2": 26.31, "paklaida": 0.0113,
                          "menamos": [[[0.4, 0.2], [0.4, 0.35]]], "su": ["05"], "saltinis": "padalinta"}}
    blank = next(x for x in build_room_facts({"patalpos": [room]}, "04")["facts"] if x["key"] == "perimetras")
    assert blank["status"] == "missing" and blank["suggestion"]["value"] == 18.41
    assert blank["sentence"].endswith("Bendrą erdvę su patalpa 05 padalijote patys — riba tarp jų menama (sienos ten nėra), "
                                      "į perimetrą neįskaičiuota.")
    assert f["sentence"].count("padalijote patys") == 1

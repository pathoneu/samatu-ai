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
from tests.synthetic_plan import PT_PER_M, build_plan, pocket_and_room, two_rooms  # noqa: E402

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


def _click(client, x_m, y_m, nr="01", page=1, project_id="p1", **more):
    x, y = _pct(x_m, y_m)
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/outline-at", json={"page": page, "x_pct": x, "y_pct": y, **more})


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


def test_tinka_on_a_proposed_outline_is_the_same_click_and_says_whose_it_is(tmp_path, monkeypatch):
    """2026-09-23: the lane proposes the face the walls close when the table disagrees; „Tinka" sends the point
    inside it with `pritarta` — the outline is his, the sentence says the program offered it, the proposal goes."""
    _isolate(tmp_path, monkeypatch)
    blob = _blob(_konturo_siulymas={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], "plotas_m2": 12.0,
                                   "perimetras_m": 14.0, "paklaida": 0.3, "taskas_pct": [0.15, 0.13]})
    _store(blob=blob)
    room = _click(TestClient(app), 2.0, 2.5, pritarta=True).json()["room"]
    assert room["polygon_source"] == "corrected" and room["_konturas"]["saltinis"] == "pasiulyta"
    assert room["_konturo_siulymas"] is None and room["perimetras_m"] == 14.0


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


def test_an_accepted_proposal_is_said_to_be_the_programs_offer_that_he_confirmed():
    f = _perimeter_fact(saltinis="pasiulyta", paklaida=0.3616)
    assert f["status"] == "read"
    assert f["sentence"].endswith("Kontūrą pasiūliau pagal sienas prie patalpos numerio — patvirtinote. Kontūro plotas 2,86 m², "
                                  "lentelėje užrašyta 4,48 m² — plotui imamas užrašas, kontūras tik sienoms.")
    assert _perimeter_fact(saltinis="pasiulyta", paklaida=0.02)["sentence"].endswith("prie patalpos numerio — patvirtinote.")


# ── a click in the neighbour's room from a pocket: the joined space, proposed — „Tinka" or a drawn line ──

def _pocket_blob():
    """Room 01's walls close 3 m² (its number is printed there); the table gives it 9 — far more than the
    neighbour can spare, so the lane leaves it a proposal and outlines 02 (15 m²) on its own."""
    r1 = {"nr": "01", "pavadinimas": "A", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 12.0}
    r2 = {"nr": "02", "pavadinimas": "B", "plotas_m2": 15.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 16.0}
    return {"name": "P", "tipas": "interjeras", "patalpos": [r1, r2], "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}}


def _store_pocket(project_id="p1"):
    db.upsert_project(project_id, _pocket_blob(), user_id=None)
    storage.get_storage().put(storage.pdf_key(project_id), build_plan([pocket_and_room()]))


def test_a_click_in_the_neighbours_room_from_a_pocket_proposes_the_boundary_between_them(tmp_path, monkeypatch):
    """2026-09-23: „jei patalpa didesnė — spustelėkite kitoje jos vietoje … bet paspaudus nieko negali padaryti".
    The place belongs to room 02 (the lane's outline); 01's walls close a pocket beside it: one space, proposed."""
    _isolate(tmp_path, monkeypatch)
    _store_pocket()
    c = TestClient(app)
    out = _click(c, 4.0, 2.5).json()                          # inside room 02, from room 01
    assert out["status"] == "shared" and out["su"] == "02" and out["page"] == 1 and out["pagal"] == "plotai"
    assert set(out["rooms"]) == {"01", "02"} and len(out["line_pct"]) == 2
    assert out["rooms"]["01"]["plotas_uzrasas_m2"] == 9.0 and out["rooms"]["01"]["plotas_m2"] > 3.5
    assert len(out["rooms"]["01"]["menamos"]) == 1
    # „Tinka": the same click, labelled — both rooms come back divided, nothing saved
    before = copy.deepcopy(db.get_project("p1"))
    ok = _click(c, 4.0, 2.5, pritarta=True).json()
    assert ok["status"] == "ok" and set(ok["rooms"]) == {"01", "02"}
    for nr, other in (("01", "02"), ("02", "01")):
        room = ok["rooms"][nr]
        assert room["polygon_source"] == "corrected" and room["_konturas"]["saltinis"] == "padalinta" and room["_konturas"]["su"] == [other]
    assert db.get_project("p1")["patalpos"] == before["patalpos"]
    # a click in a room a PERSON outlined is never a proposal: the place is simply taken
    blob = _pocket_blob()
    blob["patalpos"][1].update({"polygon_pct": ok["rooms"]["02"]["polygon_pct"], "polygon_source": "corrected"})
    db.upsert_project("p2", blob, user_id=None)
    storage.get_storage().put(storage.pdf_key("p2"), build_plan([pocket_and_room()]))
    assert _click(c, 5.5, 2.5, project_id="p2").json() == {"status": "taken", "nr": "02"}


def test_nubresiu_pats_after_such_a_click_cuts_the_joined_space_along_his_line(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store_pocket()
    ax, ay = _pct(2.0, -0.5)
    bx, by = _pct(2.0, 4.0)
    out = TestClient(app).post("/api/projects/p1/rooms/01/split-space",
                               json={"page": 1, "a": {"x_pct": ax, "y_pct": ay}, "b": {"x_pct": bx, "y_pct": by}, "su": "02"}).json()
    assert out["status"] == "ok" and set(out["rooms"]) == {"01", "02"}
    assert abs(out["rooms"]["01"]["_konturas"]["plotas_m2"] - 5.0) < 0.4      # 3 m² pocket + 0,2 m² opening + a 0,6 m strip
    assert out["rooms"]["01"]["_konturas"]["saltinis"] == "padalinta" and out["rooms"]["01"]["_konturas"]["menamos"]
    # without the neighbour named, this room shares no space
    out2 = TestClient(app).post("/api/projects/p1/rooms/01/split-space",
                                json={"page": 1, "a": {"x_pct": ax, "y_pct": ay}, "b": {"x_pct": bx, "y_pct": by}}).json()
    assert out2["status"] == "not_shared"


# ── outline-set (2026-10-16): a ring a person drew or edited vertex by vertex ──────────────────────

def _set(client, ring_m, nr="01", page=1, project_id="p1"):
    ring = [list(_pct(x, y)) for x, y in ring_m]
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/outline-set", json={"page": page, "polygon_pct": ring})


def test_a_drawn_ring_becomes_the_corrected_outline_and_the_walls_are_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    r = _set(TestClient(app), [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)])   # room 1's inner faces
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok"
    room = out["room"]
    assert room["polygon_source"] == "corrected" and len(room["polygon_pct"]) == 4
    assert room["_konturas"]["saltinis"] == "nubrezta" and room["_konturas"]["page"] == 1
    assert abs(room["_konturas"]["plotas_m2"] - 12.0) < 0.2
    assert abs(room["_konturas"]["perimetras_m"] - 14.0) < 0.2
    # its walls were read again from the drawing — dimension strings along the drawn ring
    assert room.get("_sienos")
    assert room["perimetras_saltinis"] in ("matmenu_eilutes", "sienu_konturas", "konturo_ivertis")
    assert "_angos_sienose" in room


def test_outline_set_rejects_a_degenerate_ring(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    assert c.post("/api/projects/p1/rooms/01/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.2]]}).status_code == 422
    assert c.post("/api/projects/p1/rooms/01/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.1, 0.1], [0.1, 0.1]]}).status_code == 400
    assert c.post("/api/projects/p1/rooms/99/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]}).status_code == 404


# ── holes („Atimti", 2026-10-16): a column or a shaft cut out of a drawn outline ─────────────────────

def _set_holes(client, ring_m, holes_m, nr="01", page=1, project_id="p1"):
    ring = [list(_pct(x, y)) for x, y in ring_m]
    holes = [[list(_pct(x, y)) for x, y in h] for h in holes_m]
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/outline-set",
                       json={"page": page, "polygon_pct": ring, "holes": holes})


def test_a_hole_comes_off_the_area_and_its_perimeter_is_kept_apart(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    outer = [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)]
    column = [(1.0, 1.0), (1.5, 1.0), (1.5, 1.5), (1.0, 1.5)]          # 0,5 × 0,5 m
    r = _set_holes(TestClient(app), outer, [column])
    assert r.status_code == 200, r.text
    room = r.json()["room"]
    k = room["_konturas"]
    assert abs(k["plotas_m2"] - (12.0 - 0.25)) < 0.2                    # outer − hole
    assert abs(k["perimetras_m"] - 14.0) < 0.2                          # the OUTER ring only
    assert abs(k["skyliu_plotas_m2"] - 0.25) < 0.02 and abs(k["skyliu_perimetras_m"] - 2.0) < 0.05
    # one record per hole; with no answer to „Kas atimama?" a hole is a column — its faces are walls
    assert len(k["skyles"]) == 1 and k["skyles"][0]["sienos"] is True and k["skyles"][0]["kampai"] == 4
    assert abs(k["skyles"][0]["perimetras_m"] - 2.0) < 0.05 and abs(k["skyles"][0]["plotas_m2"] - 0.25) < 0.02
    assert len(room["polygon_holes_pct"]) == 1 and len(room["polygon_holes_pct"][0]) == 4
    # a ring without holes clears the ones it had
    plain = _set(TestClient(app), outer).json()["room"]
    assert plain["polygon_holes_pct"] is None and "skyles" not in plain["_konturas"]


def test_each_hole_keeps_his_answer_whether_it_has_walls(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    outer = [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)]
    column = [(1.0, 1.0), (1.5, 1.0), (1.5, 1.5), (1.0, 1.5)]
    floor_hole = [(2.5, 1.0), (3.5, 1.0), (3.5, 2.0), (2.5, 2.0)]
    ring = [list(_pct(x, y)) for x, y in outer]
    holes = [[list(_pct(x, y)) for x, y in h] for h in (column, floor_hole)]
    r = TestClient(app).post("/api/projects/p1/rooms/01/outline-set",
                             json={"page": 1, "polygon_pct": ring, "holes": holes, "holes_walls": [True, False]})
    assert r.status_code == 200, r.text
    k = r.json()["room"]["_konturas"]
    assert [h["sienos"] for h in k["skyles"]] == [True, False]
    assert abs(k["skyliu_perimetras_m"] - 6.0) < 0.1                     # both holes' edges, as before


def test_a_hole_outside_the_outline_or_overlapping_another_is_refused(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    t = 0.2
    outer = [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)]
    out = _set_holes(c, outer, [[(3.9, 1.0), (4.8, 1.0), (4.8, 1.5), (3.9, 1.5)]])
    assert out.status_code == 400 and "kontūro viduje" in out.json()["detail"]
    a = [(1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0)]
    b = [(1.5, 1.5), (2.5, 1.5), (2.5, 2.5), (1.5, 2.5)]
    assert _set_holes(c, outer, [a, b]).status_code == 400
    assert c.post("/api/projects/p1/rooms/01/outline-set",
                  json={"page": 1, "polygon_pct": [list(_pct(x, y)) for x, y in outer], "holes": [[[0.3, 0.3], [0.31, 0.3]]]}).status_code == 400
    assert c.post("/api/projects/p1/rooms/01/outline-set",
                  json={"page": 1, "polygon_pct": [list(_pct(x, y)) for x, y in outer], "holes": [[[0.3, 0.3], [1.3, 0.3], [0.3, 0.4]]]}).status_code == 400


# ── outline-merge („Sujungti", 2026-10-16): one room absorbed into another ─────────────────────────────

def _merge(client, ring_m, *, gone="02", kept="01", page=1, project_id="p1"):
    ring = [list(_pct(x, y)) for x, y in ring_m]
    return client.post(f"/api/projects/{project_id}/rooms/{gone}/outline-merge",
                       json={"page": page, "kept_nr": kept, "polygon_pct": ring})


def test_merge_bills_both_rows_in_the_kept_room_and_marks_the_other_structurally(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    blob = _blob(elementai=[{"tipas": "duris", "kiekis": 1}])
    blob["patalpos"][1]["elementai"] = [{"tipas": "langas", "kiekis": 2}, {"tipas": "duris", "kiekis": 1}]
    _store(blob=blob)
    before = copy.deepcopy(db.get_project("p1"))
    t = 0.2
    union = [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]       # both rooms and the partition between them
    r = _merge(TestClient(app), union)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and "neskaiciuoti" not in out
    kept, gone = out["rooms"]["01"], out["rooms"]["02"]
    assert kept["polygon_source"] == "corrected" and kept["_konturas"]["saltinis"] == "nubrezta"
    assert kept["_konturas"]["prijungta"] == ["02"] and kept["_konturas"]["plotas_uzrasas_kartu_m2"] == 21.0
    # the drawn union is compared with BOTH printed areas, not with the kept room's alone
    assert abs(kept["_konturas"]["plotas_m2"] - 21.6) < 0.3 and abs(kept["_konturas"]["paklaida"]) < 0.05
    # the kept room bills both table rows, and says so
    k = out["sujungimas"]["01"]
    assert k["plotas_m2"] == 21.0 and k["plotas_saltinis"] == "eksplikacija_sujungta" and k["_plotas_pries_sujungima"] == 12.0
    assert k["_sujungimas"]["sakinys"] == "Plotas: 12,00 + 9,00 m² iš eksplikacijos — patalpos sujungtos"
    assert k["_sujungimas"]["su"] == ["02"]
    # a window in the absorbed half is still a window: its openings move into the kept room, marked where from
    assert [(e["tipas"], e["kiekis"], e.get("_is_patalpos")) for e in k["elementai"]] == [
        ("duris", 1, None), ("langas", 2, "02"), ("duris", 1, "02")]
    # the absorbed room keeps its table row, no outline and no openings of its own — marked structurally
    g = out["sujungimas"]["02"]
    assert g["_sujungta_i"] == "01" and g["elementai"] == [] and len(g["_elementai_pries_sujungima"]) == 2
    assert g["plotas_m2"] == 9.0
    assert gone["polygon_pct"] is None and gone["polygon_source"] is None
    assert gone["_konturas"] == {"page": 1, "saltinis": "sujungta", "i": "01", "plotas_m2": 0.0, "perimetras_m": 0.0,
                                 "plotas_uzrasas_m2": 9.0}
    assert gone["_sienos"] is None and gone["_angos_sienose"] is None
    # …and nothing was saved
    assert db.get_project("p1")["patalpos"] == before["patalpos"]


def test_a_merged_room_cannot_be_merged_again(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    blob = _blob()
    blob["patalpos"][1]["_sujungta_i"] = "01"
    _store(blob=blob)
    t = 0.2
    r = _merge(TestClient(app), [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)])
    assert r.status_code == 400 and "jau sujungta" in r.json()["detail"]


def test_merge_bad_requests(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    t = 0.2
    union = [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]
    assert _merge(c, union, gone="01", kept="01").status_code == 400
    assert _merge(c, union, gone="77").status_code == 404
    assert _merge(c, union, kept="77").status_code == 404
    assert _merge(c, union, project_id="nope").status_code == 404
    assert c.post("/api/projects/p1/rooms/02/outline-merge", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]}).status_code == 422


@pytest.mark.parametrize("k_a, k_b, expected", [
    (14.2, 12.2, 15.0 + 13.0 - 6.0),     # two drawn outlines meeting along a 3 m line: that run, once on each side, goes
    (11.2, 9.2, 15.0 + 13.0),            # an open space divided by an imaginary line: neither outline counted it
])
def test_a_merge_of_typed_perimeters_keeps_both_rooms_walls_less_the_shared_run(tmp_path, monkeypatch, k_a, k_b, expected):
    _isolate(tmp_path, monkeypatch)
    ring = lambda x0, x1: [list(_pct(x, y)) for x, y in ((x0, 0.2), (x1, 0.2), (x1, 3.2), (x0, 3.2))]  # noqa: E731
    blob = _blob(perimetras_m=15.0, perimetras_saltinis="user_override", polygon_pct=ring(0.2, 4.3), polygon_source="corrected",
                 _konturas={"page": 1, "perimetras_m": k_a, "saltinis": "nubrezta"})
    blob["patalpos"][1].update(perimetras_m=13.0, perimetras_saltinis="user_override", polygon_pct=ring(4.3, 7.4),
                               polygon_source="corrected", _konturas={"page": 1, "perimetras_m": k_b, "saltinis": "nubrezta"})
    _store(blob=blob)
    union = [(0.2, 0.2), (7.4, 0.2), (7.4, 3.2), (0.2, 3.2)]                # 7,2 × 3 m: 20,4 m round
    out = _merge(TestClient(app), union).json()
    kept = out["rooms"]["01"]
    assert kept["perimetras_saltinis"] == "user_override"
    assert kept["perimetras_m"] == pytest.approx(expected, abs=0.05)
    k = out["sujungimas"]["01"]
    assert k["_perimetras_pries_sujungima"] == 15.0 and k["_sujungimas"]["perimetras"].startswith("Perimetras: 15,00 + 13,00")


def test_a_merge_of_rooms_with_different_floors_says_what_moves_before_and_after(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    blob = _blob(grindu_danga="plyteles", plyteles_grindys_m2=12.0)
    blob["patalpos"][1].update(grindu_danga="minksta", pvc_grindys_m2=9.0)
    _store(blob=blob)
    t = 0.2
    out = _merge(TestClient(app), [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]).json()
    want = ("Patalpų apdaila skiriasi: 02 grindys parketas arba laminatas, 01 plytelės — sujungus visam plotui "
            "(21,00 m²) bus taikoma 01 apdaila; 9,00 m² pereis iš parketo arba laminato į plyteles.")
    assert out["ispejimas"] == want
    assert out["sujungimas"]["01"]["_sujungimas"]["apdaila_skiriasi"] == want


def test_a_merge_of_rooms_with_the_same_finish_warns_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    out = _merge(TestClient(app), [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]).json()
    assert out["ispejimas"] is None and "apdaila_skiriasi" not in out["sujungimas"]["01"]["_sujungimas"]


def test_a_merge_counts_the_union_outlines_corners_and_keeps_both_rooms_partition_ends(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    blob = _blob(n_partition_walls=2)
    blob["patalpos"][1]["n_partition_walls"] = 3
    _store(blob=blob)
    t = 0.2
    out = _merge(TestClient(app), [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]).json()
    k = out["sujungimas"]["01"]
    assert (k["_sujungimas"]["kampai_vidiniai"], k["_sujungimas"]["kampai_isoriniai"]) == (4, 0)      # a rectangle
    assert k["n_partition_walls"] == 5 and k["_sujungimas"]["pertvaru_galai_dalys"] == [2, 3]
    assert k["_sujungimas"]["kampai"] == "Kampai iš sujungto kontūro: 4 vidiniai, 0 išoriniai; pertvarų galai: 2 + 3 iš sujungtų patalpų — pataisykite patalpos lape"


# ── the kept room's floor covering survives the merge (W0-A-2, Pathon v3 W1-F) ─────────────────────────

_FLOOR_READ = {"danga": "plyteles", "page": 1, "irodymas": "rastas", "tekstas": "60 x 60 cm plytelė", "plotas_m2": None,
               "rect_pct": [0.1, 0.1, 0.3, 0.3]}


def _floors_blob():
    """01's floor plan says tiles, 02's says laminate — both READ from the plan (`grindu_planas`)."""
    blob = _blob(grindu_danga="plyteles", grindu_danga_saltinis="grindu_planas", _grindu_danga=dict(_FLOOR_READ),
                 plyteles_grindys_m2=12.0)
    blob["patalpos"][1].update(grindu_danga="minksta", grindu_danga_saltinis="grindu_planas", pvc_grindys_m2=9.0,
                               _grindu_danga={**_FLOOR_READ, "danga": "minksta", "tekstas": "Laminatas"})
    return blob


def _landed(stored: dict, out: dict) -> dict:
    """What the sheet does with the answer: geometry keys and merge keys onto the rooms (null = remove)."""
    project = copy.deepcopy(stored)
    for r in project["patalpos"]:
        for part in ("rooms", "sujungimas"):
            for k, v in (out[part].get(str(r["nr"])) or {}).items():
                if v is None:
                    r.pop(k, None)
                else:
                    r[k] = v
    return project


def test_a_merge_keeps_the_floor_covering_the_plan_gives_the_kept_room(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_floors_blob())
    t = 0.2
    out = _merge(TestClient(app), [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]).json()
    kept = out["rooms"]["01"]
    # „Visam plotui taikoma patalpos 01 apdaila": 01's tiles, as the floor plan read them — never „—"
    assert kept["grindu_danga"] == "plyteles" and kept["grindu_danga_saltinis"] == "grindu_planas"
    assert kept["_grindu_danga"] == _FLOOR_READ and kept["_grindu_dangos_dvi"] is None
    # the two coverings differ: the finishes warning is still said, before and after
    assert out["ispejimas"].startswith("Patalpų apdaila skiriasi: 02 grindys parketas arba laminatas, 01 plytelės")
    assert out["sujungimas"]["01"]["_sujungimas"]["apdaila_skiriasi"] == out["ispejimas"]


def test_after_a_merge_patikra_does_not_ask_the_kept_rooms_floor_again(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_floors_blob())
    c = TestClient(app)

    def asked():
        qs = c.get("/api/projects/p1/questions").json()["questions"]
        return [i["room_nr"] for q in qs if q["kind"] == "grindys" for i in q["items"]]
    assert asked() == []
    t = 0.2
    out = _merge(c, [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]).json()
    db.upsert_project("p1", _landed(db.get_project("p1"), out))
    assert asked() == []
    fact = next(f for f in c.get("/api/projects/p1/rooms/01/facts").json()["facts"] if f["key"] == "grindys")
    assert fact["status"] == "read" and fact["value"] == "plytelės"
    # the founder guide's next step, „Atimti" a column inside the merged room, re-reads its outline: the union
    # still holds both coverings, and the merged room's covering is still the one the merge kept
    ring = [(t, t), (7 + 2 * t, t), (7 + 2 * t, 3 + t), (t, 3 + t)]
    hole = [(1.0, 1.0), (1.5, 1.0), (1.5, 1.5), (1.0, 1.5)]
    after = _set_holes(c, ring, [hole]).json()
    assert after["room"]["grindu_danga"] == "plyteles" and after["room"]["_grindu_danga"] == _FLOOR_READ
    db.upsert_project("p1", _landed(db.get_project("p1"), {"rooms": {"01": after["room"]}, "sujungimas": {}}))
    assert asked() == []

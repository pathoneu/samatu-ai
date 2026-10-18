"""Exports (v3 W7-A M5): grouping by aukštas / butas, and the internal copy's
„Pakeitimų žurnalas" sheet.

The invariant every grouping keeps (each line's kiekis and suma unchanged) is
already parametrised over GROUPINGS in tests/test_export_grouping.py, so the
two new modes are held to it there; these tests pin what is new.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
from api.change_log_sheet import SHEET_TITLE, describe  # noqa: E402
from api.export_grouping import (  # noqa: E402
    UNASSIGNED_ROOMS, UNKNOWN_FLAT, UNKNOWN_FLOOR, floor_label, group_export_lines, room_floor,
    totals_by_line,
)

ROOMS = [{"nr": "1F-01", "pavadinimas": "Svetainė", "butas": "2"},
         {"nr": "2F-01", "pavadinimas": "Miegamasis", "butas": "10"},
         {"nr": "05", "pavadinimas": "Sandėliukas"},
         {"nr": "07", "pavadinimas": "Rūsys", "aukstas": 0, "butas": "2"}]


def _lines():
    return [{"nr": "1", "skyrius": "Dažymas", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
             "kiekis": 40.0, "kaina": 5.0, "confidence": "zalia",
             "dalys": [{"room_nr": "2F-01", "room_name": "Miegamasis", "page": 1, "value": 10.0},
                       {"room_nr": "1F-01", "room_name": "Svetainė", "page": 1, "value": 10.0},
                       {"room_nr": "05", "room_name": "Sandėliukas", "page": 1, "value": 8.0},
                       {"room_nr": "07", "room_name": "Rūsys", "page": 1, "value": 7.0}]}]


def test_floor_comes_only_from_the_project_never_a_guess():
    assert room_floor({"nr": "2F-01"}) == 2
    assert room_floor({"nr": "05"}) is None            # a bare number names no floor
    assert room_floor({"nr": "05", "aukstas": 3}) == 3  # the room's own value wins
    assert floor_label(0).startswith("Rūsys") and floor_label(None) == UNKNOWN_FLOOR


def test_aukstai_groups_by_floor_unknown_and_unassigned_last():
    rows = group_export_lines(_lines(), "aukstai", rooms=ROOMS)
    heads = [r["skyrius"] for r in rows]
    assert heads == ["Rūsys (0 aukštas)", "1 aukštas", "2 aukštas", UNKNOWN_FLOOR, UNASSIGNED_ROOMS]
    assert totals_by_line(rows)["1"] == pytest.approx(40.0)
    assert rows[-1]["kiekis"] == pytest.approx(5.0)     # the part no room produced, labelled


def test_butai_groups_by_flat_in_number_order():
    rows = group_export_lines(_lines(), "butai", rooms=ROOMS)
    heads = [r["skyrius"] for r in rows]
    assert heads == ["Butas 2", "Butas 2", "Butas 10", UNKNOWN_FLAT, UNASSIGNED_ROOMS]
    assert totals_by_line(rows)["1"] == pytest.approx(40.0)


def test_change_log_labels_are_plain_words():
    assert describe("lubu_auksciai.104") == ("Lubų aukštis", "104")
    assert describe("patalpa.04.kontūras") == ("Patalpos kontūras", "04")
    assert describe("simbolis.3.durys-ai")[0] == "Simbolio sprendimas (lapas 3)"
    assert describe("some.internal_key.x")[0] == "Kitas pakeitimas"


# ── the sheet itself, through /generate-excel ────────────────────────────────

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "m5.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    other = db.create_user("other@x.lt", auth.hash_password(_PW), name="K")
    db.upsert_project("m5-own", {"name": "Mano", "tipas": "interjeras"}, user_id=owner["id"])
    db.upsert_project("m5-other", {"name": "Kito", "tipas": "interjeras"}, user_id=other["id"])
    db.log_correction("m5-own", "lubu_auksciai.104", 2.7, 3.1, source="prielaidos")
    db.log_correction("m5-other", "lubu_auksciai.201", 2.5, 2.9, source="prielaidos")
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "owner@x.lt", "password": _PW}).status_code == 200
    return c


def _sheets(c, **extra):
    body = {"projektas": "Mano", "eilutes": [{"nr": "1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
                                              "kiekis": 10, "kaina": 5, "suma": 50, "skyrius": "Dažymas"}],
            **extra}
    r = c.post("/generate-excel", json=body)
    assert r.status_code == 200, r.text
    return load_workbook(io.BytesIO(r.content))


def test_internal_copy_lists_his_changes(env):
    wb = _sheets(env, vidine_kopija=True, project_id="m5-own")
    assert SHEET_TITLE in wb.sheetnames
    ws = wb[SHEET_TITLE]
    rows = [[c for c in row] for row in ws.iter_rows(min_row=3, values_only=True)]
    assert any(r[1] == "Lubų aukštis" and r[2] == "104" and r[3] == "2,7" and r[4] == "3,1"
               and r[5] == "Prielaidos" for r in rows), rows


def test_client_copy_and_foreign_project_get_no_change_log(env):
    assert SHEET_TITLE not in _sheets(env, vidine_kopija=False, project_id="m5-own").sheetnames
    assert SHEET_TITLE not in _sheets(env, project_id="m5-own").sheetnames
    foreign = _sheets(env, vidine_kopija=True, project_id="m5-other")
    assert SHEET_TITLE in foreign.sheetnames             # the sheet, but nothing of his neighbour's
    texts = [v for row in foreign[SHEET_TITLE].iter_rows(values_only=True) for v in row if v]
    assert not any("201" in str(t) for t in texts)

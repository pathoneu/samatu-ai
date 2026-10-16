"""The correction corpus out of the app (togal-v2 W11, L3): `GET …/corrections.csv` for one project and
`scripts/build_ground_truth.py --with-corrections` for all of them."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import db  # noqa: E402
from tests.test_room_outline_api import _isolate  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_ground_truth", Path(__file__).resolve().parents[2] / "scripts" / "build_ground_truth.py")
bgt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bgt)


def _seed(project_id="p1"):
    db.upsert_project(project_id, {"name": "P", "patalpos": [
        {"nr": "03", "plotas_m2": 10.12, "polygon_source": "corrected", "polygon_pct": [[0, 0], [1, 0], [1, 1]]}]})
    db.log_correction_once(project_id, "eilute.abc.kiekis", 143.2, 150.0, source="eilute_kiekis")
    db.log_correction_once(project_id, "patalpa.03.kontūras", {"plotas_m2": 10.12},
                           {"saltinis": "nubrezta", "plotas_m2": 10.2}, source="konturas", room_nr="03")
    db.log_correction_once(project_id, "pokalbis.x1", None, {"ivertinimas": "ne"}, source="pokalbis_ne",
                           note="=HYPERLINK(\"x\") kiek ploto?")


def test_csv_has_a_bom_the_columns_and_one_line_per_correction(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _seed()
    with TestClient(app) as tc:
        r = tc.get("/api/projects/p1/corrections.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "mokymosi-zurnalas-p1.csv" in r.headers["content-disposition"]
    raw = r.content
    assert raw.startswith("﻿".encode("utf-8"))
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0] == ["laikas", "patalpa", "laukas", "buvo", "tapo", "saltinis", "pastaba"]
    body = rows[1:]
    assert len(body) == 3
    by_source = {row[5]: row for row in body}
    assert by_source["eilute_kiekis"][2:5] == ["eilute.abc.kiekis", "143.2", "150.0"]
    k = by_source["konturas"]
    assert k[1] == "03" and k[2] == "patalpa.03.kontūras"          # Lithuanian letters survive
    assert json.loads(k[4]) == {"plotas_m2": 10.2, "saltinis": "nubrezta"}
    # his text is never a spreadsheet formula
    assert by_source["pokalbis_ne"][6].startswith("'=")


def test_csv_of_an_unknown_project_is_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    with TestClient(app) as tc:
        assert tc.get("/api/projects/nera/corrections.csv").status_code == 404


def test_ground_truth_keeps_its_shape_and_adds_corrections_on_request(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _seed()
    path = tmp_path / "room_outline.db"

    plain = bgt.build_corpus(path)
    assert set(plain) == {"polygon_truth", "quantity_truth", "class_bias", "stats"}
    assert "corrections" not in plain["stats"]

    full = bgt.build_corpus(path, with_corrections=True)
    for key in ("polygon_truth", "quantity_truth", "class_bias"):
        assert full[key] == plain[key]
    assert [c["source"] for c in full["corrections"]] == ["eilute_kiekis", "konturas", "pokalbis_ne"]
    assert full["corrections"][0]["old_value"] == 143.2 and full["corrections"][0]["new_value"] == 150.0
    assert full["corrections"][1]["new_value"]["saltinis"] == "nubrezta"
    assert full["stats"]["corrections"] == 3
    assert full["stats"]["corrections_by_source"] == {"eilute_kiekis": 1, "konturas": 1, "pokalbis_ne": 1}


def test_ground_truth_on_a_database_without_the_table(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE projects (id TEXT, data TEXT)")
    con.commit()
    con.close()
    assert bgt.build_corpus(path, with_corrections=True)["corrections"] == []

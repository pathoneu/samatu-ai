"""build_ground_truth reads human corrections from the project blob (DB)."""
import importlib.util
import json
import sqlite3
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_ground_truth",
    Path(__file__).resolve().parents[2] / "scripts" / "build_ground_truth.py")
bgt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bgt)


def _make_db(tmp_path, projects):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE projects (id TEXT, data TEXT)")
    for pid, blob in projects:
        con.execute("INSERT INTO projects VALUES (?, ?)", (pid, json.dumps(blob)))
    con.commit(); con.close()
    return db


def test_extracts_confirmed_polygons_and_quantities(tmp_path):
    blob = {
        "patalpos": [
            {"nr": "105", "plotas_m2": 10.67, "polygon_source": "corrected",
             "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]},
            {"nr": "106", "plotas_m2": 6.84, "polygon_source": "auto_floodfill",  # AI-proposed, NOT confirmed
             "polygon_pct": [[0.3, 0.3], [0.4, 0.3], [0.4, 0.4]]},
            {"nr": "107", "polygon_source": "manual_needed"},  # no polygon
        ],
        "darbu_sarasas": [
            {"aprasymas": "Silikonavimas tarp plytelių", "quantity_source": "manual_override",
             "ai_kiekis_original": 26.56, "kiekis": 42.0},
            {"aprasymas": "Dažymo kampų montavimas", "user_verified_at": "2026-06-14T10:00:00Z",
             "ai_kiekis_original": 386.0, "kiekis": 386.0},
            {"aprasymas": "AI line not touched", "quantity_source": "ai", "kiekis": 5.0},
        ],
    }
    db = _make_db(tmp_path, [("p1", blob)])
    c = bgt.build_corpus(db)
    # Only the human-confirmed polygon (corrected) counts, not the AI-proposed one.
    assert c["stats"]["polygon_confirmed"] == 1
    assert c["polygon_truth"][0]["room_nr"] == "105"
    # Both the edited and the verified quantity count; the untouched AI row doesn't.
    assert c["stats"]["quantity_confirmed"] == 2
    silik = next(q for q in c["quantity_truth"] if q["quantity_class"] == "silikonavimas")
    assert silik["ai_value"] == 26.56 and silik["human_value"] == 42.0
    assert silik["rel_error"] < 0  # ai under human
    assert "silikonavimas" in c["class_bias"]


def test_empty_db(tmp_path):
    db = _make_db(tmp_path, [])
    c = bgt.build_corpus(db)
    assert c["stats"]["polygon_confirmed"] == 0 and c["stats"]["quantity_confirmed"] == 0

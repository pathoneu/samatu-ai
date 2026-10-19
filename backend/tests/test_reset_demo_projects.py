"""scripts/reset_demo_projects.py (Pathon v3 B2-B item 9): the two demo projects go back to their
walkthrough start state from their own version history; no other project is touched; --dry-run writes
nothing; the reset itself can be undone (the replaced state is kept as a 'grazinta' version)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import db  # noqa: E402

T0 = 1_790_000_000.0
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reset_demo_projects.py"


def _load():
    spec = importlib.util.spec_from_file_location("reset_demo_projects", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path, monkeypatch):
    path = tmp_path / "samatu.db"
    monkeypatch.setattr(db, "_DB_PATH", path)
    db.init_schema()
    db._migrate_schema()
    return path


def _h(merged=False, measurements=0):
    rooms = [{"nr": f"{n:02d}", "pavadinimas": f"Patalpa {n}", "plotas_m2": 10.0} for n in range(1, 12)]
    rooms[3]["plotas_m2"] = 61.81 if merged else 26.31
    if merged:
        rooms[4]["_sujungta_i"] = "04"
    return {"name": "Demo H", "tipas": "interjeras", "patalpos": rooms,
            "v8_totals": {"kampai_m": 495.4 if merged else 475.66, "bendras_plotas_m2": 143.27},
            "measurements": [{"id": f"m{i}"} for i in range(measurements)]}


def test_h_goes_back_to_the_newest_start_state_and_nothing_else_moves(env, capsys):
    mod = _load()
    db.upsert_project("demo-objektas_h", _h(), version_source="perskaityta", now=T0)
    db.upsert_project("other", {"name": "Kitas", "patalpos": [{"nr": "01", "plotas_m2": 5.0}]}, now=T0)
    db.upsert_project("demo-objektas_h", _h(merged=True, measurements=5), now=T0 + 600)
    other_before = db.get_project("other")

    assert mod.main(["--db", str(env), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "merged05 '04' → None" in out
    assert db.get_project("demo-objektas_h")["patalpos"][4].get("_sujungta_i") == "04"   # nothing written

    assert mod.main(["--db", str(env)]) == 0
    now = db.get_project("demo-objektas_h")
    assert now["patalpos"][3]["plotas_m2"] == 26.31 and "_sujungta_i" not in now["patalpos"][4]
    assert now["measurements"] == []
    assert db.get_project("other") == other_before
    kinds = [v["saltinis"] for v in db.list_project_versions("demo-objektas_h")]
    assert kinds[0] == "grazinta"                     # the merged state is kept: the reset can be undone

    assert mod.main(["--db", str(env)]) == 0          # a second run leaves it alone
    assert "already in its start state" in capsys.readouterr().out


def test_g_without_versions_is_left_alone_and_with_one_goes_to_pradine_busena(env, capsys):
    mod = _load()
    g = {"name": "Demo G", "patalpos": [{"nr": "01", "plotas_m2": 10.05}]}
    db.upsert_project("demo-objektas_g", g, now=T0)
    with db._conn() as c:                              # a project saved before versions existed
        c.execute("DELETE FROM project_versions")
    assert mod.main(["--db", str(env), "--only", "demo-objektas_g"]) == 0
    assert "never edited" in capsys.readouterr().out

    db.upsert_project("demo-objektas_g", {**g, "patalpos": [{"nr": "01", "plotas_m2": 99.0}]}, now=T0 + 600)
    assert mod.main(["--db", str(env), "--only", "demo-objektas_g"]) == 0
    assert db.get_project("demo-objektas_g")["patalpos"][0]["plotas_m2"] == 10.05


def test_h_with_no_start_state_version_says_so_and_fails(env, capsys):
    mod = _load()
    db.upsert_project("demo-objektas_h", _h(merged=True), now=T0)
    assert mod.main(["--db", str(env), "--only", "demo-objektas_h"]) == 1
    assert "no stored version is the founder guide's start state" in capsys.readouterr().out

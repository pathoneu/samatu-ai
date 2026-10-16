"""Project versions (togal-v2 W10): written by db.upsert_project, listed, compared,
restored through api/project_versions.py. Clock is injected (`now=`), no model call."""
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

T0 = 1_790_000_000.0          # 2026-09-21, a fixed clock
DAY = 86400.0


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "versions.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    db.init_schema()
    db._migrate_schema()
    return tmp_path


def _blob(kiekis=10.0, **extra):
    return {"name": "P", "tipas": "interjeras",
            "patalpos": [{"nr": "03", "pavadinimas": "Vonia", "plotas_m2": 6.0, "perimetras_m": 10.0}],
            "darbu_sarasas": [{"id": "r1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
                               "kiekis": kiekis, "kaina": 4.0}], **extra}


def _rows(pid="p1"):
    with db._conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, created_at, saltinis, pavadinimas, dydis, length(data) AS z "
            "FROM project_versions WHERE project_id = ? ORDER BY id", (pid,))]


# ── the write in the save path ──────────────────────────────────────────────

def test_first_save_of_a_new_project_is_its_first_version(env):
    db.upsert_project("p1", _blob(), now=T0)
    rows = _rows()
    assert [r["saltinis"] for r in rows] == ["issaugota"]
    assert rows[0]["dydis"] > rows[0]["z"] > 0          # stored compressed


def test_unchanged_save_writes_no_version_even_when_the_stamp_moves(env):
    db.upsert_project("p1", _blob(), now=T0)
    db.upsert_project("p1", {**_blob(), "updated_at": "2026-10-16T10:00:00Z"}, now=T0 + 600)
    db.upsert_project("p1", {**db.get_project("p1")}, now=T0 + 1200)   # what a load+save sends back
    assert len(_rows()) == 1


def test_project_without_versions_keeps_its_stored_state_first(env):
    db.upsert_project("p1", _blob(10), now=T0)
    with db._conn() as c:                  # a project saved before versions existed
        c.execute("DELETE FROM project_versions")
    db.upsert_project("p1", _blob(12), now=T0 + 600)
    rows = _rows()
    assert [(r["saltinis"], r["pavadinimas"]) for r in rows] == [("kita", "Pradinė būsena"),
                                                                 ("issaugota", None)]
    first = db.get_project_version("p1", rows[0]["id"])
    assert first["data"]["darbu_sarasas"][0]["kiekis"] == 10


def test_plain_saves_within_90_s_overwrite_the_last_plain_save(env):
    db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", _blob(11), now=T0 + 600)
    db.upsert_project("p1", _blob(12), now=T0 + 600 + 89)        # inside the burst
    rows = _rows()
    assert len(rows) == 2
    assert db.get_project_version("p1", rows[-1]["id"])["data"]["darbu_sarasas"][0]["kiekis"] == 12
    # the overwritten row moved its clock: 89 s after it is still within the window
    db.upsert_project("p1", _blob(13), now=T0 + 600 + 89 + 91)  # 91 s later: its own row
    assert len(_rows()) == 3


def test_other_sources_and_named_saves_always_get_their_own_row(env):
    db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", _blob(11), now=T0 + 10, version_source="perskaityta")
    db.upsert_project("p1", _blob(12), now=T0 + 20)                       # after a re-read
    db.upsert_project("p1", _blob(13), now=T0 + 30, version_name="Prieš derybas")
    db.upsert_project("p1", _blob(14), now=T0 + 40)                       # after a named one
    assert [r["saltinis"] for r in _rows()] == ["issaugota", "perskaityta", "issaugota",
                                                "issaugota", "issaugota"]


def test_unknown_source_is_stored_as_kita(env):
    db.upsert_project("p1", _blob(10), now=T0, version_source="hack'); DROP TABLE x;--")
    assert _rows()[0]["saltinis"] == "kita"


# ── retention ───────────────────────────────────────────────────────────────

def test_retention_rule_keeps_last_30_and_one_per_day_for_90_days():
    now = T0 + 200 * DAY
    rows = []
    vid = 0
    for d in range(200):                 # three saves a day for 200 days
        for h in (8, 12, 16):
            vid += 1
            t = T0 + d * DAY + h * 3600
            rows.append((vid, db._iso_at(t)))
    keep = db.versions_to_keep(rows, now)
    newest_30 = {v for v, _ in rows[-30:]}
    assert newest_30 <= keep
    daily = keep - newest_30
    days = {dict(rows)[v][:10] for v in daily}
    assert len(days) == len(daily)                          # one per day
    assert all(db._parse_iso(dict(rows)[v]) >= now - 90 * DAY for v in daily)
    # 90 days back from `now`, ten of them already covered by the newest 30
    assert len(keep) == 30 + 80


def test_retention_runs_on_write(env, monkeypatch):
    monkeypatch.setattr(db, "VERSION_KEEP_LAST", 5)
    monkeypatch.setattr(db, "VERSION_DAILY_DAYS", 3)
    for i in range(12):                                   # one save a day, 12 days
        db.upsert_project("p1", _blob(10 + i), now=T0 + i * DAY)
    rows = _rows()
    # newest 5 = days 7–11; the daily rule (3 days back) adds nothing older
    assert [r["created_at"] for r in rows] == [db._iso_at(T0 + i * DAY) for i in range(7, 12)]


def test_daily_rule_keeps_older_days_beyond_the_last_n(env, monkeypatch):
    monkeypatch.setattr(db, "VERSION_KEEP_LAST", 2)
    for i in range(6):                                    # day i: a morning and an evening save
        db.upsert_project("p1", _blob(10 + 2 * i), now=T0 + i * DAY)
        db.upsert_project("p1", _blob(11 + 2 * i), now=T0 + i * DAY + 8 * 3600)
    rows = _rows()
    # last 2 (day 5 morning + evening), plus the evening (newest) of days 0–4
    assert len(rows) == 2 + 5
    assert [r["created_at"][11:13] for r in rows[:5]] == [db._iso_at(T0 + 8 * 3600)[11:13]] * 5


def test_retention_with_defaults_prunes_old_days(env):
    for i in range(40):
        db.upsert_project("p1", _blob(10 + i), now=T0 + i * 7 * DAY)   # weekly for 40 weeks
    rows = _rows()
    # 40 weekly saves: the newest 30 span 29 weeks, every day within 90 days is among them
    assert len(rows) == 30
    assert rows[-1]["created_at"] == db._iso_at(T0 + 39 * 7 * DAY)


# ── restore ─────────────────────────────────────────────────────────────────

def test_restore_keeps_the_replaced_state_and_survives_twice_in_a_row(env):
    db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", _blob(20), now=T0 + 600)
    first = _rows()[0]["id"]
    saved = db.restore_project_version("p1", first, now=T0 + 1200)
    assert saved["darbu_sarasas"][0]["kiekis"] == 10
    rows = _rows()
    assert rows[-1]["saltinis"] == "grazinta"
    assert rows[-1]["pavadinimas"].startswith("Prieš grąžinant versiją nuo ")
    assert db.get_project_version("p1", rows[-1]["id"])["data"]["darbu_sarasas"][0]["kiekis"] == 20

    again = db.restore_project_version("p1", first, now=T0 + 1300)
    assert again["darbu_sarasas"][0]["kiekis"] == 10
    rows = _rows()
    assert [r["saltinis"] for r in rows] == ["issaugota", "issaugota", "grazinta", "grazinta"]
    assert db.get_project_version("p1", rows[-1]["id"])["data"]["darbu_sarasas"][0]["kiekis"] == 10
    # nothing lost: both states are still there
    kiekiai = {db.get_project_version("p1", r["id"])["data"]["darbu_sarasas"][0]["kiekis"] for r in rows}
    assert kiekiai == {10, 20}


def test_restore_moves_updated_at_and_marks_the_current_version(env):
    before = db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", _blob(20), now=T0 + 600)
    first = _rows()[0]["id"]
    after = db.restore_project_version("p1", first, now=T0 + 1200)
    assert after["updated_at"] != before["updated_at"]
    listed = db.list_project_versions("p1")
    assert [v["dabartine"] for v in listed if v["id"] == first] == [True]
    assert sum(v["dabartine"] for v in listed) == 1


def test_restore_of_an_unknown_or_foreign_version_changes_nothing(env):
    a = db.create_user("a@x.lt", "h")["id"]
    b = db.create_user("b@x.lt", "h")["id"]
    db.upsert_project("p1", _blob(10), user_id=a, now=T0)
    db.upsert_project("p2", _blob(99), user_id=b, now=T0)
    foreign = _rows("p2")[0]["id"]
    assert db.restore_project_version("p1", foreign, user_id=a) is None
    assert db.restore_project_version("p1", "nope", user_id=a) is None
    assert db.restore_project_version("p2", foreign, user_id=a) is None
    assert db.list_project_versions("p2", user_id=a) is None
    assert db.get_project_version("p2", foreign, user_id=a) is None
    assert len(_rows("p1")) == 1 and db.get_project("p1")["darbu_sarasas"][0]["kiekis"] == 10


# ── lifetime ────────────────────────────────────────────────────────────────

def test_versions_go_with_the_project_and_survive_archiving(env):
    db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", {**_blob(10), "_archived": True, "_archived_at": "x"}, now=T0 + 600)
    assert len(_rows()) == 2                       # archiving is a save, never a drop
    db.upsert_project("p1", _blob(10), now=T0 + 1200)
    assert len(_rows()) == 3
    assert db.delete_project("p1")
    assert _rows() == []
    with sqlite3.connect(db._DB_PATH) as raw:     # really gone from the file
        assert raw.execute("SELECT COUNT(*) FROM project_versions").fetchone()[0] == 0


# ── routes ──────────────────────────────────────────────────────────────────

def test_put_takes_the_source_and_never_stores_it(env):
    client = TestClient(app)
    r = client.put("/api/projects/p1", json=_blob(10))
    assert r.status_code == 200, r.text
    r = client.put("/api/projects/p1", json={**_blob(15), "_versija_saltinis": "perskaityta"})
    assert r.status_code == 200
    assert "_versija_saltinis" not in r.json()
    assert "_versija_saltinis" not in db.get_project("p1")
    listed = client.get("/api/projects/p1/versions").json()["versions"]
    assert [v["saltinis"] for v in listed] == ["perskaityta", "issaugota"]
    assert listed[0]["dabartine"] is True and "data" not in listed[0]


def test_routes_read_diff_restore(env):
    client = TestClient(app)
    client.put("/api/projects/p1", json=_blob(10))
    client.put("/api/projects/p1", json={**_blob(12.5), "_versija_saltinis": "perskaityta"})
    versions = client.get("/api/projects/p1/versions").json()["versions"]
    old, new = versions[1]["id"], versions[0]["id"]

    got = client.get(f"/api/projects/p1/versions/{old}").json()
    assert got["saltinis"] == "issaugota" and got["data"]["darbu_sarasas"][0]["kiekis"] == 10

    d = client.get(f"/api/projects/p1/versions/{old}/diff/dabartine").json()
    assert d["sakiniai"] == ["Eilutė „Sienų dažymas“: kiekis 10,00 m² → 12,50 m²"]
    assert client.get(f"/api/projects/p1/versions/{old}/diff/{new}").json()["sakiniai"] == d["sakiniai"]

    r = client.post(f"/api/projects/p1/versions/{old}/restore")
    assert r.status_code == 200 and r.json()["darbu_sarasas"][0]["kiekis"] == 10
    versions = client.get("/api/projects/p1/versions").json()["versions"]
    assert versions[0]["saltinis"] == "grazinta"
    held = client.get(f"/api/projects/p1/versions/{versions[0]['id']}").json()
    assert held["data"]["darbu_sarasas"][0]["kiekis"] == 12.5


def test_routes_answer_404_for_missing_project_and_version(env):
    client = TestClient(app)
    client.put("/api/projects/p1", json=_blob(10))
    assert client.get("/api/projects/nope/versions").status_code == 404
    assert client.get("/api/projects/p1/versions/999").status_code == 404
    assert client.get("/api/projects/p1/versions/abc/diff/dabartine").status_code == 404
    assert client.post("/api/projects/p1/versions/999/restore").status_code == 404


def test_restored_project_is_the_version_data_with_the_row_columns_on_top(env):
    """restore_project_version's UPDATE mirrors upsert's column mapping: what get_project serves after a
    restore is exactly the version's blob with the row's columns over it."""
    v1 = {**_blob(10), "name": "Senas", "company_name": "UAB A", "archetipas": "butas",
          "status": "ready", "bendras_plotas_m2": 55.5, "vat_rate": 9}
    db.upsert_project("p1", v1, now=T0)
    db.upsert_project("p1", {**_blob(20), "name": "Naujas", "company_name": None, "vat_rate": 21,
                             "bendras_plotas_m2": 70.0}, now=T0 + 600)
    first = _rows()[0]["id"]
    restored = db.restore_project_version("p1", first, now=T0 + 1200)
    data = db.get_project_version("p1", first)["data"]
    with db._conn() as c:
        row = dict(c.execute("SELECT * FROM projects WHERE id = 'p1'").fetchone())
    row.pop("data")
    assert restored == {**data, **{k: v for k, v in row.items() if v is not None}}
    assert (row["name"], row["company_name"], row["archetipas"], row["bendras_plotas_m2"], row["vat_rate"]) == \
        ("Senas", "UAB A", "butas", 55.5, 9)
    assert row["updated_at"] == db._iso_at(T0 + 1200)
    assert row["created_at"] == db._iso_at(T0)          # creation date is not rewritten


def test_restore_keeps_the_current_archive_state_and_share_link(env):
    db.upsert_project("p1", _blob(10), now=T0)
    db.upsert_project("p1", {**_blob(11), "_archived": True, "_archived_at": "2026-09-21T15:00:00Z"},
                      now=T0 + 600)                                   # saved while archived
    archived_vid = _rows()[-1]["id"]
    db.upsert_project("p1", _blob(12), now=T0 + 1200)               # un-archived again
    db.set_share_token("p1", "tok-1")
    restored = db.restore_project_version("p1", archived_vid, now=T0 + 1800)
    assert "_archived" not in restored and "_archived_at" not in restored
    assert restored["darbu_sarasas"][0]["kiekis"] == 11              # the content is the version's
    assert db.get_share_status("p1") is not None and restored.get("share_token") == "tok-1"

    # and the other way round: archived now, restoring a version saved while active
    db.upsert_project("p1", {**db.get_project("p1"), "_archived": True, "_archived_at": "x"}, now=T0 + 2400)
    active_vid = _rows()[0]["id"]
    again = db.restore_project_version("p1", active_vid, now=T0 + 3000)
    assert again["_archived"] is True and again["_archived_at"] == "x"

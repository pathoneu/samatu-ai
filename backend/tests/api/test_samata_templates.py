"""Sąmatų šablonai — owner-scoped CRUD + a project rendered in HIS layout.

Every sąmata here is INVENTED — made-up sections, made-up families, made-up
numbers. No contractor file, no project identifier.

What these pin, beyond the usual 401/404 surface:
 · a template is reachable only by its owner, and a stranger gets 404 (never
   403, which answers „does this id exist?");
 · the render endpoint writes NOTHING — the sheet is a view of the project;
 · an unverified quantity never lands in one of his cells, through the endpoint
   as well as through the function.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import api.samata_templates as st_mod       # noqa: E402
import auth as _auth                        # noqa: E402
import db as _db                            # noqa: E402
from extractor.samata_template import build_template  # noqa: E402


USER_A = {"id": "tpl-test-user-a", "email": "a@example.test", "is_admin": False}
USER_B = {"id": "tpl-test-user-b", "email": "b@example.test", "is_admin": False}

PROJECT_A = "tpl-test-project-a"


def _samata(slug, rows):
    """rows = [(section, name, unit, qty), …] — invented throughout."""
    return {"slug": slug, "line_items": [
        {"page": 1, "nr": str(i + 1), "section": sec, "name": name,
         "unit": unit, "quantity": qty}
        for i, (sec, name, unit, qty) in enumerate(rows)]}


SAMATA_1 = _samata("sablonas-1", [
    ("Alfa darbai", "Angokraščių apdirbimas GKP", "m", 40.0),
    ("Alfa darbai", "Išgalvotas vienkartinis darbas", "vnt", 1.0),
    ("Omega išlaidos", "Šiukšlių išvežimas", "m3", 6.0),
])
SAMATA_2 = _samata("sablonas-2", [
    ("Alfa darbai", "Angokraščių apdirbimas GKP", "m", 44.0),
    ("Omega išlaidos", "Šiukšlių išvežimas", "m3", 7.0),
])


@pytest.fixture()
def as_user(monkeypatch):
    """Client factory. Identity travels PER REQUEST in a header — a pinned
    module-level patch would silently re-identify an earlier client and let an
    ownership test pass for the wrong reason."""
    app = FastAPI()
    app.include_router(st_mod.router)
    known = {u["id"]: u for u in (USER_A, USER_B)}

    def _resolve(request):
        uid = request.headers.get("x-test-user")
        if uid not in known:
            raise HTTPException(status_code=401, detail="Reikia prisijungti")
        return dict(known[uid])

    def _resolve_owned(request, project_id):
        user = _resolve(request)
        if _db.get_project(project_id, user_id=user["id"]) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return user

    monkeypatch.setattr(_auth, "require_user", _resolve)
    monkeypatch.setattr(_auth, "require_owned_project", _resolve_owned)

    def _make(user: dict) -> TestClient:
        return TestClient(app, headers={"x-test-user": user["id"]})

    return _make


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    # Its own throwaway database: until 2026-10-05 these users, projects and
    # templates — and the cleanup below — ran against backend/data/samatu.db.
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "samata_templates.db")
    _db.init_schema()
    _db._migrate_schema()
    # `projects.user_id` carries a FOREIGN KEY, so the two identities have to
    # exist as rows before a project can be owned by one.
    with _db._conn() as c:
        for u in (USER_A, USER_B):
            c.execute(
                "INSERT OR IGNORE INTO users (id, email, password_hash, name, "
                "is_admin, is_active, created_at) VALUES (?, ?, '!test', ?, 0, 1, ?)",
                (u["id"], u["email"], u["id"], _db._now_iso()))
    yield
    with _db._conn() as c:
        c.execute("DELETE FROM samata_templates WHERE user_id IN (?, ?)",
                  (USER_A["id"], USER_B["id"]))
        c.execute("DELETE FROM projects WHERE id = ?", (PROJECT_A,))
        c.execute("DELETE FROM users WHERE id IN (?, ?)",
                  (USER_A["id"], USER_B["id"]))


def _save_project(rows, rooms=None, user=USER_A):
    _db.upsert_project(PROJECT_A, {
        "id": PROJECT_A, "name": "Bandomasis",
        "darbu_sarasas": rows,
        "patalpos": rooms if rooms is not None else [{"nr": "1"}],
    }, user_id=user["id"])


# ── auth surface ─────────────────────────────────────────────────────────────

def test_every_route_needs_a_session():
    app = FastAPI()
    app.include_router(st_mod.router)
    with pytest.MonkeyPatch.context() as mp:
        def _reject(request, *a, **kw):
            raise HTTPException(status_code=401, detail="Reikia prisijungti")
        mp.setattr(_auth, "require_user", _reject)
        mp.setattr(_auth, "require_owned_project", _reject)
        client = TestClient(app)
        assert client.get("/api/samata-templates").status_code == 401
        assert client.post("/api/samata-templates", json={}).status_code == 401
        assert client.delete(
            f"/api/samata-templates/{uuid.uuid4()}").status_code == 401
        assert client.post(
            f"/api/projects/{PROJECT_A}/samata-render").status_code == 401


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_derive_a_template_from_one_samata_and_read_it_back(as_user):
    client = as_user(USER_A)
    r = client.post("/api/samata-templates",
                    json={"samatas": [SAMATA_1], "name": "Mano šablonas"})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["name"] == "Mano šablonas"
    assert saved["sources"] == ["sablonas-1"]
    assert [s["label"] for s in saved["sections"]] == ["Alfa darbai",
                                                       "Omega išlaidos"]
    listed = client.get("/api/samata-templates").json()["samata_templates"]
    assert [t["id"] for t in listed] == [saved["id"]]
    assert listed[0]["total_families"] == 3


def test_merging_a_second_samata_promotes_the_shared_families(as_user):
    client = as_user(USER_A)
    first = client.post("/api/samata-templates",
                        json={"samatas": [SAMATA_1]}).json()
    merged = client.post("/api/samata-templates",
                         json={"id": first["id"], "samatas": [SAMATA_2]}).json()
    assert merged["id"] == first["id"]
    assert merged["sources"] == ["sablonas-1", "sablonas-2"]
    fams = {f["label"]: f for s in merged["sections"] for f in s["families"]}
    assert fams["Angokraščių apdirbimas GKP"]["daznumas"] == "įprasta"
    assert fams["Išgalvotas vienkartinis darbas"]["daznumas"] == "kartais"
    # …and it is idempotent on the sąmata's own name.
    again = client.post("/api/samata-templates",
                        json={"id": first["id"], "samatas": [SAMATA_2]}).json()
    assert again["sources"] == merged["sources"]
    assert again["sections"] == merged["sections"]


def test_a_stranger_can_neither_read_nor_overwrite_nor_delete(as_user):
    a, b = as_user(USER_A), as_user(USER_B)
    mine = a.post("/api/samata-templates", json={"samatas": [SAMATA_1]}).json()
    assert b.get("/api/samata-templates").json()["samata_templates"] == []
    # 404, not 403 — never confirm that someone else's id exists.
    assert b.post("/api/samata-templates",
                  json={"id": mine["id"], "sections": []}).status_code == 404
    assert b.delete(f"/api/samata-templates/{mine['id']}").status_code == 404
    assert len(a.get("/api/samata-templates").json()["samata_templates"]) == 1


def test_delete_removes_only_the_callers_own(as_user):
    client = as_user(USER_A)
    mine = client.post("/api/samata-templates", json={"samatas": [SAMATA_1]}).json()
    assert client.delete(f"/api/samata-templates/{mine['id']}").status_code == 200
    assert client.get("/api/samata-templates").json()["samata_templates"] == []
    assert client.delete(f"/api/samata-templates/{mine['id']}").status_code == 404


def test_a_shapeless_body_is_a_400_not_a_500(as_user):
    client = as_user(USER_A)
    assert client.post("/api/samata-templates", json={}).status_code == 400
    assert client.post("/api/samata-templates",
                       json={"sections": "nope"}).status_code == 400
    assert client.post("/api/samata-templates",
                       json={"samatas": []}).status_code == 400
    assert client.post("/api/samata-templates",
                       json={"samatas": ["not a dict"]}).status_code == 400
    assert client.post("/api/samata-templates",
                       json={"id": "not-a-uuid", "sections": []}).status_code == 400


# ── Rendering ────────────────────────────────────────────────────────────────

def test_render_returns_his_sections_and_leaves_unverified_cells_blank(as_user):
    client = as_user(USER_A)
    tpl = client.post("/api/samata-templates",
                      json={"samatas": [SAMATA_1, SAMATA_2],
                            "is_default": True}).json()
    _save_project([
        # 2026-09-05: his „Angokraščių apdirbimas GKP" is its own family now
        # (= our GKP struktūra row); the glaistymas/dažymas row is another.
        {"id": "r1", "aprasymas": "Angokraščių apdirbimas GKP (struktūra)", "mato_vnt": "m",
         "kiekis": 38.0},
        {"id": "r2", "aprasymas": "Šiukšlių išvežimas", "mato_vnt": "m3",
         "kiekis": 5.0, "roll_up": [{"op": "sum", "label": "Σ", "value": 5.0}]},
        {"id": "r3", "aprasymas": "Mūsų pačių sugalvota eilutė", "mato_vnt": "vnt",
         "kiekis": 2.0},
    ])
    out = client.post(f"/api/projects/{PROJECT_A}/samata-render"
                      f"?template_id={tpl['id']}").json()
    rows = {r["aprasymas"]: r for r in out["eilutes"]}

    ango = rows["Angokraščių apdirbimas GKP"]
    assert ango["skyrius"] == "Alfa darbai"
    assert ango["kiekis"] is None                      # unverified → BLANK
    assert ango["_siulomas_kiekis"] == 38.0            # …offered, greyed
    assert ango["_pastaba"] == "Patikrinkite prieš naudodami"

    siuk = rows["Šiukšlių išvežimas"]
    assert siuk["kiekis"] == 5.0                       # ledgered → filled
    assert siuk["_pastaba"] is None

    blank = rows["Išgalvotas vienkartinis darbas"]
    assert blank["kiekis"] is None
    assert blank["_pastaba"] == "Iš brėžinio nenustatyta — įrašykite"

    # Nothing we computed is lost.
    ours = rows["Mūsų pačių sugalvota eilutė"]
    assert ours["skyrius"] == "Kita (iš brėžinio)"
    assert out["santrauka"]["uzpildyta"] == 1
    assert out["santrauka"]["pasiulyta"] == 1
    assert out["santrauka"]["kitos_eilutes"] == 1


def test_render_writes_nothing(as_user):
    """The sheet is a VIEW of the project. Persisting it would go stale against
    the next recompute and give two answers to „kiek?"."""
    client = as_user(USER_A)
    client.post("/api/samata-templates",
                json={"samatas": [SAMATA_1], "is_default": True})
    _save_project([{"id": "r1", "aprasymas": "Šiukšlių išvežimas",
                    "mato_vnt": "m3", "kiekis": 5.0}])
    before = json.dumps(_db.get_project(PROJECT_A, user_id=USER_A["id"]),
                        sort_keys=True, default=str)
    assert client.post(f"/api/projects/{PROJECT_A}/samata-render").status_code == 200
    after = json.dumps(_db.get_project(PROJECT_A, user_id=USER_A["id"]),
                       sort_keys=True, default=str)
    assert before == after


def test_render_takes_the_rows_the_client_is_holding_and_still_writes_nothing(as_user):
    """The frontend cache is write-through: the saved blob lags the screen by a
    round trip. Rendering the rows in the request shows his typed number NOW,
    and the store is untouched."""
    client = as_user(USER_A)
    client.post("/api/samata-templates",
                json={"samatas": [SAMATA_1], "is_default": True})
    _save_project([{"id": "r1", "aprasymas": "Šiukšlių išvežimas",
                    "mato_vnt": "m3", "kiekis": 5.0}])
    before = json.dumps(_db.get_project(PROJECT_A, user_id=USER_A["id"]),
                        sort_keys=True, default=str)
    typed = {"id": "rnk-1", "aprasymas": "Išgalvotas vienkartinis darbas",
             "mato_vnt": "vnt", "kiekis": 2.0, "manual_override": True,
             "_sablono_eile": None}
    # Name the family the way the frontend does: from a previous render.
    first = client.post(f"/api/projects/{PROJECT_A}/samata-render").json()
    fam = next(r for r in first["eilutes"]
               if r["aprasymas"] == "Išgalvotas vienkartinis darbas")
    typed["_sablono_eile"] = fam["_sablono_eile"]

    out = client.post(f"/api/projects/{PROJECT_A}/samata-render",
                      json={"darbu_sarasas": [typed], "patalpos": []}).json()
    rows = {r["aprasymas"]: r for r in out["eilutes"]}
    assert rows["Išgalvotas vienkartinis darbas"]["kiekis"] == 2.0
    assert rows["Išgalvotas vienkartinis darbas"]["_saltinio_id"] == ["rnk-1"]
    # The saved r1 is NOT in this render — the body replaced the rows…
    assert rows["Šiukšlių išvežimas"]["kiekis"] is None
    # …and the blank note says no rooms were sent.
    assert rows["Šiukšlių išvežimas"]["_pastaba"] == "Brėžinyje patalpų nerasta — įrašykite"
    after = json.dumps(_db.get_project(PROJECT_A, user_id=USER_A["id"]),
                       sort_keys=True, default=str)
    assert before == after


def test_render_body_shape_is_checked(as_user):
    client = as_user(USER_A)
    client.post("/api/samata-templates",
                json={"samatas": [SAMATA_1], "is_default": True})
    _save_project([])
    assert client.post(f"/api/projects/{PROJECT_A}/samata-render",
                       json={"darbu_sarasas": "ne sąrašas"}).status_code == 400
    assert client.post(f"/api/projects/{PROJECT_A}/samata-render",
                       json=[1, 2, 3]).status_code == 400
    # An empty body is still the saved-blob render.
    assert client.post(f"/api/projects/{PROJECT_A}/samata-render").status_code == 200


def test_render_falls_back_to_the_only_template_when_none_is_named(as_user):
    client = as_user(USER_A)
    client.post("/api/samata-templates", json={"samatas": [SAMATA_1]})
    _save_project([])
    assert client.post(f"/api/projects/{PROJECT_A}/samata-render").status_code == 200


def test_render_without_a_template_is_a_404_that_says_what_to_do(as_user):
    client = as_user(USER_A)
    _save_project([])
    r = client.post(f"/api/projects/{PROJECT_A}/samata-render")
    assert r.status_code == 404
    assert "šablon" in r.json()["detail"].lower()


def test_render_cannot_reach_someone_elses_project(as_user):
    a, b = as_user(USER_A), as_user(USER_B)
    b.post("/api/samata-templates", json={"samatas": [SAMATA_1]})
    _save_project([], user=USER_A)
    assert b.post(f"/api/projects/{PROJECT_A}/samata-render").status_code == 404
    # …and a template id from another account is 404 too, not a silent default.
    mine = a.post("/api/samata-templates", json={"samatas": [SAMATA_2]}).json()
    assert b.post(f"/api/projects/{PROJECT_A}/samata-render"
                  f"?template_id={mine['id']}").status_code == 404


def test_optional_families_can_be_dropped_from_the_render(as_user):
    client = as_user(USER_A)
    client.post("/api/samata-templates",
                json={"samatas": [SAMATA_1, SAMATA_2], "is_default": True})
    _save_project([])
    full = client.post(f"/api/projects/{PROJECT_A}/samata-render").json()
    lean = client.post(f"/api/projects/{PROJECT_A}"
                       f"/samata-render?include_optional=0").json()
    labels = {r["aprasymas"] for r in lean["eilutes"]}
    assert "Išgalvotas vienkartinis darbas" not in labels      # 1 of 2 → kartais
    assert len(lean["eilutes"]) < len(full["eilutes"])


# ── Storage ──────────────────────────────────────────────────────────────────

def test_a_corrupt_sections_blob_does_not_read_as_an_empty_template():
    """An empty template renders every sąmata as OUR row list under OUR labels —
    the exact failure this week's work exists to prevent."""
    tid = str(uuid.uuid4())
    _db.upsert_samata_template(tid, build_template([SAMATA_1]), USER_A["id"])
    with _db._conn() as c:
        c.execute("UPDATE samata_templates SET sections = ? WHERE id = ?",
                  ("{not json", tid))
    got = _db.get_samata_template(tid, USER_A["id"])
    assert got["sections"] == []
    assert got["_sections_corrupt"] is True


def test_the_owner_is_required_and_an_empty_one_does_not_widen_the_query():
    with pytest.raises(ValueError):
        _db.list_samata_templates("")
    with pytest.raises(ValueError):
        _db.get_samata_template("x", "")
    with pytest.raises(ValueError):
        _db.upsert_samata_template("x", {}, "")
    with pytest.raises(ValueError):
        _db.delete_samata_template("x", "")


def test_is_default_is_exclusive_per_user():
    a = str(uuid.uuid4())
    b = str(uuid.uuid4())
    _db.upsert_samata_template(a, {**build_template([SAMATA_1]),
                                   "is_default": True}, USER_A["id"])
    _db.upsert_samata_template(b, {**build_template([SAMATA_2]),
                                   "is_default": True}, USER_A["id"])
    defaults = [t["id"] for t in _db.list_samata_templates(USER_A["id"])
                if t["is_default"]]
    assert defaults == [b]
    assert _db.get_default_samata_template(USER_A["id"])["id"] == b
    with _db._conn() as c:
        c.execute("DELETE FROM samata_templates WHERE id IN (?, ?)", (a, b))

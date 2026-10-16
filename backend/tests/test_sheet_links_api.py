"""`GET /api/projects/{id}/pages/{page}/callouts` — references on one sheet to other sheets of the same
PDF (api/sheet_links.py). Read-only, owner-scoped, saves nothing, calls no model."""
from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
import api.sheet_links as sheet_links  # noqa: E402

_FONT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf"
pdfmetrics.registerFont(TTFont("DejaVuTest", str(_FONT)))
W, H = A4


def _pdf(pages: list[list[tuple[str, float, float]]]) -> bytes:
    """One page per list; each item (text, x_pct, y_pct-from-top)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for items in pages:
        c.setFont("DejaVuTest", 9)
        for text, x, y in items:
            c.drawString(x * W, H - y * H, text)
        c.showPage()
    c.save()
    return buf.getvalue()


PAGES = [
    [("Plytelių išdėstymą žiūrėti iškl.", 0.10, 0.20), ("Šviestuvai — žr. lapą 3", 0.10, 0.30)],
    [("Vonios išklotinės", 0.10, 0.10), ("B.02", 0.90, 0.97)],
    [("Lubų planas", 0.10, 0.10), ("B.03", 0.90, 0.97)],
    [],                                              # a sheet with no text layer (a scan)
]
PUSLAPIAI = [
    {"nr": 1, "tipas": "floor_plan", "pavadinimas": "Baldų planas"},
    {"nr": 2, "tipas": "wall_elevation", "pavadinimas": "Vonios išklotinės"},
    {"nr": 3, "tipas": "ceiling_plan", "pavadinimas": "Lubų planas"},
    {"nr": 4, "tipas": "unknown", "pavadinimas": "Vizualizacija"},
]


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "sheet_links.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    sheet_links._cache.clear()


def _store(project_id="p1", *, user_id=None, pdf=True, overrides=None):
    blob = {"name": "P", "tipas": "interjeras", "patalpos": [], "puslapiai": PUSLAPIAI, "_meta": {"model": "x"}}
    if overrides is not None:
        blob["sheet_overrides"] = overrides
    db.upsert_project(project_id, blob, user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _pdf(PAGES))


def test_callouts_on_a_plan_point_at_the_elevation_and_the_numbered_page(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/1/callouts")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["page"] == 1 and out["page_count"] == 4
    by_text = {c["text"]: c for c in out["callouts"]}
    assert set(by_text) == {"žiūrėti iškl.", "žr. lapą 3"}
    iskl = by_text["žiūrėti iškl."]
    assert iskl["target_page"] == 2 and iskl["target_name"] == "Vonios išklotinės"
    assert iskl["confidence"] == "medium" and iskl["kind"] == "tipas" and iskl["other_pages"] == []
    lapas = by_text["žr. lapą 3"]
    assert lapas["target_page"] == 3 and lapas["kind"] == "nuoroda"
    # the box sits where the words were drawn, in top-origin page fractions
    x0, y0, x1, y1 = iskl["bbox_pct"]
    assert 0.10 < x0 < x1 < 0.6 and 0.18 < y0 < y1 < 0.21


def test_a_sheet_never_links_itself_and_a_scan_has_none(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    client = TestClient(app)
    assert client.get("/api/projects/p1/pages/2/callouts").json()["callouts"] == []
    assert client.get("/api/projects/p1/pages/4/callouts").json()["callouts"] == []


def test_the_users_sheet_name_is_what_the_hover_names(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(overrides={"2": {"name": "Vonia — sienos"}})
    out = TestClient(app).get("/api/projects/p1/pages/1/callouts").json()
    iskl = next(c for c in out["callouts"] if c["kind"] == "tipas")
    assert iskl["target_name"] == "Vonia — sienos"


def test_the_users_sheet_type_moves_the_target(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(overrides={"2": {"type": "section"}, "4": {"type": "wall_elevation", "name": "Išklotinės"}})
    out = TestClient(app).get("/api/projects/p1/pages/1/callouts").json()
    iskl = next(c for c in out["callouts"] if c["kind"] == "tipas")
    assert iskl["target_page"] == 4


def test_the_pdf_text_is_read_once_per_pdf(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    calls = []
    real = sheet_links.read_text_pages
    monkeypatch.setattr(sheet_links, "read_text_pages", lambda b: calls.append(1) or real(b))
    client = TestClient(app)
    for page in (1, 2, 3):
        assert client.get(f"/api/projects/p1/pages/{page}/callouts").status_code == 200
    assert len(calls) == 1


def test_bad_pages_and_missing_pdf(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    _store("p2", pdf=False)
    client = TestClient(app)
    assert client.get("/api/projects/p1/pages/0/callouts").status_code == 400
    assert client.get("/api/projects/p1/pages/9/callouts").status_code == 400
    r = client.get("/api/projects/p2/pages/1/callouts")
    assert r.status_code == 404
    assert client.get("/api/projects/nope/pages/1/callouts").status_code == 404


def test_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = db.get_project("p1")
    TestClient(app).get("/api/projects/p1/pages/1/callouts")
    assert db.get_project("p1") == before


def test_another_users_project_is_a_404_before_anything_is_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("savininkas@example.com", auth.hash_password("passw0rd123"))
    _store(user_id=owner["id"] if isinstance(owner, dict) else owner)
    read = []
    monkeypatch.setattr(sheet_links, "read_text_pages", lambda b: read.append(1) or {"page_count": 0, "pages": {}})
    r = TestClient(app).get("/api/projects/p1/pages/1/callouts")
    assert r.status_code == 401
    assert read == []


def test_the_rate_limit_guards_the_parse_not_the_cached_answer(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    import main
    monkeypatch.setattr(main, "_RATE_LIMIT_PER_MIN", 2)
    client = TestClient(app)
    codes = [client.get(f"/api/projects/p1/pages/{1 + i % 4}/callouts").status_code for i in range(12)]
    assert codes == [200] * 12
    sheet_links._cache.clear()
    _store("p2")
    _store("p3")
    assert client.get("/api/projects/p2/pages/1/callouts").status_code == 200   # 2nd parse this minute
    assert client.get("/api/projects/p3/pages/1/callouts").status_code == 429   # 3rd

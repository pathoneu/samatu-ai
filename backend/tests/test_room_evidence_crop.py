"""GET /api/projects/{id}/evidence — the crop behind a fact.

The room check sheet is only worth building if the picture under each number is
the RIGHT picture. So these tests pin the two things that can silently go
wrong — the coordinate frame and who is allowed to ask — plus the boring
infrastructure (cache, 404s, rate limit) that keeps a six-crops-per-room screen
from re-rendering poppler every time.

The coordinate test is the important one. `eksplikacija_row_bbox` is a
pdfplumber bbox: PDF points measured from the page TOP. pdf2image rasterises
from the top too, so the conversion is a plain division — and a y-flip
"correction" would put the row at the mirrored end of the sheet. That is
exactly what the 2026-05 browser-side highlight did, and why this crop is made
server-side at all.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

# main BEFORE auth — see test_export_auth.py: main.py's load_dotenv() must run
# before auth.py freezes its module-level AUTH_DISABLED.
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api import evidence as ev  # noqa: E402

from synthetic_plan_pdf import plan_pdf  # noqa: E402

# A synthetic A3 drawing built in memory, always available. (It used to be a
# tracked sample client drawing that carried an identifier; audit 2026-09-29.)
SAMPLE_PDF = plan_pdf()

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "evidence.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    monkeypatch.setattr(ev, "CACHE_ROOT", tmp_path / "crops")
    ev._reset_render_caches_for_test()
    db.init_schema()
    db._migrate_schema()


def _project(project_id="p1", *, user_id=None, rooms=None):
    db.upsert_project(project_id,
                      {"name": "P", "tipas": "interjeras",
                       "patalpos": rooms or []},
                      user_id=user_id)


def _store_pdf(project_id="p1", path: pathlib.Path | None = None):
    storage.get_storage().put(storage.pdf_key(project_id),
                              path.read_bytes() if path else SAMPLE_PDF)


# ── the coordinate frame ────────────────────────────────────────────────────

def test_a_pdfplumber_row_bbox_maps_straight_onto_the_raster():
    """[x0, top, x1, bottom] / page dims — no y-flip, no swap.

    A row two thirds down an A3 sheet must land two thirds down the image.
    """
    from extractor.room_facts import _bbox_pdf_to_pct
    # 842 x 1191 pt A3 portrait; a table row near the bottom.
    rect = _bbox_pdf_to_pct([84.2, 794.0, 757.8, 806.0], 842.0, 1191.0)
    assert rect == [0.1, 0.6667, 0.9, 0.6767]
    # The y values stay in the lower two thirds — a flip would send them to 0.33.
    assert rect[1] > 0.5 and rect[3] > 0.5


def test_a_missing_page_size_yields_no_rectangle():
    """Rather than dividing by a guess: no dims, no claim about where."""
    from extractor.room_facts import _bbox_pdf_to_pct
    assert _bbox_pdf_to_pct([1, 2, 3, 4], None, 1191.0) is None
    assert _bbox_pdf_to_pct([1, 2, 3, 4], 842.0, 0) is None
    assert _bbox_pdf_to_pct("nonsense", 842.0, 1191.0) is None


def test_padding_grows_a_thin_row_to_something_legible():
    """A table row is ~1 % of the page tall. Cropped literally it is a sliver;
    the floor makes it a place you can recognise."""
    x0, y0, x1, y1 = ev._padded([0.10, 0.6667, 0.90, 0.6768])
    assert (y1 - y0) >= ev.MIN_CROP_H_PCT - 1e-9
    # …and it stays centred on the row it was asked about.
    assert y0 < 0.6667 < y1


def test_padding_slides_a_crop_back_onto_the_sheet():
    """A rect in the corner must not be padded off the page."""
    x0, y0, x1, y1 = ev._padded([0.0, 0.0, 0.01, 0.01])
    assert x0 >= 0 and y0 >= 0 and x1 <= 1 and y1 <= 1
    assert (x1 - x0) >= ev.MIN_CROP_W_PCT - 1e-9


def test_rect_parsing_normalises_a_reversed_or_degenerate_box():
    assert ev.parse_rect("0.9,0.8,0.1,0.2") == [0.1, 0.2, 0.9, 0.8]
    assert ev.parse_rect("0.5,0.5,0.5,0.5") == [0.5, 0.5, 0.5, 0.5]


@pytest.mark.parametrize("raw", ["", "1,2", "a,b,c,d", "0,0,2,1", "0,0,nan,1"])
def test_rect_parsing_rejects_junk(raw):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        ev.parse_rect(raw)
    assert exc.value.status_code == 400


def test_the_dpi_cap_scales_down_for_a_huge_sheet():
    """An A0 sheet at 160 dpi is ~90 Mpx. The cap is on pixels, not on dpi."""
    assert ev.safe_dpi(110, 842, 1191) == 110          # A3 — untouched
    assert ev.safe_dpi(999, 842, 1191) == ev.MAX_DPI   # clamped to the max
    a0 = ev.safe_dpi(160, 2384, 3370)                  # A0
    assert a0 < 160 and a0 * 3370 / 72 <= ev.MAX_PAGE_PX + 1


def test_the_crop_lands_where_the_percentages_say_on_a_real_page():
    """The end-to-end frame check, against poppler's own raster.

    A rectangle in the TOP tenth of the page must produce the top tenth of the
    rendered image — not the bottom tenth. This is the assertion that would
    have caught a y-flip, and it is made against an independently rendered
    full page, not against the crop code's own arithmetic. Since 2026-09-20 a
    region is rendered on its own through PDFium (sharper, another rasteriser),
    so the two pictures are compared as pictures — shrunk to one size, mean
    difference — not byte for byte.
    """
    import io

    from PIL import Image, ImageChops, ImageStat
    from pdf2image import convert_from_bytes

    data = SAMPLE_PDF
    dpi = 60  # low: this test is about geometry, not legibility
    full = convert_from_bytes(data, dpi=dpi, fmt="png",
                              first_page=2, last_page=2)[0]
    W, H = full.size

    def expected_for(rect):
        x0, y0, x1, y1 = ev._padded(rect)
        return full.crop((int(W * x0), int(H * y0),
                          max(int(W * x1), int(W * x0) + 1),
                          max(int(H * y1), int(H * y0) + 1))).convert("L")

    def difference(got_png, want):
        got = Image.open(io.BytesIO(got_png)).convert("L")
        ratio = (got.width / got.height) / (want.width / want.height)
        assert 0.98 < ratio < 1.02                                  # the same shape of place
        small = (160, max(8, round(160 * want.height / want.width)))
        return ImageStat.Stat(ImageChops.difference(got.resize(small), want.resize(small))).mean[0]

    top, bottom = [0.0, 0.0, 1.0, 0.10], [0.0, 0.90, 1.0, 1.0]
    got_top = ev.render_crop(data, 2, top, dpi)
    assert difference(got_top, expected_for(top)) < 12
    # …and the bottom strip is a different picture, so the test is not vacuous.
    assert difference(got_top, expected_for(bottom)) > 2 * difference(got_top, expected_for(top))
    assert difference(ev.render_crop(data, 2, bottom, dpi), expected_for(bottom)) < 12


# ── the endpoint ────────────────────────────────────────────────────────────

def test_a_rect_becomes_a_png_of_that_region(tmp_path, monkeypatch):
    from PIL import Image
    import io

    _isolate(tmp_path, monkeypatch)
    _project()
    _store_pdf()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence",
              params={"page": 2, "rect": "0.1,0.6,0.9,0.62", "dpi": 110})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(r.content))
    # A3 at 110 dpi is ~1286 px wide; 80 % of it, plus padding.
    assert 900 < img.width <= ev.MAX_CROP_PX
    assert img.height > 40


def test_the_second_request_is_served_from_disk(tmp_path, monkeypatch):
    """Six crops per room, one room per click — a re-render per view would make
    the check sheet unusable. The cache is keyed on the whole request."""
    _isolate(tmp_path, monkeypatch)
    _project()
    _store_pdf()
    c = TestClient(app)
    params = {"page": 2, "rect": "0.1,0.6,0.9,0.62", "dpi": 110}
    first = c.get("/api/projects/p1/evidence", params=params)
    assert first.status_code == 200

    def _boom(*a, **k):  # pragma: no cover — the point is that it never runs
        raise AssertionError("re-rendered a cached crop")

    monkeypatch.setattr(ev, "render_crop", _boom)
    second = c.get("/api/projects/p1/evidence", params=params)
    assert second.status_code == 200
    assert second.content == first.content


def test_an_etag_answers_304_without_touching_the_pdf(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _project()
    _store_pdf()
    c = TestClient(app)
    params = {"page": 2, "rect": "0.1,0.6,0.9,0.62", "dpi": 110}
    first = c.get("/api/projects/p1/evidence", params=params)
    etag = first.headers["etag"]
    again = c.get("/api/projects/p1/evidence", params=params,
                  headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["cache-control"].startswith("private")


def test_the_room_shorthand_crops_the_rooms_own_region(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _project(rooms=[{"nr": "101", "pavadinimas": "Svetainė", "puslapio_nr": 2,
                     "polygon_pct": [[0.2, 0.3], [0.5, 0.3], [0.5, 0.6],
                                     [0.2, 0.6]]}])
    _store_pdf()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence", params={"room": "101"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # The same region asked for explicitly must hit the same cache entry.
    explicit = c.get("/api/projects/p1/evidence",
                     params={"page": 2, "rect": "0.2,0.3,0.5,0.6"})
    assert explicit.content == r.content


def test_a_room_with_no_geometry_is_a_404_not_a_blank_image(tmp_path, monkeypatch):
    """„We cannot point at this" and „here it is" must not look the same."""
    _isolate(tmp_path, monkeypatch)
    _project(rooms=[{"nr": "101", "pavadinimas": "Svetainė", "puslapio_nr": 2}])
    _store_pdf()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence", params={"room": "101"})
    assert r.status_code == 404


def test_an_unknown_room_is_a_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _project(rooms=[{"nr": "101", "puslapio_nr": 1}])
    c = TestClient(app)
    assert c.get("/api/projects/p1/evidence",
                 params={"room": "999"}).status_code == 404


def test_a_project_with_no_stored_pdf_says_so(tmp_path, monkeypatch):
    """Projects extracted before durable PDF storage have rooms but no bytes.
    That is a specific 404, not a broken image."""
    _isolate(tmp_path, monkeypatch)
    _project()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence",
              params={"page": 1, "rect": "0.1,0.1,0.2,0.2"})
    assert r.status_code == 404
    assert "Brėžinys" in r.text


def test_a_page_past_the_end_is_a_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _project()
    _store_pdf()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence",
              params={"page": 999, "rect": "0.1,0.1,0.2,0.2"})
    assert r.status_code == 404


def test_missing_page_or_rect_is_a_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _project()
    c = TestClient(app)
    assert c.get("/api/projects/p1/evidence",
                 params={"page": 1}).status_code == 400
    assert c.get("/api/projects/p1/evidence").status_code == 400


def test_a_traversal_project_id_is_rejected(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    r = c.get("/api/projects/..%2F..%2Fetc/evidence",
              params={"page": 1, "rect": "0,0,1,1"})
    assert r.status_code in (400, 404)


# ── who may ask ─────────────────────────────────────────────────────────────

def test_anonymous_callers_get_401(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    _project()
    c = TestClient(app)
    r = c.get("/api/projects/p1/evidence",
              params={"page": 1, "rect": "0,0,1,1"})
    assert r.status_code == 401


def test_a_stranger_cannot_read_someone_elses_drawing(tmp_path, monkeypatch):
    """404, not 403 — the same shape as every other project route, so the
    endpoint never confirms that a project id exists."""
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    _project(user_id=owner["id"])
    _store_pdf()
    c = TestClient(app)
    assert c.post("/api/auth/login",
                  json={"email": "thief@x.lt",
                        "password": _PW}).status_code == 200
    r = c.get("/api/projects/p1/evidence",
              params={"page": 1, "rect": "0,0,1,1"})
    assert r.status_code == 404


def test_the_owner_gets_through(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    _project(user_id=owner["id"])
    c = TestClient(app)
    assert c.post("/api/auth/login",
                  json={"email": "owner@x.lt",
                        "password": _PW}).status_code == 200
    r = c.get("/api/projects/p1/evidence",
              params={"page": 1, "rect": "0,0,1,1"})
    # No PDF stored → 404 on the BYTES, which proves the auth gate let it past.
    assert r.status_code == 404
    assert "Brėžinys" in r.text


def test_the_crop_endpoint_is_rate_limited(tmp_path, monkeypatch):
    """A render is ~0,4 s of poppler; one account must not be able to loop it."""
    import main
    _isolate(tmp_path, monkeypatch)
    _project()
    main._RATE_BUCKET.clear()
    c = TestClient(app)
    codes = [c.get("/api/projects/p1/evidence",
                   params={"page": 1, "rect": "0,0,1,1"}).status_code
             for _ in range(main._RATE_LIMIT_PER_MIN + 2)]
    assert 429 in codes
    main._RATE_BUCKET.clear()


# ── the URL the check sheet embeds ──────────────────────────────────────────

def test_evidence_url_round_trips_through_the_parser():
    url = ev.evidence_url("p1", 2, [0.1, 0.6, 0.9, 0.62], 110)
    assert url.startswith("/api/projects/p1/evidence?page=2&rect=")
    raw = url.split("rect=", 1)[1].split("&", 1)[0]
    assert ev.parse_rect(raw) == [0.1, 0.6, 0.9, 0.62]


def test_evidence_url_is_none_when_there_is_nothing_to_point_at():
    assert ev.evidence_url("p1", None, [0, 0, 1, 1]) is None
    assert ev.evidence_url("p1", 2, None) is None


def test_a_rooms_burst_of_crops_fetches_the_pdf_once(tmp_path, monkeypatch):
    """Six facts on one sheet = one PDF fetch, not six (2026-09-15 review).
    Since 2026-09-20 a PLACE is rendered on its own through PDFium, so the
    whole sheet is not rasterised at all for it; the whole-sheet request (what
    the enlarge dialog opens with) still rasterises the page once and shares
    it."""
    _isolate(tmp_path, monkeypatch)
    _project()
    _store_pdf()
    calls = {"render": 0, "load": 0}
    real_render, real_load = ev._render_page, ev._load_pdf_uncached

    def counting_render(pdf_bytes, page, dpi):
        calls["render"] += 1
        return real_render(pdf_bytes, page, dpi)

    def counting_load(project_id):
        calls["load"] += 1
        return real_load(project_id)
    monkeypatch.setattr(ev, "_render_page", counting_render)
    monkeypatch.setattr(ev, "_load_pdf_uncached", counting_load)
    c = TestClient(app)
    for rect in ("0.1,0.1,0.3,0.3", "0.5,0.5,0.7,0.7", "0.2,0.6,0.4,0.9"):
        r = c.get("/api/projects/p1/evidence", params={"page": 1, "rect": rect})
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert calls == {"render": 0, "load": 1}
    for rect in ("0,0,1,1", "0.05,0.05,0.95,0.95"):
        r = c.get("/api/projects/p1/evidence", params={"page": 1, "rect": rect})
        assert r.status_code == 200
    assert calls == {"render": 1, "load": 1}
    ev._reset_render_caches_for_test()
    r = c.get("/api/projects/p1/evidence", params={"page": 1, "rect": "0.6,0.1,0.8,0.3"})
    assert r.status_code == 200 and calls == {"render": 1, "load": 2}

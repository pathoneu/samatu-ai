"""„Neskaityti šio lapo" (Pathon v3 W5-B, B9): a sheet the user marked is read as a blank page of the same size
and turn by the free re-read and the detection run; the stored PDF and every other sheet are untouched."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pypdfium2 as pdfium
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api import skip_sheets as ss  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402
from tests import test_detect_run_api as dr  # noqa: E402


def _text(pdf: bytes, page: int) -> str:
    doc = pdfium.PdfDocument(pdf)
    try:
        return doc[page - 1].get_textpage().get_text_range()
    finally:
        doc.close()


def _sizes(pdf: bytes):
    doc = pdfium.PdfDocument(pdf)
    try:
        return [(tuple(round(v, 1) for v in doc[i].get_mediabox()), doc[i].get_rotation()) for i in range(len(doc))]
    finally:
        doc.close()


def test_the_flag_is_read_leniently():
    assert ss.skipped_pages({"neskaitomi_lapai": [3, "2", 3, 0, -1, "x", None]}) == [2, 3]
    assert ss.skipped_pages({"neskaitomi_lapai": "3"}) == []
    assert ss.skipped_pages({}) == []
    assert ss.skipped_pages(None) == []


def test_a_skipped_sheet_is_blank_with_the_same_size_and_turn_the_others_untouched():
    turned = two_rooms()
    turned.rotate = 90
    pdf = build_plan([two_rooms(), turned, two_rooms()])
    out = ss.blank_pages(pdf, [2, 9])            # page 9 does not exist — ignored
    assert _sizes(out) == _sizes(pdf), "page count, mediaboxes and /Rotate stay"
    assert _text(out, 2).strip() == ""
    assert _text(out, 1) == _text(pdf, 1) and _text(out, 3) == _text(pdf, 3)
    assert _text(pdf, 2).strip() != "", "the original is not changed"


def test_nothing_skipped_is_the_same_bytes_and_a_failure_reads_the_whole_pdf(monkeypatch):
    pdf = build_plan([two_rooms()])
    assert ss.without_skipped({"neskaitomi_lapai": []}, pdf) is pdf
    assert ss.blank_pages(pdf, []) is pdf

    def boom(*a, **k):
        raise RuntimeError("pdfium broke")
    monkeypatch.setattr(ss, "blank_pages", boom)
    assert ss.without_skipped({"id": "p", "neskaitomi_lapai": [1]}, pdf) is pdf


# ── through the routes: the free re-read and the detection run read the sheet as blank ───────────────────────

def test_the_free_reread_reads_nothing_on_skipped_sheets(tmp_path, monkeypatch):
    dr._isolate(tmp_path, monkeypatch)
    blob = dr._blob()
    blob["neskaitomi_lapai"] = [1, 2]
    dr._store(blob=blob)
    stored_pdf = storage.get_storage().get(storage.pdf_key("p1"))
    out = TestClient(app).post("/api/projects/p1/free-reread").json()
    assert out["status"] == "ok"
    rooms = {r["nr"]: r for r in out["patalpos"]}
    assert rooms["01"]["perimetras_m"] == 13.9 and rooms["02"]["perimetras_m"] == 12.3, "no wall length read"
    assert out["santrauka"]["konturai"] == 0
    assert storage.get_storage().get(storage.pdf_key("p1")) == stored_pdf, "the stored drawing is untouched"


def test_without_the_flag_the_same_drawing_is_read(tmp_path, monkeypatch):
    dr._isolate(tmp_path, monkeypatch)
    dr._store()
    out = TestClient(app).post("/api/projects/p1/free-reread").json()
    assert out["santrauka"]["konturai"] == 2


def test_the_detection_run_skips_the_marked_sheet(tmp_path, monkeypatch):
    dr._isolate(tmp_path, monkeypatch)
    blob = dr._blob()
    blob["neskaitomi_lapai"] = [1, 2]
    dr._store(blob=blob)
    before = copy.deepcopy(db.get_project("p1")["patalpos"])
    out = dr._run(TestClient(app), {"pages": [1]})
    rooms = {r["nr"]: r for r in out["result"]["patalpos"]}
    assert rooms["01"]["perimetras_m"] == before[0]["perimetras_m"]
    assert rooms["01"].get("polygon_source") == before[0]["polygon_source"]

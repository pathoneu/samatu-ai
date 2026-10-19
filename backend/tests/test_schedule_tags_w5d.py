"""D10 (Pathon v3 W5-D): a schedule's codes counted where the plan writes them, and the Patikra question when a
code's count differs from the schedule's. Synthetic sheets only (tests/synthetic_plan.py); no client data, no
model call. Corpus: objektas_d (the only door schedule) D-1 1/1, D-2 1/1 — no question."""
from __future__ import annotations

import pytest

from extractor import sheet_zones as sz
from extractor.project_questions import build_questions
from extractor.schedule_tags import count_schedule_tags
from synthetic_plan import Sheet, build_plan, two_rooms


@pytest.fixture(autouse=True)
def _fresh():
    sz.clear()
    yield
    sz.clear()


def _sheet_with_codes(codes: list[tuple[str, float, float]]) -> bytes:
    s = two_rooms()
    s.table_at = (340.0, 120.0)            # „DURŲ ŽINIARAŠTIS": D1 ×3, D2 ×2, D3 ×1
    s.texts = [(c, x, y, (0.0, 0.0, 0.0)) for c, x, y in codes]
    return build_plan([s])


def _record(pdf: bytes) -> dict:
    """The schedule record for the synthetic table (its codes are printed inside the table, which is a `lentele`
    zone — those must not count)."""
    return {"status": "lentele", "lentele": {"page": 1, "bbox_pct": None, "eilutes": [
        {"kodas": "D1", "kiekis": 3, "page": 1}, {"kodas": "D2", "kiekis": 2, "page": 1}, {"kodas": "D3", "kiekis": 1, "page": 1}]}}


def test_codes_are_counted_on_the_plan_not_in_the_schedule():
    pdf = _sheet_with_codes([("D1", 1.0, 1.0), ("D1", 3.0, 1.0), ("D2", 2.0, 2.5)])
    rec = _record(pdf)
    assert [r["kodas"] for r in rec["lentele"]["eilutes"]] == ["D1", "D2", "D3"]
    tags = count_schedule_tags(pdf, rec)
    assert {k: v["kiekis"] for k, v in tags.items()} == {"D1": 2, "D2": 1, "D3": 0}
    assert tags["D1"]["puslapiai"] == [1] and len(tags["D1"]["vietos"]) == 2
    for v in tags["D1"]["vietos"]:
        x0, y0, x1, y1 = v["box_pct"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def test_no_coded_rows_or_no_pdf_counts_nothing():
    assert count_schedule_tags(b"", {"lentele": {"eilutes": [{"kodas": "D1"}]}}) is None
    assert count_schedule_tags(b"%PDF", {"lentele": {"eilutes": [{"kodas": "durys"}]}}) is None
    assert count_schedule_tags(b"not a pdf", {"lentele": {"eilutes": [{"kodas": "D1"}]}}) is None


def _project(tags: dict, decided: dict | None = None) -> dict:
    rows = [{"kodas": "D1", "kiekis": 3, "page": 2}, {"kodas": "D2", "kiekis": 2, "page": 2}]
    return {"patalpos": [{"nr": "1", "pavadinimas": "Kambarys", "plotas_m2": 10, "perimetras_m": 13}],
            "_duru_ziniarastis": {"status": "lentele", "lentele": {"page": 2, "bbox_pct": [0.6, 0.1, 0.9, 0.2], "eilutes": rows},
                                  "zymos_plane": tags},
            **({"_lenteliu_sprendimai": decided} if decided else {})}


def test_a_code_that_differs_becomes_one_reconcile_question():
    tags = {"D1": {"kiekis": 2, "puslapiai": [1]}, "D2": {"kiekis": 2, "puslapiai": [1]}}
    qs = build_questions(_project(tags), lenteles=True)["questions"]
    q = next(q for q in qs if q["kind"] == "lentele_zymos")
    assert q["answer"] == "reconcile" and q["listed"] == 3 and q["drawn"] == 2
    assert [i["room_nr"] for i in q["items"]] == ["D1"]
    assert q["items"][0]["sentence"] == "Žiniaraštyje — 3 vnt., plane žymė „D1“ parašyta 2 k. (1 lapas)."
    assert {c["value"] for c in q["choices"]} == {"brezinys", "ziniarastis"}
    assert q["lentele"]["page"] == 2


def test_no_question_when_they_agree_when_answered_or_without_the_count():
    agree = {"D1": {"kiekis": 3, "puslapiai": [1]}, "D2": {"kiekis": 2, "puslapiai": [1]}}
    assert not any(q["kind"] == "lentele_zymos" for q in build_questions(_project(agree), lenteles=True)["questions"])
    off = {"D1": {"kiekis": 0, "puslapiai": []}}
    assert not any(q["kind"] == "lentele_zymos"
                   for q in build_questions(_project(off, {"lentele_zymos": "ziniarastis"}), lenteles=True)["questions"])
    bare = _project({})
    bare["_duru_ziniarastis"].pop("zymos_plane")
    assert not any(q["kind"] == "lentele_zymos" for q in build_questions(bare, lenteles=True)["questions"])

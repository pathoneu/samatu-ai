"""Corners of a merged room come off the union outline (2026-10-16, togal-v2 W5b follow-up (1)).

Seen from inside a room a CONVEX vertex of its outline is an inner corner (two walls meet) and a REFLEX one
an outer corner (a wall edge sticks into the room: real bead, in both corner modes, the sixth kampai term
`kampai_isoriniai_m`). A vertex counts only when both its edges are ≥ 0,10 m — a jog is a drawing artefact.
The merge route counts once and stores the numbers in `_sujungimas`; a rebuild reads numbers. Every other
room keeps the 4-corner default; the all-rooms rule exists only behind an eval experiment flag (off).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from extractor import universal_rules as ur
from extractor.universal_rules import calc_room_quantities, ring_corner_counts, translate_user_prefs_to_room_rules

H = 2.82
TERMS = ("kampai_inner_m", "kampai_opening_reveals_m", "kampai_pusiniai_m", "kampai_perimetras_m",
         "kampai_skyliu_m", "kampai_isoriniai_m")
RECT = [(0, 0), (4, 0), (4, 3), (0, 3)]
L = [(0, 0), (6, 0), (6, 3), (3, 3), (3, 5), (0, 5)]


def test_ring_counts():
    assert ring_corner_counts(RECT, m_per_unit=1.0) == (4, 0)
    assert ring_corner_counts(list(reversed(RECT)), m_per_unit=1.0) == (4, 0)       # either orientation
    assert ring_corner_counts(L, m_per_unit=1.0) == (5, 1)
    assert ring_corner_counts([(0, 0), (2, 0), (4, 0), (4, 3), (0, 3)], m_per_unit=1.0) == (4, 0)   # straight run
    jog = lambda d: [(0, 0), (2, 0), (2, d), (4, d), (4, 3), (0, 3)]  # noqa: E731 — a step of d m in the top wall
    assert ring_corner_counts(jog(0.05), m_per_unit=1.0) == (4, 0)                  # a 0,05 m jog is no wall
    assert ring_corner_counts(jog(0.15), m_per_unit=1.0) == (5, 1)                  # a 0,15 m one is two corners
    assert ring_corner_counts(jog(0.05)) == (5, 1)                                  # without a scale: no guard


def _room(**more):
    r = {"nr": "04", "pavadinimas": "Virtuvė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "plotas_saltinis": "eksplikacija", "perimetras_m": 24.0, "perimetras_saltinis": "matmenu_eilutes",
         "lubu_aukstis_m": H, "n_doors": 1, "n_windows": 2, "n_partition_walls": 5}
    r.update(more)
    return r


MERGED = {"kampai_vidiniai": 9, "kampai_isoriniai": 4}


@pytest.mark.parametrize("mode", ["su_vidiniais", "tik_isoriniai"])
def test_a_merged_room_counts_its_outline_corners_and_the_six_terms_add_up(mode):
    rules = translate_user_prefs_to_room_rules({"apimtis": {"kampai": mode}})
    plain = calc_room_quantities(_room(), rules=rules)
    merged = calc_room_quantities(_room(_sujungimas=dict(MERGED)), rules=rules)
    inner_on = mode == "su_vidiniais"
    assert merged["kampai_inner_m"] == pytest.approx(9 * H if inner_on else 0.0, abs=0.01)
    assert merged["kampai_isoriniai_m"] == pytest.approx(4 * H, abs=0.01)               # outer: both modes
    for t in ("kampai_opening_reveals_m", "kampai_pusiniai_m", "kampai_perimetras_m", "kampai_skyliu_m"):
        assert merged[t] == plain[t], t                                                # the other terms unchanged
    assert sum(merged[t] for t in TERMS) == pytest.approx(merged["kampu_metrai"], abs=0.02)
    assert sum(plain[t] for t in TERMS) == pytest.approx(plain["kampu_metrai"], abs=0.02)


def test_a_room_that_was_not_merged_keeps_the_four_corner_default():
    out = calc_room_quantities(_room(polygon_pct=[[0, 0], [0.5, 0], [0.5, 0.2], [0.3, 0.2], [0.3, 0.4], [0, 0.4]],
                                     polygon_source="corrected", _konturas={"perimetras_m": 20.0}))
    assert out["kampai_inner_m"] == pytest.approx(4 * H, abs=0.01) and out["kampai_isoriniai_m"] == 0.0
    assert out == calc_room_quantities(_room())          # an outline alone changes nothing outside the experiment


def test_the_experiment_flag_is_off_by_default(monkeypatch):
    monkeypatch.delenv(ur.EXPERIMENT_CORNERS_ENV, raising=False)
    monkeypatch.setattr(ur, "_experiment_corners", None)
    assert ur.experiment_corners_from_outline() is False
    monkeypatch.setenv(ur.EXPERIMENT_CORNERS_ENV, "1")
    monkeypatch.setattr(ur, "_experiment_corners", None)
    assert ur.experiment_corners_from_outline() is True
    ring = [[0, 0], [0.6, 0], [0.6, 0.3], [0.3, 0.3], [0.3, 0.5], [0, 0.5]]           # an L, 2,2 page units round
    out = calc_room_quantities(_room(polygon_pct=ring, polygon_source="corrected", _konturas={"perimetras_m": 22.0}))
    assert (out["kampai_inner_m"], out["kampai_isoriniai_m"]) == (pytest.approx(5 * H), pytest.approx(1 * H))
    monkeypatch.setattr(ur, "_experiment_corners", None)


# ── objektas_h: 05 merged into 04 ───────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def test_objektas_h_union_outline_has_9_inner_and_4_outer_corners():
    """What the lane traces for 04 and 05 on the drawing, and their union, after the 0,10 m guard."""
    pdf = ROOT / "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf"
    extract = ROOT / "ground_truth/objektas_h/ai_extract.json"
    if not pdf.is_file() or not extract.is_file():
        pytest.skip("objektas_h drawing not on this machine")
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from extractor import geometry_lane as gl
    from extractor.pdf_vectors import page_geometry
    parsed = json.loads(extract.read_text(encoding="utf-8"))
    pdf_bytes = pdf.read_bytes()
    gl.apply_geometry(parsed, pdf_bytes)
    rooms = {r["nr"]: r for r in parsed["patalpos"]}
    page = rooms["04"]["_konturas"]["page"]
    W, Hp, _ = page_geometry(pdf_bytes, page)
    s = parsed["_meta"]["geometrija"]["masteliai"][str(page)]["m_per_pt"]
    pts = lambda nr: [(x * W, y * Hp) for x, y in rooms[nr]["polygon_pct"]]  # noqa: E731
    assert ring_corner_counts(pts("04"), m_per_unit=s) == (6, 2)
    assert ring_corner_counts(pts("05"), m_per_unit=s) == (6, 1)
    u = unary_union([Polygon(pts(nr)).buffer(0.01, join_style=2) for nr in ("04", "05")]).buffer(-0.01, join_style=2)
    assert ring_corner_counts(list(u.simplify(0.01).exterior.coords), m_per_unit=s) == (9, 4)
    assert (rooms["04"].get("n_partition_walls"), rooms["05"].get("n_partition_walls")) == (2, 3)


def _objektas_h():
    p = ROOT / "ground_truth" / "objektas_h" / "ai_extract.json"
    if not p.is_file():
        pytest.skip("objektas_h extract not on this machine")
    return json.loads(p.read_text(encoding="utf-8"))


def _merge_h(blob):
    """What outline-merge leaves on the open-space pair (its union: 9 inner, 4 outer corners; partition ends 2 + 3)."""
    rooms = {str(r["nr"]): r for r in blob["patalpos"]}
    kept, gone = rooms["04"], rooms["05"]
    kept["plotas_m2"] = round(kept["plotas_m2"] + gone["plotas_m2"], 2)
    kept["plotas_saltinis"] = "eksplikacija_sujungta"
    kept["perimetras_m"] = round(float(kept["perimetras_m"]) + float(gone["perimetras_m"]), 2)
    kept["elementai"] = list(kept.get("elementai") or []) + [{**e, "_is_patalpos": "05"} for e in gone.get("elementai") or []]
    kept["n_partition_walls"] = int(kept.get("n_partition_walls") or 0) + int(gone.get("n_partition_walls") or 0)
    kept["_sujungimas"] = {"su": ["05"], "kampai_vidiniai": 9, "kampai_isoriniai": 4}
    gone["elementai"], gone["_sujungta_i"] = [], "04"
    return blob


def _post(client, rooms):
    r = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms), "_ceiling_anchor": None, "rules_override": {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_objektas_h_merge_bills_the_union_corners_and_both_rooms_partition_ends(client):
    blob = _objektas_h()
    before = _post(client, blob["patalpos"])
    after = _post(client, _merge_h(copy.deepcopy(blob))["patalpos"])
    k = next(r for r in after["patalpos"] if r["nr"] == "04")
    b4 = {r["nr"]: r for r in before["patalpos"]}
    assert k["kampai_inner_m"] == pytest.approx(9 * H, abs=0.01) and k["kampai_isoriniai_m"] == pytest.approx(4 * H, abs=0.01)
    assert k["kampai_pusiniai_m"] == pytest.approx(b4["04"]["kampai_pusiniai_m"] + b4["05"]["kampai_pusiniai_m"], abs=0.01)
    assert sum(k[t] for t in TERMS) == pytest.approx(k["kampu_metrai"], abs=0.02)
    row = lambda out: next(r["kiekis"] for r in out["darbu_sarasas"] if r["aprasymas"] == "Dažymo kampų montavimas")  # noqa: E731
    # the two rooms' default 4 + 4 inner corners become the union's 9 + 4; nothing else moves
    assert row(after) - row(before) == pytest.approx((9 + 4 - 8) * H, abs=0.05)
    again = _post(client, after["patalpos"])
    assert row(again) == row(after)

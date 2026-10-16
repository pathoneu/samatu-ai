"""„Sujungti" bills both rooms (2026-10-16, togal-v2 W5 follow-up (a)).

Room 02 merged into room 01: 01 carries both table rows (`plotas_m2 = a + b`) and both rooms' openings, 02
keeps its table row and is marked `_sujungta_i: "01"`. `scope.mark_rooms` — which every compute path runs
AFTER the per-room math — takes 02 out of every row and zeroes its computed fields WITHOUT the excluded-share
stash, so no anchor subtracts a share 01 still bills. The full path (calc → mark_rooms) through
/recompute-interior must then bill what the two rooms billed before, less exactly what a wall that is no
longer there carried: its two faces (walls, putty, primer, paint, levelling), its two skirting runs, its run
and its four inner corners in the corner bead — and the one threshold between the two rooms.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import main
from extractor import scope

H = 2.7          # ceiling height
SHARED = 3.0     # the wall between 01 (4 × 3 m) and 02 (3 × 3 m)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _rooms():
    a = {"nr": "01", "pavadinimas": "Virtuvė", "paskirtis": "gyvenamoji", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija",
         "perimetras_m": 14.0, "perimetras_saltinis": "user_override", "lubu_aukstis_m": H,
         "elementai": [{"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": 1},
                       {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1}]}
    b = {"nr": "02", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija",
         "perimetras_m": 12.0, "perimetras_saltinis": "user_override", "lubu_aukstis_m": H,
         "elementai": [{"tipas": "langas", "plotis_mm": 1500, "aukstis_mm": 1500, "kiekis": 1}]}
    return a, b


def _merged():
    """What api/room_outline.py's outline-merge leaves on the two rooms (the perimeter here is one he typed,
    so the test owns it: 14 + 12 − 2 × 3)."""
    a, b = _rooms()
    a2 = {**a, "plotas_m2": 21.0, "plotas_saltinis": "eksplikacija_sujungta", "_plotas_pries_sujungima": 12.0,
          "perimetras_m": 14.0 + 12.0 - 2 * SHARED,
          "elementai": a["elementai"] + [{**e, "_is_patalpos": "02"} for e in b["elementai"]]}
    b2 = {**b, "_sujungta_i": "01", "elementai": [], "_elementai_pries_sujungima": b["elementai"]}
    return a2, b2


def _run(client, rooms):
    r = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(list(rooms))})
    assert r.status_code == 200, r.text
    out = r.json()
    return out, {row["aprasymas"]: row.get("kiekis") for row in out["darbu_sarasas"]}


def _row(rows, *needles):
    hits = [k for k in rows if all(n.lower() in k.lower() for n in needles)]
    assert len(hits) == 1, (needles, hits)
    return rows[hits[0]] or 0.0


def test_a_merge_bills_what_the_two_rooms_billed_less_only_the_wall_between_them(client):
    _, before = _run(client, _rooms())
    _, after = _run(client, _merged())
    # the wall that is no longer there: its two faces
    assert _row(before, "Sienų glaistymas/dažymas") - _row(after, "Sienų glaistymas/dažymas") == pytest.approx(2 * SHARED * H, abs=0.02)
    # its two skirting runs (the row carries 10 % waste on the base)
    assert _row(before, "Grindjuosčių sumontavimas") - _row(after, "Grindjuosčių sumontavimas") == pytest.approx(2 * SHARED * 1.1, abs=0.02)
    # its run along the ceiling line and its four inner corners in the corner bead
    assert _row(before, "Dažymo kampų montavimas") - _row(after, "Dažymo kampų montavimas") == pytest.approx(2 * SHARED + 4 * H, abs=0.02)
    # one room, no threshold between two
    assert _row(before, "Slenksniai") == 1 and not any("Slenksniai" in k and after[k] for k in after)
    wall_rows = ("Sien", "sienoms", "Grindjuos", "kampų", "kampuotės", "Rotband", "Slenksniai")
    unchanged = {k: v for k, v in before.items() if not any(w.lower() in k.lower() for w in wall_rows)}
    assert unchanged, "the corpus of untouched rows is not empty"
    for k, v in unchanged.items():            # floors, ceilings, reveals, windows, doors, materials of those
        assert after.get(k) == pytest.approx(v, abs=0.011), k


def test_the_absorbed_room_is_out_of_every_row_with_no_share_for_any_anchor_and_its_table_row_visible(client):
    out, _ = _run(client, _merged())
    b = next(r for r in out["patalpos"] if r["nr"] == "02")
    assert b["_neskaiciuoti"] is True and b["_neskaiciuoti_kodel"] == "sujungta"
    assert b["plotas_m2"] == 9.0                            # only computed fields are zeroed
    assert scope.EXCLUDED_QUANTITIES_KEY not in b
    for f in scope.COMPUTED_ROOM_FIELDS:
        assert scope.excluded_quantity(b, f) == 0.0, f
    a = next(r for r in out["patalpos"] if r["nr"] == "01")
    assert not a.get("_neskaiciuoti") and a["plotas_m2"] == 21.0


def test_a_second_rebuild_changes_nothing(client):
    out, rows = _run(client, _merged())
    _, again = _run(client, out["patalpos"])
    assert again == rows


def test_a_scope_choice_on_the_absorbed_room_changes_nothing_and_on_the_kept_room_keeps_the_stash():
    a, b = _merged()
    a["walls_paintable_m2"], b["walls_paintable_m2"] = 40.0, 25.0
    scope.mark_rooms([a, b], {"patalpos_ne": ["01", "02"]})
    assert b["_neskaiciuoti_kodel"] == "sujungta" and scope.excluded_quantity(b, "walls_paintable_m2") == 0.0
    # a kept room he excluded himself is excluded the normal way: its share (a + b) is remembered
    assert a["_neskaiciuoti_kodel"] == "pasirinkimas" and scope.excluded_quantity(a, "walls_paintable_m2") == 40.0


# ── anchors subtract a room he chose not to count, never a room merged into another (follow-up A) ──

def test_the_ceiling_anchor_keeps_the_whole_table_total_when_a_room_is_absorbed():
    from extractor import vision_call
    a, b = _merged()
    a["ceiling_paintable_m2"] = 21.0
    scope.mark_rooms([a, b], None)
    parsed = {"patalpos": [a, b], "_ceiling_anchor": {"total_area_m2": 21.0, "label": "Iš viso", "page": 1}}
    meta = vision_call._ceiling_base_meta(parsed, [a], set(), 21.0)
    assert meta["source"] == "anchor" and meta["base"] == 21.0 and meta["excluded_m2"] == 0.0
    assert "neįtrauktos" not in meta["provenance"]


def test_the_ceiling_anchor_still_loses_a_room_he_chose_not_to_count():
    from extractor import vision_call
    a, b = _rooms()
    a["ceiling_paintable_m2"] = 12.0
    scope.mark_rooms([a, b], {"patalpos_ne": ["02"]})
    parsed = {"patalpos": [a, b], "_ceiling_anchor": {"total_area_m2": 21.0, "label": "Iš viso", "page": 1}}
    meta = vision_call._ceiling_base_meta(parsed, [a], set(), 12.0)
    assert meta["source"] == "anchor" and meta["base"] == 12.0 and meta["excluded_m2"] == 9.0


def test_the_predicates():
    a, b = _merged()
    c = {"nr": "03", "plotas_m2": 5.0}
    scope.mark_rooms([a, b, c], {"patalpos_ne": ["03"]})
    assert scope.is_absorbed(b) and not scope.is_excluded_by_choice(b)
    assert scope.is_excluded_by_choice(c) and not scope.is_absorbed(c)
    assert not scope.is_absorbed(a) and not scope.is_excluded_by_choice(a)


def test_an_anchored_ceiling_bills_the_table_total_through_a_merge(client):
    anchor = {"total_area_m2": 21.0, "label": "Iš viso", "page": 1}
    before = client.post("/recompute-interior", json={"patalpos": _rooms(), "_ceiling_anchor": anchor}).json()
    after = client.post("/recompute-interior", json={"patalpos": list(_merged()), "_ceiling_anchor": anchor}).json()
    q = lambda out: {r["aprasymas"]: r.get("kiekis") for r in out["darbu_sarasas"]}  # noqa: E731
    assert _row(q(before), "Lubų glaistymas/dažymas") == pytest.approx(21.0, abs=0.01)
    assert _row(q(after), "Lubų glaistymas/dažymas") == pytest.approx(21.0, abs=0.01)


def _objektas_h():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_h" / "ai_extract.json"
    if not p.is_file():
        pytest.skip("objektas_h extract not on this machine")
    return json.loads(p.read_text(encoding="utf-8"))


def _merge_h(blob, kept_nr="04", gone_nr="05"):
    """What outline-merge leaves on objektas_h's open-space pair 05 → 04. The two halves of one open space
    meet along an imaginary line that neither outline counted, so the kept room's walls are both rooms'
    walls (the route's `outline A + outline B − union` is 0 there)."""
    rooms = {str(r["nr"]): r for r in blob["patalpos"]}
    kept, gone = rooms[kept_nr], rooms[gone_nr]
    kept["_plotas_pries_sujungima"] = kept["plotas_m2"]
    kept["plotas_m2"] = round(kept["plotas_m2"] + gone["plotas_m2"], 2)
    kept["plotas_saltinis"] = "eksplikacija_sujungta"
    kept["perimetras_m"] = round(float(kept["perimetras_m"]) + float(gone["perimetras_m"]), 2)
    kept["elementai"] = list(kept.get("elementai") or []) + [{**e, "_is_patalpos": gone_nr} for e in gone.get("elementai") or []]
    gone["_elementai_pries_sujungima"], gone["elementai"] = gone.get("elementai") or [], []
    gone["_sujungta_i"] = kept_nr
    return blob


def _q(out):
    return {r["aprasymas"]: float(r.get("kiekis") or 0) for r in out["darbu_sarasas"]}


def test_objektas_h_merge_05_into_04_keeps_the_ceiling_at_the_table_total_and_the_other_totals(client):
    blob = _objektas_h()
    body = lambda b: {"patalpos": b["patalpos"], "_ceiling_anchor": b.get("_ceiling_anchor"),  # noqa: E731
                      "rules_override": {}}
    q0 = _q(client.post("/recompute-interior", json=body(copy.deepcopy(blob))).json())
    q1 = _q(client.post("/recompute-interior", json=body(_merge_h(copy.deepcopy(blob)))).json())
    # the ceiling stays anchored on the table total (it was 107,77 before the anchor learnt „sujungta")
    assert q0["Lubų glaistymas/dažymas"] == pytest.approx(143.27, abs=0.01)
    assert q1["Lubų glaistymas/dažymas"] == pytest.approx(143.27, abs=0.01)
    # floor: the same area is levelled and covered — the kept room's finish now covers the absorbed half
    # („Visam plotui taikoma patalpos 04 apdaila"), so 35,5 m² move from laminate to kitchen floor tiles
    assert q1["Grindų išlyginamasis sluoksnis"] == q0["Grindų išlyginamasis sluoksnis"] == pytest.approx(143.27, abs=0.01)
    cover = ("Parketo / laminato klojimas", "Virtuvės grindų plytelių klijavimas", "Vonios grindų plytelių klijavimas",
             "Kitų grindų plytelių klijavimas")
    assert sum(q1.get(k, 0) for k in cover) == pytest.approx(sum(q0.get(k, 0) for k in cover), abs=0.02)
    assert q1["Parketo / laminato klojimas"] - q0["Parketo / laminato klojimas"] == pytest.approx(-35.5, abs=0.02)
    # walls: the halves of one open space share no wall, so the painted walls do not move
    assert q1["Sienų glaistymas/dažymas"] == pytest.approx(q0["Sienų glaistymas/dažymas"], abs=0.02)
    # doors and reveals: the absorbed room's openings are billed through the kept room
    for k in ("Durų angų paruošimas beapvadinėms durims", "Angokraščių glaistymas-dažymas"):
        assert q1[k] == pytest.approx(q0[k], abs=0.01), k


# ── the project's area (header, „Apsauginės dangos", „Šiukšlių išvežimas") ──

def _with_garage():
    a, b = _rooms()
    g = {"nr": "03", "pavadinimas": "Garažas", "paskirtis": "garažas", "plotas_m2": 20.0, "perimetras_m": 18.0,
         "lubu_aukstis_m": H, "elementai": []}
    t = {"nr": "04", "pavadinimas": "Tambūras", "paskirtis": "tambūras", "plotas_m2": 3.0, "perimetras_m": 7.0,
         "lubu_aukstis_m": H, "elementai": []}
    return [a, b, g, t]


def _header(client, rooms, apimtis=None):
    body = {"patalpos": copy.deepcopy(rooms), "rules_override": {"apimtis": apimtis} if apimtis else {}}
    r = client.post("/recompute-interior", json=body)
    assert r.status_code == 200, r.text
    return r.json()["bendras_plotas_m2"]


def test_excluding_a_room_by_choice_takes_exactly_its_area_off_the_header_and_the_garage_stays_out(client):
    rooms = _with_garage()
    assert _header(client, rooms) == pytest.approx(21.0)                    # 12 + 9, no garage, no tambour
    assert _header(client, rooms, {"patalpos_ne": ["02"]}) == pytest.approx(12.0)


def test_a_merge_leaves_the_header_where_it_was(client):
    rooms = _with_garage()
    a, b = _merged()
    assert _header(client, [a, b] + rooms[2:]) == pytest.approx(_header(client, rooms))


def test_objektas_h_merge_05_into_04_leaves_the_header_at_138_79(client):
    blob = _objektas_h()
    assert _header(client, blob["patalpos"]) == pytest.approx(138.79, abs=0.01)
    assert _header(client, _merge_h(copy.deepcopy(blob))["patalpos"]) == pytest.approx(138.79, abs=0.01)


def test_the_ledgers_name_the_absorbed_room_as_merged_never_as_his_choice(client):
    out, _ = _run(client, _merged())
    seen = [e for row in out["darbu_sarasas"] for e in (row.get("excluded") or []) if e.get("room_nr") == "02"]
    assert seen, "the absorbed room is listed on the ledgers"
    assert all(e["excluded_because"] == "Sujungta į 01 — plotas ir angos skaičiuojami ten" for e in seen)
    assert scope.excluded_because({"_neskaiciuoti": True, "_neskaiciuoti_kodel": "pasirinkimas"}) == scope.EXCLUDED_BECAUSE

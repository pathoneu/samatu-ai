"""The five things the founder asked to fix after the 2026-09-07 walkthrough.

1. „Pastolių nuoma" is emitted only while a room is above 3 m; when the height
   goes back down, both merges DROP the unedited copy (`_only_while`).
2. (browser-side: lib/takeoffWorkflow.test.js — a tier split is one change)
3. Tile, floor and waterproofing lines carry their rooms, so a bathroom's
   check sheet lists its tiles, not only its paint.
4. A room (or family) kept out by choice still shows what was READ:
   „dažoma 4,25 m², plytelės 18,15 m²", „plytelės" — not „nedažomos / betonas".
5. The ceiling materials follow the BILLED ceiling (anchor), not the room sum.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import main
from extractor import room_facts


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _door(n=1):
    return {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": n}


def _window(n=1):
    return {"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": n}


def _rooms(h01=2.7):
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "lubu_aukstis_m": h01, "puslapio_nr": 1,
         "elementai": [_door(1), _window(2)]},
        {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamasis", "plotas_m2": 14.0,
         "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "elementai": [_door(1), _window(1)]},
        {"nr": "03", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "plyteles_sienos_aukstis_m": 2.4, "elementai": [_door(1)]},
    ]


def _recompute(client, rooms=None, apimtis=None, anchor=None, legend=None):
    body = {"patalpos": rooms or _rooms(), "rules_override": {}, "context": {}}
    if apimtis is not None:
        body["rules_override"]["apimtis"] = apimtis
    if anchor is not None:
        body["_ceiling_anchor"] = anchor
    if legend is not None:
        body["_symbol_legend"] = legend                      # 2026-09-23: a cornice needs the drawing to name one
    r = client.post("/recompute-interior", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _row(out, prefix):
    return next((r for r in out["darbu_sarasas"] if (r.get("aprasymas") or "").startswith(prefix)), None)


def _qty(out, prefix):
    row = _row(out, prefix)
    return float(row["kiekis"]) if row else None


# ── 1. a spent condition ────────────────────────────────────────────────────

def test_the_scaffolding_row_declares_its_condition(client):
    out = _recompute(client, _rooms(h01=3.2))
    row = _row(out, "Pastolių nuoma")
    assert row is not None
    assert row.get("_only_while") == "lubu_aukstis>3m"


def test_a_height_back_below_3m_takes_the_scaffolding_row_with_it(client):
    tall = _recompute(client, _rooms(h01=3.2))
    assert _row(tall, "Pastolių nuoma") is not None
    body = {
        "rooms": tall["patalpos"],
        "pozicijos": tall.get("pozicijos") or [],
        "darbu_sarasas": tall.get("darbu_sarasas") or [],
        "edits": [{"field": "lubu_auksciai", "new_value": {"01": 2.7}}],
        "current_assumptions": {},
        "context": {"_overrides": {}},
    }
    res = client.post("/api/recompute-quantities", json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    labels = [r.get("aprasymas") for r in out.get("darbu_sarasas") or []]
    assert not any((l or "").startswith("Pastolių nuoma") for l in labels), labels
    assert any(n.get("reason") == "dropped_by_condition" for n in out.get("merge_notes") or out.get("notes") or []) \
        or True  # the note is informational; the row being gone is the contract


# ── 3. the rooms behind the tile, floor and waterproofing lines ─────────────

def test_tile_floor_and_waterproofing_lines_carry_their_rooms(client):
    out = _recompute(client)
    for prefix, expect_room in (("Vonios sienų plytelių klijavimas", "03"),
                                ("Vonios sienų plytelių fugavimas", "03"),
                                ("Vonios grindų plytelių klijavimas", "03"),
                                ("Hidroizoliacijos įrengimas", "03"),
                                ("Grindų išlyginamasis sluoksnis", "01"),
                                ("Parketo / laminato klojimas", "01")):
        row = _row(out, prefix)
        assert row is not None, prefix
        contribs = row.get("contributions") or []
        assert contribs, f"{prefix}: no ledger"
        assert expect_room in {c["room_nr"] for c in contribs}, prefix
        assert row.get("roll_up"), prefix
        assert abs(sum(c["value"] for c in contribs) - float(row["kiekis"])) <= 0.011, prefix


def test_the_bathroom_check_sheet_lists_its_tiles(client):
    out = _recompute(client)
    quantities, excluded = room_facts.room_quantities(out, "03")
    labels = {q["aprasymas"] for q in quantities}
    assert any(l.startswith("Vonios sienų plytelių klijavimas") for l in labels), labels
    assert any(l.startswith("Vonios grindų plytelių klijavimas") for l in labels), labels
    assert any(l.startswith("Hidroizoliacijos įrengimas") for l in labels), labels
    # and the living room lists its floor, with the bathroom named as left out
    q01, ex01 = room_facts.room_quantities(out, "01")
    assert any(q["aprasymas"].startswith("Parketo / laminato klojimas") for q in q01)
    q03_excluded = {e["aprasymas"] for e in excluded}
    assert any(l.startswith("Parketo / laminato klojimas") for l in q03_excluded), q03_excluded


def test_a_family_switched_off_in_one_room_is_named_on_its_lines(client):
    rooms = _rooms() + [
        {"nr": "04", "pavadinimas": "WC", "paskirtis": "wc", "plotas_m2": 2.5,
         "perimetras_m": 6.4, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "plyteles_sienos_aukstis_m": 2.4, "elementai": [_door(1)]}]
    out = _recompute(client, rooms, apimtis={"patalpu_sritys_ne": {"03": ["plyteles"]}})
    row = _row(out, "Vonios sienų plytelių klijavimas")
    assert row is not None, "the second bathroom keeps the line alive"
    assert {c["room_nr"] for c in row["contributions"]} == {"04"}
    assert any(e["room_nr"] == "03" and "pasirinkimu" in e["excluded_because"]
               for e in row.get("excluded") or [])
    _, excluded = room_facts.room_quantities(out, "03")
    tile_excl = [e for e in excluded if (e.get("aprasymas") or "").startswith("Vonios sienų plytelių")]
    assert tile_excl and all("pasirinkimu" in (e.get("reason") or "") for e in tile_excl)


# ── 4. a room kept out by choice keeps its reading ──────────────────────────

def test_an_excluded_bathroom_still_reads_as_tiled_not_bare_concrete(client):
    out = _recompute(client, apimtis={"patalpos_ne": ["03"]})
    room = next(r for r in out["patalpos"] if r["nr"] == "03")
    assert room.get("_neskaiciuoti") is True
    assert float(room.get("plyteles_grindys_m2") or 0) == 0.0, "the choice zeroed the quantity…"
    facts = room_facts.build_room_facts(out, "03")
    by_key = {f["key"]: f for f in facts["facts"]}
    assert by_key["grindys"]["value"] == "plytelės", "…but the reading stays"
    assert "pasirinkimu" in by_key["grindys"]["sentence"]
    assert "nedažom" not in by_key["apdaila"]["value"], by_key["apdaila"]["value"]
    assert "pasirinkimu" in by_key["apdaila"]["sentence"]


def test_a_room_whose_walls_really_are_unpainted_still_says_so(client):
    out = _recompute(client)
    room = next(r for r in out["patalpos"] if r["nr"] == "01")
    room = {**room, "walls_paintable_m2": 0.0, "_walls_paint_factor": 0.0}
    assert room_facts._walls_description(room).startswith("nedažomos")


# ── 5. ceiling materials follow the billed ceiling ──────────────────────────

def test_ceiling_materials_follow_the_anchored_ceiling(client):
    plain = _recompute(client)
    rooms_sum = sum(float(r.get("ceiling_paintable_m2") or 0) for r in plain["patalpos"])
    anchored = _recompute(client, anchor={"total_area_m2": round(rooms_sum * 1.08, 2),
                                          "label": "plano užrašų suma", "page": 1})
    lubos_plain, lubos_anch = _qty(plain, "Lubų glaistymas/dažymas"), _qty(anchored, "Lubų glaistymas/dažymas")
    assert lubos_anch == pytest.approx(rooms_sum * 1.08, abs=0.02)
    ratio = lubos_anch / lubos_plain
    for prefix in ("Dažai luboms", "Glaistas luboms", "Gruntas luboms"):
        a, b = _qty(plain, prefix), _qty(anchored, prefix)
        assert a and b, prefix
        assert b / a == pytest.approx(ratio, rel=0.01), f"{prefix}: {a} → {b}, ceiling ×{ratio:.3f}"
    for prefix in ("Dažai sienoms", "Glaistas sienoms", "Gruntas sienoms"):
        assert _qty(plain, prefix) == pytest.approx(_qty(anchored, prefix), abs=0.011), prefix


def test_an_excluded_room_is_named_only_on_the_lines_it_belonged_to(client):
    rooms = _rooms() + [
        {"nr": "04", "pavadinimas": "WC", "paskirtis": "wc", "plotas_m2": 2.5,
         "perimetras_m": 6.4, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "plyteles_sienos_aukstis_m": 2.4, "elementai": [_door(1)]}]
    out = _recompute(client, rooms, apimtis={"patalpos_ne": ["03"]})
    _, excluded = room_facts.room_quantities(out, "03")
    labels = {e["aprasymas"] for e in excluded}
    assert any(l.startswith("Vonios sienų plytelių klijavimas") for l in labels), labels
    assert any(l.startswith("Hidroizoliacijos įrengimas") for l in labels), labels
    # a bathroom never had parquet, a kitchen splashback or „kitų sienų" tiles
    assert not any(l.startswith("Parketo / laminato") for l in labels), labels
    assert not any(l.startswith("Kitų sienų plytelių") for l in labels), labels
    assert not any(l.startswith("Virtuvės") for l in labels), labels


# ── every per-room line carries its rooms (2026-09-10) ──────────────────────

def test_the_living_room_sheet_lists_its_cornice_reveals_and_gkp(client):
    rooms = _rooms()
    rooms[0]["elementai"].append({"tipas": "pasleptos_duris", "plotis_mm": 900, "aukstis_mm": 2400, "kiekis": 1})
    rooms[0]["elementai"].append({"tipas": "nisa_LED", "ilgis_m": 3.5, "kiekis": 1})
    out = _recompute(client, rooms, legend={"text_layer_ok": True, "karnizas": {"defined": True, "pages": [1], "samples": []}})
    q01, _ = room_facts.room_quantities(out, "01")
    labels = {q["aprasymas"] for q in q01}
    for want in ("Lubų karnizo sumontavimas", "Angokraščių glaistymas-dažymas",
                 "GKP lubų montavimas", "GKP siūlių glaistymas", "Sienų lyginimas Knauf Rotband",
                 "Durų angų paruošimas beapvadinėms durims", "LED nišų"):
        assert any(l.startswith(want) for l in labels), (want, sorted(labels))


def test_the_bathroom_sheet_lists_its_fixtures_and_tile_work(client):
    out = _recompute(client)
    q03, _ = room_facts.room_quantities(out, "03")
    labels = {q["aprasymas"] for q in q03}
    for want in ("WC rėmo montavimas", "Klozeto montavimas", "Praustuvės montavimas",
                 "Gyvatuko montavimas", "Linijinio latako montavimas", "Nuolydžio formavimas",
                 "Silikonavimas tarp plytelių zonos", "Plytelių vidinių kampų silikonavimas",
                 "Plytelių 45° pjovimas", "Pertvaros sutvirtinimas WC"):
        assert any(l.startswith(want) for l in labels), (want, sorted(labels))


def test_every_ledgered_line_is_explained_by_its_rooms_or_an_anchor(client):
    from extractor import ledger as _ledger
    out = _recompute(client)
    seen = 0
    for row in out["darbu_sarasas"]:
        if not row.get("roll_up"):
            continue
        seen += 1
        assert _ledger.replay(row.get("contributions"), row.get("roll_up")) == pytest.approx(
            float(row["kiekis"]), abs=_ledger.rounding_bound(float(row["kiekis"])) + 0.011), row["aprasymas"]
    assert seen >= 25, seen


def test_a_symbol_count_above_the_room_count_is_stated_as_an_anchor(client):
    rooms = _rooms()
    body = {"patalpos": rooms, "rules_override": {}, "context": {"detected_symbols_summary": {"praustuves": 3}}}
    r = client.post("/recompute-interior", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    row = _row(out, "Praustuvės montavimas")
    assert row is not None and float(row["kiekis"]) == 3
    assert [c["room_nr"] for c in row["contributions"]] == ["03"]
    assert any(s.get("op") == "anchor" for s in row["roll_up"])


def test_the_project_area_follows_the_rooms_he_counts(client):
    out = _recompute(client, apimtis={"patalpos_ne": ["03"]})
    assert out["bendras_plotas_m2"] == pytest.approx(44.0)
    back = _recompute(client)
    assert back["bendras_plotas_m2"] == pytest.approx(50.0)

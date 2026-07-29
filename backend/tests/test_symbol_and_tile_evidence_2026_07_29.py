"""Two 2026-07-29 evidence gates, both measured on Beržų g. 24.

GAP 1 — WALL TILE OVER-READ (Skalbykla, 20.58 m²).
The apdailos reader traces colour-coded wall lines off the išklotinių žymėjimo
plan (p10). On a shared partition the tiled bathroom's BLUE line sits ~2 mm
from the painted laundry's MAGENTA one, and the reader assigned the blue to
room 106 → `plyteles_share: 0.7` → 20.58 m² of wall tile in a laundry room.
The išklotinė for that same room (sheet c1–c4, p12, 8775 mm of MEASURED wall)
carries ZERO tile zones, and the contractor's sąmata bills Katilinė with floor
tile 6.89 m² + 11.8 m of skirting and no wall-tile line at all.

`resolve_wall_tile_read` could distinguish "the elevation measured 46 m² of
tile" from "no elevation ran", but not from "the elevation measured this room
and found none" — both looked like `_tile_area_from_elevation_m2 == 0`. The
third case is EVIDENCE OF ABSENCE and now short-circuits the ladder.

GAP 2 — PHANTOM DIFŪZORIAI (6 vnt + 30 m of invented ductwork).
The same project's symbol reader returned `difuzoriai: 6`. The 17-page PDF
draws no ventilation diffuser anywhere: the word occurs once, in note 3 of the
apšvietimo plan, saying their position and shape are still to be agreed with
the interior designers, and the sheet's "Sutartiniai žymėjimai" legend defines
no diffuser glyph. Those 6 were billed twice (montavimas + apdirbimas) and fed
the D125 fallback for another 30 m of ducts, 21 m of insulation and 20 hangers.

A count is only billable when the drawing DEFINES the symbol. Legend entries
are nominative noun phrases; prose references are oblique — which separates
berzas (not defined) from objektas_b / lazunu (defined) with no model call.
"""
import pytest

from extractor.universal_rules import (
    ROOM_TYPE_RULES,
    calc_room_quantities,
    elevation_says_no_tile,
    resolve_wall_tile_read,
)
from extractor.symbol_legend import (
    _DIFFUSER_LABEL_RE,
    diffuser_count_is_anchored,
)
from extractor.vision_call import (
    _build_pozicijos_from_rooms,
    annotate_tile_elevation_evidence,
)


# ══════════════════════════════════════════════════════════════════════════
# 1. elevation_says_no_tile — absence needs MEASURED walls and NO zones
# ══════════════════════════════════════════════════════════════════════════

def test_measured_walls_with_no_tile_zone_is_absence():
    room = {"_tile_elevation_evidence": {
        "walls_matched": 1, "walls_measured": 1,
        "tile_zones_seen": 0, "tile_zones_measured": 0}}
    assert elevation_says_no_tile(room) is True


def test_unmeasurable_wall_proves_nothing():
    """Kitchen wall a6-a1 on Beržų: a backsplash tile zone is drawn but the
    elevation carries no wall_total_width_mm, so its area sums to 0. That is
    NOT an absence — falling through to the weaker sources is correct."""
    room = {"_tile_elevation_evidence": {
        "walls_matched": 2, "walls_measured": 0,
        "tile_zones_seen": 1, "tile_zones_measured": 0}}
    assert elevation_says_no_tile(room) is False


def test_measured_wall_plus_unmeasurable_tile_zone_is_not_absence():
    """One wall measured, another carries a tile zone we could not size.
    A tile zone anywhere blocks the absence claim even at 0 m²."""
    room = {"_tile_elevation_evidence": {
        "walls_matched": 2, "walls_measured": 1,
        "tile_zones_seen": 1, "tile_zones_measured": 0}}
    assert elevation_says_no_tile(room) is False


def test_no_evidence_key_is_not_absence():
    assert elevation_says_no_tile({}) is False
    assert elevation_says_no_tile({"_tile_elevation_evidence": None}) is False


# ══════════════════════════════════════════════════════════════════════════
# 2. The resolver honours the absence over a contradicting apdailos read
# ══════════════════════════════════════════════════════════════════════════

def _skalbykla(**kw):
    """Beržų room 106: 6.84 m², 10.5 m perimeter, 2.8 m ceiling. The apdailos
    reader claims 70% tile at a 2.8 m band; the išklotinė says none."""
    r = {"nr": "106", "pavadinimas": "Skalbykla", "paskirtis": "skalbykla",
         "plotas_m2": 6.84, "perimetras_m": 10.5, "lubu_aukstis_m": 2.8,
         "plyteles_sienos_aukstis_m": 2.8,
         "sienu_apdailos_breakdown": {"dazymas_share": 0.3,
                                      "plyteles_share": 0.7},
         "_tile_area_from_elevation_m2": 0.0,
         "_tile_elevation_evidence": {
             "walls_matched": 1, "walls_measured": 1,
             "tile_zones_seen": 0, "tile_zones_measured": 0},
         "elementai": []}
    r.update(kw)
    return r


def test_absence_beats_apdailos_share():
    read = resolve_wall_tile_read(
        _skalbykla(), ROOM_TYPE_RULES.get("skalbykla", {}), 2.8, 29.4)
    assert read["source"] == "elevation"
    assert read["share"] == 0.0
    assert read["is_full_tile"] is False
    assert read["assumption"], "the user must be told why tile went to zero"


def test_without_the_absence_evidence_apdailos_still_wins():
    """Guard against over-reach: the ladder is unchanged for every room the
    išklotinė never covered."""
    room = _skalbykla()
    room.pop("_tile_elevation_evidence")
    read = resolve_wall_tile_read(
        room, ROOM_TYPE_RULES.get("skalbykla", {}), 2.8, 29.4)
    assert read["source"] == "apdailos"
    assert read["share"] == pytest.approx(0.7)


def test_room_quantities_bill_zero_wall_tile_and_keep_the_paint():
    """The billed consequence: 20.58 m² of tile disappears, and the wall does
    NOT silently become unpainted (the drawing colour-codes it as painted)."""
    with_evidence = calc_room_quantities(_skalbykla())
    room_no_ev = _skalbykla()
    room_no_ev.pop("_tile_elevation_evidence")
    without = calc_room_quantities(room_no_ev)

    assert without["plyteles_sienos_m2"] == pytest.approx(20.58, abs=0.01)
    assert with_evidence["plyteles_sienos_m2"] == pytest.approx(0.0, abs=0.01)
    assert with_evidence["walls_paintable_m2"] == pytest.approx(
        without["walls_paintable_m2"], abs=0.01), (
        "killing phantom tile must not move the paint area")


# ══════════════════════════════════════════════════════════════════════════
# 3. annotate_tile_elevation_evidence — derived from the saved elevations
# ══════════════════════════════════════════════════════════════════════════

def _parsed_with_elevations():
    return {
        "patalpos": [
            {"nr": "106", "pavadinimas": "Skalbykla"},
            {"nr": "102", "pavadinimas": "Svetainė/virtuvė"},
            {"nr": "107", "pavadinimas": "Vaikų san.mazgas"},
            {"nr": "108", "pavadinimas": "Berniuko kambarys"},
        ],
        "_wall_elevations": [
            # measured, no tile → absence
            {"nr": "106", "wall_id": "c", "wall_total_width_mm": 8775,
             "tile_zones": []},
            # tile zone present but unmeasurable → NOT absence
            {"nr": "102", "wall_id": "a6-a1", "wall_total_width_mm": None,
             "tile_zones": [{"from_floor_mm": 800, "to_floor_mm": 2300}]},
            # measured tile
            {"nr": "107", "wall_id": "d2", "wall_total_width_mm": 4870,
             "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 2800}]},
            # matched by name, not nr
            {"room_name": "Berniuko kambarys", "wall_id": "e1",
             "wall_total_width_mm": 1505, "tile_zones": []},
        ],
    }


def test_evidence_is_derived_per_room():
    parsed = _parsed_with_elevations()
    assert annotate_tile_elevation_evidence(parsed) == 4
    by_nr = {r["nr"]: r for r in parsed["patalpos"]}
    assert elevation_says_no_tile(by_nr["106"]) is True
    assert elevation_says_no_tile(by_nr["102"]) is False
    assert elevation_says_no_tile(by_nr["107"]) is False
    assert by_nr["107"]["_tile_elevation_evidence"]["tile_zones_measured"] == 1
    # name fallback still works when the name is unambiguous
    assert elevation_says_no_tile(by_nr["108"]) is True


def test_ambiguous_room_name_is_not_matched():
    """Two rooms called 'Berniuko kambarys' → a name-only elevation must not
    be applied to either (the pre-existing matching contract)."""
    parsed = _parsed_with_elevations()
    parsed["patalpos"].append({"nr": "109", "pavadinimas": "Berniuko kambarys"})
    annotate_tile_elevation_evidence(parsed)
    for r in parsed["patalpos"]:
        if r["nr"] in ("108", "109"):
            assert "_tile_elevation_evidence" not in r


def test_stale_evidence_is_cleared_when_the_room_no_longer_matches():
    parsed = _parsed_with_elevations()
    annotate_tile_elevation_evidence(parsed)
    renumbered = next(r for r in parsed["patalpos"] if r["nr"] == "106")
    renumbered["nr"] = "206"
    renumbered["pavadinimas"] = "Ūkinė"
    annotate_tile_elevation_evidence(parsed)
    assert "_tile_elevation_evidence" not in renumbered


def test_no_elevations_leaves_rooms_untouched():
    parsed = {"patalpos": [{"nr": "1", "_tile_elevation_evidence": {"x": 1}}]}
    assert annotate_tile_elevation_evidence(parsed) == 0
    assert parsed["patalpos"][0]["_tile_elevation_evidence"] == {"x": 1}


# ══════════════════════════════════════════════════════════════════════════
# 4. Diffuser legend anchor — nominative label vs oblique prose
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("text", [
    "Priglaistomas padavimo difuzorius",           # objektas_b legend
    "Priglaistomi apvalūs difuzoriai gipso kartono lubose",   # lazunu legend
    "Priglaistomas ištraukimo DIFUZORIUS",
    "priglaistomi difūzoriai",
])
def test_legend_labels_are_anchors(text):
    assert _DIFFUSER_LABEL_RE.search(text)


@pytest.mark.parametrize("text", [
    # berzas p7/p8 note 3 — the ONLY mention in that 17-page project
    "derinti kartu su interjero projektuotojais, dėl difuzorių vietos ir "
    "formos parinkimo, kolonėlių dydžio ir vietos bei estetinio vaizdo.",
    "Priglaistomo plyšinio difūzoriaus apdirbimas",
    "difuzoriams skirtos angos",
])
def test_oblique_prose_is_not_an_anchor(text):
    assert _DIFFUSER_LABEL_RE.search(text) is None


def test_anchor_check_defaults_to_trusting_the_count():
    """No scan / unreadable text layer / malformed record → unchanged
    behaviour. The gate may only ever downgrade, never invent."""
    assert diffuser_count_is_anchored({}) is True
    assert diffuser_count_is_anchored({"_symbol_legend": None}) is True
    assert diffuser_count_is_anchored(
        {"_symbol_legend": {"text_layer_ok": False,
                            "difuzoriai": {"defined": False}}}) is True
    assert diffuser_count_is_anchored(
        {"_symbol_legend": {"text_layer_ok": True}}) is True


def test_anchor_check_gates_only_a_readable_drawing_with_no_label():
    assert diffuser_count_is_anchored(
        {"_symbol_legend": {"text_layer_ok": True,
                            "difuzoriai": {"defined": False}}}) is False
    assert diffuser_count_is_anchored(
        {"_symbol_legend": {"text_layer_ok": True,
                            "difuzoriai": {"defined": True}}}) is True


# ══════════════════════════════════════════════════════════════════════════
# 5. The billed consequence in pozicijos[]
# ══════════════════════════════════════════════════════════════════════════

def _rooms():
    return [{"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
             "lubu_tipas": "gkp", "elementai": [], "confidence": "high"}]


def _parsed(symbols, legend=None):
    p = {"patalpos": _rooms(), "santrauka": {},
         "detected_symbols_summary": symbols}
    if legend is not None:
        p["_symbol_legend"] = legend
    return p


def _lines(out, needle):
    return [p for p in out.get("pozicijos", [])
            if needle.lower() in (p.get("aprasymas") or "").lower()]


NOT_DEFINED = {"text_layer_ok": True, "difuzoriai": {"defined": False}}
DEFINED = {"text_layer_ok": True, "difuzoriai": {"defined": True}}


def test_unanchored_count_becomes_a_checklist_row_that_names_the_number():
    out = _build_pozicijos_from_rooms(_parsed({"difuzoriai": 6}, NOT_DEFINED))
    billed = [p for p in _lines(out, "difūzor") if p.get("kiekis") is not None]
    assert billed == [], "an unanchored symbol count must not be billed"
    checklist = _lines(out, "difūzor")
    assert len(checklist) == 1
    row = checklist[0]
    assert row["kiekis"] is None
    assert row["saltinis"] == "checklist"
    # The discarded number is disclosed, not hidden (CLAUDE.md: show the
    # assumption), and so is where the real count lives.
    assert "6" in row["_assumption"]
    assert "vėdinimo" in row["_assumption"].lower()


def test_unanchored_count_does_not_fabricate_ductwork():
    out = _build_pozicijos_from_rooms(_parsed({"difuzoriai": 6}, NOT_DEFINED))
    assert [p for p in out["pozicijos"]
            if p.get("skyrius") == "Ventiliacijos darbai"] == []


def test_anchored_count_is_billed_as_before():
    out = _build_pozicijos_from_rooms(_parsed({"difuzoriai": 6}, DEFINED))
    montavimas = _lines(out, "Difūzorių montavimas (vėdinimo taškai)")
    apdirbimas = _lines(out, "Difūzorių apdirbimas")
    assert [p["kiekis"] for p in montavimas] == [6]
    assert [p["kiekis"] for p in apdirbimas] == [6]
    assert [p for p in out["pozicijos"]
            if p.get("skyrius") == "Ventiliacijos darbai"], (
        "the D125 fallback still runs for an anchored count")


def test_no_legend_scan_keeps_the_old_behaviour():
    out = _build_pozicijos_from_rooms(_parsed({"difuzoriai": 6}))
    assert [p["kiekis"] for p in _lines(out, "Difūzorių montavimas (vėdinimo")] == [6]


def test_zero_count_still_emits_the_generic_checklist_wording():
    out = _build_pozicijos_from_rooms(_parsed({"difuzoriai": 0}, NOT_DEFINED))
    row = _lines(out, "difūzor")[0]
    assert row["kiekis"] is None
    assert "Kiekis neaptiktas automatiškai" in row["_assumption"]


def test_duct_box_checklist_survives_the_phantom_being_killed():
    """Contractor line 12 (Dėžutės montavimas ortakiams, 1 vnt) was gated on
    ortakiai_total > 0, which on the reference project was only ever true
    because the phantom diffusers fed the D125 fallback. Killing the phantom
    must not kill a contractor line we do cover: an unanchored signal still
    justifies a QUESTION, just not a number."""
    parsed = _parsed({"difuzoriai": 6}, NOT_DEFINED)
    # The GKP checklist block's scope signal: this project has GKP ceilings.
    parsed["patalpos"][0]["gkp_lubu_standart_m2"] = 20.0
    out = _build_pozicijos_from_rooms(parsed)
    assert [p for p in out["pozicijos"]
            if p.get("skyrius") == "Ventiliacijos darbai"] == [], (
        "no billed ductwork may be derived from an unanchored count")
    rows = _lines(out, "Dėžutės montavimas ortakiams")
    assert len(rows) == 1
    assert rows[0]["kiekis"] is None
    assert rows[0]["saltinis"] == "checklist"


def test_duct_box_checklist_still_absent_with_no_ventilation_signal_at_all():
    """The other half of the same rule — the row is not unconditional."""
    parsed = _parsed({"sviestuvai": 12}, NOT_DEFINED)
    parsed["patalpos"][0]["gkp_lubu_standart_m2"] = 20.0
    out = _build_pozicijos_from_rooms(parsed)
    assert _lines(out, "Dėžutės montavimas ortakiams") == []

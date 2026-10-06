"""Wholly-unfinished rooms: the ceiling follows the walls (2026-07-29).

Measured on objektas_b (Rangovas B, pasiūlymas 2026-04-13). The 44 m² garage
came out of the engine with 0.00 m² of painted WALL — the paskirtis standard
says a garažas has no interior finish and the project supplied no apdailos
evidence — and 44.00 m² of painted CEILING. No estimator writes that split
down, and the contractor bills neither (the only garage ceiling work on the
pasiūlymas is item 3 "Laidų apsiuvimas garaže", 26.57 m² of wire boxing).

The 2026-05-27 Objektas A rule ("every ceiling type gets painted") stays intact for
every finished room — including Objektas A's OWN garage, which the contractor really
does paint (31.45 m² of wall paint) and which therefore keeps its ceiling. The
gate below only fires on a room the engine has already concluded is entirely
unfinished, and it DISCLOSES the withheld area instead of dropping it.
"""
from extractor.lt_rules import apply_lt_sanity
from extractor.universal_rules import calc_room_quantities

NOTE_MARK = "Lubos neįtrauktos į dažomą plotą"


def _garage(**kw):
    """objektas_b's garage, reduced to the primitives that drive the gate."""
    r = {"nr": "15", "pavadinimas": "Garažas", "paskirtis": "garazas",
         "plotas_m2": 44.0, "perimetras_m": 27.0, "lubu_aukstis_m": 2.82,
         "lubu_tipas": "betonas", "elementai": []}
    r.update(kw)
    return r


def _room(**kw):
    r = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.8,
         "elementai": []}
    r.update(kw)
    return r


# ── The gate fires ───────────────────────────────────────────────────────
def test_raw_garage_ceiling_not_painted():
    q = calc_room_quantities(_garage())
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["_ceiling_paint_source"] == "unfinished_room_standard"


def test_raw_garage_walls_and_ceiling_agree():
    """The whole point: one room, one verdict. 0 m² of wall + 44 m² of
    ceiling was the bug."""
    q = calc_room_quantities(_garage())
    assert q["walls_paintable_m2"] == 0.0
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["dazymo_plotas_m2"] == 0.0


def test_withheld_ceiling_is_disclosed_not_dropped():
    q = calc_room_quantities(_garage())
    notes = q["_ceiling_finish_assumptions"]
    assert len(notes) == 1
    assert NOTE_MARK in notes[0]
    # Names the paskirtis that drove it — by the label he sees, not the code —
    # and says where to check and what to correct (2026-10-06).
    assert "„Garažas“" in notes[0] and "garazas" not in notes[0]
    assert "lubų plane" in notes[0] and "sąmatoje" in notes[0]


def test_disclosure_surfaces_as_lt_sanity_warning():
    room = _garage()
    room.update(calc_room_quantities(room))
    out = apply_lt_sanity({"patalpos": [room]})
    hits = [w for w in out["_lt_warnings"] if NOTE_MARK in w["message"]]
    assert len(hits) == 1, out["_lt_warnings"]
    assert hits[0]["level"] == "WARN"
    assert hits[0]["patalpa_nr"] == "15"


def test_rule_is_not_garage_specific():
    """tamburas carries the same walls_paint=0 standard; a raw-slab tambūras
    gets the same verdict."""
    q = calc_room_quantities(_garage(
        nr="01", pavadinimas="Tambūras", paskirtis="tamburas", plotas_m2=7.36,
        perimetras_m=11.4))
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["_ceiling_paint_source"] == "unfinished_room_standard"


# ── The gate stays shut ──────────────────────────────────────────────────
def test_garage_with_apdailos_paint_keeps_its_ceiling():
    """Objektas A: Vision reads painted garage walls, contractor bills
    31.45 m² of them. Evidence beats the standard on BOTH surfaces."""
    q = calc_room_quantities(_garage(
        sienu_apdailos_breakdown={"dazymas_share": 1.0, "plyteles_share": 0.0}))
    assert q["walls_paintable_m2"] > 0
    assert q["ceiling_paintable_m2"] == 44.0
    assert q["_ceiling_paint_source"] == "standard"
    assert q["_ceiling_finish_assumptions"] == []


def test_garage_with_walls_paint_factor_override_keeps_its_ceiling():
    """Objektas A's GT garage carries walls_paint_factor_override=0.7988 (only 3 of
    4 walls finished). A human calibration must not silently cost the ceiling.
    This is the branch that protects `--use-gt-inputs` on objektas_a."""
    q = calc_room_quantities(_garage(walls_paint_factor_override=0.7988))
    assert q["ceiling_paintable_m2"] == 44.0
    assert q["_ceiling_paint_source"] == "standard"


def test_explicit_zero_wall_override_keeps_the_raw_ceiling_out():
    """walls_paint_factor_override=0.0 is his „Nedažomos" — what the Patikra
    question proposes for this very garage. It CONFIRMS the room is unfinished,
    so the gate stays open: until 2026-10-06 any override shut it and the
    confirmation put the 44 m² ceiling back into the paint lines. Only an
    override above 0 (the test above) says the room is finished. The note says
    it was his choice, not a missing finish on the drawing."""
    q = calc_room_quantities(_garage(walls_paint_factor_override=0.0))
    assert q["walls_paintable_m2"] == 0.0
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["_ceiling_paint_source"] == "unfinished_room_standard"
    notes = q["_ceiling_finish_assumptions"]
    assert len(notes) == 1 and NOTE_MARK in notes[0]
    assert "pažymėjote kaip nedažomas" in notes[0] and "apdailos nerasta" not in notes[0]


def test_explicit_zero_wall_override_does_not_strip_a_finished_rooms_ceiling():
    """The same „Nedažomos" in a living room under a read concrete slab: its
    room type is finished, so his word about the WALLS leaves the ceiling
    painted."""
    q = calc_room_quantities(_room(lubu_tipas="betonas", walls_paint_factor_override=0.0))
    assert q["walls_paintable_m2"] == 0.0
    assert q["ceiling_paintable_m2"] == 30.0
    assert q["_ceiling_paint_source"] == "standard"


def test_garage_with_gkp_soffit_keeps_its_ceiling():
    """gkp_extra_area_m2 = a drywall karobkė over ducting → part of the
    ceiling IS finished, so the room is not 'wholly unfinished'."""
    q = calc_room_quantities(_garage(gkp_extra_area_m2=10.05))
    assert q["ceiling_paintable_m2"] == 44.0
    assert q["_ceiling_paint_source"] == "standard"


def test_garage_with_gkp_ceiling_keeps_its_ceiling():
    q = calc_room_quantities(_garage(lubu_tipas="gkp"))
    assert q["ceiling_paintable_m2"] == 44.0
    assert q["gkp_lubu_standart_m2"] == 44.0
    assert q["_ceiling_paint_source"] == "standard"


def test_full_tile_bathroom_ceiling_still_painted():
    """A wet room tiled to the ceiling also lands on walls_paint_factor 0 —
    for a completely different reason. Its ceiling is painted."""
    q = calc_room_quantities(_room(
        nr="9", pavadinimas="Vonia", paskirtis="vonia", plotas_m2=6.83,
        perimetras_m=11.2, lubu_aukstis_m=2.8, plyteles_sienos_aukstis_m=2.8))
    assert q["_walls_full_tile"] is True
    assert q["_walls_paint_factor"] == 0.0
    assert q["ceiling_paintable_m2"] == 6.83
    assert q["_ceiling_paint_source"] == "standard"


def test_concrete_ceiling_in_a_finished_room_still_painted():
    """The 2026-05-27 rule is untouched where it was right: a raw slab over a
    living room is plastered and painted."""
    q = calc_room_quantities(_room(lubu_tipas="betonas"))
    assert q["ceiling_paintable_m2"] == 30.0
    assert q["_ceiling_paint_source"] == "standard"


# ── The user's escape hatch ──────────────────────────────────────────────
def test_ceiling_paint_override_true_beats_the_standard():
    q = calc_room_quantities(_garage(ceiling_paint_override=True))
    assert q["ceiling_paintable_m2"] == 44.0
    assert q["_ceiling_paint_source"] == "override_on"
    assert q["_ceiling_finish_assumptions"] == []


def test_ceiling_paint_override_false_beats_the_standard():
    q = calc_room_quantities(_room(ceiling_paint_override=False))
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["_ceiling_paint_source"] == "override_off"


def test_override_off_does_not_touch_gkp_install():
    """Withholding PAINT is not the same as withholding the drywall the
    painter doesn't install."""
    q = calc_room_quantities(_room(lubu_tipas="gkp", ceiling_paint_override=False))
    assert q["ceiling_paintable_m2"] == 0.0
    assert q["gkp_lubu_standart_m2"] == 30.0

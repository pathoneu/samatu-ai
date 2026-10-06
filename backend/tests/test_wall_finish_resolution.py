"""Wall-finish resolution — the 2026-07-28 paint-determinism defect.

DEFECT (reproduced from two runs of the byte-identical 17-page Objektas A
PDF, same model, same code): per-room `dazymo_plotas_m2` swung by up to 350%
between runs, in a patterned way — some rooms got exactly their FLOOR area
(ceiling only), but DIFFERENT rooms each time.

ROOT CAUSE: `calc_room_quantities` branched on the presence of
`sienu_apdailos_breakdown` — an OPTIONAL Vision field produced by a separate
API call (apdailos_reader) that can fail, return no JSON, or find no
išklotinių page. The `is_full_tile` rule (a floor-to-ceiling tiled wet room
has NO paintable wall) existed ONLY inside that branch:

    apdailos present → room 107 dazymo 8.59 m² (ceiling only)     ← correct
    apdailos absent  → room 107 dazymo 39.62 m², AND 34.72 m² of
                       tile billed on the SAME walls               ← double bill

and the same branch also decided `walls_paint_factor`, flipping
garažas / tambūras between "painted" and "ceiling only".

CONTRACTOR TRUTH (Rangovas A, docs/superpowers/fixtures/2026-05-26-objektas-a/
contractor-notes-verbatim.md): §Dažymai bills "sienos žemos 278.67 + sienos
aukštos 150.59 + garažo sienos 31.45" and lists rooms 107/111 ONLY under
§Plytelės (grindys, sienos, silikonavimas) — no paint line at all.

These tests pin the fix: the tile deduction is resolved ONCE, from whatever
evidence exists, and every branch consumes the same answer.
"""
import json
import re
from pathlib import Path

import pytest

from extractor.universal_rules import (
    ROOM_TYPE_RULES,
    calc_room_quantities,
    default_paint_prefs,
    is_full_tile_walls,
    resolve_wall_tile_read,
    translate_user_prefs_to_room_rules,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# One unsized door (the calc assumes one when a room says nothing) net of its
# painted jambs at the default 0,10 m wall — 1,38 m² (2026-09-15; was 1,125).
DOOR_NET = 0.9 * 2.1 - (0.9 + 2 * 2.1) * 0.10


def _room(**kw):
    """A Objektas A-shaped wet room: 8.59 m², 12.4 m perimeter, 2.8 m ceiling."""
    r = {"nr": "107", "pavadinimas": "Vaikų san. mazgas", "paskirtis": "san",
         "plotas_m2": 8.59, "perimetras_m": 12.4, "lubu_aukstis_m": 2.8,
         "elementai": []}
    r.update(kw)
    return r


# ══════════════════════════════════════════════════════════════════════════
# 1. A fully tiled wet room paints CEILING ONLY — with or without apdailos
# ══════════════════════════════════════════════════════════════════════════
FULL_TILE_APDAILOS = {"dazymas_share": 0.1, "plyteles_share": 0.9}


@pytest.mark.parametrize("apdailos", [None, FULL_TILE_APDAILOS],
                         ids=["apdailos_absent", "apdailos_present"])
def test_full_tile_wet_room_paints_ceiling_only(apdailos):
    kw = {"plyteles_sienos_aukstis_m": 2.8}   # tiled to the 2.8 m ceiling
    if apdailos:
        kw["sienu_apdailos_breakdown"] = apdailos
    q = calc_room_quantities(_room(**kw))

    assert q["walls_paintable_m2"] == 0.0, "tiled walls must not be painted"
    assert q["dazymo_plotas_m2"] == pytest.approx(q["ceiling_paintable_m2"])
    assert q["dazymo_plotas_m2"] == pytest.approx(8.59, abs=0.01), (
        "a fully tiled bathroom's paint area is its ceiling = its floor area")
    assert q["plyteles_sienos_m2"] > 25, "the tile itself is still billed"
    assert q["_walls_full_tile"] is True


def test_optional_vision_field_cannot_flip_the_double_billing_rule():
    """THE regression test. Dropping the optional apdailos read must not
    resurrect paint on floor-to-ceiling tiled walls."""
    kw = {"plyteles_sienos_aukstis_m": 2.8}
    with_read = calc_room_quantities(
        _room(sienu_apdailos_breakdown=FULL_TILE_APDAILOS, **kw))
    without_read = calc_room_quantities(_room(**kw))

    assert with_read["walls_paintable_m2"] == without_read["walls_paintable_m2"] == 0.0
    assert with_read["dazymo_plotas_m2"] == without_read["dazymo_plotas_m2"]
    # Pre-fix values, kept as documentation of what regressed:
    #   without_read["dazymo_plotas_m2"] was 39.62 (walls 31.03 + ceiling 8.59)
    assert without_read["dazymo_plotas_m2"] < 10.0


def test_partial_tile_band_still_gets_paint_above_it():
    """A 2.0 m band under a 2.8 m ceiling is NOT full tile: the strip above it
    is painted. 2026-09-05: the wall UNDER the band is tile, billed once as
    tile — it no longer also counts as glaistymas/dažymas (the first blind
    out-of-sample runs showed that double count to be the largest wall-paint
    error; see test_tile_band_paint.py)."""
    q = calc_room_quantities(_room(plyteles_sienos_aukstis_m=2.0))
    assert q["_walls_full_tile"] is False
    assert 0 < q["walls_paintable_m2"] < 25
    assert q["plyteles_sienos_m2"] == pytest.approx(12.4 * 2.0, abs=0.01)
    assert q["_tile_zone_deducted_m2"] > 0
    assert q["plyteles_sienos_m2"] + q["walls_paintable_m2"] <= q["walls_gross_m2"] + 0.01


# ══════════════════════════════════════════════════════════════════════════
# 2. A wet room whose tile read is MISSING does not silently paint everything
# ══════════════════════════════════════════════════════════════════════════
def test_missing_tile_read_is_disclosed_not_silent():
    """Documented behavior: with no project tile evidence we keep the
    room-type standard band (vonia/san = 2.0 m, walls above it painted) —
    but the room is flagged `_tile_read_missing` and carries an explicit LT
    assumption the UI must show. Silently painting every wall with no trace
    is what produced the demo defect."""
    q = calc_room_quantities(_room())      # no tile height, no apdailos

    assert q["_tile_read_source"] == "paskirtis_default"
    assert q["_tile_read_missing"] is True
    assert q["_wall_finish_assumptions"], "an assumption must be recorded"
    note = q["_wall_finish_assumptions"][0]
    # decimal comma, and it says where to check and what to correct (2026-10-06)
    assert "2,00 m" in note and "išklotinėse" in note and "sąmatoje" in note
    # and the assumed band is the documented room-type default, not a guess
    assert q["plyteles_sienos_m2"] == pytest.approx(
        12.4 * ROOM_TYPE_RULES["san"]["tile_walls_to_m"], abs=0.01)


def test_read_tile_height_is_not_flagged_as_an_assumption():
    """A band read off the drawing is a read: no assumption text. The band
    still leaves the paint base (2026-09-05) — that is explained by the
    ledger's per-room line, not by an „assumption" the room never made."""
    q = calc_room_quantities(_room(plyteles_sienos_aukstis_m=2.4))
    assert q["_tile_read_source"] == "vision_height"
    assert q["_tile_read_missing"] is False
    assert q["_wall_finish_assumptions"] == []
    assert q["_tile_zone_deducted_m2"] > 0


# ══════════════════════════════════════════════════════════════════════════
# 3. Garažas / tambūras follow ONE documented default
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("paskirtis", ["garazas", "tamburas"])
def test_no_finish_data_means_room_type_standard_and_says_so(paskirtis):
    """Standard (ROOM_TYPE_RULES, mirrored by the Setup Wizard default):
    garages and entry lobbies are NOT painted. With no project finish data we
    apply that standard — and disclose it, because Objektas A proves it can be
    wrong by 31.45 m²."""
    q = calc_room_quantities(_room(nr="105", pavadinimas="Garažas",
                                   paskirtis=paskirtis, plotas_m2=10.67,
                                   perimetras_m=13.6, lubu_aukstis_m=3.0))
    assert ROOM_TYPE_RULES[paskirtis]["walls_paint"] == 0.0
    assert q["walls_paintable_m2"] == 0.0
    assert q["dazymo_plotas_m2"] == pytest.approx(q["ceiling_paintable_m2"])
    assert any("neįtrauktos į dažomą plotą" in n
               for n in q["_wall_finish_assumptions"])


@pytest.mark.parametrize("paskirtis", ["garazas", "tamburas"])
def test_project_finish_data_overrides_the_standard_and_says_so(paskirtis):
    """PRECEDENCE: a confident apdailos read (project evidence) beats the
    room-type standard — Objektas A's contractor really does bill 31.45 m² of
    garage wall paint — but the user is told the standard was overridden."""
    q = calc_room_quantities(_room(
        nr="105", pavadinimas="Garažas", paskirtis=paskirtis,
        plotas_m2=10.67, perimetras_m=13.6, lubu_aukstis_m=3.0,
        sienu_apdailos_breakdown={"dazymas_share": 1.0}))
    assert q["walls_paintable_m2"] > 30
    assert any("apdailos duomenis" in n for n in q["_wall_finish_assumptions"])


def test_low_confidence_finish_guess_does_not_override_the_standard():
    """A self-reported guess ("spėjimas pagal paskirtį") must NOT paint a
    garage — pinned from the 2026-06-11 Rangovas B experiment."""
    q = calc_room_quantities(_room(
        nr="105", paskirtis="garazas", plotas_m2=10.67, perimetras_m=13.6,
        lubu_aukstis_m=3.0, sienu_apdailos_breakdown={"dazymas_share": 1.0},
        _apdailos_confidence="low"))
    assert q["walls_paintable_m2"] == 0.0


def test_user_pref_flips_the_default_through_one_translation_path():
    rules = translate_user_prefs_to_room_rules({"garazas_painted": True})
    q = calc_room_quantities(
        _room(nr="105", paskirtis="garazas", plotas_m2=10.67,
              perimetras_m=13.6, lubu_aukstis_m=3.0), rules=rules)
    assert q["walls_paintable_m2"] > 30


# ══════════════════════════════════════════════════════════════════════════
# 4. Elevation over-read is full-tile evidence, not a licence to invent paint
# ══════════════════════════════════════════════════════════════════════════
def test_elevation_overread_means_full_tile_not_proportional_paint():
    """Objektas A 107 in ground_truth/objektas_a/ai_extract.json: the elevation
    extractor read 46.32 m² of tile in a room with 30.80 m² of wall (it sums
    overlapping išklotinė strips). The old proportional clamp turned that
    overshoot into 10.32 m² of 'paint' on a bathroom the contractor never
    paints."""
    q = calc_room_quantities(_room(
        perimetras_m=11.0, plotas_m2=6.59, plyteles_sienos_aukstis_m=2.8,
        _tile_area_from_elevation_m2=46.32,
        sienu_apdailos_breakdown={"dazymas_share": 0.1, "plyteles_share": 0.9}))
    assert q["_tile_read_source"] == "elevation"
    assert q["_walls_full_tile"] is True
    assert q["walls_paintable_m2"] == 0.0
    # tile is billed on the whole wall net of the door opening (11.0 × 2.8
    # − the door's net deduction), NOT on the over-read 46.32 m².
    assert q["plyteles_sienos_m2"] == pytest.approx(11.0 * 2.8 - DOOR_NET, abs=0.01)


def test_elevation_partial_read_still_leaves_paint_above_the_tile():
    q = calc_room_quantities(_room(
        perimetras_m=11.0, plotas_m2=6.59, _tile_area_from_elevation_m2=12.0))
    assert q["_walls_full_tile"] is False
    assert q["walls_paintable_m2"] == pytest.approx(30.8 - DOOR_NET - 12.0, abs=0.01)


# ══════════════════════════════════════════════════════════════════════════
# 5. Determinism — identical inputs must give identical outputs
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("extra", [
    {},
    {"plyteles_sienos_aukstis_m": 2.8},
    {"sienu_apdailos_breakdown": FULL_TILE_APDAILOS},
    {"_tile_area_from_elevation_m2": 46.32},
])
def test_identical_inputs_identical_outputs(extra):
    runs = [calc_room_quantities(_room(**extra)) for _ in range(5)]
    first = json.dumps(runs[0], sort_keys=True, ensure_ascii=False)
    for r in runs[1:]:
        assert json.dumps(r, sort_keys=True, ensure_ascii=False) == first


def test_calc_does_not_mutate_its_input_room():
    room = _room(plyteles_sienos_aukstis_m=2.8)
    before = json.dumps(room, sort_keys=True, ensure_ascii=False)
    calc_room_quantities(room)
    assert json.dumps(room, sort_keys=True, ensure_ascii=False) == before


# ══════════════════════════════════════════════════════════════════════════
# 6. The helpers themselves
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("share,h,H,expected", [
    (0.9, 2.8, 2.8, True),     # dominant + to the ceiling
    (0.9, 2.0, 2.8, False),    # dominant but only a band
    (0.5, 2.8, 2.8, False),    # to the ceiling on half the perimeter
    (0.0, 0.0, 2.8, False),
    (1.0, 2.8, 0.0, False),    # no ceiling height → cannot conclude
])
def test_is_full_tile_walls(share, h, H, expected):
    assert is_full_tile_walls(share, h, H) is expected


def test_resolver_priority_elevation_beats_apdailos_beats_height():
    room = _room(plyteles_sienos_aukstis_m=2.0,
                 sienu_apdailos_breakdown={"plyteles_share": 0.4},
                 _tile_area_from_elevation_m2=5.0)
    assert resolve_wall_tile_read(room, ROOM_TYPE_RULES["san"], 2.8, 30.0)["source"] == "elevation"
    room.pop("_tile_area_from_elevation_m2")
    assert resolve_wall_tile_read(room, ROOM_TYPE_RULES["san"], 2.8, 30.0)["source"] == "apdailos"
    room.pop("sienu_apdailos_breakdown")
    assert resolve_wall_tile_read(room, ROOM_TYPE_RULES["san"], 2.8, 30.0)["source"] == "vision_height"
    room.pop("plyteles_sienos_aukstis_m")
    assert resolve_wall_tile_read(room, ROOM_TYPE_RULES["san"], 2.8, 30.0)["source"] == "paskirtis_default"


# ══════════════════════════════════════════════════════════════════════════
# 7. ONE source of truth for the paint defaults (backend ↔ frontend ↔ harness)
# ══════════════════════════════════════════════════════════════════════════
def test_default_paint_prefs_are_a_no_op_against_room_type_rules():
    """Passing the defaults must be indistinguishable from passing nothing —
    that is what makes it safe for the harness to send them (and what proves
    the harness and production measure the same configuration)."""
    translated = translate_user_prefs_to_room_rules(default_paint_prefs())
    for paskirtis, rule in ROOM_TYPE_RULES.items():
        if not isinstance(rule, dict):
            continue
        assert translated[paskirtis]["walls_paint"] == rule["walls_paint"], paskirtis
        assert translated[paskirtis]["tile_walls_to_m"] == rule["tile_walls_to_m"], paskirtis


def test_frontend_wizard_defaults_match_the_backend_defaults():
    """Pin frontend/src/components/project/SetupWizard.jsx DEFAULT_PREFS to
    `default_paint_prefs()`. The wizard's answers are posted verbatim as
    rules_override, so a drift here silently changes every user's paint total
    while the eval keeps scoring the backend defaults."""
    src = (REPO_ROOT / "frontend" / "src" / "components" / "project"
           / "SetupWizard.jsx").read_text(encoding="utf-8")
    block = src.split("export const DEFAULT_PREFS", 1)[1]
    backend = default_paint_prefs()
    for key, expected in backend.items():
        m = re.search(rf"^\s*{re.escape(key)}:\s*([^,\n]+)", block, re.M)
        assert m, f"{key} missing from SetupWizard DEFAULT_PREFS"
        raw = m.group(1).strip()
        actual = {"true": True, "false": False}.get(raw, None)
        if actual is None:
            actual = float(raw)
            assert actual == pytest.approx(float(expected)), key
        else:
            assert actual is bool(expected), key


# ══════════════════════════════════════════════════════════════════════════
# 8. The assumptions reach the user
# ══════════════════════════════════════════════════════════════════════════
def test_assumptions_surface_as_lt_warnings():
    from extractor.lt_rules import apply_lt_sanity
    room = _room()
    parsed = {"patalpos": [{**room, **calc_room_quantities(room)}]}
    out = apply_lt_sanity(parsed)
    msgs = [w["message"] for w in out["_lt_warnings"]]
    assert any("Plytelių aukštis brėžinyje nerastas" in m for m in msgs), msgs


def test_apdailos_reader_failure_is_persisted_as_a_warning():
    """The reader is a separate Vision call. When it fails, every room falls
    back to paskirtis standards — that swing used to leave NO trace in the
    saved blob (only a transient SSE event)."""
    from extractor.vision_call import _warn_apdailos_degraded
    parsed: dict = {}
    _warn_apdailos_degraded(parsed, "no JSON in response")
    assert parsed["warnings"][0]["level"] == "WARN"
    msg = parsed["warnings"][0]["message"]
    assert "Apdailos" in msg and "garažo" in msg
    # the reader's own failure text stays on the stored warning for diagnosis,
    # off the screen (2026-10-06)
    assert "no JSON in response" not in msg
    assert parsed["warnings"][0]["_reason"] == "no JSON in response"

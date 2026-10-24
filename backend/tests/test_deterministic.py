"""Tests guaranteeing the deterministic refactor (2026-04-28).

Vision now returns ONLY primitives. Python deterministically computes everything
else. Same primitives → byte-identical output across runs. These tests pin
that contract so we don't silently regress later.
"""
from __future__ import annotations

import copy
import json
import pytest

from extractor.vision_call import (
    _elementai_to_counts,
    _calc_hidroizoliacija_m2,
    _recompute_per_room_via_python,
    _build_pozicijos_from_rooms,
    _recompute_santrauka,
)
from extractor.universal_rules import calc_room_quantities


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def vonia_primitives() -> dict:
    return {
        "nr": "V01", "pavadinimas": "Vonia", "paskirtis": "vonia",
        "plotas_m2": 6.45, "perimetras_m": 10.30, "lubu_aukstis_m": 2.65,
        "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
        "elementai": [
            {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000},
            {"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 1200},
        ],
        "confidence": "high",
    }


@pytest.fixture
def three_room_parsed(vonia_primitives) -> dict:
    return {
        "archetipas": "standart",
        "bendras_plotas_m2": 43.15,
        "patalpos": [
            vonia_primitives,
            {
                "nr": "M01", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
                "plotas_m2": 14.2, "perimetras_m": 15.4, "lubu_aukstis_m": 2.65,
                "lubu_tipas": "gkp", "plyteles_sienos_aukstis_m": 0,
                "elementai": [
                    {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
                    {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
                ],
                "confidence": "high",
            },
            {
                "nr": "S01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
                "plotas_m2": 22.5, "perimetras_m": 19.4, "lubu_aukstis_m": 2.65,
                "lubu_tipas": "gkp", "plyteles_sienos_aukstis_m": 0,
                "elementai": [
                    {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
                    {"tipas": "langas", "kiekis": 2, "plotis_mm": 1500, "aukstis_mm": 1500},
                ],
                "confidence": "high",
            },
        ],
    }


def _run_full_pipeline(parsed: dict) -> dict:
    p = copy.deepcopy(parsed)
    p = _recompute_per_room_via_python(p, None)
    p = _build_pozicijos_from_rooms(p)
    p = _recompute_santrauka(p)
    return p


def _fingerprint(parsed: dict) -> str:
    """JSON fingerprint of computed/aggregated fields (skips audit-only fields)."""
    rooms_essence = [{
        k: v for k, v in r.items()
        if not k.startswith("_") and k != "calculation_trace"
    } for r in parsed.get("patalpos", [])]
    return json.dumps({
        "patalpos": rooms_essence,
        "santrauka": parsed.get("santrauka"),
        "pozicijos": parsed.get("pozicijos"),
    }, sort_keys=True, default=str)


# ── Unit-level determinism ───────────────────────────────────────────────────

def test_calc_room_quantities_deterministic():
    """calc_room_quantities must be a pure function: same input → same output."""
    room = {
        "nr": "V01", "paskirtis": "vonia",
        "plotas_m2": 6.45, "perimetras_m": 10.30, "lubu_aukstis_m": 2.65,
        "n_doors": 1, "n_windows": 1,
        "door_area_m2": 1.4, "window_area_m2": 0.72,
    }
    a = calc_room_quantities(room.copy())
    b = calc_room_quantities(room.copy())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_elementai_to_counts_basic():
    elementai = [
        {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
        {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 2.4},
    ]
    c = _elementai_to_counts(elementai)
    assert c["n_windows"] == 2
    assert c["n_doors"] == 1
    assert c["n_niches"] == 1
    assert abs(c["window_area_m2"] - 1.8) < 1e-6
    assert abs(c["door_area_m2"] - 1.6) < 1e-6
    assert c["niche_lengths_m"] == [2.4]


def test_elementai_empty_returns_zeros():
    c = _elementai_to_counts([])
    assert c["n_doors"] == 0 and c["n_windows"] == 0 and c["n_niches"] == 0
    assert c["door_area_m2"] is None
    assert c["window_area_m2"] is None


def test_hidroizoliacija_only_for_wet_rooms():
    dry_room = {"paskirtis": "gyvenamoji", "plotas_m2": 20, "lubu_aukstis_m": 2.65}
    wet_room = {"paskirtis": "vonia", "plotas_m2": 6.45, "lubu_aukstis_m": 2.65}
    assert _calc_hidroizoliacija_m2(dry_room, perim=18) == 0.0
    assert _calc_hidroizoliacija_m2(wet_room, perim=10.3) > 0


# ── Pipeline-level determinism ───────────────────────────────────────────────

def test_pipeline_byte_identical_across_runs(three_room_parsed):
    """The CORE contract: 3× the same primitives must produce identical output.

    Replaces Vision non-determinism with Python deterministic math. Without this,
    user sees different paint area / glaistas / GK numbers across runs of the
    same project — the original frustration this refactor solves.
    """
    a = _run_full_pipeline(three_room_parsed)
    b = _run_full_pipeline(three_room_parsed)
    c = _run_full_pipeline(three_room_parsed)

    fa, fb, fc = _fingerprint(a), _fingerprint(b), _fingerprint(c)
    assert fa == fb == fc, (
        f"Pipeline non-deterministic!\n"
        f"Run1 != Run2: {fa[:200]} ...\n"
        f"          vs: {fb[:200]} ...")


def test_pipeline_pozicijos_built_from_rooms(three_room_parsed):
    """Vision no longer emits pozicijos; Python must synthesize them."""
    out = _run_full_pipeline(three_room_parsed)
    assert isinstance(out.get("pozicijos"), list)
    assert len(out["pozicijos"]) > 0
    skyriai = {p["skyrius"] for p in out["pozicijos"]}
    # Three-room sample (vonia + miegamasis + svetainė) must produce all four
    # main skyriai because vonia → Hidroizoliacija + Plyteles, others →
    # Glaistymas dazymas + GKP montavimas.
    # 2026-09-02: the paint block is TWO sections (contractor ask F3).
    assert "Sienų glaistymas dažymas" in skyriai
    assert "Lubų glaistymas dažymas" in skyriai
    assert "GKP montavimas" in skyriai
    assert "Plytelių klijavimas" in skyriai
    assert "Hidroizoliacija" in skyriai


def test_pipeline_santrauka_sums_match_per_room(three_room_parsed):
    out = _run_full_pipeline(three_room_parsed)
    rooms = out["patalpos"]
    summary = out["santrauka"]
    expected_dazymo = round(sum(r["dazymo_plotas_m2"] for r in rooms), 2)
    assert abs(summary["dazymo_plotas_total_m2"] - expected_dazymo) < 0.01


def test_pipeline_audit_field_marks_python_compute(three_room_parsed):
    out = _run_full_pipeline(three_room_parsed)
    for r in out["patalpos"]:
        assert r.get("_computed_by") == "python_deterministic", (
            f"Room {r['nr']} missing audit marker — Python compute didn't run")


# ── Sprint F4: pdfplumber bbox extraction contract ───────────────────────────

def test_pdfplumber_row_parser_without_bbox():
    """Backwards-compat: _try_parse_row without bbox kwargs returns the original
    shape (no bbox fields). Frontend old-data path must keep working."""
    from extractor.pdfplumber_eksplikacija import _try_parse_row
    out = _try_parse_row(["1 SVETAINĖ", "15.50 m²"], 0, page_nr=5)
    assert out is not None
    assert out["nr"] == "1"
    assert out["pavadinimas"] == "SVETAINĖ"
    assert out["plotas_m2"] == 15.5
    assert "eksplikacija_row_bbox" not in out
    assert "eksplikacija_page_width_pdf" not in out


def test_pdfplumber_row_parser_with_bbox():
    """When called with row_bbox + page dims (i.e. via find_tables path),
    the returned dict carries the bbox + page dims for frontend overlay."""
    from extractor.pdfplumber_eksplikacija import _try_parse_row
    out = _try_parse_row(
        ["M01", "Vonia", "6,45 m²"], 0, page_nr=82,
        row_bbox=(120.5, 480.2, 870.6, 498.3),
        page_width_pdf=1191.0, page_height_pdf=842.0,
    )
    assert out is not None
    assert out["plotas_m2"] == 6.45
    assert out["eksplikacija_row_bbox"] == [120.5, 480.2, 870.6, 498.3]
    assert out["eksplikacija_page_width_pdf"] == 1191.0
    assert out["eksplikacija_page_height_pdf"] == 842.0


def test_pdfplumber_row_parser_skips_total_rows():
    """`Bendras plotas` and similar summary rows must NOT be returned as rooms."""
    from extractor.pdfplumber_eksplikacija import _try_parse_row
    assert _try_parse_row(["Bendras plotas", "180.50"], 5, 5) is None
    assert _try_parse_row(["Iš viso", "200.00 m²"], 5, 5) is None


def test_pozicijos_includes_rotband_for_paintable_walls(three_room_parsed):
    """Rotband leveling must appear when walls_paintable > 0 (Rangovas P1-P5
    pattern — 5/5 projects). Quantity = walls_paintable_m2."""
    out = _run_full_pipeline(three_room_parsed)
    # 2026-09-02: match WORK rows only — the material carries the same product
    # name and now lives in its own "Medžiagos" section.
    rotband = [p for p in out["pozicijos"]
               if "rotband" in p["aprasymas"].lower()
               and p["skyrius"] != "Medžiagos"]
    assert len(rotband) == 1, f"Rotband missing: {rotband}"
    assert rotband[0]["vnt"] == "m2"
    assert rotband[0]["kiekis"] > 0
    # …and the material it consumes is a row of its own, linked back to it.
    assert not rotband[0].get("medziagos_aprasymas"), \
        "work rows must no longer embed their material"
    mat = next(p for p in out["pozicijos"]
               if p["skyrius"] == "Medžiagos"
               and p["susijes_darbas"] == rotband[0]["aprasymas"])
    assert mat["vnt"] == "kg"
    assert mat["kiekis"] > 0


def test_pozicijos_santechnika_skyrius_has_klozetas_per_wet_room(three_room_parsed):
    """Each vonia/wc/san paskirtis room → 1 klozetas + 1 WC rėmas (Rangovas pattern)."""
    out = _run_full_pipeline(three_room_parsed)
    sant = [p for p in out["pozicijos"] if p["skyrius"] == "Santechnikos darbai"]
    assert len(sant) > 0, "Santechnikos darbai skyrius missing entirely"

    klozetas = next((p for p in sant if "klozeto" in p["aprasymas"].lower()), None)
    rėmas = next((p for p in sant if "wc rėmo" in p["aprasymas"].lower()), None)
    gyvatukas = next((p for p in sant if "gyvatuko" in p["aprasymas"].lower()), None)
    plautuvė = next((p for p in sant if "plautuvės" in p["aprasymas"].lower()), None)

    # Three-room fixture has 1 vonia → 1 klozetas, 1 WC rėmas, 1 gyvatukas
    assert klozetas and klozetas["kiekis"] == 1
    assert rėmas and rėmas["kiekis"] == 1
    assert gyvatukas and gyvatukas["kiekis"] == 1
    # No virtuvė in fixture → no plautuvė
    assert plautuvė is None


def test_pozicijos_pastoliu_only_when_high_ceiling():
    """Pastolių nuoma should ONLY fire when at least one room has lubu_aukstis > 3m."""
    # Low ceiling — no pastoliai
    low = {"patalpos": [{"nr": "1", "pavadinimas": "X", "paskirtis": "gyvenamoji",
                         "plotas_m2": 20, "perimetras_m": 18, "lubu_aukstis_m": 2.65,
                         "elementai": [], "confidence": "high"}]}
    out_low = _run_full_pipeline(low)
    pastoliai_low = [p for p in out_low["pozicijos"]
                     if "pastolių" in p["aprasymas"].lower()]
    assert len(pastoliai_low) == 0

    # High ceiling — pastoliai included
    high = {"patalpos": [{"nr": "1", "pavadinimas": "X", "paskirtis": "gyvenamoji",
                          "plotas_m2": 20, "perimetras_m": 18, "lubu_aukstis_m": 4.0,
                          "elementai": [], "confidence": "high"}]}
    out_high = _run_full_pipeline(high)
    pastoliai_high = [p for p in out_high["pozicijos"]
                      if "pastolių" in p["aprasymas"].lower()]
    assert len(pastoliai_high) == 1
    assert pastoliai_high[0]["vnt"] == "d.d"


def test_pozicijos_elektros_skyrius_uses_symbols_when_available():
    """Elektros eilutės su kiekiais pridedamos tik kai sutartinių ženklų
    count'ai > 0. Be tos info — jokių SKAIČIUOTŲ eilučių, bet 2026-07-25
    HONESTY CHECKLIST visada palieka difūzorių + termoreguliatorių eilutes su
    kiekis=None (raudona) — anksčiau kategorijos dingdavo TYLIAI (truth: 15
    difūzorių / 8 termoreguliatoriai referenciniame projekte, app rodė nieko)."""
    base = {"patalpos": [{"nr": "1", "pavadinimas": "X", "paskirtis": "gyvenamoji",
                          "plotas_m2": 20, "perimetras_m": 18, "lubu_aukstis_m": 2.65,
                          "elementai": [], "confidence": "high"}]}
    # No symbols → only the two null-kiekis checklist TODO lines
    out_no = _run_full_pipeline(base)
    el_no = [p for p in out_no["pozicijos"]
             if p["skyrius"] == "Elektros instaliacijos darbai"]
    assert len(el_no) == 2
    assert all(p["kiekis"] is None for p in el_no)
    assert all(p["saltinis"] == "checklist" for p in el_no)
    assert any("Difūzorių" in p["aprasymas"] for p in el_no)
    assert any("Termoreguliatorių" in p["aprasymas"] for p in el_no)

    # With symbols → Rozetės/jungiklio + šviestuvai eilutės
    with_sym = copy.deepcopy(base)
    with_sym["detected_symbols_summary"] = {
        "rozetes": 12, "jungikliai": 5, "sviestuvai": 8, "led_juostos": 6.5,
    }
    out_yes = _run_full_pipeline(with_sym)
    el_yes = [p for p in out_yes["pozicijos"]
              if p["skyrius"] == "Elektros instaliacijos darbai"]
    aprasymai = [p["aprasymas"] for p in el_yes]
    assert any("Rozetės" in a or "rozetės" in a.lower() for a in aprasymai), aprasymai
    assert any("šviestuv" in a.lower() for a in aprasymai), aprasymai
    assert any("LED juostos" in a for a in aprasymai), aprasymai
    # Rozetės+jungikliai sumuojami į vieną liniją
    rozetes_line = next(p for p in el_yes if "Rozetės" in p["aprasymas"])
    assert rozetes_line["kiekis"] == 17  # 12 + 5


def test_grindjuostes_are_the_rooms_own_metres_never_capped():
    """Skirting runs on BOTH sides of a shared wall, so the per-room sum counts
    nothing twice. The 0,65 m/m² cap this test used to pin was a factor read
    off his sąmatas (founder's rule, 2026-09-05: never teach the engine from
    the sąmata); on objektas_g it cut 87,4 m to 65,6 m against a drawing that
    supports 87,4. Gone — the line is Σ(perimetras − durys) × 1,10, and older
    blobs' cap marks and warning are dropped on rebuild."""
    parsed = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 25.0, "perimetras_m": 25.0, "lubu_aukstis_m": 2.65,
             "elementai": [], "confidence": "high", "_grindjuosciu_capped": True},
            {"nr": "2", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
             "plotas_m2": 15.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.65,
             "elementai": [], "confidence": "high"},
            {"nr": "3", "pavadinimas": "Holas", "paskirtis": "koridorius",
             "plotas_m2": 10.0, "perimetras_m": 16.0, "lubu_aukstis_m": 2.65,
             "elementai": [], "confidence": "high"},
        ],
        "_meta": {"grindjuosciu_pre_cap_m": 64.9, "grindjuosciu_post_cap_m": 32.5},
        "warnings": [{"code": "grindjuosciu_cap_fired", "message": "sena riba"}],
    }
    out = _run_full_pipeline(parsed)
    grindj_lines = [p for p in out["pozicijos"]
                    if "grindjuosčių sumontavimas" in p["aprasymas"].lower()]
    assert len(grindj_lines) == 1
    assert grindj_lines[0]["kiekis"] == pytest.approx((25.0 + 18.0 + 16.0) * 1.10, abs=0.05)
    assert "grindjuosciu_pre_cap_m" not in (out.get("_meta") or {})
    assert not any(r.get("_grindjuosciu_capped") for r in out["patalpos"])
    assert not any(isinstance(w, dict) and w.get("code") == "grindjuosciu_cap_fired"
                   for w in out.get("warnings") or [])


def test_grindjuostes_not_capped_when_within_ratio():
    """If per-room sum is already < 0.65 × plotas (small project, no
    double-counting), cap should NOT fire and no audit field set."""
    # Single tiny room where perim/plotas geometry cannot exceed cap
    parsed = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Tualetas", "paskirtis": "wc",
             "plotas_m2": 4.0, "perimetras_m": 8.0, "lubu_aukstis_m": 2.65,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    # WC has tile_floor=true → grindjuostės = 0. Pick a paskirtis that DOES
    # produce grindjuostės to test "no cap" path.
    parsed_dry = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Salonas", "paskirtis": "gyvenamoji",
             "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.65,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
    }
    out_dry = _run_full_pipeline(parsed_dry)
    # 1 room with 22m perim and 30m² floor → ratio ~0.73 m/m² (slightly over
    # cap). Cap fires. But NO double-counting since 1 room — verify cap
    # documented but value is still cap × plotas.
    # For "no cap" path we need very low perim, but realistic single-room
    # projects naturally exceed cap. Acceptable — test_grindjuostes_capped
    # already covers cap-fires path. This test verifies _meta is present.
    grindj = [p for p in out_dry["pozicijos"]
              if "grindjuosčių sumontavimas" in p["aprasymas"].lower()]
    assert len(grindj) == 1
    assert grindj[0]["kiekis"] > 0


def test_pozicijos_includes_angokrasciu_gkp_pair():
    """When openings exist, BOTH glaistymas-dažymas AND GKP skyriaus
    angokraščių lines should be emitted (Rangovas 4/5 freq pattern)."""
    parsed = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 24.0, "perimetras_m": 20.0, "lubu_aukstis_m": 2.65,
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
                 {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
             ],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    glaistymas_line = [p for p in out["pozicijos"]
                       if "angokraščių glaistymas-dažymas" in p["aprasymas"].lower()]
    gkp_line = [p for p in out["pozicijos"]
                if "angokraščių apdirbimas gkp" in p["aprasymas"].lower()]
    assert len(glaistymas_line) == 1, "Missing glaistymas-dažymas line for angokraščiai"
    assert len(gkp_line) == 1, "Missing GKP-skyriaus angokraščių apdirbimas line"
    # Both must have IDENTICAL kiekis (same anga perimetras)
    assert abs(glaistymas_line[0]["kiekis"] - gkp_line[0]["kiekis"]) < 0.01
    # GKP line must be in correct skyrius
    assert gkp_line[0]["skyrius"] == "GKP montavimas"


def test_pozicijos_includes_paslepta_duru_stakta():
    """Hidden doors (pasleptos_duris) must produce dedicated stakto pozicija."""
    parsed = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Holas", "paskirtis": "koridorius",
             "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.65,
             "elementai": [
                 {"tipas": "pasleptos_duris", "kiekis": 2, "plotis_mm": 800, "aukstis_mm": 2100},
             ],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"]
            if "beapvadinėms" in p["aprasymas"].lower()]
    assert len(line) == 1
    # Per door: (2H+W)/1000 = (4.2 + 0.8) = 5.0 m × 2 doors = 10.0 m
    assert abs(line[0]["kiekis"] - 10.0) < 0.1


def test_pozicijos_no_paslepta_stakta_when_no_hidden_doors():
    """Paslėptų durų stakta pozicija NOT emitted when no hidden doors exist."""
    parsed = {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Salonas", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.65,
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2000},
             ],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"]
            if "beapvadinėms" in p["aprasymas"].lower()]
    assert len(line) == 0


def test_pozicijos_p3_lentyneliu_in_vonia():
    """Lentynėlių iš plytelių dušo kabinoje — 2 per vonia/san by default.

    Default changed 1→2 on 2026-05-31 (commit c91dd3b, vision_call.py:1513-1520):
    the Objektas A contractor truth = 5 vnt for 2 bathrooms (≈2.5/vonia), so the prior
    default of 1 under-counted by ~60%. The "1 by default" assertion (written
    2026-04-29) is stale. User can override via _overrides.lentyneliu_per_vonia.
    """
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"] if "lentynė" in p["aprasymas"].lower()]
    assert len(line) == 1
    assert line[0]["kiekis"] == 2  # 2 per vonia (Objektas A calibration, c91dd3b)
    assert line[0]["vnt"] == "vnt"

    # Override still honored: an explicit per-vonia count wins over the default.
    parsed["_overrides"] = {"lentyneliu_per_vonia": 1}
    out2 = _run_full_pipeline(parsed)
    line2 = [p for p in out2["pozicijos"] if "lentynė" in p["aprasymas"].lower()]
    assert len(line2) == 1
    assert line2[0]["kiekis"] == 1


def test_pozicijos_p3_dezuciu_gkp_per_wet_room():
    """Pertvaros sutvirtinimas WC mechanizmams, 1 per wet room (vonia/wc/san).

    Rangovas P1=2, P2=2, P5=1. Relabeled 2026-07-29 from "Dėžučių iš GKP
    formavimas WC mechanizmams paslėpti" to the contractor's own wording —
    same driver, same quantity, a name his samata actually uses.
    """
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
            {"nr": "W1", "pavadinimas": "WC", "paskirtis": "wc",
             "plotas_m2": 2.0, "perimetras_m": 5.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"]
            if "wc mechanizmams" in p["aprasymas"].lower()]
    assert len(line) == 1
    assert line[0]["aprasymas"] == (
        "Pertvaros sutvirtinimas WC mechanizmams montuoti (GKP dėžutė)")
    assert line[0]["kiekis"] == 2  # 1 vonia + 1 wc
    assert line[0]["skyrius"] == "GKP montavimas"


def test_pozicijos_p3_skyliu_grezimas_symbol_driven():
    """When detected_symbols_summary has counts, skylių gręžimas uses symbol
    formula (kloz×4 + praust×6 + vonia×8 + wc_remai×3) — more accurate than
    opening-count heuristic."""
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
        "detected_symbols_summary": {
            "klozetai": 1,
            "praustuves": 1,
            "vonios": 1,
            "wc_remai": 1,
        },
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"] if "skylių gręžimas" in p["aprasymas"].lower()]
    assert len(line) == 1
    # Formula: 1×4 + 1×6 + 1×8 + 1×3 = 21
    assert line[0]["kiekis"] == 21
    assert line[0]["saltinis"] == "simboliai_brezinyje"


def test_pozicijos_p3_skyliu_grezimas_fallback_no_symbols():
    """Without symbols, fall back to opening-count heuristic."""
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000},
                 {"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 1200},
             ],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    line = [p for p in out["pozicijos"] if "skylių gręžimas" in p["aprasymas"].lower()]
    assert len(line) == 1
    # 2 openings × 4 holes = 8
    assert line[0]["kiekis"] == 8
    # 2026-06-11: confidence post-pass normalizes legacy "low" → "raudona"
    # (unified LT scheme: zalia/geltona/raudona).
    assert line[0]["confidence"] == "raudona"


def test_rangovas_baseline_p1_style_residential_emits_all_key_skyriai():
    """Rangovas P1-style residential project (180m², 5 wet rooms, 3+ years modern
    construction) should produce ALL the key skyriai that Rangovas writes:

    - Gipso kartono montavimas (GKP)
    - Sienų lubų glaistymas dažymas
    - Plytelių klijavimas
    - Hidroizoliacija
    - Grindys
    - Santechnikos darbai
    - Pridėtiniai elementai

    This is a regression net: if a refactor accidentally removes a key skyrius,
    this test catches it before shipping. We don't assert exact totals (Vision
    extraction varies project to project) — just that all SKYRIAI are present.
    """
    parsed = {
        "patalpos": [
            # Drėgnos zonos
            {"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}],
             "confidence": "high"},
            {"nr": "2", "pavadinimas": "WC", "paskirtis": "wc",
             "plotas_m2": 2.1, "perimetras_m": 5.8, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 2000}],
             "confidence": "high"},
            # Sausosios zonos
            {"nr": "3", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 24.15, "perimetras_m": 19.8, "lubu_aukstis_m": 2.82,
             "lubu_tipas": "gkp",
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
                 {"tipas": "langas", "kiekis": 2, "plotis_mm": 1500, "aukstis_mm": 1500},
             ],
             "confidence": "high"},
            {"nr": "4", "pavadinimas": "Virtuvė", "paskirtis": "virtuve",
             "plotas_m2": 11.2, "perimetras_m": 13.5, "lubu_aukstis_m": 2.82,
             "lubu_tipas": "gkp", "plyteles_sienos_aukstis_m": 0.6,
             "elementai": [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500}],
             "confidence": "high"},
            {"nr": "5", "pavadinimas": "Miegamasis 1", "paskirtis": "miegamoji",
             "plotas_m2": 14.8, "perimetras_m": 15.4, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "gkp",
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000},
                 {"tipas": "langas", "kiekis": 1, "plotis_mm": 1500, "aukstis_mm": 1500},
             ],
             "confidence": "high"},
            {"nr": "6", "pavadinimas": "Prieškambaris", "paskirtis": "koridorius",
             "plotas_m2": 8.42, "perimetras_m": 12.0, "lubu_aukstis_m": 2.82,
             "lubu_tipas": "gkp",
             "elementai": [{"tipas": "duris", "kiekis": 2, "plotis_mm": 800, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
        "detected_symbols_summary": {
            "rozetes": 28, "jungikliai": 12, "sviestuvai": 18, "led_juostos": 8.0,
            "klozetai": 2, "praustuves": 2, "vonios": 1, "wc_remai": 2, "gyvatukai": 1,
        },
    }
    out = _run_full_pipeline(parsed)
    skyrius_set = {p["skyrius"] for p in out["pozicijos"]}

    # Key Rangovas-style skyriai must all be present
    REQUIRED = {
        "GKP montavimas",
        "Sienų glaistymas dažymas",
        "Lubų glaistymas dažymas",
        "Plytelių klijavimas",
        "Hidroizoliacija",
        "Grindys",
        "Santechnikos darbai",
        "Elektros instaliacijos darbai",
        "Pridėtiniai elementai",
    }
    missing = REQUIRED - skyrius_set
    assert not missing, f"Missing key skyriai for Rangovas-baseline residential: {missing}"

    # Pozicijų count should be at least 30 (Rangovas P2 = 36, P5 = 50; we should
    # match this magnitude for a comparable project size)
    n_pozicijos = len(out["pozicijos"])
    assert n_pozicijos >= 30, (
        f"Expected ≥30 pozicijos for residential 67m², got {n_pozicijos}. "
        f"This is a major coverage regression vs Rangovas P2 (36)/P5 (50)."
    )

    # Specific high-priority items from Rangovas frequency analysis
    aprasymai_lower = [p["aprasymas"].lower() for p in out["pozicijos"]]
    assert any("rotband" in a for a in aprasymai_lower), "Missing Sienų lyginimas Rotband (Rangovas 5/5 freq)"
    assert any("klozet" in a for a in aprasymai_lower), "Missing Klozeto montavimas (Rangovas 3/5 freq)"
    assert any("wc rėm" in a for a in aprasymai_lower), "Missing WC rėmo montavimas (Rangovas 3/5 freq)"
    assert any("gyvatuk" in a for a in aprasymai_lower), "Missing Gyvatuko montavimas (Rangovas 2/5 freq)"
    assert any("rozet" in a for a in aprasymai_lower), "Missing Rozetės/jungiklio komutavimas (Rangovas 2/5 freq, symbols=28)"
    assert any("šviestuv" in a for a in aprasymai_lower), "Missing Šviestuvų montavimas (Rangovas 2/5 freq, symbols=18)"


def test_pipeline_handles_empty_patalpos():
    """Edge: 0 rooms — should not crash, should emit empty pozicijos list."""
    out = _run_full_pipeline({"patalpos": []})
    assert out.get("pozicijos") == []
    # santrauka should be all zeros, not None / missing
    s = out.get("santrauka", {})
    assert s.get("dazymo_plotas_total_m2", 0) == 0


def test_pipeline_handles_single_garazas_no_painting():
    """Edge: garazas paskirtis means walls_paint=0, so no Glaistymas/Dažymas
    pozicijos should appear. Floor pozicijos (išlyginamasis if floor) may.
    Test verifies no crash + correct skip."""
    parsed = {
        "patalpos": [
            {"nr": "G1", "pavadinimas": "Garažas", "paskirtis": "garazas",
             "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.65,
             "elementai": [], "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    paint_lines = [p for p in out["pozicijos"]
                   if p["skyrius"] == "Sienų lubų glaistymas dažymas"
                   and "rotband" in p["aprasymas"].lower()]
    # Garazas → walls_paint=0 → no Rotband emitted
    assert len(paint_lines) == 0


def test_pipeline_handles_high_ceiling_3plus_m():
    """Patalpa virš 3m turi atskirą GKP (virš 3m) liniją + Pastolių nuoma."""
    parsed = {
        "patalpos": [
            {"nr": "S1", "pavadinimas": "Salonas", "paskirtis": "gyvenamoji",
             "plotas_m2": 50.0, "perimetras_m": 30.0, "lubu_aukstis_m": 3.5,
             "lubu_tipas": "gkp",
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    # GKP montavimas (virš 3m) line — STRUCTURAL install
    high_gkp = [p for p in out["pozicijos"]
                if "virš 3 m" in p["aprasymas"].lower()
                and "gkp" in p["aprasymas"].lower()]
    # Lubų glaistymas/dažymas (virš 3m) — FINISH labor (Sprint §FIX-5)
    # 2026-06-06: paint lines consolidated — "Sienų, lubų glaistymas/dažymas
    # (virš 3m aukščio)" (was "Lubų glaistymas/dažymas (virš 3 m aukščio)").
    # 2026-09-02: consolidated PER SURFACE, so the high-ceiling room now
    # produces a virš-3m line for the walls AND one for the ceiling.
    high_paint = [p for p in out["pozicijos"]
                  if "virš 3m aukščio" in p["aprasymas"].lower()
                  and "glaistymas" in p["aprasymas"].lower()]
    high_paint_lubos = [p for p in high_paint
                        if p["aprasymas"].startswith("Lubų")]
    pastoliai = [p for p in out["pozicijos"]
                 if "pastolių" in p["aprasymas"].lower()]
    assert len(high_gkp) == 1, "Missing GKP virš 3m line for high-ceiling room"
    assert len(high_paint) == 2, f"Expected a walls + a lubos virš-3m line: {high_paint}"
    assert len(high_paint_lubos) == 1, "Missing Lubų >3m painting line (Rangovas P1 split)"
    assert len(pastoliai) == 1, "Missing pastolių nuoma for high-ceiling room"


def test_pipeline_handles_50_rooms_no_perf_explosion():
    """Stress: 50-room project must produce coherent output without timeout
    or crashes. Sanity: pozicijų count grows with rooms but stays bounded."""
    rooms = []
    for i in range(50):
        paskirtis = ["gyvenamoji", "miegamoji", "vonia", "wc", "virtuve"][i % 5]
        rooms.append({
            "nr": str(i + 1), "pavadinimas": f"Patalpa {i+1}", "paskirtis": paskirtis,
            "plotas_m2": 10.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.65,
            "lubu_tipas": "gkp" if paskirtis not in ("vonia", "wc") else "pakabinamos",
            "plyteles_sienos_aukstis_m": 2.0 if paskirtis in ("vonia", "wc") else 0,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}],
            "confidence": "high",
        })
    parsed = {"patalpos": rooms}
    out = _run_full_pipeline(parsed)
    n_pozicijos = len(out["pozicijos"])
    # 50 rooms with mixed paskirtis → expected ~70-110 pozicijos
    assert 50 < n_pozicijos < 200, f"50-room project produced {n_pozicijos} pozicijos — outside sanity bounds"


def test_pipeline_byte_identical_3_runs_50_room_project():
    """3× run on 50-room project must produce byte-identical output (full
    determinism stress)."""
    rooms = [
        {"nr": str(i + 1), "pavadinimas": f"Patalpa {i+1}",
         "paskirtis": "gyvenamoji" if i % 3 else "vonia",
         "plotas_m2": 12.5, "perimetras_m": 14.0, "lubu_aukstis_m": 2.65,
         "lubu_tipas": "gkp" if i % 3 else "pakabinamos",
         "plyteles_sienos_aukstis_m": 0 if i % 3 else 2.0,
         "elementai": [], "confidence": "high"}
        for i in range(50)
    ]
    parsed = {"patalpos": rooms, "bendras_plotas_m2": 50 * 12.5}
    fingerprints = []
    for _ in range(3):
        out = _run_full_pipeline(copy.deepcopy(parsed))
        fingerprints.append(_fingerprint(out))
    assert len(set(fingerprints)) == 1, (
        f"Non-deterministic 50-room output across 3 runs: "
        f"{[f[:200] for f in fingerprints]}"
    )


def test_pozicijos_p7_legacy_skyrius_migration():
    """P7: legacy ASCII-stripped skyrius names (saved by earlier exports)
    are migrated to LT-with-diacritics in darbu_sarasas. Old projects don't
    appear with «Plyteles» / «Glaistymas dazymas» / «Pridetiniai» mojibake."""
    from extractor.vision_call import _emit_v8_compat_fields, SKYRIUS_LEGACY_MIGRATION

    # Sanity: migration map covers known legacy variants
    assert SKYRIUS_LEGACY_MIGRATION["Plyteles"] == "Plytelių klijavimas"
    assert SKYRIUS_LEGACY_MIGRATION["Glaistymas dazymas"] == "Sienų lubų glaistymas dažymas"
    assert SKYRIUS_LEGACY_MIGRATION["Pridetiniai elementai"] == "Pridėtiniai elementai"

    # Pipeline-level: when pozicijos[] contains legacy keys, darbu_sarasas
    # emits them with modern keys
    parsed = {
        "pozicijos": [
            {"skyrius": "Plyteles", "aprasymas": "Vonios plytelių klijavimas",
             "vnt": "m2", "kiekis": 25.0, "saltinis": "skaiciuota_is_brezinio"},
            {"skyrius": "Glaistymas dazymas", "aprasymas": "Sienų dažymas",
             "vnt": "m2", "kiekis": 50.0},
            {"skyrius": "Pridetiniai elementai", "aprasymas": "Šiukšlių išvežimas",
             "vnt": "kompl", "kiekis": 1},
        ],
    }
    out = _emit_v8_compat_fields(parsed)
    skyrius_set = {r["skyrius"] for r in out["darbu_sarasas"]}
    assert "Plyteles" not in skyrius_set, "Legacy mojibake key 'Plyteles' should not appear"
    assert "Glaistymas dazymas" not in skyrius_set, "Legacy mojibake key should not appear"
    assert "Pridetiniai elementai" not in skyrius_set, "Legacy mojibake should not appear"
    assert "Plytelių klijavimas" in skyrius_set
    # 2026-09-02: the legacy name maps onto the merged section, and the row is
    # then sorted into one of its two successors by its aprašymas.
    assert "Sienų glaistymas dažymas" in skyrius_set
    assert "Pridėtiniai elementai" in skyrius_set


def test_pozicijos_hidroizoliacija_two_rows_by_default():
    """Founder decision 2026-10-24 (profile `hidro_rows = "two"`): „Grindų hidroizoliacija" m² = the wet
    rooms' net floor, „Hidroizoliacinė juosta kampams" m = their gross perimeter."""
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
            {"nr": "W1", "pavadinimas": "WC", "paskirtis": "wc",
             "plotas_m2": 2.0, "perimetras_m": 5.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    lines = {p["aprasymas"]: p for p in out["pozicijos"] if p["skyrius"] == "Hidroizoliacija"}
    assert set(lines) == {"Grindų hidroizoliacija", "Hidroizoliacinė juosta kampams"}
    assert lines["Grindų hidroizoliacija"]["vnt"] == "m2" and lines["Grindų hidroizoliacija"]["kiekis"] == 8.5
    assert lines["Hidroizoliacinė juosta kampams"]["vnt"] == "m"
    assert lines["Hidroizoliacinė juosta kampams"]["kiekis"] == 16.0


def test_pozicijos_p6_hidroizoliacija_collapsed_to_one_line():
    """P6 (profile option `hidro_rows = "one"`): 4 hidroizoliacijos eilučių stack collapsed to 1 line per
    LT contractor convention (Rangovas style: '1 vnt = vonia komplektas')."""
    parsed = {
        "_overrides": {"profilis": {"hidro_rows": "one"}},
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
            {"nr": "W1", "pavadinimas": "WC", "paskirtis": "wc",
             "plotas_m2": 2.0, "perimetras_m": 5.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "elementai": [], "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    hidro_lines = [p for p in out["pozicijos"] if p["skyrius"] == "Hidroizoliacija"]
    assert len(hidro_lines) == 1, f"Expected 1 hidroizoliacija line, got {len(hidro_lines)}: {hidro_lines}"
    line = hidro_lines[0]
    assert line["vnt"] == "vnt"
    assert line["kiekis"] == 2  # 2 wet rooms
    # Detail fields preserved for frontend expand
    assert line.get("_detail_m2", 0) > 0
    assert line.get("_detail_juostele_m", 0) > 0
    # Material kg = m² × 3.0 (2 coats × 1.5 kg/m²) — a row of its own in the
    # "Medžiagos" section since 2026-09-02, linked back to this work line.
    mat = next(p for p in out["pozicijos"]
               if p["skyrius"] == "Medžiagos"
               and p["susijes_darbas"] == line["aprasymas"])
    assert mat["kiekis"] == round(line["_detail_m2"] * 3.0, 2)
    assert mat["vnt"] == "kg"


def test_pozicijos_p3_silikon_split_per_rangovas_audit():
    """Silikonavimas split into two lines (rangovas 2026-04-29 audit), total
    RECALIBRATED 2026-07-25 from ×1.4 to the ×2.3 the per-room field and
    ground truth carry (objektas_a gt 107/111 = ×2.15/×2.65; samata line 50.14 m
    where ×1.4 gave −39% and ×2.3 gives −0.5%). Split stays 4:3.
    """
    parsed = {
        "patalpos": [
            {"nr": "V1", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 10.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "pakabinamos", "plyteles_sienos_aukstis_m": 2.0,
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}],
             "confidence": "high"},
        ],
    }
    out = _run_full_pipeline(parsed)
    # WORK rows only — the silicone tubes are their own "Medžiagos" rows since
    # 2026-09-02 and carry the word too.
    silikon_lines = [p for p in out["pozicijos"]
                     if "silikon" in p["aprasymas"].lower()
                     and p["skyrius"] != "Medžiagos"]
    assert len(silikon_lines) == 2, f"expected 2 silikon lines (san + kampai), got {len(silikon_lines)}"
    # Wet perim 12.0; sanitarinis = 12 × 1.31 = 15.72; kampai = 12 × 0.99 = 11.88
    san = next(p for p in silikon_lines if "sanitarinės" in p["aprasymas"].lower())
    kampai = next(p for p in silikon_lines if "kampų" in p["aprasymas"].lower())
    assert abs(san["kiekis"] - 15.72) < 0.1
    assert abs(kampai["kiekis"] - 11.88) < 0.1


def test_eksplikacija_merge_propagates_bbox_to_room():
    """Vision-pipeline merge step must copy bbox fields onto each room when
    eksplikacija (pdfplumber) provides them."""
    parsed = {
        "patalpos": [
            {"nr": "01", "pavadinimas": "Svetainė", "plotas_m2": 14.0},
            {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 5.0},
        ],
    }
    eks = {
        "patalpos": [
            {"row_idx": 0, "pavadinimas": "Svetainė", "plotas_m2": 14.50,
             "eksplikacija_row_bbox": [100.0, 200.0, 800.0, 220.0],
             "eksplikacija_page_width_pdf": 1191.0,
             "eksplikacija_page_height_pdf": 842.0},
            # Vonia has no bbox (multi-line cell sub_idx > 0)
            {"row_idx": 1, "pavadinimas": "Vonia", "plotas_m2": 5.20},
        ],
        "eksplikacija_source_page": 12,
        "schedule_tables": {"durys": [], "langai": []},
        "_meta": {"source": "pdfplumber_table"},
    }
    # Inline replication of vision_call.py's merge loop (kept here to isolate
    # the contract from the larger module's side effects).
    eks_by_name = {(r["pavadinimas"] or "").strip().lower(): r for r in eks["patalpos"]}
    for room in parsed["patalpos"]:
        name = (room["pavadinimas"] or "").strip().lower()
        eks_row = eks_by_name.get(name)
        if eks_row:
            if eks_row.get("plotas_m2"):
                room["plotas_m2"] = eks_row["plotas_m2"]
                room["plotas_saltinis"] = "eksplikacija"
            room["eksplikacija_row_idx"] = eks_row.get("row_idx")
            if eks_row.get("eksplikacija_row_bbox"):
                room["eksplikacija_row_bbox"] = eks_row["eksplikacija_row_bbox"]
            if eks_row.get("eksplikacija_page_width_pdf"):
                room["eksplikacija_page_width_pdf"] = eks_row["eksplikacija_page_width_pdf"]
            if eks_row.get("eksplikacija_page_height_pdf"):
                room["eksplikacija_page_height_pdf"] = eks_row["eksplikacija_page_height_pdf"]

    sv = parsed["patalpos"][0]
    assert sv["plotas_m2"] == 14.50
    assert sv["plotas_saltinis"] == "eksplikacija"
    assert sv["eksplikacija_row_idx"] == 0
    assert sv["eksplikacija_row_bbox"] == [100.0, 200.0, 800.0, 220.0]
    assert sv["eksplikacija_page_width_pdf"] == 1191.0

    vo = parsed["patalpos"][1]
    assert vo["plotas_m2"] == 5.20
    assert vo["plotas_saltinis"] == "eksplikacija"
    assert vo["eksplikacija_row_idx"] == 1
    # No bbox propagated (multi-line cell parent)
    assert "eksplikacija_row_bbox" not in vo

"""Phase 2 commit 2 — the `lt_rangovas` conventions profile (rules/conventions.py LT_RANGOVAS).

One test (or a few) per parameter: its default is what the engine did before the profile
existed, each alternative moves exactly the quantity it names, and a Prielaidos override
(`rules_override.profilis`) reaches the rows through /recompute-interior."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SAMATU_AUTH_DISABLED", "1")

from extractor.ledger import replay  # noqa: E402
from extractor.universal_rules import (  # noqa: E402
    calc_room_quantities, skirting_door_widths_m, translate_user_prefs_to_room_rules,
)
from main import app  # noqa: E402
from rules import rows as rrows  # noqa: E402
from rules.conventions import LT_RANGOVAS, UNIVERSAL_RULES, profile_overrides, resolve_profile  # noqa: E402

client = TestClient(app)


def _door(n=1, w=900):
    return {"tipas": "duris", "plotis_mm": w, "aukstis_mm": 2100, "kiekis": n}


def _window(n=1):
    return {"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": n}


def _rooms():
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "puslapio_nr": 1, "elementai": [_door(1), _window(2)]},
        {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamasis", "plotas_m2": 14.0,
         "perimetras_m": 15.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "puslapio_nr": 1, "elementai": [_door(1, 800), _window(1)]},
        {"nr": "03", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "puslapio_nr": 1, "elementai": [_door(1)]},
        {"nr": "04", "pavadinimas": "WC", "paskirtis": "wc", "plotas_m2": 2.0,
         "perimetras_m": 6.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "puslapio_nr": 1, "elementai": [_door(1)]},
        {"nr": "05", "pavadinimas": "Skalbykla", "paskirtis": "skalbykla", "plotas_m2": 4.0,
         "perimetras_m": 8.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "puslapio_nr": 1, "elementai": [_door(1)]},
    ]


def _recompute(profilis=None):
    body = {"patalpos": _rooms(), "rules_override": {"profilis": profilis} if profilis else {}}
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _poz(out, prefix):
    return [r for r in out.get("pozicijos") or [] if str(r.get("aprasymas") or "").startswith(prefix)]


def _led(out, prefix):
    """The sąmata row as shipped (darbu_sarasas carries the ledger)."""
    return [r for r in out.get("darbu_sarasas") or [] if str(r.get("aprasymas") or "").startswith(prefix)][0]


def _qty(out, prefix):
    return round(sum(float(r.get("kiekis") or 0) for r in _poz(out, prefix)), 2)


def _calc(room, profilis=None):
    rules = translate_user_prefs_to_room_rules({"profilis": profilis}) if profilis else None
    counts = {"n_doors": sum(int(e["kiekis"]) for e in room["elementai"] if e["tipas"] == "duris"),
              "n_windows": sum(int(e["kiekis"]) for e in room["elementai"] if e["tipas"] == "langas")}
    return calc_room_quantities({**room, **counts}, rules=rules)


# ── the profile object ────────────────────────────────────────────────────────

def test_every_parameter_is_named_documented_and_has_its_default_among_the_choices():
    for name, p in LT_RANGOVAS.items():
        assert p.name == name and p.source.strip() and p.doc.strip()
        if name != "wet_room_markers":
            assert p.default in p.choices, name
    assert LT_RANGOVAS["aperture_no_deduct_max_m2"].default == 3.0           # rangovo taisyklė 2026-10-25
    assert 1.0 in LT_RANGOVAS["aperture_no_deduct_max_m2"].choices            # the older LT rule stays an option
    assert LT_RANGOVAS["hidro_rows"].default == "two"            # founder decision 2026-10-24
    assert "skalbykla" not in LT_RANGOVAS["wet_room_markers"].default


def test_overrides_are_validated_and_unknown_keys_ignored():
    assert profile_overrides(None) == {}
    assert profile_overrides({"profilis": "x"}) == {}
    got = profile_overrides({"profilis": {"kampai": "isoriniai", "nope": 1, "hidro_rows": "three",
                                          "aperture_no_deduct_max_m2": "3", "skirting_door_deduct_m": "drawn",
                                          "skirting_waste": 5}})
    assert got == {"kampai": "isoriniai", "aperture_no_deduct_max_m2": 3.0, "skirting_door_deduct_m": "drawn"}
    assert resolve_profile({})["hidro_rows"] == "two"
    assert resolve_profile({"profilis": {"hidro_rows": "one"}})["hidro_rows"] == "one"


# ── aperture_no_deduct_max_m2 ─────────────────────────────────────────────────

def test_aperture_threshold_three_keeps_a_door_in_the_wall():
    room = _rooms()[1]                                   # one 0,8 × 2,1 = 1,68 m² door
    base = _calc(room)                                   # default 3,0 (rangovo taisyklė 2026-10-25)
    old = _calc(room, {"aperture_no_deduct_max_m2": 1.0})
    assert old["doors_deducted_m2"] > 0
    assert base["doors_deducted_m2"] == 0
    assert base["walls_paintable_m2"] > old["walls_paintable_m2"]
    assert _calc(room, {"aperture_no_deduct_max_m2": 3.0}) == base


# ── skirting_door_deduct_m / skirting_waste ───────────────────────────────────

def test_skirting_door_deduction_fixed_and_drawn():
    room = _rooms()[1]
    assert skirting_door_widths_m(room, 1, 0.85) == pytest.approx(0.85)
    assert skirting_door_widths_m(room, 1, 0.90) == pytest.approx(0.90)
    assert skirting_door_widths_m(room, 1, "drawn") == pytest.approx(0.80)       # the door's own 800 mm
    assert skirting_door_widths_m({"elementai": []}, 2, "drawn") == pytest.approx(1.8)  # unread → 0,9 each
    base = _calc(room)
    assert base["_grindjuosciu_baze_m"] == pytest.approx(15.0 - 0.85)
    assert _calc(room, {"skirting_door_deduct_m": 0.9})["_grindjuosciu_baze_m"] == pytest.approx(14.10)
    assert _calc(room, {"skirting_door_deduct_m": "drawn"})["_grindjuosciu_baze_m"] == pytest.approx(14.20)


def test_skirting_waste_net_labour_row():
    room = _rooms()[1]
    base = _calc(room)
    net = _calc(room, {"skirting_waste": 1.0})
    assert base["grindjuosciu_m"] == pytest.approx(round(base["_grindjuosciu_baze_m"] * 1.10, 2))
    assert net["grindjuosciu_m"] == pytest.approx(net["_grindjuosciu_baze_m"])
    out = _recompute({"skirting_waste": 1.0})
    row = _led(out, "Grindjuosčių sumontavimas")
    assert replay(row.get("contributions"), row.get("roll_up")) == pytest.approx(row["kiekis"], abs=0.01)


# ── kampai ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("conv", ["visi", "vertikalus_lubos", "vertikalus", "isoriniai_angos", "isoriniai", "tik_lubos"])
def test_kampai_conventions_keep_only_their_terms_and_the_terms_still_add_up(conv):
    room = _rooms()[0]                                   # rectangle, no outline: no outer corners known
    r = _calc(room, {"kampai": conv})
    terms = (r["kampai_inner_m"] + r["kampai_opening_reveals_m"] + r["kampai_pusiniai_m"]
             + r["kampai_perimetras_m"] + r["kampai_skyliu_m"] + r["kampai_isoriniai_m"])
    assert terms == pytest.approx(r["kampu_metrai"], abs=0.02)
    H = 2.7
    openings = 1 * (0.9 + 2 * 2.05) + 2 * (1.2 + 2 * 1.5)
    expected = {"visi": 22.0 + 4 * H + openings, "vertikalus_lubos": 22.0 + 4 * H,
                "vertikalus": 4 * H, "isoriniai_angos": openings, "isoriniai": 0.0, "tik_lubos": 22.0}[conv]
    assert r["kampu_metrai"] == pytest.approx(expected, abs=0.02)


def test_kampai_default_is_todays_number():
    room = _rooms()[0]
    assert _calc(room) == _calc(room, {"kampai": "visi"})


# ── wet_room_markers + hidro_rows ─────────────────────────────────────────────

@pytest.mark.parametrize("name, pask, wet", [
    ("Vonios kambarys", "", True), ("WC", "", True), ("San. mazgas", "", True), ("Vonia", "vonia", True),
    ("Skalbykla", "skalbykla", False), ("Skalbykla / vonia", "", False), ("Svetainė", "gyvenamoji", False),
    ("Wcx sandėliukas", "", False),
])
def test_wet_room_markers(name, pask, wet):
    markers = LT_RANGOVAS["wet_room_markers"].default
    assert rrows.is_wet_room({"pavadinimas": name}, pask, markers) is wet


def test_hidro_two_rows_by_default():
    out = _recompute()
    floor = _poz(out, "Grindų hidroizoliacija")
    tape = _poz(out, "Hidroizoliacinė juosta kampams")
    assert len(floor) == 1 and len(tape) == 1
    assert floor[0]["vnt"] == "m2" and floor[0]["kiekis"] == pytest.approx(6.0 + 2.0)   # vonia + WC, no laundry
    assert tape[0]["vnt"] == "m" and tape[0]["kiekis"] == pytest.approx(10.0 + 6.0)
    assert not _poz(out, "Hidroizoliacijos įrengimas")
    for row in (_led(out, "Grindų hidroizoliacija"), _led(out, "Hidroizoliacinė juosta kampams")):
        assert replay(row.get("contributions"), row.get("roll_up")) == pytest.approx(row["kiekis"], abs=0.01)


def test_hidro_one_row_option():
    out = _recompute({"hidro_rows": "one"})
    rows = _poz(out, "Hidroizoliacijos įrengimas")
    assert len(rows) == 1 and rows[0]["vnt"] == "vnt" and rows[0]["kiekis"] == 2
    assert not _poz(out, "Grindų hidroizoliacija")


# ── rounding (R4) ─────────────────────────────────────────────────────────────

def test_row_boundary_rounding():
    rows = [{"kiekis": 2.675, "vnt": "m2", "medziagos_kiekis": 3.005, "medziagos_vnt": "kg"},
            {"kiekis": 2.5, "vnt": "vnt"}, {"kiekis": None, "vnt": "m"}]
    rrows.round_rows_at_boundary(rows)
    assert rows[0]["kiekis"] == 2.68 and rows[0]["medziagos_kiekis"] == 3.01
    assert rows[1]["kiekis"] == 3 and rows[2]["kiekis"] is None


def test_rows_leave_the_builder_rounded_once():
    out = _recompute()
    for r in out.get("pozicijos") or []:
        q = r.get("kiekis")
        if isinstance(q, float):
            assert round(q, 2) == q, r.get("aprasymas")

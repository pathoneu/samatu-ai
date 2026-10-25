"""Paint pozicijos consolidation (2026-06-06).

Collapses the per-coat split (Q1 / Q2 / šlifavimas / gruntavimas /
dažymas-sluoksniai, for walls AND ceilings) into the contractor's combined
line — matching Rangovas A samata items 16/17. Rotband stays its own line
(item 15). The combined paintable area is unchanged (display-only change).

2026-09-02 (contractor ask F3): the combined line is emitted PER SURFACE —
"Sienų glaistymas/dažymas …" + "Lubų glaistymas/dažymas …" instead of one
"Sienų, lubų …" line — because walls and ceilings are now two sections, two
trades and two rates. Σ of the two still equals the old single line.
"""
import os

from extractor.vision_call import (
    _build_pozicijos_from_rooms, _calc_dazai_liters, _calc_glaistas_kg,
)
from extractor.universal_rules import calc_room_quantities


def _parsed(rooms, overrides=None):
    p = {"patalpos": rooms, "santrauka": {}}
    if overrides is not None:
        p["_overrides"] = overrides
    return p


def _room(**kw):
    r = {"paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys",
         "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "elementai": []}
    r.update(kw)
    r.update(calc_room_quantities(r))
    # The per-room material fields the extraction pipeline computes on top of
    # calc_room_quantities (`_recompute_per_room_via_python` §4.1-4.3). Without
    # them every material quantity is 0 and the material assertion below passes
    # vacuously — which is exactly what it did before 2026-09-02.
    dazymo = float(r.get("dazymo_plotas_m2") or 0)
    r["glaistas_kg"] = _calc_glaistas_kg(dazymo)
    r["dazai_l"] = _calc_dazai_liters(dazymo, paint_class=2)
    r["gruntas_l"] = round(dazymo / 7.0, 2) if dazymo > 0 else 0.0
    return r


def test_paint_consolidated_default_on():
    rooms = [_room()]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    labels = [p["aprasymas"] for p in out["pozicijos"]]
    # the split paint-coat lines are GONE (Q1/Q2/per-coat). NB: a floor line
    # "Grindų išlyginamasis sluoksnis" legitimately contains "sluoksnis" — so
    # match the paint-coat patterns specifically, not the bare word.
    bad = [l for l in labels if ("glaistymas Q1" in l) or ("glaistymas Q2" in l)
           or ("dažymas (1 sluoksnis" in l) or ("dažymas (2 sluoksni" in l)
           or ("gruntavimas (1 sluoksnis" in l)]
    assert not bad, f"split paint lines still present: {bad}"
    # one consolidated work line PER SURFACE (no >3m rooms here)
    sienos = [p for p in out["pozicijos"]
              if p["aprasymas"].startswith("Sienų glaistymas/dažymas")]
    lubos = [p for p in out["pozicijos"]
             if p["aprasymas"].startswith("Lubų glaistymas/dažymas")]
    assert len(sienos) == 1 and len(lubos) == 1, labels
    assert sienos[0]["skyrius"] == "Sienų glaistymas dažymas"
    assert lubos[0]["skyrius"] == "Lubų glaistymas dažymas"
    # each surface counted ONCE (not summed coats), and together they still add
    # up to the old single line's area
    r = rooms[0]
    assert abs(sienos[0]["kiekis"] - r["walls_paintable_m2"]) < 0.5, sienos
    assert abs(lubos[0]["kiekis"] - r["ceiling_paintable_m2"]) < 0.5, lubos
    expected = round(r["walls_paintable_m2"] + r["ceiling_paintable_m2"], 2)
    assert abs(sienos[0]["kiekis"] + lubos[0]["kiekis"] - expected) < 0.5
    # materials preserved (not lost to consolidation), and split — never doubled.
    # 2026-09-02: they no longer ride on the work line — each is a row in the
    # global "Medžiagos" section, linked back by `susijes_darbas`.
    assert not sienos[0].get("_medziagos"), "materials must leave the work line"
    def _mat(work_label, name):
        return next(p["kiekis"] for p in out["pozicijos"]
                    if p["skyrius"] == "Medžiagos"
                    and p["susijes_darbas"] == work_label
                    and p["aprasymas"] == name)
    glaistas_total = round(sum(float(x.get("glaistas_kg") or 0) for x in rooms), 2)
    assert abs(_mat(sienos[0]["aprasymas"], "Glaistas sienoms (pradinis + baigiamasis)")
               + _mat(lubos[0]["aprasymas"], "Glaistas luboms (pradinis + baigiamasis)")
               - glaistas_total) < 0.05
    # Rotband stays a separate line (contractor item 15)
    assert any("Rotband" in l for l in labels), labels


def test_paint_split_when_flag_off():
    os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"] = "0"
    try:
        out = _build_pozicijos_from_rooms(_parsed([_room()]))
        labels = [p["aprasymas"] for p in out["pozicijos"]]
        assert any("glaistymas Q1" in l for l in labels), \
            f"flag off should keep the split: {labels}"
    finally:
        del os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"]


def test_high_room_gets_iki_and_virs_3m_lines():
    # one normal room (≤3m) + one high room (>3m) → split into the two
    # contractor lines (items 16/17). Combined area preserved.
    rooms = [_room(plotas_m2=20.0, perimetras_m=18.0, perimetras_saltinis="plano_matmenys", lubu_aukstis_m=2.7, lubu_aukstis_saltinis="plano_uzrasas"),
             _room(plotas_m2=30.0, perimetras_m=22.0, perimetras_saltinis="plano_matmenys", lubu_aukstis_m=3.4, lubu_aukstis_saltinis="plano_uzrasas")]
    out = _build_pozicijos_from_rooms(_parsed(rooms))
    for surf in ("Sienų glaistymas/dažymas", "Lubų glaistymas/dažymas"):
        gd = [p["aprasymas"] for p in out["pozicijos"]
              if p["aprasymas"].startswith(surf)]
        assert any("iki 3m" in l.lower() for l in gd), f"expected an iki-3m line: {gd}"
        assert any("virš 3m" in l.lower() for l in gd), f"expected a virš-3m line: {gd}"
    # Combined area is still the sum of both surfaces across both tiers.
    total = round(sum(float(p["kiekis"]) for p in out["pozicijos"]
                      if "glaistymas/dažymas" in p["aprasymas"]
                      and p.get("vnt") == "m2"), 2)
    expected = round(sum(r["walls_paintable_m2"] + r["ceiling_paintable_m2"]
                         for r in rooms), 2)
    assert abs(total - expected) < 0.05, f"{total} vs {expected}"


def test_led_niche_consolidated_default_on():
    # 'LED nišų glaistymas' + 'LED nišų dažymas' collapse into the contractor's
    # single 'LED nišų glaistymas/dažymas' line (Rangovas A samata item 23 — one
    # m rate for both phases). Same length; the structural GKP framing line stays.
    os.environ.pop("ENABLE_CONSOLIDATE_PAINT_LINES", None)  # defensive: default ON
    r = _room()
    r["elementai"] = [{"tipas": "nisa_LED", "ilgis_m": 42.3}]
    parsed = _parsed([r])
    # v4 3b: the length is the legend's, the room's niche only says there are niches
    parsed["_autoriaus_kiekiai"] = [{"page": 3, "label": "LED juosta", "value": 42.3, "unit": "m", "family": "led"}]
    out = _build_pozicijos_from_rooms(parsed)
    labels = [p["aprasymas"] for p in out["pozicijos"]]
    assert "LED nišų glaistymas/dažymas" in labels, labels
    assert "LED nišų glaistymas" not in labels, labels
    assert "LED nišų dažymas" not in labels, labels
    led = [p for p in out["pozicijos"] if p["aprasymas"] == "LED nišų glaistymas/dažymas"]
    assert len(led) == 1
    assert abs(led[0]["kiekis"] - 42.3) < 0.01, led[0]["kiekis"]
    assert led[0].get("_detalus") == ["LED nišų glaistymas", "LED nišų dažymas"]
    # the structural GKP framing line is a distinct operation — NOT collapsed
    assert "Nišų formavimas GKP konstrukcijoje" in labels, labels


def test_led_niche_split_when_flag_off():
    os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"] = "0"
    try:
        r = _room()
        r["nisu_metrai"] = 42.3
        out = _build_pozicijos_from_rooms(_parsed([r]))
        labels = [p["aprasymas"] for p in out["pozicijos"]]
        assert "LED nišų glaistymas" in labels, labels
        assert "LED nišų dažymas" in labels, labels
        assert "LED nišų glaistymas/dažymas" not in labels, labels
    finally:
        del os.environ["ENABLE_CONSOLIDATE_PAINT_LINES"]

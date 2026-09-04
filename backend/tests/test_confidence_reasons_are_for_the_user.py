"""Every _confidence_reason a contractor can see must guide, never confess.

2026-08-31, founder catch on the live review queue: a row read "Formulė
kalibruota pagal 1 rangovo samatą (Objektas A) — … tikslumas nepatvirtintas
(reikia daugiau etalonų)". Three failures in one string: it LEAKS another
client's project name to every future user, it quotes our benchmark
methodology (sample counts, error pairs) as if the number were copied from
someone else's job, and it speaks pipeline jargon no contractor can act on.
The calibration facts belong in code comments; the visible string answers
"what is this based on, what do I check".

This test bans the whole class from every reason-producing surface.
"""
from __future__ import annotations

import re

import pytest

from extractor.confidence import CLASS_RULES, _OVERBILLING_RULES, apply_confidence

# Client identifiers, benchmark bookkeeping, internal jargon, dev-speak.
BANNED = re.compile(
    r"Objektas [A-F]\b|Rangovas [A-D]|rangovo samat|rangovą|\(\d+ projekt|projektai\)"
    r"|\bvs\b|%/|recall|etalon|kalibruota|ginčytin|Ekstrakcij|Gretimyb"
    r"|pradinis pass|archetip|low confidence|Vision|žinomai|Sprint|TODO",
    re.IGNORECASE)


@pytest.mark.parametrize("needle,conf,reason",
                         CLASS_RULES + _OVERBILLING_RULES,
                         ids=[r[0] for r in CLASS_RULES + _OVERBILLING_RULES])
def test_static_rule_reasons_are_clean(needle, conf, reason):
    m = BANNED.search(reason)
    assert not m, f"banned token {m.group(0)!r} in reason for {needle!r}: {reason}"


def test_dynamic_reasons_are_clean():
    """The f-string reasons (apdailos-low, voting disagreement, no-partitions,
    unread dims) are only observable through apply_confidence — drive every
    branch and scan what it writes."""
    parsed = {
        "patalpos": [
            {"nr": "01", "_apdailos_confidence": "low", "n_partition_walls": 0,
             "elementai": [{"tipas": "langas", "plotis_m": None, "aukstis_m": None}]},
        ],
        "_voting": {"low_confidence_fields": ["01.plotas_m2"]},
        "pozicijos": [
            {"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 100},
            {"aprasymas": "Dažymo kampų montavimas", "kiekis": 200},
            {"aprasymas": "Angokraščių glaistymas-dažymas", "kiekis": 50},
            {"aprasymas": "Parketo / laminato klojimas", "kiekis": 80},
        ],
    }
    out = apply_confidence(parsed)
    for p in out["pozicijos"]:
        r = p.get("_confidence_reason") or ""
        m = BANNED.search(r)
        assert not m, f"banned token {m.group(0)!r} on {p['aprasymas']!r}: {r}"
    # The branches actually fired — this test must not pass by vacuity.
    joined = " | ".join(p.get("_confidence_reason") or "" for p in out["pozicijos"])
    assert "AI skaitymai nesutarė" in joined
    assert "PER MAŽA" in joined


def test_material_row_reasons_are_clean():
    """The Medžiagos section (2026-09-02) adds one reason of its own — the note
    a material row carries when its parent work line had none — and inherits
    the parent's otherwise. Scan the new string, and the rows a real build
    produces, through the same net."""
    from extractor.vision_call import (
        _MEDZIAGOS_REASON, SK_MEDZIAGOS, _build_pozicijos_from_rooms,
    )
    m = BANNED.search(_MEDZIAGOS_REASON)
    assert not m, f"banned token {m.group(0)!r} in the material reason"

    out = _build_pozicijos_from_rooms({
        "patalpos": [
            {"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
             "glaistas_kg": 120.0, "dazai_l": 12.0, "gruntas_l": 8.0,
             "walls_paintable_m2": 45.0, "ceiling_paintable_m2": 20.0,
             "dazymo_plotas_m2": 65.0, "kampu_metrai": 30.0,
             "grindjuosciu_m": 16.0, "elementai": []},
        ],
        "santrauka": {},
    })
    mats = [p for p in out["pozicijos"] if p["skyrius"] == SK_MEDZIAGOS]
    assert mats, "the build produced no material rows to scan"
    for p in mats:
        r = p.get("_confidence_reason") or ""
        hit = BANNED.search(r)
        assert not hit, f"banned token {hit.group(0)!r} on {p['aprasymas']!r}: {r}"


def test_contribution_ledger_strings_are_clean():
    """The ledger (2026-09-02) adds a whole new class of user-visible prose:
    why each room is IN a number, why each one is OUT, and what every roll-up
    step did. Same net — a contractor reads these the way he reads a reason."""
    from extractor.vision_call import _build_pozicijos_from_rooms

    out = _build_pozicijos_from_rooms({
        "patalpos": [
            {"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
             "walls_paintable_m2": 45.0, "ceiling_paintable_m2": 20.0,
             "dazymo_plotas_m2": 65.0, "kampu_metrai": 30.0,
             "kampai_inner_m": 10.8, "kampai_opening_reveals_m": 1.2,
             "kampai_pusiniai_m": 0.0, "kampai_perimetras_m": 18.0,
             "grindjuosciu_m": 16.0, "_grindjuosciu_baze_m": 14.55,
             "elementai": []},
            {"nr": "102", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.0, "perimetras_m": 10.0, "lubu_aukstis_m": 2.7,
             "walls_paintable_m2": 0.0, "ceiling_paintable_m2": 6.0,
             "plyteles_grindys_m2": 6.0, "kampu_metrai": 0.0,
             "grindjuosciu_m": 0.0, "elementai": []},
        ],
        "santrauka": {},
    })
    seen = 0
    for p in out["pozicijos"]:
        strings = (
            [c["included_because"] for c in (p.get("contributions") or [])]
            + [e["excluded_because"] for e in (p.get("excluded") or [])]
            + [s["label"] for s in (p.get("roll_up") or [])]
            + [s.get("note") or "" for s in (p.get("roll_up") or [])]
            + [k for c in (p.get("contributions") or [])
               for k in (c.get("terms") or {})]
        )
        seen += len(strings)
        for s in strings:
            m = BANNED.search(s)
            assert not m, f"banned token {m.group(0)!r} on {p['aprasymas']!r}: {s}"
    assert seen > 10, "the ledger produced almost no prose — did it stop emitting?"


def test_door_reconciliation_reasons_are_clean():
    """Drive every branch of reconcile_frameless and scan the reasons it
    actually returns — banning identifiers in source was the wrong net
    (`archetipas` is a parameter name, not a user string)."""
    from extractor.door_type_reader import reconcile_frameless
    outs = [
        reconcile_frameless(2, 0, "beapvadines", 7, "premium"),
        reconcile_frameless(2, 0, "beapvadines", 7, None),
        reconcile_frameless(2, 5, None, 7, None),
        reconcile_frameless(5, 2, None, 7, None),
        reconcile_frameless(3, 3, None, 7, None),
        reconcile_frameless(0, 0, None, 7, None),
    ]
    for o in outs:
        r = o.get("reason") or ""
        m = BANNED.search(r)
        assert not m, f"banned token {m.group(0)!r} in door reason: {r}"
    assert any("specifikacij" in (o.get("reason") or "") for o in outs), \
        "the guidance strings must actually be exercised"

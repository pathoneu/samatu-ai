"""Every _confidence_reason a contractor can see must guide, never confess.

2026-08-31, founder catch on the live review queue: a row read "Formulė
kalibruota pagal 1 rangovo samatą (Beržų) — … tikslumas nepatvirtintas
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
    r"Berž|Rangovas [A-D]|rangovo samat|rangovą|\(\d+ projekt|projektai\)"
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

"""F2/F3 export now falls back to the project's `pozicijos[]` field when
no explicit `data/projects/<id>/lines.json` override is present. Pre-fix
every saved project hit a 501 unless someone manually pre-staged a JSON
file — meaning F2/F3 was effectively unreachable from the UI.

Locks the translation contract from LT `pozicija` shape into F2Row shape.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.exports_v2 import _pozicija_to_line  # noqa: E402


def test_lt_pozicija_translates_to_f2_line():
    p = {
        "skyrius": "Sienų lubų glaistymas dažymas",
        "aprasymas": "Sienų antrinis glaistymas Q2",
        "vnt": "m2",
        "kiekis": 474.6,
        "ikainis_eur": 7.5,
        "saltinis": "skaiciuota_is_brezinio",
        "puslapio_nr": 5,
    }
    out = _pozicija_to_line(p, idx=1)
    assert out["label_lt"] == "Sienų antrinis glaistymas Q2"
    assert out["unit"] == "m2"
    assert out["quantity"] == 474.6
    assert out["unit_price_eur_be_pvm"] == 7.5
    assert out["source"] == "rule"
    assert out["source_pages"] == [5]


def test_user_override_pozicija_marks_source_user():
    p = {"aprasymas": "X", "vnt": "vnt", "kiekis": 3, "saltinis": "user_override"}
    out = _pozicija_to_line(p, idx=0)
    assert out["source"] == "user"
    # No price → confidence still defaults to yellow (sensible for unpriced)
    assert out["confidence"] == "yellow"


def test_verified_pozicija_marks_confidence_green():
    p = {"aprasymas": "X", "vnt": "vnt", "kiekis": 3, "saltinis": "rule",
         "verified": True}
    out = _pozicija_to_line(p, idx=0)
    assert out["confidence"] == "green"


def test_missing_code_synthesizes_stable_id():
    p = {"aprasymas": "Foo", "vnt": "m", "kiekis": 1.0, "saltinis": "rule"}
    out = _pozicija_to_line(p, idx=11)
    # Code is the F2 row's primary key for audit/correction joining; we
    # synthesize one if upstream didn't set it. Stable on idx so re-runs
    # don't break audit history references.
    assert out["code"] == "poz-012"


def test_ai_vision_source_maps_to_ai():
    p = {"aprasymas": "Y", "vnt": "vnt", "kiekis": 1, "saltinis": "ai_vision"}
    out = _pozicija_to_line(p, idx=0)
    assert out["source"] == "ai"

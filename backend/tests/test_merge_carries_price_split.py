"""A rebuild keeps the darbo + medžiagų split, the rinkinys and the kodas (togal-v2 W9).

Twin of the `ROW_CHOICE_KEYS` / split cases in frontend mergeDarbuSarasas.test.js
— the two merge layers must stay behaviourally identical.
"""
from __future__ import annotations

from api.recompute_quantities import _merge_user_edits


def _row(**over):
    base = {"id": "r1", "skyrius": "Sienų glaistymas dažymas",
            "aprasymas": "Sienų glaistymas/dažymas", "vnt": "m2", "kiekis": 100.0}
    base.update(over)
    return base


def test_split_and_choices_survive_a_rebuild_by_id_and_suma_follows_the_new_quantity():
    prior = [_row(kaina=5.3, suma=530.0, kaina_source="rinkinys", kaina_darbo=4.2,
                  kaina_medziagu=1.1, rinkinys_medziagos=["Klijai"], rinkinys_id="a1",
                  kodas="01.01")]
    out = _merge_user_edits([_row(kiekis=120.0)], prior)
    r = out[0]
    assert (r["kaina"], r["kaina_darbo"], r["kaina_medziagu"]) == (5.3, 4.2, 1.1)
    assert r["kaina_source"] == "rinkinys" and r["rinkinys_id"] == "a1"
    assert r["rinkinys_medziagos"] == ["Klijai"] and r["kodas"] == "01.01"
    assert r["suma"] == 636.0


def test_a_typed_code_survives_on_an_unpriced_row():
    out = _merge_user_edits([_row()], [_row(kodas="X-7")])
    assert out[0]["kodas"] == "X-7"
    assert "kaina" not in out[0] or out[0]["kaina"] in (None, 0)


def test_by_label_when_the_rebuild_has_no_id():
    prior = [_row(id=None, kaina=4.2, kaina_source="kainynas", kaina_darbo=4.2,
                  kaina_medziagu=0.0, kodas="01.01")]
    out = _merge_user_edits([_row(id=None)], prior)
    assert out[0]["kaina_darbo"] == 4.2 and out[0]["kaina_medziagu"] == 0.0
    assert out[0]["kodas"] == "01.01"

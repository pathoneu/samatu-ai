"""api/version_diff.py — two saved states of a project → Lithuanian sentences. Pure."""
from __future__ import annotations

import copy

from api.version_diff import diff_projects, lt_number

NB = " "


def _room(nr="03", **kw):
    r = {"nr": nr, "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 36.56, "lubu_aukstis_m": 2.7, "polygon_source": "sienu_konturas",
         "polygon_pct": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]],
         "elementai": [{"tipas": "duris", "kiekis": 1}, {"tipas": "langas", "kiekis": 1}]}
    r.update(kw)
    return r


def _row(id_="r1", **kw):
    r = {"id": id_, "aprasymas": "Sienų dažymas", "mato_vnt": "m²", "kiekis": 92.5, "kaina": 4.0}
    r.update(kw)
    return r


def _blob(rooms=None, rows=None, **kw):
    return {"patalpos": rooms if rooms is not None else [_room()],
            "darbu_sarasas": rows if rows is not None else [_row()], **kw}


def test_lt_number():
    assert lt_number(36.56) == "36,56"
    assert lt_number(1234.5) == f"1{NB}234,50"
    assert lt_number(3, 0) == "3"


def test_identical_states_say_nothing():
    a = _blob()
    d = diff_projects(a, copy.deepcopy(a))
    assert d["tuscia"] is True and d["sakiniai"] == []


def test_perimeter_with_corrected_outline_reads_like_the_brief():
    a = _blob()
    b = _blob(rooms=[_room(perimetras_m=38.10, polygon_source="corrected",
                           polygon_pct=[[0.1, 0.1], [0.32, 0.1], [0.32, 0.3]])])
    assert diff_projects(a, b)["sakiniai"] == [
        f"Patalpa 03 Vonia: perimetras 36,56{NB}m → 38,10{NB}m (kontūras pataisytas)"]


def test_room_facts_openings_and_purpose():
    a = _blob()
    b = _blob(rooms=[_room(lubu_aukstis_m=3.0, paskirtis="wc", grindu_danga="plyteles",
                           elementai=[{"tipas": "duris", "kiekis": 2}])])
    (s,) = diff_projects(a, b)["sakiniai"]
    assert s.startswith("Patalpa 03 Vonia: ")
    assert f"lubų aukštis 2,70{NB}m → 3,00{NB}m" in s
    assert "paskirtis „vonia“ → „WC“" in s
    assert "grindų danga „—“ → „plytelės“" in s
    assert "durys 1 → 2 vnt." in s and "langai 1 → 0 vnt." in s


def test_rounding_noise_is_not_a_change():
    a = _blob()
    b = _blob(rooms=[_room(perimetras_m=36.561)], rows=[_row(kiekis=92.5001)])
    assert diff_projects(a, b)["tuscia"]


def test_rooms_added_and_removed():
    a = _blob(rooms=[_room("03"), _room("04", pavadinimas="WC", plotas_m2=1.5)])
    b = _blob(rooms=[_room("03"), _room("05", pavadinimas="Sandėliukas", plotas_m2=4.5)])
    d = diff_projects(a, b)
    assert d["patalpos"]["pridetos"][0]["text"] == f"Pridėta: Patalpa 05 Sandėliukas (4,50{NB}m²)"
    assert d["patalpos"]["pasalintos"][0]["text"] == "Pašalinta: Patalpa 04 WC"
    assert d["patalpos"]["pakeistos"] == []


def test_rows_quantity_price_added_deleted():
    a = _blob(rows=[_row(), _row("r2", aprasymas="Grindjuostės", mato_vnt="m", kiekis=40)])
    b = _blob(rows=[_row(kiekis=95.1, kaina=4.5),
                    _row("rnk-1", aprasymas="Papildomas darbas", mato_vnt="vnt.", kiekis=2)])
    d = diff_projects(a, b)
    assert d["eilutes"]["pakeistos"][0]["text"] == (
        f"Eilutė „Sienų dažymas“: kiekis 92,50{NB}m² → 95,10{NB}m², kaina 4,00{NB}€ → 4,50{NB}€")
    assert d["eilutes"]["istrintos"][0]["text"] == "Ištrinta eilutė „Grindjuostės“"
    assert d["eilutes"]["pridetos"][0]["text"] == f"Pridėta eilutė „Papildomas darbas“ (2,00{NB}vnt.)"


def test_rows_without_id_match_by_label():
    a = _blob(rows=[{"aprasymas": "Senas", "kiekis": 1, "mato_vnt": "m"}])
    b = _blob(rows=[{"aprasymas": "senas ", "kiekis": 2, "mato_vnt": "m"}])
    assert diff_projects(a, b)["sakiniai"] == [f"Eilutė „senas“: kiekis 1,00{NB}m → 2,00{NB}m"]


def test_price_set_for_the_first_time():
    a = _blob(rows=[_row(kaina=None)])
    b = _blob(rows=[_row(kaina=3.2)])
    assert diff_projects(a, b)["sakiniai"] == [f"Eilutė „Sienų dažymas“: kaina — → 3,20{NB}€"]


def test_assumptions_known_room_heights_and_unknown_counted():
    a = _blob(_overrides={"paint_class": 2, "lubu_auksciai": {"04": 2.82}, "sienos_storis_m": 0.2,
                          "zzz_internal": 1},
              _apimtis={"lubos": "dazomos", "kampai": "su_vidiniais", "patalpos_ne": []})
    b = _blob(_overrides={"paint_class": 3, "lubu_auksciai": {"04": 3.0}, "sienos_storis_m": 0.25,
                          "zzz_internal": 2},
              _apimtis={"lubos": "itempiamos", "kampai": "su_vidiniais", "patalpos_ne": ["07"]})
    s = diff_projects(a, b)["sakiniai"]
    assert "Prielaida „dažymo klasė“: 2 → 3" in s
    assert f"Patalpa 04: lubų aukštis prielaidose 2,82{NB}m → 3,00{NB}m" in s
    assert f"Prielaida „sienų storis“: 0,20{NB}m → 0,25{NB}m" in s
    assert "Prielaida „lubos“: dažomos → įtempiamos" in s
    assert "Prielaida „neskaičiuojamos patalpos“: nėra → 07" in s
    assert "Pakeista kitų skaičiavimo nustatymų: 1" in s
    assert not any("zzz" in x or "_" in x for x in s)


def test_garbage_in_does_not_raise():
    assert diff_projects(None, {"patalpos": "x", "darbu_sarasas": [None, 3]})["tuscia"]
    d = diff_projects({}, {"patalpos": [{"plotas_m2": "abc"}]})
    assert d["patalpos"]["pridetos"][0]["text"] == "Pridėta: Patalpa #1"

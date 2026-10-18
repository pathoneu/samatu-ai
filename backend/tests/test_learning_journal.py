"""The „Mokymosi žurnalas" sentences (togal-v2 W11, api/learning_journal.py): one sentence per
correction, comma decimals, never a client or project name — and the list route serves them."""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import db  # noqa: E402
from api.learning_journal import journal, lt_number, sentence_for  # noqa: E402
from tests.test_room_outline_api import _isolate  # noqa: E402

PROJECT = {
    "name": "UAB Slaptas Klientas — Vilniaus g. 1",
    "darbu_sarasas": [
        {"id": "6d8ebdb80723", "aprasymas": "Sienų dažymas", "mato_vnt": "m²", "kiekis": 143.2},
        {"id": "rnk-7", "aprasymas": "Grindjuostės", "mato_vnt": "m", "kiekis": 40},
    ],
}
ROWS = {r["id"]: r for r in PROJECT["darbu_sarasas"]}


def test_numbers_use_a_comma_decimal():
    assert lt_number(143.2) == "143,2"
    assert lt_number(150) == "150,0"
    assert lt_number(10.123) == "10,12"
    assert lt_number(None) is None and lt_number(True) is None and lt_number("x") is None


def test_a_row_edit_and_a_row_accept():
    assert sentence_for({"source": "eilute_kiekis", "field_path": "eilute.6d8ebdb80723.kiekis",
                         "old_value": 143.2, "new_value": 150}, ROWS) == \
        "Eilutė „Sienų dažymas“: kiekį pakeitėte 143,2 → 150,0 m²"
    assert sentence_for({"source": "eilute_teisinga", "field_path": "eilute.rnk-7.kiekis",
                         "old_value": 40, "new_value": 40}, ROWS) == \
        "Eilutė „Grindjuostės“: kiekį 40,0 m patvirtinote kaip teisingą"
    # a row that is gone since is still a sentence
    assert sentence_for({"source": "eilute_teisinga", "field_path": "eilute.gone.kiekis", "new_value": 3}, ROWS) == \
        "Eilutė: kiekį 3,0 patvirtinote kaip teisingą"


def test_a_count_of_pieces_has_no_decimal():
    rows = {"d": {"id": "d", "aprasymas": "Difūzorių montavimas", "mato_vnt": "vnt"}}
    assert sentence_for({"source": "eilute_teisinga", "field_path": "eilute.d.kiekis", "new_value": 9.0}, rows) == \
        "Eilutė „Difūzorių montavimas“: kiekį 9 vnt patvirtinote kaip teisingą"
    assert sentence_for({"source": "eilute_kiekis", "field_path": "eilute.d.kiekis", "old_value": 9, "new_value": 8.5}, rows) == \
        "Eilutė „Difūzorių montavimas“: kiekį pakeitėte 9,0 → 8,5 vnt"


def test_rooms_outlines_questions_symbols_and_chat():
    assert sentence_for({"source": "konturas", "room_nr": "03", "field_path": "patalpa.03.kontūras",
                         "new_value": {"saltinis": "nubrezta", "plotas_m2": 10.12}}) == \
        "Patalpa 03: kontūrą nubrėžėte ranka (pagal kontūrą 10,12 m²)"
    assert sentence_for({"source": "konturas", "room_nr": "02", "new_value": {"saltinis": "sujungta", "plotas_m2": 0.0}}) == \
        "Patalpa 02: patalpą sujungėte su kita"
    assert sentence_for({"source": "konturas", "room_nr": "05", "new_value": None}) == \
        "Patalpa 05: kontūrą pataisėte ranka"
    # „Atšaukti" after an outline save (Pathon v3 W1-D): what was undone
    assert sentence_for({"source": "atsaukta", "room_nr": "04", "new_value": {"atsaukta": "konturas"}}) == \
        "Patalpa 04: kontūro pakeitimą atšaukėte"
    assert sentence_for({"source": "atsaukta", "room_nr": "05", "new_value": {"atsaukta": "sujungimas"}}) == \
        "Patalpa 05: patalpų sujungimą atšaukėte"
    assert sentence_for({"source": "atsaukta", "room_nr": "04", "new_value": {"atsaukta": "padalijimas"}}) == \
        "Patalpa 04: erdvės padalijimą atšaukėte"
    assert sentence_for({"source": "atsaukta", "room_nr": "04", "new_value": None}) == \
        "Patalpa 04: pakeitimą atšaukėte"
    assert sentence_for({"source": "patalpa_patvirtinta", "room_nr": "03", "new_value": 10.12}) == \
        "Patalpa 03: plotą 10,12 m² patvirtinote"
    assert sentence_for({"source": "klausimas_tinka", "note": "erdve:03-04"}) == \
        "Klausimas apie atvirą erdvę: priėmėte siūlymą"
    assert sentence_for({"source": "klausimas_netinka", "note": "aukstis"}) == \
        "Klausimas apie lubų aukštį: atsakėte savaip"
    assert sentence_for({"source": "klausimas_tinka", "note": "kazkas"}) == "Patikros klausimas: priėmėte siūlymą"
    assert sentence_for({"source": "simbolis", "field_path": "simbolis.2.difuzorius",
                         "new_value": {"sprendimas": "reject"}}) == "Lapas 2: rastą simbolį „difuzorius“ atmetėte"
    assert sentence_for({"source": "pokalbis_ne", "note": "Kiek dažomo ploto?"}) == "Pokalbis: atsakymas netiko"
    assert sentence_for({"source": "pokalbis_taip"}) == "Pokalbis: atsakymas tiko"


def test_prielaidos_rows_read_as_settings():
    assert sentence_for({"source": "prielaidos", "field_path": "lubu_auksciai.03", "room_nr": "03",
                         "old_value": 2.7, "new_value": 2.82}) == "Patalpa 03: lubų aukštį pakeitėte 2,7 → 2,82"
    assert sentence_for({"source": "prielaidos", "field_path": "glaistimo_lygis", "old_value": "Q2",
                         "new_value": "Q3"}) == "Glaistymo lygį pakeitėte"
    assert sentence_for({"source": "kitas", "field_path": "x.y"}) == "Nustatymą pakeitėte"


def test_no_sentence_carries_the_project_name():
    rows = [{"source": s, "field_path": f, "room_nr": "03", "old_value": 1, "new_value": 2, "note": "aukstis"}
            for s, f in (("eilute_kiekis", "eilute.6d8ebdb80723.kiekis"), ("konturas", "patalpa.03.kontūras"),
                         ("klausimas_tinka", "klausimas.aukstis"), ("prielaidos", "lubu_auksciai.03"))]
    for entry in journal(PROJECT, rows):
        assert "Slaptas" not in entry["sentence"] and "Vilniaus" not in entry["sentence"]


def test_the_list_route_serves_the_sentence(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", PROJECT)
    db.log_correction_once("p1", "eilute.6d8ebdb80723.kiekis", 143.2, 150.0, source="eilute_kiekis")
    with TestClient(app) as tc:
        out = tc.get("/api/projects/p1/corrections").json()["corrections"]
    assert [c["sentence"] for c in out] == ["Eilutė „Sienų dažymas“: kiekį pakeitėte 143,2 → 150,0 m²"]
    assert out[0]["source"] == "eilute_kiekis" and out[0]["new_value"] == 150.0

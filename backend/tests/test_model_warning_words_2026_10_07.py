"""The reading model's own warnings, without the prompt's English words (2026-10-07).

The 2026-10-07 walkthrough read, under „Verta patikrinti":
„Perimetrai daugumai patalpų apskaičiuoti iš ploto ir dalinių matmenų
(dimension chain nepilnai įskaitomas) — tikslinti" and „… matmenys įvertinti iš
planų ir išklotinių, confidence žema" — the model writes the English words its
prompt teaches it back into Lithuanian sentences. extractor/model_warnings.py
`plain_words` is a small glossary for the words the stored readings carry
(ground_truth/*/ai_extract.json and the local projects): whole words, in a
Lithuanian sentence, never inside quoted drawing text, a code or a room's name,
numbers untouched, and the two machine readers of these texts read the same.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from extractor.height_markers import salvage_heights_from_warnings
from extractor.model_warnings import normalise_model_warnings, plain_numbers, plain_words, room_identifiers
from extractor.model_warnings import enumerated_led_rooms

ROOMS = [
    {"nr": "101", "pavadinimas": "Tambūras", "paskirtis": "tamburas"},
    {"nr": "102", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"},
    {"nr": "103", "pavadinimas": "Koridorius", "paskirtis": "koridorius"},
]
# What the glossary covers — none of it may survive a rewrite.
LEAKED = re.compile(r"(?<![\w'’`])(?:dimension|confidence|default|fallback|count|inline)(?![\w`])",
                    re.IGNORECASE)


# ── what changes ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,want", [
    # the two walkthrough sentences
    ("Perimetrai daugumai patalpų apskaičiuoti iš ploto ir dalinių matmenų "
     "(dimension chain nepilnai įskaitomas) — tikslinti",
     "Perimetrai daugumai patalpų apskaičiuoti iš ploto ir dalinių matmenų "
     "(matmenų grandinė nepilnai įskaitoma) — tikslinti"),
    ("Langų ir durų specifikacijos lentelės projekte nėra; matmenys įvertinti iš planų "
     "ir išklotinių, confidence žema",
     "Langų ir durų specifikacijos lentelės projekte nėra; matmenys įvertinti iš planų "
     "ir išklotinių, patikimumas žemas"),
    # the stored readings
    ("Išklotinių lapo nėra - low confidence; spėta pagal paskirtį (dažymas)",
     "Išklotinių lapo nėra - žemas patikimumas; spėta pagal paskirtį (dažymas)"),
    ("Pjūvis nerastas - lubų aukštis priimtas default 2.82m gyvenamosioms patalpoms",
     "Pjūvis nerastas - lubų aukštis priimtas numatytasis 2.82m gyvenamosioms patalpoms"),
    ("lubų aukščiai visose patalpose neišmatuoti, naudotas fallback 2.82 m (san. mazguose 2.50 m).",
     "lubų aukščiai visose patalpose neišmatuoti, naudotas numatytasis 2.82 m (san. mazguose 2.50 m)."),
    ("Rozečių/šviestuvų count'as agreguotas iš puslapių 4-8; galimas ±10% netikslumas.",
     "Rozečių/šviestuvų skaičius agreguotas iš puslapių 4-8; galimas ±10% netikslumas."),
    ("Simbolių count yra apytikslis (±2vnt) dėl tankaus elektros plano.",
     "Simbolių skaičius yra apytikslis (±2vnt) dėl tankaus elektros plano."),
    ("patalpų plotai imti iš lubų plano inline žymų (psl. 4).",
     "patalpų plotai imti iš lubų plano žymų (psl. 4)."),
    ("Sienų dimension chain'ų su bendrais patalpos ilgiais nesimato.",
     "Sienų matmenų grandinių su bendrais patalpos ilgiais nesimato."),
    ("koridoriaus sienų dimension chain nematomas, todėl perimetras nepatikslintas.",
     "koridoriaus sienų matmenų grandinė nematoma, todėl perimetras nepatikslintas."),
    ("Sienų dimension chains nematomi.", "Sienų matmenų grandinės nematomos."),
    ("Matomos dimension grandinės: viršutinė siena.", "Matomos matmenų grandinės: viršutinė siena."),
    # the level in either order, with its separator; the case follows the model's
    ("Confidence: high — aukštis iš pjūvio.", "Patikimumas: aukštas — aukštis iš pjūvio."),
    ("Plotas iš plano, confidence – vidutinė.", "Plotas iš plano, patikimumas – vidutinis."),
    ("Aukštis spėtas, žema confidence.", "Aukštis spėtas, žemas patikimumas."),
    ("Durų matmenys neanotuoti, confidence'as žemas.", "Durų matmenys neanotuoti, patikimumas žemas."),
    ("Šiam įvertinimui confidence nedidelis.", "Šiam įvertinimui patikimumas nedidelis."),
])
def test_the_leaked_words_read_lithuanian(raw, want):
    assert plain_words(raw, ROOMS) == want
    assert not LEAKED.search(want)


@pytest.mark.parametrize("raw", [
    # not a Lithuanian sentence — its only Lithuanian letters are a quote or a room's name
    "Window count unknown, low confidence",
    "Room „Svetainė“ count unknown, low confidence",
    "Svetainė: window count unknown, low confidence",
    # the drawing's own quoted text, a code, a setting's code name
    "Lape parašyta „dimension chain“ — palikta, kaip įrašyta.",
    "Laukas `confidence` užpildytas, žr. confidence_zoom ir plotas_saltinis=inline_label.",
    "Durų count_vnt neužpildytas, default_fallback taikytas.",
    # inside another word, or an ending the glossary does not know
    "Sąskaitos account ir counter nėra; inlined žymės, defaults lentelė.",
    "Sienų dimension chain'uką sunku įžiūrėti.",
    # default / fallback with no value after them — „numatytasis" would not agree
    "Taikyta default reikšmė lubų aukščiui.",
])
def test_what_the_glossary_does_not_know_stays_as_written(raw):
    assert plain_words(raw, ROOMS) == raw


def test_a_room_called_by_a_glossary_word_is_his_name():
    rooms = [{"nr": "5", "pavadinimas": "Count kambarys", "paskirtis": "gyvenamoji"}]
    raw = "Patalpa „Count kambarys“ ir Count kambarys — plotas iš plano, count'as tikslus."
    assert plain_words(raw, rooms) == ("Patalpa „Count kambarys“ ir Count kambarys — plotas iš "
                                       "plano, skaičius tikslus.")


def test_a_rewrite_a_reader_would_read_differently_is_not_made():
    # „aukštas patikimumas" puts „aukš" in the sentence, and the height salvage
    # then reads 5,70 m as a narrated double height for Svetainė — it did not
    # before. The text stays as the model wrote it.
    raw = "Svetainė 5,70 m pagal vizualizaciją — high confidence."
    assert salvage_heights_from_warnings([raw], ROOMS) == {}
    assert plain_words(raw, ROOMS) == raw
    assert plain_words(raw, []) == "Svetainė 5,70 m pagal vizualizaciją — aukštas patikimumas."


@pytest.mark.parametrize("raw", [
    "LED nišos kambariuose 101, 102 (dimension chain nematomas), confidence žema.",
    "Svetainėje +3400, koridoriuje 2.80 m — default 2.82 čia netaikytas, count'as 3.",
])
def test_numbers_and_the_machine_readers_are_untouched(raw):
    out = plain_words(raw, ROOMS)
    assert out != raw
    assert re.findall(r"\d+(?:[.,]\d+)*", out) == re.findall(r"\d+(?:[.,]\d+)*", raw)
    assert enumerated_led_rooms([out]) == enumerated_led_rooms([raw])
    assert salvage_heights_from_warnings([out], ROOMS) == salvage_heights_from_warnings([raw], ROOMS)


# ── wired into the one pass over the model's warnings ────────────────────────

def test_the_models_warnings_get_both_passes_and_the_pipelines_none():
    model = {"level": "WARN", "message": "Pjūvio nėra — priimtas default 2.82 m, confidence žema."}
    model_str = "Sienų dimension chain nematomas."
    pipeline = {"level": "WARN", "code": "x", "message": "Mūsų tekstas: confidence žema, 2.82 m."}
    parsed = {"patalpos": ROOMS, "warnings": [model, model_str]}
    captured = list(parsed["warnings"])
    parsed["warnings"] = parsed["warnings"] + [pipeline]
    assert normalise_model_warnings(parsed, captured) == 2
    assert parsed["warnings"] == [
        {"level": "WARN", "message": "Pjūvio nėra — priimtas numatytasis 2,82 m, patikimumas žemas."},
        "Sienų matmenų grandinė nematoma.",
        {"level": "WARN", "code": "x", "message": "Mūsų tekstas: confidence žema, 2.82 m."},
    ]


def test_no_stored_model_warning_keeps_a_glossary_word():
    root = Path(__file__).resolve().parents[2]
    fixtures = sorted((root / "ground_truth").glob("*/ai_extract.json"))
    assert fixtures, "no corpus fixture to scan — this test would pass vacuously"
    rewritten = 0
    for fixture in fixtures:
        src = json.loads(fixture.read_text(encoding="utf-8"))
        rooms = [r for r in src.get("patalpos") or [] if isinstance(r, dict)]
        ids = room_identifiers(rooms)
        for w in src.get("warnings") or []:
            raw = w.get("message") if isinstance(w, dict) else w
            if not isinstance(raw, str):
                continue
            out = plain_numbers(plain_words(raw, rooms), ids, rooms)
            if re.search(r"[ąčęėįšųūž]", raw, re.IGNORECASE):
                left = [m.group(0) for m in LEAKED.finditer(_drop_codes(out))]
                assert not left, f"{fixture.parent.name}: {left} — {out}"
            rewritten += plain_words(raw, rooms) != raw
    assert rewritten >= 3, f"only {rewritten} stored warnings rewritten — is the corpus still the one measured?"


def _drop_codes(text: str) -> str:
    """A setting's code name is not a word of the sentence (`plotas_saltinis=inline_label`)."""
    return re.sub(r"[\w.]+_[\w.]+|`[^`]*`", "", text)

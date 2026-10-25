"""The reading model's own warnings, in the numbers his screen writes (2026-10-06).

A production reading of objektas_a listed, under „Verta patikrinti":
„Trijų +3400 žymeklių priskyrimas tarp 101 ir 102 nėra visiškai vienareikšmis;
priimta 101=3.40 ir 102=3.40." — the model's own sentence, shown as written.
extractor/model_warnings.py rewrites the model-written texts only: decimal
commas, „101 — 3,40 m". Codes, dates, page and section numbers, the drawing's
quoted text and the project's room numbers stay exactly as written, and the
two steps that read these texts by machine read the same thing afterwards.
"""
from __future__ import annotations

import pytest

from extractor.height_markers import salvage_heights_from_warnings
from extractor.model_warnings import normalise_model_warnings, plain_numbers, room_identifiers
from extractor.model_warnings import enumerated_led_rooms

ROOMS = [
    {"nr": "101", "pavadinimas": "Tambūras", "paskirtis": "tamburas"},
    {"nr": "102", "pavadinimas": "Svetainė/virtuvė", "paskirtis": "gyvenamoji"},
    {"nr": "103", "pavadinimas": "Koridorius", "paskirtis": "koridorius"},
    {"nr": "106", "pavadinimas": "Skalbykla", "paskirtis": "skalbykla"},
]
IDS = room_identifiers(ROOMS)
DOTTED_ROOMS = [{"nr": "1.01", "pavadinimas": "Holas"}, {"nr": "1.03", "pavadinimas": "Vonia"},
                {"nr": "2.05", "pavadinimas": "Miegamasis"}]


def plain(text: str, rooms=ROOMS) -> str:
    return plain_numbers(text, room_identifiers(rooms), rooms)


# ── what changes ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,want", [
    # the production sentence
    ("Trijų +3400 žymeklių priskyrimas tarp 101 ir 102 nėra visiškai vienareikšmis; "
     "priimta 101=3.40 ir 102=3.40.",
     "Trijų +3400 žymeklių priskyrimas tarp 101 ir 102 nėra visiškai vienareikšmis; "
     "priimta 101 — 3,40 m ir 102 — 3,40 m."),
    # corpus texts the model wrote (ground_truth/*/ai_extract.json)
    ("Svetainė/valgomasis/virtuvė turi dvigubo aukščio lubas (~5.7m pagal vizualizacijas ir lubų planą)",
     "Svetainė/valgomasis/virtuvė turi dvigubo aukščio lubas (~5,7m pagal vizualizacijas ir lubų planą)"),
    ("Pjūvis nerastas - lubų aukštis priimtas default 2.82m gyvenamosioms patalpoms",
     "Pjūvis nerastas - lubų aukštis priimtas default 2,82m gyvenamosioms patalpoms"),
    ("faktinis aukštis miegamajame ir svetainėje ~2.66m, sanitariniame mazge ir koridoriuje ~2.39m",
     "faktinis aukštis miegamajame ir svetainėje ~2,66m, sanitariniame mazge ir koridoriuje ~2,39m"),
    ("naudotas fallback 2.82 m (san. mazguose 2.50 m). Būtina patikslinti vietoje.",
     "naudotas fallback 2,82 m (san. mazguose 2,50 m). Būtina patikslinti vietoje."),
    ("Eksplikacijoje 1A bendras plotas 170.67m², 2A 97.04m², iš viso 267.71m²",
     "Eksplikacijoje 1A bendras plotas 170,67m², 2A 97,04m², iš viso 267,71m²"),
    ("Bendras eksplikacijos plotas 165.61 m² deklaruotas; individualių plotų suma atitinka.",
     "Bendras eksplikacijos plotas 165,61 m² deklaruotas; individualių plotų suma atitinka."),
    # the room-number = height form, with and without its unit, spaced, in brackets
    ("Aukščiai: 103 = 3.0 m; (106=2.75).", "Aukščiai: 103 — 3,0 m; (106 — 2,75 m)."),
    ("Aukštis 101=3,40.", "Aukštis 101 — 3,40 m."),
    # an unquoted drafting marker is a number in his sentence
    ("Lubų plane žymė +2.800 ties 102.", "Lubų plane žymė +2,800 ties 102."),
    # dimensions and slopes
    ("GKP 1200x2500x12.5 mm, nuolydis 1:1.5", "GKP 1200x2500x12,5 mm, nuolydis 1:1,5"),
])
def test_the_model_text_reads_like_his_screen(raw, want):
    assert plain(raw) == want
    assert plain(want) == want                                   # once is enough


# ── what must NOT change ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw", [
    "Pagal STR 2.04.01:2018 ir LST EN 13964:2014 — drėgnų patalpų hidroizoliacija.",
    "Brėžinio laida 2025.04.02, keista 2025.05.",                 # dates
    "Žr. psl. 2.3 ir lapas 4.1; apdaila — 4.1–5.1 punktas.",       # page, sheet, section numbers
    "Durys D-2.1 ir mazgas M-3.2, lango tipas A1.2.",               # codes with letters in front
    "Pjūvio žymeklis „+2.800“ ir užrašas \"H=2.65\" lieka, kaip brėžinyje.",  # the drawing's quoted text
    "Lubų aukščiai struktūrizuoti: 1 aukšte 3,00m (iš lubų plano '+300cm')",  # already plain
    "LED juostos (karnizo nišos) 20cm gylio matomos kambariuose 01, 03, 04, 05",
    "Plytelės iki lubų vonioje 107, 111 ir skalbykloje 106",
    "Grindų dangų suma (76,65 + 3,70 + 3,95 = 84,30 m²) didesnė už patalpų plotų sumą.",
    "102=+3400 — žymeklis be kablelio lieka žymekliu.",            # not metres: not a room height
    "Premium archetipas: paslėptos durys, LED nišos, dideli formatai plytelių (1200x1200, 2800x1200)",
    "",
])
def test_codes_dates_references_and_quotes_stay_as_written(raw):
    assert plain(raw) == raw


def test_a_number_the_project_has_no_room_for_is_not_a_room_height():
    # „300=3.00" is centimetres = metres, not a room: only the decimal changes
    assert plain("Aukštis 300=3.00 pagal pjūvį.") == "Aukštis 300=3,00 pagal pjūvį."
    # …and a value no ceiling has is not a height either
    assert plain("Nuolydis 103=0.30.") == "Nuolydis 103=0,30."
    # with no rooms known, nothing is read as a room
    assert plain_numbers("priimta 101=3.40", (), []) == "priimta 101=3,40"


def test_his_dotted_room_numbers_are_numbers_of_rooms_not_decimals():
    raw = "LED nišos matomos kambariuose 1.01, 1.03 ir 2.05; patalpos 1.01 aukštis 2.70 m."
    want = "LED nišos matomos kambariuose 1.01, 1.03 ir 2.05; patalpos 1.01 aukštis 2,70 m."
    assert plain(raw, DOTTED_ROOMS) == want
    # a list after „kambariuose" is rooms even when the project lists other numbers
    assert plain("LED nišos kambariuose 3.01, 3.02", DOTTED_ROOMS) == "LED nišos kambariuose 3.01, 3.02"
    # a room number = height, the room number kept as his
    assert plain("1.03=2.50; Kambario 1.01 plotas 12.5 m².", DOTTED_ROOMS) == \
        "1.03 — 2,50 m; Kambario 1.01 plotas 12,5 m²."


# ── meaning: the machine readers of these texts read the same ──────────────

_READER_TEXTS = [
    "LED nišos matomos kambariuose 1.01, 1.03 ir 2.05; patalpos 1.01 aukštis 2.70 m.",
    "LED nišos kambariuose 01, 03, 2.5 m ilgio",
    "Svetainė/virtuvė turi +3400 lubas, koridorius 2.80 m.",
    "Svetainė/virtuvė 102=3.40, kitur 2.80 m.",
    "Tambūras 2.95 m aukščio; Skalbykla 2.6 m.",
]


@pytest.mark.parametrize("raw", _READER_TEXTS)
def test_the_led_gate_and_the_height_salvage_read_the_same(raw):
    for rooms in (ROOMS, DOTTED_ROOMS):
        out = plain(raw, rooms)
        assert enumerated_led_rooms([out]) == enumerated_led_rooms([raw]), out
        assert salvage_heights_from_warnings([out], rooms) == salvage_heights_from_warnings([raw], rooms), out


def test_a_rewrite_a_reader_would_read_differently_is_not_made():
    # Without the fail-safe the LED gate would read „2,5" as the rooms „2" and „5".
    raw = "LED nišos kambariuose 01, 03, 2.5 m ilgio"
    assert enumerated_led_rooms([raw]) == {"01", "03", "2.5"}
    assert plain(raw) == raw
    # The height salvage would newly read „3,40 m" for the named room: the
    # room-height form is skipped and only the decimal changes.
    raw = "Svetainė/virtuvė 102=3.40, kitur 2.80 m."
    out = plain(raw)
    assert salvage_heights_from_warnings([out], ROOMS) == salvage_heights_from_warnings([raw], ROOMS)
    assert out == "Svetainė/virtuvė 102=3,40, kitur 2,80 m."


# ── model-written texts only ─────────────────────────────────────────────────

def test_only_the_models_own_entries_are_rewritten():
    model = {"level": "WARN", "message": "Pjūvis nerastas — priimta 2.82 m."}
    model_str = "Lubų aukštis 2.70 m pagal pjūvį."
    pipeline = {"level": "WARN", "code": "x", "message": "Mūsų tekstas su 2.82 m lieka nepaliestas."}
    parsed = {"patalpos": ROOMS, "warnings": [model, model_str]}
    captured = list(parsed["warnings"])                 # what Pass 1 returned
    parsed["warnings"] = parsed["warnings"] + [pipeline]  # a later step appends its own note
    assert normalise_model_warnings(parsed, captured) == 2
    assert parsed["warnings"] == [
        {"level": "WARN", "message": "Pjūvis nerastas — priimta 2,82 m."},
        "Lubų aukštis 2,70 m pagal pjūvį.",
        {"level": "WARN", "code": "x", "message": "Mūsų tekstas su 2.82 m lieka nepaliestas."},
    ]
    assert model["message"] == "Pjūvis nerastas — priimta 2,82 m."     # in place: one object
    # nothing captured / no list: nothing to do
    assert normalise_model_warnings(parsed, []) == 0
    assert normalise_model_warnings({"warnings": None}, captured) == 0


def test_the_extraction_runs_it_on_pass1_warnings_before_the_checks():
    """Wired where the model's warnings are taken into the result: captured
    right after Pass 1, rewritten at Step 3.9 — after the height salvage and the
    LED gate read them, before `apply_lt_sanity` and the list's mirror."""
    import inspect

    from extractor import vision_call as vc
    src = inspect.getsource(vc.extract_interior)
    capture = src.index("_model_warnings = list(parsed[\"warnings\"])")
    assert src.index("_run_pass1_once(") < capture < src.index("salvage_heights_from_warnings")
    run = src.index("normalise_model_warnings(parsed, _model_warnings)")
    assert src.index("_recompute_per_room_via_python(parsed, rules_override)") < run
    assert run < src.index("apply_lt_sanity(parsed)") < src.index("build_lt_sanity(parsed)")

"""Room-name → paskirtis vocabulary sweep (2026-08-23).

WHY THIS FILE EXISTS
    Every accuracy number we quote comes from four projects by one contractor.
    A drawing from a designer we have never seen drifts exactly where the code
    keys on OUR projects' words: `normalize_paskirtis` used to be sixteen
    substring rules covering the labels those four projects happen to use.
    Running 114 real Lithuanian room labels through it found 47 that fell to
    the generic living-room default and 8 that landed on an outright WRONG
    class — "Vonios kambarys" was billed as a living room (no tile, no
    waterproofing, parquet floor) because the old needle was the exact string
    "vonia", and "vonios" does not contain it.

WHAT IT PINS
    1. the label → class table itself, one parametrized case per label;
    2. that every class the classifier can emit has an explicit
       ROOM_TYPE_RULES entry (no silent gyvenamoji fallback);
    3. that every value the Vision RoomType enum may emit resolves;
    4. the downstream consequences that actually move money — wet-room flags,
       unpainted exterior/sauna rooms, tile bands, LED ratios;
    5. a DIFFERENTIAL guard: the paskirtis values in the benchmark corpus must
       keep resolving to the class they resolved to before the sweep, so a
       future vocabulary edit cannot silently move the eval numbers.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.line_items import WET_ROOM_PASKIRTIS  # noqa: E402
from extractor.universal_rules import (  # noqa: E402
    ROOM_TYPE_RULES,
    classify_room_name,
    fold_room_label,
    normalize_paskirtis,
)

# ── 1. THE TABLE ───────────────────────────────────────────────────────────
# (label as it appears on a Lithuanian drawing, expected canonical class)
VOCABULARY: list[tuple[str, str]] = [
    # circulation / entry
    ("Holas", "holas"),
    ("HOLAS", "holas"),
    ("Hallas", "holas"),
    ("Vestibiulis", "holas"),
    ("Prieškambaris", "holas"),
    ("Prieskambaris", "holas"),
    ("Fojė", "holas"),
    ("Foje", "holas"),
    ("Priimamasis", "holas"),
    ("Laiptų holas", "holas"),
    ("Tambūras", "tamburas"),
    ("Tamburas", "tamburas"),
    ("TAMBŪRAS", "tamburas"),
    ("Tamb.", "tamburas"),
    ("Koridorius", "koridorius"),
    ("KORIDORIUS", "koridorius"),
    ("Koridorius 1", "koridorius"),
    ("Kor.", "koridorius"),
    ("Kor. 2", "koridorius"),
    ("Įėjimo koridorius", "koridorius"),
    ("Ijimo koridorius", "koridorius"),
    ("Laiptinė", "laiptine"),
    ("Laiptine", "laiptine"),
    ("Laiptai", "laiptine"),
    # living
    ("Svetainė", "gyvenamoji"),
    ("Svetaine", "gyvenamoji"),
    ("SVETAINĖ", "gyvenamoji"),
    ("Svet.", "gyvenamoji"),
    ("Kambarys", "gyvenamoji"),
    ("Kamb.", "gyvenamoji"),
    ("Kamb. 3", "gyvenamoji"),
    ("Poilsio kambarys", "gyvenamoji"),
    ("Žaidimų kambarys", "gyvenamoji"),
    ("Sporto salė", "gyvenamoji"),
    ("Kino salė", "gyvenamoji"),
    ("Mansarda", "gyvenamoji"),
    ("Svetainė-virtuvė", "virtuve"),
    ("Svetainė/virtuvė", "virtuve"),
    ("Virtuvė-valgomasis", "virtuve"),
    ("Virtuvė", "virtuve"),
    ("Virtuve", "virtuve"),
    ("VIRTUVĖ", "virtuve"),
    ("Virt.", "virtuve"),
    ("Valgomasis", "valgomasis"),
    ("Miegamasis", "miegamoji"),
    ("Miegamoji", "miegamoji"),
    ("MIEGAMASIS", "miegamoji"),
    ("Mieg.", "miegamoji"),
    ("Tėvų miegamasis", "miegamoji"),
    ("Tevu miegamasis", "miegamoji"),
    ("Vaikų kambarys", "miegamoji"),
    ("Svečių kambarys", "miegamoji"),
    ("Berniuko kambarys", "miegamoji"),
    ("Mergaitės kambarys", "miegamoji"),
    ("Darbo kambarys", "kabinetas"),
    ("Kabinetas", "kabinetas"),
    ("Biblioteka", "kabinetas"),
    ("Ofisas", "kabinetas"),
    ("Posėdžių salė", "kabinetas"),
    # wet
    ("Vonia", "vonia"),
    ("Vonia 1", "vonia"),
    ("Vonios kambarys", "vonia"),
    ("Von.", "vonia"),
    ("Dušas", "vonia"),
    ("Dušinė", "vonia"),
    ("Dusine", "vonia"),
    ("Dušo kambarys", "vonia"),
    ("San. mazgas", "san"),
    ("San.mazgas", "san"),
    ("Sanmazgas", "san"),
    ("Sanitarinis mazgas", "san"),
    ("S.M.", "san"),
    ("Prausykla", "san"),
    ("WC", "wc"),
    ("Wc", "wc"),
    ("Tualetas", "wc"),
    ("Pirtis", "pirtis"),
    ("Sauna", "pirtis"),
    ("Garinė pirtis", "pirtis"),
    ("Baseinas", "baseinas"),
    ("Skalbykla", "skalbykla"),
    ("Skalbykla-džiovykla", "skalbykla"),
    # storage / service
    ("Drabužinė", "drabuzine"),
    ("Drabuzine", "drabuzine"),
    ("Drab.", "drabuzine"),
    ("Rūbinė", "drabuzine"),
    ("Rubine", "drabuzine"),
    ("Rūbų kambarys", "drabuzine"),
    ("Spinta", "drabuzine"),
    ("Sandėliukas", "sandeliukas"),
    ("Sandėlis", "sandeliukas"),
    ("Sandeliukas", "sandeliukas"),
    ("Sand.", "sandeliukas"),
    ("Ūkinė patalpa", "sandeliukas"),
    ("Pagalbinė patalpa", "sandeliukas"),
    ("Rūsys", "sandeliukas"),
    ("Palėpė", "sandeliukas"),
    ("Katilinė", "katiline"),
    ("Katiline", "katiline"),
    ("Šilumos punktas", "katiline"),
    ("Techninė patalpa", "techpatalpa"),
    ("Tech. patalpa", "techpatalpa"),
    ("Techpatalpa", "techpatalpa"),
    ("Dirbtuvės", "techpatalpa"),
    ("Tarnybinė patalpa", "techpatalpa"),
    ("Valymo patalpa", "techpatalpa"),
    ("Garažas", "garazas"),
    ("Garazas", "garazas"),
    ("Gar.", "garazas"),
    # exterior
    ("Terasa", "terasa"),
    ("Atvira terasa", "terasa"),
    ("Balkonas", "terasa"),
    ("Lodžija", "terasa"),
    ("Lodzija", "terasa"),
    ("Veranda", "terasa"),
    ("Žiemos sodas", "terasa"),
]


@pytest.mark.parametrize("label,expected", VOCABULARY,
                         ids=[lbl for lbl, _ in VOCABULARY])
def test_room_label_classifies(label, expected):
    assert normalize_paskirtis(label) == expected


@pytest.mark.parametrize("label,expected", VOCABULARY,
                         ids=[lbl for lbl, _ in VOCABULARY])
def test_every_classified_label_has_explicit_rules(label, expected):
    """No label in the table may reach the silent `or ROOM_TYPE_RULES
    ["gyvenamoji"]` fallback — that fallback is how a terrace got billed as a
    painted living room."""
    assert expected in ROOM_TYPE_RULES, (
        f"{label!r} → {expected!r} has no ROOM_TYPE_RULES entry")


def test_vocabulary_table_is_at_least_eighty_labels():
    """Guard against someone trimming the sweep back to our four projects'
    words."""
    assert len(VOCABULARY) >= 80


# ── 2. THE VISION SCHEMA CONTRACT ──────────────────────────────────────────
# Exactly the enum in extractor/prompt.py (Room.paskirtis). Anything Vision is
# ALLOWED to emit must land on a class we have finishing rules for.
ROOMTYPE_ENUM = [
    "gyvenamoji", "miegamoji", "virtuve", "vonia", "wc", "san", "koridorius",
    "holas", "drabuzine", "rubine", "katiline", "skalbykla", "valgomasis",
    "tamburas", "garazas", "sandeliukas", "kabinetas", "terasa", "lodzija",
    "techpatalpa", "laiptai", "laiptine",
]


@pytest.mark.parametrize("enum_value", ROOMTYPE_ENUM)
def test_vision_enum_value_resolves_to_known_rules(enum_value):
    cls = normalize_paskirtis(enum_value)
    assert cls in ROOM_TYPE_RULES, (
        f"Vision may emit paskirtis={enum_value!r}; it normalises to {cls!r} "
        f"which has no ROOM_TYPE_RULES entry and silently gets living-room "
        f"finishes")


def test_prompt_enum_and_test_list_agree():
    """If someone widens the Vision enum, this test drags the vocabulary
    sweep along with it instead of letting the new value drift."""
    from extractor.prompt import OUTPUT_SCHEMA
    schema_enum = (OUTPUT_SCHEMA["properties"]["patalpos"]["items"]
                   ["properties"]["paskirtis"]["enum"])
    assert sorted(schema_enum) == sorted(ROOMTYPE_ENUM)


# ── 3. DIFFERENTIAL GUARD ──────────────────────────────────────────────────
# Every paskirtis value present in the six ground-truth extracts, with the
# class it resolved to BEFORE the 2026-08-23 sweep. The eval gate (corpus MAE
# 7.82%, per-project 3.10 / 19.64 / 7.46 / 2.26) is only meaningful while
# these stay put.
CORPUS_PASKIRTYS = {
    "tamburas": "tamburas",
    "valgomasis": "valgomasis",
    "koridorius": "koridorius",
    "kabinetas": "kabinetas",
    "garazas": "garazas",
    "skalbykla": "skalbykla",
    "san": "san",
    "miegamoji": "miegamoji",
    "gyvenamoji": "gyvenamoji",
    "virtuve": "virtuve",
    "drabuzine": "drabuzine",
    "vonia": "vonia",
    "wc": "wc",
    "techpatalpa": "techpatalpa",
    "rubine": "drabuzine",   # legacy: "rubin" needle predates the sweep
    "holas": "holas",
    "katiline": "katiline",
    "sandeliukas": "sandeliukas",
}


@pytest.mark.parametrize("value,expected", sorted(CORPUS_PASKIRTYS.items()))
def test_corpus_paskirtis_class_is_frozen(value, expected):
    assert normalize_paskirtis(value) == expected


def test_corpus_classes_keep_their_pre_sweep_finish_rules():
    """kabinetas and techpatalpa gained EXPLICIT ROOM_TYPE_RULES entries in the
    sweep. Both were previously served by the implicit gyvenamoji fallback, so
    the new entries must be byte-equal to gyvenamoji or the eval moves."""
    for cls in ("kabinetas", "techpatalpa"):
        assert ROOM_TYPE_RULES[cls] == ROOM_TYPE_RULES["gyvenamoji"], (
            f"{cls} rules diverged from the pre-sweep fallback — rerun "
            f"eval_harness.py --totals-only --recompute before accepting")


# ── 4. DOWNSTREAM CONSEQUENCES ─────────────────────────────────────────────

def test_exterior_rooms_get_no_interior_finishes():
    """Terasa / balkonas / lodžija sit outside the thermal envelope. Billing
    them as painted GKP rooms with a parquet floor was the worst over-bill the
    sweep found."""
    rules = ROOM_TYPE_RULES["terasa"]
    assert rules["walls_paint"] == 0.0
    assert rules["ceiling_type"] == "betonas"   # trips the ceiling-unfinished gate
    assert rules["tile_floor"] is False
    assert rules["tile_walls_to_m"] == 0


def test_sauna_is_wet_and_unpainted():
    rules = ROOM_TYPE_RULES["pirtis"]
    assert rules["walls_paint"] == 0.0
    assert rules["ceiling_type"] == "medis"     # wood lining, never painted
    assert rules["tile_floor"] is True
    assert "pirtis" in WET_ROOM_PASKIRTIS


def test_stairwell_is_painted_circulation():
    rules = ROOM_TYPE_RULES["laiptine"]
    assert rules["walls_paint"] == 1.0
    assert rules["ceiling_type"] == "gkp"


@pytest.mark.parametrize("label", [
    "Vonios kambarys", "Dušinė", "San. mazgas", "WC", "Pirtis", "Baseinas",
    "Skalbykla", "Katilinė",
])
def test_wet_labels_reach_the_waterproofing_lane(label):
    """`line_items._is_wet_room` drives hidroizoliacija. Before the sweep this
    keyed on the raw lowercased paskirtis, so "Vonios kambarys" got none."""
    from extractor.line_items import _is_wet_room
    assert _is_wet_room({"paskirtis": label}) is True


@pytest.mark.parametrize("label", [
    "Vonios kambarys", "Dušinė", "San. mazgas", "WC", "Pirtis", "Baseinas",
    "Skalbykla",
])
def test_wet_labels_reach_the_OTHER_waterproofing_lane_too(label):
    """The test above pins `line_items`, which serves /api/recompute-quantities
    (Prielaidos). It is NOT the lane /extract-interior and /recompute-interior
    use — that one is `vision_call._calc_hidroizoliacija_m2`, and on
    2026-08-23 only the first was widened. A sauna project then reported 0 m²
    hidroizoliacija in the estimate and ~62 m² after one Prielaidos slider.
    Both lanes are live, so both are pinned here; `katiline` is deliberately
    absent because it has never been waterproofed in the extract lane.
    """
    from extractor.vision_call import _calc_hidroizoliacija_m2
    room = {"paskirtis": label, "plotas_m2": 12.0, "lubu_aukstis_m": 2.7}
    assert _calc_hidroizoliacija_m2(room, 14.0) > 0


@pytest.mark.parametrize("label", ["Svetainė", "Miegamasis", "Terasa", "Garažas"])
def test_dry_labels_do_not_reach_the_extract_waterproofing_lane(label):
    from extractor.vision_call import _calc_hidroizoliacija_m2
    room = {"paskirtis": label, "plotas_m2": 12.0, "lubu_aukstis_m": 2.7}
    assert _calc_hidroizoliacija_m2(room, 14.0) == 0.0


@pytest.mark.parametrize("label,cls", [
    ("Svetainė su spinta", "gyvenamoji"),
    ("Koridorius su spinta", "koridorius"),
    ("Valgomasis su spinta", "valgomasis"),
    ("Miegamasis su spinta", "miegamoji"),
])
def test_a_wardrobe_in_the_label_does_not_replace_the_room(label, cls):
    """"spinta" is furniture. Placed above the room words it swallowed every
    "<room> su spinta" label into `drabuzine`, whose LED niche ratio is 0.00 —
    so the LED strip metres for a living room with a fitted wardrobe silently
    became zero. It must be the LAST needle consulted."""
    assert normalize_paskirtis(label) == cls


def test_kitchen_with_a_wardrobe_keeps_its_backsplash():
    assert normalize_paskirtis("Virtuvė su spinta") == "virtuve"
    assert ROOM_TYPE_RULES["virtuve"]["tile_walls_to_m"] == 0.6
    assert ROOM_TYPE_RULES["virtuve"]["tile_floor"] is True


@pytest.mark.parametrize("label", [
    "Spinta", "Rūbinė-spinta", "Drabužinė / spinta zona prie miegamojo",
])
def test_a_label_that_is_only_a_wardrobe_still_classifies(label):
    """Moving the needle last must not lose the cases it was added for —
    including the one that really is in the corpus."""
    assert normalize_paskirtis(label) == "drabuzine"


@pytest.mark.parametrize("label", ["Svetainė", "Miegamasis", "Terasa", "Garažas"])
def test_dry_labels_do_not_reach_the_waterproofing_lane(label):
    from extractor.line_items import _is_wet_room
    assert _is_wet_room({"paskirtis": label}) is False


def test_blank_paskirtis_is_not_promoted_to_a_wet_room():
    from extractor.line_items import _is_wet_room
    assert _is_wet_room({"paskirtis": ""}) is False
    assert _is_wet_room({}) is False


def test_bathroom_family_keeps_its_tile_band():
    for cls in ("vonia", "wc", "san"):
        assert ROOM_TYPE_RULES[cls]["tile_walls_to_m"] == 2.0
        assert ROOM_TYPE_RULES[cls]["tile_floor"] is True


def test_pool_is_not_in_the_bathroom_family():
    """The santechnika lane bills one klozetas + WC rėmas per vonia/wc/san
    room. A pool hall is tiled and wet but it is not a toilet."""
    assert normalize_paskirtis("Baseinas") == "baseinas"
    assert "baseinas" not in ("vonia", "wc", "san")
    assert ROOM_TYPE_RULES["baseinas"]["tile_floor"] is True


# (The LED-ratio checks went with the room-type niche estimator — v4 3b, 2026-10-25.)


# ── 5. THE FOLDER + THE "DON'T GUESS" CONTRACT ─────────────────────────────

@pytest.mark.parametrize("raw,folded", [
    ("San. mazgas", "san mazgas"),
    ("Kor.", "kor"),
    ("S.M.", "s m"),
    ("Svetainė/virtuvė", "svetaine virtuve"),
    ("TAMBŪRAS", "tamburas"),
    ("  Vonia  ", "vonia"),
])
def test_fold_room_label(raw, folded):
    assert fold_room_label(raw) == folded


def test_single_letter_k_is_deliberately_not_guessed():
    """On LT plans a bare "K." is used for kambarys, koridorius AND katilinė.
    Guessing is worse than the generic default, so it must pass through."""
    assert normalize_paskirtis("K.") == "k."


def test_unknown_label_passes_through_unchanged():
    """The pre-sweep contract: an unrecognised value is returned lowercased
    and stripped, and callers keep their gyvenamoji fallback."""
    assert normalize_paskirtis("  Zonzonas  ") == "zonzonas"
    assert normalize_paskirtis("") == "gyvenamoji"


def test_classify_room_name_prefers_an_explicit_paskirtis():
    assert classify_room_name("Vonia", "miegamoji") == "miegamoji"
    # …but falls back to the NAME when the paskirtis is junk or missing.
    assert classify_room_name("Vonios kambarys", None) == "vonia"
    assert classify_room_name("Vonios kambarys", "zonzonas") == "vonia"

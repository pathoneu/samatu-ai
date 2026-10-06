"""Round 12 (2026-10-03): rows that were invented and shown as read.

  • calc-engine-6 — every vonia/san got a walk-in shower (zone, slope, drain,
    mixer, shelves) with no count and no disclosure;
  • vision-pipeline-7 — sanitary rows were room-type counts, ignored the
    plumbing reader, and showed green;
  • vision-pipeline-1 — LED niche lengths estimated from the room type were
    billed on three rows and shown green;
  • calc-engine-5 — the screen described the corner metres as „išoriniai
    kampai × aukštis", which is not what the engine adds up.
"""
from __future__ import annotations

import copy

import pytest

from extractor.confidence import (
    KAMPAI_REASON, ROOM_DEFAULT_REASON, apply_confidence,
)
from extractor.niche_inference import LED_ESTIMATE_CHOICE_KEY
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import (
    SHOWER_ASSUMED_SENTENCE, SHOWER_KEY, _build_pozicijos_from_rooms,
    _calc_hidroizoliacija_m2, _recompute_per_room_via_python, _rooms_named_in,
    mark_shower_rooms, plumbing_reading, shower_count, toilet_count,
)


# ── fixtures ────────────────────────────────────────────────────────────────

def _room(nr, name, paskirtis, plotas=6.0, perim=10.0, **kw):
    r = {"nr": nr, "pavadinimas": name, "paskirtis": paskirtis,
         "plotas_m2": plotas, "perimetras_m": perim, "lubu_aukstis_m": 2.7,
         "lubu_tipas": "pakabinamos", "elementai": [
             {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}]}
    r.update(kw)
    return r


def _three_bathrooms() -> dict:
    """Two vonios kambariai and a san. mazgas — the shape of an out-of-sample
    project whose plumbing plan shows a shower in two of the three."""
    return {
        "patalpos": [
            _room("01", "Svetainė", "gyvenamoji", plotas=30.0, perim=22.0),
            _room("03", "Miegamojo san. mazgas", "san", plotas=4.0, perim=8.0),
            _room("06", "Vonios kambarys", "vonia"),
            _room("07", "Vonios kambarys", "vonia"),
        ],
        "santrauka": {},
    }


def _with_plumbing(parsed: dict) -> dict:
    p = copy.deepcopy(parsed)
    p["_meta"] = {"fixtures_status": "ok"}
    p["detected_symbols_summary"] = {"klozetai": 2, "praustuves": 2, "dusai": 2,
                                     "wc_remai": 3, "vonios": 1, "vonios_kubilai": 1}
    p["_sanitary_prietaisai"] = [
        {"tipas": "praustuve", "vieta": "03 Miegamojo san. mazgas – praustuvas, h=1.070"},
        {"tipas": "klozetas", "vieta": "03 Miegamojo san. mazgas – pakabinamas klozetas"},
        {"tipas": "dusas", "vieta": "07 Vonios kambarys (viršutinis) – dušo maišytuvas"},
        {"tipas": "dusas", "vieta": "05/06 zona – dušo maišytuvas, plyšinis latakas"},
        {"tipas": "klozetas", "vieta": "06 Vonios kambarys – pakabinamas klozetas"},
        {"tipas": "praustuve", "vieta": "06 Vonios kambarys – praustuvas"},
        {"tipas": "kita", "vieta": "Terasa/išorė – trapas"},
    ]
    return p


def _extract_tail(parsed: dict, overrides: dict | None = None) -> dict:
    """What the extraction does from the plumbing reader on: the reader step
    marks the rooms, then the per-room tail runs (Step 2.9)."""
    p = copy.deepcopy(parsed)
    mark_shower_rooms(p)
    return _recompute_per_room_via_python(p, overrides or {})


def _build(parsed: dict, overrides: dict | None = None) -> list[dict]:
    return _build_pozicijos_from_rooms(_extract_tail(parsed, overrides))["pozicijos"]


def _row(rows, prefix):
    hits = [r for r in rows if (r.get("aprasymas") or "").startswith(prefix)]
    assert hits, f"no row starts with {prefix!r}"
    return hits[0]


# ── the plumbing reading ────────────────────────────────────────────────────

def test_no_plumbing_reading_without_an_ok_reader():
    assert plumbing_reading({}) is None
    assert plumbing_reading({"_meta": {"fixtures_status": "skipped"},
                             "detected_symbols_summary": {"klozetai": 2}}) is None
    # the main pass's glance alone is not a plumbing reading
    assert plumbing_reading({"detected_symbols_summary": {"klozetai": 2, "dusai": 2}}) is None


def test_plumbing_reading_from_status_and_from_an_older_extract():
    ok = plumbing_reading({"_meta": {"fixtures_status": "ok"},
                           "detected_symbols_summary": {"klozetai": 2, "dusai": "1"}})
    assert ok["klozetai"] == 2 and ok["dusai"] == 1
    # before the status was kept: `fixtures_raised` is written only on an ok read
    legacy = plumbing_reading({"_meta": {"fixtures_raised": []},
                               "detected_symbols_summary": {"praustuves": 3}})
    assert legacy["praustuves"] == 3
    # an ok read that counted nothing usable is no reading
    assert plumbing_reading({"_meta": {"fixtures_status": "ok"},
                             "detected_symbols_summary": {"rozetes": 40}}) is None
    # …also when the main pass's glance filled the summary: the reader's own
    # (kept) counts decide whether it read anything
    assert plumbing_reading({"_meta": {"fixtures_status": "ok",
                                       "fixtures_counts": {"klozetai": 0, "dusai": 0}},
                             "detected_symbols_summary": {"klozetai": 2, "dusai": 2}}) is None


# ── which room a fixture stands in ──────────────────────────────────────────

def test_room_named_by_leading_number_or_unique_name():
    rooms = [_room("01", "Tambūras", "tamburas"), _room("02", "Katilinė", "katiline"),
             _room("07", "Vonios kambarys 1", "san"), _room("08", "Vonios kambarys 2", "san")]
    assert _rooms_named_in("07 Vonios kambarys – praustuvas", rooms) == {"07"}
    # a digit inside the name is the name's, never room 01 / 02
    assert _rooms_named_in("Vonios kambarys 1 – potinkinis praustuvas H 1.1m", rooms) == {"07"}
    assert _rooms_named_in("Vonios kambarys 2 – dušo galva H 2.2m", rooms) == {"08"}
    assert _rooms_named_in("05/07 zona – dušo maišytuvas", rooms) == {"07"}
    # heights and unknown places name nothing
    assert _rooms_named_in("Patalpa prie skalbyklės – h=1.070", rooms) == set()
    assert _rooms_named_in("", rooms) == set()


def test_shower_flags_from_the_plumbing_list():
    p = _with_plumbing(_three_bathrooms())
    assert mark_shower_rooms(p) == 3
    flags = {r["nr"]: r.get(SHOWER_KEY) for r in p["patalpos"]}
    assert flags == {"01": None, "03": False, "06": True, "07": True}


def test_the_per_room_tail_alone_does_not_re_mark_the_rooms():
    """The tail is what every recompute path shares; the marking belongs to the
    reader step, so a stored project recomputes to the numbers it was stored
    with (test_recompute_interior_parity)."""
    p = _recompute_per_room_via_python(_with_plumbing(_three_bathrooms()), {})
    assert all(SHOWER_KEY not in r for r in p["patalpos"])


def test_no_list_leaves_the_rooms_to_their_type():
    p = _three_bathrooms()
    assert mark_shower_rooms(p) == 0
    assert all(SHOWER_KEY not in r for r in p["patalpos"])


# ── hidroizoliacija: the shower zone only where a shower may be ─────────────

def test_hydro_drops_the_shower_zone_where_the_plan_lists_no_shower():
    r = _room("03", "San. mazgas", "san", plotas=4.0, perim=8.0)
    with_zone = _calc_hidroizoliacija_m2(r, 8.0)
    r[SHOWER_KEY] = False
    without = _calc_hidroizoliacija_m2(r, 8.0)
    assert with_zone - without == pytest.approx((1.0 * 2 + 1.2) * 2.7, abs=0.01)


def test_hydro_row_names_the_rooms_whose_shower_zone_is_assumed():
    rows = _build(_three_bathrooms())
    hydro = _row(rows, "Hidroizoliacijos įrengimas")
    assert hydro["confidence"] != "zalia"
    assert "03, 06 ir 07" in hydro["_confidence_reason"]
    assert "dušo zona" in hydro["_assumption"].lower()
    # with the plumbing plan every bathroom is answered — nothing assumed
    hydro_read = _row(_build(_with_plumbing(_three_bathrooms())), "Hidroizoliacijos įrengimas")
    assert "_assumption" not in hydro_read


# ── showers: counted where read, disclosed where assumed ────────────────────

_SHOWER_ROWS = ("Nuolydžio formavimas dušo zonoje", "Linijinio latako montavimas",
                "Potinkinio dušo maišytuvo potinkinės dalies montavimas",
                "Potinkinio dušo maišytuvo virštinkinės dalies montavimas")


def test_without_a_plumbing_reading_showers_are_a_disclosed_assumption():
    rows = _build(_three_bathrooms())
    for prefix in _SHOWER_ROWS:
        row = _row(rows, prefix)
        assert row["kiekis"] == 3, prefix               # quantities unchanged
        assert row["saltinis"] == "paskirtis_default", prefix
        assert row["confidence"] != "zalia", prefix
        assert "Patikrinkite, ar patalpose 03, 06 ir 07 yra dušas" in row["_confidence_reason"]
    # the room's own sheet says it per room
    nuolydis = _row(rows, "Nuolydžio formavimas dušo zonoje")
    assert {c["included_because"] for c in nuolydis["contributions"]} == {SHOWER_ASSUMED_SENTENCE}


def test_with_a_plumbing_reading_showers_are_its_count():
    rows = _build(_with_plumbing(_three_bathrooms()))
    for prefix in _SHOWER_ROWS:
        row = _row(rows, prefix)
        assert row["kiekis"] == 2, prefix
        assert row["saltinis"] == "simboliai_brezinyje", prefix
    nuolydis = _row(rows, "Nuolydžio formavimas dušo zonoje")
    assert sorted(c["room_nr"] for c in nuolydis["contributions"]) == ["06", "07"]
    shelves = _row(rows, "Lentynėlių iš plytelių įrengimas dušo kabinoje")
    assert shelves["kiekis"] == 4 and shelves["saltinis"] == "project_assumption"
    # the per-shower number is still an assumption: never green
    assert shelves["confidence"] != "zalia"


def test_no_shower_anywhere_the_plan_answers_means_no_shower_rows():
    p = _with_plumbing(_three_bathrooms())
    p["detected_symbols_summary"]["dusai"] = 0
    p["_sanitary_prietaisai"] = [
        {"tipas": "klozetas", "vieta": "03 Miegamojo san. mazgas – klozetas"},
        {"tipas": "praustuve", "vieta": "06 Vonios kambarys – praustuvas"},
        {"tipas": "vonia", "vieta": "07 Vonios kambarys – vonia"},
    ]
    rows = _build(p)
    assert not any((r.get("aprasymas") or "").startswith(_SHOWER_ROWS) for r in rows)


def test_shower_count_helper():
    rooms = _three_bathrooms()["patalpos"]
    assert shower_count(rooms, None)["n"] == 3
    rooms[1][SHOWER_KEY] = False
    sc = shower_count(rooms, None)
    assert sc["n"] == 2 and sc["source"] == "paskirtis_default"
    assert shower_count(rooms, {"dusai": 1}) == {"n": 1, "source": "simboliai_brezinyje", "assumed": []}


# ── toilets and basins ──────────────────────────────────────────────────────

def test_toilet_rows_follow_the_plumbing_reading():
    rows = _build(_with_plumbing(_three_bathrooms()))
    for prefix in ("WC rėmo montavimas", "Klozeto montavimas",
                   "Pertvaros sutvirtinimas WC mechanizmams", "Praustuvės montavimas"):
        row = _row(rows, prefix)
        assert row["kiekis"] == 2, prefix
        assert row["saltinis"] == "simboliai_brezinyje", prefix
    # three rooms, two toilets: the rooms stay named and the anchor says why
    wc = _row(rows, "WC rėmo montavimas")
    assert wc["roll_up"][-1]["op"] == "anchor" and wc["roll_up"][-1]["value"] == 2


def test_toilet_rows_without_a_reading_are_never_green():
    rows = _build(_three_bathrooms())
    for prefix in ("WC rėmo montavimas", "Klozeto montavimas", "Gyvatuko montavimas",
                   "Pertvaros sutvirtinimas WC mechanizmams"):
        row = _row(rows, prefix)
        assert row["kiekis"] == 3, prefix
        assert row["saltinis"] == "paskirtis_default", prefix
        assert row["confidence"] == "geltona", prefix
        assert row["_confidence_reason"] == ROOM_DEFAULT_REASON, prefix


def test_toilet_count_helper_ignores_frames():
    rooms = _three_bathrooms()["patalpos"]
    assert toilet_count(rooms, None) == (3, "paskirtis_default")
    assert toilet_count(rooms, {"klozetai": 2, "wc_remai": 3}) == (2, "simboliai_brezinyje")


def test_the_prielaidos_rebuild_keeps_the_extractions_counts():
    """The recompute context carries `_meta` and `detected_symbols_summary` but
    not the fixture list — the rooms' flags and the reading must still give the
    rows the extraction gave."""
    extracted = _extract_tail(_with_plumbing(_three_bathrooms()))
    first = _build_pozicijos_from_rooms(copy.deepcopy(extracted))["pozicijos"]
    context = {k: extracted[k] for k in ("_meta", "detected_symbols_summary")}
    rebuilt = _build_pozicijos_from_rooms(
        {**context, "patalpos": copy.deepcopy(extracted["patalpos"]), "santrauka": {}})["pozicijos"]
    for prefix in _SHOWER_ROWS + ("WC rėmo montavimas", "Hidroizoliacijos įrengimas"):
        assert _row(first, prefix)["kiekis"] == _row(rebuilt, prefix)["kiekis"], prefix
        assert _row(first, prefix).get("_detail_m2") == _row(rebuilt, prefix).get("_detail_m2"), prefix


def test_the_room_sheet_recompute_keeps_the_stored_shower_answer(monkeypatch):
    """A project extracted with a plumbing plan stores the flags on its rooms;
    /recompute-interior must give the per-room hidroizoliacija the extraction
    gave (no shower zone in the san. mazgas the plan shows without a shower)."""
    from fastapi.testclient import TestClient

    import main
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    stored = _extract_tail(_with_plumbing(_three_bathrooms()))
    body = {"patalpos": copy.deepcopy(stored["patalpos"]),
            "context": {k: stored[k] for k in ("_meta", "detected_symbols_summary")}}
    r = TestClient(main.app).post("/recompute-interior", json=body)
    assert r.status_code == 200, r.text
    sheet = {x["nr"]: x for x in r.json()["patalpos"]}
    for room in stored["patalpos"]:
        assert sheet[room["nr"]]["hidroizoliacija_m2"] == pytest.approx(
            room["hidroizoliacija_m2"], abs=0.011), room["nr"]
    assert sheet["03"][SHOWER_KEY] is False
    nuolydis = _row(r.json()["darbu_sarasas"], "Nuolydžio formavimas dušo zonoje")
    assert nuolydis["kiekis"] == 2


# ── apply_confidence: a room-type count is never green ──────────────────────

def test_room_type_source_is_demoted_and_explained():
    p = {"pozicijos": [
        {"aprasymas": "Gyvatuko montavimas, teno pajungimas", "kiekis": 2,
         "saltinis": "paskirtis_default"},
        {"aprasymas": "Klozeto montavimas", "kiekis": 2, "saltinis": "paskirtis_default"},
        {"aprasymas": "Klozeto montavimas", "kiekis": 2, "saltinis": "simboliai_brezinyje"},
        {"aprasymas": "Linijinio latako montavimas (dušo zonoje)", "kiekis": 2,
         "saltinis": "paskirtis_default", "_confidence_reason": "Patikrinkite dušą."},
    ]}
    out = apply_confidence(p)["pozicijos"]
    assert out[0]["confidence"] == "geltona" and out[0]["_confidence_reason"] == ROOM_DEFAULT_REASON
    # the class note says „from symbols" — not on a room-type count
    assert out[1]["_confidence_reason"] == ROOM_DEFAULT_REASON
    assert "simbolių" in out[2]["_confidence_reason"]
    # a specific upstream reason stands, the tier still drops
    assert out[3]["confidence"] == "geltona" and out[3]["_confidence_reason"] == "Patikrinkite dušą."


# ── LED niches estimated from the room type ─────────────────────────────────

def _led_project(read_m: float | None) -> dict:
    els = [{"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 6.6,
            "_source": "statistical_inference", "_confidence": "low"}]
    living = _room("01", "Svetainė", "gyvenamoji", plotas=30.0, perim=22.0)
    if read_m:
        living["elementai"].append({"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": read_m,
                                    "_source": "niche_locator"})
    return {"patalpos": [living, _room("02", "Koridorius", "koridorius", plotas=8.0,
                                       perim=12.0, elementai=els)],
            "santrauka": {}}


_LED_ROWS = ("Nišų formavimas GKP konstrukcijoje", "LED nišų glaistymas")
# Since 2026-10-06 an estimate is billed only once he accepts it in Nustatymai
# (niche_inference.LED_ESTIMATE_OPT_IN, tests/test_led_estimate_choice_2026_10_06.py);
# the disclosure below is what the rows say after he did.
_ACCEPTED = {LED_ESTIMATE_CHOICE_KEY: True}


def test_led_rows_with_an_estimate_are_never_green_and_name_the_rooms():
    rows = _build(_led_project(read_m=8.0), _ACCEPTED)
    for prefix in _LED_ROWS:
        row = _row(rows, prefix)
        assert row["kiekis"] == pytest.approx(14.6), prefix     # quantity unchanged
        assert row["confidence"] == "geltona", prefix
        assert "02 (6,60 m)" in row["_confidence_reason"], prefix
        assert "ne išmatuota" in row["_confidence_reason"], prefix
    framing = _row(rows, "Nišų formavimas GKP konstrukcijoje")
    why = {c["room_nr"]: c["included_because"] for c in framing["contributions"]}
    assert "neišmatuotas" in why["02"] and why["01"] == "LED nišos lubose"


def test_led_rows_all_estimated_are_red():
    rows = _build(_led_project(read_m=None), _ACCEPTED)
    assert _row(rows, "Nišų formavimas GKP konstrukcijoje")["confidence"] == "raudona"


def test_led_rows_all_read_stay_as_before():
    p = _led_project(read_m=8.0)
    p["patalpos"][1]["elementai"] = []
    row = _row(_build(p), "Nišų formavimas GKP konstrukcijoje")
    assert row["kiekis"] == 8.0 and row["confidence"] == "zalia"
    assert not row.get("_confidence_reason")


# ── kampai: the words say what the engine adds up ───────────────────────────

def test_kampai_reason_names_the_terms_the_engine_adds():
    assert "išoriniai kampai ×" not in KAMPAI_REASON
    for term in ("perimetro", "vidinių kampų", "angų kraštų", "pertvarų sandūrų", "standartinio dydžio"):
        assert term in KAMPAI_REASON, term
    # …and the engine adds exactly those terms (calc-engine-5: text only, math untouched)
    room = {"nr": "1", "paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
            "lubu_aukstis_m": 2.7, "n_doors": 2, "n_windows": 1, "n_partition_walls": 1}
    q = calc_room_quantities(room)
    expected = 18.0 + 4 * 2.7 + 2 * (0.9 + 2 * 2.05) + 1 * (1.2 + 2 * 1.5) + 1 * 2.7
    assert q["kampu_metrai"] == pytest.approx(expected, abs=0.01)
    assert q["kampu_metrai"] == pytest.approx(
        q["kampai_perimetras_m"] + q["kampai_inner_m"] + q["kampai_opening_reveals_m"]
        + q["kampai_pusiniai_m"], abs=0.01)


def test_kampai_row_carries_the_reason():
    rows = _build({"patalpos": [_room("01", "Svetainė", "gyvenamoji", plotas=30.0, perim=22.0,
                                      n_partition_walls=1)], "santrauka": {}})
    assert KAMPAI_REASON in _row(rows, "Dažymo kampų montavimas")["_confidence_reason"]

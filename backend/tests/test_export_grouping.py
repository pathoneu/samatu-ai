"""api/export_grouping.py — the Excel groupings (togal-v2 W8). The invariant: whatever the grouping, every
line's quantity and amount come out exactly as in the default layout; only order and subtotals change."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from api.export_grouping import (
    GROUPINGS, OVERSHOOT_LABEL, REMAINDER_LABEL, UNASSIGNED_ROOMS, UNASSIGNED_SHEET, group_export_lines,
    kaip_gauta, normalize_grouping, preview, totals_by_line,
)

ROOMS = [{"nr": "01", "pavadinimas": "Tambūras"}, {"nr": "02", "pavadinimas": "Katilinė"},
         {"nr": "03", "pavadinimas": "Koridorius"}]
SHEETS = [{"nr": 1, "pavadinimas": "IŠDĖSTYMO PLANAS"}, {"nr": 5, "pavadinimas": "LUBŲ PLANAS"}]


def _lines():
    return [
        {"nr": "1", "skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
         "kiekis": 30.01, "kaina": 7.33, "confidence": "zalia",
         "dalys": [{"room_nr": "02", "room_name": "Katilinė", "page": 1, "value": 10.0},
                   {"room_nr": "01", "room_name": "Tambūras", "page": 1, "value": 10.0},
                   {"room_nr": "03", "room_name": "Koridorius", "page": 1, "value": 10.01}]},
        # contributions short of the line (an anchor added 2 m²) → a remainder row
        {"nr": "2", "skyrius": "Lubų glaistymas dažymas", "aprasymas": "Lubų dažymas", "mato_vnt": "m²",
         "kiekis": 22.0, "kaina": 5.0, "confidence": "geltona",
         "dalys": [{"room_nr": "01", "room_name": "Tambūras", "page": 5, "value": 8.0},
                   {"room_nr": "03", "room_name": "Koridorius", "page": 5, "value": 12.0}]},
        # contributions above the line (a cap) → a negative correction row
        {"nr": "3", "skyrius": "Grindys", "aprasymas": "Grindjuostės", "mato_vnt": "m", "kiekis": 9.0,
         "kaina": 3.17, "confidence": "geltona",
         "dalys": [{"room_nr": "02", "room_name": "Katilinė", "page": 1, "value": 5.0},
                   {"room_nr": "03", "room_name": "Koridorius", "page": 1, "value": 5.0}]},
        # no room parts at all, priced by the person
        {"nr": "4", "skyrius": "Santechnikos darbai", "aprasymas": "WC rėmo montavimas", "mato_vnt": "vnt",
         "kiekis": 2, "kaina": 85, "confidence": "zalia", "kilme": "pataisyta"},
        # no price
        {"nr": "5", "skyrius": "Kiti darbai", "aprasymas": "Šiukšlių išvežimas", "mato_vnt": "kompl",
         "kiekis": 1, "kaina": 0, "kilme": "jusu"},
    ]


def _cents(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amount(row):
    return Decimal(str(row["_suma"])) if row.get("_suma") is not None else _cents(row["kiekis"] * row["kaina"])


@pytest.mark.parametrize("mode", GROUPINGS)
def test_every_grouping_keeps_each_lines_quantity(mode):
    lines = _lines()
    rows = group_export_lines(lines, mode, rooms=ROOMS, sheets=SHEETS)
    flat = {ln["nr"]: float(ln["kiekis"]) for ln in lines}
    got = totals_by_line(rows)
    assert set(got) == set(flat)
    for nr, total in flat.items():
        assert got[nr] == pytest.approx(total, abs=1e-9), (mode, nr)
    # …and the grand total over all groups equals the flat total
    assert sum(got.values()) == pytest.approx(sum(flat.values()), abs=1e-9)


@pytest.mark.parametrize("mode", GROUPINGS)
def test_every_grouping_keeps_the_money_to_the_cent(mode):
    lines = _lines()
    rows = group_export_lines(lines, mode, rooms=ROOMS, sheets=SHEETS)
    expected = sum(_cents(ln["kiekis"] * ln["kaina"]) for ln in lines)
    assert sum(_amount(r) for r in rows) == expected
    # per line too
    for ln in lines:
        mine = [r for r in rows if r["nr"] == ln["nr"]]
        assert sum(_amount(r) for r in mine) == _cents(ln["kiekis"] * ln["kaina"]), (mode, ln["nr"])


@pytest.mark.parametrize("mode", [m for m in GROUPINGS if m not in ("skyriai", "be_grupavimo")])
def test_group_subtotals_add_up_to_the_flat_total(mode):
    rows = group_export_lines(_lines(), mode, rooms=ROOMS, sheets=SHEETS)
    by_group: dict[str, Decimal] = {}
    for r in rows:
        by_group[r["skyrius"]] = by_group.get(r["skyrius"], Decimal(0)) + _amount(r)
    assert sum(by_group.values()) == sum(_cents(ln["kiekis"] * ln["kaina"]) for ln in _lines())
    # each group's rows are contiguous — the sheet prints one heading per group
    seen, last = [], None
    for r in rows:
        if r["skyrius"] != last:
            assert r["skyrius"] not in seen, (mode, r["skyrius"])
            seen.append(r["skyrius"])
            last = r["skyrius"]


def test_default_grouping_is_todays_layout_untouched():
    lines = _lines()
    rows = group_export_lines(lines, "skyriai")
    assert [(r["nr"], r["skyrius"], r["aprasymas"], r["kiekis"]) for r in rows] == \
        [(ln["nr"], ln["skyrius"], ln["aprasymas"], ln["kiekis"]) for ln in lines]
    assert all("_suma" not in r and "dalys" not in r for r in rows)
    assert normalize_grouping(None) == "skyriai" and normalize_grouping("") == "skyriai"
    with pytest.raises(ValueError):
        normalize_grouping("bet-kas")


def test_rooms_grouping_is_plan_order_then_unassigned():
    rows = group_export_lines(_lines(), "patalpos", rooms=ROOMS, sheets=SHEETS)
    heads = list(dict.fromkeys(r["skyrius"] for r in rows))
    assert heads == ["01 Tambūras", "02 Katilinė", "03 Koridorius", UNASSIGNED_ROOMS]
    unassigned = [r for r in rows if r["skyrius"] == UNASSIGNED_ROOMS]
    descs = {r["aprasymas"] for r in unassigned}
    assert f"Lubų dažymas — {REMAINDER_LABEL}" in descs
    assert f"Grindjuostės — {OVERSHOOT_LABEL}" in descs
    over = next(r for r in unassigned if r["aprasymas"].startswith("Grindjuostės"))
    assert over["kiekis"] == pytest.approx(-1.0)
    assert {"WC rėmo montavimas", "Šiukšlių išvežimas"} <= descs


def test_sheets_grouping_names_the_sheet_and_the_room():
    rows = group_export_lines(_lines(), "lapai", rooms=ROOMS, sheets=SHEETS)
    heads = list(dict.fromkeys(r["skyrius"] for r in rows))
    assert heads == ["Lapas 1 — IŠDĖSTYMO PLANAS", "Lapas 5 — LUBŲ PLANAS", UNASSIGNED_SHEET]
    assert any(r["aprasymas"] == "Lubų dažymas — 01 Tambūras" for r in rows)


def test_families_grouping_is_the_quantities_panel_tree():
    rows = group_export_lines(_lines(), "seimos", rooms=ROOMS, sheets=SHEETS)
    heads = list(dict.fromkeys(r["skyrius"] for r in rows))
    assert heads[0] == "Sienų glaistymas dažymas · Sienų dažymas"
    first = [r["aprasymas"] for r in rows if r["skyrius"] == heads[0]]
    assert first == ["02 Katilinė", "01 Tambūras", "03 Koridorius"]  # the server's contribution order
    whole = [r for r in rows if r["nr"] == "4"]
    assert len(whole) == 1 and whole[0]["aprasymas"] == "WC rėmo montavimas" and "_suma" not in whole[0]


def test_flat_rows_carry_every_attribute_and_no_headings():
    rows = group_export_lines(_lines(), "be_grupavimo", rooms=ROOMS, sheets=SHEETS)
    assert all(r["skyrius"] == "" for r in rows)
    first = rows[0]
    assert first["_skyrius"] == "Sienų glaistymas dažymas" and first["_patalpa"] == "02 Katilinė"
    assert first["_lapas"] == "Lapas 1 — IŠDĖSTYMO PLANAS" and first["_eilute"] == "Sienų dažymas"
    assert len(rows) == 3 + 3 + 3 + 1 + 1


def test_every_row_says_how_it_was_obtained():
    assert kaip_gauta({"confidence": "zalia"}) == "Programa — skaityta tiesiogiai"
    assert kaip_gauta({"confidence": "geltona"}) == "Programa — patikrinti"
    assert kaip_gauta({"confidence": "low"}) == "Programa — būtina patikrinti"
    assert kaip_gauta({"confidence": "junk"}) == "Programa — patikrinti"
    assert kaip_gauta({}) == "Programa — skaityta tiesiogiai"
    assert kaip_gauta({"kilme": "pataisyta", "confidence": "raudona"}) == "Pataisyta jūsų"
    assert kaip_gauta({"kilme": "jusu"}) == "Įvesta jūsų"
    for mode in GROUPINGS:
        assert all(r["_kaip_gauta"] for r in group_export_lines(_lines(), mode, rooms=ROOMS))


def test_preview_prints_headings_and_marks_program_rows():
    rows = group_export_lines(_lines(), "patalpos", rooms=ROOMS, sheets=SHEETS)
    out = preview(rows, limit=4)
    kinds = [x["kind"] for x in out["rows"]]
    assert kinds[0] == "heading" and kinds.count("row") == 4
    assert out["row_count"] == len(rows) and out["groups"] == 4
    full = preview(rows, limit=100)["rows"]
    mine = [x for x in full if x["kind"] == "row" and not x["programos"]]
    assert {x["aprasymas"] for x in mine} == {"WC rėmo montavimas", "Šiukšlių išvežimas"}

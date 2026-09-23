"""2026-09-23 — the drawing's DOOR SCHEDULE read without a model (extractor/door_schedule), and what the
project-level pass does with it (universal_rules: doors to the outside, the frameless-door assumption's
evidence, the counted list reconciled with the table). The founder: „kiek durų su apvadais žiniaraštis
rodo? patikrink durų žiniaraščio skaitymą"."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.door_schedule import scan_door_schedule  # noqa: E402
from extractor.line_items import hidden_door_count  # noqa: E402


# ── a drawing with a schedule, written with reportlab (word positions like a CAD export) ─────────────

def _pdf(pages: list[list[tuple[float, float, str]]]) -> bytes:
    """Pages of (x, y, text) in points on A3 landscape; y from the top."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(1191, 842))
    for items in pages:
        c.setFont("Helvetica", 9)
        for x, y, text in items:
            c.drawString(x, 842 - y, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def _schedule_page(rows, heading="Vidinių angų (durų) žiniaraštis", note=True, plan_tags=("D-1", "D-2")):
    items = [(120, 200, "Patalpų eksplikacija"), (120, 215, "01. Įėjimo koridorius 4.05 m²"),
             (300, 400, "002"), (838, 358, heading),
             (838, 380, "Kodas"), (880, 380, "Angos plotis, mm"), (960, 380, "Angos aukštis, mm"), (1040, 380, "Durų tipas")]
    y = 411
    for kodas, w, h, tipas in rows:
        items += [(840, y, kodas), (890, y, str(w)), (965, y, str(h)), (1040, y, tipas)]
        y += 31
    if note:
        items += [(120, 700, "PASTABOS:"), (120, 715, "1. Durų staktas ruošti beapvadinėms durims: lyginti, glaistyti, dažyti.")]
    for k, tag in enumerate(plan_tags):
        items.append((316 + 170 * k, 468, tag))                 # the tags on the plan, left of the table
    return items


def test_the_schedule_table_is_read_with_sizes_types_and_plan_counts():
    pdf = _pdf([_schedule_page([("D-1", 910, 2100, "Dešininės, beapvadinės"), ("D-2", 910, 2100, "Kairinės, beapvadinės")])])
    out = scan_door_schedule(pdf)
    assert out["status"] == "lentele" and out["lentele"]["page"] == 1
    rows = out["lentele"]["eilutes"]
    assert [(r["kodas"], r["plotis_mm"], r["aukstis_mm"], r["tipas"], r["kiekis"]) for r in rows] == [
        ("D-1", 910, 2100, "beapvadines", 1), ("D-2", 910, 2100, "beapvadines", 1)]
    assert (out["beapvadines"], out["su_apvadais"]) == (2, 0) and out["pastaba_beapvadines"] is True
    assert "D-1 910×2100 beapvadinės ×1" in out["sakinys"] and "su apvadais nėra" in out["sakinys"]


def test_a_framed_row_and_a_tag_standing_twice_on_the_plan_are_counted():
    pdf = _pdf([_schedule_page([("D-1", 800, 2100, "su apvadais"), ("D-2", 700, 2100, "beapvadinės")],
                               note=False, plan_tags=("D-1", "D-1", "D-2"))])
    out = scan_door_schedule(pdf)
    rows = {r["kodas"]: r for r in out["lentele"]["eilutes"]}
    assert rows["D-1"]["tipas"] == "su_apvadais" and rows["D-1"]["kiekis"] == 2
    assert rows["D-2"]["tipas"] == "beapvadines" and rows["D-2"]["kiekis"] == 1
    assert (out["beapvadines"], out["su_apvadais"]) == (1, 2) and "su apvadais — 2" in out["sakinys"]


def test_annotations_products_and_nothing_are_told_apart():
    anno = _pdf([[(200, 300, "Durų anga iki lubų, skirta beapvadinėms durims"), (600, 300, "Durų anga iki lubų,"),
                  (600, 312, "skirta beapvadinėms durims"), (100, 100, "PATALPŲ EKSPLIKACIJA 101 Tambūras 11.01 m²"),
                  (100, 120, "x" * 200)]])
    out = scan_door_schedule(anno)
    assert out["status"] == "anotacijos" and out["anotacijos_beapvadines"] == 2 and out["lentele"] is None
    assert "2 angos pažymėtos" in out["sakinys"]
    board = _pdf([[(100, 100, "DECO-10 vidaus durys, nashville oak"), (100, 130, "Dažytos vidaus durys LOFT (baltos)"),
                   (100, 160, "GRINDJUOSTĖS - 80x16 MDF baltai dažytos"), (100, 190, "y" * 200)]])
    out = scan_door_schedule(board)
    assert out["status"] == "gaminiai" and out["gaminiai"][0] == "DECO-10 vidaus durys"
    assert "beapvadinių niekur neminima" in out["sakinys"]
    nothing = _pdf([[(100, 100, "LUBŲ PLANAS"), (100, 120, "z" * 300)]])
    out = scan_door_schedule(nothing)
    assert out["status"] == "nera" and out["sakinys"] == "Durų žiniaraščio ar durų tipo užrašų brėžinyje nėra."
    scan = _pdf([[(100, 100, "a")]])
    assert scan_door_schedule(scan)["text_layer_ok"] is False


# ── what the pass does with it ─────────────────────────────────────────────────────────────────────

def _room(nr, elementai, **more):
    return {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": "gyvenamoji", "plotas_m2": 12.0, "perimetras_m": 14.0,
            "lubu_aukstis_m": 2.7, "elementai": elementai, **more}


def door(w=None, h=None, **more):
    el = {"tipas": "duris", "kiekis": 1, **more}
    if w:
        el["plotis_mm"] = w
    if h:
        el["aukstis_mm"] = h
    return el


def window(w, h=1500):
    return {"tipas": "langas", "kiekis": 1, "plotis_mm": w, "aukstis_mm": h}


def openings(*angos):
    return {"page": 1, "angos": [{"i": i, "plotis_m": w, "line_pct": [[0, 0], [0.1, 0]]} for i, w in angos]}


def test_a_door_whose_wall_opening_leads_outside_is_exterior_and_the_windows_claim_theirs_first():
    kitchen = _room("04", [window(1370), window(1360), window(1350), door()],
                    _angos_sienose=openings(("03", 2.13), ("laukas", 1.37), ("laukas", 1.36), ("laukas", 0.89), ("laukas", 1.35)))
    assert ur.mark_exterior_doors([kitchen]) == 1
    assert kitchen["elementai"][3].get(ur.EXTERIOR_KEY) is True    # the 0,89 m opening no window claims — the terrace door
    ur.settle_frameless_default([kitchen], overrides={"vidaus_durys_beapvadines": True})
    out = ur.calc_room_quantities(kitchen)
    assert out["pasleptu_duru_staktu_m"] == 0                       # a terrace door is never a frameless interior one
    assert out["angokrasciu_gkp_m"] > 3 * (1.2 + 3.0)               # …but its reveal is counted with the windows'


def test_a_door_to_a_room_stays_interior_and_the_entrance_room_without_walls_read_gives_up_one_door():
    corridor = _room("03", [door(), door()], _angos_sienose=openings(("06", 0.77), ("09", 0.87)))
    assert ur.mark_exterior_doors([corridor]) == 0
    hall = _room("01", [door(), door()], pavadinimas="Įėjimo koridorius")
    assert ur.mark_exterior_doors([hall]) == 1
    assert hall["elementai"][0].get(ur.EXTERIOR_KEY) is True and not hall["elementai"][1].get(ur.EXTERIOR_KEY)
    # a Vision flag already there is left alone, and the mark is idempotent
    assert ur.mark_exterior_doors([hall]) == 1 and sum(bool(e.get(ur.EXTERIOR_KEY)) for e in hall["elementai"]) == 1


def test_an_element_of_several_units_gives_its_exterior_unit_its_own_element():
    hall = _room("01", [door(900, kiekis=3)], paskirtis="tamburas")
    ur.mark_exterior_doors([hall])
    assert [(e["kiekis"], bool(e.get(ur.EXTERIOR_KEY))) for e in hall["elementai"]] == [(1, True), (2, False)]


def _d_like():
    """objektas_d as the cache had it: three doors counted in the entrance corridor beside the entrance,
    the schedule has two (D-1, D-2, 910×2100, beapvadinės)."""
    hall = _room("01", [door(800, 2100, _exterior=True), door(700, 2100), {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100},
                        door(900, 2100)], pavadinimas="Įėjimo koridorius", paskirtis="koridorius")
    schedule = {"status": "lentele", "beapvadines": 2, "su_apvadais": 0, "pastaba_beapvadines": True,
                "lentele": {"page": 2, "eilutes": [
                    {"kodas": "D-1", "plotis_mm": 910, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1},
                    {"kodas": "D-2", "plotis_mm": 910, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1}]},
                "sakinys": "Durų žiniaraštyje (2 lapas): D-1 910×2100 beapvadinės ×1, D-2 910×2100 beapvadinės ×1; su apvadais nėra."}
    return hall, schedule


def test_the_counted_doors_are_matched_to_the_schedule_and_the_extra_one_counts_for_no_row():
    hall, schedule = _d_like()
    prep = ur.prepare_rooms_for_calc([hall], schedule=schedule)
    assert prep["frameless"]["source"] == "ziniarastis" and prep["frameless"]["value"] is True
    assert prep["ziniarastis"] == {"units": 2, "matched": 2, "beyond": 1}
    els = hall["elementai"]
    assert els[3].get(ur.SCHEDULE_TYPE_KEY) == "beapvadines" and els[3]["plotis_mm"] == 910    # 900 → D-1's 910
    assert els[2].get(ur.SCHEDULE_TYPE_KEY) == "beapvadines" and els[2]["plotis_mm"] == 910    # 800 → D-2's 910
    assert els[1].get(ur.BEYOND_SCHEDULE_KEY) is True                                          # the 700 — not in the table
    out = ur.calc_room_quantities(hall)
    assert out["pasleptu_duru_staktu_m"] == round(2 * (0.91 + 2 * 2.1), 2) == 10.22            # his row to the centimetre
    assert out["pasleptu_duru_kompl"] == 2
    assert hidden_door_count(els, frameless_default=True) == 2


def test_a_framed_schedule_row_is_never_prepared_even_under_the_assumption():
    room = _room("05", [door(800, 2100), door(900, 2100)])
    schedule = {"lentele": {"page": 1, "eilutes": [
        {"kodas": "D-1", "plotis_mm": 800, "aukstis_mm": 2100, "tipas": "su_apvadais", "kiekis": 1},
        {"kodas": "D-2", "plotis_mm": 900, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1}]},
        "beapvadines": 1, "su_apvadais": 1, "sakinys": "…"}
    prep = ur.prepare_rooms_for_calc([room], schedule=schedule)
    assert prep["frameless"]["source"] == "ziniarastis_misrus" and prep["frameless"]["value"] is False
    out = ur.calc_room_quantities(room)
    assert out["pasleptu_duru_staktu_m"] == round(0.9 + 4.2, 2) and out["pasleptu_duru_kompl"] == 1
    assert hidden_door_count(room["elementai"], frameless_default=False) == 1


def test_the_assumptions_evidence_ladder():
    rooms = [_room("03", [{"tipas": "pasleptos_duris", "kiekis": 1}, door(800)])]
    by_note = ur.settle_frameless_default(rooms, schedule={"pastaba_visos": True, "sakinys": "brėžinio pastaba…"})
    assert (by_note["value"], by_note["source"]) == (True, "pastaba")
    by_anno = ur.settle_frameless_default(rooms, schedule={"anotacijos_beapvadines": 2, "sakinys": "plane 2 angos…"})
    assert (by_anno["value"], by_anno["source"]) == (True, "anotacija") and "tokiomis pat" in by_anno["sakinys"]
    by_board = ur.settle_frameless_default(rooms, schedule={"gaminiai": ["DECO-10 vidaus durys"], "sakinys": "apdailos lape…"})
    assert (by_board["value"], by_board["source"]) == (False, "gaminiai") and "su apvadais" in by_board["sakinys"]
    his = ur.settle_frameless_default(rooms, overrides={"vidaus_durys_beapvadines": False},
                                      schedule={"beapvadines": 2, "sakinys": "…"})
    assert (his["value"], his["source"]) == (False, "jusu")
    none = ur.settle_frameless_default([_room("09", [door(800)])], schedule={"status": "nera", "sakinys": "Durų žiniaraščio ar durų tipo užrašų brėžinyje nėra."})
    assert (none["value"], none["source"]) == (False, "nera_pozymiu") and "patvirtinkite" in none["sakinys"]


def test_a_door_wider_than_a_door_is_a_passage_and_no_frameless_frame():
    """objektas_h: a 2,0 m opening between the corridor and the kitchen came back as a hidden door —
    „durys 1,40 pločio nebus tikrai" (the founder, 2026-09-23)."""
    kitchen = _room("04", [{"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 2000, "aukstis_mm": 2100}, door(800, 2100)])
    ur.settle_frameless_default([kitchen], overrides={"vidaus_durys_beapvadines": True})
    out = ur.calc_room_quantities(kitchen)
    assert out["pasleptu_duru_staktu_m"] == round(0.8 + 4.2, 2) and out["pasleptu_duru_kompl"] == 1
    assert hidden_door_count(kitchen["elementai"], frameless_default=True) == 1
    # …unless the drawing's schedule names it a door of that size
    kitchen["elementai"][0][ur.SCHEDULE_TYPE_KEY] = "beapvadines"
    assert ur.calc_room_quantities(kitchen)["pasleptu_duru_kompl"] == 2


def test_his_su_apvadais_covers_the_plans_hidden_door_symbols_and_the_schedule_still_wins():
    """The question's own words: „su apvadais ji nereikalinga" — the row goes, symbols and all."""
    room = _room("03", [{"tipas": "pasleptos_duris", "kiekis": 2, "plotis_mm": 900, "aukstis_mm": 2100}, door(800, 2100)])
    ur.prepare_rooms_for_calc([room], overrides={"vidaus_durys_beapvadines": False})
    assert ur.calc_room_quantities(room)["pasleptu_duru_staktu_m"] == 0
    assert hidden_door_count(room["elementai"], frameless_default=False, chosen_framed=True) == 0
    # a door the drawing's schedule names frameless is not a symbol — it stays
    room["elementai"][1][ur.SCHEDULE_TYPE_KEY] = "beapvadines"
    assert ur.calc_room_quantities(room)["pasleptu_duru_kompl"] == 1
    # with no choice of his, the symbols count as before
    ur.prepare_rooms_for_calc([room], overrides={})
    room["elementai"][1].pop(ur.SCHEDULE_TYPE_KEY, None)          # the pass already cleared it: no schedule
    assert ur.calc_room_quantities(room)["pasleptu_duru_kompl"] == 3    # 2 tagged + the untagged one under the assumption

"""Round 13 (audit 2026-09-29, geometry-lanes-8): the door schedule's frame words and size tokens.

„be apvadų" — with its space — is FRAMELESS (a look-behind for „be" did not see „be " and read it as framed),
„paslėpta stakta" is frameless too, a size written as one „910x2100" token is read, and a row that names both
frame types is counted as neither — the sentence asks to check it, nothing is settled from it."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.door_schedule import _row_size, _row_type, scan_door_schedule  # noqa: E402


def _pdf(items: list[tuple[float, float, str]]) -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(1191, 842))
    c.setFont("Helvetica", 9)
    for x, y, text in items:
        c.drawString(x, 842 - y, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _sheet(rows, note=None):
    """A schedule: rows of (code, size cells, type text); the codes stand once more on the plan."""
    items = [(120, 200, "Patalpų eksplikacija"), (120, 215, "01. Įėjimo koridorius 4.05 m²"),
             (838, 358, "Durų žiniaraštis"), (838, 380, "Kodas"), (890, 380, "Matmenys, mm"), (1040, 380, "Tipas")]
    y = 411
    for kodas, sizes, tipas in rows:
        items.append((840, y, kodas))
        for k, s in enumerate(sizes):
            items.append((890 + 70 * k, y, s))
        items.append((1010, y, tipas))
        y += 31
    for k, (kodas, _, _) in enumerate(rows):
        items.append((316 + 120 * k, 468, kodas))
    if note:
        items.append((120, 715, note))
    items.append((120, 760, "Pastabos: matmenys tikslinami vietoje, angos matuojamos iki apdailos. " * 3))
    return _pdf(items)


def test_be_apvadu_with_a_space_is_frameless():
    assert _row_type("Dešininės, be apvadų") == "beapvadines"
    assert _row_type("beapvadinės") == "beapvadines"
    assert _row_type("su paslėpta stakta") == "beapvadines"
    assert _row_type("su apvadais") == "su_apvadais"
    assert _row_type("Apvadai MDF") == "su_apvadais"
    out = scan_door_schedule(_sheet([("D-1", ["910", "2100"], "Dešininės, be apvadų"),
                                     ("D-2", ["810", "2100"], "Kairinės, be apvadų")]))
    assert out["status"] == "lentele"
    assert [r["tipas"] for r in out["lentele"]["eilutes"]] == ["beapvadines", "beapvadines"]
    assert (out["beapvadines"], out["su_apvadais"]) == (2, 0) and "su apvadais nėra" in out["sakinys"]


def test_a_size_written_as_one_token_is_read():
    assert _row_size("910x2100 Dešininės", []) == (910, 2100)
    assert _row_size("810 × 2050", []) == (810, 2050)
    assert _row_size("700*2000", []) == (700, 2000)
    out = scan_door_schedule(_sheet([("D-1", ["910x2100"], "beapvadinės"), ("D-2", ["810×2100"], "su apvadais")]))
    rows = {r["kodas"]: r for r in out["lentele"]["eilutes"]}
    assert (rows["D-1"]["plotis_mm"], rows["D-1"]["aukstis_mm"]) == (910, 2100)
    assert (rows["D-2"]["plotis_mm"], rows["D-2"]["aukstis_mm"]) == (810, 2100)
    assert "D-1 910×2100 beapvadinės" in out["sakinys"]


def test_a_row_with_both_frame_words_settles_nothing_and_says_so():
    assert _row_type("D-1 be apvadų / D-2 su apvadais") == "neaisku"
    out = scan_door_schedule(_sheet([("D-1", ["910", "2100"], "be apvadų arba su apvadais")]))
    row = out["lentele"]["eilutes"][0]
    assert row["tipas"] == "neaisku"
    assert (out["beapvadines"], out["su_apvadais"], out["kitos"], out["neaiskios"]) == (0, 0, 1, 1)
    assert out["neaiskus_kodai"] == ["D-1"]
    assert "D-1 eilutėje užrašyta ir „be apvadų“, ir „su apvadais“ — patikrinkite" in out["sakinys"]
    # the project assumption is not settled by the schedule: neither type is counted from that row
    room = {"nr": "01", "pavadinimas": "P01", "plotas_m2": 12.0, "perimetras_m": 14.0, "lubu_aukstis_m": 2.7,
            "elementai": [{"tipas": "duris", "kiekis": 1}]}
    settled = ur.settle_frameless_default([room], schedule=out)
    assert settled["source"] not in ("ziniarastis", "ziniarastis_misrus")


def test_notes_with_the_spaced_negation_are_read():
    out = scan_door_schedule(_pdf([(100, 100, "PASTABOS: Visos vidaus durys be apvadų."),
                                   (100, 130, "Durų staktas ruošti be apvadinėms durims."),
                                   (100, 160, "x" * 220)]))
    assert out["pastaba_visos"] is True and out["pastaba_beapvadines"] is True

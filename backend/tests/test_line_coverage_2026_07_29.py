"""Line-coverage pass 2026-07-29 — the contractor lines we used to emit NOTHING for.

Measured against Beržų g. 24 (`ground_truth/berzas/contractor_samata_parsed.json`,
53 priced lines): 13 of his lines had no counterpart in our kiekių žiniaraštis at
all. `scripts/reconcile_samata_lines.py` scores the set; this file pins the
behaviour those rows depend on.

Three groups, three different contracts:

  · HONESTY CHECKLIST (nr 4, 5, 6, 8, 11, 12, 21) — bespoke GKP carpentry and
    the magnetic TRACK rail. Described in the interjero projekto TEKSTE and the
    išklotinės, never in a symbol legend, never as a readable dimension. Emitted
    with `kiekis=None` so the contractor SEES the omission before he quotes,
    instead of discovering it after. The invariants below are what make such a
    row safe to ship: it must never turn into a number, never carry a price,
    and never reach the client's PDF as a silent 0,00 €.

  · COMPUTED (nr 35) — plytelių grindjuostės. `calc_room_quantities` zeroes
    `grindjuosciu_m` on every tile-floor room, so the skirting in tambūras /
    katilinė vanished entirely. Same primitives as the MDF line; ground truth
    (`gt_per_room` 101 = 10.32 m, 106 = 11.80 m) validates the result.

  · RELABEL (nr 7) — the work existed under a name no samata uses. Renaming a
    line is only safe together with the legacy map in api/recompute_quantities,
    or a recompute shows the user the same work twice.
"""
from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

from extractor.vision_call import (  # noqa: E402
    _build_pozicijos_from_rooms,
    _emit_v8_compat_fields,
    _recompute_per_room_via_python,
)
from api.recompute_quantities import _merge_user_edits  # noqa: E402


# ── fixtures ─────────────────────────────────────────────────────────────────

def _run(parsed: dict) -> dict:
    p = copy.deepcopy(parsed)
    p = _recompute_per_room_via_python(p, None)
    return _build_pozicijos_from_rooms(p)


@pytest.fixture
def gkp_project() -> dict:
    """Two rooms with GKP ceilings + a wet room + a tiled-floor tambūras.

    Shaped like a real interior fit-out: the checklist gates key off GKP works
    existing, so a fixture without them proves nothing.
    """
    return {
        "archetipas": "standart",
        "patalpos": [
            {"nr": "101", "pavadinimas": "Tambūras", "paskirtis": "tamburas",
             "plotas_m2": 11.0, "perimetras_m": 13.5, "lubu_aukstis_m": 2.8,
             "lubu_tipas": "gkp", "confidence": "high",
             "elementai": [
                 {"tipas": "duris", "kiekis": 3, "plotis_mm": 900, "aukstis_mm": 2100}]},
            {"nr": "102", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.8,
             "lubu_tipas": "gkp", "confidence": "high",
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100},
                 {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500}]},
            {"nr": "103", "pavadinimas": "Vonia", "paskirtis": "vonia",
             "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
             "lubu_tipas": "gkp", "plyteles_sienos_aukstis_m": 2.2,
             "confidence": "high",
             "elementai": [
                 {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}]},
        ],
        "detected_symbols_summary": {"sviestuvai": 12, "rozetes": 20},
    }


def _berzas() -> dict:
    path = REPO / "ground_truth" / "berzas" / "ai_extract.json"
    if not path.exists():
        pytest.skip("berzas cached extract not present")
    return json.loads(path.read_text(encoding="utf-8"))


def _checklist(poz: list[dict]) -> list[dict]:
    return [p for p in poz if p.get("saltinis") == "checklist"]


def _labels(poz: list[dict]) -> list[str]:
    return [p.get("aprasymas") or "" for p in poz]


def _has(poz: list[dict], needle: str) -> list[dict]:
    return [p for p in poz if needle.lower() in (p.get("aprasymas") or "").lower()]


# ── 1. the checklist-row contract ────────────────────────────────────────────

def test_every_checklist_row_is_null_red_and_lithuanian(gkp_project):
    """The four properties that make an unfilled row honest instead of wrong."""
    poz = _run(gkp_project)["pozicijos"]
    rows = _checklist(poz)
    assert rows, "no checklist rows emitted at all"
    for p in rows:
        label = p["aprasymas"]
        assert p["kiekis"] is None, f"{label}: checklist row carries a quantity"
        # apply_confidence maps low → raudona; red is what the UI renders.
        assert p.get("confidence") == "raudona", f"{label}: {p.get('confidence')}"
        assert "suveskite" in label.lower(), f"{label}: no LT call to action"
        assert p.get("vnt"), f"{label}: no unit"
        assert p.get("_assumption"), f"{label}: no hint where to look"
        assert "Kur ieškoti" in p["_assumption"] or "planas" in p["_assumption"]
        assert not any(ch in label for ch in "?<>"), label


def test_checklist_row_carries_no_price_or_sum(gkp_project):
    poz = _run(gkp_project)["pozicijos"]
    for p in _checklist(poz):
        assert p.get("kaina") in (None, 0)
        assert p.get("suma") in (None, 0)
        assert "medziagos_kiekis" not in p, p["aprasymas"]


# ── 2. the bespoke-GKP block (berzas nr 4, 5, 6, 8, 12) ──────────────────────

BESPOKE = [
    ("GKP „dėžučių“ montavimas ant lubų", "m"),      # nr 4  — 11.16 m
    ("Nišų pertvarose įrengimas", "m"),               # nr 5  —  9.11 m
    ("Pertvarų storinimas", "m2"),                    # nr 6  —  6.24 m²
    ("Gipso kartono klijavimas sienai išlyginti", "m2"),  # nr 8 — 9.64 m²
]


@pytest.mark.parametrize("needle,unit", BESPOKE)
def test_bespoke_gkp_checklist_row_emitted(gkp_project, needle, unit):
    poz = _run(gkp_project)["pozicijos"]
    rows = _has(poz, needle)
    assert len(rows) == 1, f"{needle}: {len(rows)} rows"
    assert rows[0]["skyrius"] == "GKP montavimas"
    assert rows[0]["vnt"] == unit
    assert rows[0]["saltinis"] == "checklist"


def test_bespoke_gkp_block_absent_without_gkp_works(gkp_project):
    """No GKP ceilings and no niches → the carpentry checklist is noise."""
    p = copy.deepcopy(gkp_project)
    for r in p["patalpos"]:
        r["lubu_tipas"] = "betonines"
    poz = _run(p)["pozicijos"]
    for needle, _ in BESPOKE:
        assert not _has(poz, needle), needle


def test_ortakiu_dezute_gated_on_ducts(gkp_project):
    """nr 12 fires only when ducts were actually read — otherwise there is no
    duct to box in and the row is pure noise."""
    assert not _has(_run(gkp_project)["pozicijos"], "ortakiams paslėpti")
    p = copy.deepcopy(gkp_project)
    p["detected_symbols_summary"] = {**p["detected_symbols_summary"],
                                     "ortakiai_d125_m": 18.0}
    rows = _has(_run(p)["pozicijos"], "ortakiams paslėpti")
    assert len(rows) == 1 and rows[0]["kiekis"] is None


# ── 3. TRACK apšvietimas (berzas nr 11 + 21) ─────────────────────────────────

def test_track_pair_emitted_when_a_lighting_plan_was_read(gkp_project):
    poz = _run(gkp_project)["pozicijos"]
    rows = _has(poz, "TRACK apšvietimo sistemos")
    assert len(rows) == 2, _labels(rows)
    assert {r["aprasymas"].split("—")[0].strip().split()[-1] for r in rows} == {
        "montavimas", "apdirbimas"}, _labels(rows)
    assert all(r["skyrius"] == "Elektros instaliacijos darbai" for r in rows)
    assert all(r["vnt"] == "m" and r["kiekis"] is None for r in rows)


def test_track_absent_when_no_lighting_symbols(gkp_project):
    p = copy.deepcopy(gkp_project)
    p["detected_symbols_summary"] = {"rozetes": 20}
    assert not _has(_run(p)["pozicijos"], "TRACK apšvietimo sistemos")


# ── 4. plytelių grindjuostės (berzas nr 35, 22.72 m) ─────────────────────────

def test_plyteliu_grindjuostes_matches_the_contractor_on_berzas():
    poz = _build_pozicijos_from_rooms(_berzas())["pozicijos"]
    rows = _has(poz, "Plytelių grindjuosčių supjovimas")
    assert len(rows) == 1
    line = rows[0]
    assert line["skyrius"] == "Plytelių klijavimas"
    assert line["vnt"] == "m"
    # Contractor nr 35 = 22.72 m (his notes: tambūras 10.32 + katilinė 11.80).
    assert abs(line["kiekis"] - 22.72) / 22.72 < 0.10, line["kiekis"]


def test_plyteliu_grindjuostes_skip_wet_rooms(gkp_project):
    """A fully tiled vonia has no skirting — the walls are tiled to height.
    Only the tambūras (tiled floor, painted walls) may contribute."""
    p = copy.deepcopy(gkp_project)
    out = _run(p)
    rooms = {r["nr"]: r for r in out["patalpos"]}
    assert float(rooms["103"].get("plyteles_grindys_m2") or 0) > 0, "vonia not tiled"
    rows = _has(out["pozicijos"], "Plytelių grindjuosčių supjovimas")
    assert len(rows) == 1
    expected = round(max(0.0, 13.5 - 3 * 0.85) * 1.10, 2)   # tambūras only
    assert rows[0]["kiekis"] == expected, rows[0]["kiekis"]


def test_plyteliu_grindjuostes_do_not_double_count_the_mdf_line():
    """The MDF line is unchanged: tile-floor rooms were already 0 there."""
    poz = _build_pozicijos_from_rooms(_berzas())["pozicijos"]
    mdf = _has(poz, "Grindjuosčių sumontavimas")
    tile = _has(poz, "Plytelių grindjuosčių supjovimas")
    assert len(mdf) == 1 and len(tile) == 1
    # Grindjuostės are wall work → the Sienų half of the 2026-09-02 split.
    assert mdf[0]["skyrius"] == "Sienų glaistymas dažymas"
    assert mdf[0]["kiekis"] != tile[0]["kiekis"]


# ── 5. the relabel (berzas nr 7) ─────────────────────────────────────────────

_LEGACY_WC = "Dėžučių iš GKP formavimas WC mechanizmams paslėpti"
_NEW_WC = "Pertvaros sutvirtinimas WC mechanizmams montuoti (GKP dėžutė)"


def test_wc_line_uses_the_contractor_wording(gkp_project):
    poz = _run(gkp_project)["pozicijos"]
    assert _labels(_has(poz, "WC mechanizmams")) == [_NEW_WC]
    assert not _has(poz, _LEGACY_WC)


def test_legacy_wc_label_folds_into_the_rename_instead_of_duplicating():
    """A project priced under the old label must NOT come back with both rows."""
    rebuilt = [{"skyrius": "GKP montavimas", "aprasymas": _NEW_WC,
                "vnt": "vnt", "kiekis": 2}]
    prior = [{"skyrius": "GKP montavimas", "aprasymas": _LEGACY_WC,
              "vnt": "vnt", "kiekis": 2, "kaina": 35.0, "suma": 70.0}]
    notes: list = []
    merged = _merge_user_edits(rebuilt, prior, notes)
    assert len(merged) == 1, _labels(merged)
    assert merged[0]["aprasymas"] == _NEW_WC
    assert merged[0]["kaina"] == 35.0        # the money followed the rename
    assert any(n.get("reason") == "relabeled" for n in notes), notes


def test_legacy_wc_label_folds_even_without_a_price():
    """Un-priced legacy row: pass 2 can't fire (no user edit to carry), so the
    legacy map has to catch it in pass 3 or the user sees the work twice."""
    rebuilt = [{"skyrius": "GKP montavimas", "aprasymas": _NEW_WC,
                "vnt": "vnt", "kiekis": 2}]
    prior = [{"skyrius": "GKP montavimas", "aprasymas": _LEGACY_WC,
              "vnt": "vnt", "kiekis": 2}]
    notes: list = []
    merged = _merge_user_edits(rebuilt, prior, notes)
    assert _labels(merged) == [_NEW_WC], _labels(merged)
    assert [n["reason"] for n in notes] == ["relabeled"]


# ── 6. checklist rows through the merge + export payload ─────────────────────

def test_checklist_rows_survive_a_recompute_merge_unpriced(gkp_project):
    """The orphan-carry rules (2026-07-28) must not invent a quantity for a
    null row, and a null row must not lose its checklist provenance."""
    poz = _run(gkp_project)["pozicijos"]
    prior = [dict(p) for p in poz]
    merged = _merge_user_edits([dict(p) for p in poz], prior, [])
    assert len(merged) == len(poz), "merge duplicated or dropped rows"
    for p in _checklist(merged):
        assert p["kiekis"] is None
        assert p.get("suma") in (None, 0)


def test_checklist_row_reaches_darbu_sarasas_as_null_not_zero(gkp_project):
    """`_emit_v8_compat_fields` is what the Kiekiai table, the totals and the
    export all read. A None that became 0 there would present unquoted work as
    a real zero-quantity line."""
    out = _run(gkp_project)
    out = _emit_v8_compat_fields(out)
    by_label = {r["aprasymas"]: r for r in out["darbu_sarasas"]}
    for p in _checklist(out["pozicijos"]):
        row = by_label[p["aprasymas"]]
        assert row["kiekis"] is None, f"{p['aprasymas']}: {row['kiekis']!r}"


def test_null_row_cannot_become_a_silent_zero_euro_line_in_excel(monkeypatch):
    """End of the chain: even if a null row DOES reach /generate-excel (the
    frontend filters `kiekis > 0` first), its Kiekis cell must stay empty and
    the sąmata total must be identical to the same payload without it."""
    import auth
    import main
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    client = TestClient(main.app)

    real = {"nr": "1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
            "kiekis": 100.0, "kaina": 12.0, "suma": 1200.0, "skyrius": "APDAILA"}
    null_row = {"nr": "2",
                "aprasymas": "Nišų pertvarose įrengimas — suveskite ilgį",
                "mato_vnt": "m", "kiekis": None, "kaina": None, "suma": None,
                "skyrius": "APDAILA"}

    def _totals(rows):
        r = client.post("/generate-excel",
                        json={"projektas": "Test", "tipas": "kz", "eilutes": rows})
        assert r.status_code == 200, r.text
        wb = load_workbook(io.BytesIO(r.content))
        ws = wb[wb.sheetnames[0]]
        cells = {}
        for row in ws.iter_rows(min_row=4):
            label = row[1].value
            if label:
                cells[str(label)] = row[3].value      # Kiekis column
        return cells

    with_null = _totals([real, null_row])
    assert with_null[null_row["aprasymas"]] is None, with_null
    assert with_null["Sienų dažymas"] == 100.0


def test_null_row_prints_blank_cells_not_the_word_none_in_the_pdf(monkeypatch):
    """Same row through /generate-pdf. It used to render literally
    "… — suveskite ilgį m None None None" in the document the contractor hands
    his client; the grand total was right, the page was not."""
    import auth
    import main
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    client = TestClient(main.app)
    rows = [
        {"nr": "1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
         "kiekis": 100.0, "kaina": 12.0, "suma": 1200.0, "skyrius": "APDAILA"},
        {"nr": "2", "aprasymas": "Nišų pertvarose įrengimas — suveskite ilgį",
         "mato_vnt": "m", "kiekis": None, "kaina": None, "suma": None,
         "skyrius": "APDAILA"},
    ]
    r = client.post("/generate-pdf",
                    json={"projektas": "T", "tipas": "kz", "eilutes": rows})
    assert r.status_code == 200, r.text
    import pdfplumber
    with pdfplumber.open(io.BytesIO(r.content)) as doc:
        text = "\n".join((p.extract_text() or "") for p in doc.pages)
    assert "None" not in text, [l for l in text.splitlines() if "None" in l]
    # the priced row and the total are untouched
    assert any("100,00" in l and "1 200,00" in l.replace(" ", " ")
               for l in text.splitlines()), text
    assert any("1 452,00" in l.replace(" ", " ") for l in text.splitlines()), text

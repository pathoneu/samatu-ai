"""An export's sections come out in the order a sąmata is read in.

F13(a), 2026-09-02 final review. `_sequential_export_nr` grouped sections by
FIRST APPEARANCE, which is right for de-duplicating headers and wrong for
order: a legacy blob whose first paint row is "Lubų karnizo sumontavimas"
migrates into the Lubų section and dragged it in front of Sienų. Sienų comes
before Lubų everywhere else in the product.

The second test here is the drift guard for the duplicated order map: main.py
cannot import vision_call at module level (circular), so the ranks are
literals. Rather than compare the two tables, this builds real positions with
the canonical builder and asserts the export reproduces the section sequence
the builder itself chose.
"""
from __future__ import annotations

import random

import pytest

import main
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms

SK_SIENOS = "Sienų glaistymas dažymas"
SK_LUBOS = "Lubų glaistymas dažymas"
SK_MERGED = "Sienų lubų glaistymas dažymas"


def _sections(rows: list[dict]) -> list[str]:
    """The section sequence a printed export would show — one entry per header,
    i.e. collapsed on change, which is exactly how both exporters emit them."""
    out: list[str] = []
    for r in rows:
        s = (r.get("skyrius") or "").strip()
        if not out or out[-1] != s:
            out.append(s)
    return out


def _row(nr: int, skyrius: str, aprasymas: str) -> dict:
    return {"nr": str(nr), "skyrius": skyrius, "aprasymas": aprasymas,
            "vnt": "m2", "kiekis": 10.0}


def test_the_ceiling_section_never_overtakes_the_walls(monkeypatch):
    """The reported shape: a legacy blob under the merged section name whose
    FIRST row is ceiling work."""
    legacy = [
        _row(1, SK_MERGED, "Lubų karnizo sumontavimas"),
        _row(2, SK_MERGED, "Sienų glaistymas 2 sluoksniais"),
        _row(3, SK_MERGED, "Lubų dažymas"),
        _row(4, SK_MERGED, "Sienų gruntavimas"),
    ]
    out = main._sequential_export_nr(legacy)
    assert _sections(out) == [SK_SIENOS, SK_LUBOS]
    # …and the rows are renumbered 1..N with no gaps, as before.
    assert [r["nr"] for r in out] == ["1", "2", "3", "4"]


def test_sections_group_and_rank_however_the_rows_were_shuffled():
    rows = [
        _row(1, "Medžiagos", "Dažai"),
        _row(2, SK_LUBOS, "Lubų dažymas"),
        _row(3, "Grindys", "Laminatas"),
        _row(4, SK_SIENOS, "Sienų dažymas"),
        _row(5, "GKP montavimas", "GKP lubos"),
        _row(6, "Grindys", "Grindjuostės"),
        _row(7, SK_SIENOS, "Sienų gruntavimas"),
    ]
    for seed in range(8):
        shuffled = list(rows)
        random.Random(seed).shuffle(shuffled)
        assert _sections(main._sequential_export_nr(shuffled)) == [
            SK_SIENOS, SK_LUBOS, "GKP montavimas", "Grindys", "Medžiagos",
        ], f"seed {seed}"


def test_an_unknown_section_lands_last_in_first_appearance_order():
    """We must not invent an order for something we do not recognise — but it
    still has to GROUP, or the duplicate-header bug comes back."""
    rows = [
        _row(1, "Nežinomas B", "x"),
        _row(2, SK_LUBOS, "Lubų dažymas"),
        _row(3, "Nežinomas A", "y"),
        _row(4, SK_SIENOS, "Sienų dažymas"),
        _row(5, "Nežinomas B", "z"),
    ]
    assert _sections(main._sequential_export_nr(rows)) == [
        SK_SIENOS, SK_LUBOS, "Nežinomas B", "Nežinomas A",
    ]


def test_a_tender_kz_keeps_its_own_numbering_and_order():
    """Hierarchical positions ("1.1", "2.14") are the client's reference — the
    export may not renumber OR re-sort them."""
    rows = [
        _row(0, SK_LUBOS, "Lubų dažymas"),
        _row(0, SK_SIENOS, "Sienų dažymas"),
    ]
    rows[0]["nr"], rows[1]["nr"] = "2.14", "1.1"
    out = main._sequential_export_nr(rows)
    assert [r["nr"] for r in out] == ["2.14", "1.1"]
    assert _sections(out) == [SK_LUBOS, SK_SIENOS]


def test_the_export_order_matches_the_builders_own(monkeypatch):
    """Drift guard for the duplicated rank table in main.py.

    Build a project rich enough to emit most sections, take the order the
    CANONICAL builder put them in, then hand the same rows to the export
    shuffled. The export must reproduce the builder's sequence exactly.
    """
    def _room(nr, paskirtis, plotas, perimetras):
        r = {"nr": nr, "pavadinimas": nr, "paskirtis": paskirtis,
             "plotas_m2": plotas, "perimetras_m": perimetras,
             "lubu_aukstis_m": 2.7, "elementai": []}
        r.update(calc_room_quantities(r))
        return r

    parsed = _build_pozicijos_from_rooms({
        "patalpos": [
            _room("101", "gyvenamoji", 20.0, 18.0),
            _room("102", "vonia", 6.0, 10.0),
            _room("103", "virtuve", 12.0, 14.0),
        ],
        "santrauka": {},
    })
    poz = [dict(p) for p in parsed["pozicijos"]]
    builder_sections = _sections(poz)
    # Enough breadth for the guard to be worth anything.
    assert len(builder_sections) >= 4, builder_sections
    assert len(set(builder_sections)) == len(builder_sections), \
        f"the builder itself emitted a section twice: {builder_sections}"

    for i, p in enumerate(poz, 1):
        p["nr"] = str(i)
    for seed in range(5):
        shuffled = list(poz)
        random.Random(seed).shuffle(shuffled)
        assert _sections(main._sequential_export_nr(shuffled)) == builder_sections, \
            f"seed {seed}: main._EXPORT_SKYRIUS_RANK has drifted from " \
            f"vision_call's SKYRIUS_ORDER"


def test_every_ranked_section_is_a_name_the_enum_knows():
    """A typo in the rank table would silently sort that section to 999."""
    from extractor.vision_call import _SKYRIUS_ENUM
    unknown = [s for s in main._EXPORT_SKYRIUS_RANK if s not in _SKYRIUS_ENUM]
    # "Ventiliacijos darbai" is emitted by the builder but was never added to
    # _SKYRIUS_ENUM — that gap is pre-existing and not this change's to close.
    assert unknown == ["Ventiliacijos darbai"], unknown

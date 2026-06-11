"""apdailos_reader reconstruction tests (module was lost from git; rebuilt from
the surviving .pyc + the universal_rules consumer contract).

The critical regression: without sienu_apdailos_breakdown, calc_room_quantities
falls to the legacy paskirtis path that hardcodes walls_paint=0 for tamburas/
garazas and full-tile-clips wet rooms to 0. merge_apdailos_into_rooms must set
the breakdown so the apdailos branch (universal_rules.py:707-745) restores paint.
"""
from extractor.apdailos_reader import merge_apdailos_into_rooms, build_user_text
from extractor.universal_rules import calc_room_quantities


def _room(nr, paskirtis, **kw):
    r = {"nr": nr, "pavadinimas": paskirtis.title(), "paskirtis": paskirtis,
         "plotas_m2": 16.0, "perimetras_m": 16.0, "lubu_aukstis_m": 2.8, "elementai": []}
    r.update(kw)
    return r


def test_merge_sets_breakdown_and_tile_height():
    rooms = [_room("101", "tamburas"), _room("105", "garazas")]
    result = {"status": "ok", "patalpos": [
        {"nr": "101", "sienu_apdaila": {"dazymas_share": 1.0, "plyteles_share": 0.0},
         "plyteliu_aukstis_m": None, "pastabos": "dažoma"},
        {"nr": "105", "sienu_apdaila": {"dazymas_share": 0.8, "plyteles_share": 0.0},
         "plyteliu_aukstis_m": None, "pastabos": "dažoma"},
    ]}
    n = merge_apdailos_into_rooms(rooms, result)
    assert n == 2
    assert rooms[0]["sienu_apdailos_breakdown"]["dazymas_share"] == 1.0
    assert rooms[0].get("_apdailos_pastabos") == "dažoma"


def test_apdailos_restores_walls_paint_for_tamburas():
    # Tamburas with NO breakdown → legacy path → walls_paint = 0 (the bug).
    bug = calc_room_quantities(_room("101", "tamburas"))
    assert float(bug.get("walls_paintable_m2") or 0) == 0.0, "precondition: legacy zeros tamburas"
    # With the apdailos breakdown (mostly paint) → apdailos path → walls_paint > 0.
    rooms = [_room("101", "tamburas")]
    merge_apdailos_into_rooms(rooms, {"status": "ok", "patalpos": [
        {"nr": "101", "sienu_apdaila": {"dazymas_share": 1.0, "plyteles_share": 0.0},
         "plyteliu_aukstis_m": None, "pastabos": ""}]})
    fixed = calc_room_quantities(rooms[0])
    assert float(fixed.get("walls_paintable_m2") or 0) > 20.0, fixed.get("walls_paintable_m2")


def test_merge_skipped_status_is_noop():
    rooms = [_room("101", "tamburas")]
    assert merge_apdailos_into_rooms(rooms, {"status": "skipped"}) == 0
    assert "sienu_apdailos_breakdown" not in rooms[0]


def test_build_user_text_lists_rooms_and_schema():
    txt = build_user_text([{"nr": "101", "pavadinimas": "Tambūras", "plotas_m2": 5.0}])
    assert "Tambūras" in txt
    assert "sienu_apdaila" in txt          # schema present
    assert "dazymas_share" in txt


def test_find_apdailos_page_skips_vizualizacija(monkeypatch):
    # Bacevičiaus regression: the reader classified finishes from RENDERS.
    import extractor.apdailos_reader as ar

    class _Page:
        def __init__(self, text): self._t = text
        def extract_text(self): return self._t

    class _Pdf:
        def __init__(self, pages): self.pages = pages
        def __enter__(self): return self
        def __exit__(self, *a): return False

    pages = [_Page("TITULINIS"),
             _Page("INTERJERO VIZUALIZACIJA. APDAILŲ PLANAS fragmentas"),  # render — skip
             _Page("GRINDŲ APDAILOS PLANAS"),                              # ok, prio 1
             _Page("SIENŲ IŠKLOTINIŲ IR APDAILŲ PLANAS")]                  # best, prio 0
    monkeypatch.setattr(ar.pdfplumber, "open", lambda *_a, **_k: _Pdf(pages))
    assert ar._find_apdailos_page(b"x") == 4


def test_find_apdailos_pages_returns_all_iskotines(monkeypatch):
    # Multi-page TPs: per-room išklotinės across many sheets — return them ALL.
    import extractor.apdailos_reader as ar

    class _Page:
        def __init__(self, text): self._t = text
        def extract_text(self): return self._t

    class _Pdf:
        def __init__(self, pages): self.pages = pages
        def __enter__(self): return self
        def __exit__(self, *a): return False

    pages = [_Page("TITULINIS"), _Page("VIZUALIZACIJA IŠKLOTINĖ"),
             _Page("SIENŲ IŠKLOTINĖS L1"), _Page("SIENŲ IŠKLOTINĖS L2"),
             _Page("GRINDŲ APDAILOS PLANAS")]
    monkeypatch.setattr(ar.pdfplumber, "open", lambda *_a, **_k: _Pdf(pages))
    assert ar._find_apdailos_pages(b"x") == [3, 4, 5]  # išklotinės first, render skipped

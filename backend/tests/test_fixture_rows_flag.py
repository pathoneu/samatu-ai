"""v3 W5-E E5 — bathtub and floor-drain rows behind SAMATU_BATH_DRAIN_ROWS (default off)."""
import json

from extractor import fixture_rows_flag as fr
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _parsed(**extra):
    room = {"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys",
            "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "n_doors": 1, "n_windows": 0}
    room.update(calc_room_quantities(room))
    blob = {"patalpos": [room], "santrauka": {}}
    blob.update(extra)
    return json.loads(json.dumps(blob))


def _rows(monkeypatch, flag, **extra):
    if flag is None:
        monkeypatch.delenv(fr.FLAG_ENV, raising=False)
    else:
        monkeypatch.setenv(fr.FLAG_ENV, flag)
    return _build_pozicijos_from_rooms(_parsed(**extra))["pozicijos"]


# v4 3c-2: the tub-only count is the legend's (the plumbing reader is gone)
TUBS = {"detected_symbols_summary": {"vonios": 2},
        "_meta": {"legendos_siulymai": {"status": "ok", "lapai_su_legenda": [4],
                                        "seimos": {"vonios_kubilai": {"kiekis": 2, "tekstas": "Vonia", "lapai": [4]}}}}}
DRAINS = {fr.LEGEND_COUNTS_KEY: {"trapai": {"kiekis": 3, "tekstas": "Trapas"}}}


def test_flag_off_changes_nothing(monkeypatch):
    for extra in ({}, TUBS, DRAINS, {"detected_symbols_summary": {"vonios": 1}}):
        a = _rows(monkeypatch, None, **extra)
        b = _rows(monkeypatch, "0", **extra)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        assert not any(str(p.get("aprasymas", "")).startswith((fr.BATHTUB_ROW, fr.DRAIN_ROW)) for p in a)


def test_bathtub_row_from_the_tub_only_count(monkeypatch):
    poz = _rows(monkeypatch, "1", **TUBS)
    row = next(p for p in poz if p["aprasymas"] == fr.BATHTUB_ROW)
    assert row["kiekis"] == 2 and row["vnt"] == "vnt" and "santechnikos plane" in row["_confidence_reason"]


def test_tub_or_tray_without_a_reading_is_a_question(monkeypatch):
    poz = _rows(monkeypatch, "1", detected_symbols_summary={"vonios": 1})
    row = next(p for p in poz if p["aprasymas"].startswith(fr.BATHTUB_ROW))
    assert row["kiekis"] is None and row["aprasymas"].endswith("suveskite kiekį")


def test_no_tub_read_no_billed_row(monkeypatch):
    # v4 3c-2: no legend count of a bathtub → never a number, only the question
    poz = _rows(monkeypatch, "1", detected_symbols_summary={"vonios_kubilai": 0, "vonios": 1})
    assert all(p["kiekis"] is None for p in poz if p["aprasymas"].startswith(fr.BATHTUB_ROW))


def test_drains_only_from_a_legend_count(monkeypatch):
    poz = _rows(monkeypatch, "1", **DRAINS)
    row = next(p for p in poz if p["aprasymas"] == fr.DRAIN_ROW)
    assert row["kiekis"] == 3 and "„Trapas“" in row["_confidence_reason"]
    # the main pass's glance is not a reading
    poz = _rows(monkeypatch, "1", detected_symbols_summary={"trapai": 4})
    assert not any(p["aprasymas"] == fr.DRAIN_ROW for p in poz)


def test_legend_count_shape():
    assert fr.legend_count({fr.LEGEND_COUNTS_KEY: {"trapai": {"kiekis": "2"}}}, "trapai") == (2, "")
    assert fr.legend_count({fr.LEGEND_COUNTS_KEY: {"trapai": {"kiekis": 0}}}, "trapai") is None
    assert fr.legend_count({}, "trapai") is None


# ── the writer (Pathon v3 W5-D, (a)): the browser sends _legendos_kiekiai in the recompute context ──────────

class _Req:
    class _Client:
        host = "127.0.0.1"
    client = _Client()


def _recompute_with_context(monkeypatch, context):
    import main
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "u1"})
    room = {"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0, "perimetras_saltinis": "plano_matmenys",
            "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas"}
    payload = main.RecomputePayload(patalpos=[room], bendras_plotas_m2=6.0, context=context)
    return main.recompute_interior(payload=payload, request=_Req())


def test_the_recompute_context_carries_the_legend_counts_to_the_row_and_back(monkeypatch):
    # the shape lib/legendCounts.js builds (frontend/src/lib/legendCounts.test.js pins the same object)
    sent = {"trapai": {"kiekis": 3, "tekstas": "Trapas; Linijinis trapas", "row_id": "p4-aa", "page": 4,
                       "eilutes": ["Trapas", "Linijinis trapas"]}}
    monkeypatch.setenv(fr.FLAG_ENV, "1")
    out = _recompute_with_context(monkeypatch, {fr.LEGEND_COUNTS_KEY: sent})
    rows = out.get("pozicijos") or []
    row = next(p for p in rows if p.get("aprasymas") == fr.DRAIN_ROW)
    assert row["kiekis"] == 3 and "Trapas; Linijinis trapas" in row["_confidence_reason"]
    # the response is spread over the project: the counts land on it
    assert out[fr.LEGEND_COUNTS_KEY] == sent
    # flag off: the counts ride along, no row
    monkeypatch.delenv(fr.FLAG_ENV, raising=False)
    off = _recompute_with_context(monkeypatch, {fr.LEGEND_COUNTS_KEY: sent})
    assert not any(p.get("aprasymas") == fr.DRAIN_ROW for p in off.get("pozicijos") or [])

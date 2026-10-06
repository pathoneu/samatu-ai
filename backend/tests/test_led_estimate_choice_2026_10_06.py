"""An LED niche length estimated from the room type is not billed until he
accepts it (2026-10-06, founder decision; re-applied from
docs/superpowers/patches/2026-10-03-round12-led-optin.patch).

The ratios behind the estimate were fitted on one contractor's sąmata, and the
engine may not learn from a sąmata. So: the read metres stay billed; the
estimate is a blank row naming the rooms and their metres, and a choice in
Nustatymai („Palikti tuščią / Priimti įvertinimą", `_overrides.led_nisu_ivertinimas`);
accepting it bills exactly what was billed before, with the 2026-10-03
disclosure. The extraction and both recompute paths must agree.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import main
from extractor import niche_inference
from extractor.niche_inference import (
    LED_ESTIMATE_CHOICE_KEY, WAITING_ROW_CONDITION, WAITING_ROW_LABEL, estimate_accepted,
)
from extractor.vision_call import (
    _build_pozicijos_from_rooms, _emit_v8_compat_fields, _recompute_per_room_via_python,
    _recompute_santrauka,
)

_LED_PREFIXES = ("Nišų formavimas GKP konstrukcijoje", "LED nišų glaistymas", "LED nišų dažymas")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _opt_in(monkeypatch):
    monkeypatch.setattr(niche_inference, "LED_ESTIMATE_OPT_IN", True)


def _parsed(read_m: float | None = 8.0) -> dict:
    """A living room whose niche was read (8,00 m) and a corridor where the
    locator read nothing and the room type gave 6,60 m."""
    living = {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
              "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.7, "elementai": []}
    if read_m:
        living["elementai"].append({"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": read_m,
                                    "_source": "niche_locator"})
    corridor = {"nr": "02", "pavadinimas": "Koridorius", "paskirtis": "koridorius",
                "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.7,
                "elementai": [{"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 6.6,
                               "_source": "statistical_inference", "_confidence": "low"}]}
    return {"patalpos": [living, corridor], "santrauka": {}}


def _extracted(parsed: dict, overrides: dict | None = None) -> dict:
    """The extraction's tail: per-room math (Step 2.9), totals, rows."""
    p = copy.deepcopy(parsed)
    if overrides:
        p["_overrides"] = dict(overrides)
    p = _recompute_per_room_via_python(p, overrides or {})
    p = _recompute_santrauka(p)
    return _build_pozicijos_from_rooms(p)


def _led_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if str(r.get("aprasymas") or "").startswith(_LED_PREFIXES)]


def _waiting(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("aprasymas") == WAITING_ROW_LABEL]


def _summary(rows: list[dict]) -> list[tuple]:
    return sorted((r["aprasymas"], r.get("kiekis"), r.get("confidence"))
                  for r in _led_rows(rows) + _waiting(rows))


# ── the default: what was read is billed, the estimate waits ────────────────

def test_the_read_metres_stay_billed_and_the_estimate_waits():
    out = _extracted(_parsed())
    rows = out["pozicijos"]
    for r in _led_rows(rows):
        assert r["kiekis"] == 8.0, r["aprasymas"]               # read metres only
        assert r["confidence"] == "zalia" and not r.get("_led_ivertinta_m"), r["aprasymas"]
    assert out["santrauka"]["nisu_metrai_total"] == 8.0
    by_nr = {r["nr"]: r for r in out["patalpos"]}
    assert by_nr["02"]["nisu_metrai"] == 0.0 and by_nr["02"]["_nisu_ivertinta_m"] == 6.6
    assert "_nisu_ivertinta_m" not in by_nr["01"]
    [blank] = _waiting(rows)
    assert blank["kiekis"] is None and blank["saltinis"] == "checklist" and blank["vnt"] == "m"
    assert blank["confidence"] == "raudona"
    assert blank["_led_ivertinta_m"] == 6.6 and blank["_only_while"] == WAITING_ROW_CONDITION
    assert "02 (įvertinimas 6,60 m)" in blank["_confidence_reason"]
    assert "6,60 m" in blank["_assumption"] and "„Nustatymai“" in blank["_assumption"]
    assert "„Priimti įvertinimą“" in blank["_assumption"]


def test_no_read_metres_leaves_only_the_blank_row():
    rows = _extracted(_parsed(read_m=None))["pozicijos"]
    assert _led_rows(rows) == []
    assert [r["_led_ivertinta_m"] for r in _waiting(rows)] == [6.6]


# ── accepting it bills exactly what was billed before ────────────────────────

def test_accepting_bills_exactly_the_old_estimate(monkeypatch):
    accepted = _extracted(_parsed(), {LED_ESTIMATE_CHOICE_KEY: True})["pozicijos"]
    monkeypatch.setattr(niche_inference, "LED_ESTIMATE_OPT_IN", False)
    before = _extracted(_parsed())["pozicijos"]                 # the 2026-10-03 behaviour
    keys = ("aprasymas", "kiekis", "confidence", "_confidence_reason", "_assumption", "_led_ivertinta_m")
    assert [{k: r.get(k) for k in keys} for r in _led_rows(accepted)] == \
        [{k: r.get(k) for k in keys} for r in _led_rows(before)]
    framing = next(r for r in accepted if r["aprasymas"] == "Nišų formavimas GKP konstrukcijoje")
    assert framing["kiekis"] == pytest.approx(14.6)
    assert framing["confidence"] != "zalia" and "02 (6,60 m)" in framing["_confidence_reason"]
    assert _waiting(accepted) == [] and _waiting(before) == []


def test_the_choice_reads_his_answer_and_nothing_else(monkeypatch):
    for yes in (True, "true", "1", 1, "priimti"):
        assert estimate_accepted({LED_ESTIMATE_CHOICE_KEY: yes}), yes
    for no in (False, "false", None, 0, ""):
        assert not estimate_accepted({LED_ESTIMATE_CHOICE_KEY: no}), no
    assert not estimate_accepted({}) and not estimate_accepted(None)
    monkeypatch.setattr(niche_inference, "LED_ESTIMATE_OPT_IN", False)
    assert estimate_accepted({}) and estimate_accepted({LED_ESTIMATE_CHOICE_KEY: False})


def test_the_projects_own_answer_counts_on_the_extraction_tail():
    """`_overrides` on the project, not only the call's rules — as the
    project-level pass reads them (prepare_rooms_for_calc)."""
    p = _parsed()
    p["_overrides"] = {LED_ESTIMATE_CHOICE_KEY: True}
    out = _build_pozicijos_from_rooms(_recompute_per_room_via_python(copy.deepcopy(p), {}))
    assert {r["kiekis"] for r in _led_rows(out["pozicijos"])} == {14.6}


# ── his scope: a room he does not do is not named ───────────────────────────

@pytest.mark.parametrize("apimtis", [{"patalpos_ne": ["02"]},
                                     {"patalpu_sritys_ne": {"02": ["apdaila"]}}])
def test_a_room_he_does_not_do_is_not_named(apimtis):
    from extractor import scope
    p = _recompute_per_room_via_python(copy.deepcopy(_parsed()), {})
    scope.mark_rooms(p["patalpos"], scope.normalize_apimtis(apimtis))
    rows = _build_pozicijos_from_rooms(p)["pozicijos"]
    assert _waiting(rows) == []
    assert {r["kiekis"] for r in _led_rows(rows)} == {8.0}


# ── the extraction and both recompute paths agree ───────────────────────────

def _stored() -> dict:
    """The project as the extraction stored it (nothing chosen yet)."""
    return _emit_v8_compat_fields(_extracted(_parsed()))


def _interior(client, stored: dict, overrides: dict) -> dict:
    r = client.post("/recompute-interior", json={
        "patalpos": copy.deepcopy(stored["patalpos"]), "rules_override": overrides})
    assert r.status_code == 200, r.text
    return r.json()


def _prielaidos(client, stored: dict, field: str, value, prior: list | None = None) -> dict:
    r = client.post("/api/recompute-quantities", json={
        "rooms": copy.deepcopy(stored["patalpos"]), "pozicijos": prior or [],
        "edits": [{"field": field, "new_value": value}], "current_assumptions": {},
        "context": {"archetipas": "standart"}})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("choice", [None, True, False])
def test_extraction_and_both_recomputes_agree(client, choice):
    stored = _stored()
    overrides = {} if choice is None else {LED_ESTIMATE_CHOICE_KEY: choice}
    fresh = _extracted(_parsed(), overrides)
    sheet = _interior(client, stored, overrides)
    prielaidos = (_prielaidos(client, stored, "glaistimo_lygis", "Q2") if choice is None
                  else _prielaidos(client, stored, LED_ESTIMATE_CHOICE_KEY, choice))
    want = _summary(fresh["pozicijos"])
    assert want, "no LED row at all — nothing compared"
    assert _summary(sheet["pozicijos"]) == want
    assert _summary(prielaidos["pozicijos"]) == want
    rooms = {r["nr"]: (r["nisu_metrai"], r.get("_nisu_ivertinta_m")) for r in fresh["patalpos"]}
    assert {r["nr"]: (r["nisu_metrai"], r.get("_nisu_ivertinta_m")) for r in sheet["patalpos"]} == rooms
    assert {r["nr"]: (r["nisu_metrai"], r.get("_nisu_ivertinta_m")) for r in prielaidos["rooms"]} == rooms
    # the blank row reaches the table the screen reads, with its reason
    blanks = [r for r in sheet["darbu_sarasas"] if r.get("aprasymas") == WAITING_ROW_LABEL]
    assert len(blanks) == (0 if choice else 1)
    if blanks:
        assert blanks[0]["kiekis"] is None and "02 (įvertinimas 6,60 m)" in blanks[0]["_confidence_reason"]


def test_accepting_takes_the_blank_row_away_instead_of_carrying_it(client):
    stored = _stored()
    assert _waiting(stored["pozicijos"])
    out = _prielaidos(client, stored, LED_ESTIMATE_CHOICE_KEY, True, prior=stored["pozicijos"])
    assert _waiting(out["pozicijos"]) == []
    assert {r["kiekis"] for r in _led_rows(out["pozicijos"])} == {14.6}
    assert any(n.get("reason") == "dropped_by_condition" and n.get("aprasymas") == WAITING_ROW_LABEL
               for n in out["_merge_notes"])
    assert not [n for n in out["_merge_notes"] if n.get("reason") == "orphan_carried"]
    # …and „Palikti tuščią" brings it back with the read metres only
    back = _prielaidos(client, {**stored, "patalpos": out["rooms"]}, LED_ESTIMATE_CHOICE_KEY, False,
                       prior=out["pozicijos"])
    assert [r["_led_ivertinta_m"] for r in _waiting(back["pozicijos"])] == [6.6]
    assert {r["kiekis"] for r in _led_rows(back["pozicijos"])} == {8.0}

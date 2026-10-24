"""Phase 2 commit 3 — scope and granularity in the `lt_rangovas` profile.

Built on the existing scope object (`_apimtis`, extractor/scope.py — rooms, families, ceilings, walls with
or without openings, Rotband, corner bead) and the reveals choice (`angokrasciai_apimtis`): the profile adds
DEFAULTS for them (`scope_defaults`, `reveals_scope`) that a project's own choice overrides, and the row
granularity (`paint_rows`, `tile_rows`) applied at row generation."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SAMATU_AUTH_DISABLED", "1")

from extractor import scope as _scope  # noqa: E402
from extractor.ledger import replay  # noqa: E402
from extractor.universal_rules import settle_reveals_scope  # noqa: E402
from main import app  # noqa: E402
from rules.conventions import LT_RANGOVAS, profile_overrides  # noqa: E402

client = TestClient(app)


def _door(n=1):
    return {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": n}


def _window(n=1):
    return {"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": n}


def _rooms():
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1, "elementai": [_door(1), _window(2)]},
        {"nr": "02", "pavadinimas": "Virtuvė", "paskirtis": "virtuve", "plotas_m2": 14.0,
         "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1, "elementai": [_door(1), _window(1)]},
        {"nr": "03", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1, "elementai": [_door(1)]},
    ]


def _recompute(rules_override=None):
    res = client.post("/recompute-interior", json={"patalpos": _rooms(), "rules_override": rules_override or {}})
    assert res.status_code == 200, res.text
    return res.json()


def _poz(out, prefix):
    return [r for r in out.get("pozicijos") or [] if str(r.get("aprasymas") or "").startswith(prefix)]


def _led(out, prefix):
    return [r for r in out.get("darbu_sarasas") or [] if str(r.get("aprasymas") or "").startswith(prefix)][0]


def _qty(out, prefix):
    return round(sum(float(r.get("kiekis") or 0) for r in _poz(out, prefix)), 2)


# ── reveals_scope ─────────────────────────────────────────────────────────────

def test_reveals_scope_from_the_profile_and_his_choice_wins():
    rooms = [dict(r) for r in _rooms()]
    got = settle_reveals_scope(rooms, {"profilis": {"reveals_scope": {"langai": False}}})
    assert got["value"]["langai"] is False and got["value"]["lauko_durys"] is True
    got = settle_reveals_scope(rooms, {"profilis": {"reveals_scope": {"langai": False}},
                                       "angokrasciai_apimtis": {"langai": True}})
    assert got["value"]["langai"] is True and got["source"] == "jusu"
    assert settle_reveals_scope(rooms, {})["value"] == {"langai": True, "lauko_durys": True, "praejimai": True,
                                                         "vidaus_durys": False}


def test_reveals_scope_without_windows_moves_the_reveals_row():
    base = _qty(_recompute(), "Angokraščių apdirbimas GKP")
    none = _qty(_recompute({"profilis": {"reveals_scope": {"langai": False}}}), "Angokraščių apdirbimas GKP")
    assert base == pytest.approx(3 * (1.2 + 2 * 1.5))
    assert none == 0.0


# ── scope_defaults ────────────────────────────────────────────────────────────

def test_scope_defaults_are_a_default_his_own_scope_wins():
    prof = {"profilis": {"scope_defaults": {"darbai_ne": ["elektra"], "lubos": "ne_musu"}}}
    assert profile_overrides(prof)["scope_defaults"] == {"darbai_ne": ["elektra"], "lubos": "ne_musu"}
    eff = _scope.with_profile_defaults({"lubos": "dazomos"}, prof)
    assert eff == {"darbai_ne": ["elektra"], "lubos": "dazomos"}
    assert _scope.with_profile_defaults(None, {}) is None
    assert _scope.with_profile_defaults({"kampai": "tik_isoriniai"}, {}) == {"kampai": "tik_isoriniai"}


def test_scope_defaults_reach_the_rows():
    base = _recompute()
    out = _recompute({"profilis": {"scope_defaults": {"lubos": "ne_musu", "kampai": "tik_isoriniai"}}})
    assert _qty(base, "Lubų glaistymas/dažymas") > 0
    assert _qty(out, "Lubų glaistymas/dažymas") == 0
    assert _qty(out, "Dažymo kampų montavimas") < _qty(base, "Dažymo kampų montavimas")
    mine = _recompute({"apimtis": {"lubos": "dazomos"},
                       "profilis": {"scope_defaults": {"lubos": "ne_musu"}}})
    assert _qty(mine, "Lubų glaistymas/dažymas") == pytest.approx(_qty(base, "Lubų glaistymas/dažymas"))


# ── granularity ───────────────────────────────────────────────────────────────

def test_granularity_defaults_split():
    assert LT_RANGOVAS["paint_rows"].default == "split" and LT_RANGOVAS["tile_rows"].default == "split"


def test_paint_and_tile_rows_merged_keep_the_totals_and_the_ledger():
    base = _recompute()
    merged = _recompute({"profilis": {"paint_rows": "merged", "tile_rows": "merged"}})
    paint = _qty(base, "Sienų glaistymas/dažymas") + _qty(base, "Lubų glaistymas/dažymas")
    assert _qty(merged, "Sienų, lubų glaistymas/dažymas") == pytest.approx(paint, abs=0.02)
    assert not _poz(merged, "Lubų glaistymas/dažymas") and not _poz(merged, "Sienų glaistymas/dažymas")
    tiles = sum(float(r["kiekis"]) for r in base["pozicijos"]
                if str(r.get("aprasymas", "")).endswith("plytelių klijavimas") and r.get("vnt") == "m2")
    assert _qty(merged, "Sienų ir grindų plytelių klijavimas") == pytest.approx(tiles, abs=0.02)
    for prefix in ("Sienų, lubų glaistymas/dažymas", "Sienų ir grindų plytelių klijavimas"):
        row = _led(merged, prefix)
        assert replay(row.get("contributions"), row.get("roll_up")) == pytest.approx(float(row["kiekis"]), abs=0.01)

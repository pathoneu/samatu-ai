"""Medžiagos — one global section at the END (2026-09-02, contractor ask F2).

Founder decision: work sections carry LABOUR only; every auto-computed material
moves to a single "Medžiagos" section at the foot of the sąmata, and each
material row says which work it belongs to. Nothing is recomputed — the
quantities are the ones the work rows were already carrying in
`medziagos_kiekis` / `_medziagos`, which no export ever showed and no user could
price.

The invariants worth pinning are about MONEY and TRUST, not shape:
  · a material label is a price key, so no two may collide;
  · a material may not exist without a work row to belong to;
  · a material the engine cannot quantify stays OUT (a 0-kiekis line in a
    shopping list reads as "nothing needed", which is a lie);
  · rebuilding an old project may not delete or move a single priced row.
"""
from __future__ import annotations

import copy

import pytest

from api.recompute_quantities import _merge_user_edits
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import (
    SK_MEDZIAGOS,
    _MEDZIAGOS_REASON,
    _build_pozicijos_from_rooms,
    _calc_dazai_liters,
    _calc_glaistas_kg,
    _calc_hidroizoliacija_m2,
    _emit_v8_compat_fields,
)


def _room(nr="101", **kw):
    r = {"nr": nr, "pavadinimas": f"Kambarys {nr}", "paskirtis": "gyvenamoji",
         "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
         "elementai": [{"tipas": "duris", "kiekis": 1,
                        "plotis_mm": 900, "aukstis_mm": 2100}]}
    r.update(kw)
    r.update(calc_room_quantities(r))
    # The per-room material fields `_recompute_per_room_via_python` §4 adds on
    # top of calc_room_quantities. Without them every paint/waterproofing
    # material is 0 and the assertions below would pass vacuously.
    dazymo = float(r.get("dazymo_plotas_m2") or 0)
    r["glaistas_kg"] = _calc_glaistas_kg(dazymo)
    r["dazai_l"] = _calc_dazai_liters(dazymo, paint_class=2)
    r["gruntas_l"] = round(dazymo / 7.0, 2) if dazymo > 0 else 0.0
    r["hidroizoliacija_m2"] = _calc_hidroizoliacija_m2(
        r, float(r.get("perimetras_m") or 0))
    return r


def _built(rooms=None, overrides=None):
    parsed = {"patalpos": rooms or [_room("101"),
                                    _room("102", paskirtis="vonia",
                                          plotas_m2=6.0, perimetras_m=10.0)],
              "santrauka": {}}
    if overrides is not None:
        parsed["_overrides"] = overrides
    return _build_pozicijos_from_rooms(parsed)


def _mats(out):
    return [p for p in out["pozicijos"] if p["skyrius"] == SK_MEDZIAGOS]


def _works(out):
    return [p for p in out["pozicijos"] if p["skyrius"] != SK_MEDZIAGOS]


# ── the section exists, and it is the last thing in the sąmata ──────────────

def test_materials_are_their_own_section_at_the_end():
    out = _built()
    mats = _mats(out)
    assert mats, "no materials extracted at all"
    assert out["pozicijos"][-len(mats):] == mats, \
        "the shopping list must be the LAST thing the contractor reads"


def test_section_maps_to_the_materials_enum():
    out = _built()
    out["santrauka"] = {}
    rows = _emit_v8_compat_fields(out)["darbu_sarasas"]
    mat_rows = [r for r in rows if r["skyrius"] == SK_MEDZIAGOS]
    assert mat_rows
    assert {r["skyrius_enum"] for r in mat_rows} == {"materials"}
    # the section survives the compat layer as the last group
    assert [r["skyrius"] for r in rows][-len(mat_rows):] == [SK_MEDZIAGOS] * len(mat_rows)


# ── the enumerated set actually moved ───────────────────────────────────────

def test_the_materials_the_builder_computes_all_land_in_the_section():
    """The families the engine quantifies today. A material that stops being
    emitted is a silently lost line on the contractor's shopping list."""
    out = _built()
    labels = " | ".join(m["aprasymas"] for m in _mats(out))
    for needle in ("Rotband", "Glaistas sienoms", "Gruntas sienoms",
                   "Dažai sienoms", "Glaistas luboms", "Gruntas luboms",
                   "Dažai luboms", "PVC kampuotės", "Grindjuostės",
                   "GKP lapas luboms", "CD 60×27", "UW 28×27",
                   "Savisriegiai GKP", "plytelių klijai", "plytelės (m²",
                   "fugavimo masė", "Hidroizoliacijos medžiaga",
                   "Savaime išsilyginantis", "Grindų danga", "Slenksnis",
                   "PE plėvelė"):
        assert needle in labels, f"{needle!r} missing from Medžiagos: {labels}"


def test_work_rows_no_longer_embed_their_material():
    out = _built()
    leftover = [p["aprasymas"] for p in _works(out)
                if p.get("medziagos_aprasymas") or p.get("medziagos_kiekis")
                or p.get("medziagos_vnt") or p.get("_medziagos")]
    assert not leftover, f"materials still riding on work rows: {leftover}"


def test_every_material_has_a_quantity_a_unit_and_a_parent():
    out = _built()
    work_labels = {p["aprasymas"] for p in _works(out)}
    for m in _mats(out):
        assert float(m["kiekis"]) > 0, m          # no 0-qty placeholder rows
        assert m["vnt"] in {"kg", "l", "m", "m2", "m3", "vnt", "d.d"}, m
        assert m["susijes_darbas"] in work_labels, \
            f"{m['aprasymas']!r} belongs to a work row that does not exist"


def test_material_labels_are_unique_because_a_label_is_a_price_key():
    """Two materials sharing a label share a price on every rebuild — and a
    user who priced them apart would see one of the two carried back as an
    orphan. The colliding families are the ones with several instances per
    project: paint (walls + ceilings) and tiles (up to six locations)."""
    out = _built(rooms=[_room("101"),
                        _room("102", paskirtis="vonia", plotas_m2=6.0,
                              perimetras_m=10.0),
                        _room("103", paskirtis="virtuve", plotas_m2=12.0,
                              perimetras_m=14.0)])
    labels = [m["aprasymas"] for m in _mats(out)]
    assert len(labels) == len(set(labels)), \
        f"duplicate material labels: {[l for l in labels if labels.count(l) > 1]}"


def test_counts_stay_whole_numbers():
    """4 649 savisriegiai, not 4 649.0 — the row is read by a human."""
    out = _built()
    for m in _mats(out):
        if m["vnt"] == "vnt":
            assert isinstance(m["kiekis"], int), m


# ── confidence + reasons ────────────────────────────────────────────────────

def test_material_inherits_its_work_row_confidence():
    """A bag of glaistas is exactly as trustworthy as the area it was computed
    from — never greener, and never separately scored on its own label."""
    out = _built()
    by_label = {p["aprasymas"]: p for p in _works(out)}
    tiers = set()
    for m in _mats(out):
        parent = by_label[m["susijes_darbas"]]
        assert m["confidence"] == (parent.get("confidence") or "zalia"), m
        tiers.add(m["confidence"])
    # the fixture must actually exercise a demoted parent, or this proves nothing
    assert "geltona" in tiers, tiers


def test_material_reason_guides_and_never_confesses():
    """Same net as test_confidence_reasons_are_for_the_user, applied to the
    strings only the Medžiagos rows can produce."""
    from tests.test_confidence_reasons_are_for_the_user import BANNED
    out = _built()
    assert not BANNED.search(_MEDZIAGOS_REASON), _MEDZIAGOS_REASON
    for m in _mats(out):
        reason = m.get("_confidence_reason") or ""
        assert reason, m                         # never an unexplained row
        hit = BANNED.search(reason)
        assert not hit, f"banned token {hit.group(0)!r} on {m['aprasymas']!r}"


# ── old projects ────────────────────────────────────────────────────────────

def _priced_old_shape(out):
    """The list as a pre-2026-09-02 project carries it: materials embedded on
    the work rows, no Medžiagos section, and every work row priced."""
    prior = []
    for p in _works(copy.deepcopy(out)):
        prior.append({**p, "kaina": 12.0,
                      "suma": round(float(p.get("kiekis") or 0) * 12.0, 2),
                      "medziagos_aprasymas": "Medžiaga",
                      "medziagos_kiekis": 1.0, "medziagos_vnt": "vnt"})
    return prior


def test_rebuilding_an_old_project_deletes_no_priced_row_and_moves_no_price():
    out = _built()
    prior = _priced_old_shape(out)
    merged = _merge_user_edits([dict(p) for p in out["pozicijos"]],
                               [dict(p) for p in prior])
    by_label = {}
    for p in merged:
        by_label.setdefault(p["aprasymas"], []).append(p)
    for old in prior:
        rows = by_label.get(old["aprasymas"])
        assert rows, f"priced row deleted by the rebuild: {old['aprasymas']}"
        assert any(r.get("kaina") == 12.0 for r in rows), \
            f"price lost on {old['aprasymas']}"
    # …and no price landed on a row that never had one: the new material rows
    # come back unpriced, which is visible and correct — the contractor prices
    # labour and materials separately, which is why he asked for the split.
    for m in merged:
        if m["skyrius"] == SK_MEDZIAGOS:
            assert m.get("kaina") in (None, 0), m


def test_a_combined_work_plus_material_price_is_never_split():
    """An old row's price bought labour AND material together. We cannot know
    how it divided, so it stays whole on the work row — guessing would silently
    reprice the sąmata."""
    out = _built()
    prior = _priced_old_shape(out)
    merged = _merge_user_edits([dict(p) for p in out["pozicijos"]],
                               [dict(p) for p in prior])
    total_priced = sum(1 for p in merged if p.get("kaina"))
    assert total_priced == len(prior), \
        "the rebuild invented or dropped priced rows"


def test_old_blobs_keep_rendering_their_embedded_material():
    """The fields are no longer WRITTEN, but they stay READABLE so a project
    saved before today does not lose information on load."""
    legacy = {"pozicijos": [{"skyrius": "Grindys", "aprasymas": "Senas darbas",
                             "vnt": "m2", "kiekis": 10.0,
                             "medziagos_aprasymas": "Sena medžiaga",
                             "medziagos_kiekis": 11.0, "medziagos_vnt": "m2"}],
              "santrauka": {}}
    row = _emit_v8_compat_fields(legacy)["darbu_sarasas"][0]
    assert row["medziagos_aprasymas"] == "Sena medžiaga"
    assert row["medziagos_kiekis"] == 11.0


# ── stretch ceilings still take their material with them ────────────────────

def test_a_stretch_ceiling_takes_its_material_out_of_the_shopping_list():
    rooms = [_room("101"), _room("102")]
    base = _built([dict(r) for r in rooms])
    out = _built([dict(r) for r in rooms],
                 {"stretch_ceiling_override": {"101": 1}})

    def _l(built, label):
        return next((m["kiekis"] for m in _mats(built)
                     if m["aprasymas"] == label), 0.0)

    assert _l(out, "Gruntas sienoms") == pytest.approx(
        _l(base, "Gruntas sienoms"), abs=0.05), "wall primer must not grow"
    assert _l(out, "Gruntas luboms") == pytest.approx(
        _l(base, "Gruntas luboms") / 2, abs=0.05)

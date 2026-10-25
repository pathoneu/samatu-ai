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
         "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
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
                                          plotas_m2=6.0, perimetras_m=10.0, perimetras_saltinis="plano_matmenys")],
              "santrauka": {}}
    if overrides is not None:
        parsed["_overrides"] = overrides
    return _build_pozicijos_from_rooms(parsed)


def _mats(out):
    # v4 3b: the goods of a blank work row stay as blank rows (place, id, price) — the norms below are about
    # the goods that carry a quantity
    return [p for p in out["pozicijos"] if p["skyrius"] == SK_MEDZIAGOS and p.get("kiekis") is not None]


def _works(out):
    return [p for p in out["pozicijos"] if p["skyrius"] != SK_MEDZIAGOS]


# ── the section exists, and it is the last thing in the sąmata ──────────────

def test_materials_are_their_own_section_at_the_end():
    out = _built()
    mats = [p for p in out["pozicijos"] if p["skyrius"] == SK_MEDZIAGOS]   # blank goods included
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
    emitted is a silently lost line on the contractor's shopping list.

    2026-09-02 (second audit pass): the rows that ARE the purchase — tiles, GKP
    boards, profiles, screws, hatches, underlay, thresholds — are MOVED here
    under their own labels instead of being cloned, so the needles are the work
    labels now. Their old clone names are asserted GONE below."""
    out = _built()
    labels = " | ".join(m["aprasymas"] for m in _mats(out))
    # v4 3b: Rotband (until he chooses a share), the GKP ceiling goods (until the drawing marks the ceilings)
    # and the thresholds (a count the drawing does not give) are blank work rows — no goods are bought for them
    for needle in ("Glaistas sienoms", "Gruntas sienoms",
                   "Dažai sienoms", "Glaistas luboms", "Gruntas luboms",
                   "Dažai luboms", "PVC kampuotės", "Grindjuostės",
                   "plytelių klijai", "Vonios sienų plytelės",
                   "fugavimo masė", "Hidroizoliacinė medžiaga",
                   "Savaime išsilyginantis", "Grindų danga",
                   "Grindų dangos pamušalas"):
        assert needle in labels, f"{needle!r} missing from Medžiagos: {labels}"


def test_a_purchase_is_never_billed_on_two_rows():
    """THE P0 (2026-09-02, second audit pass).

    A family of "work" rows in this builder ARE the product: their kiekis and
    vnt are the material's. Each also carried a `medziagos_*` copy of itself, so
    one purchase reached the sąmata as TWO priceable rows — and the kainynas
    auto-fill, which scores substring containment at 0.92, filled both from one
    price line ("Vonios sienų plytelės" AND "Vonios sienų plytelės (m² + 8%
    atliekų)"): 137 m² of tiles quoted as 275 m² to a client.

    The invariant, stated so it survives a future emit site: a material must not
    repeat its parent's quantity AND unit AND its opening words. All three
    together are the signature of a row cloning itself — and of a price list
    entry short enough to be contained in both labels, which is how one kainynas
    line filled two rows. A genuine labour+material pair fails the third test:
    "Angokraščių apdirbimas GKP" and "GKP juostelės + savisriegiai" are the same
    metres of the same job, but no single price line matches both, and the
    contractor really does pay for the fitting and for the strips."""
    def _head(label):
        return " ".join((label or "").lower().split()[:2])

    for rooms in (None,
                  [_room("201", paskirtis="vonia", plotas_m2=8.0, perimetras_m=12.0, perimetras_saltinis="plano_matmenys"),
                   _room("202", paskirtis="virtuve", plotas_m2=14.0, perimetras_m=15.0, perimetras_saltinis="plano_matmenys"),
                   _room("203", lubu_aukstis_m=3.4, lubu_aukstis_saltinis="plano_uzrasas")]):
        out = _built(rooms=rooms)
        works = {p["aprasymas"]: p for p in _works(out)}
        for m in _mats(out):
            parent = works.get(m.get("susijes_darbas") or "")
            if parent is None:
                continue
            same = (round(float(m["kiekis"]), 2)
                    == round(float(parent.get("kiekis") or 0), 2)
                    and str(m["vnt"]) == str(parent.get("vnt"))
                    and _head(m["aprasymas"]) == _head(parent["aprasymas"]))
            assert not same, (
                f"{m['aprasymas']!r} ({m['kiekis']} {m['vnt']}) is the same "
                f"purchase as {parent['aprasymas']!r} — one kainynas line "
                f"prices both and the client is billed twice")


def test_the_old_self_clone_labels_are_gone():
    """Belt and braces for the P0: the clone names must not come back, in the
    Medžiagos section or anywhere else. Each of these was a second row for a
    purchase the sąmata already carried."""
    out = _built(rooms=[_room("101"),
                        _room("102", paskirtis="vonia", plotas_m2=6.0,
                              perimetras_m=10.0, perimetras_saltinis="plano_matmenys"),
                        _room("103", lubu_aukstis_m=3.4, lubu_aukstis_saltinis="plano_uzrasas")])
    labels = " | ".join(p["aprasymas"] for p in out["pozicijos"])
    for gone in ("GKP lapas luboms", "GKP lapas sienoms", "CD 60×27",
                 "UW 28×27", "plytelės (m² + 8% atliekų)", "Pamušalo membrana",
                 "Slenksnis (alu / mediena)", "Reviziniai dureliai 200×200",
                 "Pastoliai (mobilūs)", "Konteineris + transportas",
                 "PE plėvelė + dažymo juostos"):
        assert gone not in labels, f"{gone!r} is back — one purchase, two rows"


def test_a_moved_purchase_keeps_its_label_so_an_old_price_still_lands():
    """The label is the price key every rebuild matches on. A row that moves
    into the shopping list must keep the name it was priced under, or a legacy
    priced project loses the money on it."""
    out = _built(rooms=[_room("101"),
                        _room("102", paskirtis="vonia", plotas_m2=6.0,
                              perimetras_m=10.0, perimetras_saltinis="plano_matmenys")])
    mats = {m["aprasymas"]: m for m in _mats(out)}
    tiles = mats.get("Vonios sienų plytelės")
    assert tiles is not None, sorted(mats)
    prior = [{"aprasymas": "Vonios sienų plytelės", "kiekis": tiles["kiekis"],
              "vnt": "m2", "kaina": 24.0, "skyrius": "Plytelių klijavimas"}]
    merged = _merge_user_edits([dict(p) for p in out["pozicijos"]], prior)
    row = next(r for r in merged if r["aprasymas"] == "Vonios sienų plytelės")
    assert row["kaina"] == 24.0
    assert row["skyrius"] == SK_MEDZIAGOS
    assert not row.get("_orphaned_after_rebuild"), \
        "the moved row must be MATCHED, not carried as an orphan duplicate"


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
                              perimetras_m=10.0, perimetras_saltinis="plano_matmenys"),
                        _room("103", paskirtis="virtuve", plotas_m2=12.0,
                              perimetras_m=14.0, perimetras_saltinis="plano_matmenys")])
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
    from — never greener, and never separately scored on its own label.

    Applies to CLONED materials, whose quantity is a norm applied to the
    parent's. A row that was MOVED (`_is_material_line`) carries its own
    quantity and was scored on it, so it keeps its own tier."""
    out = _built()
    by_label = {p["aprasymas"]: p for p in _works(out)}
    tiers = set()
    for m in _mats(out):
        if m.get("_is_material_line"):
            continue
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

"""Santechnika — potinkinių maišytuvų POROS (2026-07-29).

A concealed (potinkinis) mixer is two jobs at two different times: the in-wall
body during rough-in, the visible trim after tiling. LT contractors bill the
pair; we billed one bundled line and under-quoted the installer by a visit.
Measured on Objektas A: 5 vnt emitted against the contractor's 22.

Tests assert BEHAVIOUR — pair-ness, count identity between the halves, which
items stay single, and that a guessed concealment is DISCLOSED — not magic
numbers, so they survive future count-driver changes.
"""
import pytest

from extractor.vision_call import (
    _build_pozicijos_from_rooms,
    _SAN_MIXER_LINES,
    _SAN_ASSUMPTION_FIELD,
)
from extractor.universal_rules import calc_room_quantities


def _room(**kw):
    r = {"paskirtis": "san", "plotas_m2": 6.0, "perimetras_m": 10.0,
         "lubu_aukstis_m": 2.7, "elementai": []}
    r.update(kw)
    r.update(calc_room_quantities(r))
    return r


def _build(symbols=None, overrides=None, rooms=None, **extra):
    parsed = {"patalpos": rooms if rooms is not None else [_room(nr="107"),
                                                           _room(nr="111")],
              "santrauka": {},
              "detected_symbols_summary": symbols or {}}
    if overrides is not None:
        parsed["_overrides"] = overrides
    parsed.update(extra)
    return _build_pozicijos_from_rooms(parsed)


def _san(out):
    return [p for p in out["pozicijos"] if p["skyrius"] == "Santechnikos darbai"]


def _qty(out, label_fragment):
    """Quantities of every sanitary line containing `label_fragment`."""
    return [p["kiekis"] for p in _san(out)
            if label_fragment.lower() in p["aprasymas"].lower()]


# ── the reference shape: objektas_a/objektas_b as the contractor bills it ────────
def test_concealed_project_emits_pairs_singles_and_matching_counts():
    """3 praustuvė mixers + 2 shower mixers + 3 bidė + 2 klozetai."""
    out = _build(symbols={"praustuves": 3, "bide": 3})

    for family, (potinkine, virstinkine, _single) in _SAN_MIXER_LINES.items():
        got_p = _qty(out, potinkine)
        got_v = _qty(out, virstinkine)
        if family == "vonia":
            continue  # no bathtub symbol in this project → correctly absent
        assert len(got_p) == 1, f"{family}: expected one potinkinė line, got {got_p}"
        assert len(got_v) == 1, f"{family}: expected one virštinkinė line, got {got_v}"
        # THE invariant: one count source, two lines. 3+3, never 3+5.
        assert got_p == got_v, f"{family}: pair halves disagree {got_p} vs {got_v}"

    assert _qty(out, "praustuvės maišytuvo potinkinės") == [3]
    assert _qty(out, "praustuvės maišytuvo virštinkinės") == [3]
    assert _qty(out, "dušo maišytuvo potinkinės") == [2]
    assert _qty(out, "dušo maišytuvo virštinkinės") == [2]
    assert _qty(out, "bidė dušiuko potinkinės") == [3]
    assert _qty(out, "bidė dušiuko virštinkinės") == [3]

    # Genuinely single-job work stays ONE line at its own count.
    assert _qty(out, "klozeto montavimas") == [2]
    assert _qty(out, "wc rėmo montavimas") == [2]
    assert _qty(out, "praustuvės montavimas") == [3]      # the basin, not its mixer
    assert _qty(out, "gyvatuko montavimas") == [2]
    assert _qty(out, "skalbimo mašinos montavimas") == [1]
    assert _qty(out, "linijinio latako") == [2]


def test_bathtub_mixer_pair_follows_the_readers_tub_only_count():
    """`vonios` in the symbol summary is "Vonios + dušo padėklai" — tubs AND
    shower trays in one integer. Only the sanitary reader's tub-only count
    (`vonios_kubilai`) may bill a BATHTUB mixer."""
    out = _build(symbols={"praustuves": 3, "vonios": 3, "vonios_kubilai": 1})
    assert _qty(out, "vonios maišytuvo potinkinės") == [1]
    assert _qty(out, "vonios maišytuvo virštinkinės") == [1]
    # No bathtub read → no bathtub mixer invented.
    out0 = _build(symbols={"praustuves": 3})
    assert _qty(out0, "vonios maišytuvo") == []


def test_shower_tray_read_as_a_tub_does_not_bill_a_bathtub_mixer():
    """objektas_d: the contractor bills only "Dušo maišytuvo sistemos montavimas
    (ne potinkinės)" — no bathtub anywhere — yet the conflated symbol reads 1.
    Reader says 0 tubs → the bathtub line must not appear at all."""
    out = _build(symbols={"praustuves": 1, "vonios": 1, "vonios_kubilai": 0,
                          "dusai": 1})
    assert _qty(out, "vonios maišytuvo") == []


def test_conflated_tub_symbol_without_reader_evidence_is_a_todo_not_a_guess():
    """No reader ran (2 of 6 registry PDFs have no plumbing sheet), so the 1
    could be a tub or a tray. Billing the wrong fixture is worse than billing
    neither — ask, visibly."""
    out = _build(symbols={"praustuves": 1, "vonios": 1})
    vonia = [p for p in _san(out) if "vonios maišytuvo" in p["aprasymas"].lower()]
    assert len(vonia) == 2                                   # still the pair
    assert all(p["kiekis"] is None for p in vonia), vonia
    assert all(p["saltinis"] == "checklist" for p in vonia), vonia
    assert all("suveskite kiekį" in p["aprasymas"] for p in vonia), vonia


def test_no_single_line_survives_alongside_its_pair():
    """The bundled legacy line must not co-exist with the split — that would
    bill the same work twice inside one sąmata."""
    out = _build(symbols={"praustuves": 3})
    labels = [p["aprasymas"] for p in _san(out)]
    assert "Praustuvės maišytuvo montavimas" not in labels, labels
    assert "Dušo maišytuvo sistemos montavimas" not in labels, labels


# ── surface-mounted (objektas_d: "Dušo maišytuvo sistemos montavimas ( ne
#    potinkinės)") — one job, one line, and the legacy label preserved ────────
def test_surface_mounted_project_emits_no_potinkine_lines():
    out = _build(symbols={"praustuves": 2, "vonios": 1},
                 overrides={"santechnika_potinkinis": False})
    labels = [p["aprasymas"] for p in _san(out)]
    assert not [l for l in labels if "potinkin" in l.lower()], labels
    # …and the pre-split labels come back verbatim, so an already-priced
    # project keeps matching them on rebuild.
    assert "Praustuvės maišytuvo montavimas" in labels
    assert "Dušo maišytuvo sistemos montavimas" in labels
    assert _qty(out, "praustuvės maišytuvo montavimas") == [2]


def test_per_family_override_is_honoured_independently():
    out = _build(symbols={"praustuves": 2},
                 overrides={"santechnika_potinkinis": {"dusas": False}})
    labels = [p["aprasymas"] for p in _san(out)]
    assert "Dušo maišytuvo sistemos montavimas" in labels          # forced surface
    assert "Potinkinio praustuvės maišytuvo potinkinės dalies montavimas" in labels


# ── disclosure ───────────────────────────────────────────────────────────────
def test_guessed_concealment_is_disclosed_as_an_assumption():
    out = _build(symbols={"praustuves": 3})
    notes = out["_sanitary_assumptions"]
    assert notes, "a guessed concealment must be disclosed"
    assert any("POTINKINIU" in n for n in notes), notes
    assert any("santechnika_potinkinis" in n for n in notes), notes
    # …and it reaches the UI channel, tagged so a rebuild can retract it.
    tagged = [w for w in out.get("warnings") or []
              if w.get("field") == _SAN_ASSUMPTION_FIELD]
    assert len(tagged) == len(notes)
    # Every split line carries the reasoning inline too.
    split = [p for p in _san(out) if "potinkinės dalies" in p["aprasymas"].lower()]
    assert split and all(p.get("_assumption") for p in split)


def test_explicit_answer_is_not_reported_as_an_assumption():
    out = _build(symbols={"praustuves": 2},
                 overrides={"santechnika_potinkinis": True})
    assert out["_sanitary_assumptions"] == []
    # An evidence read (the hook a future reader fills) is likewise not a guess.
    out2 = _build(symbols={"praustuves": 2},
                  _sanitary_evidence={"praustuve": True, "dusas": True,
                                      "vonia": True, "bide": True})
    assert out2["_sanitary_assumptions"] == []


def test_assumption_notes_do_not_accumulate_across_rebuilds():
    parsed = {"patalpos": [_room(nr="107")], "santrauka": {},
              "detected_symbols_summary": {"praustuves": 1}}
    first = _build_pozicijos_from_rooms(parsed)
    n1 = len([w for w in first["warnings"] if w.get("field") == _SAN_ASSUMPTION_FIELD])
    second = _build_pozicijos_from_rooms(first)
    n2 = len([w for w in second["warnings"] if w.get("field") == _SAN_ASSUMPTION_FIELD])
    assert n1 == n2 > 0, (n1, n2)
    # Turning the split off retracts the note that justified it.
    second["_overrides"] = {"santechnika_potinkinis": False}
    third = _build_pozicijos_from_rooms(second)
    assert not [w for w in third["warnings"]
                if w.get("field") == _SAN_ASSUMPTION_FIELD]


# ── bidė: a read count, not a TODO (2026-07-29) ──────────────────────────────
def test_read_bide_count_becomes_a_real_pair_not_a_checklist():
    out = _build(symbols={"praustuves": 3, "bide": 3})
    bide = [p for p in _san(out) if "bidė dušiuko" in p["aprasymas"].lower()]
    assert len(bide) == 2
    assert [p["kiekis"] for p in bide] == [3, 3]          # pair halves agree
    assert all(p["saltinis"] == "simboliai_brezinyje" for p in bide), bide
    assert not any("suveskite kiekį" in p["aprasymas"] for p in bide), bide


def test_bide_count_is_never_derived_from_the_klozetas_count():
    """objektas_a is billed 3 bidė against 2 klozetai — a 1-per-WC default would be
    wrong by construction. No bidė read ⇒ no bidė number, only the TODO."""
    out = _build(symbols={"praustuves": 3, "klozetai": 2})
    bide = [p for p in _san(out) if "bidė dušiuko" in p["aprasymas"].lower()]
    assert all(p["kiekis"] is None for p in bide), bide


def test_read_bide_line_is_never_a_confident_green():
    """LT drawings rarely write "bidė" — the count is inferred from position +
    altitude, so the line must carry a verify-me flag."""
    from extractor.confidence import apply_confidence, ZALIA
    out = apply_confidence(_build(symbols={"praustuves": 3, "bide": 3}))
    bide = [p for p in _san(out) if "bidė dušiuko" in p["aprasymas"].lower()]
    assert bide and all(p["confidence"] != ZALIA for p in bide), bide
    assert all(p.get("_confidence_reason") for p in bide), bide


# ── unread categories stay VISIBLE, never silently zero ──────────────────────
def test_bide_without_a_count_is_a_checklist_todo_not_a_silent_zero():
    out = _build(symbols={"praustuves": 2})
    bide = [p for p in _san(out) if "bidė dušiuko" in p["aprasymas"].lower()]
    assert len(bide) == 2, bide                       # still the pair
    assert all(p["kiekis"] is None for p in bide), bide
    assert all(p["saltinis"] == "checklist" for p in bide), bide
    # emitted as "low"; the builder's confidence pass normalises it to the red
    # tier — assert the tier, not whichever spelling survives.
    from extractor.confidence import RAUDONA
    assert all(p["confidence"] in ("low", RAUDONA) for p in bide), bide
    assert all("suveskite kiekį" in p["aprasymas"] for p in bide), bide


# ── praustuvė ≠ plautuvė: one sink, one line (2026-07-29) ───────────────────
# The sanitary reader was asked for "praustuvės/kriauklės" — and a kriauklė is
# also a KITCHEN sink, so a live objektas_a probe put the virtuvės and skalbyklos
# plautuvės inside praustuves_count. "Plautuvės montavimas" is billed off its
# own count, so on any project with a room classified `virtuve` that one sink
# was billed twice. The contractor bills them as separate lines (objektas_d nr 32
# "Plautuvės montavimas" alongside nr 33 "Praustuvės montavimas").

def _kitchen(nr="102"):
    return _room(nr=nr, paskirtis="virtuve")


def test_kitchen_sink_is_billed_once_not_once_per_bucket():
    """2 bathroom basins + 1 kitchen sink = 3 sinks → 2 praustuvės, 1 plautuvė.
    The kitchen sink must appear in exactly one of the two counts."""
    out = _build(symbols={"praustuves": 2, "plautuves": 1},
                 rooms=[_room(nr="107"), _room(nr="111"), _kitchen()])
    assert _qty(out, "praustuvės montavimas") == [2]
    assert _qty(out, "plautuvės montavimas") == [1]
    # …and their mixers follow the same split — no fixture pays twice.
    assert _qty(out, "praustuvės maišytuvo potinkinės") == [2]
    assert _qty(out, "virtuvės maišytuvo montavimas") == [1]


def test_praustuve_lines_never_consume_the_plautuve_count():
    """THE regression guard. Whatever the kitchen/laundry count is, it may not
    move the praustuvė lines by one — that leak, in reverse, was the bug."""
    rooms = [_room(nr="107"), _room(nr="111"), _kitchen()]
    base = _build(symbols={"praustuves": 2}, rooms=rooms)
    plus = _build(symbols={"praustuves": 2, "plautuves": 4}, rooms=rooms)
    assert _qty(plus, "praustuvės montavimas") == _qty(base, "praustuvės montavimas") == [2]
    assert _qty(plus, "praustuvės maišytuvo potinkinės") == [2]
    assert _qty(plus, "plautuvės montavimas") == [4]


def test_read_plautuve_count_raises_the_room_type_default():
    """One virtuvė room, but the plumbing sheet also shows the laundry sink."""
    out = _build(symbols={"praustuves": 2, "plautuves": 2},
                 rooms=[_room(nr="107"), _kitchen()])
    assert _qty(out, "plautuvės montavimas") == [2]
    assert _qty(out, "virtuvės maišytuvo montavimas") == [2]


def test_read_plautuves_bill_even_when_no_room_is_classified_virtuve():
    """objektas_a: room 102 "Svetainė/virtuvė" is classified `valgomasis` and the
    skalbykla is its own paskirtis, so the room-type default is 0 — yet the
    plumbing sheet shows two sinks. Evidence has to be able to bill them."""
    out = _build(symbols={"praustuves": 2, "plautuves": 2},
                 rooms=[_room(nr="107"), _room(nr="111"),
                        _room(nr="102", paskirtis="valgomasis"),
                        _room(nr="106", paskirtis="skalbykla")])
    assert _qty(out, "plautuvės montavimas") == [2]
    assert _qty(out, "virtuvės maišytuvo montavimas") == [2]


def test_a_read_plautuve_count_is_not_labelled_a_room_type_default():
    out = _build(symbols={"praustuves": 2, "plautuves": 2},
                 rooms=[_room(nr="107"), _kitchen()])
    plaut = [p for p in _san(out) if "plautuvės montavimas" in p["aprasymas"].lower()]
    assert [p["saltinis"] for p in plaut] == ["simboliai_brezinyje"]
    # …and the room-type fallback still says so.
    only_room = _build(symbols={"praustuves": 2}, rooms=[_room(nr="107"), _kitchen()])
    plaut2 = [p for p in _san(only_room) if "plautuvės montavimas" in p["aprasymas"].lower()]
    assert [p["saltinis"] for p in plaut2] == ["paskirtis_default"]


def test_extract_without_the_plautuves_key_behaves_exactly_as_before():
    """Every project cached or priced before 2026-07-29 carries no `plautuves`.
    Those must rebuild on the room-type count alone — no new lines appearing
    under an already-quoted sąmata, no retroactive re-pricing."""
    no_kitchen = _build(symbols={"praustuves": 3},
                        rooms=[_room(nr="107"), _room(nr="111")])
    assert _qty(no_kitchen, "plautuvės montavimas") == []
    with_kitchen = _build(symbols={"praustuves": 3},
                          rooms=[_room(nr="107"), _kitchen()])
    assert _qty(with_kitchen, "plautuvės montavimas") == [1]
    assert _qty(with_kitchen, "virtuvės maišytuvo montavimas") == [1]


@pytest.mark.parametrize("n_plautuves", [1, 2, 5])
def test_plautuve_and_its_mixer_can_never_drift(n_plautuves):
    out = _build(symbols={"praustuves": 2, "plautuves": n_plautuves},
                 rooms=[_room(nr="107"), _kitchen()])
    assert (_qty(out, "plautuvės montavimas")
            == _qty(out, "virtuvės maišytuvo montavimas") == [n_plautuves])


def test_moving_a_sink_between_buckets_does_not_change_the_hole_count():
    """Skylių gręžimas bills 6 holes per sink. The kitchen sink changed BUCKET,
    not location — it is still drilled through a tiled backsplash, so the total
    must be identical either way. No eval metric covers this line."""
    rooms = [_room(nr="107"), _room(nr="111"), _kitchen()]

    def _holes(out):
        return [p["kiekis"] for p in out["pozicijos"]
                if "skylių gręžimas" in p["aprasymas"].lower()]

    before = _build(symbols={"praustuves": 3}, rooms=rooms)          # old bucket
    after = _build(symbols={"praustuves": 2, "plautuves": 1}, rooms=rooms)
    assert _holes(after) == _holes(before) != []


def test_dry_project_emits_no_sanitary_lines_at_all():
    out = _build(rooms=[_room(nr="1", paskirtis="miegamoji")])
    assert _san(out) == []
    assert out["_sanitary_assumptions"] == []


# ── merge safety: a project priced BEFORE the split must not double-bill ─────
def _prior(label, **kw):
    row = {"skyrius": "Santechnikos darbai", "aprasymas": label,
           "vnt": "vnt", "kiekis": 2}
    row.update(kw)
    return row


def test_legacy_label_folds_onto_the_rough_in_half():
    from api.recompute_quantities import _norm_label
    assert (_norm_label("Praustuvės maišytuvo montavimas")
            == "potinkinio praustuvės maišytuvo potinkinės dalies montavimas")
    assert (_norm_label("Dušo maišytuvo sistemos montavimas")
            == "potinkinio dušo maišytuvo potinkinės dalies montavimas")


def test_priced_legacy_line_carries_its_price_onto_the_pair_not_a_duplicate():
    from api.recompute_quantities import _merge_user_edits
    rebuilt = [_prior(_SAN_MIXER_LINES["praustuve"][0]),
               _prior(_SAN_MIXER_LINES["praustuve"][1])]
    prior = [_prior("Praustuvės maišytuvo montavimas", kaina=45.0)]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    labels = [p["aprasymas"] for p in out]
    assert "Praustuvės maišytuvo montavimas" not in labels, labels
    assert len(out) == 2, labels
    rough_in = next(p for p in out if p["aprasymas"] == _SAN_MIXER_LINES["praustuve"][0])
    assert rough_in["kaina"] == 45.0
    assert any(n.get("reason") == "relabeled" for n in notes), notes


def test_unpriced_legacy_line_is_suppressed_not_orphan_carried():
    from api.recompute_quantities import _merge_user_edits
    rebuilt = [_prior(_SAN_MIXER_LINES["dusas"][0]),
               _prior(_SAN_MIXER_LINES["dusas"][1])]
    prior = [_prior("Dušo maišytuvo sistemos montavimas")]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 2, [p["aprasymas"] for p in out]
    assert not any(p.get("_orphaned_after_rebuild") for p in out)
    # `relabeled` (not `superseded_by_tier`) so InteriorProject.jsx forwards it
    # to the frontend merge and the browser side drops the row too.
    note = next(n for n in notes if n["aprasymas"] == "Dušo maišytuvo sistemos montavimas")
    assert note["reason"] == "relabeled"
    assert note["into"] == _SAN_MIXER_LINES["dusas"][0].lower()


def test_legacy_line_is_kept_when_the_rebuild_did_not_split():
    """Split turned off → the rebuild re-emits the legacy label, pass 1 matches
    it exactly and nothing is suppressed or renamed."""
    from api.recompute_quantities import _merge_user_edits
    rebuilt = [_prior("Praustuvės maišytuvo montavimas")]
    prior = [_prior("Praustuvės maišytuvo montavimas", kaina=45.0)]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 1 and out[0]["kaina"] == 45.0
    assert not notes, notes


@pytest.mark.parametrize("n_praustuves", [1, 3, 7])
def test_pair_halves_can_never_drift(n_praustuves):
    out = _build(symbols={"praustuves": n_praustuves})
    p = _qty(out, "praustuvės maišytuvo potinkinės")
    v = _qty(out, "praustuvės maišytuvo virštinkinės")
    assert p == v == [max(n_praustuves, 2)]

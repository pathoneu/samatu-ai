"""Every reader of a room's paint litres has to read BOTH fields.

F14, 2026-09-02 final review. The extraction pipeline writes one figure per
room in `dazai_l` — walls and ceiling together. The assumptions recompute
(api/recompute_quantities.py) writes the SAME quantity as two fields,
`dazai_l` (walls) + `dazai_luboms_l` (ceiling). Two readers took the first
alone, so both went walls-only the moment a contractor touched Prielaidos:

  · cross_page_validator._rule_paint_consumption_sane divided by
    `dazymo_plotas_m2`, which is walls AND ceiling — the ratio halved on a
    ceiling-heavy room and it warned about a formula that was fine.
  · main._chat_room_summary feeds the AiChat room totals, so the assistant
    under-reported the paint the contractor is buying, as a stated fact.

extractor.sanity_checks already summed both; vision_call._room_dazai_l is the
single definition and both sites now go through it.
"""
from __future__ import annotations

import main
from extractor.cross_page_validator import _rule_paint_consumption_sane


def _room(nr: str, **kw) -> dict:
    """A room painted at exactly the textbook 0.20 l/m²: 40 m² of wall and
    60 m² of ceiling, 20 l in total."""
    r = {"nr": nr, "pavadinimas": f"Kambarys {nr}",
         "walls_paintable_m2": 40.0, "ceiling_paintable_m2": 60.0,
         "dazymo_plotas_m2": 100.0}
    r.update(kw)
    return r


EXTRACTED = _room("101", dazai_l=20.0)                      # one field
RECOMPUTED = _room("102", dazai_l=8.0, dazai_luboms_l=12.0)  # the same 20 l


# ── cross_page_validator ─────────────────────────────────────────────────────

def test_a_split_paint_figure_raises_no_warning():
    assert _rule_paint_consumption_sane([RECOMPUTED]) == []


def test_the_pre_fix_reading_really_did_warn():
    """The control: 8 l over 100 m² is 0.08 l/m², under the 0.10 floor. Without
    this the test above would pass on a rule that never fires."""
    walls_only = {k: v for k, v in RECOMPUTED.items() if k != "dazai_luboms_l"}
    warns = _rule_paint_consumption_sane([walls_only])
    assert len(warns) == 1
    assert "dažų sąnauda" in warns[0]["message_lt"]


def test_an_extracted_room_is_unchanged():
    """No `dazai_luboms_l` ⇒ byte-identical to before, on both sides of the
    band."""
    assert _rule_paint_consumption_sane([EXTRACTED]) == []
    assert len(_rule_paint_consumption_sane([_room("103", dazai_l=45.0)])) == 1


def test_a_genuinely_wrong_consumption_is_still_caught():
    """The fix must not turn the rule off: 60 l over 100 m² is 0.60 l/m²."""
    warns = _rule_paint_consumption_sane(
        [_room("104", dazai_l=24.0, dazai_luboms_l=36.0)])
    assert len(warns) == 1
    assert warns[0]["discrepancy_pct"] == 200.0


# ── the chat room summary ────────────────────────────────────────────────────

def test_the_chat_totals_count_the_ceiling_litres():
    out = main._chat_room_summary([RECOMPUTED, RECOMPUTED])
    assert out["dazai_l"] == 40.0


def test_the_chat_totals_are_unchanged_for_an_extracted_project():
    out = main._chat_room_summary([EXTRACTED, EXTRACTED])
    assert out["dazai_l"] == 40.0


def test_mixed_rooms_add_up():
    """A project half-edited through Prielaidos carries both shapes at once."""
    out = main._chat_room_summary([EXTRACTED, RECOMPUTED])
    assert out["dazai_l"] == 40.0


def test_a_junk_value_in_one_field_does_not_lose_the_other():
    room = _room("105", dazai_l="n/a", dazai_luboms_l=12.0)
    assert main._chat_room_summary([room])["dazai_l"] == 12.0


def test_every_other_total_still_reads_one_field():
    """The tuple-source change must not have widened anything else."""
    out = main._chat_room_summary([RECOMPUTED])
    assert out["sienu_dazomas_plotas_m2"] == 40.0
    assert out["lubu_dazomas_plotas_m2"] == 60.0
    assert out["dazomas_plotas_m2"] == 100.0

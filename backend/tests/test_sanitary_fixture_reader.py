"""Sanitary fixture reader — point-list reconciliation (2026-06-14).

2026-07-29 additions: `bide` as a first-class fixture, the tub-only
`vonios_kubilai` publication, and classification-aware page selection.
"""
import io

import pytest

from extractor.sanitary_fixture_reader import (
    _FIXTURE_KEYS,
    _USER_SCHEMA,
    SYSTEM_PROMPT,
    _aggregate_fixture_votes,
    _find_sanitary_pages,
    build_user_text,
    reconcile_fixture_counts,
)


def test_reconcile_raises_to_higher_and_reports():
    # main pass saw 3 sinks; point-list enumeration found 4 → raise + report.
    out = reconcile_fixture_counts({"praustuves": 3, "klozetai": 2},
                                   {"praustuves": 4, "klozetai": 2, "dusai": 2})
    assert out["merged"]["praustuves"] == 4
    assert out["merged"]["dusai"] == 2          # reader-only fixture also raised
    assert "praustuves" in out["raised"] and out["any_raised"]
    assert out["merged"]["klozetai"] == 2       # agree → unchanged, not in raised


def test_reconcile_never_lowers():
    # reader under-counts vs the symbol pass → keep the higher symbol count.
    out = reconcile_fixture_counts({"praustuves": 5}, {"praustuves": 3})
    assert out["merged"]["praustuves"] == 5
    assert out["raised"] == []


def test_build_user_text_lists_wet_rooms():
    txt = build_user_text([{"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia"},
                           {"nr": "2", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji"}])
    assert "Vonia" in txt and "Miegamasis" not in txt  # only wet rooms listed
    assert "prietais" in txt.lower()


# ── bidė as a first-class fixture (2026-07-29) ───────────────────────────────
# The contractor bills "Bide dušiukų potinkinės/virštinkinės dalies" on berzas
# AND objektas_b (3+3 each). No reader produced the count, so the emit layer
# could only raise a kiekis=null checklist row.

def test_bide_is_a_fixture_key_the_whole_chain_carries():
    assert "bide" in _FIXTURE_KEYS
    assert "bide_count" in _USER_SCHEMA          # the model is asked for it
    assert "BIDĖ" in SYSTEM_PROMPT.upper()       # …and told how to recognise it


def test_bide_count_reaches_the_symbol_summary():
    out = reconcile_fixture_counts({"praustuves": 3, "klozetai": 2},
                                   {"praustuves": 3, "klozetai": 2, "bide": 3})
    assert out["merged"]["bide"] == 3            # symbols carry no bide → raised
    assert "bide" in out["raised"]


def test_no_bide_read_stays_zero_not_invented():
    """Absent bidė must land as 0 — the emit layer turns that into a visible
    checklist TODO. It must never be defaulted from the klozetas count: berzas
    is billed 3 bidė against 2 klozetai."""
    out = reconcile_fixture_counts({"praustuves": 3, "klozetai": 2},
                                   {"praustuves": 3, "klozetai": 2, "bide": 0})
    assert out["merged"]["bide"] == 0
    assert "bide" not in out["raised"]


def test_bide_votes_are_moded_like_every_other_fixture():
    def _run(bide):
        return {"status": "ok",
                "counts": {"praustuves": 3, "klozetai": 2, "vonios": 1,
                           "dusai": 2, "wc_remai": 2, "bide": bide}}
    out = _aggregate_fixture_votes([_run(3), _run(2), _run(3)])
    assert out["counts"]["bide"] == 3            # mode of (3,2,3), not max/mean
    assert out["_vote"]["spread"]["bide"] == 1   # disagreement surfaced


def test_bide_vote_tie_takes_the_median_not_the_max():
    """Two rounds, two answers — no covert oracle drift toward the bigger number."""
    def _run(bide):
        return {"status": "ok", "counts": {"bide": bide}}
    assert _aggregate_fixture_votes([_run(1), _run(3)])["counts"]["bide"] == 2


# ── vonia ≠ dušas: the tub-only count is published separately ────────────────
# detected_symbols_summary["vonios"] means "Vonios + dušo padėklai" (prompt.py),
# so it cannot gate a BATHTUB mixer. The reader counts the two apart.

def test_reader_tub_count_is_published_separately_from_the_conflated_symbol():
    out = reconcile_fixture_counts({"vonios": 3},           # 1 tub + 2 trays
                                   {"vonios": 1, "dusai": 2})
    assert out["merged"]["vonios"] == 3          # conflated key untouched
    assert out["merged"]["vonios_kubilai"] == 1  # …tub-only count alongside it
    assert out["merged"]["dusai"] == 2           # showers stay showers


def test_shower_only_project_publishes_zero_tubs():
    out = reconcile_fixture_counts({"vonios": 1},           # the tray
                                   {"vonios": 0, "dusai": 1})
    assert out["merged"]["vonios_kubilai"] == 0


def test_no_reader_run_publishes_no_tub_key_at_all():
    """Absent key is the signal "we have no tub evidence" — distinct from 0."""
    out = reconcile_fixture_counts({"vonios": 1}, {})
    assert "vonios_kubilai" not in out["merged"]


# ── praustuvė ≠ plautuvė: the kitchen sink gets its own key (2026-07-29) ─────
# The prompt used to ask for "praustuvės/kriauklės", and "kriauklė" covers a
# KITCHEN sink. A live 3/3-agreeing probe on berzas enumerated 4 praustuvės, of
# which two were the virtuvės and skalbyklos PLAUTUVĖS. The emit layer bills
# "Plautuvės montavimas" off a separate count, so on any project with a room
# classified `virtuve` that one sink was billed twice.

def test_plautuve_is_a_fixture_key_the_whole_chain_carries():
    assert "plautuves" in _FIXTURE_KEYS
    assert "plautuves_count" in _USER_SCHEMA        # the model is asked for it
    assert '"plautuve"' in _USER_SCHEMA             # …and it is a valid `tipas`
    assert "PLAUTUVĖ" in SYSTEM_PROMPT.upper()      # …and told how to tell them apart


def test_prompt_no_longer_calls_a_kitchen_sink_a_praustuve():
    """The exact wording that caused the miscount. `kriauklė` may appear only
    where it defines a PLAUTUVĖ, never as a gloss for `praustuvės`."""
    assert "praustuvės/kriauklės" not in SYSTEM_PROMPT
    assert "praustuvės / kriauklės" not in SYSTEM_PROMPT


def test_kitchen_and_laundry_sinks_reach_their_own_symbol_key():
    """berzas as the reader now reads it: 2 praustuvės + 2 plautuvės, not 4
    praustuvės. Both counts survive to detected_symbols_summary."""
    out = reconcile_fixture_counts({"praustuves": 0},
                                   {"praustuves": 2, "plautuves": 2})
    assert out["merged"]["praustuves"] == 2
    assert out["merged"]["plautuves"] == 2
    assert "plautuves" in out["raised"]             # symbols carried none


def test_plautuve_count_obeys_the_never_lower_policy():
    """Same rule as every other fixture: enumeration may RAISE the symbol pass,
    never silently lower it."""
    out = reconcile_fixture_counts({"plautuves": 3}, {"plautuves": 1})
    assert out["merged"]["plautuves"] == 3
    assert "plautuves" not in out["raised"]


def test_plautuves_votes_are_moded_like_every_other_fixture():
    def _run(plautuves):
        return {"status": "ok", "counts": {"praustuves": 2, "plautuves": plautuves}}
    out = _aggregate_fixture_votes([_run(2), _run(1), _run(2)])
    assert out["counts"]["plautuves"] == 2          # mode of (2,1,2)
    assert out["_vote"]["spread"]["plautuves"] == 1


def test_no_plautuve_read_is_zero_not_absent():
    """A reader that ran and saw no kitchen sink must say 0, so the emit layer
    can tell "none there" from "never looked"."""
    out = reconcile_fixture_counts({}, {"praustuves": 2, "plautuves": 0})
    assert out["merged"]["plautuves"] == 0


# ── page selection ───────────────────────────────────────────────────────────
class _FakePage:
    def __init__(self, text):
        self._t = text

    def extract_text(self):
        return self._t


class _FakePdf:
    def __init__(self, texts):
        self.pages = [_FakePage(t) for t in texts]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_pdf(monkeypatch):
    def _install(texts):
        monkeypatch.setattr(
            "extractor.sanitary_fixture_reader.pdfplumber.open",
            lambda *a, **k: _FakePdf(texts))
    return _install


def test_classified_plumbing_page_wins_over_any_text_hit(fake_pdf):
    fake_pdf(["Maišytuvas ant baldo", "SANTECHNIKOS PLANAS", "Maišytuvas"])
    pages = _find_sanitary_pages(b"", [{"nr": 1, "tipas": "floor_plan"},
                                       {"nr": 3, "tipas": "plumbing"}])
    assert pages == [3]


def test_title_block_hit_beats_a_bare_maisytuvas_mention(fake_pdf):
    """objektas_b: page 2 is the baldų planas that annotates a maišytuvas,
    page 4 is the santechnikos planas. The old scan burned a slot on page 2."""
    fake_pdf(["titulinis", "Maišytuvo pajungimas", "baldai", "SANTECHNIKOS PLANAS"])
    assert _find_sanitary_pages(b"", None) == [4]


def test_a_page_classified_as_another_role_can_never_be_the_plumbing_sheet(fake_pdf):
    """romainiai: the two sheets naming SANTECHNIKA are the apšvietimo planas."""
    fake_pdf(["Maišytuvas", "SANTECHNIKA minima pastabose"])
    pages = _find_sanitary_pages(b"", [{"nr": 2, "tipas": "electrical"}])
    assert pages == [1]                      # the vetoed strong hit does not win


def test_no_plumbing_evidence_reads_nothing(fake_pdf):
    """ciurliu/lazunu have no plumbing sheet — skipping is the correct answer,
    not reading a floor plan and counting fixtures off it."""
    fake_pdf(["Baldų planas", "Elektros planas", "Apšvietimo planas"])
    assert _find_sanitary_pages(b"", None) == []


def test_page_budget_is_still_two(fake_pdf):
    fake_pdf(["SANTECHNIKOS PLANAS"] * 5)
    assert len(_find_sanitary_pages(b"", None)) == 2

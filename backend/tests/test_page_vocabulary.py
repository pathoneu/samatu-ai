"""ONE canonical page vocabulary (2026-07-29).

Two page-type vocabularies used to coexist without lining up:
`page_classifier.PageType` and the `puslapiai[].tipas` enum in `prompt.py`.
The consequence was silent: lookups keyed on names that no producer could
ever emit, so the branch behind them never ran and nobody noticed.

These tests pin the reconciliation and — more importantly — assert that the
previously-dead names now resolve.
"""
from __future__ import annotations

import pytest

from extractor.height_fusion import HEIGHT_SECTION_TIPAI, height_scan_pages
from extractor.page_classifier import (
    CANONICAL_TIPAI,
    PageType,
    canonical_tipas,
)
from extractor.prompt import OUTPUT_SCHEMA


def _prompt_tipas_enum() -> set[str]:
    """The `puslapiai[].tipas` enum straight out of the Pass-1 output schema
    — the vocabulary the extraction prompts actually emit."""
    return set(OUTPUT_SCHEMA["properties"]["puslapiai"]["items"]
               ["properties"]["tipas"]["enum"])


# ── prompt.py is canonical ────────────────────────────────────────────────

def test_every_prompt_tipas_is_canonical():
    """prompt.py's names win: each one must be a canonical value verbatim.
    If someone adds a page type to the Pass-1 schema without adding it here,
    every routing lookup silently stops matching it."""
    missing = _prompt_tipas_enum() - CANONICAL_TIPAI
    assert not missing, f"prompt.py emits page types the vocabulary lacks: {missing}"


def test_canonical_adds_only_the_two_classifier_only_tags():
    """The canonical set is prompt.py's enum plus exactly the classifier
    tags that have no prompt counterpart — no silent third vocabulary."""
    assert CANONICAL_TIPAI - _prompt_tipas_enum() == {"stogo_planas", "legend"}


def test_every_page_type_enum_member_resolves():
    """`PageType` is the other producer. Every member must map onto a
    canonical name — `stogo_planas` in particular was unreachable before."""
    for member in PageType:
        resolved = canonical_tipas(member)
        assert resolved in CANONICAL_TIPAI, f"{member} → {resolved}"


def test_stogo_planas_is_reachable():
    """The bug: `stogo_planas` existed in the classifier enum and in NO
    consumer vocabulary, so no lookup could ever match a roof plan."""
    assert canonical_tipas(PageType.STOGO_PLANAS) == "stogo_planas"
    assert canonical_tipas("stogo_planas") == "stogo_planas"
    assert canonical_tipas("roof_plan") == "stogo_planas"


# ── the dead height_fusion lookups ────────────────────────────────────────

def test_dead_height_lookup_names_now_resolve_to_section():
    """`height_fusion.HEIGHT_SECTION_TIPAI` listed "cross_section" and
    "detail" as page types. Neither exists in either vocabulary, so those
    two lookups could never match anything. They are aliases now."""
    assert canonical_tipas("cross_section") == "section"
    assert canonical_tipas("detail") == "section"
    assert canonical_tipas("pjuvis") == "section"


def test_height_section_tipai_are_all_canonical():
    """Whatever this tuple lists must be matchable — that was the bug."""
    for tipas in HEIGHT_SECTION_TIPAI:
        assert tipas in CANONICAL_TIPAI


def test_height_scan_routes_a_formerly_dead_alias():
    """End-to-end: an extract labelling its pjūvis "cross_section" used to
    be ignored by the height scan. It must now sort first, ahead of the
    ceiling plan, exactly as a "section" would."""
    ai = {"puslapiai": [
        {"nr": 1, "tipas": "floor_plan"},
        {"nr": 2, "tipas": "ceiling_plan"},
        {"nr": 3, "tipas": "cross_section"},
    ]}
    assert height_scan_pages(ai, max_pages=6)[0] == 3


def test_height_scan_still_prefers_plain_section():
    ai = {"puslapiai": [
        {"nr": 1, "tipas": "floor_plan"},
        {"nr": 2, "tipas": "section"},
    ]}
    assert height_scan_pages(ai, max_pages=6)[0] == 2


# ── normalisation is total and fails open ─────────────────────────────────

@pytest.mark.parametrize("raw", [None, "", "   ", "gibberish", "42", "FLOOR-PLAN"])
def test_unrecognised_input_becomes_unknown_never_raises(raw):
    """Every caller is a page-routing decision. Unrecognised input must
    resolve to "unknown" (treated as keep/don't-route), never crash an
    extraction mid-flight."""
    assert canonical_tipas(raw) == "unknown"


@pytest.mark.parametrize("raw,expected", [
    ("FLOOR_PLAN", "floor_plan"),
    ("  Ceiling_Plan  ", "ceiling_plan"),
    ("Section", "section"),
])
def test_case_and_whitespace_are_normalised(raw, expected):
    assert canonical_tipas(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("išklotinė", "wall_elevation"),
    ("isklotine", "wall_elevation"),
    ("wall_development", "wall_elevation"),
    ("vizualizacija", "non_relevant"),
    ("visualization", "non_relevant"),
    ("render", "non_relevant"),
    ("sklypo_planas", "site_plan"),
    ("cover", "title_page"),
    ("room_schedule", "eksplikacija"),
])
def test_lt_and_common_aliases_map_explicitly(raw, expected):
    assert canonical_tipas(raw) == expected


def test_canonical_values_are_idempotent():
    """Normalising an already-canonical name must be a no-op, or repeated
    passes through the router would drift."""
    for tipas in CANONICAL_TIPAI:
        assert canonical_tipas(tipas) == tipas

"""Week 3 Task 3.3 — page classifier routing."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from backend.extractor.page_classifier import (  # noqa: E402
    PageType,
    PageClassification,
    parse_classification,
)
from backend.extractor.prompts import PROMPTS_BY_PAGE_TYPE  # noqa: E402


def test_all_page_types_present():
    expected = {
        "floor_plan", "ceiling_plan", "wall_elevation", "electrical",
        "plumbing", "eksplikacija", "legend", "unknown",
    }
    got = {pt.value for pt in PageType}
    assert expected.issubset(got)


def test_parse_classification_high_confidence():
    payload = {"page_type": "floor_plan", "confidence": 0.97, "top_2": None}
    c = parse_classification(payload)
    assert c.page_type == PageType.FLOOR_PLAN
    assert c.confidence == pytest.approx(0.97)
    assert c.top_2 is None


def test_parse_classification_low_confidence_exposes_top_2():
    """When Haiku confidence < 0.85, top_2 must be populated for downstream
    Opus prompt fallback (Council R2 risk: classifier errors propagate)."""
    payload = {"page_type": "floor_plan", "confidence": 0.6, "top_2": "wall_elevation"}
    c = parse_classification(payload)
    assert c.confidence < 0.85
    assert c.top_2 == PageType.WALL_ELEVATION


def test_routing_table_covers_six_specialized_pages():
    """Six specialized prompts: floor_plan, ceiling_plan, wall_elevation,
    electrical, plumbing, eksplikacija. legend + unknown are routed elsewhere."""
    expected_keys = {
        "floor_plan", "ceiling_plan", "wall_elevation",
        "electrical", "plumbing", "eksplikacija",
    }
    assert expected_keys == set(PROMPTS_BY_PAGE_TYPE.keys())


def test_all_specialized_prompts_share_base_rules():
    from backend.extractor.prompts.base_system import BASE_RULES
    for name, prompt in PROMPTS_BY_PAGE_TYPE.items():
        assert BASE_RULES[:60] in prompt, f"{name} prompt missing base rules"


def test_no_specialized_prompt_hardcodes_color_rules():
    """Hard-coded `RED=LED`-style rules removed in Week 3 (R3)."""
    forbidden = ["RED=LED", "BLUE=smoke", "YELLOW=lights", "raudona=LED"]
    for name, prompt in PROMPTS_BY_PAGE_TYPE.items():
        for token in forbidden:
            assert token not in prompt, f"{name} re-introduced {token}"

"""Week 3 Task 3.4 — Sonnet legend output is structured + injectable."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extractor import legend_injection  # noqa: E402
from extractor.prompts.floor_plan import FLOOR_PLAN_PROMPT  # noqa: E402


def test_module_has_no_hardcoded_color_semantics():
    src = inspect.getsource(legend_injection)
    forbidden = ["RED=LED", "BLUE=smoke", "YELLOW=lights"]
    for token in forbidden:
        assert token not in src, f"legend_injection still hard-codes {token}"


def test_build_legend_block_renders_glyph_and_color_layers():
    legend = {
        "symbols": [
            {"glyph": "circle_with_cross", "meaning": "ceiling_light"},
            {"colored_line": "#ff0000", "meaning": "led_strip"},
            {"colored_hatch": "#999999", "meaning": "gkp_partition"},
        ],
    }
    block = legend_injection.build_legend_block(legend)
    assert "ceiling_light" in block
    assert "led_strip" in block
    assert "gkp_partition" in block
    assert "circle_with_cross" in block
    # Color hex preserved (case-insensitive).
    assert "#ff0000" in block.lower()
    assert "#999999" in block.lower()


def test_inject_legend_appends_block_to_prompt():
    legend = {"symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    composed = legend_injection.inject_legend(FLOOR_PLAN_PROMPT, legend)
    assert FLOOR_PLAN_PROMPT in composed
    assert "led_strip" in composed
    # Legend block is AFTER the base/page-type prompt so Opus reads project
    # legend BEFORE applying any conventions.
    assert composed.index("led_strip") > composed.index("aukšto planas")


def test_inject_legend_with_none_returns_prompt_unchanged():
    composed = legend_injection.inject_legend(FLOOR_PLAN_PROMPT, None)
    assert composed == FLOOR_PLAN_PROMPT


def test_build_legend_block_handles_empty_symbols_explicitly():
    block = legend_injection.build_legend_block({"symbols": []})
    assert "no legend detected" in block.lower()
    # Even with empty legend, downstream behaviour (return unknown_symbol)
    # is still spelled out.
    assert "unknown_symbol" in block

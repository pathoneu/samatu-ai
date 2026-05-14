"""Unit tests for the sub-dimension-sum constraint verifier."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.constraint_check import (  # noqa: E402
    SubDimensionGroup,
    verify_sub_dim_sums,
)
from extractor.roof.evidence import HITLFlagReason  # noqa: E402
from extractor.roof.page_authority import RoofInputField  # noqa: E402


def test_clean_sum_no_flag():
    """4.10 + 3.10 = 7.20 (within 1cm of overall 7.20)."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=7.20,
            sub_values_m=[4.10, 3.10],
            tolerance_m=0.01,
        ),
    ])
    assert flags == []


def test_mismatched_sum_flags_axis_width():
    """4.10 + 3.10 = 7.20 but overall reads 7.12 → 8cm mismatch."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=7.12,
            sub_values_m=[4.10, 3.10],
            tolerance_m=0.01,
        ),
    ])
    assert len(flags) == 1
    assert flags[0].field == RoofInputField.AXIS_WIDTH
    assert flags[0].reason == HITLFlagReason.SUB_DIM_SUM_MISMATCH
    assert "7.12" in flags[0].message and "7.20" in flags[0].message


def test_no_sub_dims_no_flag():
    """If sub_values_m is empty, no constraint to check."""
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=10,
            page_class=PageType.STOGO_PLANAS,
            overall_value_m=8.70,
            sub_values_m=[],
            tolerance_m=0.01,
        ),
    ])
    assert flags == []


@pytest.mark.parametrize("overall,subs,expect_flag", [
    (7.20, [3.80, 3.40], False),    # sums exactly
    (7.20, [3.80, 3.41], False),    # within 1cm
    (7.20, [3.80, 3.39], False),    # within 1cm on the other side
    (7.20, [3.85, 3.40], True),     # 5cm off — flag
    (7.20, [4.10, 3.10], False),    # different breakdown, still sums
])
def test_tolerance_boundary(overall, subs, expect_flag):
    flags = verify_sub_dim_sums([
        SubDimensionGroup(
            field=RoofInputField.AXIS_WIDTH,
            page_num=46,
            page_class=PageType.FLOOR_PLAN,
            overall_value_m=overall,
            sub_values_m=subs,
            tolerance_m=0.01,
        ),
    ])
    assert (len(flags) > 0) == expect_flag

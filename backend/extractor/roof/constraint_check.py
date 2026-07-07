"""Constraint Verification Graph.

LT brėžiniai often annotate BOTH an overall axis dimension and the
sub-segments that should sum to it (e.g. axis spacing 4.10m + 3.10m =
overall 7.20m). When Vision extracts both, this module verifies the
sums and raises HITLFlag entries on mismatch.

Source: 2026-05-14 consultcouncil — Gemini's Constraint Verification
Graph proposal, three-way consensus in R3. This is the *independent*
within-artifact check (vs Claude R1's circular geometric cross-val).
"""
from __future__ import annotations

from dataclasses import dataclass

from extractor.page_classifier import PageType
from extractor.roof.evidence import HITLFlag, HITLFlagReason
from extractor.roof.page_authority import RoofInputField


@dataclass(frozen=True)
class SubDimensionGroup:
    """One (field, page) pair carrying both an overall and its sub-dim breakdown."""
    field: RoofInputField
    page_num: int
    page_class: PageType
    overall_value_m: float
    sub_values_m: list[float]
    tolerance_m: float = 0.01


def verify_sub_dim_sums(groups: list[SubDimensionGroup]) -> list[HITLFlag]:
    """Return a HITLFlag for each group where sub_values don't sum to overall."""
    flags: list[HITLFlag] = []
    for g in groups:
        if not g.sub_values_m:
            continue
        actual_sum = sum(g.sub_values_m)
        diff = abs(actual_sum - g.overall_value_m)
        # Round to mm precision to absorb FP representation noise
        # (e.g. 3.80 + 3.39 - 7.20 == 0.01000000000000067 in IEEE-754).
        if round(diff, 4) > g.tolerance_m:
            flags.append(HITLFlag(
                field=g.field,
                reason=HITLFlagReason.SUB_DIM_SUM_MISMATCH,
                message=(
                    f"On page {g.page_num} ({g.page_class.value}): "
                    f"sub-dimensions {g.sub_values_m} sum to {actual_sum:.2f}m "
                    f"but overall reads {g.overall_value_m:.2f}m "
                    f"(Δ {diff*100:.0f}cm > {g.tolerance_m*100:.0f}cm tol)."
                ),
                evidence=[],
                eur_impact_estimate=350.0,
            ))
    return flags

"""Unit tests for DimensionEvidence + HITLFlag."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.evidence import (  # noqa: E402
    DimensionEvidence,
    HITLFlag,
    HITLFlagReason,
)
from extractor.roof.page_authority import RoofInputField  # noqa: E402


def test_dimension_evidence_roundtrip():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=7.12,
        page_num=46,
        page_class=PageType.FLOOR_PLAN,
        source_crop_bbox=(0.1, 0.2, 0.5, 0.6),
        raw_label_text="7,12",
        confidence=0.86,
    )
    assert ev.field is RoofInputField.AXIS_WIDTH
    assert ev.value == pytest.approx(7.12)
    assert ev.is_authoritative()


def test_dimension_evidence_unauthoritative_when_wrong_page_class():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=4.61,
        page_num=48,
        page_class=PageType.SECTION,        # SECTION cannot write AXIS_WIDTH
        source_crop_bbox=None,
        raw_label_text="4,61",
        confidence=0.8,
    )
    assert not ev.is_authoritative()


def test_hitl_flag_carries_reason_and_evidence():
    ev = DimensionEvidence(
        field=RoofInputField.AXIS_WIDTH,
        value=7.12,
        page_num=46,
        page_class=PageType.FLOOR_PLAN,
        source_crop_bbox=None,
        raw_label_text="7,12",
        confidence=0.7,
    )
    flag = HITLFlag(
        field=RoofInputField.AXIS_WIDTH,
        reason=HITLFlagReason.SUB_DIM_SUM_MISMATCH,
        message="sub-dims sum to 7.20, overall reads 7.12 (0.08m mismatch)",
        evidence=[ev],
        eur_impact_estimate=420.0,
    )
    assert flag.reason is HITLFlagReason.SUB_DIM_SUM_MISMATCH
    assert flag.eur_impact_estimate == pytest.approx(420.0)
    assert flag.evidence[0].page_num == 46


@pytest.mark.parametrize("reason", list(HITLFlagReason))
def test_hitl_flag_reasons_have_human_readable_names(reason):
    assert isinstance(reason.value, str)
    assert len(reason.value) > 0

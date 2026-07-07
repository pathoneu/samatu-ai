"""Evidence + HITL flag dataclasses for the typed roof merger.

Each DimensionEvidence is one (field, value, page) triple with full
provenance: which page produced it, what page_class that page was
classified as, the source crop bbox, the raw text label that was read,
and the model's confidence. The merger uses these to populate
RoofInput; the UI (separate plan) renders them as the "patikrinkite"
ledger.

HITLFlag entries are raised when the constraint-verification step
catches a mismatch that cannot be resolved silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from enum import Enum

from extractor.page_classifier import PageType
from extractor.roof.page_authority import PAGE_AUTHORITY, RoofInputField


@dataclass(frozen=True)
class DimensionEvidence:
    """One extracted value with full provenance back to its source page."""
    field: RoofInputField
    value: float | int | str
    page_num: int
    page_class: PageType
    source_crop_bbox: tuple[float, float, float, float] | None  # normalized (x0,y0,x1,y1)
    raw_label_text: str
    confidence: float

    def is_authoritative(self) -> bool:
        """True iff this evidence's page_class is allowed to write `self.field`."""
        return self.field in PAGE_AUTHORITY.get(self.page_class, set())


class HITLFlagReason(str, Enum):
    """Why a dimension was kicked to human-in-the-loop review."""
    SUB_DIM_SUM_MISMATCH = "sub_dim_sum_mismatch"           # sums don't add up
    NO_AUTHORITATIVE_SOURCE = "no_authoritative_source"     # all sources unauthorized
    LOW_CONFIDENCE = "low_confidence"                       # model conf < threshold
    CONFLICTING_AUTHORITATIVE_SOURCES = "conflicting_authoritative_sources"


@dataclass(frozen=True)
class HITLFlag:
    """A dimension the system refuses to commit autonomously.

    `evidence` lists all extracted candidates for this field. `message`
    is the human-readable explanation for the patikrinkite UI.
    `eur_impact_estimate` is the maximum cost swing if this dimension
    is off by its current uncertainty band — used to prioritise which
    flags to surface first.
    """
    field: RoofInputField
    reason: HITLFlagReason
    message: str
    evidence: list[DimensionEvidence] = dc_field(default_factory=list)
    eur_impact_estimate: float = 0.0

"""Base interfaces for roof type strategies.

Each strategy maps from RoofInput (geometric + structural dim's extracted
from PDF) to RoofOutput (15-row kiekių žiniaraštis conformant to LT-pro
sąmata template per roof type).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


RoofTypeName = Literal[
    "dvislaitis", "keturslaitis", "vienslaitis", "plokscias",
    "mansardinis", "sudetinis", "unknown"
]


@dataclass
class RoofInput:
    """All extracted dim's + slope angles needed for geometric calc.

    Filled by Vision extraction (Phase 1+) or hardcoded in Phase 0 tests.
    """
    roof_type: RoofTypeName
    building_length_m: float
    building_width_m: float
    eaves_overhang_m: float
    slopes_deg: list[float]               # 1 for vienslaitis, 1 for dvislaitis, 2 for keturslaitis asym
    wall_thickness_m: float = 0.25        # blokeliai 25cm typical
    eaves_to_ground_m: float = 0.0
    soflitas_depth_m: float = 0.5
    chimney_count: int = 0
    rooflight_count: int = 0
    windows_count: int = 0
    waste_factor: float = 0.05
    # Optional structural cross-check (from SK dalis)
    murloto_total_length_m: float | None = None


@dataclass
class LineItem:
    """One row of the kiekių žiniaraštis."""
    pozicija: str                          # e.g., "Stogas (skarda)"
    kiekis: float
    vnt: str                               # m², m, vnt
    confidence: Literal["high", "medium", "low"] = "high"
    source_pages: list[int] = field(default_factory=list)
    note: str = ""


@dataclass
class RoofOutput:
    """Computed kiekių žiniaraštis output."""
    roof_type: RoofTypeName
    line_items: list[LineItem]
    warnings: list[str] = field(default_factory=list)
    cross_check_passes: int = 0
    cross_check_total: int = 0


class RoofStrategy(ABC):
    """Strategy interface — one impl per roof type."""

    @abstractmethod
    def supports(self, input_: RoofInput) -> bool:
        """Return True if this strategy can handle the given RoofInput."""
        ...

    @abstractmethod
    def compute(self, input_: RoofInput) -> RoofOutput:
        """Compute kiekių žiniaraštis rows from RoofInput."""
        ...

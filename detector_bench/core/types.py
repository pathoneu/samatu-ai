"""Common types for the symbol-detection bake-off.

All detectors implement Detector ABC and return DetectionResult. Coordinates
are normalized 0-1 fractions of page (BBox.x_pct etc.) so they're DPI-agnostic.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in normalized page coordinates (0.0 - 1.0)."""
    x_pct: float
    y_pct: float
    w_pct: float
    h_pct: float

    def __post_init__(self) -> None:
        for name, val in [
            ("x_pct", self.x_pct), ("y_pct", self.y_pct),
            ("w_pct", self.w_pct), ("h_pct", self.h_pct),
        ]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"BBox.{name}={val} outside [0, 1]")


@dataclass
class DetectionResult:
    """One detector's output for one (pdf, page, symbol_code) call."""
    count: int                       # Reported count (authoritative for ranking)
    bboxes: list[BBox]               # Optional spatial detail; some pipelines
                                     # only count and leave this empty
    runtime_s: float                 # Wall time for this single detect() call
    cost_usd: float                  # API cost ($ for this call), 0 for local
    errors: list[str] = field(default_factory=list)  # Non-fatal warnings
    notes: str = ""                  # Free-form for human inspection


class Detector(ABC):
    """Common interface for every pipeline.

    Lifecycle:
        det = ConcretePipeline()
        det.setup(pdf_path)        # one-time per PDF: extract legend, prerender, etc.
        result = det.detect(pdf_path, page_nr=3, symbol_code="rozete")
        # ... call detect() many times for different (page, symbol) combos
        det.teardown()             # optional cleanup
    """
    name: str = "base"               # Subclass overrides

    @abstractmethod
    def setup(self, pdf_path: Path) -> None:
        """One-time prep per PDF. May extract legend, render pages, build index."""

    @abstractmethod
    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        """Detect all instances of `symbol_code` on `page_nr` of `pdf_path`."""

    def teardown(self) -> None:  # noqa: B027 - optional override
        """Cleanup (close caches, kill subprocesses). Default no-op."""

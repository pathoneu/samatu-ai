"""Human ground-truth schema for EUR-weighted benchmark (R4 / canonical plan §1.5).

Used to validate samatininkas-filled JSONs in `data/human_gt/` before they
become inputs to `scripts/run_eur_benchmark.py`. Replaces the prior AI-seeded
ground truth which was Claude-grading-Claude and produced a 49.3% number that
nobody could trust.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HumanGTLine(BaseModel):
    """One line item on a samatininkas's invoice for one PDF.

    Convention: prices are be-PVM (without VAT) to avoid mode noise across
    the dataset. `bundled_group` lets us collapse rangovas-style invoice lines
    (e.g. glaistymas + dažymas + gruntavimas → one bundle at ~14 €/m²).
    """
    code: str
    label_lt: str
    unit: str
    quantity: float
    unit_price_eur_be_pvm: float | None = None
    bundled_group: str | None = None
    verified_by: str
    notes: str | None = None


class HumanGTPdf(BaseModel):
    """One PDF's full GT. Extra fields (city, floor area) are useful for
    Vilnius +15-25% calibration and per-floor-area sanity checks but optional.
    """
    pdf_id: str
    pdf_hash: str | None = None
    project_type: Literal["interior_finishing"] = "interior_finishing"
    city: str | None = None
    floor_area_m2: float | None = None
    vat_mode: Literal["be_pvm", "with_pvm", "reverse_vat"] = "be_pvm"
    lines: list[HumanGTLine]

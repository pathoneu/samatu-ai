"""Shared PDF discovery helper for baseline / comparison scripts.

Extracted from run_v8_baseline.py during cleanup so baseline_vision.py and
compare_to_extractor.py don't depend on the (now-deleted) V8 baseline script.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training-data"


def find_breziniai_pdf(n: int) -> Path | None:
    """Return the canonical brėžiniai PDF for project N (1..5).

    Strategy:
    1. Exact name `projektas_N_breziniai.pdf` if present
    2. Otherwise the LARGEST `projektas_N(*)_breziniai.pdf` (P5 has 9 numbered
       PDFs; the smallest are 1-page detail sheets — pick the main set).
    3. Also handles the `porjektas_5(4)_breziniai.pdf` typo file.
    """
    proj_dir = TRAINING / f"projektas_{n}"
    if not proj_dir.exists():
        return None
    exact = proj_dir / f"projektas_{n}_breziniai.pdf"
    if exact.exists():
        return exact
    candidates = list(proj_dir.glob(f"projektas_{n}(*)*_breziniai.pdf"))
    candidates += list(proj_dir.glob(f"porjektas_{n}(*)*_breziniai.pdf"))
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_size)
    return None

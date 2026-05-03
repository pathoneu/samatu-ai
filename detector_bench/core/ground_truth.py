"""Ground truth (human-confirmed symbol counts) per (pdf, page).

YAML schema:
    pdf_name: projektas_3_breziniai.pdf
    page_nr: 23
    dpi: 200                       # render DPI when ground truth was authored
    symbols:
      rozete: 47
      jungtukas: 19
      led_strip: 8
    confirmed_at: '2026-05-02T18:00:00Z'
    confirmed_by: user
    notes: electrical layout, 1st floor
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class GroundTruth:
    pdf_name: str
    page_nr: int
    dpi: int
    symbols: dict[str, int]
    confirmed_at: str
    confirmed_by: str
    notes: str = ""


@dataclass
class PageGroundTruth:
    """Convenience alias used in benchmark.py."""
    gt: GroundTruth


def save_ground_truth(gt: GroundTruth, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "pdf_name": gt.pdf_name,
        "page_nr": gt.page_nr,
        "dpi": gt.dpi,
        "symbols": dict(gt.symbols),
        "confirmed_at": gt.confirmed_at,
        "confirmed_by": gt.confirmed_by,
        "notes": gt.notes,
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def load_ground_truth(path: Path) -> GroundTruth:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ground truth not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    syms = data.get("symbols") or {}
    if not isinstance(syms, dict):
        raise ValueError("symbols must be a mapping {symbol_code: int}")
    for k, v in syms.items():
        if not isinstance(v, int):
            raise ValueError(f"symbols.{k}={v!r} must be int")
    return GroundTruth(
        pdf_name=data["pdf_name"],
        page_nr=int(data["page_nr"]),
        dpi=int(data.get("dpi", 200)),
        symbols=syms,
        confirmed_at=str(data.get("confirmed_at", "")),
        confirmed_by=str(data.get("confirmed_by", "")),
        notes=str(data.get("notes", "")),
    )

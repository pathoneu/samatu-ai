"""Translate a fresh /extract-interior response into a canonical
data/predictions/<pdf_id>.pred.json record.

Distinct from build_pred_from_project.py — that one reads from the saved
DB project blob (which has been re-massaged via /recompute and
/save-overrides). This one consumes the raw extractor output, so the
benchmark measures the AI pipeline alone, not the round-trip through
project storage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_pred_from_project import (  # noqa: E402
    project_to_predictions, write_predictions,
)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: build_pred_from_extract.py <extract.json> <pdf_id>",
              file=sys.stderr)
        return 2
    extract_path = Path(sys.argv[1])
    pdf_id = sys.argv[2]
    extract = json.loads(extract_path.read_text(encoding="utf-8"))
    if extract.get("status") == "error":
        print(f"ERR: extraction failed: {extract.get('_error')}",
              file=sys.stderr)
        return 1
    # Map fresh extract shape onto the project shape project_to_predictions
    # expects. v8_rooms holds the deterministic per-room totals; if missing,
    # fall back to patalpos (raw vision pass-1).
    project_like = {
        "v8_rooms": extract.get("v8_rooms") or extract.get("patalpos") or [],
        "patalpos": extract.get("patalpos") or [],
        "pozicijos": extract.get("pozicijos") or [],
    }
    sums = project_to_predictions(project_like)
    out = write_predictions(pdf_id, sums)
    matched = sum(1 for v in sums.values() if v > 0)
    print(f"  {extract_path.name} → {pdf_id}: {matched}/10 codes filled "
          f"→ {out.name}")
    for code, qty in sums.items():
        if qty > 0:
            print(f"    {code:<28} {qty:>8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

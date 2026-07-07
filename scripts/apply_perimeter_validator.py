"""One-shot: run the geometric perimeter validator against every project's
existing ai_extract.json and write the report back as
``_perimeter_validation``.

This backfills the validator output for projects already extracted before
the validator was wired into the production pipeline (in vision_call.py).
Future ``extract_interior()`` runs include it automatically.

Zero Vision spend.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.perimeter_validator import validate_extract


def main() -> int:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    total_flagged = 0
    for entry in (reg.get("projects") or []):
        slug = entry["slug"]
        ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
        if not ai_path.exists():
            print(f"  skip {slug}: no ai_extract.json")
            continue
        ai = json.loads(ai_path.read_text(encoding="utf-8"))
        report = validate_extract(ai)
        ai["_perimeter_validation"] = report
        ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
        flag_count = report["n_needs_reextraction"]
        total_flagged += flag_count
        marker = "⚠" if flag_count else "✓"
        print(f"  {marker} {slug:<14} {report['n_total']} rooms — "
              f"pass {report['n_pass']}, flagged {flag_count}, no_data {report['n_no_data']}")
        for fr in report["flagged_rooms"]:
            print(f"      ↳ room {fr['room_nr']} {fr['room_name'][:30]:<30}  "
                  f"area={fr['area_m2']:.1f}m² perim={fr['perim_m']:.1f}m "
                  f"Δ={fr['discrepancy_pct']:+.1f}%")
    print(f"\n  Total flagged across all projects: {total_flagged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

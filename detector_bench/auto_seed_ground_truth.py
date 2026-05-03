"""Generate UNVERIFIED ground-truth YAMLs from AI first-pass counts.

This is a stand-in for the interactive build_ground_truth.py. The output
files are seeded by Claude alone (no human confirmation), marked
`confirmed_by: claude_unverified_seed`. The benchmark can run against
these — pipelines are scored against AI's-best-guess, not against truth.
The user can later edit any file by hand to correct counts before
re-running benchmark.py.

Usage: venv/bin/python -m detector_bench.auto_seed_ground_truth
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from detector_bench.core.legend_extractor import extract_legend_from_page, crop_glyph_templates
from detector_bench.core.first_pass_count import first_pass_count
from detector_bench.core.ground_truth import GroundTruth, save_ground_truth

REPO = Path("/Users/ignasgaldikas/samatu-ai")
GT_DIR = REPO / "ground_truth"
LEGEND_DIR = REPO / "legends"

# Same test set as build_ground_truth.py (manual flow)
TEST_PAGES = [
    (REPO / "training-data/projektas_1/projektas_1_breziniai.pdf", 8,  8,  "projektas_1_p08", "P1 page 8 — interjeras"),
    (REPO / "training-data/projektas_1/projektas_1_breziniai.pdf", 5,  5,  "projektas_1_p05", "P1 page 5 — santechnika"),
    (REPO / "training-data/projektas_3/projektas_3_breziniai.pdf", 23, 23, "projektas_3_p23", "P3 page 23 — elektra 1 aukštas"),
    (REPO / "training-data/projektas_3/projektas_3_breziniai.pdf", 24, 23, "projektas_3_p24", "P3 page 24 — elektra 2 aukštas (legend on 23)"),
    (Path("/Users/ignasgaldikas/Desktop/Visi techniniai 01.28.pdf"), 5, 5, "visi_techniniai_p05", "VT page 5 — rozetės"),
    (Path("/Users/ignasgaldikas/Desktop/Visi techniniai 01.28.pdf"), 7, 7, "visi_techniniai_p07", "VT page 7 — apšvietimas"),
]


def _load_env() -> None:
    env_path = REPO / "backend" / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    GT_DIR.mkdir(exist_ok=True)
    LEGEND_DIR.mkdir(exist_ok=True)

    for pdf_path, page_nr, legend_page_nr, label, notes in TEST_PAGES:
        pdf_name = pdf_path.name
        gt_path = GT_DIR / f"{label}.yaml"
        if gt_path.exists():
            print(f"[{label}] already exists at {gt_path} — skipping")
            continue

        legend_json = LEGEND_DIR / f"{pdf_path.stem}.json"
        if legend_json.exists():
            items = json.loads(legend_json.read_text())
            print(f"\n[{label}] cached legend: {len(items)} symbols")
        else:
            print(f"\n[{label}] extracting legend from {pdf_name} page {legend_page_nr}…")
            try:
                items = extract_legend_from_page(pdf_path, page_nr=legend_page_nr)
            except Exception as e:
                print(f"  ERROR extracting legend: {e}")
                continue
            legend_json.write_text(json.dumps(items, ensure_ascii=False, indent=2))
            try:
                crop_glyph_templates(
                    pdf_path, page_nr=legend_page_nr, items=items,
                    out_dir=LEGEND_DIR / pdf_path.stem,
                )
            except Exception as e:
                print(f"  WARN cropping templates: {e}")
            print(f"  ↳ {len(items)} symbols saved to {legend_json}")

        if not items:
            print(f"  WARN: no legend symbols. Skipping {label}.")
            continue

        print(f"  asking Claude to count {len(items)} symbols on page {page_nr}…")
        try:
            counts = first_pass_count(pdf_path, page_nr=page_nr, legend_items=items)
        except Exception as e:
            print(f"  ERROR first-pass: {e}")
            continue

        gt = GroundTruth(
            pdf_name=pdf_name,
            page_nr=page_nr,
            dpi=200,
            symbols={k: int(v) for k, v in counts.items()},
            confirmed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            confirmed_by="claude_unverified_seed",
            notes=notes + " — AI-seeded, NOT human-confirmed",
        )
        save_ground_truth(gt, gt_path)
        print(f"  ✓ saved {gt_path}: {gt.symbols}")


if __name__ == "__main__":
    main()

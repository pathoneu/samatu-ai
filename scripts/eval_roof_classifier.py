"""3-tier model bake-off for the stogai V1 page classifier.

Runs `classify_page` against ground-truth page labels for an LT
construction PDF, comparing Haiku 4.5 / Sonnet 4.6 / Opus 4.7 on the
exact same input. Prints accuracy + per-page predictions so the model
choice can be made empirically, not from a stale plan default.

Usage:
    python scripts/eval_roof_classifier.py
        --pdf backend/tests/fixtures/stogai/a_laida.pdf
        --labels ground_truth/a_laida_pages.yaml
        [--models haiku,sonnet,opus]
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml
from PIL import Image
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from extractor.page_classifier import (  # noqa: E402
    HAIKU_MODEL,
    OPUS_MODEL,
    SONNET_MODEL,
    Dalis,
    PageType,
    RoofTypeHint,
    classify_page,
)

MODEL_TIERS = {
    "haiku": HAIKU_MODEL,
    "sonnet": SONNET_MODEL,
    "opus": OPUS_MODEL,
}

# Rough $/1M tokens (input,output); image cost ~1600 tokens per page at
# default Anthropic image-resize. Used only to estimate run cost — not
# the bake-off metric.
_PRICES = {
    "haiku": (1.00, 5.00),
    "sonnet": (3.00, 15.00),
    "opus": (15.00, 75.00),
}


def render_page_jpeg_b64(pdf_path: Path, page_num: int, dpi: int = 150) -> str:
    """Render a single PDF page to a JPEG base64 string (for Vision API)."""
    pdf_bytes = pdf_path.read_bytes()
    pages = convert_from_bytes(
        pdf_bytes,
        dpi=dpi,
        first_page=page_num,
        last_page=page_num,
        fmt="jpeg",
    )
    if not pages:
        raise ValueError(f"page {page_num} not found in {pdf_path}")
    buf = io.BytesIO()
    pages[0].save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _est_cost_usd(n_pages: int, tier: str) -> float:
    in_per_m, out_per_m = _PRICES[tier]
    # ~1600 input tokens (mostly image) + ~150 output tokens per call.
    return n_pages * ((1600 / 1_000_000) * in_per_m + (150 / 1_000_000) * out_per_m)


def load_labels(labels_path: Path) -> dict:
    with labels_path.open() as f:
        return yaml.safe_load(f)


def run_model(pdf_path: Path, pages_to_eval: list[dict], model_id: str) -> list[dict]:
    """Run classifier on all `pages_to_eval` (each entry is a label dict)."""
    rows: list[dict] = []
    for entry in pages_to_eval:
        page_num = entry["page_num"]
        t0 = time.time()
        img_b64 = render_page_jpeg_b64(pdf_path, page_num)
        result = classify_page(
            img_b64,
            pdf_path=pdf_path,
            page_num=page_num,
            model=model_id,
        )
        rows.append({
            "page_num": page_num,
            "expected_page_type": entry.get("expected_page_type"),
            "got_page_type": result.page_type.value,
            "expected_dalis": entry.get("expected_dalis"),
            "got_dalis": result.dalis.value if result.dalis else None,
            "expected_roof_type_hint": entry.get("expected_roof_type_hint"),
            "got_roof_type_hint": result.roof_type_hint.value if result.roof_type_hint else None,
            "confidence": result.confidence,
            "elapsed_s": round(time.time() - t0, 2),
            "note": entry.get("note", ""),
        })
    return rows


def score(rows: list[dict]) -> dict:
    """Compute per-field accuracy."""
    n = len(rows)
    if n == 0:
        return {"n": 0}

    page_correct = sum(
        1 for r in rows
        if r["expected_page_type"] is not None
        and r["got_page_type"] == r["expected_page_type"]
    )
    page_evaluable = sum(1 for r in rows if r["expected_page_type"] is not None)

    dalis_correct = sum(
        1 for r in rows
        if r["expected_dalis"] is not None
        and r["got_dalis"] == r["expected_dalis"]
    )
    dalis_evaluable = sum(1 for r in rows if r["expected_dalis"] is not None)

    rth_evaluable = [r for r in rows if r["expected_roof_type_hint"] is not None]
    rth_correct = sum(
        1 for r in rth_evaluable
        if r["got_roof_type_hint"] == r["expected_roof_type_hint"]
    )

    return {
        "n": n,
        "page_type_acc": page_correct / page_evaluable if page_evaluable else None,
        "page_type_correct": f"{page_correct}/{page_evaluable}",
        "dalis_acc": dalis_correct / dalis_evaluable if dalis_evaluable else None,
        "dalis_correct": f"{dalis_correct}/{dalis_evaluable}",
        "roof_type_hint_acc": (
            rth_correct / len(rth_evaluable) if rth_evaluable else None
        ),
        "roof_type_hint_correct": f"{rth_correct}/{len(rth_evaluable)}",
    }


def print_summary(per_model: dict[str, list[dict]]) -> None:
    print()
    print("=" * 78)
    print(f"{'MODEL':<10} {'PAGE_TYPE':<15} {'DALIS':<12} {'ROOF_HINT':<12} {'EST $':<8}")
    print("-" * 78)
    for tier, rows in per_model.items():
        s = score(rows)
        cost = _est_cost_usd(len(rows), tier)
        print(
            f"{tier:<10} "
            f"{s['page_type_correct']:<15} "
            f"{s['dalis_correct']:<12} "
            f"{s['roof_type_hint_correct']:<12} "
            f"${cost:.3f}"
        )
    print("=" * 78)


def print_per_page_table(per_model: dict[str, list[dict]]) -> None:
    """Full per-page predictions for every model, side by side."""
    # Build {page_num: {model: row}}
    by_page: dict[int, dict] = defaultdict(dict)
    for model, rows in per_model.items():
        for r in rows:
            by_page[r["page_num"]][model] = r

    models = list(per_model.keys())
    print()
    print(f"PER-PAGE PREDICTIONS")
    header = ["page", "expected_pt"] + [f"{m}_pt" for m in models] + ["expected_dalis"] + [f"{m}_dalis" for m in models]
    print("  ".join(f"{c:<13}" for c in header))
    print("-" * (15 * len(header)))
    for page_num in sorted(by_page):
        row = by_page[page_num]
        first = next(iter(row.values()))
        cells = [str(page_num), str(first.get("expected_page_type", ""))]
        for m in models:
            r = row.get(m, {})
            ok = "✓" if r.get("got_page_type") == r.get("expected_page_type") else "✗"
            cells.append(f"{r.get('got_page_type', '?')}{ok}")
        cells.append(str(first.get("expected_dalis", "")))
        for m in models:
            r = row.get(m, {})
            ok = "✓" if r.get("got_dalis") == r.get("expected_dalis") else "✗"
            cells.append(f"{r.get('got_dalis', '?')}{ok}")
        print("  ".join(f"{c:<13}" for c in cells))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="Path to source PDF")
    parser.add_argument(
        "--labels", required=True,
        help="YAML file with expected per-page labels"
    )
    parser.add_argument(
        "--models", default="haiku,sonnet,opus",
        help="Comma-separated tier keys (default: all three)"
    )
    args = parser.parse_args()

    load_dotenv(ROOT / "backend" / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY missing — check backend/.env")

    pdf_path = Path(args.pdf).resolve()
    labels = load_labels(Path(args.labels))
    expected_dalis = labels.get("expected_dalis")
    expected_roof_type = labels.get("expected_roof_type")

    # Inject project-level dalis + roof_type expectations into per-page rows
    # so the scoring function has a uniform shape.
    pages_to_eval = []
    for entry in labels["pages"]:
        if entry.get("skip_in_eval"):
            continue
        e = dict(entry)
        e["expected_dalis"] = expected_dalis
        # roof_type_hint only meaningful on stogo_planas pages
        if entry.get("expected_page_type") == "stogo_planas":
            e["expected_roof_type_hint"] = entry.get(
                "expected_roof_type_hint", expected_roof_type
            )
        else:
            e["expected_roof_type_hint"] = None
        pages_to_eval.append(e)

    print(f"PDF:    {pdf_path.name}")
    print(f"Pages:  {len(pages_to_eval)} evaluated (skip_in_eval excluded)")
    print(f"Models: {args.models}")
    print()

    per_model = {}
    for tier_key in args.models.split(","):
        tier_key = tier_key.strip()
        model_id = MODEL_TIERS[tier_key]
        print(f"→ Running {tier_key} ({model_id}) ...")
        t0 = time.time()
        rows = run_model(pdf_path, pages_to_eval, model_id)
        per_model[tier_key] = rows
        print(f"  done in {time.time() - t0:.1f}s")

    print_summary(per_model)
    print_per_page_table(per_model)


if __name__ == "__main__":
    main()

"""Interactive harness for building roof ground truth (Phase 1 T8).

Usage:
    python3 scripts/build_roof_ground_truth.py \
        --pdf path/to/project.pdf \
        --out ground_truth/<slug>_roof_v2.yaml

Walks every page, renders it, asks the user to confirm/correct the
classifier output and then to enter each per-field value visible on
the page. Saves to v2 YAML on quit.
"""
from __future__ import annotations

import argparse
import base64
import io
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pdf2image import convert_from_bytes

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from extractor.page_classifier import PageType, classify_page, OPUS_MODEL  # noqa: E402


PAGE_CLASSES = [pt.value for pt in PageType]
FIELD_PROMPTS = [
    ("roof_type", "Roof type (dvislaitis/keturslaitis/...) or skip", str),
    ("axis_to_axis_length_m", "Axis length (m)", float),
    ("axis_to_axis_width_m", "Axis width (m)", float),
    ("eaves_overhang_from_axis_m", "Eaves overhang from axis (m)", float),
    ("wall_thickness_m", "Wall thickness (m)", float),
    ("slope_angles_deg", "Slope angle(s) deg (comma-separated)", "list[float]"),
    ("visible_slope_angles_deg", "Slopes labelled on plan view (csv)", "list[float]"),
    ("chimney_count", "Chimney count", int),
    ("rooflight_count", "Rooflight count", int),
    ("windows_count", "Roof window count", int),
]


def render(pdf_path: Path, page_num: int, dpi: int = 200, preview_path: Path | None = None) -> str:
    pages = convert_from_bytes(
        pdf_path.read_bytes(), dpi=dpi,
        first_page=page_num, last_page=page_num, fmt="jpeg",
    )
    img = pages[0]
    if preview_path is not None:
        img.save(preview_path, format="JPEG", quality=85)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def prompt(text: str, parser):
    raw = input(f"  {text}: ").strip()
    if raw == "" or raw.lower() == "skip":
        return None
    if parser is float:
        return float(raw.replace(",", "."))
    if parser is int:
        return int(raw)
    if parser == "list[float]":
        return [float(x.strip().replace(",", ".")) for x in raw.split(",") if x.strip()]
    return raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--preview-dir", default="/tmp/gt_previews")
    args = p.parse_args()

    load_dotenv(ROOT / "backend" / ".env")
    pdf_path = Path(args.pdf).resolve()
    out = Path(args.out)
    preview_dir = Path(args.preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = pdf_path.read_bytes()
    from pypdfium2 import PdfDocument  # already in requirements
    doc = PdfDocument(pdf_bytes)
    n = len(doc)

    pages: list[dict] = []

    print(f"\nLabeling {pdf_path.name} ({n} pages). Press 's' to skip a page, 'q' to save+quit.")
    for page_num in range(1, n + 1):
        print(f"\n=== Page {page_num}/{n} ===")
        preview = preview_dir / f"{pdf_path.stem}_p{page_num}.jpg"
        try:
            b64 = render(pdf_path, page_num, preview_path=preview)
        except Exception as e:
            print(f"  render failed: {e}; skipping")
            continue

        try:
            cls = classify_page(b64, pdf_path=pdf_path, page_num=page_num, model=OPUS_MODEL)
            print(f"  Opus says: page_type={cls.page_type.value} (conf {cls.confidence:.2f})")
            print(f"  Preview saved: {preview}")
        except Exception as e:
            cls = None
            print(f"  Opus failed: {e}")

        choice = input("  Action [accept/c=correct-class/s=skip/q=save+quit]: ").strip().lower()
        if choice == "q":
            break
        if choice == "s":
            continue
        if choice == "c":
            print(f"  Available: {', '.join(PAGE_CLASSES)}")
            page_class_str = input("  page_class: ").strip()
        else:
            page_class_str = cls.page_type.value if cls else "unknown"

        if page_class_str == "unknown":
            print("  (no fields to label for page_class=unknown)")
            continue

        fields: dict = {}
        print("  Enter values visible ON THIS PAGE (skip if not visible):")
        for key, label, parser_fn in FIELD_PROMPTS:
            v = prompt(label, parser_fn)
            if v is not None:
                fields[key] = v

        if PageType(page_class_str) == PageType.FLOOR_PLAN:
            sub_w = input("  Sub-segment widths sum (csv, or skip): ").strip()
            sub_l = input("  Sub-segment lengths sum (csv, or skip): ").strip()
            sub = {}
            if sub_w:
                sub["axis_to_axis_width_m"] = [float(x.replace(",", ".")) for x in sub_w.split(",") if x]
            if sub_l:
                sub["axis_to_axis_length_m"] = [float(x.replace(",", ".")) for x in sub_l.split(",") if x]
            if sub:
                fields["sub_dimensions_m"] = sub

        pages.append({"page_num": page_num, "page_class": page_class_str, "fields": fields})

    print("\nNow enter the AUTHORITATIVE roof_input (the answer the system should produce):")
    roof_input: dict = {}
    for key, label, parser_fn in FIELD_PROMPTS:
        if key == "visible_slope_angles_deg":
            continue
        v = prompt(label, parser_fn)
        if v is not None:
            roof_input[key] = v

    project_id = input("project_id slug (e.g. 'a_laida'): ").strip()
    out_data = {
        "project_id": project_id,
        "source_pdf": str(pdf_path.relative_to(ROOT) if pdf_path.is_relative_to(ROOT) else pdf_path),
        "roof_type": roof_input.get("roof_type", "unknown"),
        "roof_input": roof_input,
        "pages": pages,
        "roofer_samata": {
            "source": "TODO_fill_in",
            "pvm_included": False,
            "line_items": [],
            "total_eur_no_vat": 0,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(out_data, sort_keys=False, allow_unicode=True))
    print(f"\nSaved: {out}")
    print("Fill in `roofer_samata.line_items` and `total_eur_no_vat` manually before running the eval.")


if __name__ == "__main__":
    main()

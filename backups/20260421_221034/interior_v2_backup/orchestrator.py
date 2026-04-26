"""
V2.1 Orchestrator — main entry point for the 4-phase pipeline.
Accepts list of (filename, pdf_bytes) tuples.
"""
import asyncio
import base64
import io
import traceback
from typing import Any

from .page_classifier import classify_pages_with_filenames
from .phase1_analyzer import phase1_analyze_project
from .phase2_extractors import phase2_extract_all, merge_phase2_results
from .phase3_validator import phase3_validate
from .phase4_materials import calculate_phase4


def _pdf_to_pages(filename: str, pdf_bytes: bytes, dpi: int = 200) -> list[dict]:
    """Convert a single PDF to a list of page dicts with base64 images."""
    import pdfplumber
    from pdf2image import convert_from_bytes

    # Extract text per page for classifier
    text_by_page: dict[int, str] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text_by_page[i] = page.extract_text() or ""
    except Exception:
        pass

    pages = []
    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
        for idx, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            pages.append({
                "filename": filename,
                "page_idx": idx,
                "image_b64": b64,
                "text": text_by_page.get(idx, ""),
            })
    except Exception as e:
        # If pdf2image fails, return empty pages for this file
        pages = []

    return pages


async def process_interior_project_v2_1(
    pdf_files: list[tuple[str, bytes]],
) -> dict[str, Any]:
    """
    V2.1 full pipeline.

    Args:
        pdf_files: list of (filename, pdf_bytes) tuples

    Returns:
        {
            status: "ok" | "error",
            project_context: phase1 result,
            raw_extractions: phase2 merged,
            validated_quantities: phase3 validated items,
            warnings: list of validation warnings,
            confidence: "high" | "medium" | "low",
            scope_type: confirmed scope,
            materials: phase4 material quantities,
            line_items: phase4 line items,
            total_darbo_kaina_eur: number,
            total_su_pvm_eur: number,
        }
    """
    if not pdf_files:
        return {"status": "error", "error": "No PDF files provided"}

    # Convert all PDFs to page images
    all_pages: list[dict] = []
    for filename, pdf_bytes in pdf_files:
        pages = _pdf_to_pages(filename, pdf_bytes, dpi=200)
        all_pages.extend(pages)

    if not all_pages:
        return {"status": "error", "error": "Failed to extract pages from PDFs"}

    # Phase 1 — classify project
    try:
        phase1 = phase1_analyze_project(all_pages)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Phase 1 failed: {e}",
            "traceback": traceback.format_exc(),
        }

    # Check Phase 1 confidence
    confidence = phase1.get("confidence", 0)
    if confidence < 0.5:
        return {
            "status": "error",
            "error": "Phase 1: could not extract room table (confidence < 0.5)",
            "phase1": phase1,
        }

    # Classify pages by type
    classified_pages = classify_pages_with_filenames(all_pages)

    # Phase 2 — parallel extraction
    try:
        phase2_results = await phase2_extract_all(classified_pages, phase1)
        phase2_merged = merge_phase2_results(phase2_results)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Phase 2 failed: {e}",
            "phase1": phase1,
            "traceback": traceback.format_exc(),
        }

    # Phase 3 — validate
    try:
        phase3 = phase3_validate(phase2_merged, phase1)
    except Exception as e:
        phase3 = {
            "validated_items": {},
            "warnings": [{"rule_id": "PHASE3_EXCEPTION", "severity": "warning",
                          "description": str(e), "actual_value": None, "expected_range": None}],
            "confidence_level": "low",
            "scope_confirmed": phase1.get("scope_type", "full_project"),
            "similar_projects": [],
        }

    # Phase 4 — deterministic materials
    project_class = phase1.get("sudetingumo_klase", "medium_house")
    try:
        phase4 = calculate_phase4(phase2_merged, project_class)
    except Exception as e:
        phase4 = {
            "materials": {},
            "line_items": [],
            "total_darbo_kaina_eur": 0,
            "total_su_pvm_eur": 0,
            "error": str(e),
        }

    return {
        "status": "ok",
        "project_context": phase1,
        "raw_extractions": phase2_merged,
        "validated_quantities": phase3.get("validated_items", {}),
        "warnings": phase3.get("warnings", []),
        "confidence": phase3.get("confidence_level", "low"),
        "scope_type": phase3.get("scope_confirmed", phase1.get("scope_type", "full_project")),
        "similar_projects": phase3.get("similar_projects", []),
        "materials": phase4.get("materials", {}),
        "line_items": phase4.get("line_items", []),
        "total_darbo_kaina_eur": phase4.get("total_darbo_kaina_eur", 0),
        "total_su_pvm_eur": phase4.get("total_su_pvm_eur", 0),
    }

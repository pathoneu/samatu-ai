"""
V2 Vision pipeline orchestrator.
3-phase architecture: Phase 1 (project analysis) → Phase 2 (parallel extractors) → Phase 3 (validation).
Exposed as /extract-interior-v2 endpoint.
"""
import asyncio
import base64
import io
import json
import pathlib
from typing import Any

from phase1_analyzer import phase1_from_pdf_bytes
from phase2_extractors import phase2_extract_all, merge_phase2_results
from phase3_validator import phase3_validate
from materials_calculator import calculate_materials
from vision_tools import TOOL_FOR_PAGE_TYPE

_TRAINING_PATH = pathlib.Path(__file__).parent / "training_dataset.json"
_training_cache: dict | None = None


def _load_training() -> dict:
    global _training_cache
    if _training_cache is None:
        _training_cache = json.loads(_TRAINING_PATH.read_text(encoding="utf-8"))
    return _training_cache


def _pdf_to_b64_pages(pdf_bytes: bytes, dpi: int = 200) -> list[tuple[int, str]]:
    """Convert PDF pages to (page_number, base64_jpeg) tuples."""
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    result = []
    for i, img in enumerate(images):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        result.append((i + 1, b64))
    return result


def _classify_pages(pdf_bytes: bytes) -> dict[int, str]:
    """Reuse V1 text-based page classification from main module."""
    import pdfplumber
    import re

    # Minimal page type patterns (mirrors main.py)
    PAGE_PATTERNS: dict[str, re.Pattern] = {
        "pertvarų": re.compile(r"pertvar|baldų\s+išdėstymo|pertvaru|furniture\s+plan", re.I),
        "išklotinė": re.compile(r"išklotinė|isklotine|sienu\s+isklotine|wall\s+elevation", re.I),
        "lubų": re.compile(r"lubų\s+planas|lubu\s+planas|ceiling\s+plan", re.I),
        "grindų": re.compile(r"grindų\s+planas|grindu\s+planas|floor\s+finish", re.I),
        "santechnikos": re.compile(r"santechnikos|vandentiekio|kanalizaci|plumbing", re.I),
        "rozecių": re.compile(r"rozečių|rozeciu|elektros\s+instal|outlet\s+plan", re.I),
        "apšvietimo": re.compile(r"apšvietimo|apsvietime|šviestuv|lighting\s+plan", re.I),
    }

    page_types: dict[int, str] = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pno = i + 1
            matched = "kita"
            for pt, pat in PAGE_PATTERNS.items():
                if pat.search(text):
                    matched = pt
                    break
            page_types[pno] = matched
    return page_types


async def process_interior_project_v2(pdf_bytes: bytes) -> dict[str, Any]:
    """
    Full V2 pipeline.
    Returns validated quantities, warnings, confidence, materials.
    """
    # Convert PDF to images
    try:
        pages = _pdf_to_b64_pages(pdf_bytes, dpi=200)
    except Exception as exc:
        return {"status": "error", "error": f"PDF konversija nepavyko: {exc}"}

    if not pages:
        return {"status": "error", "error": "PDF neturi puslapių"}

    all_b64 = [b64 for _, b64 in pages]

    # ── PHASE 1: Project context (one call, first 20 pages at low-res) ─────
    try:
        phase1 = phase1_from_pdf_bytes(pdf_bytes, max_pages=20)
    except Exception as exc:
        return {"status": "error", "error": f"Phase 1 nepavyko: {exc}"}

    if phase1.get("confidence", 1.0) < 0.5:
        return {
            "status": "low_confidence",
            "error": "Nerastas patalpų sąrašas (PATALPŲ EKSPLIKACIJA)",
            "phase1": phase1,
        }

    # ── PHASE 2: Classify pages and run specialized extractors ──────────────
    try:
        page_types = _classify_pages(pdf_bytes)
    except Exception:
        page_types = {}

    pages_with_types: list[tuple[int, str, str]] = [
        (pno, page_types.get(pno, "kita"), b64)
        for pno, b64 in pages
        if page_types.get(pno, "kita") in TOOL_FOR_PAGE_TYPE
    ]

    try:
        phase2_grouped = await phase2_extract_all(pages_with_types, phase1)
    except Exception as exc:
        return {"status": "error", "error": f"Phase 2 nepavyko: {exc}", "phase1": phase1}

    merged = merge_phase2_results(phase2_grouped, phase1)

    # Ensure mandatory fields for Phase 3
    if "dazomas_plotas_m2" not in merged:
        merged["dazomas_plotas_m2"] = merged.get("sienos_dazomas_m2_is_iskl", 0)
    if "lubu_plotas_m2" not in merged:
        merged["lubu_plotas_m2"] = merged.get("gkp_lubu_standartinis_m2", 0) or phase1.get("bendras_plotas_m2", 0)
    if "gkp_lubu_m2" not in merged:
        merged["gkp_lubu_m2"] = merged.get("gkp_lubu_standartinis_m2", 0)

    # ── PHASE 3: Validation ─────────────────────────────────────────────────
    try:
        phase3 = phase3_validate(merged, phase1)
    except Exception as exc:
        # Phase 3 failure is non-fatal — return Phase 2 results with warning
        phase3 = {
            "validated_quantities": merged,
            "warnings": [{"rule_id": "phase3_error", "severity": "warning",
                          "description": str(exc), "actual_value": 0, "expected_range": "n/a"}],
            "confidence_level": "low",
            "similar_projects": [],
        }

    validated = phase3.get("validated_quantities", merged)

    # ── MATERIALS: deterministic calculation ────────────────────────────────
    training = _load_training()
    try:
        materials = calculate_materials(validated, training)
    except Exception:
        materials = {}

    return {
        "status": "ok",
        "project_context": {
            "patalpos": phase1.get("patalpos", []),
            "bendras_plotas_m2": phase1.get("bendras_plotas_m2"),
            "garazo_plotas_m2": phase1.get("garazo_plotas_m2"),
            "lubu_aukstis_m": phase1.get("lubu_aukstis_m", 2.8),
            "sudetingumo_klase": phase1.get("sudetingumo_klase"),
            "features": phase1.get("features", {}),
            "confidence": phase1.get("confidence"),
        },
        "raw_extractions": phase2_grouped,
        "merged_quantities": merged,
        "validated_quantities": validated,
        "warnings": phase3.get("warnings", []),
        "confidence": phase3.get("confidence_level", "low"),
        "similar_projects": phase3.get("similar_projects", []),
        "materials": materials,
    }

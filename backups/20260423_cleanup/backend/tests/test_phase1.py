"""
Phase 1 accuracy test.
Run from backend/ directory: python -m pytest tests/test_phase1.py -v -s
"""
import json
import pathlib
import sys
import os

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import pytest

BACKEND = pathlib.Path(__file__).parent.parent
TEST_PDFS = BACKEND / "test_pdfs"
TRAINING = json.loads((BACKEND / "training_dataset.json").read_text())

# Map project IDs to available PDF files
PDF_MAP = {
    "P1": TEST_PDFS / "1_BD.pdf",
    "P3": TEST_PDFS / "03_SA.pdf",
}


def pdf_to_b64_pages(pdf_path, dpi=200, max_pages=40):
    import base64
    import io
    from pdf2image import convert_from_path
    images = convert_from_path(str(pdf_path), dpi=dpi, fmt="jpeg")
    result = []
    for i, img in enumerate(images[:max_pages]):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        result.append(base64.b64encode(buf.getvalue()).decode())
    return result


def get_expected(project_id: str) -> dict:
    for p in TRAINING["projects"]:
        if p["id"] == project_id:
            return p
    raise KeyError(f"Project {project_id} not in training_dataset.json")


@pytest.mark.parametrize("project_id,pdf_path", [
    (pid, path) for pid, path in PDF_MAP.items() if path.exists()
])
def test_phase1_rooms_extracted(project_id, pdf_path):
    from phase1_analyzer import phase1_from_pdf_bytes

    pdf_bytes = pdf_path.read_bytes()
    result = phase1_from_pdf_bytes(pdf_bytes, max_pages=20)

    expected = get_expected(project_id)
    expected_rooms = len(expected.get("patalpu_eksplikacija", []))
    expected_area = expected["plotai"]["bendras_be_garazo_m2"]

    extracted_rooms = len(result.get("patalpos", []))
    extracted_area = result.get("bendras_plotas_m2", 0) or 0

    print(f"\n=== {project_id} ===")
    print(f"Rooms: {extracted_rooms} / expected {expected_rooms}")
    print(f"Area: {extracted_area} m² / expected {expected_area} m²")
    print(f"Class: {result.get('sudetingumo_klase')}")
    print(f"Confidence: {result.get('confidence')}")
    if result.get("patalpos"):
        for r in result["patalpos"][:5]:
            print(f"  {r['nr']} {r['pavadinimas']} {r['plotas_m2']}m²")

    # Rooms within 20% of expected
    assert extracted_rooms >= max(1, expected_rooms * 0.8), (
        f"{project_id}: got {extracted_rooms} rooms, expected >= {int(expected_rooms * 0.8)}"
    )

    # Area within 5%
    area_error = abs(extracted_area - expected_area) / expected_area if expected_area else 1
    assert area_error <= 0.05, (
        f"{project_id}: area {extracted_area:.1f} vs expected {expected_area:.1f} "
        f"(error {area_error*100:.1f}%)"
    )


@pytest.mark.parametrize("project_id,pdf_path", [
    (pid, path) for pid, path in PDF_MAP.items() if path.exists()
])
def test_phase1_confidence_high(project_id, pdf_path):
    from phase1_analyzer import phase1_from_pdf_bytes

    result = phase1_from_pdf_bytes(pdf_path.read_bytes(), max_pages=20)

    confidence = result.get("confidence", 0)
    assert confidence >= 0.5, (
        f"{project_id}: confidence {confidence} too low — room table probably not found"
    )

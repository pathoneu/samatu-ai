"""
V2.1 accuracy test against training_dataset_v2.json ground truth.

CRITICAL: Uses accuracy_test_fields whitelist per project.
P3 and P4 are partial — only whitelisted fields are tested.
"""
import asyncio
import json
import pathlib
import sys

import pytest

# Add backend to path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from interior_v2.orchestrator import process_interior_project_v2_1
from interior_v2.scope_method import load_dataset

TRAINING_DATA_DIR = pathlib.Path(__file__).parent.parent.parent.parent / "training-data"
DATASET = load_dataset()


def load_project_pdfs(project_id: str) -> list[tuple[str, bytes]]:
    """Load all PDF files for a project. Returns list of (filename, bytes)."""
    project_dir = TRAINING_DATA_DIR / f"projektas_{project_id[1:]}"
    if not project_dir.exists():
        pytest.skip(f"Training data directory not found: {project_dir}")

    # For P5 — load all breziniai files (9 files)
    pdf_files = []
    for pdf_path in sorted(project_dir.glob("*.pdf")):
        name = pdf_path.name.lower()
        # Skip pasiulymas (proposal PDF, not drawings)
        if "pasiulymas" in name:
            continue
        pdf_files.append((pdf_path.name, pdf_path.read_bytes()))

    if not pdf_files:
        pytest.skip(f"No drawing PDFs found for {project_id} in {project_dir}")

    return pdf_files


def extract_field_from_result(result: dict, field: str) -> float:
    """
    Map accuracy_test_fields names to values in pipeline result.
    Checks validated_quantities first, then raw_extractions.
    """
    validated = result.get("validated_quantities", {})
    raw = result.get("raw_extractions", {})

    # Direct mapping from field name to kategorija
    FIELD_TO_KATEGORIJA: dict[str, str | list[str]] = {
        "dazymo_plotas_standart_m2": "standart_sienos_lubos",
        "dazymo_plotas_total_m2": ["standart_sienos_lubos", "standart_sienos_lubos_virs_3m"],
        "dazymo_plotas_virs_3m_m2": "standart_sienos_lubos_virs_3m",
        "papildomas_sienu_glaistymas_m2": "papildomas_sienu_glaistymas",
        "kampai_m": "kampai_montavimas",
        "angokrasciai_gkp_m": "angokrasciai_apdirbimas_gkp",
        "angokrasciai_dazymo_m": "duru_angos_beapvadines_paruosimas",
        "gkp_lubu_standart_m2": "lubos_standart_aukstis",
        "gkp_lubu_virs_3m_m2": "lubos_virs_3m",
        "gkp_lubu_total_m2": ["lubos_standart_aukstis", "lubos_virs_3m"],
        "gkp_pertvara_m2": "pertvara_dviguba",
        "moldingai_bm": "moldingu_dazymas",
        "stiklo_audinio": "stiklo_audinio_klijavimas",
        "pvc_grindys_m2": "pvc_grindys",
        "plyteles_1200x1200_m2": ["1200x1200x6_sienos_grindys", "1200x1200x6_nisos_angokrasciai"],
        "plyteles_1200x600_m2": ["1200x600x9_sienos_grindys", "1200x600x9_nisos_angokrasciai"],
        "plyteles_didziaformates_m2": ["didziaformates_sienos_grindys", "didziaformates_nisos_angokrasciai"],
        "parketlentes_m2": ["parketlentes_klijavimas_45_eglute", "parketlentes_klasikinis"],
        "dazymo_plotas_premium_benjamin_moore_m2": [
            "premium_benjamin_moore_lubos",
            "premium_benjamin_moore_sienos_lubos",
        ],
        "dazymo_plotas_premium_supreme_ultimate_m2": "premium_supreme_ultimate_sienos_lubos",
        "stiklo_audinio_m2": "stiklo_audinio_klijavimas",
        "plyteles_standart_m2": ["standartinio_formato_sienos_grindys", "standartinio_formato_nisos_angokrasciai"],
        "plyteles_nisos_bm": "standartinio_formato_nisos_angokrasciai",
        "isliginamasis_m2": "isliginamasis_sluoksnis",
    }

    # Special fields that need aggregation
    if field == "plyteles_total_m2":
        tile_keys = [
            "standartinio_formato_sienos_grindys",
            "1200x1200x6_sienos_grindys",
            "1200x600x9_sienos_grindys",
            "didziaformates_sienos_grindys",
            "iki_120x60_sienos_grindys",
        ]
        return sum(_get_item_total(raw, k) + validated.get(k, 0) for k in tile_keys)

    if field == "grindjuostes_total_m":
        floor_keys = [
            "grindjuostes_i_siena_ileistos",
            "grindjuostes_paprastos_medines",
            "grindjuostes_aliuminio",
        ]
        return sum(_get_item_total(raw, k) + validated.get(k, 0) for k in floor_keys)

    if field == "rozetes_jungikliai_vnt":
        return _get_item_total(raw, "rozetes_jungiklio_komutavimas") + \
               validated.get("rozetes_jungiklio_komutavimas", 0)

    if field == "rekuperatoriaus_montavimas_vnt":
        return _get_item_total(raw, "rekuperatoriaus_montavimas") + \
               validated.get("rekuperatoriaus_montavimas", 0)

    if field == "kondicionieriaus_irengimas_vnt":
        return _get_item_total(raw, "kondicionieriaus_irengimas") + \
               validated.get("kondicionieriaus_irengimas", 0)

    if field == "stoglangiu_vnt":
        return _get_item_total(raw, "stoglangiu_apdirbimas") + \
               validated.get("stoglangiu_apdirbimas", 0)

    # Generic field mapping
    kategorija_or_list = FIELD_TO_KATEGORIJA.get(field)
    if kategorija_or_list is None:
        return 0.0

    if isinstance(kategorija_or_list, list):
        total = 0.0
        for k in kategorija_or_list:
            total += _get_item_total(raw, k) + validated.get(k, 0)
        return total
    else:
        k = kategorija_or_list
        return _get_item_total(raw, k) + validated.get(k, 0)


def _get_item_total(raw: dict, kategorija: str) -> float:
    """Sum kiekis for a kategorija across all item arrays in raw_extractions."""
    total = 0.0
    for section_key in ["paint_items", "gkp_items", "tiles_items", "floor_items",
                        "plumbing_items", "electrical_items", "ventilation_items",
                        "special_works_items"]:
        for item in raw.get(section_key, []):
            if item.get("kategorija") == kategorija:
                total += float(item.get("kiekis", 0))
    return total


def get_all_projects():
    return DATASET.get("projects", [])


@pytest.mark.parametrize("project", get_all_projects(), ids=lambda p: p["id"])
@pytest.mark.asyncio
async def test_v2_accuracy_per_project(project):
    """
    Test V2.1 pipeline accuracy per project.
    Uses accuracy_test_fields whitelist — never tests out-of-scope fields.
    """
    pid = project["id"]
    scope_type = project.get("scope_type", "full_project")
    test_fields = project.get("accuracy_test_fields", [])
    tolerance = project.get("accuracy_test_tolerance", 0.15)
    faktiniai = project.get("faktiniai_kiekiai_suvestinis", {})

    if not test_fields:
        pytest.skip(f"{pid}: no accuracy_test_fields defined")

    # Check if we have P5 multi-file PDFs
    pdf_files = load_project_pdfs(pid)

    # Run pipeline
    result = await process_interior_project_v2_1(pdf_files)

    assert result["status"] == "ok", (
        f"{pid}: pipeline failed with error: {result.get('error', 'unknown')}"
    )

    failed_fields = []
    passed_fields = []

    for field in test_fields:
        expected = faktiniai.get(field)
        if expected is None or expected == 0:
            continue

        actual = extract_field_from_result(result, field)
        error_pct = abs(actual - expected) / expected

        if error_pct > tolerance:
            failed_fields.append({
                "field": field,
                "expected": expected,
                "actual": round(actual, 2),
                "error_pct": round(error_pct * 100, 1),
                "tolerance_pct": round(tolerance * 100, 1),
            })
        else:
            passed_fields.append(field)

    # Report
    print(f"\n{pid} ({scope_type}) — {len(passed_fields)}/{len(test_fields)} fields passed")
    for f in passed_fields:
        expected = faktiniai.get(f, "?")
        actual = extract_field_from_result(result, f)
        print(f"  ✓ {f}: {round(actual, 2)} (expected {expected})")
    for f in failed_fields:
        print(f"  ✗ {f['field']}: actual={f['actual']}, expected={f['expected']}, "
              f"error={f['error_pct']}% (tolerance {f['tolerance_pct']}%)")

    assert not failed_fields, (
        f"{pid}: {len(failed_fields)} field(s) outside tolerance:\n"
        + "\n".join(
            f"  {f['field']}: actual={f['actual']}, expected={f['expected']}, "
            f"error={f['error_pct']}%"
            for f in failed_fields
        )
    )


if __name__ == "__main__":
    # Manual run for quick testing
    import asyncio

    async def run_one(pid: str):
        project = next(p for p in get_all_projects() if p["id"] == pid)
        pdf_files = load_project_pdfs(pid)
        result = await process_interior_project_v2_1(pdf_files)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    pid = sys.argv[1] if len(sys.argv) > 1 else "P5"
    asyncio.run(run_one(pid))

"""
Loads and caches training_dataset_v2.json.
Provides helpers for accuracy_test_fields, aggregated_ratios, material coefficients.
"""
import json
import pathlib

_DATASET_PATH = pathlib.Path(__file__).parent.parent / "training_dataset_v2.json"
_cache: dict | None = None


def load_dataset() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))
    return _cache


def get_ratios_for_class(klase: str) -> dict:
    ds = load_dataset()
    return ds.get("aggregated_ratios_by_class", {}).get(klase, {})


def get_material_coefs() -> dict:
    return load_dataset().get("material_conversion_coefficients", {})


def get_sanity_rules() -> list:
    return load_dataset().get("sanity_check_rules", [])


def get_project_by_id(pid: str) -> dict | None:
    ds = load_dataset()
    for p in ds.get("projects", []):
        if p["id"] == pid:
            return p
    return None


def get_accuracy_test_fields(pid: str) -> list[str]:
    p = get_project_by_id(pid)
    return p.get("accuracy_test_fields", []) if p else []


def get_faktiniai_kiekiai(pid: str) -> dict:
    """Returns the faktiniai_kiekiai_suvestinis dict for a project."""
    p = get_project_by_id(pid)
    return p.get("faktiniai_kiekiai_suvestinis", {}) if p else {}


def get_scope_type(pid: str) -> str:
    p = get_project_by_id(pid)
    return p.get("scope_type", "full_project") if p else "full_project"


def parse_lt_number(s) -> float:
    """Parse Lithuanian decimal notation (comma) or standard (dot)."""
    if isinstance(s, (int, float)):
        return float(s)
    return float(str(s).replace(",", ".").strip())


def get_schema_enums() -> dict:
    return load_dataset().get("_schema_enums", {})

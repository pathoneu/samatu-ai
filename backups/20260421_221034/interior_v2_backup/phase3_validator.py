"""
V2.1 Phase 3 — Validator.
Improvements vs V2.0:
- Low-confidence single-example class handling
- Partial project scope awareness
- Uses training_dataset_v2.json ratios
"""
import json
import time
from typing import Any

from anthropic import Anthropic

from .tools import VALIDATOR_TOOL
from .prompts import PHASE3_VALIDATOR_PROMPT
from .scope_method import get_ratios_for_class, get_sanity_rules

VISION_MODEL = "claude-opus-4-7"

_SINGLE_EXAMPLE_CLASSES = {"small_apartment", "medium_house", "premium"}

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _flatten_items_for_validator(phase2_merged: dict) -> dict[str, Any]:
    """
    Convert Phase 2 merged (items arrays) into a flat dict for the validator prompt.
    Keys = kategorija, values = total kiekis.
    """
    flat: dict[str, float] = {}

    for section_key in ["paint_items", "gkp_items", "floor_items", "plumbing_items",
                        "electrical_items", "tiles_items", "ventilation_items",
                        "special_works_items", "site_overhead_items"]:
        for item in phase2_merged.get(section_key, []):
            k = item.get("kategorija", "")
            v = item.get("kiekis", 0)
            if k:
                flat[k] = flat.get(k, 0) + float(v)

    # Partition data
    pd = phase2_merged.get("partition_data")
    if pd:
        flat["visu_kampu_vnt"] = pd.get("visu_kampu_vnt", 0)
        flat["duru_skaicius"] = len(pd.get("doors", []))
        flat["langu_skaicius"] = len(pd.get("langai", []))

    return flat


def phase3_validate(
    phase2_merged: dict,
    phase1: dict,
) -> dict[str, Any]:
    """
    Validate Phase 2 results against training ratios.
    Returns: validated_items, warnings, confidence_level, scope_confirmed, similar_projects
    """
    client = _get_client()
    project_class = phase1.get("sudetingumo_klase", "medium_house")
    scope_type = phase1.get("scope_type", "full_project")

    ratios = get_ratios_for_class(project_class)
    flat_items = _flatten_items_for_validator(phase2_merged)

    prompt = PHASE3_VALIDATOR_PROMPT.format(
        phase1_json=json.dumps(phase1, indent=2, ensure_ascii=False),
        phase2_json=json.dumps(flat_items, indent=2, ensure_ascii=False),
        ratios_json=json.dumps(ratios, indent=2, ensure_ascii=False),
        project_class=project_class,
        scope_type=scope_type,
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                tools=[VALIDATOR_TOOL],
                tool_choice={"type": "tool", "name": "validate_and_finalize_v2"},
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    result = dict(block.input)
                    # Always add single-example warning for applicable classes
                    if project_class in _SINGLE_EXAMPLE_CLASSES:
                        result.setdefault("warnings", []).append({
                            "rule_id": "SINGLE_EXAMPLE_CLASS",
                            "severity": "info",
                            "description": (
                                f"Klasė '{project_class}' turi tik 1 training example. "
                                "Ratios yra spėjimai, ne statistinis pagrindas."
                            ),
                            "actual_value": None,
                            "expected_range": None,
                        })
                    # Add partial project warning
                    if scope_type != "full_project":
                        result.setdefault("warnings", []).append({
                            "rule_id": "PARTIAL_PROJECT_LIMITED_VALIDATION",
                            "severity": "info",
                            "description": (
                                f"Dalinis projektas ({scope_type}). Validacija apribota tik "
                                "scope kategorijoms."
                            ),
                            "actual_value": None,
                            "expected_range": None,
                        })
                    # Attach original flat items if validator didn't change them
                    if not result.get("validated_items"):
                        result["validated_items"] = flat_items
                    return result
            raise ValueError("Phase 3: validator tool not called")
        except Exception:
            if attempt == 2:
                # Return pass-through result with low confidence
                return {
                    "validated_items": flat_items,
                    "warnings": [{
                        "rule_id": "PHASE3_FAILED",
                        "severity": "warning",
                        "description": "Phase 3 validator failed to run, returning Phase 2 data unvalidated",
                        "actual_value": None,
                        "expected_range": None,
                    }],
                    "confidence_level": "low",
                    "scope_confirmed": scope_type,
                    "similar_projects": [],
                }
            time.sleep(2 ** attempt)

    raise ValueError("Phase 3: all retries exhausted")

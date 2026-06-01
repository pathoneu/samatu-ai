"""Validate every truth.json against the registry.

Checks performed:
  • registry.yaml parseable and lists ≥1 project
  • every listed truth_path exists, parses as JSON, and matches the
    documented top-level schema (project_id, source, gt_totals, …)
  • every gt_totals entry has {value, confidence, source}
  • every value is a finite number ≥ 0 OR a small list of finite numbers
  • cross-field consistency: ceiling_paint ≤ dazymo_combined when both
    present; walls_paint ≤ dazymo_combined when both present
  • blocked_for_vision_extraction projects flagged but not failed
    (they're valid totals truth; just gated from Vision extraction)

Exit code 0 if every project passes; non-zero if any project fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TOP_KEYS = {"$schema_version", "project_id", "name", "source",
                     "gt_totals"}
REQUIRED_SOURCE_KEYS = {"samata_pdf", "contractor", "date_collected"}
REQUIRED_METRIC_KEYS = {"value", "confidence", "source"}
VALID_CONFIDENCES = {"green", "yellow", "incomplete", "partial", "red"}

# When both members of a pair appear in gt_totals, the first ≤ second
# must hold (within tolerance) for the totals to be internally
# consistent. Tolerance accounts for rounding in the contractor's PDF.
TOLERANCE_M2 = 1.0
CONSISTENCY_PAIRS = [
    ("walls_paint_total_m2", "dazymo_walls_plus_ceilings_combined_m2"),
    ("ceiling_paint_total_m2", "dazymo_walls_plus_ceilings_combined_m2"),
    ("dazymo_iki_3m_m2", "dazymo_walls_plus_ceilings_combined_m2"),
    ("dazymo_virs_3m_m2", "dazymo_walls_plus_ceilings_combined_m2"),
    ("plyteles_grindys_total_m2", "floor_total_m2"),
]


class V:
    """Single project's validation result."""
    def __init__(self, slug: str):
        self.slug = slug
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def _validate_metric(v: V, metric: str, body) -> float | None:
    if not isinstance(body, dict):
        v.fail(f"gt_totals.{metric} must be an object")
        return None
    missing = REQUIRED_METRIC_KEYS - body.keys()
    if missing:
        v.fail(f"gt_totals.{metric} missing keys: {sorted(missing)}")
        return None
    if body["confidence"] not in VALID_CONFIDENCES:
        v.fail(f"gt_totals.{metric} confidence={body['confidence']!r} "
               f"not in {sorted(VALID_CONFIDENCES)}")
    val = body["value"]
    if isinstance(val, list):
        for i, item in enumerate(val):
            if not isinstance(item, (int, float)) or item < 0:
                v.fail(f"gt_totals.{metric}.value[{i}]={item!r} must be ≥0 number")
        return sum(float(x) for x in val if isinstance(x, (int, float)))
    if val is None:
        v.warn(f"gt_totals.{metric}.value is null")
        return None
    if not isinstance(val, (int, float)):
        v.fail(f"gt_totals.{metric}.value={val!r} must be a number or list")
        return None
    if val < 0:
        v.fail(f"gt_totals.{metric}.value={val} must be ≥0")
    return float(val)


def _validate_one(slug: str, truth_path: Path,
                  registry_entry: dict) -> V:
    v = V(slug)
    if not truth_path.exists():
        v.fail(f"truth_path not found: {truth_path}")
        return v
    try:
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        v.fail(f"truth_path not valid JSON: {e}")
        return v

    missing = REQUIRED_TOP_KEYS - truth.keys()
    if missing:
        v.fail(f"top-level missing: {sorted(missing)}")

    src = truth.get("source") or {}
    if not isinstance(src, dict):
        v.fail("source must be an object")
    else:
        missing_src = REQUIRED_SOURCE_KEYS - src.keys()
        if missing_src:
            v.fail(f"source missing keys: {sorted(missing_src)}")

    if truth.get("project_id") != slug:
        v.fail(f"project_id={truth.get('project_id')!r} ≠ registry slug={slug!r}")

    totals = truth.get("gt_totals") or {}
    if not isinstance(totals, dict):
        v.fail("gt_totals must be an object")
        return v
    if not totals:
        v.fail("gt_totals is empty — no contractor numbers extracted")
        return v

    # Validate each metric and collect numeric values for consistency checks.
    metric_values: dict[str, float | None] = {}
    for metric, body in totals.items():
        metric_values[metric] = _validate_metric(v, metric, body)

    # Cross-field consistency
    for smaller, larger in CONSISTENCY_PAIRS:
        sv, lv = metric_values.get(smaller), metric_values.get(larger)
        if sv is not None and lv is not None and sv > lv + TOLERANCE_M2:
            v.fail(f"consistency: {smaller}={sv} > {larger}={lv} + {TOLERANCE_M2}m² tol")

    # Sanity: gt_dimensions either empty list or list of objects
    gd = truth.get("gt_dimensions")
    if gd is not None and not isinstance(gd, list):
        v.fail("gt_dimensions must be a list or absent")

    # blocked_for_vision_extraction is informational, not a failure
    if truth.get("blocked_for_vision_extraction"):
        v.warn("blocked_for_vision_extraction=true — Vision pipeline will skip until unblocked")
    if registry_entry.get("blocked_for_vision_extraction") and not truth.get("blocked_for_vision_extraction"):
        v.warn("registry marks blocked_for_vision_extraction=true but truth.json does not — keep them in sync")

    return v


def main() -> int:
    reg_path = REPO_ROOT / "ground_truth" / "registry.yaml"
    if not reg_path.exists():
        print(f"FAIL: {reg_path} not found", file=sys.stderr)
        return 2
    reg = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
    projects = reg.get("projects") or []
    if not projects:
        print("FAIL: registry has no projects", file=sys.stderr)
        return 2

    results: list[V] = []
    for entry in projects:
        slug = entry["slug"]
        truth_path = REPO_ROOT / entry["truth_path"]
        results.append(_validate_one(slug, truth_path, entry))

    width = max(len(r.slug) for r in results)
    print(f"\n  Validation report — {len(results)} project(s)\n")
    for r in results:
        status = "  ✓ OK   " if r.ok else "  ✗ FAIL "
        print(f"{status} {r.slug:<{width}}", end="")
        if r.errors:
            print()
            for e in r.errors:
                print(f"           ERROR: {e}")
        if r.warnings:
            if not r.errors:
                print()
            for w in r.warnings:
                print(f"           warn:  {w}")
        if not r.errors and not r.warnings:
            print("  (no issues)")
    print()

    failing = [r for r in results if not r.ok]
    if failing:
        print(f"  ✗ {len(failing)}/{len(results)} project(s) failed validation.")
        return 1
    print(f"  ✓ all {len(results)} project(s) passed validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

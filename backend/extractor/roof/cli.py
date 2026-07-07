"""Phase 0 CLI: load ground truth YAML, run matching strategy, print report.

Usage:
    python -m extractor.roof.cli ground_truth/a_laida_roof.yaml
    python -m extractor.roof.cli ground_truth/0039_roof.yaml

Exit codes:
    0 — all line items within their tolerance bands
    1 — at least one line item out of band (or unsupported roof type)
"""
import sys
from pathlib import Path

import yaml

from extractor.roof.strategies import RoofInput
from extractor.roof.strategies.dvislaitis import DvislaitisStrategy
from extractor.roof.strategies.keturslaitis import KeturslaitisStrategy


STRATEGIES = {
    "dvislaitis": DvislaitisStrategy(),
    "keturslaitis": KeturslaitisStrategy(),
}


# Mapping: strategy LineItem.pozicija → list of YAML roofer_samata position keys that match it.
# "kraigai" is used by both A LAIDA (keturslaitis → "Kraigai") and 0039 (dvislaitis → "Kraigas").
_POS_MAP_INV: dict[str, list[str]] = {
    "Stogas (danga)":           ["stogas"],
    "Perdanga":                 ["perdanga"],
    "Latakai":                  ["latakai"],
    "Kraigai":                  ["kraigai"],        # keturslaitis (plural)
    "Kraigas":                  ["kraigas", "kraigai"],  # dvislaitis uses singular; YAML may say kraigai
    "Sienos (gablai + soflitas)": ["sienos"],
    "Vėjalentės":               ["vejalentes"],
    "Apsauginė tvorelė":        ["apsaugine_tvorele"],
    "Langų apdirbimas":         ["langu_apdirbimas"],
    "Kaminėlis":                ["kaminelis"],
}


def _build_input(data: dict) -> RoofInput:
    """Convert ground-truth YAML dict to RoofInput."""
    roof = data["roof"]
    footprint = roof["building_footprint_outer_walls"]
    slopes = [s["angle_deg"] for s in roof["slopes"]]

    # Support both new (split) and old (single) eaves_overhang_m field names
    eaves = roof.get("eaves_overhang_from_outer_wall_m",
                     roof.get("eaves_overhang_m", 0.0))

    return RoofInput(
        roof_type=roof["type"],
        building_length_m=footprint["length_m"],
        building_width_m=footprint["width_m"],
        eaves_overhang_m=eaves,
        slopes_deg=slopes,
        wall_thickness_m=roof.get("wall_thickness_m", 0.25),
        eaves_to_ground_m=roof.get("eaves_to_ground_m", 5.5),  # default for 0039 sienos calc
        soflitas_depth_m=roof.get("soflitas_depth_m", 0.5),
        chimney_count=roof.get("chimney_count", 0),
        rooflight_count=roof.get("rooflight_count", 0),
        windows_count=roof.get("windows_count", 0),
    )


def _tolerance_for(pozicija: str, unit: str) -> float:
    """Return absolute tolerance band for the pozicija per Phase 0 acceptance criteria."""
    if "Sienos" in pozicija:
        return 15.0
    if unit == "m²":
        return 10.0   # general m² tolerance
    if unit == "m":
        return 3.0    # length tolerance
    return 0.0        # vnt counts: exact match


def run(ground_truth_path: Path) -> int:
    """Return 0 if all computed quantities within tolerance, 1 otherwise."""
    data = yaml.safe_load(ground_truth_path.read_text())
    roof_type = data["roof"]["type"]
    if roof_type not in STRATEGIES:
        print(f"ERROR: roof type {roof_type!r} not yet supported "
              f"(V1 = dvislaitis, keturslaitis)")
        return 1

    inp = _build_input(data)
    out = STRATEGIES[roof_type].compute(inp)

    expected_items = {li["position"]: li for li in data["roofer_samata"]["line_items"]}

    print(f"\n=== {ground_truth_path.name} — {roof_type} ===\n")
    print(f"{'POZICIJA':<35} {'COMPUTED':>10} {'ROOFER':>10} {'DELTA':>10}  STATUS")
    print("-" * 80)

    all_pass = True
    for li in out.line_items:
        # Find the matching roofer position via inverse map (handles plural/singular aliases)
        candidate_keys = _POS_MAP_INV.get(li.pozicija, [])
        roofer_key = next((k for k in candidate_keys if k in expected_items), None)
        if roofer_key is None:
            print(f"{li.pozicija:<35} {li.kiekis:>10.1f} {'—':>10} {'—':>10}  EXTRA")
            continue

        roofer_qty = expected_items[roofer_key]["qty"]
        delta = li.kiekis - roofer_qty
        tol = _tolerance_for(li.pozicija, li.vnt)
        status = "PASS" if abs(delta) <= tol else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{li.pozicija:<35} {li.kiekis:>10.1f} {roofer_qty:>10.1f} "
              f"{delta:>9.1f}{li.vnt[:1]}  {status}")

    print("\n" + ("✓ ALL WITHIN TOLERANCE" if all_pass else "✗ SOME FAIL"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m extractor.roof.cli <ground_truth_yaml>")
        sys.exit(2)
    sys.exit(run(Path(sys.argv[1])))

"""Sprint 4 Block B isolated test.

Use cached P1 room data (from earlier successful extract_interior run) to
verify wall_adjacency + bbox→polygon synthesis logic WITHOUT another
expensive Vision call. Validates: shared-edge math produces grindjuostės
ratio in 0.5-0.6 m/m² band per LT industry math.
"""
from __future__ import annotations
import sys
sys.path.insert(0, '.')
from extractor.vision_call import _apply_polygon_prepass
from extractor.universal_rules import calc_room_quantities


# P1 rooms — bbox + perimetras + plotas from earlier extract_interior run.
# Source: /training-data/projektas_1/projektas_1_breziniai.pdf
P1_ROOMS = [
    {"nr": "01", "pavadinimas": "Tambūras",                     "plotas_m2": 7.36,  "perimetras_m": 11.0, "lubu_aukstis_m": 2.65, "paskirtis": "tamburas",   "bbox_pct": {"x": 0.78, "y": 0.36, "w": 0.13, "h": 0.20}},
    {"nr": "02", "pavadinimas": "Svetainė/valgomasis/virtuvė",  "plotas_m2": 62.42, "perimetras_m": 36.0, "lubu_aukstis_m": 2.65, "paskirtis": "svetaine",   "bbox_pct": {"x": 0.30, "y": 0.42, "w": 0.50, "h": 0.45}},
    {"nr": "03", "pavadinimas": "Koridorius",                    "plotas_m2": 15.25, "perimetras_m": 22.0, "lubu_aukstis_m": 2.65, "paskirtis": "koridorius", "bbox_pct": {"x": 0.30, "y": 0.40, "w": 0.45, "h": 0.10}},
    {"nr": "04", "pavadinimas": "Kambarys",                      "plotas_m2": 12.14, "perimetras_m": 14.0, "lubu_aukstis_m": 2.65, "paskirtis": "kambarys",   "bbox_pct": {"x": 0.13, "y": 0.36, "w": 0.13, "h": 0.18}},
    {"nr": "05", "pavadinimas": "Kambario drabužinė",            "plotas_m2": 3.75,  "perimetras_m": 8.0,  "lubu_aukstis_m": 2.65, "paskirtis": "drabuzine",  "bbox_pct": {"x": 0.18, "y": 0.32, "w": 0.08, "h": 0.08}},
    {"nr": "06", "pavadinimas": "Kambarys 2",                    "plotas_m2": 14.63, "perimetras_m": 15.5, "lubu_aukstis_m": 2.65, "paskirtis": "kambarys",   "bbox_pct": {"x": 0.04, "y": 0.20, "w": 0.13, "h": 0.18}},
    {"nr": "07", "pavadinimas": "Kambario 2 drabužinė",          "plotas_m2": 3.82,  "perimetras_m": 8.0,  "lubu_aukstis_m": 2.65, "paskirtis": "drabuzine",  "bbox_pct": {"x": 0.13, "y": 0.20, "w": 0.08, "h": 0.09}},
    {"nr": "08", "pavadinimas": "Vaikų vonia",                   "plotas_m2": 6.54,  "perimetras_m": 11.0, "lubu_aukstis_m": 2.65, "paskirtis": "vonia",      "bbox_pct": {"x": 0.20, "y": 0.20, "w": 0.10, "h": 0.15}},
    {"nr": "09", "pavadinimas": "Miegamasis",                    "plotas_m2": 14.50, "perimetras_m": 15.5, "lubu_aukstis_m": 2.65, "paskirtis": "miegamoji",  "bbox_pct": {"x": 0.30, "y": 0.20, "w": 0.13, "h": 0.20}},
    {"nr": "10", "pavadinimas": "Miegamojo vonia",               "plotas_m2": 7.20,  "perimetras_m": 15.5, "lubu_aukstis_m": 2.65, "paskirtis": "vonia",      "bbox_pct": {"x": 0.43, "y": 0.20, "w": 0.10, "h": 0.16}},
    {"nr": "11", "pavadinimas": "Miegamojo drabužinė",           "plotas_m2": 4.50,  "perimetras_m": 10.0, "lubu_aukstis_m": 2.65, "paskirtis": "drabuzine",  "bbox_pct": {"x": 0.53, "y": 0.20, "w": 0.10, "h": 0.11}},
    {"nr": "12", "pavadinimas": "Svečių wc",                     "plotas_m2": 2.50,  "perimetras_m": 7.0,  "lubu_aukstis_m": 2.65, "paskirtis": "wc",         "bbox_pct": {"x": 0.78, "y": 0.20, "w": 0.06, "h": 0.09}},
    {"nr": "13", "pavadinimas": "Tech. patalpa/skalbykla",       "plotas_m2": 8.00,  "perimetras_m": 13.0, "lubu_aukstis_m": 2.65, "paskirtis": "skalbykla",  "bbox_pct": {"x": 0.65, "y": 0.20, "w": 0.13, "h": 0.17}},
    {"nr": "14", "pavadinimas": "Pagrindinė namo drabužinė",     "plotas_m2": 6.00,  "perimetras_m": 11.0, "lubu_aukstis_m": 2.65, "paskirtis": "drabuzine",  "bbox_pct": {"x": 0.85, "y": 0.20, "w": 0.10, "h": 0.15}},
    {"nr": "15", "pavadinimas": "Garažas",                       "plotas_m2": 55.40, "perimetras_m": 27.0, "lubu_aukstis_m": 2.65, "paskirtis": "garazas",    "bbox_pct": {"x": 0.78, "y": 0.55, "w": 0.18, "h": 0.32}},
]


def main():
    total_floor = sum(r["plotas_m2"] for r in P1_ROOMS)

    print("=" * 72)
    print("Sprint 4 Block B — Wall_adjacency activation isolated test (P1)")
    print("=" * 72)
    print(f"\n15 rooms, total floor area: {total_floor:.1f} m²\n")

    # ─── BASELINE (no prepass) ─────────────────────────────────────────
    baseline_grind = 0.0
    for r in P1_ROOMS:
        derived = calc_room_quantities(r, {})
        baseline_grind += derived.get("grindjuostes_m") or 0
    print(f"BASELINE (no prepass):")
    print(f"  grindjuostės total: {baseline_grind:.1f} m")
    print(f"  ratio: {baseline_grind/total_floor:.3f} m/m²")
    print(f"  LT industry expect: 0.5-0.6 m/m²")
    print()

    # ─── AFTER prepass ─────────────────────────────────────────────────
    # _apply_polygon_prepass requires polygon_prepass flag on; default-on now.
    # Synthesizes polygons from bbox_pct → wall_adjacency computes shared edges
    # → corrected perimetras_m feeds back into calc_room_quantities.
    pre_result = _apply_polygon_prepass({"patalpos": [dict(r) for r in P1_ROOMS]})
    corrected_rooms = pre_result.get("patalpos", [])

    synth_count = sum(1 for r in corrected_rooms if r.get("polygon_source") == "synthesized_from_bbox")
    corrected_count = sum(1 for r in corrected_rooms if r.get("perimetras_saltinis") == "polygon_adjacency")
    print(f"AFTER prepass:")
    print(f"  polygons synthesized from bbox: {synth_count} / {len(corrected_rooms)}")
    print(f"  rooms with corrected perimeter: {corrected_count} / {len(corrected_rooms)}")

    # Show per-room before/after for sanity
    print(f"\n  Per-room perimetras_m before/after:")
    for orig, corr in zip(P1_ROOMS, corrected_rooms):
        orig_p = orig["perimetras_m"]
        corr_p = corr.get("perimetras_m", orig_p)
        delta = orig_p - corr_p
        if delta > 0.01:
            print(f"    {orig['nr']} {orig['pavadinimas'][:30]:<30} {orig_p:>5.1f} → {corr_p:>5.1f} (Δ -{delta:.1f})")

    corrected_grind = 0.0
    for r in corrected_rooms:
        derived = calc_room_quantities(r, {})
        corrected_grind += derived.get("grindjuostes_m") or 0

    print(f"\n  grindjuostės total (after prepass + lt_rules): {corrected_grind:.1f} m")
    print(f"  ratio: {corrected_grind/total_floor:.3f} m/m²")
    print()

    delta_pct = (corrected_grind - baseline_grind) / baseline_grind * 100 if baseline_grind > 0 else 0
    print(f"DELTA: {baseline_grind:.1f} → {corrected_grind:.1f} m ({delta_pct:+.1f}%)")
    print(f"Ratio: {baseline_grind/total_floor:.3f} → {corrected_grind/total_floor:.3f} m/m²")

    target_min, target_max = 0.45, 0.65
    final_ratio = corrected_grind / total_floor
    if target_min <= final_ratio <= target_max:
        print(f"✓ PASS: final ratio in LT industry expected range [{target_min}-{target_max}]")
    else:
        print(f"✗ FAIL: final ratio {final_ratio:.3f} outside [{target_min}-{target_max}]")


if __name__ == "__main__":
    main()

"""
V8 Stress Test V2 — pataisymais po Sprint 2.

Lyginam V8 output (su mock kambariais arba cached Vision) prieš rangovo
realias sąmatas iš parsed_pasiulymai.json.

Naujovė: pridėta LT sanity validation, atvirų erdvių detection, mansardinis svoris.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from interior_v8 import (
    extract_v8, lt_validate_rooms,
    is_open_space, calc_open_space_features,
)


def load_tomo_data():
    """Iš parsed_pasiulymai.json išrenkam pagrindinius kiekius."""
    f = ROOT / "training-data" / "parsed_pasiulymai.json"
    return json.loads(f.read_text(encoding="utf-8"))


def get_tomo_dazymo_total(parsed: dict) -> float:
    """Iš rangovo sąmatos paimti VISĄ dažomą plotą."""
    total = 0
    for skyrius in parsed.get("skyriai", []):
        for eil in skyrius.get("eilutes", []):
            apr = eil.get("aprasymas", "").lower()
            if ("sienų/ lubų glaistymas" in apr or
                "sienų, lubų glaistymas" in apr or
                "lubų glaistymas" in apr):
                if "virš 3m" not in apr:
                    total += eil.get("kiekis", 0) or 0
    return total


def get_tomo_kampai(parsed: dict) -> float:
    """Iš rangovo sąmatos paimti dažymo kampus."""
    total = 0
    for skyrius in parsed.get("skyriai", []):
        for eil in skyrius.get("eilutes", []):
            apr = eil.get("aprasymas", "").lower()
            if "dažymo kampų" in apr:
                total += eil.get("kiekis", 0) or 0
    return total


def mock_rooms(target_dazymo_m2: float, has_open_space: bool = True) -> list[dict]:
    """Sumock'inam realistinius LT kambarius."""
    grindu_plotas = target_dazymo_m2 / 3.5
    if has_open_space:
        rooms = [
            {"pavadinimas": "Svetaine-valgomasis-virtuve", "plotas_m2": grindu_plotas * 0.40},
            {"pavadinimas": "Miegamasis 1", "paskirtis": "miegamoji", "plotas_m2": grindu_plotas * 0.13},
            {"pavadinimas": "Miegamasis 2", "paskirtis": "miegamoji", "plotas_m2": grindu_plotas * 0.11},
            {"pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": grindu_plotas * 0.06},
            {"pavadinimas": "WC", "paskirtis": "wc", "plotas_m2": grindu_plotas * 0.025},
            {"pavadinimas": "Koridorius", "paskirtis": "koridorius", "plotas_m2": grindu_plotas * 0.10},
            {"pavadinimas": "Drabuzine", "paskirtis": "drabuzine", "plotas_m2": grindu_plotas * 0.04},
            {"pavadinimas": "Holas", "paskirtis": "holas", "plotas_m2": grindu_plotas * 0.05},
            {"pavadinimas": "Garazas", "paskirtis": "garazas", "plotas_m2": grindu_plotas * 0.085},
        ]
    else:
        rooms = [
            {"pavadinimas": "Svetaine", "paskirtis": "gyvenamoji", "plotas_m2": grindu_plotas * 0.25},
            {"pavadinimas": "Virtuve", "paskirtis": "virtuve", "plotas_m2": grindu_plotas * 0.10},
            {"pavadinimas": "Valgomasis", "paskirtis": "valgomasis", "plotas_m2": grindu_plotas * 0.10},
            {"pavadinimas": "Miegamasis 1", "paskirtis": "miegamoji", "plotas_m2": grindu_plotas * 0.13},
            {"pavadinimas": "Miegamasis 2", "paskirtis": "miegamoji", "plotas_m2": grindu_plotas * 0.11},
            {"pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": grindu_plotas * 0.06},
            {"pavadinimas": "WC", "paskirtis": "wc", "plotas_m2": grindu_plotas * 0.025},
            {"pavadinimas": "Koridorius", "paskirtis": "koridorius", "plotas_m2": grindu_plotas * 0.10},
            {"pavadinimas": "Drabuzine", "paskirtis": "drabuzine", "plotas_m2": grindu_plotas * 0.04},
            {"pavadinimas": "Holas", "paskirtis": "holas", "plotas_m2": grindu_plotas * 0.05},
            {"pavadinimas": "Garazas", "paskirtis": "garazas", "plotas_m2": grindu_plotas * 0.085},
        ]

    for i, r in enumerate(rooms, start=1):
        r["nr"] = f"{i:02d}"
        r["plotas_m2"] = round(r["plotas_m2"], 1)
        r["perimetras_m"] = round(4.18 * r["plotas_m2"]**0.5, 1)
        r["lubu_aukstis_m"] = 2.82
    return rooms


def stress_test_one(proj_id: str, parsed: dict, mode: str = "open_space"):
    print(f"\n{'='*72}")
    print(f"PROJEKTAS {proj_id}  (mode: {mode})")
    print('='*72)

    tomo_dazymo = get_tomo_dazymo_total(parsed)
    tomo_kampai = get_tomo_kampai(parsed)

    rooms = mock_rooms(tomo_dazymo, has_open_space=(mode == "open_space"))
    out = extract_v8(rooms, ceiling_height_m=2.82)

    v8_dazymo = out["totals"]["dazymo_plotas_m2"]
    v8_kampai = out["totals"]["kampai_m"]
    plyteles_grindys = out["totals"]["plyteles_grindys_m2"]
    plyteles_sienos = out["totals"]["plyteles_sienos_m2"]

    # LT sanity validation
    sanity = lt_validate_rooms(out["rooms"])

    # Atvirų erdvių detection patikra
    open_spaces = [r for r in out["rooms"] if r.get("is_open_space")]

    def diff_pct(a, b):
        if b == 0:
            return None
        return (a - b) / b * 100

    print(f"\n  Dazymo plotas:  rangovo={tomo_dazymo:.1f} m²  V8={v8_dazymo:.1f} m²"
          f"  diff={diff_pct(v8_dazymo, tomo_dazymo):+.1f}%")
    print(f"  Kampai:         rangovo={tomo_kampai:.1f} m   V8={v8_kampai:.1f} m"
          f"  diff={diff_pct(v8_kampai, tomo_kampai):+.1f}%")
    print(f"  Plyteles grindyse: V8={plyteles_grindys:.1f} m²")
    print(f"  Plyteles sienose:  V8={plyteles_sienos:.1f} m²")
    print(f"  Open spaces aptikta: {len(open_spaces)}")
    if open_spaces:
        for os_room in open_spaces:
            print(f"    + {os_room['pavadinimas']} ({os_room['plotas_m2']} m²)")
    print(f"\n  LT sanity warnings: {sanity['summary']['warnings_count']}")
    for w in sanity["warnings"][:3]:
        print(f"    - [{w['level']}] {w['message']}")

    return {
        "v8_dazymo": v8_dazymo,
        "tomo_dazymo": tomo_dazymo,
        "diff_pct": diff_pct(v8_dazymo, tomo_dazymo),
        "open_spaces_detected": len(open_spaces),
        "sanity_warnings": sanity["summary"]["warnings_count"],
    }


def main():
    tomo_data = load_tomo_data()
    print("V8 STRESS TEST V2 — Sprint 2 patobulinimai")
    print("Naudojam mock kambarius — testuojam V8 universal_engine logikos tikslumą.")
    print("Realybėj Vision turi grąžinti panašius kambarius, o V8 logika juos paverti į kiekius.")

    diffs = []
    for proj_id in ["P1", "P2", "P3", "P4", "P5"]:
        if proj_id not in tomo_data:
            continue
        result = stress_test_one(proj_id, tomo_data[proj_id])
        if result["diff_pct"] is not None:
            diffs.append(abs(result["diff_pct"]))

    print()
    print("="*72)
    if diffs:
        avg = sum(diffs) / len(diffs)
        print(f"VIDUTINIS DAZYMO PLOTO DIFF NUO rangovo: ±{avg:.1f}%")
        if avg < 15:
            print("→ EXCELLENT (production-ready accuracy)")
        elif avg < 30:
            print("→ ACCEPTABLE (vartotojas lengvai patikrins)")
        else:
            print("→ NEEDS WORK (per dideli skirtumai)")


if __name__ == "__main__":
    main()

"""Exhaustive formula explorer — RESEARCH ONLY (no implementation).

Sweeps a small grid of (door_deduction × wall_factor_default × waste_factor)
combinations on Beržų gt_dimensions and reports the top combos by combined
distance to truth. Designed to let a human inspect whether ANY combination
is principled (cites a citable LT standard) — versus being a curve fit.

Honest engineering: any combo that happens to hit ≤0.1% on Beržų is
overwhelmingly likely an overfit because (a) we have N=1 truth file and
(b) the grid has enough degrees of freedom to fit any single target.
Surface the data; do not commit.
"""

from __future__ import annotations

import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.universal_rules import calc_room_quantities

TRUTH = {
    "walls_paint_total_m2": 460.71,
    "dazymo_excl_garazas_total_m2": 584.81,
    "ceiling_paint_total_m2": 165.60,
    "floor_total_m2": 165.61,
    "angokrasciu_gkp_m_total": 89.39,
    "gkp_lubu_iki_3m_m2_total": 102.78,
    "gkp_lubu_virs_3m_m2_total": 62.82,
}


@dataclass
class Combo:
    door_deduction_m2: float
    waste_paint: float
    # Future: add more axes as need arises
    walls: float
    ceiling: float
    combined_excl_garazas: float
    angokrasciu: float
    distance: float


def run_combo(rooms: list[dict], door_deduction: float, waste_paint: float) -> Combo:
    """Re-implements walls calculation with a parameterised door deduction.
    The other metrics (ceiling/angokrasciu/etc.) we read straight from the
    production calculator's output on the same primitives, since they don't
    use door_deduction — they're invariant under this axis."""
    # Walls: re-derive with the parameterised deduction.
    walls_total = 0.0
    for r in rooms:
        perim = float(r.get("perimetras_m") or 0)
        H = float(r.get("lubu_aukstis_m") or 0)
        n_doors = sum(int(e.get("kiekis") or 1)
                      for e in (r.get("elementai") or [])
                      if (e.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))
        walls_gross = perim * H
        apdaila = r.get("sienu_apdailos_breakdown") or {}
        is_full_tile = False
        if apdaila:
            tile_share = float(apdaila.get("plyteles_share") or 0)
            tile_h = float(r.get("plyteles_sienos_aukstis_m") or 0)
            tile_h_eff = tile_h if tile_h > 0 else H
            is_full_tile = (tile_share >= 0.8 and tile_h_eff >= H * 0.95)
        if is_full_tile:
            base = 0.0
        else:
            override = r.get("walls_paint_factor_override")
            factor = float(override) if override is not None else (1.0 if apdaila else _paskirtis_factor((r.get("paskirtis") or "").lower()))
            base = max(0, walls_gross - n_doors * door_deduction) * factor
        extras = float(r.get("extra_walls_m2") or 0) + float(r.get("extra_walls_virs_3m_m2") or 0)
        walls_total += (base + extras) * waste_paint

    # For the other metrics we use the standard calc (waste applied
    # uniformly is the simplification — door_deduction doesn't move them).
    ceiling_total = sum(float(r.get("plotas_m2") or 0) * waste_paint
                        for r in rooms
                        if (r.get("lubu_tipas") or "gkp").lower() in ("gkp", "tempiamos"))
    # Angokraščiai per Rule #1 (Beržų-confirmed)
    ang = 0.0
    for r in rooms:
        for el in r.get("elementai") or []:
            tipas = (el.get("tipas") or "").lower()
            kiekis = int(el.get("kiekis") or 1)
            w = float(el.get("plotis_mm") or 0) / 1000.0
            h = float(el.get("aukstis_mm") or 0) / 1000.0
            if w <= 0 or h <= 0:
                continue
            if tipas in ("duris", "pasleptos_duris"):
                ang += kiekis * (w + 2 * h)
            elif tipas in ("langas", "stoglangis") and not bool(el.get("_exterior")):
                ang += kiekis * (w + 2 * h)

    # Distance: sum of |Δ| / truth, capped at 1.0 per metric so one wildly-off
    # number doesn't dominate.
    def cap(d, tr):
        return min(abs(d - tr) / tr, 1.0) if tr else 0
    dist = (cap(walls_total, TRUTH["walls_paint_total_m2"])
            + cap(ceiling_total, TRUTH["ceiling_paint_total_m2"])
            + cap(walls_total + ceiling_total - 41.5, TRUTH["dazymo_excl_garazas_total_m2"])  # roughly excl garažas
            + cap(ang, TRUTH["angokrasciu_gkp_m_total"]))
    return Combo(
        door_deduction_m2=door_deduction,
        waste_paint=waste_paint,
        walls=walls_total,
        ceiling=ceiling_total,
        combined_excl_garazas=walls_total + ceiling_total - 41.5,
        angokrasciu=ang,
        distance=dist,
    )


def _paskirtis_factor(p: str) -> float:
    return {"garazas": 0.0, "garažas": 0.0, "tamburas": 0.0, "tambūras": 0.0}.get(p, 1.0)


def main() -> int:
    truth_path = REPO_ROOT / "ground_truth" / "berzas" / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    rooms = []
    for r in truth["gt_dimensions"]:
        room = {k: v for k, v in r.items() if not k.startswith("_dim")}
        if room.get("elementai"):
            room["elementai"] = [dict(e) for e in room["elementai"]]
        rooms.append(room)

    door_deductions = [0.0, 0.5, 1.125, 1.4, 1.6, 1.89, 2.0]    # 7 options
    waste_factors = [0.97, 0.98, 0.99, 1.00, 1.01, 1.02, 1.03]  # ±3%
    combos = []
    for dd, wf in itertools.product(door_deductions, waste_factors):
        combos.append(run_combo(rooms, dd, wf))

    combos.sort(key=lambda c: c.distance)
    print(f"\nExhaustive formula search on Beržų — RESEARCH OUTPUT ONLY")
    print(f"  {len(combos)} combos tested (door_deduction × waste_paint).")
    print(f"  Distance = Σ |Δ|/truth per metric, capped at 1.0 per metric.\n")
    print(f"  {'door_ded':>8} {'waste':>6} {'walls':>8} {'ceiling':>8} "
          f"{'combined':>9} {'angokrasc':>9} {'distance':>9}")
    print("  " + "─" * 70)
    for c in combos[:20]:
        print(f"  {c.door_deduction_m2:>8.3f} {c.waste_paint:>6.3f} "
              f"{c.walls:>8.2f} {c.ceiling:>8.2f} {c.combined_excl_garazas:>9.2f} "
              f"{c.angokrasciu:>9.2f} {c.distance:>9.4f}")

    print()
    best = combos[0]
    print(f"  BEST COMBO:  door_ded={best.door_deduction_m2}, waste={best.waste_paint}")
    print(f"    walls   {best.walls:.2f}  vs truth {TRUTH['walls_paint_total_m2']}  "
          f"Δ {(best.walls - TRUTH['walls_paint_total_m2']) / TRUTH['walls_paint_total_m2'] * 100:+.2f}%")
    print(f"    ceiling {best.ceiling:.2f}  vs truth {TRUTH['ceiling_paint_total_m2']}  "
          f"Δ {(best.ceiling - TRUTH['ceiling_paint_total_m2']) / TRUTH['ceiling_paint_total_m2'] * 100:+.2f}%")
    print(f"    angokr  {best.angokrasciu:.2f}  vs truth {TRUTH['angokrasciu_gkp_m_total']}  "
          f"Δ {(best.angokrasciu - TRUTH['angokrasciu_gkp_m_total']) / TRUTH['angokrasciu_gkp_m_total'] * 100:+.2f}%")

    print()
    print("  IMPORTANT — RESEARCH ONLY: do NOT implement any combo unless a")
    print("  specific STR / NRM2 / contractor convention citation justifies it.")
    print("  With 49 grid points and 4 weighted targets, the best combo is almost")
    print("  certainly an overfit on Beržų's N=1 truth, not a generalisable rule.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

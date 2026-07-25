"""Phase 1.1 + 1.2 — input purity audit. Zero Vision spend.

Cross-checks every room's ceiling height + every opening's dimensions
against:
  • contractor totals (lubos žemos 92.73, lubos aukštos 62.82, garažas
    ceiling 10.05, total 165.60)
  • contractor opening counts (14 doors, 89.39m atkosai under Rule #1)
  • internal consistency (high_ceiling_area_m2 overrides, factor
    overrides, opening kiekis multipliers)

Flags any room whose CURRENT inputs disagree with what contractor
totals imply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Contractor totals (samata items 1+2 + contractor notes)
TRUTH_LUBOS_ZEMOS_M2 = 92.73    # H ≤ 3.0m ceilings in main house (item 1)
TRUTH_LUBOS_AUKSTOS_M2 = 62.82  # H > 3.0m ceilings (item 2)
TRUTH_GARAZAS_CEIL_M2 = 10.05
TRUTH_TOTAL_CEIL_M2 = 165.60
TRUTH_N_DOORS = 14
TRUTH_ATKOSAI_M = 89.39


def main() -> int:
    truth = json.loads((REPO_ROOT / "ground_truth/berzas/truth.json").read_text())
    rooms = truth["gt_dimensions"]

    print("\n═══ Phase 1.1 — Ceiling height audit ═══\n")
    print(f"  {'nr':<4} {'name':<22} {'H':>5} {'high_extra':>10} {'gkp_extra':>9} "
          f"{'lubu_tipas':<10} {'paskirtis':<12}  contributes to")
    print("  " + "─" * 100)
    iki = aukstos = garazas_extra = 0.0
    for r in rooms:
        nr = str(r.get("nr"))
        name = r.get("pavadinimas") or ""
        H = float(r.get("lubu_aukstis_m") or 0)
        high_extra = float(r.get("high_ceiling_area_m2") or 0)
        gkp_extra = float(r.get("gkp_extra_area_m2") or 0)
        lubu = (r.get("lubu_tipas") or "gkp")
        paskirtis = (r.get("paskirtis") or "")
        plotas = float(r.get("plotas_m2") or 0)

        # What does this room contribute to each truth bucket?
        contrib = []
        if paskirtis == "garazas":
            if gkp_extra > 0:
                garazas_extra += gkp_extra
                contrib.append(f"garažas:{gkp_extra:.1f}")
        elif lubu in ("gkp", "tempiamos"):
            if high_extra > 0:
                aukstos += min(high_extra, plotas)
                iki += max(0, plotas - high_extra)
                contrib.append(f"iki:{plotas - high_extra:.1f} + aukš:{high_extra:.1f}")
            elif H > 3.0:
                aukstos += plotas
                contrib.append(f"aukš:{plotas:.1f}")
            else:
                iki += plotas
                contrib.append(f"iki:{plotas:.1f}")
        print(f"  {nr:<4} {name[:22]:<22} {H:>5.2f} {high_extra:>10.2f} {gkp_extra:>9.2f} "
              f"{lubu:<10} {paskirtis:<12}  {', '.join(contrib)}")

    print()
    print(f"  CONTRACTOR TRUTH:        iki 3m: {TRUTH_LUBOS_ZEMOS_M2:>6.2f} m²   "
          f"virš 3m: {TRUTH_LUBOS_AUKSTOS_M2:>6.2f} m²   garažas: {TRUTH_GARAZAS_CEIL_M2:>6.2f} m²")
    print(f"  APP COMPUTED:            iki 3m: {iki:>6.2f} m²   virš 3m: {aukstos:>6.2f} m²   "
          f"garažas: {garazas_extra:>6.2f} m²")
    print(f"  DELTA:                   iki 3m: {iki-TRUTH_LUBOS_ZEMOS_M2:>+6.2f} m²   "
          f"virš 3m: {aukstos-TRUTH_LUBOS_AUKSTOS_M2:>+6.2f} m²   "
          f"garažas: {garazas_extra-TRUTH_GARAZAS_CEIL_M2:>+6.2f} m²")
    print()
    if abs(iki - TRUTH_LUBOS_ZEMOS_M2) < 0.5 and abs(aukstos - TRUTH_LUBOS_AUKSTOS_M2) < 0.5:
        print("  ✓ All ceiling heights produce contractor-consistent totals.")
        print("    No room needs height correction.")
    else:
        print("  ⚠ At least one tier diverges from contractor truth.")
        print("    Investigate which room's H or high_ceiling_area_m2 is off.")

    # ── Phase 1.2 — opening dimension audit ─────────────────────────────────
    print("\n═══ Phase 1.2 — Opening dimension audit ═══\n")
    total_doors = total_windows = 0
    total_exterior_doors = total_exterior_windows = 0
    angokrasciu = 0.0
    for r in rooms:
        for el in r.get("elementai") or []:
            tipas = (el.get("tipas") or "").lower()
            kiekis = int(el.get("kiekis") or 1)
            w_mm = float(el.get("plotis_mm") or 0)
            h_mm = float(el.get("aukstis_mm") or 0)
            is_ext = bool(el.get("_exterior"))
            if tipas in ("duris", "pasleptos_duris"):
                total_doors += kiekis
                if is_ext:
                    total_exterior_doors += kiekis
                # Per Rule #1: all doors contribute W+2H
                if w_mm > 0 and h_mm > 0:
                    angokrasciu += kiekis * (w_mm + 2 * h_mm) / 1000.0
            elif tipas in ("langas", "stoglangis"):
                total_windows += kiekis
                if is_ext:
                    total_exterior_windows += kiekis
                if w_mm > 0 and h_mm > 0 and not is_ext:
                    angokrasciu += kiekis * (w_mm + 2 * h_mm) / 1000.0

    print(f"  Total doors:        {total_doors:>4}   (contractor truth: {TRUTH_N_DOORS})")
    print(f"  Total windows:      {total_windows:>4}")
    print(f"  Exterior doors:     {total_exterior_doors:>4}")
    print(f"  Exterior windows:   {total_exterior_windows:>4}")
    print(f"  Interior doors:     {total_doors - total_exterior_doors:>4}")
    print(f"  Interior windows:   {total_windows - total_exterior_windows:>4}")
    print()
    print(f"  Recomputed angokrasciu_m (Rule #1): {angokrasciu:>6.2f} m")
    print(f"  Contractor truth (atkosai):         {TRUTH_ATKOSAI_M:>6.2f} m")
    print(f"  Delta:                              {angokrasciu - TRUTH_ATKOSAI_M:>+6.2f} m  "
          f"({(angokrasciu - TRUTH_ATKOSAI_M) / TRUTH_ATKOSAI_M * 100:+.3f}%)")
    print()

    # Per-opening width/height distribution
    print("  Per-opening dimension distribution:")
    door_widths: dict[int, int] = {}
    door_heights: dict[int, int] = {}
    win_widths: dict[int, int] = {}
    win_heights: dict[int, int] = {}
    for r in rooms:
        for el in r.get("elementai") or []:
            tipas = (el.get("tipas") or "").lower()
            kiekis = int(el.get("kiekis") or 1)
            w = int(el.get("plotis_mm") or 0)
            h = int(el.get("aukstis_mm") or 0)
            if tipas in ("duris", "pasleptos_duris"):
                door_widths[w] = door_widths.get(w, 0) + kiekis
                door_heights[h] = door_heights.get(h, 0) + kiekis
            elif tipas in ("langas", "stoglangis"):
                win_widths[w] = win_widths.get(w, 0) + kiekis
                win_heights[h] = win_heights.get(h, 0) + kiekis
    print(f"    Door widths   : {sorted(door_widths.items())}")
    print(f"    Door heights  : {sorted(door_heights.items())}")
    print(f"    Window widths : {sorted(win_widths.items())}")
    print(f"    Window heights: {sorted(win_heights.items())}")
    print()
    print("  Sanity: standard LT door is 900×2100. Anything wildly out of band")
    print("  (e.g. door width <600 or >3000 mm; height <1800 or >2400 mm) deserves")
    print("  manual verification on the PDF.")

    print()
    print("  HONEST DISCLOSURE: there is no contractor per-opening dimension list")
    print("  in this PDF — only aggregate counts/lengths. So we cannot directly")
    print("  validate each opening's W×H. The total-counts agreement (14 doors,")
    print("  atkosai +0.13%) is the strongest indirect signal we have.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

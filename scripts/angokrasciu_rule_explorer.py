"""Angokraščiai rule explorer — brute-force candidate formulas.

Loads Beržų gt_dimensions, enumerates every opening (doors + windows),
then tries every combination of:
  • per-opening length formula (W+2H, W+H, 2(W+H), …)
  • which-openings-count filter (all, interior-only, doors only, …)

Reports the top candidates by closeness to the contractor truth (89.39 m).

PURE PYTHON. NO VISION CALLS. The output is a RANKED REPORT that the
user uses to PICK ONE RULE; nothing in this script modifies the production
calculator or eval. Per the user's explicit gate — explorer must be a
report, not an implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
TRUTH_PATH = REPO_ROOT / "ground_truth" / "berzas" / "truth.json"
TRUTH_TOTAL = 89.39   # contractor samata items 13/14 "Atkosai"

DOOR_TIPAS = {"duris", "pasleptos_duris"}
WINDOW_TIPAS = {"langas", "stoglangis"}
WET_PASKIRTYS = {"vonia", "wc", "san", "skalbykla", "katiline"}


@dataclass
class Opening:
    room_nr: str
    paskirtis: str
    tipas: str
    width_mm: float
    height_mm: float
    is_exterior: bool

    @property
    def is_door(self) -> bool:
        return self.tipas in DOOR_TIPAS

    @property
    def is_window(self) -> bool:
        return self.tipas in WINDOW_TIPAS

    @property
    def w_m(self) -> float:
        return self.width_mm / 1000.0

    @property
    def h_m(self) -> float:
        # When height_mm is missing (e.g. LED niches), fall back to door
        # height 2.1 for doors / 1.5 for windows.
        if self.height_mm > 0:
            return self.height_mm / 1000.0
        return 2.1 if self.is_door else 1.5


def load_openings() -> list[Opening]:
    truth = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    out: list[Opening] = []
    for room in truth["gt_dimensions"]:
        nr = str(room.get("nr") or "")
        paskirtis = (room.get("paskirtis") or "").lower()
        for el in room.get("elementai") or []:
            tipas = (el.get("tipas") or "").lower()
            if tipas not in (DOOR_TIPAS | WINDOW_TIPAS):
                continue
            kiekis = int(el.get("kiekis") or 1)
            for _ in range(kiekis):
                out.append(Opening(
                    room_nr=nr, paskirtis=paskirtis, tipas=tipas,
                    width_mm=float(el.get("plotis_mm") or 0),
                    height_mm=float(el.get("aukstis_mm") or 0),
                    is_exterior=bool(el.get("_exterior", False)),
                ))
    return out


# ── Per-opening length formulas ──────────────────────────────────────────────
FORMULAS: dict[str, Callable[[Opening], float]] = {
    "W + 2H":         lambda o: o.w_m + 2 * o.h_m,
    "W + H":          lambda o: o.w_m + o.h_m,
    "2(W + H)":       lambda o: 2 * (o.w_m + o.h_m),    # full perimeter
    "2H":             lambda o: 2 * o.h_m,              # vertical sides only
    "H + W":          lambda o: o.h_m + o.w_m,          # same as W+H, alias
    "2H + 2W":        lambda o: 2 * o.h_m + 2 * o.w_m,  # alias of 2(W+H)
    "W + 2H + bottom":lambda o: o.w_m + 2 * o.h_m + o.w_m,  # 2W+2H
    "fixed 2.8":      lambda o: 2.8,                    # contractor item-19
                                                        # "14 × 2.8 = 39.2"
}


# ── Which-openings-count filters ─────────────────────────────────────────────
def _all(o: Opening) -> bool:               return True
def _interior(o: Opening) -> bool:          return not o.is_exterior
def _exterior(o: Opening) -> bool:          return o.is_exterior
def _doors(o: Opening) -> bool:             return o.is_door
def _windows(o: Opening) -> bool:           return o.is_window
def _interior_doors(o: Opening) -> bool:    return o.is_door and not o.is_exterior
def _exterior_doors(o: Opening) -> bool:    return o.is_door and o.is_exterior
def _wet(o: Opening) -> bool:               return o.paskirtis in WET_PASKIRTYS
def _non_garage(o: Opening) -> bool:        return o.paskirtis not in ("garazas", "garažas")
def _doors_or_interior_windows(o: Opening) -> bool:
    return o.is_door or (o.is_window and not o.is_exterior)


FILTERS: dict[str, Callable[[Opening], bool]] = {
    "all openings":              _all,
    "interior only":             _interior,
    "exterior only":             _exterior,
    "doors only":                _doors,
    "windows only":              _windows,
    "interior doors only":       _interior_doors,
    "exterior doors only":       _exterior_doors,
    "wet rooms only":            _wet,
    "non-garage rooms":          _non_garage,
    "doors + interior windows":  _doors_or_interior_windows,
}


@dataclass
class Candidate:
    rule: str
    total_m: float
    n_openings: int
    error_pct: float
    error_abs: float


def evaluate(openings: list[Opening], formula_label: str, filter_label: str) -> Candidate:
    formula = FORMULAS[formula_label]
    flt = FILTERS[filter_label]
    selected = [o for o in openings if flt(o)]
    total = sum(formula(o) for o in selected)
    error_abs = total - TRUTH_TOTAL
    error_pct = (error_abs / TRUTH_TOTAL) * 100.0
    return Candidate(
        rule=f"{formula_label}  |  {filter_label}",
        total_m=total, n_openings=len(selected),
        error_pct=error_pct, error_abs=error_abs,
    )


# ── Mixed rules (per-type formula) ───────────────────────────────────────────
def evaluate_mixed(openings: list[Opening],
                   door_formula: str, window_formula: str,
                   filter_label: str) -> Candidate:
    flt = FILTERS[filter_label]
    selected = [o for o in openings if flt(o)]
    door_fn = FORMULAS[door_formula]
    win_fn = FORMULAS[window_formula]
    total = sum(
        door_fn(o) if o.is_door else win_fn(o)
        for o in selected
    )
    error_abs = total - TRUTH_TOTAL
    error_pct = (error_abs / TRUTH_TOTAL) * 100.0
    return Candidate(
        rule=f"doors:{door_formula} / windows:{window_formula}  |  {filter_label}",
        total_m=total, n_openings=len(selected),
        error_pct=error_pct, error_abs=error_abs,
    )


def main() -> int:
    openings = load_openings()
    n_doors = sum(1 for o in openings if o.is_door)
    n_windows = sum(1 for o in openings if o.is_window)
    n_exterior = sum(1 for o in openings if o.is_exterior)
    print(f"Beržų openings loaded: {len(openings)}  ({n_doors} doors, "
          f"{n_windows} windows; {n_exterior} flagged exterior)")
    print(f"Contractor truth (atkosai item 13/14): {TRUTH_TOTAL} m")
    print()

    candidates: list[Candidate] = []
    # Cartesian product of single-formula rules
    for f_label in FORMULAS:
        for filt_label in FILTERS:
            candidates.append(evaluate(openings, f_label, filt_label))

    # Mixed (per-type) rules — the most common LT samata convention
    interesting_mixes = [
        ("W + 2H", "W + 2H"),
        ("W + H",  "W + 2H"),
        ("W + 2H", "2(W + H)"),
        ("fixed 2.8", "W + 2H"),
        ("W + 2H", "W + H"),
    ]
    for d, w in interesting_mixes:
        for filt_label in FILTERS:
            candidates.append(evaluate_mixed(openings, d, w, filt_label))

    # Sort by absolute error
    candidates.sort(key=lambda c: abs(c.error_pct))

    print(f"Top 20 candidates by |Δ%| vs truth {TRUTH_TOTAL:.2f} m:\n")
    print(f"  {'rule':<60} {'total_m':>10} {'n_open':>7} {'Δ_m':>8} {'Δ%':>8}")
    print("  " + "─" * 96)
    for c in candidates[:20]:
        print(f"  {c.rule[:60]:<60} {c.total_m:>10.2f} {c.n_openings:>7} "
              f"{c.error_abs:>+8.2f} {c.error_pct:>+7.2f}%")
    print()

    # Also surface the current production formula's result for context
    # ("interior only" + "W + 2H" approximates what the calc emits today).
    print("For reference — current production formula (interior-only, W+2H):")
    current = evaluate(openings, "W + 2H", "interior only")
    print(f"  total = {current.total_m:.2f} m  ({current.n_openings} openings)  "
          f"Δ {current.error_pct:+.2f}%")
    print()

    # Top 3 — what the user explicitly asked for
    print("=" * 96)
    print("  USER GATE: TOP 3 CANDIDATES — REPORT TO USER BEFORE IMPLEMENTING")
    print("=" * 96)
    for i, c in enumerate(candidates[:3], 1):
        print(f"\n  #{i}: {c.rule}")
        print(f"     total = {c.total_m:.2f} m   ({c.n_openings} openings)")
        print(f"     vs truth {TRUTH_TOTAL:.2f} m → Δ {c.error_abs:+.2f} m ({c.error_pct:+.2f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Experiment 1 — FALSE-GREEN RATE: of quantities the system would present as
high-confidence (🟢), how many are actually wrong vs contractor truth?

Confidence assignment (mirrors what the UI would show):
  - A quantity is FLAGGED (🟡/🔴) if any of its input room-fields appears in
    _voting.low_confidence_fields, or a structural fallback fired (e.g. the
    adjacency pass produced 0 partition walls → kampai is missing pusiniai).
  - Otherwise it is GREEN.
WRONG = |error vs contractor truth| > 10% (5% also reported).

false_green_rate = wrong greens / all greens   (the existential metric)
flag_precision   = wrong flagged / all flagged (are flags meaningful?)
error_recall     = wrong flagged / all wrong   (do flags catch the errors?)

Usage: venv/bin/python scripts/exp1_false_green.py <voted_extract.json> <slug>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from extractor.universal_rules import calc_room_quantities  # noqa: E402


def _flagged_rooms(extract: dict) -> dict[str, set]:
    """room-label -> set of flagged fields, from the voting block."""
    out: dict[str, set] = {}
    for f in ((extract.get("_voting") or {}).get("low_confidence_fields") or []):
        out.setdefault(str(f.get("room")), set()).add(f.get("field"))
    return out


def _q(rooms, field):
    return round(sum(float(calc_room_quantities(r).get(field) or 0) for r in rooms), 2)


def build_quantities(extract: dict, slug: str) -> list[dict]:
    """[{name, app, truth, inputs:[(room,field)...], structural_flag}]"""
    rooms = extract.get("patalpos") or []
    npw_total = sum(int(r.get("n_partition_walls") or 0) for r in rooms)
    all_perim = [(r.get("pavadinimas"), "perimetras_m") for r in rooms]
    all_h = [(r.get("pavadinimas"), "lubu_aukstis_m") for r in rooms]

    walls = _q(rooms, "walls_paintable_m2")
    ceil = _q(rooms, "ceiling_paintable_m2")
    kampai = _q(rooms, "kampu_metrai")
    floor = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
    gkp_std = _q(rooms, "gkp_lubu_standart_m2")
    gkp_hi = _q(rooms, "gkp_lubu_virs_3m_m2")
    nisos = _q(rooms, "nisu_metrai")
    angokr = _q(rooms, "angokrasciu_gkp_m")
    grindj = _q(rooms, "grindjuosciu_m")
    silik = _q(rooms, "silikonavimas_m")
    pl_sien = _q(rooms, "plyteles_sienos_m2")
    pl_grind = _q(rooms, "plyteles_grindys_m2")

    def room(nr):
        return next((r for r in rooms if str(r.get("nr")) == nr), None)

    Q: list[dict] = []
    if slug == "objektas_a":
        Q = [
            dict(name="floor_total", app=floor, truth=165.64, inputs=[]),
            dict(name="ceiling_paint", app=ceil, truth=165.6, inputs=[]),
            dict(name="walls_paint", app=walls, truth=460.71, inputs=all_perim + all_h),
            dict(name="combined_paint", app=round(walls + ceil, 2), truth=584.81,
                 inputs=all_perim + all_h),
            dict(name="kampai", app=kampai, truth=493.35, inputs=all_perim + all_h,
                 structural_flag=("adjacency_zero" if npw_total == 0 else None)),
            dict(name="led_nisos", app=nisos, truth=42.3, inputs=[]),
            dict(name="angokrasciai", app=angokr, truth=89.39, inputs=[]),
            dict(name="grindjuostes_total", app=grindj, truth=None, inputs=all_perim),
        ]
        per_room = {
            ("105", "walls_paintable_m2", 31.45): "p105_garazo_walls",
            ("101", "grindjuosciu_m", 10.32): "p101_grindjuostes",
            ("106", "grindjuosciu_m", 11.8): "p106_grindjuostes",
            ("105", "grindjuosciu_m", 10.92): "p105_grindjuostes",
            ("107", "plyteles_sienos_m2", 32.73): "p107_plyteles_sienos",
            ("107", "silikonavimas_m", 23.64): "p107_silikonavimas",
            ("101", "plyteles_grindys_m2", 8.54): "p101_plyteles_grindys",
            ("106", "plyteles_grindys_m2", 6.89): "p106_plyteles_grindys",
            ("105", "plyteles_grindys_m2", 10.1): "p105_plyteles_grindys",
            ("107", "plyteles_grindys_m2", 6.52): "p107_plyteles_grindys",
        }
        for (nr, field, truth), name in per_room.items():
            r = room(nr)
            if not r:
                continue
            app = round(float(calc_room_quantities(r).get(field) or 0), 2)
            Q.append(dict(name=name, app=app, truth=truth,
                          inputs=[(r.get("pavadinimas"), "perimetras_m"),
                                  (r.get("pavadinimas"), "lubu_aukstis_m")]))
    elif slug == "objektas_b":
        Q = [
            dict(name="gkp_lubu_iki3m", app=gkp_std, truth=74.91, inputs=all_h),
            dict(name="gkp_lubu_virs3m", app=gkp_hi, truth=68.28, inputs=all_h),
            dict(name="led_nisos", app=nisos, truth=54.98, inputs=[]),
            dict(name="angokrasciai", app=angokr, truth=94.02, inputs=[]),
            dict(name="rotband", app=round(walls * 0.30, 2), truth=138.69,
                 inputs=all_perim + all_h),
            dict(name="combined_paint", app=round(walls + ceil, 2), truth=493.03,
                 inputs=all_perim + all_h),
            dict(name="kampai", app=kampai, truth=580.54, inputs=all_perim + all_h,
                 structural_flag=("adjacency_zero" if npw_total == 0 else None)),
            dict(name="durys_beapvadines", app=None, truth=55.52, inputs=[]),  # filled below
            dict(name="grindjuostes_total", app=grindj, truth=93.8, inputs=all_perim),
            dict(name="plyteles_total_m2", app=round(pl_sien + pl_grind, 2),
                 truth=round(157.34 + 52.59 + 7.52, 2), inputs=all_perim),
            dict(name="silikonavimas", app=silik, truth=128.97, inputs=all_perim),
            dict(name="islyginamasis", app=None, truth=143.19, inputs=[]),
        ]
        # paslėptų durų staktos
        pasl = 0.0
        for r in rooms:
            for el in (r.get("elementai") or []):
                if (el.get("tipas") or "").lower() == "pasleptos_duris":
                    W = (el.get("plotis_mm") or 0) / 1000
                    H = (el.get("aukstis_mm") or 0) / 1000
                    if W > 0 and H > 0:
                        pasl += (2 * H + W) * int(el.get("kiekis") or 1)
        for q in Q:
            if q["name"] == "durys_beapvadines":
                q["app"] = round(pasl, 2)
            if q["name"] == "islyginamasis":
                q["app"] = floor  # išlyginamasis ≈ grindų plotas
    return Q


def main() -> int:
    extract_path, slug = sys.argv[1], sys.argv[2]
    extract = json.load(open(extract_path))
    flags = _flagged_rooms(extract)
    Q = build_quantities(extract, slug)

    rows, greens, flagged = [], [], []
    for q in Q:
        if q.get("app") is None or q.get("truth") in (None, 0):
            continue
        err = (q["app"] - q["truth"]) / q["truth"] * 100
        is_flagged = bool(q.get("structural_flag")) or any(
            f in flags.get(str(room), set()) for room, f in q.get("inputs") or [])
        wrong10, wrong5 = abs(err) > 10, abs(err) > 5
        row = dict(name=q["name"], app=q["app"], truth=q["truth"],
                   err_pct=round(err, 1),
                   conf=("FLAGGED" if is_flagged else "GREEN"),
                   structural=q.get("structural_flag"),
                   wrong_10pct=wrong10, wrong_5pct=wrong5)
        rows.append(row)
        (flagged if is_flagged else greens).append(row)

    n_g = len(greens)
    fg10 = sum(1 for r in greens if r["wrong_10pct"])
    fg5 = sum(1 for r in greens if r["wrong_5pct"])
    wrong_all = [r for r in rows if r["wrong_10pct"]]
    fl_wrong = sum(1 for r in flagged if r["wrong_10pct"])

    print(f"\n══ FALSE-GREEN RATE — {slug} ══")
    print(f"{'quantity':24} {'app':>9} {'truth':>9} {'err%':>7}  conf")
    for r in sorted(rows, key=lambda x: -abs(x["err_pct"])):
        mark = "✗" if r["wrong_10pct"] else ("~" if r["wrong_5pct"] else "✓")
        print(f"{r['name']:24} {r['app']:>9} {r['truth']:>9} {r['err_pct']:>+7.1f}  "
              f"{r['conf']}{' ['+r['structural']+']' if r['structural'] else ''} {mark}")
    print(f"\nGREEN quantities: {n_g} | wrong>10%: {fg10} | wrong>5%: {fg5}")
    print(f"FALSE-GREEN RATE: {fg10}/{n_g} = {fg10/n_g*100:.0f}% (@10% tol) ; "
          f"{fg5}/{n_g} = {fg5/n_g*100:.0f}% (@5% tol)")
    print(f"FLAGGED: {len(flagged)} | of which wrong: {fl_wrong} "
          f"(precision {fl_wrong/len(flagged)*100:.0f}%)" if flagged else "FLAGGED: 0")
    print(f"ERROR RECALL by flags: {fl_wrong}/{len(wrong_all)} wrong quantities were flagged"
          if wrong_all else "no wrong quantities")

    out = Path(extract_path).parent / f"exp1_false_green_{slug}.json"
    out.write_text(json.dumps(dict(rows=rows, false_green_rate_10=fg10 / n_g if n_g else None,
                                   false_green_rate_5=fg5 / n_g if n_g else None),
                              ensure_ascii=False, indent=2))
    print(f"saved → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

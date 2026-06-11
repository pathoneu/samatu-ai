"""Experiment 1 (production-level) — FALSE-GREEN RATE on the pozicijos/santrauka
the user actually sees, vs contractor truth.

GREEN unless: a voting low-confidence flag touches the quantity's input rooms,
or a structural fallback fired. WRONG = |err| > 10% (5% reported too).

Usage: venv/bin/python scripts/exp1b_false_green_production.py <voted.json> <slug>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from extractor.universal_rules import calc_room_quantities  # noqa: E402


def poz(extract, needle, exact=False):
    """Sum kiekis over pozicijos whose label matches."""
    tot, found = 0.0, False
    for p in extract.get("pozicijos") or []:
        a = (p.get("aprasymas") or "")
        if (a == needle) if exact else (needle.lower() in a.lower()):
            tot += float(p.get("kiekis") or 0)
            found = True
    return (round(tot, 2) if found else None)


def main():
    extract_path, slug = sys.argv[1], sys.argv[2]
    e = json.load(open(extract_path))
    rooms = e.get("patalpos") or []
    voting = e.get("_voting") or {}
    flags = voting.get("low_confidence_fields") or []
    flagged_rooms = {str(f.get("room")) for f in flags}
    npw = sum(int(r.get("n_partition_walls") or 0) for r in rooms)
    floor = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)

    iki = poz(e, "glaistymas/dažymas (iki 3m") or 0
    virs = poz(e, "glaistymas/dažymas (virš 3m") or 0

    def room_calc(nr, field):
        r = next((x for x in rooms if str(x.get("nr")) == nr), None)
        return round(float(calc_room_quantities(r).get(field) or 0), 2) if r else None

    # (name, app_value, truth, room_sensitive: does it depend on flagged geometry?)
    if slug == "berzas":
        Q = [
            ("floor_total", floor, 165.64, False),
            ("combined_paint", round(iki + virs, 2), 584.81, True),
            ("paint_iki_3m", iki, 371.40, True),
            ("paint_virs_3m", virs, 213.41, True),
            ("kampai", poz(e, "Dažymo kampų montavimas", exact=True), 493.35, True),
            ("led_nisos", poz(e, "Nišų formavimas GKP"), 42.3, False),
            ("angokrasciai_gkp", poz(e, "Angokraščių apdirbimas GKP"), 89.39, False),
            ("durys_beapvadines", poz(e, "beapvadinėms durims"), 39.2, False),
            ("skyliu_grezimas", poz(e, "Skylių gręžimas plytelėse"), 56, False),
            ("silikonavimas_total",
             round((poz(e, "Silikonavimas tarp plytelių") or 0)
                   + (poz(e, "vidinių kampų silikonavimas") or 0), 2), 50.14, False),
            ("pjovimas_45", poz(e, "45° pjovimas"), 9.7, False),
            ("rotband", poz(e, "Rotband"), 138.69, True),
            ("lentyneles", poz(e, "Lentynėlių iš plytelių"), 5, False),
            ("nuolydis", poz(e, "Nuolydžio formavimas"), 2, False),
            ("hidroizoliacija", poz(e, "Hidroizoliacijos įrengimas"), 2, False),
            ("wc_remai", poz(e, "WC rėmo montavimas"), 2, False),
            ("klozetai", poz(e, "Klozeto montavimas"), 2, False),
            ("p105_garazo_walls", room_calc("105", "walls_paintable_m2"), 31.45, True),
            ("p107_plyteles_sienos", room_calc("107", "plyteles_sienos_m2"), 32.73, True),
            ("p107_silikonavimas", room_calc("107", "silikonavimas_m"), 23.64, True),
            ("p101_plyteles_grindys", room_calc("101", "plyteles_grindys_m2"), 8.54, False),
            ("p106_plyteles_grindys", room_calc("106", "plyteles_grindys_m2"), 6.89, False),
            ("p105_plyteles_grindys", room_calc("105", "plyteles_grindys_m2"), 10.1, False),
            ("p107_plyteles_grindys", room_calc("107", "plyteles_grindys_m2"), 6.52, False),
        ]
    else:  # bacveviciaus
        gkp_std = round(sum(float(calc_room_quantities(r).get("gkp_lubu_standart_m2") or 0) for r in rooms), 2)
        gkp_hi = round(sum(float(calc_room_quantities(r).get("gkp_lubu_virs_3m_m2") or 0) for r in rooms), 2)
        Q = [
            ("gkp_lubu_iki3m", gkp_std, 74.91, True),
            ("gkp_lubu_virs3m", gkp_hi, 68.28, True),
            ("led_nisos", poz(e, "Nišų formavimas GKP"), 54.98, False),
            ("angokrasciai_gkp", poz(e, "Angokraščių apdirbimas GKP"), 94.02, False),
            ("rotband", poz(e, "Rotband"), 138.69, True),
            ("combined_paint", round((poz(e, "glaistymas/dažymas (iki 3m") or 0)
                                     + (poz(e, "glaistymas/dažymas (virš 3m") or 0)
                                     + (poz(e, "glaistymas/dažymas”") or 0), 2), 493.03, True),
            ("kampai", poz(e, "Dažymo kampų montavimas", exact=True), 580.54, True),
            ("durys_beapvadines", poz(e, "beapvadinėms durims"), 55.52, False),
            ("skyliu_grezimas", poz(e, "Skylių gręžimas plytelėse"), 109, False),
            ("silikonavimas_total",
             round((poz(e, "Silikonavimas tarp plytelių") or 0)
                   + (poz(e, "vidinių kampų silikonavimas") or 0), 2), 128.97, False),
            ("pjovimas_45", poz(e, "45° pjovimas"), 45.72, False),
            ("hidroizoliacija", poz(e, "Hidroizoliacijos įrengimas"), 3, False),
            ("lentyneles", poz(e, "Lentynėlių iš plytelių"), 3, False),
            ("klozetai_bide", poz(e, "Klozeto montavimas"), 5, False),
            ("praustuvu_maisytuvai", poz(e, "Praustuvės maišytuvo"), 5, False),
            ("duso_maisytuvai", poz(e, "Dušo maišytuvo"), 2, False),
            ("parketas", poz(e, "laminato klojimas"), 108.08, False),
            ("islyginamasis", poz(e, "išlyginamasis sluoksnis"), 143.19, False),
            ("grindjuostes_viso", poz(e, "Grindjuosčių sumontavimas"), 93.8, True),
            ("sviestuvu_apdirbimas", poz(e, "Šviestuvų apdirbimas"), 69, False),
            ("difuzoriu_apdirbimas", poz(e, "Difūzorių apdirbimas"), 20, False),
        ]
        # combined paint fallback: single consolidated line (no height split)
        if not (poz(e, "glaistymas/dažymas (iki 3m") or poz(e, "glaistymas/dažymas (virš 3m")):
            single = poz(e, "lubų glaistymas/dažymas")
            Q = [(n, (single if n == "combined_paint" else v), t, s) for n, v, t, s in Q]

    rows = []
    for name, app, truth, room_sensitive in Q:
        if app is None:
            rows.append(dict(name=name, app=None, truth=truth, err_pct=None,
                             conf="NOT_EMITTED", wrong_10pct=True, wrong_5pct=True))
            continue
        err = (app - truth) / truth * 100
        is_flagged = (room_sensitive and bool(flagged_rooms)) or \
                     (name == "kampai" and npw == 0)
        rows.append(dict(name=name, app=app, truth=truth, err_pct=round(err, 1),
                         conf=("FLAGGED" if is_flagged else "GREEN"),
                         wrong_10pct=abs(err) > 10, wrong_5pct=abs(err) > 5))

    emitted = [r for r in rows if r["conf"] != "NOT_EMITTED"]
    greens = [r for r in emitted if r["conf"] == "GREEN"]
    flagged = [r for r in emitted if r["conf"] == "FLAGGED"]
    fg10 = sum(1 for r in greens if r["wrong_10pct"])
    fg5 = sum(1 for r in greens if r["wrong_5pct"])
    wrong_all = [r for r in emitted if r["wrong_10pct"]]
    fl_wrong = sum(1 for r in flagged if r["wrong_10pct"])

    print(f"\n══ FALSE-GREEN (production outputs) — {slug} ══")
    print(f"voting flags this run: {len(flags)} ({[f.get('room') for f in flags]}) | npw={npw}")
    print(f"{'quantity':24} {'app':>9} {'truth':>9} {'err%':>7}  conf")
    for r in sorted(rows, key=lambda x: -(abs(x["err_pct"]) if x["err_pct"] is not None else 999)):
        mark = "✗" if r["wrong_10pct"] else ("~" if r["wrong_5pct"] else "✓")
        ep = f"{r['err_pct']:+7.1f}" if r["err_pct"] is not None else "   MISS"
        print(f"{r['name']:24} {str(r['app']):>9} {str(r['truth']):>9} {ep}  {r['conf']} {mark}")
    print(f"\nEMITTED: {len(emitted)} | GREEN: {len(greens)} | FLAGGED: {len(flagged)} | NOT_EMITTED: {len(rows)-len(emitted)}")
    if greens:
        print(f"FALSE-GREEN RATE: {fg10}/{len(greens)} = {fg10/len(greens)*100:.0f}% (@10%) ; "
              f"{fg5}/{len(greens)} = {fg5/len(greens)*100:.0f}% (@5%)")
    if flagged:
        print(f"flag precision: {fl_wrong}/{len(flagged)}; error recall by flags: "
              f"{fl_wrong}/{len(wrong_all)}")
    out = Path(extract_path).parent / f"exp1b_production_{slug}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"saved → {out}")


if __name__ == "__main__":
    main()

"""Phase 0 / Phase 2 method reconstruction — families inventory + hypotheses.

Reads the dumps written by run_engine.py and outline_errors.py (in
common.out_dir()) plus his parsed sąmatos and reading_truth.json from the
main checkout. Prints the tables the baseline doc quotes and writes
<out>/analysis.json. Quantities only; codenames only.

    venv/bin/python scripts/method_reconstruction/analyze.py [--mode replay]

Families: every row (his and ours) is put into ONE family by the ordered
regex list FAMILIES on its lower-cased wording; our rows in the „Medžiagos"
section form their own family (he never bills material quantities).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

# (family, regex) — first match wins; order matters (specific before generic)
FAMILIES: list[tuple[str, str]] = [
    ("demontavimas", r"demont|griov|išardym"),
    ("hidroizoliacija", r"hidroizol"),
    ("plytelių angokraščiai / nišos", r"plytel\w*.*angokrašč|angokrašč\w*.*plytel|didžiaformač\w*.*angokrašč"),
    ("angokraščiai", r"angokrašč"),
    ("durų angos beapvadinėms / staktos", r"beapvad|beapvasd|stakt"),
    ("priglaistomi elementai (šviestuvai, difūzoriai, profiliai, durelės)",
     r"priglaist|revizin|difūzorių apdirb|šviestuvų apdirb|track"),
    ("dažymo kampai", r"kampų montavimas|kampų statymas"),
    ("plytelių fugavimas", r"fugav|^siūlių glaist|epoksidiniu glaist"),
    ("silikonavimas", r"silikon"),
    ("grindų danga", r"parket|pvc|laminat|dangos klij|dangos montav"),
    ("plytelių 45° pjovimas", r"plytel\w*.*45|45.*plytel"),
    ("skylės plytelėse", r"skyl\w*.*plytel|plytel\w*.*skyl"),
    ("grindjuosčių dažymas", r"grindjuosč\w* dažym"),
    ("grindjuostės", r"grindjuost|grindjuosč|plintus"),
    ("dušo įrengimas (nuolydis, lentynėlės, latakai, trapai)", r"nuolydž|lentynėl|latak|trapo montav"),
    ("plytelės sienų+grindų (viena eilutė)", r"sienų ir grindų"),
    ("plytelės sienų", r"plytel\w*.*sien|sienų plytel|atatvar"),
    ("plytelės grindų", r"plytel\w*.*grind|grindų plytel"),
    ("plytelės kita (didžiaformatės, mozaika, apsiuvimas)", r"plytel|mozaik"),
    ("išlyginamasis sluoksnis", r"išlyginam|grindų lyginim"),
    ("rotband (sienų lyginimas)", r"rotband|lyginimas sausu"),
    ("GKP / LED nišų glaistymas-dažymas", r"niš\w*.*(glaist|daž)"),
    ("GKP nišų formavimas (LED, karnizai)", r"nišų formavim|led niš|bortel"),
    ("GKP lubos", r"gkp\w* (monatavimas|montavimas) ant lubų|gkp lubų montav"),
    ("GKP kita (pertvaros, dėžutės, apsiuvimai)", r"gkp|gipso kartono|pertvar|karkas|apsiuv|dėžut|dėžuč|niš"),
    ("tapetai / stiklo audinys", r"tapet|stiklo audin"),
    ("gruntas", r"grunt"),
    ("dažymas: sienos+lubos (viena eilutė)", r"sienų, lubų|sienų/ lubų"),
    ("dažymas: lubos", r"^lubų glaist"),
    ("dažymas: sienos", r"^sienų glaist"),
    ("glaistymas atskirai", r"glaist"),
    ("elektros taškai", r"rozet|jungikl|šviestuv|led juost|kabel|automatin|el\. darb|signalizac|termoregul"),
    ("vėdinimas / kondicionavimas", r"rekuper|ortak|difuz|difūz|kondicion|combiflex|sonoduct|optiflex"),
    ("santechnikos taškai", r"maišytuv|\bwc\b|klozet|bide|bidė|praustuv|sifon|gyvatuk|santechnik|plautuv|skalbimo|"
                            r"džiovykl|čiaup|vandens|potinkin|dušo sistem"),
    ("statybvietė", r"šiukšl|pastol|drėgmės|statybvietės|apsaugin|sutvarkym"),
]
PAINT_FAMILIES = ("dažymas: sienos+lubos (viena eilutė)", "dažymas: lubos", "dažymas: sienos")
TILE_FAMILIES = ("plytelės sienų+grindų (viena eilutė)", "plytelės sienų", "plytelės grindų")
WET = ("vonia", "san", "wc", "dusas")
DOOR_KINDS = ("duris", "pasleptos_duris")


def family(name: str, section: str | None = None) -> str:
    s = name.lower()
    if section and re.search(r"rekuper|vėdinim|ventiliac", section.lower()):
        return "vėdinimas / kondicionavimas"   # his ventilation sections bill fittings and diffusers as one trade
    for fam, rx in FAMILIES:
        if re.search(rx, s):
            if fam == "grindjuostės":
                tile = "plytel" in s or (section or "").lower().startswith("plytel")
                return "grindjuostės plytelių" if tile else "grindjuostės (medinės / PVC)"
            return fam
    return "kita"


def unit(u: str | None) -> str:
    s = (u or "").lower().replace(" ", "").rstrip(".")
    if s in ("m2", "m²"):
        return "m²"
    if s in ("m", "b/m", "bv/m", "m/b"):
        return "m"
    if s in ("vnt", "kompl", "komp"):
        return "vnt"
    return s or "?"


def load(mode: str, variant: str) -> dict:
    p = common.out_dir() / f"engine_{mode}_{variant}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ours_rows(entry: dict) -> list[dict]:
    out = []
    for r in entry.get("pozicijos") or []:
        name = str(r.get("aprasymas") or r.get("pavadinimas") or "")
        sec = r.get("skyrius")
        fam = "medžiagos (kiekiai)" if sec == "Medžiagos" else family(name, sec)
        out.append({"name": name, "section": sec, "unit": unit(r.get("vnt")), "quantity": r.get("kiekis"), "family": fam})
    return out


def his_family_rows(folder: str) -> list[dict]:
    rows = []
    for r in common.his_rows(folder):
        rows.append({**r, "unit": unit(r["unit"]), "family": family(r["name"], r.get("section"))})
    return rows


def _sum(rows, fam, u=None):
    xs = [r for r in rows if r["family"] == fam and (u is None or r["unit"] == u)]
    q = [float(r["quantity"]) for r in xs if isinstance(r.get("quantity"), (int, float))]
    return (round(sum(q), 2) if q else None), len(xs)


def inventory(mode: str) -> dict:
    eng = load(mode, "today")
    table: dict[str, dict[str, dict]] = defaultdict(dict)
    his_fams, our_fams = defaultdict(set), defaultdict(set)
    for code, folder in common.projects():
        his = his_family_rows(folder)
        entry = (eng.get("projects") or {}).get(code) or {}
        ours = ours_rows(entry) if entry.get("pozicijos") else None
        fams = {r["family"] for r in his} | ({r["family"] for r in ours} if ours else set())
        for fam in fams:
            hu = sorted({r["unit"] for r in his if r["family"] == fam})
            hq = {u: _sum(his, fam, u) for u in hu}
            cell = {"his": {u: {"q": q, "n": n} for u, (q, n) in hq.items()}}
            if ours is not None:
                ou = sorted({r["unit"] for r in ours if r["family"] == fam})
                cell["ours"] = {u: {"q": q, "n": n} for u, (q, n) in ((u, _sum(ours, fam, u)) for u in ou)}
            table[fam][code] = cell
            if hu:
                his_fams[fam].add(code)
            if ours is not None and cell.get("ours"):
                our_fams[fam].add(code)
    with_extract = {c for c, _ in common.projects() if ((eng.get("projects") or {}).get(c) or {}).get("pozicijos")}
    never_ours = {f: sorted(his_fams[f]) for f in his_fams
                  if not (our_fams.get(f, set()) & his_fams[f] & with_extract) and his_fams[f] & with_extract}
    never_his = {f: sorted(our_fams[f]) for f in our_fams if not his_fams.get(f)}
    return {"table": table, "his_never_ours": never_ours, "ours_never_his": never_his}


# ── hypotheses ────────────────────────────────────────────────────────────────

def paint_compare() -> dict:
    """(i): his paint m² vs ours under each opening threshold, both modes."""
    out: dict = {}
    for mode in ("plain", "replay"):
        for variant in ("today", "open05", "open30", "open_inf"):
            eng = load(mode, variant)
            if not eng:
                continue
            for code, folder in common.projects():
                entry = (eng.get("projects") or {}).get(code) or {}
                if not entry.get("pozicijos"):
                    continue
                his = his_family_rows(folder)
                ours = ours_rows(entry)
                his_walls_only = all(r["family"] != "dažymas: sienos+lubos (viena eilutė)" and r["family"] != "dažymas: lubos"
                                     for r in his) and any(r["family"] == "dažymas: sienos" for r in his)
                fams = ("dažymas: sienos",) if his_walls_only else PAINT_FAMILIES
                hq = sum(_sum(his, f, "m²")[0] or 0 for f in fams)
                oq = sum(_sum(ours, f, "m²")[0] or 0 for f in fams)
                rooms = entry.get("rooms") or []
                o = out.setdefault(code, {"his_m2": round(hq, 2), "scope": "walls only" if his_walls_only else "walls+ceilings"})
                o[f"{mode}/{variant}"] = {
                    "ours_m2": round(oq, 2), "err_pct": round((oq - hq) / hq * 100, 2) if hq else None,
                    "doors_deducted_m2": round(sum(float(r.get("doors_deducted_m2") or 0) for r in rooms), 2),
                    "windows_deducted_m2": round(sum(float(r.get("windows_deducted_m2") or 0) for r in rooms), 2),
                    "walls_anchor": "designer" if any("Sienų glaistymas/dažymas" == r["name"] and r["quantity"] in (220.0, 320.0)
                                                       for r in ours) else None,
                    "rows_within10": (entry.get("scorecard") or {}).get("within_10_share"),
                }
    return out


def _door_counts(folder: str) -> dict[str, dict]:
    """Doors per room from reading_truth.json (counted by eye from the drawing): each pair once in
    one of the two rooms → each room gets every door in its walls; passages listed apart."""
    rt = common.load_json(folder, "reading_truth.json")
    if not rt:
        return {}
    per: dict[str, dict] = defaultdict(lambda: {"doors": 0, "exterior": 0, "passages": 0})
    for nr, p in (rt.get("patalpos") or {}).items():
        for other, n in (p.get("durys") or {}).items():
            per[str(nr)]["doors"] += int(n)
            per[str(other)]["doors"] += int(n)
        per[str(nr)]["exterior"] += int(p.get("durys_lauko") or 0)
        for other, n in (p.get("praejimai") or {}).items():
            per[str(nr)]["passages"] += int(n)
            per[str(other)]["passages"] += int(n)
    return dict(per)


def skirting(mode: str) -> dict:
    """(ii): his skirting rows vs four formulas on the rooms OUR engine skirts."""
    eng = load(mode, "today")
    out = {}
    for code, folder in common.projects():
        his = his_family_rows(folder)
        hrows = [r for r in his if r["family"].startswith("grindjuostės")]
        entry = (eng.get("projects") or {}).get(code) or {}
        if not hrows or not entry.get("rooms"):
            if hrows:
                out[code] = {"his": [(r["name"], r["unit"], r["quantity"]) for r in hrows], "note": "no extract"}
            continue
        dc = _door_counts(folder)
        sets = {"medinės/PVC (engine skirts)": [], "plytelių (tile floor, not fully tiled walls)": []}
        for r in entry["rooms"]:
            if float(r.get("_grindjuosciu_baze_m") or 0) > 0:
                sets["medinės/PVC (engine skirts)"].append(r)
            elif float(r.get("plyteles_grindys_m2") or 0) > 0 and r.get("paskirtis") not in WET:
                sets["plytelių (tile floor, not fully tiled walls)"].append(r)
        res = {"his": [(r["name"], r["unit"], r["quantity"]) for r in hrows], "door_source":
               "reading_truth (eye count)" if dc else "elementai (model's list)", "sets": {}}
        for label, rooms in sets.items():
            P = D_fixed = D_drawn = 0.0
            nd_total = 0
            for r in rooms:
                P += float(r.get("perimetras_m") or 0)
                widths = [float(e.get("plotis_mm") or 0) / 1000 for e in r.get("elementai") or []
                          if isinstance(e, dict) and e.get("tipas") in DOOR_KINDS
                          for _ in range(int(e.get("kiekis") or 1))]
                if dc:
                    c = dc.get(str(r.get("nr"))) or {}
                    nd = int(c.get("doors", 0)) + int(c.get("exterior", 0))
                else:
                    nd = len(widths)
                known = [w for w in widths if w > 0.3]
                mean_w = (sum(known) / len(known)) if known else 0.9
                drawn = known[:nd] + [mean_w] * max(0, nd - len(known))
                nd_total += nd
                D_fixed += 0.90 * nd
                D_drawn += sum(drawn)
            res["sets"][label] = {
                "rooms": [str(r.get("nr")) for r in rooms], "perimeter_m": round(P, 2), "doors": nd_total,
                "P-0.90n": round(P - D_fixed, 2), "P-drawn": round(P - D_drawn, 2),
                "(P-0.90n)x1.10": round((P - D_fixed) * 1.10, 2), "(P-drawn)x1.10": round((P - D_drawn) * 1.10, 2),
                "engine_m": round(sum(float(r.get("grindjuostes_m") or 0) for r in rooms), 2),
            }
        out[code] = res
    return out


def wet_rooms(mode: str) -> dict:
    """(iii): his waterproofing rows vs wet-room counts and areas."""
    eng = load(mode, "today")
    out = {}
    for code, folder in common.projects():
        his = [r for r in his_family_rows(folder) if r["family"] == "hidroizoliacija"]
        entry = (eng.get("projects") or {}).get(code) or {}
        rooms = entry.get("rooms") or []
        wet = [r for r in rooms if r.get("paskirtis") in WET]
        out[code] = {
            "his": [(r["name"], r["unit"], r["quantity"]) for r in his],
            "ours": [(r["name"], r["unit"], r["quantity"]) for r in ours_rows(entry) if r["family"] == "hidroizoliacija"] if rooms else None,
            "wet_rooms": [(str(r.get("nr")), r.get("paskirtis"), r.get("plotas_m2"), r.get("perimetras_m")) for r in wet],
            "n_wet": len(wet),
            # the founder's name markers („Vonia", „WC", „San. mazgas") and the candidates (dušas, tualetas, skalbykla)
            "by_name_core": [str(r.get("nr")) for r in rooms if re.search(r"vonia|vonios|\bwc\b|san\.? ?mazg|san\. ?maz", str(r.get("pavadinimas") or "").lower())],
            "by_name_candidates": [(str(r.get("nr")), r.get("pavadinimas")) for r in rooms
                                   if re.search(r"duš|tualet|skalbykl", str(r.get("pavadinimas") or "").lower())],
            "wet_floor_m2": round(sum(float(r.get("plotas_m2") or 0) for r in wet), 2),
            "wet_perimeter_m": round(sum(float(r.get("perimetras_m") or 0) for r in wet), 2),
            "engine_hidro_m2": round(sum(float(r.get("hidroizoliacija_m2") or 0) for r in rooms), 2),
            "his_tile_walls_m2": _sum(his_family_rows(folder), "plytelės sienų", "m²")[0],
        }
    return out


def waste(mode: str) -> dict:
    """(iv): his floor-covering / tile m² vs the designer's net areas of the rooms that carry them."""
    eng = load(mode, "today")
    out = {}
    for code, folder in common.projects():
        his = his_family_rows(folder)
        entry = (eng.get("projects") or {}).get(code) or {}
        rooms = entry.get("rooms") or []
        if not rooms:
            continue
        tabled = all(r.get("plotas_saltinis") in ("eksplikacija", "plano_uzrasas") for r in rooms)
        soft = [r for r in rooms if float(r.get("pvc_grindys_m2") or 0) > 0]
        tile = [r for r in rooms if float(r.get("plyteles_grindys_m2") or 0) > 0]
        a = lambda rs: round(sum(float(r.get("plotas_m2") or 0) for r in rs), 2)  # noqa: E731
        out[code] = {
            "areas_from_designer": tabled,
            "his_floor_covering_m2": _sum(his, "grindų danga", "m²")[0],
            "net_soft_floor_rooms_m2": a(soft), "net_all_rooms_m2": a(rooms),
            "net_non_wet_rooms_m2": a([r for r in rooms if r.get("paskirtis") not in WET]),
            "his_floor_tiles_m2": _sum(his, "plytelės grindų", "m²")[0],
            "his_wall_tiles_m2": _sum(his, "plytelės sienų", "m²")[0],
            "his_combined_tiles_m2": _sum(his, "plytelės sienų+grindų (viena eilutė)", "m²")[0],
            "net_tile_floor_rooms_m2": a(tile), "net_wet_rooms_m2": a([r for r in rooms if r.get("paskirtis") in WET]),
            "ours_tile_walls_m2": round(sum(float(r.get("plyteles_sienos_m2") or 0) for r in rooms), 2),
            "ours_tile_floors_m2": round(sum(float(r.get("plyteles_grindys_m2") or 0) for r in rooms), 2),
        }
        # his per-room tile figures, where the truth file carries them (his own notes), against the table area
        per = (common.load_json(folder, "truth.json") or {}).get("gt_per_room") or {}
        by_nr = {str(r.get("nr")): r for r in rooms}
        pairs = []
        for nr, facts in per.items():
            v = (facts.get("plyteles_grindys_m2") or {}).get("value") if isinstance(facts, dict) else None
            r = by_nr.get(str(nr))
            if v and r and r.get("plotas_saltinis") in ("eksplikacija", "plano_uzrasas") and r.get("plotas_m2"):
                pairs.append((str(nr), r.get("paskirtis"), float(v), float(r["plotas_m2"]), round(float(v) / float(r["plotas_m2"]), 3)))
        if pairs:
            out[code]["his_per_room_floor_tiles_vs_table"] = pairs
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="replay", help="engine dump the inventory and (ii)–(iv) read")
    a = ap.parse_args()
    res = {"mode": a.mode, "inventory": inventory(a.mode), "paint": paint_compare(),
           "skirting": skirting(a.mode), "wet": wet_rooms(a.mode), "waste": waste(a.mode)}
    p = common.out_dir() / f"analysis_{a.mode}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"→ {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

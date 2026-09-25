#!/usr/bin/env python3
"""Skaitymo lentelė — how well the app READS the drawing, fact by fact (2026-09-24).

The row scorecard (eval_harness --rows) measures the sąmata against the contractor's; this one measures the
READING against the drawing itself: what a person wrote down looking at the plan
(ground_truth/<slug>/reading_truth.json — doors as room↔neighbour pairs, exterior doors, windows,
passages) versus what the engine's rooms carry after the geometry lane and the project-level pass
(universal_rules.prepare_rooms_for_calc: doors stood in the wall openings).

    venv/bin/python scripts/reading_scorecard.py                # every project with a reading_truth.json
    venv/bin/python scripts/reading_scorecard.py objektas_h     # one

Zero API: the cached extract + the fixture PDF (the same inputs eval_harness --recompute --geometry uses).
Prints, per project: interior-door pairs the drawing has vs the list has (matched / missing / extra), exterior
doors, windows and passages per room, and a corpus line. Exit 0 always — it is a measuring stick, not a gate.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import yaml  # noqa: E402

from extractor import universal_rules as ur  # noqa: E402
from extractor.door_schedule import scan_door_schedule  # noqa: E402
from extractor.geometry_lane import apply_geometry  # noqa: E402

_DOOR_KINDS = ("duris", "pasleptos_duris")


def _pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((str(a), str(b))))


def truth_pairs(truth: dict) -> Counter:
    out: Counter = Counter()
    for nr, room in (truth.get("patalpos") or {}).items():
        for other, n in (room.get("durys") or {}).items():
            out[_pair(nr, other)] += int(n)
    return out


def truth_passages(truth: dict) -> Counter:
    out: Counter = Counter()
    for nr, room in (truth.get("patalpos") or {}).items():
        for other, n in (room.get("praejimai") or {}).items():
            out[_pair(nr, other)] += int(n)
    return out


def app_view(rooms: list[dict]) -> dict:
    """What the engine's rooms say after the pass: door pairs (each physical door once), unbacked doors per
    room, exterior doors per room, windows per room, passage pairs."""
    pairs: Counter = Counter()
    unbacked: Counter = Counter()
    unstood: Counter = Counter()                               # doors of rooms whose walls were not read (no lane)
    exterior: Counter = Counter()
    windows: Counter = Counter()
    passages: Counter = Counter()
    unbacked_vidus: Counter = Counter()
    for r in rooms:
        nr = str(r.get("nr") or "").strip()
        walls_read = bool(r.get("_angos_sienose_suderinta"))
        for e in r.get("elementai") or []:
            if not isinstance(e, dict):
                continue
            t = (e.get("tipas") or "").lower()
            if t == "langas":
                windows[nr] += int(e.get("kiekis") or 1)
                continue
            if t not in _DOOR_KINDS:
                continue
            units = ur.door_units_counted(e)                   # a door two rooms list counts once
            if units <= 0:
                continue
            if e.get(ur.EXTERIOR_KEY):
                exterior[nr] += units
            elif e.get(ur.PASSAGE_KEY):
                side = str(e.get(ur.OPENING_SIDE_KEY) or "?")
                passages[_pair(nr, side)] += units
            elif e.get(ur.UNBACKED_KEY):
                unbacked[nr] += units
            elif not walls_read:
                unstood[nr] += units                           # no walls to stand it in — not scored as a pair
            else:
                side = str(e.get(ur.OPENING_SIDE_KEY) or e.get("_is_sienu_angos") or "?")
                if side == "vidus":
                    unbacked_vidus[nr] += units                # a door into a space the table does not number
                elif side in ("laukas", "?", ""):
                    unbacked[nr] += units                      # a door stood in no room's opening is not a pair
                else:
                    pairs[_pair(nr, side)] += units
    return {"pairs": pairs, "unbacked": unbacked, "unstood": unstood, "exterior": exterior, "windows": windows,
            "passages": passages, "unbacked_vidus": unbacked_vidus}


def score_project(slug: str, registry: dict) -> dict | None:
    entry = next((p for p in registry["projects"] if p["slug"] == slug), None)
    truth_path = ROOT / "ground_truth" / slug / "reading_truth.json"
    extract_path = ROOT / "ground_truth" / slug / "ai_extract.json"
    if entry is None or not truth_path.exists() or not extract_path.exists():
        return None
    pdf_path = ROOT / entry["project_pdf"]
    if not pdf_path.exists():
        print(f"  {slug}: PDF not on disk — skipped")
        return None
    truth = json.loads(truth_path.read_text())
    parsed = copy.deepcopy(json.loads(extract_path.read_text()))
    pdf = pdf_path.read_bytes()
    apply_geometry(parsed, pdf)
    rooms = [r for r in parsed.get("patalpos") or [] if isinstance(r, dict)]
    ur.prepare_rooms_for_calc(rooms, overrides={}, door_types=parsed.get("_door_types"), schedule=scan_door_schedule(pdf))
    app = app_view(rooms)
    tp, tpas = truth_pairs(truth), truth_passages(truth)
    matched = sum(min(n, app["pairs"].get(k, 0)) for k, n in tp.items())
    missing = sum(max(0, n - app["pairs"].get(k, 0)) for k, n in tp.items())
    extra = sum(max(0, n - tp.get(k, 0)) for k, n in app["pairs"].items()) + sum(app["unbacked"].values())
    kitur = sum(app["unbacked_vidus"].values())
    # a fact the person could not read unambiguously (`neaisku`) is left out of that fact's count
    ext_truth = {nr: int(r.get("durys_lauko") or 0) for nr, r in truth["patalpos"].items() if "durys_lauko" not in (r.get("neaisku") or [])}
    win_truth = {nr: int(r.get("langai") or 0) for nr, r in truth["patalpos"].items() if "langai" not in (r.get("neaisku") or [])}
    ext_ok = sum(1 for nr, n in ext_truth.items() if app["exterior"].get(nr, 0) == n)
    win_ok = sum(1 for nr, n in win_truth.items() if app["windows"].get(nr, 0) == n)
    pas_matched = sum(min(n, app["passages"].get(k, 0)) for k, n in tpas.items())
    no_walls = sum(app["unstood"].values())
    # doors into a space the table does not number (a garage, a porch): the truth lists them under `durys_kitur`;
    # the engine stands them in an opening „į vidų" — said per room, never scored as a pair (2026-09-25)
    kitur_truth = {nr: sum(int(v) for v in (r.get("durys_kitur") or {}).values()) for nr, r in truth["patalpos"].items() if r.get("durys_kitur")}
    kitur_app = {nr: n for nr, n in app["unbacked_vidus"].items()}
    print(f"\n### {slug} — vidaus durys (poros): brėžinyje {sum(tp.values())}, sąraše sutampa {matched}, "
          f"trūksta {missing}, per daug {extra} (iš jų be angos {sum(app['unbacked'].values())})"
          + (f"; be sienų (juosta neskaitė) {no_walls} durys — poros nevertinamos" if no_walls else "")
          + (f"; į nesunumeruotą erdvę {kitur}" if kitur else "") + "; "
          f"lauko durys sutampa {ext_ok}/{len(ext_truth)} patalpų; langai sutampa {win_ok}/{len(win_truth)} patalpų; "
          f"praėjimai {pas_matched}/{sum(tpas.values())}")
    for k in sorted(set(tp) | set(app["pairs"])):
        t, a = tp.get(k, 0), app["pairs"].get(k, 0)
        mark = "ok" if t == a else ("TRŪKSTA" if a < t else "PER DAUG")
        if t != a:
            print(f"    durys {k[0]}↔{k[1]}: brėžinyje {t}, sąraše {a}  {mark}")
    for nr in sorted(truth["patalpos"], key=lambda s: (len(s), s)):
        e_t, e_a = ext_truth.get(nr), app["exterior"].get(nr, 0)
        w_t, w_a = win_truth.get(nr), app["windows"].get(nr, 0)
        u = app["unbacked"].get(nr, 0)
        k_t, k_a = kitur_truth.get(nr), kitur_app.get(nr, 0)
        bad_e = e_t is not None and e_t != e_a
        bad_w = w_t is not None and w_t != w_a
        bad_k = (k_t or 0) != k_a
        if bad_e or bad_w or u or bad_k:
            print(f"    {nr}: lauko durys {'?' if e_t is None else e_t}→{e_a}, langai {'?' if w_t is None else w_t}→{w_a}"
                  + (f", durys be angos {u}" if u else "")
                  + (f", durys į nesunumeruotą erdvę {k_t or 0}→{k_a}" if bad_k or k_t else ""))
    return {"slug": slug, "pairs_truth": sum(tp.values()), "matched": matched, "missing": missing, "extra": extra,
            "ext_ok": ext_ok, "ext_n": len(ext_truth), "win_ok": win_ok, "win_n": len(win_truth),
            "pas_matched": pas_matched, "pas_truth": sum(tpas.values())}


def main() -> int:
    registry = yaml.safe_load((ROOT / "ground_truth" / "registry.yaml").read_text())
    slugs = sys.argv[1:] or sorted(p.parent.name for p in (ROOT / "ground_truth").glob("*/reading_truth.json"))
    results = [r for r in (score_project(s, registry) for s in slugs) if r]
    if not results:
        print("no project with a reading_truth.json")
        return 0
    pairs = sum(r["pairs_truth"] for r in results)
    print("\n=== Skaitymo lentelė — korpusas ===")
    print(f"  vidaus durų poros: {sum(r['matched'] for r in results)}/{pairs} sutampa, "
          f"{sum(r['missing'] for r in results)} trūksta, {sum(r['extra'] for r in results)} per daug")
    print(f"  lauko durys per patalpą: {sum(r['ext_ok'] for r in results)}/{sum(r['ext_n'] for r in results)} sutampa")
    print(f"  langai per patalpą: {sum(r['win_ok'] for r in results)}/{sum(r['win_n'] for r in results)} sutampa")
    print(f"  praėjimai: {sum(r['pas_matched'] for r in results)}/{sum(r['pas_truth'] for r in results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

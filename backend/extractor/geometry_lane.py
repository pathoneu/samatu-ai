"""Step 2.44d of the extraction: geometry READ from the drawing — no Vision.

Order: locate the rooms (area label → number badge → Vision's box) → which
plan sheets are the same plan → scale per sheet from the dimension strings →
outlines from the vector walls for the rooms that have no precise outline yet
(the raster outline lane keeps its turn before this one in vision_call; an
outline a person corrected is never replaced) → perimeters by ADDING the
strings written along those outlines' walls, from every sheet of the plan.

What it leaves on a room: `_vieta`; `polygon_pct` + `polygon_source =
"vektoriniai_konturai"` + `_konturas`, or `_konturo_priezastis`; for an open
plan `_atvira_erdve` {nariai, polygon_pct, plotas_m2, perimetras_m,
lenteles_suma_m2, page} — the shared outline, never an invented cut — and a
perimeter that is the room's share (by floor area) of the shared space's
real walls, marked as an ESTIMATE (`perimetras_saltinis =
"atviros_erdves_ivertis"`); and what
dimension_sum writes (`_sienos`, `_perimetras_suma`, a stated perimeter or the
outline's length marked `konturo_ivertis`, with its reason). An estimate is a
number — the sąmata rows are built from `perimetras_m` — that the check sheet
shows as a BLANK with the number to accept. The figure a stated or
blanked perimeter replaces is kept as `_perimetras_pries_geometrija`. A room
the lane cannot place or outline is left exactly as it was.

Last, the FLOOR COVERING the floor plan draws in each room (2026-09-20,
extractor/floor_coverings.py): `grindu_danga` + `grindu_danga_saltinis =
"grindu_planas"` + `_grindu_danga` {page, irodymas, tekstas, plotas_m2,
rect_pct}; `_grindu_dangos_dvi` when the sheet writes two kinds of covering in
one room. His own choice (`user_override`) is never touched.

`_meta.geometrija` says how many rooms came from where. Never raises.
"""
from __future__ import annotations

import time
from typing import Sequence

from .dimension_sum import ESTIMATE_SOURCE, KEEP as STATED_PERIMETERS, sum_perimeters
from .floor_coverings import find_floor_sheets, read_floor_coverings
from .pdf_vectors import page_geometry
from .plan_area_annotations import plan_pages_from_classification
from .plan_dimensions import read_dimension_strings
from .room_locator import locate_rooms
from .sheet_alignment import align_sheets, from_base, to_base
from .vector_rooms import SOURCE as VECTOR_SOURCE, STRONG, trace_vector_rooms

KEEP_POLYGONS = ("sienu_konturas", "corrected", "manual", VECTOR_SOURCE)
OPEN_PLAN_ESTIMATE = "atviros_erdves_ivertis"
ESTIMATES = (ESTIMATE_SOURCE, OPEN_PLAN_ESTIMATE)
_PT_M = 25.4 / 72 / 1000          # metres per PDF point at 1:1


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


FLOOR_PLAN_SOURCE = "grindu_planas"
FLOOR_KEYS = ("grindu_danga", "grindu_danga_saltinis", "_grindu_danga")


def _read_floor_coverings(rooms, pdf_bytes, sheets, alignment, lay_over, scale, sizes, meta) -> None:
    """Which covering the FLOOR PLAN draws in each room (extractor/floor_coverings.py).

    The rooms are laid onto the floor sheet the way their outlines are laid onto
    the wall-painting sheet: a wall-exact or human outline when the room has one,
    otherwise the place of its printed number — and only a place that was READ
    (a badge, an area label), never Vision's box. His own choice is never
    touched; a reading that is gone on this run is taken back."""
    floor_sheets = find_floor_sheets(pdf_bytes, sheets)
    meta["grindu_dangos"]["lapai"] = floor_sheets
    read: dict[str, dict] = {}
    two: dict[str, dict] = {}
    if floor_sheets:
        al = alignment
        if any(p not in (al.get("transform") or {}) for p in floor_sheets):
            al = lay_over(sorted(set(al.get("transform") or {}) | set(floor_sheets)))
        group_of = {p: i for i, g in enumerate(al["groups"]) for p in g}
        for fp in floor_sheets:
            if fp not in sizes or fp not in group_of:
                continue
            W, H = sizes[fp]

            def onto(page: int, x_pct: float, y_pct: float):
                if page == fp:
                    return x_pct * W, y_pct * H
                if page not in sizes or group_of.get(page) != group_of[fp]:
                    return None
                bx, by = to_base(al, page, x_pct * sizes[page][0], y_pct * sizes[page][1])
                return from_base(al, fp, bx, by)

            asked = []
            for r in rooms:
                nr = _nr(r)
                if nr in read:
                    continue
                polygon = point = None
                poly = r.get("polygon_pct")
                if str(r.get("polygon_source") or "") in KEEP_POLYGONS and isinstance(poly, list) and len(poly) >= 3:
                    page = int((r.get("_konturas") or {}).get("page") or r.get("puslapio_nr") or 0)
                    pts = [onto(page, float(x), float(y)) for x, y in poly]
                    if all(q is not None for q in pts):
                        polygon = [[q[0], q[1]] for q in pts]
                v = r.get("_vieta")
                if polygon is None and isinstance(v, dict) and v.get("saltinis") in STRONG:
                    q = onto(int(v["page"]), float(v["cx"]), float(v["cy"]))
                    if q is not None:
                        point = (q[0], q[1])
                if polygon is not None or point is not None:
                    asked.append({"nr": nr, "polygon": polygon, "point": point})
            got = read_floor_coverings(pdf_bytes, fp, asked, m_per_pt=scale.get(fp))
            read.update(got["rooms"])
            for nr, texts in got["dvi_dangos"].items():
                two.setdefault(nr, {"page": fp, "tekstai": list(texts)})
    for r in rooms:
        nr = _nr(r)
        if nr in two and nr not in read:
            r["_grindu_dangos_dvi"] = two[nr]
        else:
            r.pop("_grindu_dangos_dvi", None)
        if str(r.get("grindu_danga_saltinis") or "") == "user_override":
            continue
        hit = read.get(nr)
        if hit:
            r["grindu_danga"] = hit["danga"]
            r["grindu_danga_saltinis"] = FLOOR_PLAN_SOURCE
            r["_grindu_danga"] = {k: hit[k] for k in ("page", "irodymas", "tekstas", "plotas_m2", "rect_pct")}
            meta["grindu_dangos"]["perskaityta"][nr] = hit["danga"]
        elif str(r.get("grindu_danga_saltinis") or "") == FLOOR_PLAN_SOURCE:
            for key in FLOOR_KEYS:
                r.pop(key, None)
    meta["grindu_dangos"]["dvi_dangos"] = sorted(nr for nr in two if nr not in read)


def apply_geometry(parsed: dict, pdf_bytes: bytes, dims: Sequence[dict] | None = None) -> dict:
    t0 = time.time()
    meta: dict = {"vietos": {}, "grupes": [], "sutapdinimas": {}, "lapai": [], "konturai": [], "konturu_priezastys": {}, "atviros_erdves": [],
                  "perimetrai_sudeti": [], "perimetrai_tusti": [],
                  "grindu_dangos": {"lapai": [], "perskaityta": {}, "dvi_dangos": []}, "seconds": 0.0}
    status = "insufficient"
    try:
        rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict) and _nr(r)]
        plan_pages = plan_pages_from_classification(parsed.get("puslapiai"))
        if not plan_pages:
            plan_pages = sorted({int(r["puslapio_nr"]) for r in rooms if r.get("puslapio_nr")}) or [1]
        if dims is None:
            dims = read_dimension_strings(pdf_bytes, pages=None)
        # Which sheets belong to the plan is decided by ALIGNMENT — the same walls in the same place —
        # not by the page classifier (objektas_g, 2026-09-10: the dimensioned sheet was called something
        # else and every wall was lost; two of its outlines were traced on the plumbing plan). So every
        # sheet that carries line-backed strings, or an earlier lane's outline, is a candidate.
        traced_on = {int(r["_konturas"]["page"]) for r in rooms if isinstance(r.get("_konturas"), dict) and r["_konturas"].get("page")}
        dimensioned = {int(d["page"]) for d in dims if d.get("span_source") == "line"}
        sheets = sorted(set(plan_pages) | traced_on | dimensioned)
        scale: dict[int, float] = {}
        for d in dims:
            if d.get("scale_m_per_pt"):
                scale.setdefault(int(d["page"]), float(d["scale_m_per_pt"]))

        where = locate_rooms(pdf_bytes, rooms, plan_pages)
        for r in rooms:
            v = where.get(_nr(r))
            if v:
                r["_vieta"] = v
                meta["vietos"][v["saltinis"]] = meta["vietos"].get(v["saltinis"], 0) + 1

        def lay_over(pages: Sequence[int]) -> dict:
            """Align these sheets; a sheet without strings of its own takes its plan's scale."""
            al = align_sheets(pdf_bytes, sorted(pages))
            for group in al["groups"]:
                known = next((p for p in group if p in scale), None)
                if known is None:
                    continue
                per_base_pt = scale[known] / (al["transform"][known]["k"] or 1.0)
                for p in group:
                    scale.setdefault(p, per_base_pt * (al["transform"][p]["k"] or 1.0))
            return al

        # Laying sheets over each other means reading every sheet's walls — seconds per heavy sheet
        # (objektas_b: 19 dimensioned sheets, 17 s). The rooms' own sheets come first; the rest are read
        # only when there is an outline whose walls their strings could state.
        anchors = {int(v["page"]) for v in where.values()} | traced_on
        everything = any(p not in scale for p in anchors)      # an anchor sheet with no strings needs its plan's scale
        alignment = lay_over(sheets if everything else anchors)

        areas = {_nr(r): float(r.get("plotas_m2") or 0) for r in rooms}
        sizes: dict[int, tuple[float, float]] = {}
        for d in dims:                                        # the strings already carry their sheet's size — no parsing
            if d.get("page_width") and d.get("page_height"):
                sizes.setdefault(int(d["page"]), (float(d["page_width"]), float(d["page_height"])))
        for p in sheets:
            if p not in sizes:
                W, H, _ = page_geometry(pdf_bytes, p)
                if W > 0 and H > 0:
                    sizes[p] = (W, H)
        for group in alignment["groups"]:
            located = [r for r in rooms if r.get("_vieta") and int(r["_vieta"]["page"]) in group]
            todo = {_nr(r) for r in located if str(r.get("polygon_source") or "") not in KEEP_POLYGONS}
            if not todo:
                continue
            # ONE sheet of the plan is traced: where most of the rooms still to do were found. Every located
            # room of the plan is laid onto it (a neighbour owns its face there) — only `todo` is written.
            on_page: dict[int, int] = {}
            for r in located:
                if _nr(r) in todo:
                    on_page[int(r["_vieta"]["page"])] = on_page.get(int(r["_vieta"]["page"]), 0) + 1
            page = max(sorted(on_page), key=lambda p: on_page[p])
            if page not in scale or page not in sizes:
                continue
            W, H = sizes[page]
            everyone = {}
            for r in located:
                v = r["_vieta"]
                q = int(v["page"])
                if q == page:
                    everyone[_nr(r)] = v
                elif q in sizes:
                    bx, by = to_base(alignment, q, float(v["cx"]) * sizes[q][0], float(v["cy"]) * sizes[q][1])
                    x, y = from_base(alignment, page, bx, by)
                    everyone[_nr(r)] = {**v, "page": page, "cx": x / W, "cy": y / H}
            res = trace_vector_rooms(pdf_bytes, page, everyone, areas, scale[page], (W, H))
            meta["lapai"].append(page)
            for r in rooms:
                nr = _nr(r)
                if nr not in todo:
                    continue
                hit = res["rooms"].get(nr)
                if hit:
                    r["polygon_pct"] = hit["polygon_pct"]
                    r["polygon_source"] = VECTOR_SOURCE
                    r["_konturas"] = {"page": page, "plotas_m2": hit["plotas_m2"], "perimetras_m": hit["perimetras_m"],
                                      "plotas_uzrasas_m2": areas.get(nr), "paklaida": hit["paklaida"],
                                      "plotas_nesutampa": hit["plotas_nesutampa"], "sujungta": hit["sujungta"],
                                      "durys_m": hit["durys_m"], "saltinis": VECTOR_SOURCE}
                    r.pop("_konturo_priezastis", None)
                    meta["konturai"].append(nr)
                elif nr in res["reasons"]:
                    r["_konturo_priezastis"] = res["reasons"][nr]
                    meta["konturu_priezastys"][nr] = res["reasons"][nr]
            for g in res["groups"]:
                meta["atviros_erdves"].append(g["nariai"])
                members = [r for r in rooms if _nr(r) in g["nariai"]]
                total_area = sum(areas.get(_nr(r)) or 0 for r in members)
                for r in members:
                    if _nr(r) not in todo:
                        continue
                    r["_atvira_erdve"] = dict(g)
                    # The shared space's walls are real; each room's share of them is written nowhere.
                    # The share by floor area is the ESTIMATE the walls are computed with — blank, reason,
                    # a number to accept. objektas_h: the rooms' guessed perimeters gave 340 m² of painted
                    # wall, this gives 320,3 m² — the designer's own legend on that drawing says 320 m².
                    if str(r.get("perimetras_saltinis") or "") in STATED_PERIMETERS and r.get("perimetras_m"):
                        continue
                    if total_area <= 0 or not (areas.get(_nr(r)) or 0) > 0:
                        continue
                    others = ", ".join(n for n in g["nariai"] if n != _nr(r))
                    if r.get("perimetras_m") is not None and r.get("perimetras_saltinis") not in ESTIMATES:
                        r.setdefault("_perimetras_pries_geometrija", r["perimetras_m"])
                    share = round(g["perimetras_m"] * areas[_nr(r)] / total_area, 2)
                    r["perimetras_m"] = share                  # a number the rows can use; the SOURCE says it is an estimate
                    r["perimetras_saltinis"] = OPEN_PLAN_ESTIMATE
                    r["_perimetras_ivertis_m"] = share
                    r["_perimetras_ivertis_saltinis"] = "atviros_erdves_konturas"
                    r["_perimetras_priezastis"] = (f"atvira erdvė su {others} — sienos šių patalpų neskiria; bendras erdvės sienų ilgis "
                                                   f"{g['perimetras_m']:.2f} m padalytas pagal plotą").replace(".", ",")
                    meta["perimetrai_tusti"].append(_nr(r))

        outlined = any(str(r.get("polygon_source") or "") in KEEP_POLYGONS for r in rooms)
        if outlined and not everything:
            alignment = lay_over(sheets)
        meta["grupes"] = alignment["groups"]
        # how the plan's sheets lie over each other (sheet → its base, in page fractions of the BASE) — the
        # check sheet shows a room's outline on the sheet its numbers are written on
        for p, t in sorted(alignment["transform"].items()):
            base = int(t.get("base", p))
            if p not in sizes or base not in sizes:
                continue
            meta["sutapdinimas"][str(p)] = {"base": base, "k": round(float(t["k"]), 5),
                                            "kx": round(float(t["k"]) * sizes[p][0] / sizes[base][0], 6),
                                            "ky": round(float(t["k"]) * sizes[p][1] / sizes[base][1], 6),
                                            "dx_pct": round(float(t["dx"]) / sizes[base][0], 6),
                                            "dy_pct": round(float(t["dy"]) / sizes[base][1], 6)}
        # the sheets' scales, exact from their own dimension lines — for the viewer's measuring tools
        meta["masteliai"] = {str(p): {"m_per_pt": round(v, 6), "mastelis": int(round(v / _PT_M))} for p, v in sorted(scale.items())}

        before = {_nr(r): (r.get("perimetras_m") if r.get("perimetras_saltinis") not in ESTIMATES else None) for r in rooms}
        done = sum_perimeters(rooms, dims, alignment, scale, page_sizes=sizes)
        meta["perimetrai_sudeti"] = done["stated"]
        meta["perimetrai_tusti"] = sorted(set(meta["perimetrai_tusti"]) | set(done["blank"]))
        for r in rooms:
            nr = _nr(r)
            if nr in done["stated"] or nr in done["blank"]:
                old = before.get(nr)
                if old is not None and str(r.get("perimetras_saltinis") or "") not in [s for s in STATED_PERIMETERS if s != "matmenu_eilutes"]:
                    r.setdefault("_perimetras_pries_geometrija", old)
        _read_floor_coverings(rooms, pdf_bytes, sheets, alignment, lay_over, scale, sizes, meta)
        if meta["konturai"] or done["stated"] or meta["grindu_dangos"]["perskaityta"]:
            status = "applied"
        elif rooms:
            status = "no_match"
    except Exception as exc:  # noqa: BLE001 — a lane must never sink the extraction
        status = "failed"
        meta["error"] = repr(exc)
        print(f"[extractor] geometry lane failed: {exc!r}")
    meta["seconds"] = round(time.time() - t0, 2)
    if isinstance(parsed, dict):
        parsed.setdefault("_meta", {})["geometrija"] = meta
    return {"status": status, **meta}

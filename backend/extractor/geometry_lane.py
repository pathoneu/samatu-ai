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
lenteles_suma_m2, page} — the shared outline, never an invented cut; and what
dimension_sum writes (`_sienos`, `_perimetras_suma`, a stated perimeter or a
blank one with its reason and the outline's estimate). The figure a stated or
blanked perimeter replaces is kept as `_perimetras_pries_geometrija`. A room
the lane cannot place or outline is left exactly as it was.

`_meta.geometrija` says how many rooms came from where. Never raises.
"""
from __future__ import annotations

import time
from typing import Sequence

from .dimension_sum import KEEP as STATED_PERIMETERS, sum_perimeters
from .pdf_vectors import page_geometry
from .plan_area_annotations import plan_pages_from_classification
from .plan_dimensions import read_dimension_strings
from .room_locator import locate_rooms
from .sheet_alignment import align_sheets, from_base, to_base
from .vector_rooms import SOURCE as VECTOR_SOURCE, trace_vector_rooms

KEEP_POLYGONS = ("sienu_konturas", "corrected", "manual", VECTOR_SOURCE)


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def apply_geometry(parsed: dict, pdf_bytes: bytes, dims: Sequence[dict] | None = None) -> dict:
    t0 = time.time()
    meta: dict = {"vietos": {}, "grupes": [], "lapai": [], "konturai": [], "konturu_priezastys": {}, "atviros_erdves": [],
                  "perimetrai_sudeti": [], "perimetrai_tusti": [], "seconds": 0.0}
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

        alignment = align_sheets(pdf_bytes, sheets)
        meta["grupes"] = alignment["groups"]
        for group in alignment["groups"]:                     # a sheet without strings of its own takes its plan's scale
            known = next((p for p in group if p in scale), None)
            if known is None:
                continue
            per_base_pt = scale[known] / (alignment["transform"][known]["k"] or 1.0)
            for p in group:
                scale.setdefault(p, per_base_pt * (alignment["transform"][p]["k"] or 1.0))

        areas = {_nr(r): float(r.get("plotas_m2") or 0) for r in rooms}
        sizes: dict[int, tuple[float, float]] = {}
        for p in sheets:
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
                for r in rooms:
                    if _nr(r) in g["nariai"] and _nr(r) in todo:
                        r["_atvira_erdve"] = dict(g)

        before = {_nr(r): r.get("perimetras_m") for r in rooms}
        done = sum_perimeters(rooms, dims, alignment, scale, page_sizes=sizes)
        meta["perimetrai_sudeti"], meta["perimetrai_tusti"] = done["stated"], done["blank"]
        for r in rooms:
            nr = _nr(r)
            if nr in done["stated"] or nr in done["blank"]:
                old = before.get(nr)
                if old is not None and str(r.get("perimetras_saltinis") or "") not in [s for s in STATED_PERIMETERS if s != "matmenu_eilutes"]:
                    r.setdefault("_perimetras_pries_geometrija", old)
        if meta["konturai"] or done["stated"]:
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

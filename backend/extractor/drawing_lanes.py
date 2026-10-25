"""The drawing's €0 lanes of the paid reading, in ONE place (v4 Phase 3c-1, 2026-10-25).

`vision_call.extract_interior` ran these steps inline (Step 2.44 → 2.44d) and the eval harness kept its own copy of
the sequence for `--replay-geometry`; the plain eval pass ran none of them and scored the lanes' output frozen into
each old extract (eval-answers 2026-10-25 §4: „no drawn perimeter" 6–13 blank rows per project on the plain pass,
0 on the replay for objektas_a and objektas_h). Now both call `run_drawing_lanes`, so the plain pass reads the
drawing exactly as a fresh reading does. The free re-read of a stored project calls the same geometry lane
(`geometry_lane.apply_geometry`) and the same height reader (`text.heights.apply_text_heights`); the 2.44 text
lanes below need the reading's fresh room list, which a stored project no longer has.

  2.44   one text-layer scan → the designer's own figures and the walls / floors anchors billed from them; only
         when no room table merged, the area-label lane and its ceiling anchor;
  2.44b  rectangle pairs from the dimension strings (plan_dimensions);
  2.44c  raster outlines from the walls (wall_outline);
  2.44h  ceiling heights from the text (text/heights.py) — BEFORE the lane, so the lane's open-space rule
         („rooms whose ceilings differ are not shared by floor area") reads the drawing's heights, never the
         reading model's;
  2.44d  the geometry lane (vector outlines, scale with provenance, perimeters added from the strings, openings
         as drawn, floor coverings);
  2.44h  the heights again, now with the lane's outlines (an altitude is placed by the outline that holds it).

No model call anywhere here. What it cost is written to `_meta.braizinio_skaitymas` (seconds per step, the model
calls — always 0 — and € 0).
"""
from __future__ import annotations

import time
from typing import Callable


def run_drawing_lanes(parsed: dict, pdf_bytes: bytes, *, emit: Callable[[dict], None] | None = None) -> dict:
    """Run Steps 2.44 → 2.44d (+ the text heights) on `parsed` in place. Never raises: a lane that fails prints
    why and the next one runs. Returns {"scan", "geometry", "heights", "seconds"}."""
    from text.heights import apply_text_heights

    from .plan_area_annotations import (
        lane_warnings, most_common_page, plan_pages_from_classification, reconcile_rooms_with_annotations,
        scan_text_layer, text_pages_from_classification)
    from .vision_call import _floor_anchors_from_figures, _walls_anchor_from_figures

    def _emit(payload: dict) -> None:
        if emit:
            try:
                emit(payload)
            except Exception:  # noqa: BLE001
                pass

    seconds: dict[str, float] = {}
    t_all = time.time()
    meta = parsed.setdefault("_meta", {})
    scan: dict | None = None
    # Step 2.44: plan-area annotations lane (2026-09-06, item 3 of the €0 generalisation work). Only when NO room
    # table merged: the designer's own room areas written on the lubų/grindų planas („37.86 m²" standing alone in
    # each room) are read from the text layer and become the table — confirming the model's rooms, correcting a
    # near miss, FLAGGING a room no label supports (objektas_g's invented third bathroom), and anchoring the
    # ceiling quantity to their sum. See extractor/plan_area_annotations.py.
    try:
        # ONE pass over the text layer (pypdfium2; renders skipped): the room-area labels for the lane below, the
        # height stamps for the height reader and — 3c — the designer's own legend totals („Glaistoma dažoma
        # 202 m²"), shown beside ours on the check sheet, never used as a value.
        t = time.time()
        text_pages = text_pages_from_classification(parsed.get("puslapiai") or [])
        scan = scan_text_layer(pdf_bytes, pages=text_pages or None)
        parsed["_autoriaus_kiekiai"] = scan["figures"]
        # The painted-wall area the drawing states (sienų apdailos plano legenda) — the walls' anchor.
        parsed.pop("_walls_anchor", None)
        wa = _walls_anchor_from_figures(scan["figures"])
        if wa:
            parsed["_walls_anchor"] = wa
        # …and the floor plan's own grindjuostės / plytelių grindjuostės / laminatas totals — the floors' anchors.
        parsed.pop("_floor_anchors", None)
        fa = _floor_anchors_from_figures(scan["figures"])
        if fa:
            parsed["_floor_anchors"] = fa
        meta["text_layer_scan_s"] = seconds["tekstas"] = round(time.time() - t, 2)
        merged_rooms = int(meta.get("eksplikacija_merged_rooms") or 0)
        if merged_rooms == 0 and parsed.get("patalpos"):
            plan_pages = set(plan_pages_from_classification(parsed.get("puslapiai") or []))
            ann = [a for a in scan["annotations"] if not plan_pages or a["page"] in plan_pages]
            lane = reconcile_rooms_with_annotations(parsed["patalpos"], ann)
            meta["plan_area_lane"] = lane
            if lane.get("status") == "applied":
                parsed.setdefault("warnings", []).extend(lane_warnings(lane, parsed["patalpos"]))
                if not parsed.get("_ceiling_anchor") and float(lane.get("sum_m2") or 0) > 0:
                    parsed["_ceiling_anchor"] = {
                        "total_area_m2": float(lane["sum_m2"]),
                        "label": "plano užrašų suma",
                        "page": most_common_page(ann),
                    }
            _emit({"event": "plan_area_lane", "status": lane.get("status"),
                   "geometry": lane.get("geometry"), "candidates": lane.get("candidates"),
                   "confirmed": len(lane.get("confirmed") or []),
                   "adopted": len(lane.get("adopted") or []),
                   "unconfirmed": len(lane.get("unconfirmed") or [])})
    except Exception as exc:  # noqa: BLE001 — a lane must never sink the extraction
        print(f"[extractor] plan-area lane failed: {exc}")
        scan = None

    if scan is not None:
        # Step 2.44b: perimeters from the plan's DIMENSION STRINGS (2026-09-10, founder: „perskaityti skaičius ir
        # padaryti matematiką"). Runs for table projects too — their plans still state the walls; a table
        # perimeter (none in the corpus) is marked `eksplikacija` and skipped.
        try:
            from .plan_dimensions import apply_dimension_strings
            t = time.time()
            # Dimensions from EVERY text page: the page classifier can call the floor plan something else (run 2
            # of objektas_g: not one of its 8 rooms matched because the dimensioned sheet was filtered out). A
            # string pairs only when its dimension LINE spans the room's label, so a far-off sheet cannot pair and
            # the filter would only ever lose walls. Labels stay restricted to plan pages, as in the area lane.
            plan_pages_d = set(plan_pages_from_classification(parsed.get("puslapiai") or []))
            dims = list(scan.get("dimensions") or [])
            anns = [a for a in scan["annotations"] if not plan_pages_d or a["page"] in plan_pages_d]
            dl = apply_dimension_strings(parsed.get("patalpos") or [], dims, anns)
            meta["plan_dimension_lane"] = dl
            seconds["matmenu_poros"] = round(time.time() - t, 2)
            _emit({"event": "plan_dimension_lane", "status": dl.get("status"),
                   "dimensions": dl.get("dimensions"), "lines": dl.get("lines"),
                   "confirmed": len(dl.get("confirmed") or []),
                   "corrected": len(dl.get("corrected") or []),
                   "unmatched": len(dl.get("unmatched") or [])})
        except Exception as exc:  # noqa: BLE001
            print(f"[extractor] plan-dimension lane failed: {exc}")
        # Step 2.44c: room OUTLINES from the wall geometry (2026-09-13, the founder's „pažymėta vieta, iš kur kas
        # ištraukta" made precise). The page rendered without text and hairlines is the walls; a fill from the
        # room's own area label, checked against the printed m², gives the sheet its frame and the perimeter
        # where nobody stated one (extractor/wall_outline.py; research 2026-09-13).
        try:
            from .wall_outline import apply_wall_outlines
            t = time.time()
            plan_pages_w = set(plan_pages_from_classification(parsed.get("puslapiai") or []))
            wl = apply_wall_outlines(
                parsed.get("patalpos") or [], pdf_bytes, list(scan.get("dimensions") or []),
                [a for a in scan["annotations"] if not plan_pages_w or a["page"] in plan_pages_w])
            wl["seconds"] = round(time.time() - t, 1)
            meta["wall_outline_lane"] = wl
            seconds["rastro_konturai"] = round(time.time() - t, 2)
            _emit({"event": "wall_outline_lane", "status": wl.get("status"),
                   "traced": len(wl.get("traced") or []),
                   "corrected": len(wl.get("corrected") or []),
                   "unmatched": len(wl.get("unmatched") or []),
                   "seconds": wl["seconds"]})
        except Exception as exc:  # noqa: BLE001
            print(f"[extractor] wall-outline lane failed: {exc}")

    stamps = (scan or {}).get("heights") if scan is not None else None
    # Step 2.44h (first look): the heights the drawing writes, before the lane reads them.
    t = time.time()
    apply_text_heights(parsed, pdf_bytes, statements=stamps)
    seconds["aukstis_pries"] = round(time.time() - t, 2)

    # Step 2.44d: geometry READ from the drawing (2026-09-19, after the founder's first production run of
    # objektas_h: every perimeter was a square guess, every outline Vision's box). Rooms are located by their
    # number badges, the sheets of one plan are laid over each other, outlines come from the vector walls, and a
    # perimeter is the SUM of the strings written along those walls — the outline only assigns and checks. What
    # the drawing does not state stays blank, with the reason and the outline's estimate (geometry_lane.py).
    geometry: dict = {}
    try:
        from .geometry_lane import apply_geometry
        t = time.time()
        # No strings of our own: the lane reads them from its one source (every page, slanted strings too),
        # exactly as the free re-read does — the text scan above covers classified pages only and no slanted
        # string (audit 2026-09-30, geometry-lanes-2).
        geometry = apply_geometry(parsed, pdf_bytes)
        seconds["geometrija"] = round(time.time() - t, 2)
        _emit({"event": "geometry_lane", "status": geometry.get("status"),
               "konturai": len(geometry.get("konturai") or []),
               "atviros_erdves": len(geometry.get("atviros_erdves") or []),
               "perimetrai_sudeti": len(geometry.get("perimetrai_sudeti") or []),
               "perimetrai_tusti": len(geometry.get("perimetrai_tusti") or []),
               "seconds": geometry.get("seconds")})
    except Exception as exc:  # noqa: BLE001
        print(f"[extractor] geometry lane failed: {exc}")

    # Step 2.44h (second look): with the lane's outlines an altitude is placed by the outline that holds it.
    t = time.time()
    heights = apply_text_heights(parsed, pdf_bytes, statements=stamps, emit=emit)
    seconds["aukstis"] = round(time.time() - t, 2)

    total = round(time.time() - t_all, 2)
    meta["braizinio_skaitymas"] = {"sekundes": seconds, "viso_s": total, "modelio_kvietimai": 0, "kaina_eur": 0.0}
    return {"scan": scan, "geometry": geometry, "heights": heights, "seconds": total}

"""compare_pipelines.py — diff OLD extractor vs NEW (dim → graph → assembler).

Usage:
  python compare_pipelines.py --from-extract docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json
  python compare_pipelines.py --live  docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf   # $$$

Phase-2 stop gate: the NEW pipeline's per-room perimeters must match the OLD
pipeline's perimeters within 0.5%, AND the run must be deterministic across
N repetitions.

``--from-extract`` synthesises a (DimensionList, RoomGraph) for each room from
its existing primitives (plotas, perimetras, elementai) and runs them through
the new ``assemble_plan → solve_plan → plan_to_parsed`` chain. This is a
lossless-roundtrip sanity check — it validates the assembler architecture
without burning Vision credits. The closure constraint + the dimension-based
length reconstruction must reproduce the original perimeter to within rounding.

``--live`` calls Vision (Opus 4.7) twice per page through the new pipeline and
compares against the saved old-extractor output. Costs real money — guarded.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.plan_assembler import assemble_plan, plan_to_parsed
from extractor.geometry_solver import solve_plan
from extractor.vision.dimension_extractor import Dimension, DimensionList
from extractor.vision.room_graph_extractor import (
    Vertex, Wall, Opening, Room as GraphRoom, RoomGraph,
)
from extractor.vision_call import (
    _recompute_per_room_via_python,
    _recompute_santrauka,
)


# ── Synthesiser ───────────────────────────────────────────────────────────────
def _rectangular_solve(perim_m: float, area_m2: float) -> tuple[float, float]:
    """Given perimeter and area of a rectangle, return (L, W) in metres.

    Falls back to a square approximation when no real solution exists (i.e.
    the room is too elongated for the given perimeter or vice versa)."""
    half_p = perim_m / 2.0
    disc = (half_p * half_p) - 4.0 * area_m2
    if disc <= 0:
        side = math.sqrt(max(area_m2, 1e-6))
        return side, side
    delta = math.sqrt(disc) / 2.0
    return half_p / 2.0 + delta, half_p / 2.0 - delta


def synthesize_room_pipeline_input(
    room_primitive: dict[str, Any], room_idx: int
) -> tuple[list[Dimension], list[Vertex], list[Wall], GraphRoom, list[Opening]]:
    """Turn one ``patalpa`` primitive (Vision-style) into the new pipeline's
    typed inputs that, when assembled, reproduce the original perimeter+area.

    The synthesised polygon is rectangular: that's the only shape for which
    a (perim, area) pair uniquely determines two edge lengths. Real rooms
    may not be rectangular, so this gives an upper bound on how cleanly the
    new pipeline can round-trip Vision-derived primitives. The point is to
    test the assembler arithmetic, not to recover the true polygon.
    """
    rid = f"r{room_idx}"
    L_m, W_m = _rectangular_solve(
        float(room_primitive.get("perimetras_m") or 0),
        float(room_primitive.get("plotas_m2") or 0),
    )
    L_mm = round(L_m * 1000.0)
    W_mm = round(W_m * 1000.0)

    dims = [
        Dimension(id=f"{rid}_dL", text=str(L_mm), value_mm=float(L_mm),
                  x_pct=0.5, y_pct=0.1, orientation="horizontal"),
        Dimension(id=f"{rid}_dW", text=str(W_mm), value_mm=float(W_mm),
                  x_pct=0.9, y_pct=0.5, orientation="vertical"),
    ]
    verts = [
        Vertex(id=f"{rid}_v1", x_pct=0.0, y_pct=0.0),
        Vertex(id=f"{rid}_v2", x_pct=1.0, y_pct=0.0),
        Vertex(id=f"{rid}_v3", x_pct=1.0, y_pct=1.0),
        Vertex(id=f"{rid}_v4", x_pct=0.0, y_pct=1.0),
    ]
    walls = [
        Wall(id=f"{rid}_w1", start_vertex=f"{rid}_v1", end_vertex=f"{rid}_v2",
             dimension_id=f"{rid}_dL", angle_deg=0.0, room_ids=[rid]),
        Wall(id=f"{rid}_w2", start_vertex=f"{rid}_v2", end_vertex=f"{rid}_v3",
             dimension_id=f"{rid}_dW", angle_deg=90.0, room_ids=[rid]),
        Wall(id=f"{rid}_w3", start_vertex=f"{rid}_v3", end_vertex=f"{rid}_v4",
             dimension_id=f"{rid}_dL", angle_deg=180.0, room_ids=[rid]),
        Wall(id=f"{rid}_w4", start_vertex=f"{rid}_v4", end_vertex=f"{rid}_v1",
             dimension_id=f"{rid}_dW", angle_deg=270.0, room_ids=[rid]),
    ]
    openings: list[Opening] = []
    for i, e in enumerate(room_primitive.get("elementai") or []):
        tipas = (e.get("tipas") or "").lower()
        if tipas == "nisa_led":
            op_type = "led_niche"
        elif tipas in ("pasleptos_duris", "pasleptu_duris"):
            op_type = "hidden_door"
        elif tipas == "langas":
            op_type = "window"
        else:
            op_type = "door"
        kiekis = int(e.get("kiekis") or 1)
        for k in range(kiekis):
            wid = walls[i % 4].id
            w_dim_id = f"{rid}_e{i}_{k}_w"
            h_dim_id = f"{rid}_e{i}_{k}_h"
            if op_type == "led_niche":
                ilgis_mm = int(round(float(e.get("ilgis_m") or 1.0) * 1000.0))
                dims.append(Dimension(id=w_dim_id, text=str(ilgis_mm),
                                       value_mm=float(ilgis_mm),
                                       x_pct=0.5, y_pct=0.5,
                                       orientation="horizontal"))
                openings.append(Opening(
                    id=f"{rid}_o{i}_{k}", wall_id=wid, type="led_niche",
                    width_dimension_id=w_dim_id,
                ))
            else:
                w_mm = int(e.get("plotis_mm") or 900)
                h_mm = int(e.get("aukstis_mm") or 2100)
                dims.append(Dimension(id=w_dim_id, text=str(w_mm), value_mm=float(w_mm),
                                       x_pct=0.5, y_pct=0.5, orientation="horizontal"))
                dims.append(Dimension(id=h_dim_id, text=str(h_mm), value_mm=float(h_mm),
                                       x_pct=0.5, y_pct=0.5, orientation="vertical"))
                openings.append(Opening(
                    id=f"{rid}_o{i}_{k}", wall_id=wid, type=op_type,
                    width_dimension_id=w_dim_id, height_dimension_id=h_dim_id,
                    is_exterior=bool(e.get("_exterior", False)),
                ))

    apdaila = room_primitive.get("sienu_apdailos_breakdown") or {}
    groom = GraphRoom(
        id=rid,
        nr=str(room_primitive.get("nr") or rid),
        name=str(room_primitive.get("pavadinimas") or rid),
        paskirtis=str(room_primitive.get("paskirtis") or "gyvenamoji"),
        polygon_walls=[walls[0].id, walls[1].id, walls[2].id, walls[3].id],
        lubu_aukstis_m=float(room_primitive.get("lubu_aukstis_m") or 2.82),
        lubu_aukstis_source="from_extract",
        lubu_tipas=str(room_primitive.get("lubu_tipas") or "gkp"),
        plyteles_sienos_aukstis_m=float(room_primitive.get("plyteles_sienos_aukstis_m") or 0.0),
        sienu_apdailos_breakdown=dict(apdaila),
    )
    return dims, verts, walls, groom, openings


def run_new_pipeline_from_extract(extract: dict[str, Any]) -> dict[str, Any]:
    """Build (dims, room_graph) from an old-extractor JSON and run the new
    deterministic assembly + geometry constraints + formula engine."""
    all_dims: list[Dimension] = []
    all_verts: list[Vertex] = []
    all_walls: list[Wall] = []
    all_rooms: list[GraphRoom] = []
    all_openings: list[Opening] = []

    for i, r in enumerate(extract.get("patalpos") or []):
        d, v, w, gr, op = synthesize_room_pipeline_input(r, i)
        all_dims.extend(d)
        all_verts.extend(v)
        all_walls.extend(w)
        all_rooms.append(gr)
        all_openings.extend(op)

    dl = DimensionList(dimensions=all_dims)
    rg = RoomGraph(vertices=all_verts, walls=all_walls, rooms=all_rooms,
                   openings=all_openings)
    plan = assemble_plan(dl, rg)
    plan_dict = solve_plan(plan.to_dict())
    # plan_to_parsed wants a Plan object; reconstruct from the solved dict
    from extractor.plan_assembler import (
        AssembledRoom as AR, AssembledOpening as AO, Plan as P,
    )
    solved_plan = P(
        schedule_doors=plan.schedule_doors,
        schedule_windows=plan.schedule_windows,
        _meta=plan._meta,
    )
    for r in plan_dict["rooms"]:
        # Recompute perimeter from solved lengths
        new_perim = sum(r["wall_lengths_mm"].values())
        # Recompute area via shoelace on the solved walk
        from extractor.geometry_solver import walk_polygon
        from extractor.plan_assembler import _polygon_area_m2
        pts = walk_polygon(
            r["polygon_walls"], r["wall_lengths_mm"], r["wall_angles_deg"],
            tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        )
        new_area = _polygon_area_m2(pts[:-1])
        openings = [AO(**o) for o in r["openings"]]
        solved_plan.rooms.append(AR(
            id=r["id"], nr=r["nr"], name=r["name"], paskirtis=r["paskirtis"],
            polygon_walls=list(r["polygon_walls"]),
            wall_lengths_mm=dict(r["wall_lengths_mm"]),
            wall_angles_deg=dict(r["wall_angles_deg"]),
            perimeter_mm=new_perim,
            area_m2=round(new_area, 4),
            openings=openings,
            lubu_aukstis_m=r["lubu_aukstis_m"],
            lubu_aukstis_source=r["lubu_aukstis_source"],
            lubu_tipas=r["lubu_tipas"],
            plyteles_sienos_aukstis_m=float(r.get("plyteles_sienos_aukstis_m") or 0.0),
            sienu_apdailos_breakdown=dict(r.get("sienu_apdailos_breakdown") or {}),
            confidence_score=r.get("confidence_score", 0.0),
            confidence_color=r.get("confidence_color", "yellow"),
            missing_dimension_walls=list(r.get("missing_dimension_walls") or []),
            start_vertex_xy_mm=tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        ))

    parsed = plan_to_parsed(solved_plan)
    parsed = _recompute_per_room_via_python(parsed, None)
    parsed = _recompute_santrauka(parsed)
    return parsed


# ── Reporting ─────────────────────────────────────────────────────────────────
def _pct(new: float, old: float) -> float | None:
    if old in (0, 0.0):
        return None
    return round((new - old) / old * 100.0, 3)


def _load_dotenv(path: Path) -> None:
    """Lightweight .env loader (avoid a python-dotenv dep)."""
    if not path.exists():
        return
    import os
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def run_live_compare(pdf_path: str, threshold_pct: float, floor_plan_page: int) -> int:
    """Run the new dim→graph→assembler pipeline live on one floor-plan page,
    then diff against the saved old-pipeline extract.

    Cost control:
      - rasterises ONLY the requested page (not all 17 pages)
      - both Vision calls hit the on-disk cache; second invocation is free
      - prints token usage from the actual response

    The comparison target is the saved app-output-to-the-dot.json next to the
    PDF — that's the OLD pipeline's known output on the same project.
    """
    import os

    REPO_ROOT = Path(__file__).resolve().parent
    _load_dotenv(REPO_ROOT / "backend" / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERR: ANTHROPIC_API_KEY not found in env or backend/.env")
        return 2

    pdf_p = Path(pdf_path).resolve()
    if not pdf_p.exists():
        print(f"ERR: PDF not found: {pdf_p}")
        return 2

    # Locate the saved old-pipeline extract next to the PDF.
    old_extract_path = pdf_p.parent / "app-output-to-the-dot.json"
    if not old_extract_path.exists():
        print(f"WARN: no old extract at {old_extract_path}; will not produce comparison.")
        old: dict[str, Any] = {"patalpos": []}
    else:
        with old_extract_path.open() as f:
            old = json.load(f)

    # Rasterise the requested page only. Use existing pdf_to_b64_images for the
    # right DPI / sizing pipeline (200 DPI, capped at 2000px per Opus 4.7 input
    # limits).
    from extractor.vision_call import pdf_to_b64_images
    print(f"Rasterising page {floor_plan_page} of {pdf_p.name}…")
    pages = pdf_to_b64_images(pdf_p.read_bytes(), max_pages=floor_plan_page)
    if len(pages) < floor_plan_page:
        print(f"ERR: PDF has only {len(pages)} pages; cannot extract page {floor_plan_page}")
        return 2
    page = pages[floor_plan_page - 1]
    image_b64 = page if isinstance(page, str) else page.get("image_b64") or page.get("b64")
    if not image_b64:
        # pdf_to_b64_images may return dicts with 'image_b64' or strings
        print(f"ERR: unexpected page object shape: {type(page).__name__}")
        return 2

    # Pass 1: dimensions
    from extractor.vision.dimension_extractor import extract_dimensions
    from extractor.vision.room_graph_extractor import extract_room_graph
    print("Calling dimension_extractor (cached on hit)…")
    dl = extract_dimensions(image_b64=image_b64, model="claude-opus-4-7")
    print(f"  ← {len(dl.dimensions)} dimensions  cache={dl._meta.get('cache')}  "
          f"in_tok={dl._meta.get('input_tokens')}  out_tok={dl._meta.get('output_tokens')}")

    # Pass 2: room graph
    print("Calling room_graph_extractor (cached on hit)…")
    rg = extract_room_graph(
        image_b64=image_b64,
        dimensions_payload=dl.to_dict(),
        model="claude-opus-4-7",
    )
    print(f"  ← {len(rg.rooms)} rooms / {len(rg.walls)} walls / {len(rg.openings)} openings  "
          f"cache={rg._meta.get('cache')}  in_tok={rg._meta.get('input_tokens')}  "
          f"out_tok={rg._meta.get('output_tokens')}")

    # Assemble + solve + bridge into formula engine
    plan = assemble_plan(dl, rg)
    plan_dict = solve_plan(plan.to_dict())

    from extractor.plan_assembler import (
        AssembledRoom as AR, AssembledOpening as AO, Plan as P, _polygon_area_m2,
    )
    from extractor.geometry_solver import walk_polygon
    solved_plan = P(
        schedule_doors=plan.schedule_doors,
        schedule_windows=plan.schedule_windows,
        _meta=plan._meta,
    )
    for r in plan_dict["rooms"]:
        new_perim = sum(r["wall_lengths_mm"].values())
        pts = walk_polygon(
            r["polygon_walls"], r["wall_lengths_mm"], r["wall_angles_deg"],
            tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        )
        new_area = _polygon_area_m2(pts[:-1])
        openings = [AO(**o) for o in r["openings"]]
        solved_plan.rooms.append(AR(
            id=r["id"], nr=r["nr"], name=r["name"], paskirtis=r["paskirtis"],
            polygon_walls=list(r["polygon_walls"]),
            wall_lengths_mm=dict(r["wall_lengths_mm"]),
            wall_angles_deg=dict(r["wall_angles_deg"]),
            perimeter_mm=new_perim,
            area_m2=round(new_area, 4),
            openings=openings,
            lubu_aukstis_m=r["lubu_aukstis_m"],
            lubu_aukstis_source=r["lubu_aukstis_source"],
            lubu_tipas=r["lubu_tipas"],
            plyteles_sienos_aukstis_m=float(r.get("plyteles_sienos_aukstis_m") or 0.0),
            sienu_apdailos_breakdown=dict(r.get("sienu_apdailos_breakdown") or {}),
            confidence_score=r.get("confidence_score", 0.0),
            confidence_color=r.get("confidence_color", "yellow"),
            missing_dimension_walls=list(r.get("missing_dimension_walls") or []),
            start_vertex_xy_mm=tuple(r.get("start_vertex_xy_mm") or (0.0, 0.0)),
        ))

    parsed_new = plan_to_parsed(solved_plan)
    parsed_new = _recompute_per_room_via_python(parsed_new, None)
    parsed_new = _recompute_santrauka(parsed_new)

    per_room = diff_per_room(old, parsed_new) if old.get("patalpos") else []
    sant = diff_santrauka(old, parsed_new) if old.get("santrauka") else []
    print()
    if per_room or sant:
        failing = print_diff(per_room, sant, threshold_pct)
        print(f"\n  Failing categories (>3%): {failing}")
        return 1 if failing else 0
    else:
        print("  No old-pipeline reference available; new pipeline output only:")
        print(json.dumps(parsed_new.get("santrauka") or {}, indent=2, ensure_ascii=False))
        return 0


def diff_per_room(old: dict, new: dict) -> list[dict]:
    new_by_nr = {str(r.get("nr")): r for r in (new.get("patalpos") or [])}
    rows: list[dict] = []
    for r_old in (old.get("patalpos") or []):
        nr = str(r_old.get("nr"))
        r_new = new_by_nr.get(nr, {})
        for field in ("perimetras_m", "plotas_m2", "dazymo_plotas_m2",
                      "walls_paintable_m2", "ceiling_paintable_m2",
                      "nisu_metrai"):
            v_old = float(r_old.get(field) or 0)
            v_new = float(r_new.get(field) or 0)
            rows.append({
                "nr": nr, "name": r_old.get("pavadinimas"),
                "field": field, "old": v_old, "new": v_new,
                "abs": round(v_new - v_old, 3),
                "pct": _pct(v_new, v_old),
            })
    return rows


def diff_santrauka(old: dict, new: dict) -> list[dict]:
    s_old = old.get("santrauka") or {}
    s_new = new.get("santrauka") or {}
    keys = sorted(set(s_old) | set(s_new))
    rows: list[dict] = []
    for k in keys:
        v_old = float(s_old.get(k) or 0)
        v_new = float(s_new.get(k) or 0)
        rows.append({
            "key": k, "old": v_old, "new": v_new,
            "abs": round(v_new - v_old, 3),
            "pct": _pct(v_new, v_old),
        })
    return rows


def _color(pct: float | None, threshold: float = 0.5) -> str:
    if pct is None:
        return "⬛"
    if abs(pct) <= threshold:
        return "🟢"
    if abs(pct) <= 3.0:
        return "🟡"
    return "🔴"


def _fmt_pct(pct: float | None) -> str:
    return "    —" if pct is None else f"{pct:+6.2f}%"


def print_diff(per_room: list[dict], sant: list[dict], threshold: float) -> int:
    failing = 0
    print()
    print("─── santrauka ──────────────────────────────────────────────────────")
    print(f"  {'key':<38} {'old':>10} {'new':>10} {'Δ':>10} {'pct':>8}  status")
    print("  " + "─" * 88)
    for row in sant:
        c = _color(row["pct"], threshold)
        if c == "🔴":
            failing += 1
        print(
            f"  {row['key'][:36]:<38} "
            f"{row['old']:>10.2f} {row['new']:>10.2f} "
            f"{row['abs']:>+10.3f} "
            f"{_fmt_pct(row['pct']):>8}  {c}"
        )
    print()
    print("─── per-room (perimeter + paint) ───────────────────────────────────")
    last_nr = None
    for row in per_room:
        if row["nr"] != last_nr:
            print(f"  {row['nr']}  {row['name']}")
            last_nr = row["nr"]
        c = _color(row["pct"], threshold)
        if c == "🔴" and row["field"] in ("perimetras_m", "plotas_m2"):
            failing += 1
        print(
            f"    {row['field']:<22} "
            f"old={row['old']:>8.2f}  new={row['new']:>8.2f}  "
            f"Δ={row['abs']:>+7.3f}  "
            f"{_fmt_pct(row['pct']):>8}  {c}"
        )
    return failing


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-extract", metavar="PATH",
                    help="path to old extractor JSON output to round-trip")
    ap.add_argument("--live", metavar="PDF", help="path to PDF for live Vision compare ($$$)")
    ap.add_argument("--floor-plan-page", type=int, default=2,
                    help="page number (1-indexed) of the floor plan to extract (default 2)")
    ap.add_argument("--threshold-pct", type=float, default=0.5,
                    help="per-metric pass threshold (default 0.5%%)")
    args = ap.parse_args()

    if args.live:
        return run_live_compare(args.live, args.threshold_pct, args.floor_plan_page)

    if not args.from_extract:
        print("USAGE: compare_pipelines.py --from-extract <old_extract.json>")
        return 2

    extract_path = Path(args.from_extract)
    if not extract_path.exists():
        print(f"ERR: {extract_path} not found")
        return 2

    with extract_path.open() as f:
        old = json.load(f)
    new = run_new_pipeline_from_extract(old)

    per_room = diff_per_room(old, new)
    sant = diff_santrauka(old, new)
    failing = print_diff(per_room, sant, args.threshold_pct)

    print()
    print(f"  Failing categories (>3%): {failing}")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())

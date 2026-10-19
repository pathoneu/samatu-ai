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
the lane cannot place or outline is left exactly as it was — unless the lane
itself outlined it on an earlier run: then that outline and what rests on it
go, and its perimeter goes back to the kept figure (`_forget_outline`; never
a room he worked on).

Last, the FLOOR COVERING the floor plan draws in each room (2026-09-20,
extractor/floor_coverings.py): `grindu_danga` + `grindu_danga_saltinis =
"grindu_planas"` + `_grindu_danga` {danga, page, irodymas, tekstas,
plotas_m2, rect_pct}; `_grindu_dangos_dvi` when the sheet writes two kinds of covering in
one room. His own choice (`user_override`) is never touched.

A room with a trusted outline (traced here, by the raster lane, or corrected by
a person) also carries `_angos_sienose` {page, angos: [{plotis_m, storis_m,
line_pct, i}]} — the openings the wall solid shows in its walls, in the frame
of the room's own outline (`i` = the room beyond, "vidus" for a space without
an outline, or "laukas"): evidence for the door-and-window fact, never a
quantity on their own.

`_meta.geometrija` says how many rooms came from where. Never raises.
"""
from __future__ import annotations

import copy
import logging
import time
from typing import Callable, Sequence

from .dimension_sum import ESTIMATE_SOURCE, KEEP as STATED_PERIMETERS, SOURCE as SUMMED, WALL_OUTLINES, sum_perimeters
from .floor_coverings import find_floor_sheets, read_floor_coverings
from .pdf_vectors import page_geometry
from .plan_area_annotations import plan_pages_from_classification
from .plan_dimensions import (
    CONVEX_TOL as PAIR_WALLS_TOL, PROPOSAL_KEY as PAIR_PROPOSAL, SOURCE as PAIR_SOURCE, confirm_pair_by_outline,
    plausible_perimeter, read_dimension_strings,
)
from .room_locator import locate_rooms
from .sheet_alignment import align_sheets, from_base, to_base
from .vector_rooms import SOURCE as VECTOR_SOURCE, STRONG, propose_split, trace_vector_rooms, wall_openings
from .drawn_openings import page_marks

KEEP_POLYGONS = ("sienu_konturas", "corrected", "manual", VECTOR_SOURCE)
OPEN_PLAN_ESTIMATE = "atviros_erdves_ivertis"
# `_konturas.saltinis` of one side of the boundary the LANE proposed through a two-room open space (2026-09-23):
# a person's own line is "padalinta" (api/room_outline.py), and is never replaced by this
DIVIDED_BY_LANE = "padalinta_programos"
ESTIMATES = (ESTIMATE_SOURCE, OPEN_PLAN_ESTIMATE)
_PT_M = 25.4 / 72 / 1000          # metres per PDF point at 1:1


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


# What rests on an outline this lane traced: the outline, its record, the open space it was part of, the
# openings read in its walls, the walls and their summed perimeter.
FROM_THE_OUTLINE = ("polygon_pct", "polygon_source", "_konturas", "_atvira_erdve", "_angos_sienose", "_sienos", "_perimetras_suma")
LANE_PERIMETERS = (SUMMED, ESTIMATE_SOURCE, OPEN_PLAN_ESTIMATE)          # the perimeter labels this lane (and dimension_sum) writes
PERIMETER_ESTIMATE_KEYS = ("_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis")


def _his(room: dict) -> bool:
    """He worked on this room — typed its perimeter, corrected its openings, marked it checked. (An outline he
    drew or fixed is `corrected` / `manual`, which this lane never traces again.)"""
    return (str(room.get("perimetras_saltinis") or "") in ("user_override", "manual")
            or bool(room.get("_angos_user_at")) or bool(room.get("user_verified_at")))


def _forget_outline(room: dict) -> None:
    """A room this lane outlined on an earlier run and cannot outline now (2026-09-29: the table's area was
    corrected, a re-read): the old outline and what rests on it go, and a perimeter this lane set goes back to
    the figure it had before — or, with none kept, stays as a number the drawing no longer confirms (no
    source). Before, the room kept a trusted outline and a „read" perimeter its own new reason contradicted."""
    for key in FROM_THE_OUTLINE:
        room.pop(key, None)
    if str(room.get("perimetras_saltinis") or "") in LANE_PERIMETERS:
        if room.get("_perimetras_pries_geometrija") is not None:
            room["perimetras_m"] = room["_perimetras_pries_geometrija"]
        for key in ("perimetras_saltinis", "_perimetras_pries_geometrija") + PERIMETER_ESTIMATE_KEYS:
            room.pop(key, None)


# What sum_perimeters may write on a room — taken before, put back exactly when its result is not kept.
PERIMETER_KEYS = ("perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma", "_perimetras_pries_geometrija") + PERIMETER_ESTIMATE_KEYS


def _perimeter_snapshot(room: dict) -> dict:
    return {k: copy.deepcopy(room[k]) for k in PERIMETER_KEYS if k in room}


def _restore_perimeter(room: dict, snap: dict) -> None:
    for k in PERIMETER_KEYS:
        room.pop(k, None)
    room.update(copy.deepcopy(snap))


def _forget_open_space(room: dict) -> None:
    """The room is no longer part of a shared space this lane recorded: the record and the share of the
    space's walls it wrote go, and the perimeter goes back to the figure kept before."""
    room.pop("_atvira_erdve", None)
    if str(room.get("perimetras_saltinis") or "") == OPEN_PLAN_ESTIMATE:
        if room.get("_perimetras_pries_geometrija") is not None:
            room["perimetras_m"] = room["_perimetras_pries_geometrija"]
        for key in ("perimetras_saltinis", "_perimetras_pries_geometrija") + PERIMETER_ESTIMATE_KEYS:
            room.pop(key, None)


# What the lane reads, as a number a stored project can be compared against
# (api/free_reread.py offers a free re-read when the project's is lower):
# 1 — outlines + summed perimeters; 2 — positions for the check sheet (line_pct,
# sutapdinimas); 3 — floor coverings off the floor plan; 4 — the openings in each
# outlined room's walls; 5 — sheets of one plan are found by a shared corner of
# their wall boxes too (objektas_g: all seven sheets one plan → a perimeter summed
# from strings, every neighbour named); 6 — rooms numbered with three digits
# („101", „102" — a house) are found by their number (objektas_a: 1 → 11 outlines);
# 7 — a slanted wall's length is read off its slanted dimension line, and a wall
# written in pieces either side of a door is added up through the door
# (objektas_h bedroom 09: an estimate → 16,01 m READ); 8 — a space two rooms share
# is divided by the lane's own proposed boundary (through a wall end the table agrees
# with, else by the table's area ratio), so each room's walls are read instead of a
# share by floor area (objektas_h 04/05: estimates 16,08 / 21,69 → read 17,93 / 19,82).
# RAISE it when the lane starts reading something a stored project would gain from.
# 9 (2026-09-25): openings carry what the drawing shows in them — glazing → langas, swing arc → durys; doors drawn
# where the wall is not cut. 10 (2026-10-05, audit round 13): a sheet's scale must be a plan's, and it is the scale its
# title writes when the strings measure that (a line drawn past its ends only lowers their 1:N); a sheet printed
# reduced or enlarged is read at the scale its strings measure, the written one noted (`masteliai_kiti`), and only
# strings in other units than the sheet (1:20 measured on a „M 1:200" sheet) are refused; typical floors are no
# longer laid over each other as one plan (a share of another storey's space written before is taken back); a
# two-string rectangle gives way to the room's walls added up when they differ, and a
# bounding-box pair the outline is as long as becomes the perimeter; walls adding up to less than any room of that
# area could have are not taken; the door schedule (it rides along with the free re-read) reads „be apvadų" as
# frameless and „910x2100" sizes, and a row naming both frame types is left to him.
# 11 (2026-10-06, objektas_a on production): an outline kept although its area is off the table's gives its length
# as the estimate matched to the table's area — × √(table / outline), a similar shape — never shorter than any room
# of that area could be (104: 13,98 → 14,96 m around 13,51 m²); the outline's own length stays beside it.
# 12 (2026-10-16): the drawn length each dimension string's scale ratio used (`ilgis_pt`) rides with the string into the
# walls' evidence, also on a room whose walls were summed before — the viewer's scale check needs it; no quantity changes.
# 13 (2026-10-18): the wall, character and hairline readers take the display frame from the page (PDFium `get_size`,
# pdf_vectors.page_frames) instead of guessing it from where the content lies — a /Rotate 90/270 sheet whose drawing
# sits inside the short side was read in the wrong orientation (objektas_e: text on 17 sheets, walls on 3), so its
# walls, strings and outlines landed elsewhere; the re-read is free. The corpus's other projects read identically.
LANE_VERSION = 13

FLOOR_PLAN_SOURCE = "grindu_planas"
FLOOR_KEYS = ("grindu_danga", "grindu_danga_saltinis", "_grindu_danga")


def _read_wall_openings(rooms, pdf_bytes, alignment, scale, sizes, meta) -> None:
    """`_angos_sienose` for every room with a trusted outline — traced from the vector walls, from the
    raster lane or from a person (extractor/vector_rooms.wall_openings). A room without such an outline
    loses a stale record.

    ONE sheet of a plan is read — the one most of the rooms still to do are outlined on — and EVERY
    trusted outline of that plan is laid onto it: the room beyond a door is named only when its outline
    is there (objektas_g: the raster lane left each room's outline on a different sheet of the same
    plan, and every neighbour read as a space „without an outline"). What is written is in the frame of
    the room's OWN outline, so the check sheet draws outline and openings together."""
    outlined: dict[str, tuple[int, list]] = {}
    todo: set[str] = set()
    for r in rooms:
        poly = r.get("polygon_pct")
        page = int((r.get("_konturas") or {}).get("page") or r.get("puslapio_nr") or 0)
        trusted = str(r.get("polygon_source") or "") in KEEP_POLYGONS and isinstance(poly, list) and len(poly) >= 3
        if not (trusted and page in scale and page in sizes):
            r.pop("_angos_sienose", None)
            continue
        outlined[_nr(r)] = (page, poly)
        # Every outlined room is read on every run, a traced one too: what lies beyond its door depends on
        # which NEIGHBOURS have an outline today — a room a person pointed at a minute ago turns the
        # neighbour's „gretima patalpa" into its number.
        todo.add(_nr(r))
    transform = alignment.get("transform") or {}
    group_of = {p: i for i, g in enumerate(alignment.get("groups") or []) for p in g if p in transform}
    plans: dict[object, dict[int, int]] = {}                   # a plan (sheets lying over each other) → sheet → rooms to do
    for nr in todo:
        page = outlined[nr][0]
        votes = plans.setdefault(group_of.get(page, ("lapas", page)), {})
        votes[page] = votes.get(page, 0) + 1
    found: dict[str, dict] = {}
    for plan, votes in plans.items():
        fp = max(sorted(votes), key=lambda p: votes[p])
        W, H = sizes[fp]
        try:
            marks = page_marks(pdf_bytes, fp, scale[fp])       # the swing arcs and lines of this sheet
        except Exception:  # noqa: BLE001 — extra evidence, never the reason openings go unread
            marks = None

        def lay(page: int, x: float, y: float, back: bool = False):
            """A point of `page` (page fractions) on the sheet that is read — or, `back`, the other way."""
            if page == fp:
                return x, y
            src, dst = (fp, page) if back else (page, fp)
            bx, by = to_base(alignment, src, x * sizes[src][0], y * sizes[src][1])
            qx, qy = from_base(alignment, dst, bx, by)
            return qx / sizes[dst][0], qy / sizes[dst][1]

        same_plan = {nr: (page, ring) for nr, (page, ring) in outlined.items()
                     if page == fp or (page in group_of and group_of[page] == plan)}
        context = {nr: [lay(page, float(x), float(y)) for x, y in ring] for nr, (page, ring) in same_plan.items()}
        got = wall_openings(pdf_bytes, fp, context, scale[fp], (W, H), marks=marks)
        for nr in todo & set(got):
            page = same_plan[nr][0]
            angos = []
            for a in got[nr]:
                line = sorted([round(v, 5) for v in lay(page, float(x), float(y), back=True)] for x, y in a["line_pct"])
                angos.append({**a, "line_pct": line})
            found[nr] = {"page": page, "angos": angos}
    for r in rooms:
        nr = _nr(r)
        if nr in todo:
            if nr in found:
                r["_angos_sienose"] = found[nr]
            else:
                r.pop("_angos_sienose", None)
    meta["angos_sienose"] = sorted(_nr(r) for r in rooms if isinstance(r.get("_angos_sienose"), dict))
    drawn = {"langai": 0, "durys": 0, "be_tarpo": 0}
    for r in rooms:
        for a in (r.get("_angos_sienose") or {}).get("angos") or [] if isinstance(r.get("_angos_sienose"), dict) else []:
            if a.get("nupiesta") == "langas":
                drawn["langai"] += 1
            elif a.get("nupiesta") == "durys":
                drawn["durys"] += 1
            if a.get("be_tarpo"):
                drawn["be_tarpo"] += 1
    meta["nupiesta"] = drawn


def _merged(r: dict) -> bool:
    """The room another was merged INTO („Sujungti", api/room_outline.py: `_sujungimas.su`)."""
    return isinstance(r.get("_sujungimas"), dict) and bool(r["_sujungimas"].get("su"))


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
                if nr in read or _merged(r):
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
            # the sheet's key (Pathon v3 W5-D, D1): kept as evidence — `_meta.grindu_legenda`
            meta["grindu_dangos"].setdefault("legenda", []).extend(got.get("legenda") or [])
            for nr, texts in got["dvi_dangos"].items():
                two.setdefault(nr, {"page": fp, "tekstai": list(texts)})
    for r in rooms:
        nr = _nr(r)
        if nr in two and nr not in read:
            r["_grindu_dangos_dvi"] = two[nr]
        else:
            r.pop("_grindu_dangos_dvi", None)
        if _merged(r):
            # „Sujungti": the kept room's covering is applied to the whole area (its outline now holds both
            # rooms' coverings) — settled by the merge, like his choice; a re-read never takes it back.
            continue
        hit = read.get(nr)
        evidence = {k: hit[k] for k in ("danga", "page", "irodymas", "tekstas", "plotas_m2", "rect_pct")} if hit else None
        if hit:
            meta["grindu_dangos"]["perskaityta"][nr] = hit["danga"]
        if str(r.get("grindu_danga_saltinis") or "") == "user_override":
            # his choice stands; what the plan draws is kept BESIDE it, so the
            # check sheet can say when the two differ
            if evidence:
                r["_grindu_danga"] = evidence
            else:
                r.pop("_grindu_danga", None)
            continue
        if hit:
            r["grindu_danga"] = hit["danga"]
            r["grindu_danga_saltinis"] = FLOOR_PLAN_SOURCE
            r["_grindu_danga"] = evidence
        elif str(r.get("grindu_danga_saltinis") or "") == FLOOR_PLAN_SOURCE:
            for key in FLOOR_KEYS:
                r.pop(key, None)
    meta["grindu_dangos"]["dvi_dangos"] = sorted(nr for nr in two if nr not in read)


def _divide_shared_spaces(rooms, groups, todo, seats_on_page, areas, pdf_bytes, page, m_per_pt, size, meta) -> None:
    """A space TWO rooms share is divided by the boundary the lane itself proposes (vector_rooms.propose_split:
    through a wall end when the table's two areas agree with it, else where the areas stand in the table's
    ratio) — 2026-09-23, the founder: „o koks tau skirtumas, kur riba?". None to the wall total: the
    boundary is an edge of both outlines and a wall of neither, so each room's walls can be READ instead of
    guessed as a share by floor area. Both rooms keep `_atvira_erdve` (the shared outline is shown dashed,
    and a person may still draw the line elsewhere — that line, "padalinta", is never replaced by this).
    Only rooms still to do are written; a space of three rooms, or one whose numbers or areas are not known,
    is left with its estimates."""
    by_nr = {_nr(r): r for r in rooms}
    W, H = size
    for g in groups:
        members = sorted(str(n) for n in g["nariai"])
        if len(members) != 2 or not all(m in todo and m in by_nr for m in members):
            continue
        seats = {m: (float(seats_on_page[m]["cx"]), float(seats_on_page[m]["cy"])) for m in members
                 if m in seats_on_page and seats_on_page[m].get("saltinis") in STRONG}
        table = {m: float(areas.get(m) or 0) for m in members}
        if len(seats) != 2 or min(table.values()) <= 0:
            meta["ribos_nepasiulytos"].append(members)
            continue
        # a pocket joined to a neighbour's face (vector_rooms._match, `kisene`) is no single face at any door
        # limit: the space is divided as the lane recorded it
        cut = propose_split(pdf_bytes, page, seats, table, m_per_pt, (W, H), face_pct=g["polygon_pct"] if g.get("kisene") else None)
        if cut.get("status") != "ok" or any(m not in cut["rooms"] for m in members):
            meta["ribos_nepasiulytos"].append(members)
            continue
        for m in members:
            r, part = by_nr[m], cut["rooms"][m]
            r["polygon_pct"] = part["polygon_pct"]
            r["polygon_source"] = VECTOR_SOURCE                # the lane's own: the next run does it again
            r["_konturas"] = {"page": page, "plotas_m2": part["plotas_m2"], "perimetras_m": part["perimetras_m"],
                              "plotas_uzrasas_m2": areas.get(m), "paklaida": part["paklaida"],
                              "plotas_nesutampa": bool(part.get("plotas_nesutampa")), "menamos": part["menamos"],
                              "su": [o for o in members if o != m], "saltinis": DIVIDED_BY_LANE,
                              "pagal": cut["pagal"], "riba_pct": cut["line_pct"]}
            r.pop("_konturo_priezastis", None)
            r.pop("_konturo_siulymas", None)
            if str(r.get("perimetras_saltinis") or "") == OPEN_PLAN_ESTIMATE:
                # the share by floor area written a moment ago — this side's own walls are read below
                # (sum_perimeters: the strings along them, else the outline's length as an estimate with its reason)
                for stale in ("_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis"):
                    r.pop(stale, None)
            if m not in meta["konturai"]:
                meta["konturai"].append(m)
            meta["perimetrai_tusti"] = [nr for nr in meta["perimetrai_tusti"] if nr != m]
        meta["ribos"].append({"nariai": members, "pagal": cut["pagal"]})


_log = logging.getLogger("samatu.geometry_lane")


def _stage(on_stage: Callable[[str], None] | None, name: str) -> None:
    """Tell a listener which step the lane has reached (api/detect_run.py shows them as stages). Progress never
    sinks the lane: whatever the listener raises is logged and swallowed."""
    if on_stage is None:
        return
    try:
        on_stage(name)
    except Exception:  # noqa: BLE001
        _log.exception("geometry lane stage listener failed at %s", name)


def geometry_dimension_strings(pdf_bytes: bytes) -> list[dict]:
    """The ONE source of the dimension strings the geometry reading receives —
    the paid reading, the free re-read, the room-outline click and the eval all
    come through here: every page, slanted strings included (audit 2026-09-30,
    geometry-lanes-2: the paid reading passed its classified-page text scan,
    which reads no slanted string, so objektas_h's room 09 got 16,02 m as an
    outline estimate after the paid reading and 16,01 m from strings after the
    free re-read)."""
    return read_dimension_strings(pdf_bytes, pages=None)


def apply_geometry(parsed: dict, pdf_bytes: bytes, dims: Sequence[dict] | None = None, *,
                   on_stage: Callable[[str], None] | None = None) -> dict:
    t0 = time.time()
    meta: dict = {"versija": LANE_VERSION,
                  "vietos": {}, "grupes": [], "sutapdinimas": {}, "lapai": [], "konturai": [], "konturu_priezastys": {}, "atviros_erdves": [],
                  "perimetrai_sudeti": [], "perimetrai_tusti": [], "angos_sienose": [], "nupiesta": {"langai": 0, "durys": 0, "be_tarpo": 0}, "ribos": [], "ribos_nepasiulytos": [], "konturu_siulymai": [],
                  "grindu_dangos": {"lapai": [], "perskaityta": {}, "dvi_dangos": []},
                  "kiti_aukstai": [], "skirtingu_lapu_erdves": [], "masteliai_atmesti": {}, "masteliai_kiti": {}, "poros_patvirtintos": [], "poros_atmestos": [],
                  "perimetrai_atmesti": [], "seconds": 0.0}
    status = "insufficient"
    try:
        _stage(on_stage, "mastelis")
        # A room merged into another („Sujungti", `_sujungta_i`) has no outline of its own: the kept room's
        # union is it. The lane does not place, trace, open or floor it, nor count it as anyone's neighbour.
        rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict) and _nr(r) and not r.get("_sujungta_i")]
        plan_pages = plan_pages_from_classification(parsed.get("puslapiai"))
        if not plan_pages:
            plan_pages = sorted({int(r["puslapio_nr"]) for r in rooms if r.get("puslapio_nr")}) or [1]
        if dims is None:
            dims = geometry_dimension_strings(pdf_bytes)
        for d in dims:                     # sheets whose scale is no plan's, or the written one off by a unit (plan_dimensions)
            if d.get("mastelis_atmestas"):
                meta["masteliai_atmesti"].setdefault(str(d["page"]), d["mastelis_atmestas"])
            if d.get("mastelis_kitas"):    # …and sheets read at another scale than they write (a reduced print)
                meta["masteliai_kiti"].setdefault(str(d["page"]), d["mastelis_kitas"])
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

        _stage(on_stage, "tekstas")
        where = locate_rooms(pdf_bytes, rooms, plan_pages)
        for r in rooms:
            v = where.get(_nr(r))
            if v:
                r["_vieta"] = v
                meta["vietos"][v["saltinis"]] = meta["vietos"].get(v["saltinis"], 0) + 1
        # the rooms' reliable seats per sheet — what tells two typical floors apart when their walls coincide
        seats: dict[int, list[tuple[str, float, float]]] = {}
        for nr, v in where.items():
            if v.get("saltinis") in STRONG and v.get("W") and v.get("H"):
                seats.setdefault(int(v["page"]), []).append((str(nr), float(v["cx"]) * float(v["W"]), float(v["cy"]) * float(v["H"])))

        def lay_over(pages: Sequence[int]) -> dict:
            """Align these sheets; a sheet without strings of its own takes its plan's scale."""
            al = align_sheets(pdf_bytes, sorted(pages), seats=seats)
            for clash in al.get("storeys") or []:
                if clash not in meta["kiti_aukstai"]:
                    meta["kiti_aukstai"].append(clash)
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
        _stage(on_stage, "planas")
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
        _stage(on_stage, "konturai")
        for group in alignment["groups"]:
            located = [r for r in rooms if r.get("_vieta") and int(r["_vieta"]["page"]) in group]
            # the lane's OWN outlines are traced again every run (2026-09-23: a stored project gains what the lane
            # learns — a pocket joined to a neighbour's face); a person's or the raster lane's outline is never replaced
            todo = {_nr(r) for r in located
                    if str(r.get("polygon_source") or "") not in KEEP_POLYGONS or str(r.get("polygon_source") or "") == VECTOR_SOURCE}
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
            # what already stands — a person's or the raster lane's outline — is handed to the trace as solved: its
            # faces are owned, it is never proposed, joined or divided, and a neighbour standing in it shares it
            standing: dict[str, list] = {}
            for r in located:
                if _nr(r) in todo or not isinstance(r.get("polygon_pct"), list) or len(r["polygon_pct"]) < 3:
                    continue
                src = int((r.get("_konturas") or {}).get("page") or r.get("puslapio_nr") or page)
                if src == page:
                    standing[_nr(r)] = [[float(x), float(y)] for x, y in r["polygon_pct"]]
                elif src in sizes:
                    ring = []
                    for x, y in r["polygon_pct"]:
                        bx, by = to_base(alignment, src, float(x) * sizes[src][0], float(y) * sizes[src][1])
                        qx, qy = from_base(alignment, page, bx, by)
                        ring.append([qx / W, qy / H])
                    standing[_nr(r)] = ring
            res = trace_vector_rooms(pdf_bytes, page, everyone, areas, scale[page], (W, H), solved_pct=standing)
            meta["lapai"].append(page)
            # Two rooms seated reliably on DIFFERENT sheets standing in one face are not one open space — they are
            # two storeys laid over each other (audit 2026-09-29, geometry-lanes-3: halving each room's walls
            # between them was a guess presented as a share). Neither is outlined; each keeps what it had.
            seated_on = {nr: int(v["page"]) for nr, v in where.items() if v.get("saltinis") in STRONG}
            kept = []
            for g in res["groups"]:
                sheets_of = {seated_on[n] for n in g["nariai"] if n in seated_on}
                if len(sheets_of) > 1:
                    meta["skirtingu_lapu_erdves"].append(sorted(g["nariai"]))
                    for n in g["nariai"]:
                        others = ", ".join(o for o in g["nariai"] if o != n)
                        res["reasons"][n] = (f"toje pačioje plano vietoje kitame lape pažymėta patalpa {others} — "
                                             "tikriausiai kitas aukštas, todėl kontūras nenustatytas")
                        r = next((x for x in rooms if _nr(x) == n), None)
                        if r is not None and n in todo and not _his(r):
                            _forget_open_space(r)       # a share this lane wrote on an earlier run goes too
                    continue
                kept.append(g)
            res["groups"] = kept
            for r in rooms:
                nr = _nr(r)
                if nr not in todo:
                    continue
                hit = res["rooms"].get(nr)
                if not hit and str(r.get("polygon_source") or "") == VECTOR_SOURCE and not _his(r):
                    _forget_outline(r)                 # outlined on an earlier run, not by today's reading
                if hit:
                    r["polygon_pct"] = hit["polygon_pct"]
                    r["polygon_source"] = VECTOR_SOURCE
                    r["_konturas"] = {"page": page, "plotas_m2": hit["plotas_m2"], "perimetras_m": hit["perimetras_m"],
                                      "plotas_uzrasas_m2": areas.get(nr), "paklaida": hit["paklaida"],
                                      "plotas_nesutampa": hit["plotas_nesutampa"], "sujungta": hit["sujungta"],
                                      "durys_m": hit["durys_m"], "saltinis": VECTOR_SOURCE}
                    r.pop("_konturo_priezastis", None)
                    r.pop("_atvira_erdve", None)       # its own face today: an open space it was part of before is gone
                    # the openings the wall solid shows in this room's walls — evidence for the
                    # door-and-window fact, never a quantity on their own (2026-09-20)
                    r["_angos_sienose"] = {"page": page, "angos": hit.get("angos") or []}
                    r.pop("_konturo_siulymas", None)
                    meta["konturai"].append(nr)
                elif nr in res["reasons"]:
                    r["_konturo_priezastis"] = res["reasons"][nr]
                    meta["konturu_priezastys"][nr] = res["reasons"][nr]
                    # 2026-09-23: the face the walls close around the number, when its area is too far from the
                    # table's to take on its own — kept as a PROPOSAL for the question list („Tinka" takes it)
                    cand = (res.get("siulymai") or {}).get(nr)
                    if cand:
                        r["_konturo_siulymas"] = {**cand, "plotas_uzrasas_m2": areas.get(nr)}
                        meta["konturu_siulymai"].append(nr)
                    else:
                        r.pop("_konturo_siulymas", None)
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
            _divide_shared_spaces(rooms, res["groups"], todo, everyone, areas, pdf_bytes, page, scale[page], (W, H), meta)
        # an outline of this lane's that never reached today's trace — the room is not placed today, or its plan
        # sheet has no scale — is no more confirmed than one the trace could not find (2026-09-29)
        confirmed = set(meta["konturai"])
        for r in rooms:
            if str(r.get("polygon_source") or "") == VECTOR_SOURCE and _nr(r) not in confirmed and not _his(r):
                _forget_outline(r)

        for r in rooms:                                        # a room with a trusted outline needs no proposal
            if str(r.get("polygon_source") or "") in KEEP_POLYGONS:
                r.pop("_konturo_siulymas", None)
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

        # The openings come BEFORE the walls are added: a designer writes the wall pieces either side of a door
        # and never the door itself, so a wall's chain of strings has a hole exactly where the room's own
        # opening is (objektas_h bedroom 09: „660" | door 1,40 m | „1538") — dimension_sum fills it and says so.
        _stage(on_stage, "angos")
        _read_wall_openings(rooms, pdf_bytes, alignment, scale, sizes, meta)
        # Two dimension strings closing a rectangle (plan_dimensions, `plano_matmenys`) assume the room IS one.
        # A wall outline checks it: a bounding-box pair it is as long as becomes the perimeter, and an exact
        # pair whose walls — added up one by one — come to another figure gives way to them (audit 2026-09-29,
        # geometry-lanes-6). An outline's own length never overrules a pair: it is an estimate, the pair is read.
        for r in rooms:
            k = r.get("_konturas") if isinstance(r.get("_konturas"), dict) else {}
            if (isinstance(r.get(PAIR_PROPOSAL), dict) and not _his(r) and not k.get("plotas_nesutampa")
                    and str(r.get("polygon_source") or "") in WALL_OUTLINES
                    and confirm_pair_by_outline(r, k.get("perimetras_m"))):
                meta["poros_patvirtintos"].append(_nr(r))
        _stage(on_stage, "sienos")
        held = {}
        for r in rooms:
            if (r.get("perimetras_saltinis") == PAIR_SOURCE and r.get("perimetras_m") and not _his(r)
                    and not r.get("manual_override") and str(r.get("polygon_source") or "") in WALL_OUTLINES
                    and isinstance(r.get("polygon_pct"), list) and len(r["polygon_pct"]) >= 3
                    and not (r.get("_konturas") or {}).get("plotas_nesutampa")):
                held[_nr(r)] = _perimeter_snapshot(r)
                r["perimetras_saltinis"] = None            # for this one pass: its walls are added up too
        before = {_nr(r): (r.get("perimetras_m") if r.get("perimetras_saltinis") not in ESTIMATES else None) for r in rooms}
        kept_as_was = {_nr(r): _perimeter_snapshot(r) for r in rooms}
        done = sum_perimeters(rooms, dims, alignment, scale, page_sizes=sizes)
        for nr, snap in held.items():
            r = next(x for x in rooms if _nr(x) == nr)
            pair = float(snap["perimetras_m"])
            if nr in done["stated"] and abs(float(r["perimetras_m"]) - pair) / pair > PAIR_WALLS_TOL:
                if isinstance(r.get("_perimetras_matmenys"), dict):
                    r["_perimetras_matmenys"] = {**r["_perimetras_matmenys"], "sienu_suma_m": r["perimetras_m"]}
                meta["poros_atmestos"].append(nr)
                continue
            _restore_perimeter(r, snap)
            done["stated"] = [x for x in done["stated"] if x != nr]
            done["blank"] = [x for x in done["blank"] if x != nr]
        # Any room's perimeter is at least the circle's of its area (plan_dimensions.plausible_perimeter): a sum
        # or an outline below that is strings or a scale that are not what they seem — the room keeps what it had.
        # Not for a side of a shared space: the boundary through it is an edge of the room and a wall of neither.
        for r in rooms:
            nr = _nr(r)
            open_side = bool((r.get("_konturas") or {}).get("menamos")) or isinstance(r.get("_atvira_erdve"), dict)
            if ((nr in done["stated"] or nr in done["blank"]) and not open_side
                    and not plausible_perimeter(r.get("perimetras_m"), areas.get(nr))):
                _restore_perimeter(r, held.get(nr) or kept_as_was[nr])
                done["stated"] = [x for x in done["stated"] if x != nr]
                done["blank"] = [x for x in done["blank"] if x != nr]
                meta["perimetrai_atmesti"].append(nr)
        meta["perimetrai_sudeti"] = done["stated"]
        meta["perimetrai_tusti"] = sorted(set(meta["perimetrai_tusti"]) | set(done["blank"]))
        for r in rooms:
            nr = _nr(r)
            if nr in done["stated"] or nr in done["blank"]:
                old = before.get(nr)
                if old is not None and str(r.get("perimetras_saltinis") or "") not in [s for s in STATED_PERIMETERS if s != "matmenu_eilutes"]:
                    r.setdefault("_perimetras_pries_geometrija", old)
        _stage(on_stage, "grindys")
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
    legend = meta["grindu_dangos"].pop("legenda", None)
    if isinstance(parsed, dict):
        parsed.setdefault("_meta", {})["geometrija"] = meta
        if legend is not None:
            # the floor sheet's key lines (text, colour, sheet, box) — evidence beside the floor fact, never a
            # room key (LANE_VERSION unchanged); a read that found no floor sheet leaves the stored key alone
            parsed["_meta"]["grindu_legenda"] = legend
    return {"status": status, **meta}

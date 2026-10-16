"""/api/projects/{project_id}/rooms/{room_nr}/outline-at — a room gets its outline from ONE
click inside it, and its walls are read again right away. No Vision call, no cost.

A room the geometry lane could not outline (its number is not printed where it could be found,
its drawn area disagrees with the table) showed WHY on the check sheet and a blank perimeter —
and nothing there could fix it. The person points at the room; the outline is the face of the
wall solid under the click (extractor/vector_rooms.outline_at), marked `corrected`, which the
lane already honours: it is never re-traced, the strings along its walls are summed, the
openings in its walls are read.

`…/split-space` (2026-09-21) is its sibling for two rooms NO WALL separates — a kitchen and a living
room, usually the biggest rooms of a flat: one line a person draws divides the shared space
(vector_rooms.split_space); both rooms get their own outlines, and the boundary between them is
marked `menamos` — never a wall, never in a perimeter.

`…/split-proposal` (2026-09-21) PROPOSES that line (vector_rooms.propose_split: through a wall end between
the two rooms when the table's areas agree with it, else where the areas stand in the table's ratio) and
answers exactly as a drawn line does — „programa siūlo, jūs patvirtinate": a person only says „Tinka".

The server SAVES NOTHING (same rule as api/free_reread.py): it answers with the room's geometry
keys — a key that is `null` is to be removed — and with the neighbours' wall openings, which now
lead to a NAMED room. The sheet patches the room and recomputes on the one path every other edit
takes (/recompute-interior → consequence strip → undo).
"""
from __future__ import annotations

import copy
import logging
import math
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.free_reread import NO_PDF, _project_for
from extractor.geometry_lane import KEEP_POLYGONS, apply_geometry, geometry_dimension_strings
from extractor.pdf_vectors import page_geometry
from extractor.vector_rooms import SOURCE as VECTOR_SOURCE, STRONG, joined_space, outline_at, propose_split, split_space

log = logging.getLogger("samatu.room_outline")

router = APIRouter(prefix="/api/projects", tags=["room-outline"])

POINTED_AT = "parodyta"           # `_konturas.saltinis` of an outline a person pointed at
ACCEPTED_PROPOSAL = "pasiulyta"   # …of the face the lane PROPOSED (its area off the table's) that a person accepted (2026-09-23)
DIVIDED = "padalinta"             # …of an outline that is one side of a line a person drew through a shared space
_ESTIMATE_KEYS = ("perimetras_saltinis", "_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis")

# What a room's geometry is made of — everything else of the room (its name, its area, the
# quantities built from it) is never sent back, so a click can never overwrite it.
GEOMETRY_ROOM_KEYS = (
    "polygon_pct", "polygon_source", "polygon_corrected_at", "_konturas", "_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve",
    "perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma", "_perimetras_priezastis",
    "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis", "_perimetras_pries_geometrija",
    "_angos_sienose", "grindu_danga", "grindu_danga_saltinis", "_grindu_danga", "_grindu_dangos_dvi",
)


class OutlineAt(BaseModel):
    page: int = Field(ge=1)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)
    pritarta: bool = False            # the point is inside the outline the lane proposed and he said „Tinka"


class PagePoint(BaseModel):
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)


class SplitSpace(BaseModel):
    page: int = Field(ge=1)
    a: PagePoint
    b: PagePoint
    su: str | None = Field(default=None, max_length=8)   # the neighbour whose face this room's pocket joins (2026-09-23)


class OutlineSet(BaseModel):
    """A ring a PERSON drew or edited in the viewer (2026-10-16): display-frame page fractions, ≥ 3 points."""
    page: int = Field(ge=1)
    polygon_pct: list[list[float]] = Field(min_length=3, max_length=500)


DRAWN = "nubrezta"               # `_konturas.saltinis` of an outline a person drew or edited vertex by vertex


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _laid_onto(page: int, sutapdinimas: dict):
    """Page fractions of another sheet of the same plan → fractions of `page` (None when not the same plan)."""
    to = sutapdinimas.get(str(page))

    def lay(src: int, x: float, y: float):
        if int(src) == int(page):
            return x, y
        frm = sutapdinimas.get(str(src))
        if not frm or not to or frm.get("base") != to.get("base"):
            return None
        bx, by = frm["kx"] * x + frm["dx_pct"], frm["ky"] * y + frm["dy_pct"]
        return (bx - to["dx_pct"]) / to["kx"], (by - to["dy_pct"]) / to["ky"]
    return lay


def _todays_reading(request: Request, project_id: str, room_nr: str, page: int, bucket: str):
    """Everything both endpoints start from: the owner's project, its drawing, and TODAY's lane reading on a
    deep copy — where the other rooms are, every sheet's scale, how the sheets lie over each other.
    → (pdf_bytes, (W, H), parsed copy, dims, geo meta, scale of `page`, rooms, the room)."""
    project = _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), bucket)

    wanted = str(room_nr).strip()
    if not any(_nr(r) == wanted for r in (project.get("patalpos") or []) if isinstance(r, dict)):
        raise HTTPException(status_code=404, detail="Patalpa nerasta")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("room-outline pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    W, H, _ = page_geometry(pdf_bytes, page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")

    parsed = copy.deepcopy(project)
    dims = geometry_dimension_strings(pdf_bytes)   # read once, reused below
    apply_geometry(parsed, pdf_bytes, dims)
    geo = (parsed.get("_meta") or {}).get("geometrija") or {}
    scale = ((geo.get("masteliai") or {}).get(str(page)) or {}).get("m_per_pt")
    if not scale:
        raise HTTPException(status_code=400, detail="Šio lapo mastelio neradau — parodykite patalpą plane, kuriame užrašyti matmenys.")
    rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict)]
    room = next(r for r in rooms if _nr(r) == wanted)
    return pdf_bytes, (W, H), parsed, dims, geo, float(scale), rooms, room


# Plain `def`: PDF parsing and geometry, 100 % blocking — the threadpool's job.
@router.post("/{project_id}/rooms/{room_nr}/outline-at")
def api_room_outline_at(request: Request, project_id: str, room_nr: str, body: OutlineAt):
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    lay = _laid_onto(body.page, geo.get("sutapdinimas") or {})
    others: dict[str, list] = {}
    seats: dict[str, tuple[float, float]] = {}
    for r in rooms:
        if r is room:
            continue
        poly = r.get("polygon_pct")
        if str(r.get("polygon_source") or "") in KEEP_POLYGONS and isinstance(poly, list) and len(poly) >= 3:
            src = int((r.get("_konturas") or {}).get("page") or r.get("puslapio_nr") or 0)
            ring = [lay(src, float(x), float(y)) for x, y in poly]
            if all(pt is not None for pt in ring):
                others[_nr(r)] = [list(pt) for pt in ring]
            continue
        v = r.get("_vieta")
        if isinstance(v, dict) and v.get("saltinis") in STRONG:
            pt = lay(int(v["page"]), float(v["cx"]), float(v["cy"]))
            if pt is not None:
                seats[_nr(r)] = pt

    hit = outline_at(pdf_bytes, body.page, body.x_pct, body.y_pct, room.get("plotas_m2"), float(scale), (W, H),
                     others_pct=others, other_seats_pct=seats)
    if hit["status"] == "taken":
        # 2026-09-23 (objektas_h tambūras: „jei patalpa didesnė — spustelėkite kitoje jos vietoje … bet paspaudus
        # nieko negali padaryti"): the place belongs to a neighbour the LANE outlined, and this room's walls close a
        # pocket beside it — the two are one space with an imaginary boundary. The boundary is proposed (both
        # outlines + line, nothing saved); with `pritarta` it is applied to both rooms.
        joined = _joined_with(pdf_bytes, page=body.page, rooms=rooms, room=room, other_nr=str(hit.get("nr") or ""),
                              lay=lay, scale=scale, size=(W, H))
        if joined is not None:
            other, union, seats2, areas2 = joined
            cut = propose_split(pdf_bytes, body.page, seats2, areas2, float(scale), (W, H), face_pct=union)
            if cut.get("status") == "ok":
                if body.pritarta:
                    return _divided(parsed, pdf_bytes, dims, rooms, [_nr(room), other], body.page, cut)
                return {"status": "shared", "su": other, "page": body.page, "line_pct": cut["line_pct"], "pagal": cut["pagal"],
                        "rooms": {nr: {**part, "plotas_uzrasas_m2": areas2.get(nr)} for nr, part in cut["rooms"].items()}}
        return hit
    if hit["status"] != "ok":
        return hit

    room["polygon_pct"] = hit["polygon_pct"]
    room["polygon_source"] = "corrected"
    room["polygon_corrected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # A person confirmed this outline: a disagreement with the table is SHOWN (`paklaida`), but it no
    # longer keeps the wall lengths from being added (dimension_sum reads `plotas_nesutampa`).
    room["_konturas"] = {"page": body.page, "plotas_m2": hit["plotas_m2"], "perimetras_m": hit["perimetras_m"],
                         "plotas_uzrasas_m2": room.get("plotas_m2"), "paklaida": hit["paklaida"],
                         "plotas_nesutampa": False, "sujungta": hit["sujungta"], "durys_m": hit["durys_m"],
                         "saltinis": ACCEPTED_PROPOSAL if body.pritarta else POINTED_AT}
    for stale in ("_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve", "_angos_sienose"):
        room.pop(stale, None)
    if str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis"):
        # an ESTIMATE made without this outline — the walls are read afresh
        for stale in _ESTIMATE_KEYS:
            room.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)

    return {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }


@router.post("/{project_id}/rooms/{room_nr}/outline-set")
def api_room_outline_set(request: Request, project_id: str, room_nr: str, body: OutlineSet):
    """The ring the person drew IS the room's outline (2026-10-16, Togal analysis §10): marked `corrected`
    (the lane never re-traces it), its area and perimeter measured at the sheet's scale, its walls and
    openings read again — exactly what a click (`outline-at`) does, with the person's geometry instead of
    the wall solid's face. The printed area stays the room's area; the drawn one is shown beside it
    (`_konturas.plotas_m2`, `paklaida`). Saves nothing — the sheet patches the room and recomputes."""
    # Ownership FIRST (tests/test_route_ownership_policy.py): a stranger's malformed ring must get the
    # same 404 as a stranger's well-formed one — never a 400 that says the project exists.
    _project_for(request, project_id)
    ring: list[tuple[float, float]] = []
    for pt in body.polygon_pct:
        if len(pt) != 2 or not all(0.0 <= float(v) <= 1.0 for v in pt):
            raise HTTPException(status_code=400, detail="Kontūro taškai turi būti lapo dalys 0–1")
        ring.append((float(pt[0]), float(pt[1])))
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    pts = [(x * W, y * H) for x, y in ring]
    n = len(pts)
    area_pt2 = abs(sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))) / 2
    if area_pt2 < 1.0:
        raise HTTPException(status_code=400, detail="Kontūras per mažas arba išsigimęs")
    perim_pt = sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n))
    plotas = round(area_pt2 * scale * scale, 2)
    perimetras = round(perim_pt * scale, 2)
    table = room.get("plotas_m2")
    has_table = isinstance(table, (int, float)) and not isinstance(table, bool) and float(table) > 0
    paklaida = round((plotas - float(table)) / float(table), 4) if has_table else None

    room["polygon_pct"] = [[round(x, 5), round(y, 5)] for x, y in ring]
    room["polygon_source"] = "corrected"
    room["polygon_corrected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    room["_konturas"] = {"page": body.page, "plotas_m2": plotas, "perimetras_m": perimetras,
                         "plotas_uzrasas_m2": table if has_table else None, "paklaida": paklaida,
                         "plotas_nesutampa": False, "saltinis": DRAWN}
    for stale in ("_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve", "_angos_sienose"):
        room.pop(stale, None)
    if str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis", "sienu_konturas"):
        # a perimeter that rested on the OLD outline — the walls are read afresh along the new one
        for stale in _ESTIMATE_KEYS:
            room.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)
    if str(room.get("perimetras_saltinis") or "") in ("", "vision"):
        # no dimension strings along the drawn walls: the drawn perimeter is the room's, named as such
        room["_perimetras_pries_geometrija"] = room.get("perimetras_m")
        room["perimetras_m"] = perimetras
        room["perimetras_saltinis"] = "sienu_konturas"
    return {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }


def _joined_with(pdf_bytes: bytes, *, page: int, rooms: list[dict], room: dict, other_nr: str, lay, scale: float,
                 size: tuple[float, float]):
    """The space this room's pocket makes with `other_nr`'s lane-traced outline across a doorless opening
    (vector_rooms.joined_space) → (other, union_pct, seats, table areas) — or None: no such neighbour, a person's
    outline (never divided by the program), no printed numbers, or no opening between them."""
    by_nr = {_nr(r): r for r in rooms}
    other = by_nr.get(other_nr)
    if other is None or str(other.get("polygon_source") or "") != VECTOR_SOURCE or not isinstance(other.get("polygon_pct"), list):
        return None
    seats: dict[str, tuple[float, float]] = {}
    for r in (room, other):
        v = r.get("_vieta")
        pt = lay(int(v["page"]), float(v["cx"]), float(v["cy"])) if isinstance(v, dict) and v.get("saltinis") in STRONG else None
        if pt is None:
            return None
        seats[_nr(r)] = pt
    src = int((other.get("_konturas") or {}).get("page") or other.get("puslapio_nr") or page)
    ring = [lay(src, float(x), float(y)) for x, y in other["polygon_pct"]]
    if any(pt is None for pt in ring):
        return None
    union = joined_space(pdf_bytes, page, seats[_nr(room)], [list(pt) for pt in ring], float(scale), size)
    if union is None:
        return None
    areas = {nr: float(by_nr[nr].get("plotas_m2") or 0) for nr in seats}
    return other_nr, union, seats, areas


def _shared_space(rooms: list[dict], room: dict, lay) -> tuple[str | None, list[str], dict[str, tuple[float, float]]]:
    """(status | None, the two members, where their numbers stand on the sheet being divided)."""
    space = room.get("_atvira_erdve")
    members = [str(n) for n in (space.get("nariai") or [])] if isinstance(space, dict) else []
    if len(members) < 2:
        return "not_shared", members, {}
    if len(members) > 2:
        return "too_many", members, {}
    by_nr = {_nr(r): r for r in rooms}
    seats: dict[str, tuple[float, float]] = {}
    for nr in members:
        v = (by_nr.get(nr) or {}).get("_vieta")
        pt = lay(int(v["page"]), float(v["cx"]), float(v["cy"])) if isinstance(v, dict) and v.get("saltinis") in STRONG else None
        if pt is None:
            return "not_shared", members, {}
        seats[nr] = pt
    return None, members, seats


def _divided(parsed: dict, pdf_bytes: bytes, dims, rooms: list[dict], members: list[str], page: int, hit: dict) -> dict:
    """Both rooms take their side of the boundary (`hit` — vector_rooms' answer), their walls are read again,
    and only their geometry keys go back. The boundary is `menamos`: never a wall. Saves nothing."""
    by_nr = {_nr(r): r for r in rooms}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for nr in members:
        r, part = by_nr[nr], hit["rooms"][nr]
        r["polygon_pct"] = part["polygon_pct"]
        r["polygon_source"] = "corrected"
        r["polygon_corrected_at"] = now
        r["_konturas"] = {"page": page, "plotas_m2": part["plotas_m2"], "perimetras_m": part["perimetras_m"],
                          "plotas_uzrasas_m2": r.get("plotas_m2"), "paklaida": part["paklaida"], "plotas_nesutampa": False,
                          "menamos": part["menamos"], "su": [m for m in members if m != nr], "saltinis": DIVIDED}
        for stale in ("_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve", "_angos_sienose"):
            r.pop(stale, None)
        if str(r.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis"):
            for stale in _ESTIMATE_KEYS:
                r.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)
    return {
        "status": "ok",
        "rooms": {nr: {k: by_nr[nr].get(k) for k in GEOMETRY_ROOM_KEYS} for nr in members},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if _nr(r) not in members and isinstance(r.get("_angos_sienose"), dict)},
    }


@router.post("/{project_id}/rooms/{room_nr}/split-space")
def api_room_split_space(request: Request, project_id: str, room_nr: str, body: SplitSpace):
    """Two rooms no wall separates, divided by ONE line through `a` and `b` (vector_rooms.split_space). Both
    rooms come back with their own outlines — the boundary marked `menamos`, never a wall — and their walls
    read again. Saves nothing."""
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    lay = _laid_onto(body.page, geo.get("sutapdinimas") or {})
    by_nr = {_nr(r): r for r in rooms}
    if body.su:
        # „Nubrėšiu pats" after a click in the neighbour's room (2026-09-23): the line cuts the JOINED space
        joined = _joined_with(pdf_bytes, page=body.page, rooms=rooms, room=room, other_nr=str(body.su).strip(), lay=lay,
                              scale=scale, size=(W, H))
        if joined is None:
            return {"status": "not_shared"}
        other, union, seats, areas = joined
        members = [_nr(room), other]
        face = union
    else:
        status, members, seats = _shared_space(rooms, room, lay)
        if status:
            return {"status": status}
        areas = {nr: by_nr[nr].get("plotas_m2") for nr in members}
        space = room.get("_atvira_erdve") if isinstance(room.get("_atvira_erdve"), dict) else {}
        face = space.get("polygon_pct") if space.get("kisene") else None      # a joined space is no single face
    hit = split_space(pdf_bytes, body.page, (body.a.x_pct, body.a.y_pct), (body.b.x_pct, body.b.y_pct), seats,
                      areas, scale, (W, H), face_pct=face)
    if hit["status"] != "ok":
        return hit
    return _divided(parsed, pdf_bytes, dims, rooms, members, body.page, hit)


@router.post("/{project_id}/rooms/{room_nr}/split-proposal")
def api_room_split_proposal(request: Request, project_id: str, room_nr: str):
    """The boundary the PROGRAM proposes for the space this room shares (vector_rooms.propose_split) — so
    that a person only says „Tinka" (2026-09-21). The answer is the very one a drawn line gives, plus
    `line_pct` (the boundary, for showing it BEFORE it is accepted), `page` and `pagal`. Saves nothing: the
    sheet applies the answer on the path every other edit takes, or asks for a line drawn by hand."""
    stored = _project_for(request, project_id)
    mine = next((r for r in (stored.get("patalpos") or []) if isinstance(r, dict) and _nr(r) == str(room_nr).strip()), None)
    if mine is None:
        raise HTTPException(status_code=404, detail="Patalpa nerasta")
    space = mine.get("_atvira_erdve") if isinstance(mine.get("_atvira_erdve"), dict) else {}
    page = int(space.get("page") or (mine.get("_vieta") or {}).get("page") or mine.get("puslapio_nr") or 1)
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, page, "room_outline")
    status, members, seats = _shared_space(rooms, room, _laid_onto(page, geo.get("sutapdinimas") or {}))
    if status:
        return {"status": status}
    by_nr = {_nr(r): r for r in rooms}
    hit = propose_split(pdf_bytes, page, seats, {nr: by_nr[nr].get("plotas_m2") for nr in members}, scale, (W, H),
                        face_pct=space.get("polygon_pct") if space.get("kisene") else None)
    if hit["status"] != "ok":
        return {"status": hit["status"]}
    return {**_divided(parsed, pdf_bytes, dims, rooms, members, page, hit),
            "line_pct": hit["line_pct"], "pagal": hit["pagal"], "page": page}

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
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.free_reread import NO_PDF, _project_for
from extractor.geometry_lane import FLOOR_KEYS, KEEP_POLYGONS, apply_geometry, geometry_dimension_strings
from extractor.pdf_vectors import page_geometry
from extractor.universal_rules import ring_corner_counts
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
    "polygon_holes_pct",
    "_sienu_apdaila",          # the wall finishes as drawn, face by face (v4 2026-10-26, geometry_lane._read_wall_finishes)
)


def _remembered(project_id: str, answer: dict, nr: str | None = None, klausimas: str | None = None) -> dict:
    """The learning journal (togal-v2 W11): every outline a person confirmed, drew, divided or merged is one
    `corrections` row per room (source „konturas"), written HERE so every client path counts. The endpoints save
    nothing to the project; the journal row says what the person did, the sheet lands the geometry. A failed
    write never fails the answer. `klausimas`: the Patikra question this outline answers — it rides in `note`,
    and this row IS that answer's record (the browser writes no `klausimas_*` row for it: one act, one row)."""
    if not isinstance(answer, dict) or answer.get("status") != "ok":
        return answer
    rooms = answer.get("rooms") if isinstance(answer.get("rooms"), dict) else ({nr: answer["room"]} if nr and isinstance(answer.get("room"), dict) else {})
    try:
        import db as _db
        for room_nr, r in rooms.items():
            k = (r or {}).get("_konturas") or {}
            _db.log_correction_once(
                project_id=project_id, field_path=f"patalpa.{room_nr}.kontūras",
                old_value={"plotas_m2": k.get("plotas_uzrasas_m2")},
                new_value={"saltinis": k.get("saltinis"), "plotas_m2": k.get("plotas_m2"),
                           "perimetras_m": k.get("perimetras_m"), "page": k.get("page")},
                source="konturas", room_nr=str(room_nr), note=klausimas or None)
    except Exception as exc:  # noqa: BLE001 — the journal is never the outline
        log.warning("outline journal write failed project=%s: %r", project_id, exc)
    return answer


class OutlineAt(BaseModel):
    page: int = Field(ge=1)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)
    pritarta: bool = False            # the point is inside the outline the lane proposed and he said „Tinka"
    klausimas: str | None = Field(default=None, max_length=64)   # the Patikra question answered (journal note)
    # The viewer's room tool R (Pathon v3 W1-D): the outline is only PROPOSED — he reviews it and his next
    # click or Enter saves it through `outline-set` (`kaip: "parodyta"`). A preview is not an act: no journal row.
    perziura: bool = False


class PagePoint(BaseModel):
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)


class SplitSpace(BaseModel):
    page: int = Field(ge=1)
    a: PagePoint
    b: PagePoint
    su: str | None = Field(default=None, max_length=8)   # the neighbour whose face this room's pocket joins (2026-09-23)
    klausimas: str | None = Field(default=None, max_length=64)   # the Patikra question answered (journal note)


class OutlineSet(BaseModel):
    """A ring a PERSON drew or edited in the viewer (2026-10-16): display-frame page fractions, ≥ 3 points.
    `holes`: what he cut out of it („Atimti" — a column, a built-in closet, a shaft), each a ring inside it."""
    page: int = Field(ge=1)
    polygon_pct: list[list[float]] = Field(min_length=3, max_length=500)
    holes: list[list[list[float]]] | None = Field(default=None, max_length=50)
    klausimas: str | None = Field(default=None, max_length=64)   # the Patikra question answered (journal note)
    # „Kas atimama?" per hole: True — a column / shaft, its faces are painted walls (the default); False — a floor
    # opening or anything else with no walls. Missing or shorter than `holes` → True for the rest.
    holes_walls: list[bool] | None = Field(default=None, max_length=50)
    # „parodyta": the ring is the wall face he POINTED at with the room tool (`outline-at` with `perziura`, then
    # saved) — the outline is said to be the one he showed, and, like „Parodyti patalpą", an unread perimeter is
    # left to the walls rather than replaced by the ring's length. Absent: a ring he drew or edited.
    kaip: Literal["parodyta"] | None = None


class OutlineMerge(OutlineSet):
    """„Sujungti" (2026-10-16): the room in the path is ABSORBED into `kept_nr`, whose outline becomes the
    union the viewer drew (`polygon_pct`, `holes`)."""
    kept_nr: str = Field(min_length=1, max_length=8)


DRAWN = "nubrezta"               # `_konturas.saltinis` of an outline a person drew or edited vertex by vertex
MERGED = "sujungta"              # …of a room a person merged INTO another (`i`: the room that took its place)


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
    → (pdf_bytes, (W, H), parsed copy, dims, geo meta, scale of `page`, rooms, the room, the STORED project —
    untouched, what `previous` is read from)."""
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
    return pdf_bytes, (W, H), parsed, dims, geo, float(scale), rooms, room, project


def _previous(stored: dict, answer: dict, room_nr: str | None = None, extra_keys: tuple[str, ...] = ()) -> dict:
    """What an answer would change, AS STORED before it (Pathon v3 W1-D: „Atšaukti" after every save): for each
    room the answer gives keys to (`room` — that is `room_nr` — or `rooms`), every geometry key (+ `extra_keys`)
    with its stored value, null where the room had none; for each neighbour in `kitu_angos`, its stored
    openings. The browser PUTs it back through the same route to undo the save."""
    by_nr = {_nr(r): r for r in (stored.get("patalpos") or []) if isinstance(r, dict)}
    changed = list((answer.get("rooms") or {}).keys()) if isinstance(answer.get("rooms"), dict) else (
        [str(room_nr)] if room_nr is not None and isinstance(answer.get("room"), dict) else [])
    out: dict[str, dict] = {}
    for nr in changed:
        r = by_nr.get(str(nr)) or {}
        out[str(nr)] = {k: copy.deepcopy(r.get(k)) for k in (*GEOMETRY_ROOM_KEYS, *extra_keys)}
    for nr in (answer.get("kitu_angos") or {}):
        if str(nr) not in out:
            out[str(nr)] = {"_angos_sienose": copy.deepcopy((by_nr.get(str(nr)) or {}).get("_angos_sienose"))}
    return out


def _with_previous(stored: dict, answer: dict, room_nr: str | None = None, extra_keys: tuple[str, ...] = ()) -> dict:
    """`answer` + its `previous` when it is a saving answer (`status: "ok"`); any other answer unchanged."""
    if not isinstance(answer, dict) or answer.get("status") != "ok":
        return answer
    return {**answer, "previous": _previous(stored, answer, room_nr, extra_keys)}


# Plain `def`: PDF parsing and geometry, 100 % blocking — the threadpool's job.
@router.post("/{project_id}/rooms/{room_nr}/outline-at")
def api_room_outline_at(request: Request, project_id: str, room_nr: str, body: OutlineAt):
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room, stored = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
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
                    divided = _with_previous(stored, _divided(parsed, pdf_bytes, dims, rooms, [_nr(room), other], body.page, cut))
                    return divided if body.perziura else _remembered(project_id, divided, klausimas=body.klausimas)
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

    answer = _with_previous(stored, {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }, _nr(room))
    return answer if body.perziura else _remembered(project_id, answer, _nr(room), klausimas=body.klausimas)


def _ring_of(raw: list[list[float]], what: str) -> list[tuple[float, float]]:
    ring: list[tuple[float, float]] = []
    for pt in raw:
        if len(pt) != 2 or not all(0.0 <= float(v) <= 1.0 for v in pt):
            raise HTTPException(status_code=400, detail=f"{what} taškai turi būti lapo dalys 0–1")
        ring.append((float(pt[0]), float(pt[1])))
    return ring


def _drawn_rings(body: OutlineSet) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    """The outline and its holes as page fractions — validated AFTER ownership (a stranger's malformed ring
    gets the same 404 as a well-formed one)."""
    ring = _ring_of(body.polygon_pct, "Kontūro")
    holes = []
    for raw in body.holes or []:
        if not 3 <= len(raw) <= 200:
            raise HTTPException(status_code=400, detail="Išpjovoje turi būti nuo 3 iki 200 taškų")
        holes.append(_ring_of(raw, "Išpjovos"))
    return ring, holes


def _measured(ring, holes, size: tuple[float, float], scale: float) -> dict:
    """Area (outer − holes), the OUTER perimeter, and the holes' own perimeter kept apart — whether the
    faces round a column count as wall surface is the engine's question, not this route's."""
    from shapely.geometry import Polygon
    W, H = size
    outer = Polygon([(x * W, y * H) for x, y in ring])
    if outer.area < 1.0:
        raise HTTPException(status_code=400, detail="Kontūras per mažas arba išsigimęs")
    if not outer.is_valid:
        raise HTTPException(status_code=400, detail="Kontūras kertasi pats su savimi")
    cut = []
    for h in holes:
        hole = Polygon([(x * W, y * H) for x, y in h])
        if hole.area < 1.0 or not hole.is_valid:
            raise HTTPException(status_code=400, detail="Išpjova per maža arba kertasi pati su savimi")
        if not outer.contains(hole):
            raise HTTPException(status_code=400, detail="Išpjova turi būti visa kontūro viduje")
        if any(hole.intersects(o) for o in cut):
            raise HTTPException(status_code=400, detail="Išpjovos persidengia")
        cut.append(hole)
    perim_pt = outer.exterior.length
    holes_m = [{"perimetras_m": round(h.exterior.length * scale, 2), "plotas_m2": round(h.area * scale * scale, 2),
                "kampai": _convex_corners(h, scale)} for h in cut]
    return {
        "skyles": holes_m,
        "plotas_m2": round((outer.area - sum(h.area for h in cut)) * scale * scale, 2),
        "perimetras_m": round(perim_pt * scale, 2),
        "skyliu_plotas_m2": round(sum(h.area for h in cut) * scale * scale, 2) if cut else None,
        "skyliu_perimetras_m": round(sum(h.exterior.length for h in cut) * scale, 2) if cut else None,
    }


def _convex_corners(hole, scale: float) -> int:
    """The hole's corners that stick INTO the room (a column's outer corners: corner bead): the convex vertices
    of the hole's own ring, straight runs and jogs under 0,10 m skipped (`ring_corner_counts`)."""
    return ring_corner_counts(list(hole.exterior.coords), m_per_unit=scale)[0]


def _set_outline(room: dict, ring, holes, page: int, size: tuple[float, float], scale: float,
                 *, table_m2: float | None = None, extra: dict | None = None,
                 holes_walls: list[bool] | None = None, saltinis: str = DRAWN) -> float:
    """Write the person's ring (and holes) onto `room` as its corrected outline → the drawn perimeter.
    `table_m2`: the printed area the drawn one is compared with (default: the room's own). `saltinis`: what he
    did — drew it (`nubrezta`, the default) or pointed at the wall face with the room tool (`parodyta`)."""
    m = _measured(ring, holes, size, scale)
    if table_m2 is None:
        table = room.get("plotas_m2")
        table_m2 = float(table) if isinstance(table, (int, float)) and not isinstance(table, bool) and float(table) > 0 else None
    paklaida = round((m["plotas_m2"] - table_m2) / table_m2, 4) if table_m2 else None
    room["polygon_pct"] = [[round(x, 5), round(y, 5)] for x, y in ring]
    if holes:
        room["polygon_holes_pct"] = [[[round(x, 5), round(y, 5)] for x, y in h] for h in holes]
    else:
        room.pop("polygon_holes_pct", None)
    room["polygon_source"] = "corrected"
    room["polygon_corrected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    own = room.get("plotas_m2")
    room["_konturas"] = {"page": page, "plotas_m2": m["plotas_m2"], "perimetras_m": m["perimetras_m"],
                         "plotas_uzrasas_m2": own if isinstance(own, (int, float)) and not isinstance(own, bool) and own > 0 else None,
                         "paklaida": paklaida, "plotas_nesutampa": False, "saltinis": saltinis}
    if holes:
        walls = list(holes_walls or [])
        skyles = [{**h, "sienos": bool(walls[i]) if i < len(walls) else True} for i, h in enumerate(m["skyles"])]
        room["_konturas"].update(skyles=skyles, skyliu_plotas_m2=m["skyliu_plotas_m2"],
                                 skyliu_perimetras_m=m["skyliu_perimetras_m"])
    if extra:
        room["_konturas"].update(extra)
    for stale in ("_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve", "_angos_sienose"):
        room.pop(stale, None)
    if str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis", "sienu_konturas"):
        # a perimeter that rested on the OLD outline — the walls are read afresh along the new one
        for stale in _ESTIMATE_KEYS:
            room.pop(stale, None)
    return m["perimetras_m"]


def _drawn_perimeter_if_unread(room: dict, perimetras: float) -> None:
    if str(room.get("perimetras_saltinis") or "") in ("", "vision"):
        # no dimension strings along the drawn walls: the drawn perimeter is the room's, named as such
        room["_perimetras_pries_geometrija"] = room.get("perimetras_m")
        room["perimetras_m"] = perimetras
        room["perimetras_saltinis"] = "sienu_konturas"


@router.post("/{project_id}/rooms/{room_nr}/outline-set")
def api_room_outline_set(request: Request, project_id: str, room_nr: str, body: OutlineSet):
    """The ring the person drew IS the room's outline (2026-10-16, Togal analysis §10): marked `corrected`
    (the lane never re-traces it), its area and perimeter measured at the sheet's scale, its walls and
    openings read again — exactly what a click (`outline-at`) does, with the person's geometry instead of
    the wall solid's face. The printed area stays the room's area; the drawn one is shown beside it
    (`_konturas.plotas_m2`, `paklaida`). Holes („Atimti") come off the drawn area; their perimeter is kept
    apart (`_konturas.skyliu_perimetras_m`), never added to the room's `perimetras_m`. Each hole is recorded in
    `_konturas.skyles[i]` with its perimeter, its convex corners and his answer to „Kas atimama?" (`sienos`):
    a column or shaft whose faces are painted walls (the engine adds its perimeter and corners) or not. Saves nothing — the sheet patches
    the room and recomputes."""
    # Ownership FIRST (tests/test_route_ownership_policy.py): a stranger's malformed ring must get the
    # same 404 as a stranger's well-formed one — never a 400 that says the project exists.
    _project_for(request, project_id)
    ring, holes = _drawn_rings(body)
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room, stored = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    pointed = body.kaip == "parodyta"
    perimetras = _set_outline(room, ring, holes, body.page, (W, H), scale, holes_walls=body.holes_walls,
                              saltinis=POINTED_AT if pointed else DRAWN)
    apply_geometry(parsed, pdf_bytes, dims)
    if not pointed:
        _drawn_perimeter_if_unread(room, perimetras)
    return _remembered(project_id, _with_previous(stored, {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }, _nr(room)), _nr(room), klausimas=body.klausimas)


# „Sujungti" writes these room keys besides the geometry ones (2026-10-16, follow-up (a)): the kept room bills BOTH
# table rows and holds both rooms' openings; the absorbed one is marked structurally and lists nothing of its own.
MERGE_ROOM_KEYS = ("plotas_m2", "plotas_saltinis", "_plotas_pries_sujungima", "_sujungimas", "elementai",
                   "_sujungta_i", "_elementai_pries_sujungima", "_perimetras_pries_sujungima", "n_partition_walls")
MERGED_AREA = "eksplikacija_sujungta"     # `plotas_saltinis` of a room that bills two eksplikacija rows


def _lt(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


# `grindu_danga` → (nominative, genitive, accusative): what the merge warning says the floor is, moves from, moves to
_FLOOR_WORDS = {
    "plyteles": ("plytelės", "plytelių", "plyteles"),
    "minksta": ("parketas arba laminatas", "parketo arba laminato", "parketą arba laminatą"),
    "be_dangos": ("betonas be dangos", "betono be dangos", "betoną be dangos"),
}


def _floor_kind(r: dict) -> str | None:
    """The room's floor covering: what the floor plan says (`grindu_danga`), else what the engine laid."""
    k = r.get("grindu_danga")
    if k in _FLOOR_WORDS:
        return k

    def pos(f):
        v = r.get(f)
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
    return "plyteles" if pos("plyteles_grindys_m2") else ("minksta" if pos("pvc_grindys_m2") else None)


def merge_finish_warning(kept: dict, gone: dict, kept_nr: str, gone_nr: str, both: float, b: float) -> str | None:
    """„Sujungti" applies the kept room's finishes to the whole area. When the two rooms' floor coverings or wall
    tiles differ that moves billed quantities between lines — say so before the merge and keep it after."""
    parts = []
    fk, fg = _floor_kind(kept), _floor_kind(gone)
    if fk and fg and fk != fg:
        parts.append(f"{gone_nr} grindys {_FLOOR_WORDS[fg][0]}, {kept_nr} {_FLOOR_WORDS[fk][0]}")
    wall_tiles = gone.get("plyteles_sienos_m2")
    wall_tiles = float(wall_tiles) if isinstance(wall_tiles, (int, float)) and not isinstance(wall_tiles, bool) else 0.0
    kept_tiles = kept.get("plyteles_sienos_m2")
    kept_tiles = float(kept_tiles) if isinstance(kept_tiles, (int, float)) and not isinstance(kept_tiles, bool) else 0.0
    lost_tiles = wall_tiles > 0 and kept_tiles <= 0
    if not parts and not lost_tiles:
        return None
    text = "Patalpų apdaila skiriasi: " + (parts[0] if parts else f"{gone_nr} sienose plytelės, {kept_nr} — ne")
    text += f" — sujungus visam plotui ({_lt(both)} m²) bus taikoma {kept_nr} apdaila"
    tail = []
    if parts and b > 0:
        tail.append(f"{_lt(b)} m² pereis iš {_FLOOR_WORDS[fg][1]} į {_FLOOR_WORDS[fk][2]}")
    if lost_tiles:
        tail.append(f"{gone_nr} sienų plytelių ({_lt(wall_tiles)} m²) sąmatoje nebeliks")
    return text + ("; " + "; ".join(tail) if tail else "") + "."


@router.post("/{project_id}/rooms/{room_nr}/outline-merge")
def api_room_outline_merge(request: Request, project_id: str, room_nr: str, body: OutlineMerge):
    """„Sujungti" (2026-10-16): room `room_nr` is merged INTO `kept_nr`. The kept room takes the union the
    viewer drew — exactly as `outline-set` writes a drawn ring, its drawn area compared with BOTH printed
    areas — and bills both: `plotas_m2 = a + b` (`plotas_saltinis = "eksplikacija_sujungta"`, the table's
    own figure kept in `_plotas_pries_sujungima`, the sentence in `_sujungimas.sakinys`). A window or a door
    in the absorbed half is still there: the absorbed room's `elementai` move into the kept room (each
    carried record says where from, `_is_patalpos`). The kept room's finishes cover the whole area. The
    absorbed room keeps its table row and is marked STRUCTURALLY — `_sujungta_i: kept_nr`, no outline, no
    openings of its own — so the engine bills it inside the kept room and nowhere else. Saves nothing: the
    sheet applies `rooms` (geometry keys) and `sujungimas` (MERGE_ROOM_KEYS, null = remove)."""
    _project_for(request, project_id)
    ring, holes = _drawn_rings(body)
    kept_nr, gone_nr = str(body.kept_nr).strip(), str(room_nr).strip()
    if kept_nr == gone_nr:
        raise HTTPException(status_code=400, detail="Patalpos su ja pačia sujungti negalima")
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, kept, stored = _todays_reading(request, project_id, kept_nr, body.page, "room_outline")
    gone = next((r for r in rooms if _nr(r) == gone_nr), None)
    if gone is None:
        raise HTTPException(status_code=404, detail="Patalpa nerasta")
    if gone.get("_sujungta_i") or kept.get("_sujungta_i"):
        raise HTTPException(status_code=400, detail="Ši patalpa jau sujungta su kita")

    def printed(r):
        v = r.get("plotas_m2")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) > 0 else None

    a, b = printed(kept) or 0.0, printed(gone) or 0.0
    both = round(a + b, 2)
    finish_warning = merge_finish_warning(kept, gone, kept_nr, gone_nr, both, b)

    def outline_perimeter(r):
        """The walls its outline counts (the lane's / the person's figure, imaginary edges left out), or None."""
        k = r.get("_konturas") if isinstance(r.get("_konturas"), dict) else {}
        v = k.get("perimetras_m")
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None

    def number(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None

    k_a, k_b = outline_perimeter(kept), outline_perimeter(gone)
    p_a, p_b = number(kept.get("perimetras_m")), number(gone.get("perimetras_m"))
    # What the floor plan says for each room, AS STORED: the union outline holds BOTH rooms' coverings, so the
    # lane's re-read found two and took the kept room's away („plytelės" → „—", Patikra asked again — W0-A-2).
    # The kept room's finish covers the whole area (`_sujungimas.apdaila`); the merge changes no covering.
    floors = {}
    for r in stored.get("patalpos") or []:
        if isinstance(r, dict) and _nr(r) in (kept_nr, gone_nr) and r.get("grindu_danga"):
            floors[_nr(r)] = {k: copy.deepcopy(r[k]) for k in FLOOR_KEYS if k in r}
    perimetras = _set_outline(kept, ring, holes, body.page, (W, H), scale, table_m2=both or None,
                              extra={"prijungta": [gone_nr], "plotas_uzrasas_kartu_m2": both or None},
                              holes_walls=body.holes_walls)

    # ── what the kept room bills: both table rows, both rooms' openings ──
    before = kept.get("_sujungimas") if isinstance(kept.get("_sujungimas"), dict) else None
    parts = list((before or {}).get("plotai") or [{"nr": kept_nr, "plotas_m2": a}]) + [{"nr": gone_nr, "plotas_m2": b}]
    if both > 0:
        kept["_plotas_pries_sujungima"] = kept.get("_plotas_pries_sujungima", printed(kept))
        kept["plotas_m2"] = both
        kept["plotas_saltinis"] = MERGED_AREA
    kept["_sujungimas"] = {
        "su": [p["nr"] for p in parts if p["nr"] != kept_nr],
        "plotai": parts,
        "sakinys": "Plotas: " + " + ".join(_lt(p["plotas_m2"]) for p in parts) + " m² iš eksplikacijos — patalpos sujungtos",
        "apdaila": "Visam plotui taikoma patalpos " + kept_nr + " apdaila",
    }
    if finish_warning:
        kept["_sujungimas"]["apdaila_skiriasi"] = finish_warning
    # The merged room's corners come off the union outline (counted here, once: a rebuild reads the numbers),
    # and the partitions of the space still stand — rooms are merged because no wall separates them — so
    # both rooms' partition ends stay with the kept room (2026-10-16 follow-up (1)).
    vi, isr = ring_corner_counts([(x * W, y * H) for x, y in ring], m_per_unit=scale)
    def ends(r):
        v = r.get("n_partition_walls")
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else 0
    before_ends = (before or {}).get("pertvaru_galai_dalys") or [ends(kept)]
    parts_ends = list(before_ends) + [ends(gone)]
    kept["n_partition_walls"] = sum(parts_ends)
    kept["_sujungimas"].update(
        kampai_vidiniai=vi, kampai_isoriniai=isr, pertvaru_galai=kept["n_partition_walls"],
        pertvaru_galai_dalys=parts_ends,
        kampai=(f"Kampai iš sujungto kontūro: {vi} vidiniai, {isr} išoriniai; pertvarų galai: "
                + " + ".join(str(p) for p in parts_ends) + " iš sujungtų patalpų — pataisykite patalpos lape"))
    carried = [{**e, "_is_patalpos": gone_nr} for e in (gone.get("elementai") or []) if isinstance(e, dict)]
    kept["elementai"] = [e for e in (kept.get("elementai") or []) if isinstance(e, dict)] + carried

    def absorb(r):
        for k in GEOMETRY_ROOM_KEYS:
            if k not in ("perimetras_m", "perimetras_saltinis", "grindu_danga", "grindu_danga_saltinis", "_grindu_danga", "_grindu_dangos_dvi"):
                r.pop(k, None)
        r["_konturas"] = {"page": body.page, "saltinis": MERGED, "i": kept_nr, "plotas_m2": 0.0, "perimetras_m": 0.0,
                          "plotas_uzrasas_m2": printed(r)}
        r["_sujungta_i"] = kept_nr

    gone["_elementai_pries_sujungima"] = gone.get("elementai") or []
    gone["elementai"] = []
    absorb(gone)
    apply_geometry(parsed, pdf_bytes, dims)
    absorb(gone)            # whatever the lane made of a room with no outline today is not its geometry: it is merged
    for nr, r in ((kept_nr, kept), (gone_nr, gone)):
        if nr in floors:     # the merge changes no floor covering the plan gives a room
            for k in FLOOR_KEYS:
                r.pop(k, None)
            r.update(floors[nr])
            r.pop("_grindu_dangos_dvi", None)
    _drawn_perimeter_if_unread(kept, perimetras)
    if str(kept.get("perimetras_saltinis") or "") in ("user_override", "manual") and p_a and p_b:
        # A perimeter he typed is never re-read — but it described ONE room. The merged room's walls are both
        # rooms' walls less the run they shared, counted once on each side: (outline A + outline B − union).
        # A boundary drawn between two rooms of one open space is no wall and is in neither outline (→ 0).
        shared2 = max(0.0, k_a + k_b - perimetras) if (k_a and k_b) else None
        if shared2 is not None:
            kept["_perimetras_pries_sujungima"] = kept.get("_perimetras_pries_sujungima", p_a)
            kept["perimetras_m"] = round(p_a + p_b - shared2, 2)
            kept["_sujungimas"]["perimetras"] = (
                f"Perimetras: {_lt(p_a)} + {_lt(p_b)}" + (f" − {_lt(shared2)}" if shared2 >= 0.01 else "")
                + f" = {_lt(kept['perimetras_m'])} m — jūsų įrašyti perimetrai"
                + (", be bendros sienos abiejų pusių" if shared2 >= 0.01 else ""))
        else:
            kept["_sujungimas"]["perimetras"] = (f"Perimetras lieka {_lt(p_a)} m (įrašytas jūsų) — patalpos {gone_nr} "
                                                 "sienų prie jo pridėti negalima, nes vienas kontūras neturi perimetro")
    return _remembered(project_id, _with_previous(stored, {
        "status": "ok",
        "rooms": {nr: {k: r.get(k) for k in GEOMETRY_ROOM_KEYS} for nr, r in ((kept_nr, kept), (gone_nr, gone))},
        "sujungimas": {nr: {k: r.get(k) for k in MERGE_ROOM_KEYS} for nr, r in ((kept_nr, kept), (gone_nr, gone))},
        "ispejimas": finish_warning,
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not kept and r is not gone and isinstance(r.get("_angos_sienose"), dict)},
    }, extra_keys=MERGE_ROOM_KEYS), klausimas=body.klausimas)


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
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room, stored = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
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
    return _remembered(project_id, _with_previous(stored, _divided(parsed, pdf_bytes, dims, rooms, members, body.page, hit)),
                       klausimas=body.klausimas)


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
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room, stored = _todays_reading(request, project_id, room_nr, page, "room_outline")
    status, members, seats = _shared_space(rooms, room, _laid_onto(page, geo.get("sutapdinimas") or {}))
    if status:
        return {"status": status}
    by_nr = {_nr(r): r for r in rooms}
    hit = propose_split(pdf_bytes, page, seats, {nr: by_nr[nr].get("plotas_m2") for nr in members}, scale, (W, H),
                        face_pct=space.get("polygon_pct") if space.get("kisene") else None)
    if hit["status"] != "ok":
        return {"status": hit["status"]}
    return {**_with_previous(stored, _divided(parsed, pdf_bytes, dims, rooms, members, page, hit)),
            "line_pct": hit["line_pct"], "pagal": hit["pagal"], "page": page}


# ── „Atšaukti" after every save (Pathon v3 W1-D, D3; audit F5) ─────────────────────────────────────────────
# Every saving answer above carries `previous` — the rooms' keys as stored before it. The browser's undo PUTs
# that `previous` back through the SAME path; the server saves nothing (as everywhere here): it checks the
# owner, the rooms and the keys, writes ONE journal row per room with source „atsaukta", and answers in the
# forward answer's shape (`rooms` = geometry keys, `sujungimas` = merge keys, null = remove), so the sheet
# lands it with the very functions it landed the save with. The same PUT twice is the same answer.

UNDONE = "atsaukta"                    # `corrections.source` of an undo


class OutlineRestore(BaseModel):
    """„Atšaukti": `previous` of a saving answer, {room nr: {key: value | null}}."""
    previous: dict[str, Any] = Field(default_factory=dict)
    klausimas: str | None = Field(default=None, max_length=64)   # the Patikra question the undone act answered


def _restore(request: Request, project_id: str, room_nr: str, body: OutlineRestore, act: str,
             allowed: tuple[str, ...]) -> dict:
    stored = _project_for(request, project_id)          # ownership FIRST (tests/test_route_ownership_policy.py)
    prev = body.previous
    if not prev or len(prev) > 60 or not all(isinstance(v, dict) for v in prev.values()):
        raise HTTPException(status_code=400, detail="Nėra ką atšaukti")
    wanted = str(room_nr).strip()
    keys = {str(nr).strip(): v for nr, v in prev.items()}
    if wanted not in keys:
        raise HTTPException(status_code=400, detail="Atšaukti galima tik šios patalpos pakeitimą")
    by_nr = {_nr(r): r for r in (stored.get("patalpos") or []) if isinstance(r, dict)}
    if any(nr not in by_nr for nr in keys):
        raise HTTPException(status_code=404, detail="Patalpa nerasta")
    bad = sorted({k for v in keys.values() for k in v if k not in allowed})
    if bad:
        raise HTTPException(status_code=400, detail="Šių patalpos duomenų atšaukti negalima: " + ", ".join(bad))

    answer: dict = {
        "status": "ok",
        "rooms": {nr: {k: v[k] for k in GEOMETRY_ROOM_KEYS if k in v} for nr, v in keys.items()},
        "kitu_angos": {},
        "atsaukta": act,
    }
    if act == "sujungimas":
        answer["sujungimas"] = {nr: {k: v[k] for k in MERGE_ROOM_KEYS if k in v} for nr, v in keys.items()}
    try:
        import db as _db
        for nr, v in keys.items():
            if not set(v) - {"_angos_sienose"}:
                continue                                   # a neighbour's openings only: not a room he changed
            k = v.get("_konturas") if isinstance(v.get("_konturas"), dict) else {}
            _db.log_correction_once(
                project_id=project_id, field_path=f"patalpa.{nr}.kontūras", old_value=None,
                new_value={UNDONE: act, "saltinis": k.get("saltinis"), "plotas_m2": k.get("plotas_m2")},
                source=UNDONE, room_nr=nr, note=body.klausimas or None)
    except Exception as exc:  # noqa: BLE001 — the journal is never the undo
        log.warning("undo journal write failed project=%s: %r", project_id, exc)
    return answer


@router.put("/{project_id}/rooms/{room_nr}/outline-set")
def api_room_outline_set_undo(request: Request, project_id: str, room_nr: str, body: OutlineRestore):
    """Undo an outline-set answer (a drawn, edited, pointed or holed outline; a split's halves)."""
    return _restore(request, project_id, room_nr, body, "konturas", GEOMETRY_ROOM_KEYS)


@router.put("/{project_id}/rooms/{room_nr}/outline-merge")
def api_room_outline_merge_undo(request: Request, project_id: str, room_nr: str, body: OutlineRestore):
    """Undo „Sujungti": both rooms' geometry and merge keys as they were."""
    return _restore(request, project_id, room_nr, body, "sujungimas", (*GEOMETRY_ROOM_KEYS, *MERGE_ROOM_KEYS))


@router.put("/{project_id}/rooms/{room_nr}/split-space")
def api_room_split_space_undo(request: Request, project_id: str, room_nr: str, body: OutlineRestore):
    """Undo a space divided by a line: both rooms' geometry as it was."""
    return _restore(request, project_id, room_nr, body, "padalijimas", GEOMETRY_ROOM_KEYS)


# ── „Atimti" in one click (Pathon v3 W5-A A4, design §2 T1 „subtract a column 3") ─────────────────────────────

class HoleAt(BaseModel):
    """A click inside a room's outline while „Atimti" is on: which closed shape of the drawing is under it."""
    page: int = Field(ge=1)
    x_pct: float = Field(ge=0.0, le=1.0)
    y_pct: float = Field(ge=0.0, le=1.0)


HOLE_SIMPLIFY_PT = 0.35          # a third of a point, like the wall solid the browser snaps to
HOLE_MAX_SHARE = 0.5             # a „hole" bigger than half the room is a room, not a column
HOLE_MIN_PT2 = 40.0              # without a scale: about 2 × 2 mm on paper
HOLE_MIN_M2 = 0.02               # with one: 14 × 14 cm — a speck of hatch is no column


def hole_at(pdf_bytes: bytes, page: int, x_pct: float, y_pct: float, room_ring_pct, m_per_pt: float | None = None) -> dict:
    """The smallest CLOSED shape the drawing has around the click, inside the room — proposed as a hole.

    Where it is looked for, in the drawing's own vectors (extractor/pdf_vectors), never a guess:
      · a piece of the wall solid standing alone in the room — a column („kolona"); the dominant wall colour's
        fills of ANY shape, since a square column is not wall-shaped (`_is_wall_shape` wants a long thin piece);
      · a void ringed by wall solid — a shaft („šachta");
      · a closed figure of drawn lines — a built-in closet, a shaft drawn in lines („nubraižyta figūra").
    → {status: "ok", hole_pct, kind, plotas_m2?} | {status: "outside"} | {status: "none"}. Saves nothing."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import polygonize, unary_union

    from extractor.pdf_vectors import dominant_wall_colour, filled_shapes, page_paths

    W, H, _ = page_geometry(pdf_bytes, page)
    room = Polygon([(float(x) * W, float(y) * H) for x, y in room_ring_pct])
    if not room.is_valid:
        room = room.buffer(0)
    pt = Point(x_pct * W, y_pct * H)
    if room.is_empty or not room.contains(pt):
        return {"status": "outside"}
    min_area = HOLE_MIN_M2 / (m_per_pt * m_per_pt) if m_per_pt else HOLE_MIN_PT2
    near = room.buffer(1.5)

    cands: list[tuple[str, Polygon]] = []
    shapes = filled_shapes(pdf_bytes, page)
    col = dominant_wall_colour(shapes)
    if col is not None:
        solid = unary_union([poly for c, poly in shapes if c == col])
        for part in (list(solid.geoms) if solid.geom_type == "MultiPolygon" else [solid]):
            if part.geom_type != "Polygon" or part.is_empty:
                continue
            if part.contains(pt):
                cands.append(("kolona", Polygon(part.exterior)))
            for ring in part.interiors:
                void = Polygon(ring)
                if void.contains(pt):
                    cands.append(("šachta", void))
    lines = []
    for path in page_paths(pdf_bytes, page, strokes=True):
        if path.get("stroke") is None or path.get("fill") is not None:
            continue
        for sub in path["subpaths"]:
            if len(sub) < 2:
                continue
            seg = LineString(sub)
            if seg.length > 0 and seg.intersects(near):
                lines.append(seg)
    if lines:
        for face in polygonize(unary_union(lines)):
            if face.contains(pt):
                cands.append(("nubraižyta figūra", face))

    best = None
    for kind, shape in cands:
        if not shape.is_valid:
            shape = shape.buffer(0)
        if shape.is_empty or shape.geom_type != "Polygon":
            continue
        if not near.contains(shape) or not (min_area <= shape.area <= HOLE_MAX_SHARE * room.area):
            continue
        if best is None or shape.area < best[1].area:
            best = (kind, shape)
    if best is None:
        return {"status": "none"}
    kind, shape = best
    shape = shape.simplify(HOLE_SIMPLIFY_PT, preserve_topology=True)
    if not room.contains(shape):
        # a column standing in the outline's line: the hole is the part inside the room (outline-set wants it inside)
        shape = shape.intersection(room.buffer(-0.05))
        if shape.geom_type == "MultiPolygon":
            shape = max(shape.geoms, key=lambda g: g.area)
        if shape.is_empty or shape.geom_type != "Polygon" or shape.area < min_area:
            return {"status": "none"}
    ring = [[round(x / W, 5), round(y / H, 5)] for x, y in list(shape.exterior.coords)[:-1]]
    if len(ring) < 3:
        return {"status": "none"}
    out = {"status": "ok", "page": page, "hole_pct": ring, "kind": kind}
    if m_per_pt:
        out["plotas_m2"] = round(shape.area * m_per_pt * m_per_pt, 2)
    return out


def _room_ring_on(room: dict, page: int):
    """The room's stored outline when it lies on `page` (the frame the click comes in), else None."""
    poly = room.get("polygon_pct")
    if not isinstance(poly, list) or len(poly) < 3:
        return None
    src = int((room.get("_konturas") or {}).get("page") or room.get("puslapio_nr") or 0)
    return poly if src == int(page) else None


# Plain `def`: PDFium parsing and shapely — the threadpool's job.
@router.post("/{project_id}/rooms/{room_nr}/hole-at")
def api_room_hole_at(request: Request, project_id: str, room_nr: str, body: HoleAt):
    """„Atimti" in one click: the closed shape under the click PROPOSED as the room's hole — the viewer shows it
    dashed and his Enter saves it through `outline-set` (Undo there). Read only; no journal row."""
    project = _project_for(request, project_id)          # ownership FIRST (tests/test_route_ownership_policy.py)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "room_hole")   # its own bucket: a click must not eat the sheets' geometry fetches
    wanted = str(room_nr).strip()
    room = next((r for r in (project.get("patalpos") or []) if isinstance(r, dict) and _nr(r) == wanted), None)
    if room is None:
        raise HTTPException(status_code=404, detail="Patalpa nerasta")
    ring = _room_ring_on(room, body.page)
    if ring is None:
        raise HTTPException(status_code=400, detail="Šios patalpos kontūro šiame lape nėra")
    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("hole-at pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    W, H, _ = page_geometry(pdf_bytes, body.page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")
    geo = ((project.get("_meta") or {}).get("geometrija") or {})
    m_per_pt = ((geo.get("masteliai") or {}).get(str(body.page)) or {}).get("m_per_pt")
    return hole_at(pdf_bytes, body.page, body.x_pct, body.y_pct, ring, float(m_per_pt) if m_per_pt else None)

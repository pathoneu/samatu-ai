"""/api/projects/{project_id}/free-reread — the geometry lane for a project that
is already stored. No Vision call, no cost.

The lane (extractor/geometry_lane.py: vector outlines, perimeters ADDED from
the strings written on the plan, floor coverings off the floor plan) ran only
inside a full extraction, so a project read before it existed kept its guessed
perimeters and box outlines, and the one free way to refresh it was a
localhost dev script. The lane needs nothing but the stored PDF and the stored
rooms.

GET  → may this project be read again for free, and is there anything newer
       to read (`geometry_lane.LANE_VERSION` against `_meta.geometrija.versija`)?
       Cheap: a storage existence check, no PDF parsing.
POST → the lane on a COPY of the project; answers with its rooms and meta.

The server SAVES NOTHING. What a re-read may and may not replace — rooms he
verified, numbers he typed, outlines he corrected, prices on his rows — is
decided in one place (frontend/src/lib/mergeReextract.js), and the rows are
rebuilt through the same /recompute-interior path every room edit takes. A
second write path here would be a second set of rules about his work.
"""
from __future__ import annotations

import copy
import logging
import threading

from fastapi import APIRouter, HTTPException, Request

import auth as _auth
import db as _db
from extractor.geometry_lane import LANE_VERSION, apply_geometry

log = logging.getLogger("samatu.free_reread")

router = APIRouter(prefix="/api/projects", tags=["free-reread"])

NO_PDF = "Šio projekto brėžinio saugykloje nėra — perskaityti iš naujo galima tik įkėlus PDF."

# One read per project at a time: the lane holds the process-wide PDFium lock
# for seconds on a heavy drawing, and two answers for one project would race
# each other into the browser's merge.
_running: set[str] = set()
_running_lock = threading.Lock()


def _safe_project_id(project_id: str) -> str:
    if not project_id or not all(c.isalnum() or c in ("-", "_") for c in project_id):
        raise HTTPException(status_code=400, detail="Netinkamas projekto ID")
    return project_id


def _project_for(request: Request, project_id: str) -> dict:
    _safe_project_id(project_id)
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail="Projektas nerastas")
    return project


def _stored_version(project: dict) -> int | None:
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    geo = meta.get("geometrija") if isinstance(meta.get("geometrija"), dict) else {}
    try:
        return int(geo["versija"]) if geo.get("versija") is not None else None
    except (TypeError, ValueError):
        return None


def _has_pdf(project_id: str) -> bool:
    from storage import get_storage, pdf_key
    try:
        return bool(get_storage().exists(pdf_key(project_id)))
    except Exception as exc:  # noqa: BLE001 — a storage hiccup means „not now", not a 500
        log.warning("free-reread storage check failed for %s: %r", project_id, exc)
        return False


@router.get("/{project_id}/free-reread")
def api_free_reread_status(request: Request, project_id: str):
    project = _project_for(request, project_id)
    available = _has_pdf(project_id)
    stored = _stored_version(project)
    return {
        "available": available,
        "needed": bool(available and (stored is None or stored < LANE_VERSION)),
        "versija": LANE_VERSION,
        "projekto_versija": stored,
        "reason": None if available else NO_PDF,
    }


def zone_pages(lane: dict) -> list[int]:
    """The sheets the lane read the plan on — its alignment groups, the sheets it traced, the floor sheets —
    whose zones the re-read stores. Every other sheet's zones are one GET away (api/sheet_zones.py): a
    whole 65-sheet drawing is ~40 s of zone reading (objektas_b), too much to add to every re-read."""
    pages: set[int] = set()
    for group in lane.get("grupes") or []:
        pages.update(int(p) for p in group)
    pages.update(int(p) for p in lane.get("lapai") or [])
    pages.update(int(p) for p in (lane.get("grindu_dangos") or {}).get("lapai") or [])
    return sorted(p for p in pages if p >= 1)


def _store_zones(parsed: dict, pdf_bytes: bytes, lane: dict, project_id) -> None:
    """`_meta.zonos` = {"<page>": [zone, …]} for the lane's sheets (extractor/sheet_zones.py). An ADDITION:
    no room key changes, `LANE_VERSION` stays, and the browser's merge (lib/freeReread.js) takes only
    `_meta.geometrija`, so nothing lands on the stored project from here in this wave. Never fails the read."""
    try:
        from extractor.sheet_zones import REREAD_TABLE_MAX_OBJECTS, zones_for_pages
        parsed.setdefault("_meta", {})["zonos"] = zones_for_pages(pdf_bytes, zone_pages(lane),
                                                                  table_max_objects=REREAD_TABLE_MAX_OBJECTS)
    except Exception as exc:  # noqa: BLE001 — zones are extra evidence, never the reason a re-read fails
        log.warning("free-reread sheet zones failed for %s: %r", project_id, exc)


def read_tables(pdf_bytes: bytes, project_id=None) -> dict:
    """The „lentelės" stage (Pathon v3 W3-A): the drawing's ruled tables and schedules (extractor/schedules.py,
    €0) → {"meta": `_meta.lenteles`, "_langu_ziniarastis": …, "_apdailos_lentele": …}. An ADDITION like the
    zones: no room key changes, `LANE_VERSION` stays; the door schedule keeps its own scan (`kiekiai`), which
    reads the same ruled table through the same reader. Never fails the read."""
    try:
        from extractor.schedules import finish_record, read_schedules, tables_meta, windows_record
        from extractor.sheet_zones import REREAD_TABLE_MAX_OBJECTS
        res = read_schedules(pdf_bytes, max_objects=REREAD_TABLE_MAX_OBJECTS)
        return {"meta": tables_meta(res), "_langu_ziniarastis": windows_record(res, pdf_bytes),
                "_apdailos_lentele": finish_record(res)}
    except Exception as exc:  # noqa: BLE001 — tables are extra evidence, never the reason a re-read fails
        log.warning("free-reread tables failed for %s: %r", project_id, exc)
        return {}


FIGURES_FLAG = "SAMATU_REREAD_FIGURES"


def read_figures_and_heights(parsed: dict, pdf_bytes: bytes, project_id=None) -> dict:
    """Pathon v3 W5-D, D6 — behind SAMATU_REREAD_FIGURES (default off: returns {} and touches nothing). The paid
    reading's step 2.44 for a stored project: one text-layer scan (plan_area_annotations.scan_text_layer) → the
    designer's own figures (`_autoriaus_kiekiai`), the walls' and floors' anchors billed from them
    (`_walls_anchor`, `_floor_anchors` — the same helpers the paid reading uses) and the heights the plan states
    for ONE room, written on `parsed`'s rooms (`apply_height_statements`: only a room that carries our default).
    These move billed quantities, so the flag stays off until the manager's measured OK. Never fails the read."""
    import os
    if os.environ.get(FIGURES_FLAG) != "1":
        return {}
    try:
        from extractor.plan_area_annotations import apply_height_statements, scan_text_layer, text_pages_from_classification
        from extractor.vision_call import _floor_anchors_from_figures, _walls_anchor_from_figures
        pages = text_pages_from_classification(parsed.get("puslapiai") or [])
        scan = scan_text_layer(pdf_bytes, pages=pages or None)
        out: dict = {"_autoriaus_kiekiai": scan.get("figures") or []}
        wa = _walls_anchor_from_figures(scan.get("figures"))
        if wa:
            out["_walls_anchor"] = wa
        fa = _floor_anchors_from_figures(scan.get("figures"))
        if fa:
            out["_floor_anchors"] = fa
        hs = apply_height_statements(parsed.get("patalpos") or [], scan.get("heights") or [])
        parsed.setdefault("_meta", {})["plan_height_statement"] = (
            {k: v for k, v in hs.items() if k != "rooms"} | {"rooms": len(hs.get("rooms") or [])})
        return out
    except Exception as exc:  # noqa: BLE001 — extra readings are never the reason a re-read fails
        log.warning("free-reread figures / heights failed for %s: %r", project_id, exc)
        return {}


def read_drawing(project: dict, pdf_bytes: bytes, *, on_stage=None) -> dict:
    """The free re-read's whole reading of one stored project — the geometry lane on a COPY of it, the
    drawing's tables (the „lentelės" stage, read while the lane moves from the text to the plan), then the
    door schedule and the vector symbols — answered in the shape POST /free-reread returns. Saves nothing.
    `on_stage` hears the lane's steps (geometry_lane.apply_geometry), "lenteles" between "tekstas" and
    "planas", and then "kiekiai" when the project-level scans start (api/detect_run.py shows them as stages)."""
    parsed = copy.deepcopy(project)
    tables: dict = {}

    def tables_once() -> None:
        if "done" not in tables:
            tables["done"] = True
            tables.update(read_tables(pdf_bytes, project.get("id")))

    def staged(name: str) -> None:
        if name == "planas" and "done" not in tables:
            # the lane has read the text layer and turns to the plan: the tables are read here, so the stage
            # list reads mastelis → tekstas → lentelės → planas (the lane itself is not touched)
            if on_stage:
                on_stage("lenteles")
            tables_once()
        if on_stage:
            on_stage(name)

    try:
        out = apply_geometry(parsed, pdf_bytes, on_stage=staged)
    except Exception as exc:  # noqa: BLE001 — the lane never raises; if it ever does, nothing changes
        log.error("free-reread lane raised for %s: %r", project.get("id"), exc)
        return {"status": "ok", "lane": "failed", "patalpos": project.get("patalpos") or [],
                "_meta": project.get("_meta") or {}, "santrauka": None}
    if out.get("status") == "failed":
        return {"status": "ok", "lane": "failed", "patalpos": project.get("patalpos") or [],
                "_meta": project.get("_meta") or {}, "santrauka": None}
    floors = out.get("grindu_dangos") or {}
    tables_once()                       # a lane that stopped before the plan still gets the drawing's tables
    if on_stage:
        on_stage("kiekiai")
    # the drawing's door schedule (deterministic, $0) rides along: a project read before it existed
    # gets its frameless-door evidence with the same click (the browser's merge spreads project keys)
    schedule = None
    try:
        from extractor.door_schedule import scan_door_schedule
        schedule = scan_door_schedule(pdf_bytes)
    except Exception as exc:  # noqa: BLE001 — never the lane's failure
        log.warning("free-reread door schedule scan failed for %s: %r", project.get("id"), exc)
    # the symbols counted from the drawing's paths (extractor/vector_symbols): the diffuser rows take
    # this count on the next recompute
    vector_symbols = None
    try:
        from extractor.vector_symbols import scan_vector_symbols
        vector_symbols = scan_vector_symbols(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("free-reread vector symbol scan failed for %s: %r", project.get("id"), exc)
    figures = read_figures_and_heights(parsed, pdf_bytes, project.get("id"))
    # the schedules' codes counted where the plan writes them (Pathon v3 W5-D, D10 — extractor/schedule_tags.py):
    # evidence on the schedule record for the Patikra question `lentele_zymos`; no quantity reads it
    from extractor.schedule_tags import count_schedule_tags
    for rec in (schedule, tables.get("_langu_ziniarastis")):
        if isinstance(rec, dict):
            tags = count_schedule_tags(pdf_bytes, rec)
            if tags is not None:
                rec["zymos_plane"] = tags
    _store_zones(parsed, pdf_bytes, out, project.get("id"))
    if tables.get("meta") is not None:
        parsed.setdefault("_meta", {})["lenteles"] = tables["meta"]
    return {
        "status": "ok",
        "lane": out.get("status"),
        "patalpos": parsed.get("patalpos") or [],
        "_meta": parsed.get("_meta") or {},
        **({"_duru_ziniarastis": schedule} if schedule is not None else {}),
        **{k: tables[k] for k in ("_langu_ziniarastis", "_apdailos_lentele") if tables.get(k) is not None},
        **({"_vector_symbols": vector_symbols} if vector_symbols is not None else {}),
        **figures,
        "santrauka": {
            "konturai": len(out.get("konturai") or []),
            "perimetrai_sudeti": len(out.get("perimetrai_sudeti") or []),
            "perimetrai_tusti": len(out.get("perimetrai_tusti") or []),
            "grindu_dangos": len(floors.get("perskaityta") or {}),
            "sekundes": out.get("seconds"),
        },
    }


# Plain `def`: PDF parsing and geometry, 100 % blocking — the threadpool's job.
@router.post("/{project_id}/free-reread")
def api_free_reread(request: Request, project_id: str):
    project = _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "free_reread")

    with _running_lock:
        if project_id in _running:
            raise HTTPException(status_code=409, detail="Šis projektas jau skaitomas — palaukite, kol baigs.")
        _running.add(project_id)
    try:
        from storage import get_storage, pdf_key
        try:
            pdf_bytes = get_storage().get(pdf_key(project_id))
        except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
            log.warning("free-reread pdf fetch failed for %s: %r", project_id, exc)
            raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail=NO_PDF)

        return read_drawing(project, pdf_bytes)
    finally:
        with _running_lock:
            _running.discard(project_id)

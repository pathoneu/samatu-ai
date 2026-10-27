"""No-vision route for a vector PDF (v4, 2026-10-26 — founder decision).

OFF by default — set `SAMATU_NO_VISION_ROUTE=1` to enable. The gate measured on 2026-10-27 failed (billed
lines +8,4 pp vs baseline) because the route has no deterministic source yet for per-room LED niches, hidden /
sliding doors, built-in furniture, ceiling type, and openings on plans without wall outlines. The route lands
here so today's behaviour is byte-identical when the flag is unset, and the founder can switch it on locally.

When enabled: a vector PDF — walls as paths, dimensions and labels in the text layer — goes through this route
instead of Pass-1 Vision. The Vision pass costs ~1,16 USD and ~430 s on a 10-page project (objektas_h fresh
read, 2026-10-26); the deterministic lanes already in place (`extractor/geometry_lane.py`,
`extractor/room_identity.py`, `extractor/wall_finishes.py`, `extractor/legend_counts.py`, `text/page_kind.py`,
`text/heights.py`, `text/schema_llm.py`) do the same work in seconds and 0 USD. Raster / flattened PDFs keep
the Vision route (the decision reads the drawing).

Shape: the same `patalpos` / `puslapiai` / `warnings` / `pozicijos` / `santrauka` / `_meta` keys the Vision
route returns; `_meta.vision_pass = "none"` and `_meta.route = "no_vision_vector"` say so.

Stream events: the names the UI listens to (`pass1_started`, `pass1_completed`, `zoom_started`,
`zoom_completed`) are emitted with `skipped: true` and a `note` so the UI does not break. The drawing lanes
emit their own events as usual (`geometry_lane`, `wall_outline_lane`, `plan_area_lane`, `plan_dimension_lane`,
`page_kinds_from_text`, `legend_counts`).

Where a field has no deterministic source yet on a vector PDF (a room with no table row and no outline, a
description only a picture shows), the field is BLANK with a `_kilme` reason sentence — never a guess, never a
model reading pixels.

`SAMATU_FORCE_VISION=1` forces the old Vision route even when `SAMATU_NO_VISION_ROUTE=1` is set (stronger
off switch; keeps the golden replay pin working).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Callable

log = logging.getLogger("samatu.no_vision_route")

VECTOR_SENTENCE = "Brėžinys vektorinis — skaitoma be vaizdo modelio"
RASTER_SENTENCE = "Brėžinys rastrinis — paliekamas vaizdo modelio skaitymui"
MISSING_TABLE_SENTENCE = (
    "Patalpų eksplikacijos lentelė brėžinyje nerasta — vektorinio brėžinio be lentelės neperskaitome be "
    "vaizdo modelio. Patalpų sąrašą įveskite rankomis."
)
FORCE_VISION_ENV = "SAMATU_FORCE_VISION"
NO_VISION_ROUTE_ENV = "SAMATU_NO_VISION_ROUTE"
NO_VISION_NOTE = "be vaizdo skaitymo"
ROUTE_LABEL = "no_vision_vector"


def is_vector_pdf(pdf_bytes: bytes) -> tuple[bool, str]:
    """`(True, sentence)` when the PDF is vector enough to read without the Vision pass.

    Vector when at least one page has detectable wall-shaped vector fills (`pdf_vectors.wall_fills` — the
    geometry lane's own test for „can I trace walls here") AND the median text layer length across pages is at
    least `_PDF_NATIVE_MIN_MEDIAN_CHARS` (10 chars/page — a sheet with a text layer; the same gate the paid
    reading's native-PDF path uses). Fails open on any error: a predicate that cannot decide says „not vector"
    and leaves the Vision route in charge.
    """
    try:
        from .pdf_vectors import wall_fills
        from .pdf_page_cache import page_signals
    except Exception as exc:  # noqa: BLE001
        log.warning("is_vector_pdf: imports failed: %r", exc)
        return False, f"Brėžinio tipo nepavyko nustatyti ({type(exc).__name__})"
    try:
        sigs = page_signals(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("is_vector_pdf: page_signals failed: %r", exc)
        return False, "Brėžinio puslapių nepavyko perskaityti"
    if not sigs:
        return False, "Brėžinys be puslapių — negalime perskaityti"
    # Text layer gate: at least some sheets must carry readable text. A big TP ties interior sheets (text layer
    # in place) to many single-image diagrams (0 chars); the whole-document median goes to 0 on objektas_b
    # (65 sheets, text on ~20, blanks on ~45) even though every interior sheet has text and the paid reading
    # reads them. Rule: at least max(5, 20 %) of pages carry ≥ 10 chars (the native-PDF gate's own threshold).
    chars = [len(str(s.get("text") or "").strip()) for s in sigs]
    n_with_text = sum(1 for c in chars if c >= 10)
    threshold = max(5, int(0.20 * len(chars)))
    if n_with_text < min(threshold, len(chars)):
        return False, (f"Brėžinys be teksto sluoksnio ({n_with_text}/{len(chars)} psl. su tekstu) "
                       "— paliekamas vaizdo modelio skaitymui")
    # At least one page must show wall-shaped vector fills.
    for nr in range(1, len(sigs) + 1):
        try:
            if wall_fills(pdf_bytes, nr):
                return True, VECTOR_SENTENCE
        except Exception as exc:  # noqa: BLE001
            log.debug("is_vector_pdf: wall_fills failed on p%s: %r", nr, exc)
            continue
    return False, (
        f"Brėžinyje tekstas yra ({median_chars:.0f} ženklai/psl.), bet vektorinių sienų nerasta "
        "— paliekamas vaizdo modelio skaitymui")


def should_use_no_vision(pdf_bytes: bytes) -> tuple[bool, str]:
    """`(True, sentence)` when the no-vision route takes this PDF.

    OFF by default — `SAMATU_NO_VISION_ROUTE=1` must be set to enable it. When off, returns (False, sentence)
    without reading `pdf_bytes` at all. `SAMATU_FORCE_VISION=1` is a stronger off switch checked first, so the
    golden replay pin keeps working.
    """
    if os.environ.get(FORCE_VISION_ENV) == "1":
        return False, f"{FORCE_VISION_ENV}=1 — paliekamas vaizdo modelio skaitymui (palyginimui)"
    if os.environ.get(NO_VISION_ROUTE_ENV) != "1":
        return False, f"Vektorinis kelias išjungtas ({NO_VISION_ROUTE_ENV}≠1) — vaizdo modelio skaitymas"
    return is_vector_pdf(pdf_bytes)


# ── text-only eksplikacija fallback (schema_llm on the page's TEXT) ───────────

EKSPL_MARKERS = ("eksplikacij", "patalpų eksplikacija", "patalpu eksplikacija", "patalpų plotas")


def _candidate_eksplikacija_pages(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """`[(page_nr, text)]` of pages whose text layer carries an eksplikacija heading or markers. Deterministic;
    the model never sees the page — only the text layer, already extracted."""
    out: list[tuple[int, str]] = []
    try:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    txt = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    continue
                low = txt.lower()
                if any(m in low for m in EKSPL_MARKERS):
                    out.append((i, txt))
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: eksplikacija candidate scan failed: %r", exc)
    return out


def _eksplikacija_from_text_schema(pdf_bytes: bytes, client) -> dict | None:
    """When pdfplumber refused the room table (ambiguous columns, missing header), the eksplikacija page's
    TEXT is handed to text.schema_llm.structure (text in → JSON out, substring-guarded — a value whose
    source_text is not in the input is REFUSED). The model never sees the sheet. Returns the same shape
    pdfplumber returns, or None when no client / no candidate page / nothing kept.
    """
    if client is None:
        return None
    cands = _candidate_eksplikacija_pages(pdf_bytes)
    if not cands:
        return None
    try:
        from text.schema_llm import structure
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: text.schema_llm unavailable: %r", exc)
        return None
    best: dict | None = None
    MIN_ENOUGH = 5                                      # a page that produced this many rooms IS the table — stop here
    MAX_PAGES = 2                                       # at most this many model calls (one per page): the first page that reads is almost always the only one — a second page is a continuation; four pages before cost 100+ s on objektas_a with 11 rooms
    TOTALS = ("bendras", "iš viso", "is viso", "viso", "total", "patalpų plotas", "patalpu plotas")
    for page_nr, text in cands[:MAX_PAGES]:
        low = text.lower()
        start = min((low.find(m) for m in EKSPL_MARKERS if m in low), default=0)
        snippet = text[max(start - 40, 0): max(start - 40, 0) + 3500]
        if len(snippet) < 60:
            continue
        res = structure(
            snippet,
            fields={"nr": "text", "pavadinimas": "text", "plotas_m2": "number"},
            key="nr",
            instruction=(
                "Iš brėžinio TEKSTO ištrauk patalpų eksplikacijos lentelę: patalpos numeris, pavadinimas ir "
                "plotas m². source_text turi būti NUKOPIJUOTA ta pati teksto eilutė, kurioje reikšmė yra, "
                "raidė į raidę. „Bendrasis plotas“, „Iš viso“, „Viso“ eilučių NEIMK — tai sumos, ne patalpos."
            ),
            client=client,
        )
        if res.get("status") in ("no_client", "error"):
            continue
        rooms = []
        for it in (res.get("items") or []):
            nm = str(it.get("pavadinimas") or "").lower()
            if any(t in nm for t in TOTALS):
                continue
            try:
                area = float(it.get("plotas_m2"))
            except (TypeError, ValueError):
                area = None
            if area is None or area <= 0:
                continue
            rooms.append({
                "nr": str(it.get("nr") or "").strip(),
                "pavadinimas": str(it.get("pavadinimas") or "").strip(),
                "plotas_m2": area,
                "row_idx": None,
                "page": page_nr,
            })
        if not rooms:
            continue
        answer = {
            "patalpos": rooms,
            "schedule_tables": {"durys": [], "langai": []},
            "eksplikacija_source_page": page_nr,
            "_meta": {"source": "text_schema_llm", **(res.get("_meta") or {})},
        }
        if best is None or len(rooms) > len(best["patalpos"]):
            best = answer
        if len(rooms) >= MIN_ENOUGH:                    # a page with this many rooms IS the table — no need to compare
            break
    return best


# ── room list from the drawing's text table ───────────────────────────────────

def _rooms_from_table(eks: dict) -> list[dict]:
    """Each row of the pdfplumber room table becomes a room: nr, name, area, source, evidence stamps.
    `paskirtis` is inferred from the name (the extraction's own classifier, same as `_recompute_per_room_via_python`
    does for rooms the model left unclassified). An empty `elementai` list is enough — the geometry lane's
    `_angos_sienose` and `reconcile_openings_with_walls` fill in doors and windows from the walls.
    """
    from .universal_rules import classify_room_name
    out: list[dict] = []
    for row in eks.get("patalpos") or []:
        if not isinstance(row, dict):
            continue
        nr = str(row.get("nr") or "").strip()
        if not nr:
            continue
        name = str(row.get("pavadinimas") or "").strip()
        area = row.get("plotas_m2")
        room: dict = {
            "nr": nr,
            "pavadinimas": name,
            "plotas_m2": area,
            "plotas_saltinis": "eksplikacija",
            "elementai": [],
            # the drawing's text table named the room — not a model reading
            "_pavadinimas_saltinis": "lentele",
        }
        for key in ("_vienetas", "_nr_brezinyje"):
            if row.get(key) is not None:
                room[key] = row[key]
        # evidence stamps for the frontend (same keys _stamp_eksplikacija_evidence writes)
        if row.get("row_idx") is not None:
            room["eksplikacija_row_idx"] = row["row_idx"]
        for key in ("eksplikacija_row_bbox", "eksplikacija_page_width_pdf", "eksplikacija_page_height_pdf"):
            if row.get(key) is not None:
                room[key] = row[key]
        page = row.get("page") or eks.get("eksplikacija_source_page")
        if page:
            room["eksplikacija_source_page"] = page
            room["puslapio_nr"] = page         # the geometry lane re-places the room on its own sheet
        if row.get("perimetras_m"):
            room["perimetras_m"] = row["perimetras_m"]
            room["perimetras_saltinis"] = "eksplikacija"
        guessed = classify_room_name(name, None)
        if guessed:
            room["paskirtis"] = guessed
            room["_paskirtis_source"] = "inferred_from_name"
        out.append(room)
    return out


def _no_table_warning(sentence: str) -> dict:
    return {
        "level": "WARN",
        "code": "room_table_missing_no_vision",
        "message": sentence,
    }


def _ceiling_anchor_from_table(eks: dict) -> dict | None:
    """The eksplikacija's own `Iš viso` row, or the row sum (same logic as the Vision route uses when the
    guard accepts the table). On the no-vision route the table IS the room list, so the guard never fires."""
    rows = [r for r in (eks.get("patalpos") or []) if isinstance(r, dict)]
    if not rows:
        return None
    _meta = eks.get("_meta") or {}
    if _meta.get("total_area_m2"):
        return {
            "total_area_m2": _meta["total_area_m2"],
            "label": _meta.get("total_row_label") or "Iš viso",
            "page": _meta.get("total_row_page"),
        }
    rows_sum = round(sum(float(r.get("plotas_m2") or 0) for r in rows), 2)
    if rows_sum > 0:
        return {
            "total_area_m2": rows_sum,
            "label": "patalpų plotų suma",
            "page": _meta.get("source_page") or eks.get("eksplikacija_source_page"),
        }
    return None


# ── the pipeline ──────────────────────────────────────────────────────────────

def extract_interior_no_vision(
    pdf_bytes: bytes,
    rules_override: dict | None = None,
    progress_cb: Callable[[dict], None] | None = None,
    *,
    route_sentence: str | None = None,
) -> dict:
    """A vector PDF end-to-end without the Pass-1 Vision call.

    The flow:
      1. page_kinds from the sheets' text (text/page_kind.py) — the lanes pick sheets by them;
      2. the room TABLE from the text layer (pdfplumber_eksplikacija) IS the room list;
      3. drawing_lanes.run_drawing_lanes writes the outlines, perimeters, scales, openings, finishes, counts
         and heights the Vision route rebuilt afterwards;
      4. the wall finishes the finish-sheet TEXT states (apply_apdailos — the ONLY model call allowed on this
         route, through text/schema_llm.py with its substring guard);
      5. frameless / sliding door types from the drawing's text (apply_door_types);
      6. the drawing's door schedule and vector symbols (deterministic);
      7. plytelių specifikacija (text, deterministic);
      8. the per-room Python math (`_recompute_per_room_via_python`) and the sąmata rows (`_build_pozicijos_from_rooms`);
      9. the sanity checks the Vision route runs at the tail.

    Returns the same shape the Vision route returns, with `_meta.vision_pass = "none"` and
    `_meta.route = "no_vision_vector"`.
    """
    t0 = time.time()
    import anthropic

    # The client is held for the schema_llm text call inside apply_apdailos (text in → JSON out,
    # substring-guarded). No image is sent to the model from this route.
    try:
        client = anthropic.Anthropic(max_retries=1)
    except Exception as exc:  # noqa: BLE001 — missing API key or env → still try the lane; apdailos returns skipped
        log.warning("no_vision_route: anthropic client not available: %r", exc)
        client = None

    def _emit(ev: dict) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(ev)
        except Exception as exc:  # noqa: BLE001
            log.debug("no_vision_route: progress_cb raised: %r", exc)

    # Step 1 — page count and sheet kinds from text.
    _emit({"event": "rendering_pdf"})
    # Avoid a 300-DPI raster — we never send pages to the model. Count pages through pdfplumber (fast).
    try:
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as _pdf:
            n_pdf_pages = len(_pdf.pages)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: pdfplumber open failed: %r", exc)
        _emit({"event": "error", "message": f"Nepavyko atverti PDF: {type(exc).__name__}"})
        return {"status": "error", "_error": f"pdf_open_failed: {type(exc).__name__}"}

    sentence = route_sentence or VECTOR_SENTENCE
    _emit({"event": "route_selected", "route": ROUTE_LABEL, "sentence": sentence,
           "page_count": n_pdf_pages})

    parsed: dict = {
        "status": "ok",
        "patalpos": [],
        "puslapiai": [],
        "warnings": [],
        "pozicijos": [],
        "_meta": {
            "vision_pass": "none",
            "route": ROUTE_LABEL,
            "route_sakinys": sentence,
            "n_pdf_pages": n_pdf_pages,
        },
    }

    _emit({"event": "started", "page_count": n_pdf_pages, "voting": False, "route": ROUTE_LABEL})
    # Keep the pass1 event names the UI listens to — with `skipped` + a note. Metering: nothing is recorded here
    # (`run_usage` sees no vision call); only the schema_llm text call inside apply_apdailos tallies.
    _emit({"event": "pass1_started", "page_count": n_pdf_pages,
           "voting": False, "skipped": True, "note": NO_VISION_NOTE})

    # Timing probes — one row per step, written to _meta.sekundes for the runtime table.
    timings: dict[str, float] = {}

    def _tic():
        return time.time()

    def _toc(key: str, t: float) -> None:
        timings[key] = round(time.time() - t, 2)

    # Step 2 — the room table from the drawing's text layer.
    t_eks = _tic()
    _emit({"event": "eksplikacija_started"})
    try:
        from .pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
        eks = extract_eksplikacija_pdfplumber(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: pdfplumber eksplikacija failed: %r", exc)
        eks = {"patalpos": [], "schedule_tables": {"durys": [], "langai": []}, "_meta": {"source": "pdfplumber_table"}}

    # Fallback: when pdfplumber refuses the table (ambiguous columns, no header), hand the eksplikacija page's
    # TEXT to text.schema_llm — the ONE allowed model call, substring-guarded; no image is sent.
    if not (eks.get("patalpos") or []):
        try:
            alt = _eksplikacija_from_text_schema(pdf_bytes, client)
            if alt and alt.get("patalpos"):
                log.info("no_vision_route: eksplikacija from text.schema_llm (%s rooms, p%s)",
                         len(alt["patalpos"]), alt.get("eksplikacija_source_page"))
                # tally the schema_llm call so the per-user spend cap sees it
                try:
                    from . import run_usage as _run_usage
                    _run_usage.note((alt.get("_meta") or {}))
                except Exception as exc:  # noqa: BLE001
                    log.debug("no_vision_route: eksplikacija run_usage.note failed: %r", exc)
                # keep the pdfplumber _meta's diagnostic counts alongside, for the record
                prev_meta = eks.get("_meta") or {}
                eks = {**alt}
                eks["_meta"] = {**(alt.get("_meta") or {}), "pdfplumber_refused": {
                    k: prev_meta.get(k) for k in ("ambiguous_rows", "eksplikacija_pages_found",
                                                   "tables_examined", "wide_acceptance")}}
        except Exception as exc:  # noqa: BLE001 — the fallback must never sink the route
            log.warning("no_vision_route: text-schema eksplikacija fallback failed: %r", exc)

    rooms = _rooms_from_table(eks)
    _emit({
        "event": "eksplikacija_completed",
        "rooms_in_table": len(eks.get("patalpos", [])),
        "doors_in_table": len(eks.get("schedule_tables", {}).get("durys", [])),
        "windows_in_table": len(eks.get("schedule_tables", {}).get("langai", [])),
    })

    # The eksplikacija IS the room list on this route; the model's eksplikacija guard never runs
    # (no model rooms to compare), so the ceiling anchor is written straight from the table.
    if rooms:
        parsed["patalpos"] = rooms
        parsed["_eksplikacija"] = eks
        parsed["eksplikacija_source_page"] = eks.get("eksplikacija_source_page")
        parsed["bendras_plotas_m2"] = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
        parsed["_meta"]["kambariu_tapatybe"] = {
            "saltinis": "lentele", "lenteles_eilutes": len(rooms),
            "sutapo": len(rooms), "tik_lenteleje": 0, "atmesta": [],
            "perkeisti_numeriai": {},
        }
        parsed["_meta"]["eksplikacija_merged_rooms"] = len(rooms)
        parsed["_meta"]["eksplikacija_total_rows"] = len(rooms)
        anchor = _ceiling_anchor_from_table(eks)
        if anchor:
            parsed["_ceiling_anchor"] = anchor
    else:
        parsed["warnings"].append(_no_table_warning(MISSING_TABLE_SENTENCE))
        parsed["_meta"]["kambariu_tapatybe"] = {
            "saltinis": "nera_lenteles", "sakinys": MISSING_TABLE_SENTENCE,
        }

    _toc("eksplikacija", t_eks)
    _emit({"event": "eksplikacija_merged",
           "merged_rooms": len(rooms),
           "total_rows": len(eks.get("patalpos", []))})

    # Pass-1 completed — the room list is there (or blank with a reason).
    _emit({
        "event": "pass1_completed",
        "skipped": True, "note": NO_VISION_NOTE,
        "rooms_count": len(rooms),
        "patalpos": [
            {"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
             "paskirtis": r.get("paskirtis"), "plotas_m2": r.get("plotas_m2"),
             "puslapio_nr": r.get("puslapio_nr")}
            for r in rooms
        ],
    })

    # Step 3 — the drawing's €0 lanes (page kinds, text scan + anchors, dimension pairs, raster outlines,
    # heights, vector geometry, legend counts). ONE function, same as the paid reading calls (and the eval tail).
    from .drawing_lanes import run_drawing_lanes
    t_lanes = _tic()
    try:
        run_drawing_lanes(parsed, pdf_bytes, emit=_emit)
    except Exception as exc:  # noqa: BLE001 — a lane must never sink the extraction
        log.exception("no_vision_route: drawing lanes failed: %r", exc)
        parsed.setdefault("warnings", []).append({
            "level": "WARN",
            "message": ("Brėžinio skaitymo takeliai nenurodyti — kiekiai gali būti netikslūs. "
                        "Patikrinkite patalpas Patikros žingsnyje."),
        })

    # Zoom is skipped on this route — the UI listens to `zoom_started` and `zoom_completed`.
    _emit({"event": "zoom_started", "total": 0, "skipped": True, "note": NO_VISION_NOTE,
           "skipped_via_eksplikacija": 0})
    _emit({"event": "zoom_completed", "attempted": 0, "applied": 0,
           "skipped_via_eksplikacija": 0, "elapsed_s": 0.0, "skipped": True,
           "note": NO_VISION_NOTE})
    parsed["_meta"]["zoom_attempted"] = 0
    parsed["_meta"]["zoom_applied"] = 0
    parsed["_meta"]["zoom_elapsed_s"] = 0.0
    parsed["_meta"]["zoom_skipped_via_eksplikacija"] = 0

    _toc("lanes", t_lanes)

    # Step 4 — wall finishes from the finish sheets' TEXT (apply_apdailos: text layer / OCR, a model only on
    # the extracted text through text/schema_llm.py). The ONLY model call this route may make.
    t_ap = _tic()
    try:
        from .vision_call import apply_apdailos
        _emit({"event": "apdailos_started"})
        apdailos_result = apply_apdailos(parsed, pdf_bytes, client=client)
        # tally the schema_llm text call so the per-user spend cap sees it (same as the Vision route)
        try:
            from . import run_usage as _run_usage
            _run_usage.note(apdailos_result.get("_meta"))
        except Exception as exc:  # noqa: BLE001 — metering never breaks the run
            log.debug("no_vision_route: apdailos run_usage.note failed: %r", exc)
        _emit({
            "event": "apdailos_completed" if apdailos_result.get("status") == "ok" else "apdailos_skipped",
            "page": apdailos_result.get("page"), "status": apdailos_result.get("status"),
            "rooms_updated": (parsed.get("_meta") or {}).get("apdailos_rooms_updated"),
            "reason": apdailos_result.get("_error"),
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: apdailos failed: %r", exc)
        _emit({"event": "apdailos_error", "message": str(exc)})

    _toc("apdailos", t_ap)

    # Step 5 — door types from the drawing's TEXT (apply_door_types — no model).
    t_dt = _tic()
    try:
        from .vision_call import apply_door_types
        _emit({"event": "door_types_started"})
        dt = apply_door_types(parsed, pdf_bytes)
        if dt.get("status") == "ok":
            _dtt = parsed.get("_door_types") or {}
            _emit({"event": "door_types_completed", "frameless": _dtt.get("count"),
                   "confidence": _dtt.get("confidence"),
                   "reader": dt.get("beapvadines_count"), "tagged": 0})
        else:
            _emit({"event": "door_types_skipped", "reason": dt.get("_error")})
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: door types failed: %r", exc)
        _emit({"event": "door_types_error", "message": str(exc)})

    _toc("door_types", t_dt)

    # Step 6 — ceiling heights filled across rooms (same helper the Vision route and the free re-read use).
    t_h = _tic()
    try:
        from . import row_provenance as _rp
        n_h = _rp.fill_heights_from_read(parsed.get("patalpos") or [], parsed)
        if n_h:
            parsed.setdefault("_meta", {})["aukstis_is_brezinio"] = n_h
            _emit({"event": "heights_from_drawing", "rooms_changed": n_h})
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: height fill failed: %r", exc)

    _toc("heights", t_h)

    # Step 7 — tile size mentions on finish / elevation pages (deterministic, $0).
    t_scans = _tic()
    try:
        from .plyteliu_specifikacija import extract_plyteliu_specifikacija, RELEVANT_PAGE_TYPES
        relevant = [p["nr"] for p in (parsed.get("puslapiai") or [])
                    if isinstance(p, dict) and p.get("tipas") in RELEVANT_PAGE_TYPES]
        plyt = extract_plyteliu_specifikacija(pdf_bytes, relevant_pages=relevant or None)
        parsed["_plyteliu_specs"] = plyt.get("tile_specs", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: plyteliu_specifikacija failed: %r", exc)

    # Step 8 — symbol-LEGEND anchors, door schedule, vector symbols (deterministic, $0).
    try:
        from .symbol_legend import scan_symbol_legend
        parsed["_symbol_legend"] = scan_symbol_legend(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: symbol legend scan failed: %r", exc)
    try:
        from .door_schedule import scan_door_schedule
        parsed["_duru_ziniarastis"] = scan_door_schedule(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: door schedule scan failed: %r", exc)
    try:
        from .vector_symbols import scan_vector_symbols
        parsed["_vector_symbols"] = scan_vector_symbols(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: vector symbol scan failed: %r", exc)
    _toc("skenavimai", t_scans)

    # Step 9 — the per-room Python math and the sąmata rows (same functions the Vision route runs). This is
    # where `calc_room_quantities` reads every field the earlier steps wrote.
    _emit({"event": "post_processing"})
    t_math = _tic()
    try:
        from .vision_call import _recompute_per_room_via_python, _build_pozicijos_from_rooms, _recompute_santrauka, _emit_v8_compat_fields
    except Exception as exc:  # noqa: BLE001
        log.exception("no_vision_route: vision_call helpers import failed: %r", exc)
        return {"status": "error", "_error": f"recompute import failed: {exc}"}

    try:
        parsed = _recompute_per_room_via_python(parsed, rules_override)
        _emit({"event": "python_math_completed", "rooms_computed": len(parsed.get("patalpos") or [])})
    except Exception as exc:  # noqa: BLE001
        log.exception("no_vision_route: per-room recompute failed: %r", exc)
        parsed.setdefault("warnings", []).append({
            "level": "WARN",
            "message": ("Patalpų kiekių apskaičiuoti nepavyko — kiekiai gali būti neišsamūs. "
                        "Patikrinkite patalpų kiekius Patikros žingsnyje."),
        })

    # Scope and families: the apimtis picked at upload decides which rows are built; `_scope.mark_rooms` tags
    # every room's scope keys the same way the Vision route does.
    try:
        from . import scope as _scope
        if rules_override is not None:
            parsed["_overrides"] = rules_override
        _apimtis = _scope.normalize_apimtis(_scope.with_profile_defaults(
            (rules_override or {}).get("apimtis"), rules_override))
        _scope.mark_rooms(parsed.get("patalpos") or [], _apimtis)
        if _apimtis:
            parsed["_apimtis"] = _apimtis
            _scope.apply_ceiling_choice(parsed.get("patalpos") or [], _apimtis)
        parsed = _build_pozicijos_from_rooms(parsed)
        if _apimtis:
            parsed["pozicijos"] = _scope.filter_rows_by_families(parsed.get("pozicijos"), _apimtis)
    except Exception as exc:  # noqa: BLE001
        log.exception("no_vision_route: pozicijos build failed: %r", exc)
        parsed["pozicijos"] = []
        parsed.setdefault("warnings", []).append({
            "level": "ERROR", "source": "pozicijos_build_failure",
            "message": ("Sąmatos eilučių sudaryti nepavyko — sąmata tuščia. "
                        "Eilutes įrašykite rankomis sąmatoje arba brėžinį "
                        "perskaitykite iš naujo per mygtuką „Nustatymai“."),
        })

    try:
        parsed = _recompute_santrauka(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: santrauka recompute failed: %r", exc)

    # Step 10 — the sanity checks the Vision route runs at the tail.
    try:
        from .lt_rules import apply_lt_sanity
        parsed = apply_lt_sanity(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: lt_sanity failed: %r", exc)
    try:
        from .cross_page_validator import as_pipeline_warnings, validate_consistency
        cross = validate_consistency(parsed)
        if cross:
            parsed.setdefault("warnings", []).extend(as_pipeline_warnings(cross))
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: cross_page_validator failed: %r", exc)
    try:
        from .sanity_checks import run_all_checks
        sw = run_all_checks(parsed)
        if sw:
            parsed.setdefault("warnings", []).extend(sw)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: sanity_checks failed: %r", exc)
    try:
        from .consistency_checker import run_all_checks as _ck_run
        parsed["_consistency_checks"] = _ck_run(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: consistency_checker failed: %r", exc)
    try:
        from .sanity_mirror import build_lt_sanity
        parsed["lt_sanity"] = build_lt_sanity(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: lt_sanity mirror failed: %r", exc)
    try:
        parsed = _emit_v8_compat_fields(parsed)
    except Exception as exc:  # noqa: BLE001
        log.warning("no_vision_route: v8 compat emit failed: %r", exc)

    if rules_override is not None:
        parsed["_overrides"] = rules_override

    _toc("math_sanity", t_math)

    # Step 11 — finalize.
    elapsed = round(time.time() - t0, 1)
    parsed.setdefault("_meta", {})["elapsed_s"] = elapsed
    parsed["_meta"]["vision_pass"] = "none"
    parsed["_meta"]["route"] = ROUTE_LABEL
    parsed["_meta"]["route_sakinys"] = sentence
    parsed["_meta"]["no_vision_sekundes"] = timings
    parsed["_elapsed_s"] = elapsed
    parsed["status"] = "ok"
    return parsed

"""POST /api/projects/{project_id}/legend/rows  — a legend box (or the sheet's legend zones) → its rows
POST /api/projects/{project_id}/legend/count — legend rows → how many of each symbol the drawing carries

Pathon v3, track B (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §4; waves 2–4 plan, track W2-A, A4).
„Pažymėti legendą": the person accepts the suggested legend (W1-E's `legenda` zone) or draws a box; the rows
come back with their glyph and text (extractor/legend_rows.py); for the rows the person keeps, the count
answers per sheet with every instance's box, a proposal the person reviews before anything exists (W2-B).

Who counts what: a coloured glyph is counted from the drawing's own paths (vector_symbols
`count_glyph_instances_many`, saltinis „vektoriai"); a black one — or a coloured one the paths do not carry —
by its shape on the rendered sheets (cv_match `batch_find_symbol`, „rastras", each instance with its score);
a glyph that is a character of the text layer by that character standing alone (`tekstas`). One rule for
all three: the sheets that carry the row's own legend text are counted, a sheet that repeats an earlier
sheet's plan is counted once, nothing inside a legend, a table or the title block; instances on sheets
without the legend are listed (`kiti`), not counted — unless the legend stands on a sheet of its own.

Both routes are read-only and €0 (no model call): NOTHING is saved here — the legend is stored by
api/legends.py when the UI commits it. Owner-scoped (the owner check before anything about the request),
rate-limited like the other PDF handlers, explicit Lithuanian errors. A sheet without a text layer answers
`status: "be_teksto"`, never a guess.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.legend_count")

router = APIRouter(prefix="/api/projects", tags=["legend-count"])

NO_PAGE = "Tokio lapo brėžinyje nėra"
MAX_ROWS = 40
ROUTE_BUDGET_S = 60.0          # the whole count; the vector pass gets at most VECTOR_BUDGET_S of it
VECTOR_BUDGET_S = 25.0
GLYPH_PAD_PT = 1.0             # the shape search's template: the glyph and a point of paper round it
SALTINIAI = ("vektoriai", "rastras", "tekstas")


class RowsBody(BaseModel):
    page: int = 1
    bbox_pct: list[float] | None = None


class CountBody(BaseModel):
    rows: list[dict] = []
    row_ids: list[str] = []
    pages: list[int] | None = None
    min_score: float = 0.70
    other_sheets: bool = False


# ── helpers ─────────────────────────────────────────────────────────────────


def _pdf(project_id: str) -> bytes:
    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("legend pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    return pdf_bytes


def _box(v, what: str) -> list[float]:
    try:
        b = [float(x) for x in v]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{what} turi būti keturi skaičiai nuo 0 iki 1")
    if len(b) != 4 or not all(0.0 <= x <= 1.0 for x in b) or not (b[2] > b[0] and b[3] > b[1]):
        raise HTTPException(status_code=400, detail=f"{what} turi būti [x0, y0, x1, y1] nuo 0 iki 1, x1 > x0, y1 > y0")
    return b


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _with_crops(project_id: str, rows: list[dict], legend_box) -> list[dict]:
    from api.evidence import evidence_url
    out = []
    for r in rows:
        r = dict(r)
        r["legend_bbox_pct"] = list(legend_box) if legend_box else None
        r["glyph_crop_url"] = evidence_url(project_id, r["page"], r["glyph_bbox_pct"])
        r["crop_url"] = evidence_url(project_id, r["page"], _union(r["glyph_bbox_pct"], r["text_bbox_pct"]))
        out.append(r)
    return out


# ── POST …/legend/rows ──────────────────────────────────────────────────────


# Plain `def`: PDFium and pdfplumber parsing, blocking CPU — FastAPI runs it in the threadpool.
@router.post("/{project_id}/legend/rows")
def api_legend_rows(request: Request, project_id: str, body: RowsBody):
    project = _project_for(request, project_id)            # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "legend_rows")
    page = int(body.page)
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    bbox = _box(body.bbox_pct, "Legendos rėmelis") if body.bbox_pct is not None else None
    pdf_bytes = _pdf(project_id)

    from extractor.legend_rows import split_legend_rows, suggest_legend_rows
    from extractor.sheet_zones import display_frame
    if display_frame(pdf_bytes, page) is None:
        raise HTTPException(status_code=400, detail=NO_PAGE)
    if bbox is not None:
        res = split_legend_rows(pdf_bytes, page, bbox)
        legends = [{**res, "zone": None}]
        source, status, detail = "remelis", res["status"], res["detail"]
    else:
        meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
        stored = (meta.get("zonos") or {}).get(str(page)) if isinstance(meta.get("zonos"), dict) else None
        sug = suggest_legend_rows(pdf_bytes, page, stored if isinstance(stored, list) else None)
        legends = sug["legends"]
        source, status, detail = "zona", sug["status"], sug["detail"]
    for leg in legends:
        leg["rows"] = _with_crops(project_id, leg.get("rows") or [], leg.get("bbox_pct"))
    return {"page": page, "status": status, "detail": detail, "source": source, "legends": legends,
            "rows": [r for leg in legends for r in leg["rows"]]}


# ── POST …/legend/count ─────────────────────────────────────────────────────


def _row_in(r: dict) -> dict:
    """A row (or a template the person boxed) as the counters take it — validated."""
    if not isinstance(r, dict):
        raise HTTPException(status_code=400, detail="Legendos eilutė turi būti objektas")
    try:
        page = int(r.get("page"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Legendos eilutei trūksta lapo numerio")
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    kind = r.get("glyph_kind")
    if kind is not None and kind not in ("spalvotas", "juodas", "tekstas"):
        raise HTTPException(status_code=400, detail="Nežinoma ženklo rūšis")
    out = {"row_id": str(r.get("row_id") or ""), "page": page, "glyph_kind": kind,
           "glyph_bbox_pct": _box(r.get("glyph_bbox_pct"), "Ženklo rėmelis"),
           "text": str(r.get("text") or "")[:200], "glyph_text": r.get("glyph_text"),
           "countable": r.get("countable") is not False,
           "legend_bbox_pct": _box(r["legend_bbox_pct"], "Legendos rėmelis") if r.get("legend_bbox_pct") else None}
    if kind == "tekstas" and not (isinstance(out["glyph_text"], str) and out["glyph_text"].strip()):
        raise HTTPException(status_code=400, detail="Teksto ženklui trūksta paties ženklo")
    return out


def _mediabox_box(pdf_bytes: bytes, row: dict, geo) -> list[float]:
    from extractor.sheet_zones import zone_to_mediabox_pt
    w, h, rot = geo[row["page"] - 1]
    b = zone_to_mediabox_pt({"bbox_pct": row["glyph_bbox_pct"]}, (w, h), rot)
    return [max(0.0, b[0] - GLYPH_PAD_PT), max(0.0, b[1] - GLYPH_PAD_PT), min(w, b[2] + GLYPH_PAD_PT), min(h, b[3] + GLYPH_PAD_PT)]


def _sheet_rules(pdf_bytes: bytes, row: dict, per_page: dict[int, list[dict]]) -> dict:
    """The rules the vector counter applies, for the shape and text counts: the sheets carrying the row's
    legend text count; a repeat counts once; other sheets are listed — or counted when no legend sheet has one."""
    import hashlib

    from extractor.vector_symbols import _folded_texts, _repeats_earlier, _row_key
    digest = hashlib.blake2b(pdf_bytes, digest_size=16).digest()
    key = _row_key(row.get("text"))
    texts = _folded_texts(pdf_bytes, digest, sorted(per_page)) if key else {}
    on_legend = {p: (key is None or key in texts.get(p, "")) for p in per_page}
    order = sorted(per_page, key=lambda p: (p != row["page"], p))
    counted: list[dict] = []
    pages_out: list[dict] = []
    others: list[tuple[int, list[dict]]] = []
    for p in order:
        found = per_page[p]
        if not found:
            continue
        if on_legend[p]:
            rep = _repeats_earlier(found, counted)
            pages_out.append({"page": p, "count": len(found), "kartojasi": rep, "legenda_lape": True})
            if not rep:
                counted.extend(found)
        else:
            others.append((p, found))
    fallback = not counted and bool(others)
    kiti: list[dict] = []
    for p, found in others:
        rep = _repeats_earlier(found, counted) if fallback else False
        pages_out.append({"page": p, "count": len(found), "kartojasi": rep, "legenda_lape": False})
        if fallback and not rep:
            counted.extend(found)
        elif not fallback:
            kiti.extend(found)
    return {"instances": counted, "kiti": kiti, "per_page": sorted(pages_out, key=lambda r: r["page"]),
            "fallback": fallback}


def _pages_for(pdf_bytes: bytes, row: dict, wanted: list[int], other_sheets: bool) -> tuple[list[int], list[int]]:
    """(sheets to search first, sheets left for later) for the shape / text counts: the row's legend sheets
    first — a heavy sheet costs seconds to search."""
    import hashlib

    from extractor.vector_symbols import _folded_texts, _row_key
    key = _row_key(row.get("text"))
    if key is None or other_sheets:
        first = wanted
    else:
        texts = _folded_texts(pdf_bytes, hashlib.blake2b(pdf_bytes, digest_size=16).digest(), wanted)
        first = [p for p in wanted if key in texts.get(p, "")]
    first = sorted(first, key=lambda p: (p != row["page"], p))
    return first, [p for p in wanted if p not in first]


def _raster_count(pdf_bytes: bytes, row: dict, geo, wanted: list[int], min_score: float, other_sheets: bool,
                  budget: float) -> dict:
    from extractor.cv_match import batch_find_symbol
    box = _mediabox_box(pdf_bytes, row, geo)
    exclude = {row["page"]: [row["legend_bbox_pct"]]} if row.get("legend_bbox_pct") else None
    first, rest = _pages_for(pdf_bytes, row, wanted, other_sheets)
    if not first:                          # no sheet carries the row's text: search them all (pages=[] would too)
        first, rest = rest, []
    started = time.monotonic()
    res = batch_find_symbol(pdf_bytes, row["page"], box, first, min_score, exclude=exclude, time_budget_s=budget)
    if res["status"] != "ok":
        return {"status": res["status"], "detail": res["detail"], "res": res}
    found = {e["page"]: [c for c in e["candidates"] if not c["is_source"]] for e in res["pages"]}
    if rest and not any(found.values()):
        more = batch_find_symbol(pdf_bytes, row["page"], box, rest, min_score, exclude=exclude,
                                 time_budget_s=max(0.0, budget - (time.monotonic() - started)))
        if more["status"] == "ok":
            res["pages"] += more["pages"]
            res["partial"] = res["partial"] or more["partial"]
            res["pages_not_read"] = sorted(set(res["pages_not_read"]) | set(more["pages_not_read"]))
            for e in more["pages"]:
                found[e["page"]] = [c for c in e["candidates"] if not c["is_source"]]
    per_page = {p: [{"page": p, "box_pct": c["box_pct"], "x_pct": round((c["box_pct"][0] + c["box_pct"][2]) / 2, 4),
                     "y_pct": round((c["box_pct"][1] + c["box_pct"][3]) / 2, 4), "score": c["score"]}
                    for c in cs] for p, cs in found.items()}
    ruled = _sheet_rules(pdf_bytes, row, per_page)
    return {"status": "ok", "detail": res["detail"], "res": res, **ruled,
            "raster_pages": [e["page"] for e in res["pages"] if e["skipped"] == "raster"]}


def _text_hits(pdf_bytes: bytes, glyph: str, pages: list[int]) -> dict[int, list[dict]]:
    """Where the character `glyph` stands as a word of its own on each page — DISPLAY-frame boxes. PDFium's
    text search under PDFIUM_LOCK."""
    from extractor.pdf_vectors import _to_display
    from extractor.pdfium_guard import PDFIUM_LOCK
    import pypdfium2 as pdfium
    out: dict[int, list[dict]] = {}
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for p in pages:
                page = doc[p - 1]
                try:
                    W, H = (float(v) for v in page.get_size())
                    k = (int(page.get_rotation() or 0) // 90) % 4
                    Wu, Hu = (H, W) if k in (1, 3) else (W, H)
                    tp = page.get_textpage()
                    hits = []
                    try:
                        searcher = tp.search(glyph, match_case=True, match_whole_word=True)
                        try:
                            while True:
                                occ = searcher.get_next()
                                if not occ:
                                    break
                                idx, n = occ
                                boxes = [tp.get_charbox(i) for i in range(idx, idx + n)]
                                left = min(b[0] for b in boxes)
                                bottom = min(b[1] for b in boxes)
                                right = max(b[2] for b in boxes)
                                top = max(b[3] for b in boxes)
                                pts = [_to_display(x, y, Wu, Hu, k) for x, y in ((left, bottom), (right, top))]
                                x0, x1 = sorted((pts[0][0], pts[1][0]))
                                y0, y1 = sorted((pts[0][1], pts[1][1]))
                                hits.append({"page": p, "box_pct": [round(x0 / W, 5), round(y0 / H, 5), round(x1 / W, 5), round(y1 / H, 5)],
                                             "x_pct": round((x0 + x1) / 2 / W, 4), "y_pct": round((y0 + y1) / 2 / H, 4)})
                        finally:
                            searcher.close()
                    finally:
                        tp.close()
                    out[p] = hits
                finally:
                    page.close()
        finally:
            doc.close()
    return out


def _text_count(pdf_bytes: bytes, row: dict, wanted: list[int], other_sheets: bool) -> dict:
    from extractor.sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at
    from extractor.vector_symbols import ZONE_KINDS_WITHOUT_MARKS
    first, rest = _pages_for(pdf_bytes, row, wanted, other_sheets)
    hits = _text_hits(pdf_bytes, row["glyph_text"].strip(), first + rest)
    per_page: dict[int, list[dict]] = {}
    for p, hs in hits.items():
        zones = read_zones(pdf_bytes, p, table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
        keep = []
        for h in hs:
            if p == row["page"] and row.get("legend_bbox_pct"):
                b = row["legend_bbox_pct"]
                if b[0] <= h["x_pct"] <= b[2] and b[1] <= h["y_pct"] <= b[3]:
                    continue
            z = zone_at(zones, h["x_pct"], h["y_pct"])
            if z is not None and z.get("kind") in ZONE_KINDS_WITHOUT_MARKS:
                continue
            keep.append(h)
        per_page[p] = keep
    return {"status": "ok", "detail": None, **_sheet_rules(pdf_bytes, row, per_page)}


def _pages_word(pages: list[int]) -> str:
    return ("lape " if len(pages) == 1 else "lapuose ") + ", ".join(str(p) for p in pages)


def sentence_lt(row: dict, ans: dict) -> str:
    """What the person reads beside a row's count: what was counted, where, and what to check."""
    name = (row.get("text") or "be pavadinimo")[:60]
    if not row.get("countable", True):
        from extractor.legend_rows import SAMPLE_LT
        return SAMPLE_LT
    if ans["status"] == "be_teksto":
        return ans.get("detail") or "Šis ženklas automatiškai nesuskaičiuotas — pažymėkite jį rankiniu būdu."
    if ans["status"] not in ("ok",):
        return f"Ženklo „{name}“ suskaičiuoti nepavyko: {ans.get('detail') or 'patikrinkite rėmelį'}. Pažymėkite ženklus rankiniu būdu."
    counted = [p for p in ans["per_page"] if not p["kartojasi"] and p["page"] in {i["page"] for i in ans["instances"]}]
    parts = [f"{len([i for i in ans['instances'] if i['page'] == p['page']])} — lapas {p['page']}" for p in counted]
    how = {"vektoriai": "pagal ženklo spalvą ir formą brėžinyje",
           "rastras": "pagal ženklo formą — peržiūrėkite kiekvieną vietą, forma gali sutapti ir su kitu ženklu",
           "tekstas": f"pagal ženklą „{(row.get('glyph_text') or '').strip()}“ tekste"}.get(ans.get("saltinis"), "")
    if ans["count"]:
        s = f"„{name}“: rasta {ans['count']} vnt. ({'; '.join(parts)}) {how}."
    else:
        s = f"„{name}“: brėžinyje šio ženklo neradau ({how}). Jei ženklų yra, pažymėkite juos rankiniu būdu."
    repeated = sorted({p["page"] for p in ans["per_page"] if p["kartojasi"]})
    if repeated:
        s += f" {_pages_word(repeated).capitalize()} kartojamas tas pats planas — antrą kartą neskaičiuota."
    if ans.get("fallback"):
        s += " Legenda stovi kitame lape nei ženklai — suskaičiuota visuose lapuose."
    kiti = sorted({i["page"] for i in ans.get("kiti") or []})
    if kiti:
        s += f" Panašių ženklų yra ir {_pages_word(kiti)} be šios legendos — jie neįskaičiuoti; patikrinkite, ar tai tas pats ženklas."
    if ans.get("raster_pages"):
        s += f" {_pages_word(ans['raster_pages']).capitalize()} piešinys rastrinis — ten neieškota."
    if ans.get("partial"):
        s += " Ne visi lapai peržiūrėti per skirtą laiką — suskaičiuota tik dalis; paleiskite skaičiavimą dar kartą."
    return s


@router.post("/{project_id}/legend/count")
def api_legend_count(request: Request, project_id: str, body: CountBody):
    _project_for(request, project_id)                      # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "legend_count")
    started = time.monotonic()
    rows_in = list(body.rows or [])
    if body.row_ids:
        from api.legends import load_project_legend
        saved = {str(r.get("row_id")): r for r in (load_project_legend(project_id).get("rows") or []) if isinstance(r, dict)}
        for rid in body.row_ids:
            if str(rid) not in saved:
                raise HTTPException(status_code=404, detail="Tokios legendos eilutės šiame projekte nėra")
            rows_in.append(saved[str(rid)])
    if not rows_in:
        raise HTTPException(status_code=400, detail="Nurodykite bent vieną legendos eilutę")
    if len(rows_in) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"Vienu kartu galima skaičiuoti iki {MAX_ROWS} eilučių")
    if not (0.3 <= float(body.min_score) <= 1.0):
        raise HTTPException(status_code=400, detail="Panašumo riba turi būti nuo 0,3 iki 1")
    rows = [_row_in(r) for r in rows_in]
    for k, r in enumerate(rows):
        r["row_id"] = r["row_id"] or f"sablonas-{k + 1}"
    pdf_bytes = _pdf(project_id)

    from extractor.cv_match import _mediabox_geometry
    from extractor.vector_symbols import count_glyph_instances_many
    try:
        geo = _mediabox_geometry(pdf_bytes)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Brėžinio atidaryti nepavyko")
    n = len(geo)
    if any(r["page"] > n for r in rows):
        raise HTTPException(status_code=400, detail=NO_PAGE)
    wanted = sorted({int(p) for p in (body.pages or range(1, n + 1)) if 1 <= int(p) <= n})
    if not wanted:
        raise HTTPException(status_code=400, detail="Nurodyti lapai brėžinyje neegzistuoja")

    answers: dict[int, dict] = {}
    vector_rows = [k for k, r in enumerate(rows) if r["countable"] and r["glyph_kind"] in (None, "spalvotas")]
    if vector_rows:
        res = count_glyph_instances_many(pdf_bytes, [rows[k] for k in vector_rows], wanted,
                                         other_sheets=bool(body.other_sheets), time_budget_s=VECTOR_BUDGET_S)
        for k, a in zip(vector_rows, res):
            if a["status"] == "ok":
                answers[k] = {**a, "saltinis": "vektoriai",
                              "instances": [{**i, "score": None, "saltinis": "vektoriai"} for i in a["instances"]],
                              "kiti": [{**i, "score": None, "saltinis": "vektoriai"} for i in a["kiti"]]}
    for k, r in enumerate(rows):
        if k in answers:
            continue
        base = {"row_id": r["row_id"], "status": "ok", "count": 0, "per_page": [], "instances": [], "kiti": [],
                "partial": False, "pages_not_read": [], "saltinis": None, "detail": None, "score_floor": None}
        if not r["countable"]:
            answers[k] = {**base, "status": "neskaiciuojama", "detail": "medžiagos ar linijos pavyzdys"}
            continue
        remaining = max(0.0, ROUTE_BUDGET_S - (time.monotonic() - started))
        if r["glyph_kind"] == "tekstas":
            got = _text_count(pdf_bytes, r, wanted, bool(body.other_sheets))
            answers[k] = {**base, **got, "saltinis": "tekstas",
                          "instances": [{**i, "score": None, "saltinis": "tekstas"} for i in got["instances"]],
                          "kiti": [{**i, "score": None, "saltinis": "tekstas"} for i in got["kiti"]]}
            answers[k]["count"] = len(answers[k]["instances"])
            continue
        if remaining <= 0:
            answers[k] = {**base, "partial": True, "pages_not_read": wanted, "saltinis": "rastras"}
            continue
        got = _raster_count(pdf_bytes, r, geo, wanted, float(body.min_score), bool(body.other_sheets), remaining)
        if got["status"] != "ok":
            answers[k] = {**base, "status": got["status"], "detail": got["detail"], "saltinis": "rastras"}
            continue
        res = got["res"]
        answers[k] = {**base, "saltinis": "rastras", "per_page": got["per_page"], "fallback": got["fallback"],
                      "instances": [{**i, "saltinis": "rastras"} for i in got["instances"]],
                      "kiti": [{**i, "saltinis": "rastras"} for i in got["kiti"]],
                      "count": len(got["instances"]), "partial": res["partial"], "pages_not_read": res["pages_not_read"],
                      "score_floor": res["score_floor"], "raster_pages": got["raster_pages"], "detail": res["detail"]}
    out_rows = []
    for k, r in enumerate(rows):
        a = answers[k]
        out_rows.append({
            "row_id": r["row_id"], "page": r["page"], "text": r["text"], "glyph_kind": r["glyph_kind"],
            "status": a["status"], "saltinis": a.get("saltinis"), "count": a["count"],
            "per_page": a.get("per_page") or [],
            "instances": [{"page": i["page"], "box_pct": i["box_pct"], "score": i.get("score"), "saltinis": i["saltinis"]}
                          for i in a.get("instances") or []],
            "kiti": [{"page": i["page"], "box_pct": i["box_pct"], "score": i.get("score"), "saltinis": i["saltinis"]}
                     for i in a.get("kiti") or []],
            "partial": bool(a.get("partial")), "pages_not_read": a.get("pages_not_read") or [],
            "score_floor": a.get("score_floor"),
            "sentence_lt": sentence_lt(r, a),
        })
    return {"rows": out_rows, "pages": wanted, "partial": any(r["partial"] for r in out_rows),
            "elapsed_s": round(time.monotonic() - started, 2)}

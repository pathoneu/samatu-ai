"""Legend counts — how many of each legend row's symbol the drawing carries, counted from the drawing itself.
€0, no model call. The count core of the „Pažymėti legendą" route (api/legend_count.py, Pathon v3 W2-A A4) moved
here statement for statement so the reading can run it too (v4 Phase 3c-2, 2026-10-25):

  · a coloured glyph — the drawing's own paths (vector_symbols `count_glyph_instances_many`, saltinis „vektoriai");
  · a black glyph that is a ring with arms — the paths again (`ring_arm_*`, „vektoriai");
  · any other black glyph — its shape on the rendered sheet (cv_match `batch_find_symbol`, „rastras"): every
    instance carries its score and the row its own threshold (`score_floor` = the best twin's score less the
    margin, never under `min_score`), so a row whose shape is common gets a stricter floor than a rare one;
  · a glyph that is a character of the text layer — that character standing alone („tekstas").

One rule for all: the sheets that carry the row's legend text are counted, a sheet that repeats an earlier sheet's
plan once, nothing inside a legend, a table or the title block; instances on sheets without the legend are listed
(`kiti`), not counted — unless the legend stands on a sheet of its own.

`auto_legend_counts(pdf_bytes)` (the reading's step): every sheet whose zones hold a legend → its rows
(legend_rows.suggest_legend_rows) → the rows whose text names a thing the sąmata counts (`family_of`) → counted
here. The answer is a PROPOSAL (`parsed["_meta"]["legendos_siulymai"]`): the rows show it with the sheet and the legend row
it came from and ask him to confirm it with the count tool, whose confirmed counts (`_legendos_kiekiai`, written by
the frontend) always win. A sheet without a legend gives no count — the rows stay blank and say so. Stored as `_meta.legendos_siulymai`.

Never raises.
"""
from __future__ import annotations

import logging
import re
import time
import unicodedata

log = logging.getLogger("samatu.legend_counts")

ROUTE_BUDGET_S = 60.0          # the whole count; the vector pass gets at most VECTOR_BUDGET_S of it
VECTOR_BUDGET_S = 25.0
GLYPH_PAD_PT = 1.0             # the shape search's template: the glyph and a point of paper round it
SALTINIAI = ("vektoriai", "rastras", "tekstas")


def _mediabox_box(pdf_bytes: bytes, row: dict, geo) -> list[float]:
    from .sheet_zones import zone_to_mediabox_pt
    w, h, rot = geo[row["page"] - 1]
    b = zone_to_mediabox_pt({"bbox_pct": row["glyph_bbox_pct"]}, (w, h), rot)
    return [max(0.0, b[0] - GLYPH_PAD_PT), max(0.0, b[1] - GLYPH_PAD_PT), min(w, b[2] + GLYPH_PAD_PT), min(h, b[3] + GLYPH_PAD_PT)]


def _sheet_rules(pdf_bytes: bytes, row: dict, per_page: dict[int, list[dict]]) -> dict:
    """The rules the vector counter applies, for the shape and text counts: the sheets carrying the row's
    legend text count; a repeat counts once; other sheets are listed — or counted when no legend sheet has one."""
    import hashlib

    from .vector_symbols import _folded_texts, _repeats_earlier, _row_key
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


def _one_symbol_one_row(answers: dict[int, dict]) -> None:
    """A shape-search hit claimed by two rows of one count is ONE symbol: it stays with the row whose template
    it resembles most and leaves the others (Pathon v3 W5-D, D2 follow-up). objektas_h p3: the four switch rows
    („Viengubas / Dvigubas jungiklis / perjungėjas") all found the same marks at 0,92–0,94 — 107 proposals
    for one sheet. Only `rastras` instances move; the counts, pages and statuses follow."""
    hits = [(k, i, inst) for k, a in answers.items() if a.get("saltinis") == "rastras"
            for i, inst in enumerate(a.get("instances") or [])]
    if len({k for k, _, _ in hits}) < 2:
        return
    drop: set[tuple[int, int]] = set()
    for k, i, inst in hits:
        b = inst["box_pct"]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for k2, i2, other in hits:
            if k2 == k or other["page"] != inst["page"]:
                continue
            ob = other["box_pct"]
            if not (ob[0] <= cx <= ob[2] and ob[1] <= cy <= ob[3]):
                continue
            mine, theirs = float(inst.get("score") or 0.0), float(other.get("score") or 0.0)
            if theirs > mine or (theirs == mine and k2 < k):
                drop.add((k, i))
                break
    if not drop:
        return
    for k, a in answers.items():
        if a.get("saltinis") != "rastras":
            continue
        kept = [inst for i, inst in enumerate(a.get("instances") or []) if (k, i) not in drop]
        if len(kept) == len(a.get("instances") or []):
            continue
        a["instances"] = kept
        a["count"] = len(kept)
        per: dict[int, int] = {}
        for inst in kept:
            per[inst["page"]] = per.get(inst["page"], 0) + 1
        a["per_page"] = [{**pp, "count": per.get(pp["page"], 0)} for pp in a.get("per_page") or []
                         if not pp.get("legenda_lape") or per.get(pp["page"], 0) > 0 or pp.get("kartojasi")]


def _pages_for(pdf_bytes: bytes, row: dict, wanted: list[int], other_sheets: bool) -> tuple[list[int], list[int]]:
    """(sheets to search first, sheets left for later) for the shape / text counts: the row's legend sheets
    first — a heavy sheet costs seconds to search."""
    import hashlib

    from .vector_symbols import _folded_texts, _row_key
    key = _row_key(row.get("text"))
    if key is None or other_sheets:
        first = wanted
    else:
        texts = _folded_texts(pdf_bytes, hashlib.blake2b(pdf_bytes, digest_size=16).digest(), wanted)
        first = [p for p in wanted if key in texts.get(p, "")]
    first = sorted(first, key=lambda p: (p != row["page"], p))
    return first, [p for p in wanted if p not in first]


def _raster_count(pdf_bytes: bytes, row: dict, geo, wanted: list[int], min_score: float, other_sheets: bool,
                  budget: float, margin: float | None = None) -> dict:
    from .cv_match import BATCH_MARGIN, batch_find_symbol
    margin = BATCH_MARGIN if margin is None else float(margin)
    box = _mediabox_box(pdf_bytes, row, geo)
    exclude = {row["page"]: [row["legend_bbox_pct"]]} if row.get("legend_bbox_pct") else None
    first, rest = _pages_for(pdf_bytes, row, wanted, other_sheets)
    if not first:                          # no sheet carries the row's text: search them all (pages=[] would too)
        first, rest = rest, []
    started = time.monotonic()
    res = batch_find_symbol(pdf_bytes, row["page"], box, first, min_score, margin=margin, exclude=exclude,
                            time_budget_s=budget)
    if res["status"] != "ok":
        return {"status": res["status"], "detail": res["detail"], "res": res}
    found = {e["page"]: [c for c in e["candidates"] if not c["is_source"]] for e in res["pages"]}
    if rest and not any(found.values()):
        more = batch_find_symbol(pdf_bytes, row["page"], box, rest, min_score, margin=margin, exclude=exclude,
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


IN_WORD_GAP_EM = 0.2           # a neighbour character this close (line heights) on the glyph's line makes it a letter of a
                               # word: letters inside a word stand ≤ 0,13 apart on the corpus, words ≥ 0,25 (a space)


def _in_word(tp, idx: int, n: int, boxes: list) -> bool:
    """True when the hit is letters of a longer word the text layer split (B2-A): PDFium's whole-word search
    answers „Ž" inside „UŽSAKOVAS" (objektas_h title block, the neighbours 0,27–0,46 pt away at a 3,6 pt line)
    and „I" inside „IŠKLOTINĖS" (objektas_a). A symbol standing alone has no character of its line that close."""
    left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
    h = max(max(b[3] - b[1], b[2] - b[0]) for b in boxes) or 1.0
    total = tp.count_chars()
    for j, step in ((idx - 1, -1), (idx + n, 1)):
        # past a space the text layer may have made up — a space that takes no room still leaves one word
        for _ in range(2):
            if 0 <= j < total and not tp.get_text_range(j, 1).strip():
                j += step
        if not (0 <= j < total) or not tp.get_text_range(j, 1).isalnum():
            continue                                   # a bracket or a dot ends a word: „JD(2)" is the symbol JD
        x0, y0, x1, y1 = tp.get_charbox(j)
        if min(top, y1) - max(bottom, y0) >= 0.5 * min(top - bottom, y1 - y0):         # the same line, read along x
            gap = max(x0 - right, left - x1)
        elif min(right, x1) - max(left, x0) >= 0.5 * min(right - left, x1 - x0):       # turned text, read along y
            gap = max(y0 - top, bottom - y1)
        else:
            continue
        if -0.5 * h < gap < IN_WORD_GAP_EM * h:
            return True
    return False


def _text_hits(pdf_bytes: bytes, glyph: str, pages: list[int]) -> dict[int, list[dict]]:
    """Where the character `glyph` stands as a word of its own on each page — DISPLAY-frame boxes. PDFium's
    text search under PDFIUM_LOCK; a hit that is letters of a longer word (`_in_word`) is not one."""
    from .pdf_vectors import _to_display
    from .pdfium_guard import PDFIUM_LOCK
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
                                if _in_word(tp, idx, n, boxes):
                                    continue
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
    from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at
    from .vector_symbols import ZONE_KINDS_WITHOUT_MARKS
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


RING_HOW_LT = "pagal ženklo žiedą ir jo atšakas brėžinio linijose"


def _ring_count(pdf_bytes: bytes, row: dict, wanted: list[int], other_sheets: bool) -> dict | None:
    """A black glyph that is ONE ring with arms (objektas_h's switches) counted from the paths — the ring's size,
    the number of its arms and whether two stand opposite (vector_symbols `ring_arm_*`, B2-A (c)): the shape
    search scores the four switch rows alike and cannot tell them apart. None when the glyph is no ring with
    arms, or a sheet holds more objects than the reader takes — the shape search counts it then, as before.
    Nothing in a legend, a table or the title block; on a sheet with a plan zone, nothing outside the plan
    (objektas_h p3's switch-height detail draws a door handle: a ring with one arm)."""
    from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at
    from .vector_symbols import ZONE_KINDS_WITHOUT_MARKS, ring_arm_instances, ring_arm_template
    tpl = ring_arm_template(pdf_bytes, row["page"], row["glyph_bbox_pct"])
    if not tpl:
        return None
    first, rest = _pages_for(pdf_bytes, row, wanted, other_sheets)
    if not first:
        first, rest = rest, []
    per_page: dict[int, list[dict]] = {}
    listed: list[dict] = []
    own = [row["glyph_bbox_pct"]] + ([row["legend_bbox_pct"]] if row.get("legend_bbox_pct") else [])

    def read(seq: list[int]) -> bool:
        for p in seq:
            found, complete = ring_arm_instances(pdf_bytes, p, tpl)
            if not complete:
                return False
            zones = read_zones(pdf_bytes, p, table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
            plans = [z["bbox_pct"] for z in zones if z.get("kind") == "planas"]
            keep = []
            for i in found:
                x, y = i["x_pct"], i["y_pct"]
                if p == row["page"] and any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in own):
                    continue
                z = zone_at(zones, x, y)
                zona = (str(z.get("kind")) if z is not None and z.get("kind") in ZONE_KINDS_WITHOUT_MARKS
                        else "kita" if plans and not any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in plans)
                        else None)
                if zona:
                    listed.append({"page": p, "x_pct": x, "y_pct": y, "zona": zona})
                    continue
                keep.append(i)
            per_page[p] = keep
        return True
    if not read(first):
        return None
    if rest and (other_sheets or not any(per_page.values())) and not read(rest):
        return None
    return {"status": "ok", "detail": None, "uz_zonu": listed[:200], "kaip_lt": RING_HOW_LT,
            **_sheet_rules(pdf_bytes, row, per_page)}


def _pages_word(pages: list[int]) -> str:
    return ("lape " if len(pages) == 1 else "lapuose ") + ", ".join(str(p) for p in pages)


def sentence_lt(row: dict, ans: dict) -> str:
    """What the person reads beside a row's count: what was counted, where, and what to check."""
    name = (row.get("text") or "be pavadinimo")[:60]
    if not row.get("countable", True):
        from .legend_rows import SAMPLE_LT
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
    how = ans.get("kaip_lt") or how
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


def count_rows(pdf_bytes: bytes, rows: list[dict], wanted: list[int], geo, *, min_score: float = 0.70,
               margin: float | None = None, other_sheets: bool = False, started: float | None = None,
               route_budget_s: float = ROUTE_BUDGET_S, vector_budget_s: float = VECTOR_BUDGET_S) -> list[dict]:
    """Count validated legend rows ({row_id, page, glyph_kind, glyph_bbox_pct, text, glyph_text, countable,
    legend_bbox_pct}) on the 1-based sheets `wanted`; `geo` = cv_match._mediabox_geometry(pdf_bytes). One answer
    per row, in order: {row_id, page, text, glyph_kind, status, saltinis, count, per_page, instances, kiti,
    partial, pages_not_read, score_floor, uz_zonu, sentence_lt}."""
    from .vector_symbols import count_glyph_instances_many
    started = time.monotonic() if started is None else started
    answers: dict[int, dict] = {}
    vector_rows = [k for k, r in enumerate(rows) if r["countable"] and r["glyph_kind"] in (None, "spalvotas")]
    if vector_rows:
        res = count_glyph_instances_many(pdf_bytes, [rows[k] for k in vector_rows], wanted,
                                         other_sheets=other_sheets, time_budget_s=vector_budget_s)
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
        remaining = max(0.0, route_budget_s - (time.monotonic() - started))
        if r["glyph_kind"] == "tekstas":
            got = _text_count(pdf_bytes, r, wanted, other_sheets)
            answers[k] = {**base, **got, "saltinis": "tekstas",
                          "instances": [{**i, "score": None, "saltinis": "tekstas"} for i in got["instances"]],
                          "kiti": [{**i, "score": None, "saltinis": "tekstas"} for i in got["kiti"]]}
            answers[k]["count"] = len(answers[k]["instances"])
            continue
        if r["glyph_kind"] == "juodas":
            ring = _ring_count(pdf_bytes, r, wanted, other_sheets)
            if ring is not None:                           # a ring with arms: counted from the paths (B2-A (c))
                answers[k] = {**base, **ring, "saltinis": "vektoriai",
                              "instances": [{**i, "score": None, "saltinis": "vektoriai"} for i in ring["instances"]],
                              "kiti": [{**i, "score": None, "saltinis": "vektoriai"} for i in ring["kiti"]]}
                answers[k]["count"] = len(answers[k]["instances"])
                continue
        if remaining <= 0:
            answers[k] = {**base, "partial": True, "pages_not_read": wanted, "saltinis": "rastras"}
            continue
        got = _raster_count(pdf_bytes, r, geo, wanted, float(min_score), other_sheets, remaining,
                            margin)
        if got["status"] != "ok":
            answers[k] = {**base, "status": got["status"], "detail": got["detail"], "saltinis": "rastras"}
            continue
        res = got["res"]
        answers[k] = {**base, "saltinis": "rastras", "per_page": got["per_page"], "fallback": got["fallback"],
                      "instances": [{**i, "saltinis": "rastras"} for i in got["instances"]],
                      "kiti": [{**i, "saltinis": "rastras"} for i in got["kiti"]],
                      "count": len(got["instances"]), "partial": res["partial"], "pages_not_read": res["pages_not_read"],
                      "uz_zonu": [{"page": e["page"], **x} for e in res["pages"] for x in e.get("uz_zonu") or []],
                      "score_floor": res["score_floor"], "raster_pages": got["raster_pages"], "detail": res["detail"]}
    _one_symbol_one_row(answers)
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
            # matches left out because they stand in a legend, a table, the title block or on letters (W5-D D2)
            "uz_zonu": [{"page": x["page"], "zona": x["zona"]} for x in (a.get("uz_zonu") or [])][:200],
            "sentence_lt": sentence_lt(r, a),
        })
    return out_rows


# ── the reading's own pass: legend rows → the things the sąmata counts ──────────────────────────────────────

AUTO_BUDGET_S = 120.0          # the whole automatic pass over a project (vector rows first, then the shape search)
AUTO_VECTOR_BUDGET_S = 40.0
SIULYMAI_KEY = "legendos_siulymai"    # parsed["_meta"][...] — the proposals (they ride `_meta` through every recompute
                                      # context and the free re-read); his confirmed counts: `_legendos_kiekiai`


def proposals(parsed: dict) -> dict | None:
    """The reading's legend proposals stored on the project (`_meta.legendos_siulymai`), or None."""
    meta = parsed.get("_meta") if isinstance(parsed, dict) else None
    hit = meta.get(SIULYMAI_KEY) if isinstance(meta, dict) else None
    return hit if isinstance(hit, dict) else None


def fold(text) -> str:
    """Lower case, no diacritics, one space — the vocabulary below is written in this form."""
    s = unicodedata.normalize("NFD", str(text or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# What a legend row's text says it is, for the rows the sąmata bills per piece. First match wins; matched on the
# folded text and — for a broken text layer that spaces every letter („Pavir š inis š viestuvas") — on the
# folded text without spaces. The first keys are the frontend's own (lib/legendCounts.js KINDS: trapai,
# difuzoriai, davikliai, jungikliai, rozetes, sviestuvai), so a count he confirms and a count proposed here land
# on the same kind; the light subkinds fold back to `sviestuvai` there (`CONFIRMED_KIND`).
_NOT_A_PIECE = re.compile(r"\blaid|led juost|\bjuost|vienoje linijoje|kolonel|tuscia|vamzd|kabeli")
FAMILIES: tuple[tuple[str, re.Pattern], ...] = (
    ("trapai", re.compile(r"trap(as|ai|o|u)?\b|drenaz")),
    ("difuzoriai", re.compile(r"difuzor")),
    ("davikliai", re.compile(r"davikl|detektor")),
    ("termostatai", re.compile(r"termostat|termoreguliator")),
    ("jungikliai", re.compile(r"jungikl|perjung")),
    ("rozetes", re.compile(r"rozet|lizd")),
    ("sviestuvai_pakabinami", re.compile(r"pakabinam\w*.*(sviestuv|\bsv\.)|(sviestuv|\bsv\.).*pakabinam|lubinis pakabinam")),
    ("sviestuvai_sieniniai", re.compile(r"(sienin|grindin)\w*.*sviestuv|sviestuv\w*.*sienoje|\bbra\b")),
    ("sviestuvai", re.compile(r"sviestuv|\bsv\.")),
    ("wc_remai", re.compile(r"bakel|wc rem|potinkin\w* rem")),
    ("klozetai", re.compile(r"klozet|unitaz")),
    ("praustuves", re.compile(r"praustuv")),
    ("plautuves", re.compile(r"plautuv|kriaukl")),
    ("dusai", re.compile(r"\bdus(as|o|ai|u)\b")),
    ("vonios_kubilai", re.compile(r"\bvoni(a|os)\b")),
    ("bide", re.compile(r"\bbide")),
)
_SQUEEZED = tuple((k, re.compile(rx.pattern.replace("\\b", "").replace(" ", ""))) for k, rx in FAMILIES)
CONFIRMED_KIND = {"sviestuvai_pakabinami": "sviestuvai", "sviestuvai_sieniniai": "sviestuvai"}
FAMILY_LT = {
    "trapai": "trapai", "difuzoriai": "difuzoriai", "davikliai": "davikliai", "termostatai": "termostatai",
    "jungikliai": "jungikliai", "rozetes": "rozetės", "sviestuvai_pakabinami": "pakabinami šviestuvai",
    "sviestuvai_sieniniai": "sieniniai šviestuvai", "sviestuvai": "lubiniai šviestuvai", "wc_remai": "WC rėmai",
    "klozetai": "klozetai", "praustuves": "praustuvės", "plautuves": "plautuvės", "dusai": "dušai",
    "vonios_kubilai": "vonios", "bide": "bidė",
}


def family_of(text) -> str | None:
    """The family a legend row's text names (FAMILIES), or None — a wire, an LED strip, a line sample, a speaker,
    or a text that names nothing the sąmata counts."""
    f = fold(text)
    if not f or _NOT_A_PIECE.search(f):
        return None
    for key, rx in FAMILIES:
        if rx.search(f):
            return key
    # a text layer that spaced the letters apart („pavir š inis š viestuvas": ≥ 2 one-letter words) is read once
    # more with the spaces out — only then, „voniose" in a note must not become a bathtub
    if sum(1 for w in f.split() if len(w) == 1 and w.isalpha()) < 2:
        return None
    squeezed = f.replace(" ", "")
    for key, rx in _SQUEEZED:
        if rx.search(squeezed):
            return key
    return None


def _auto_rows(pdf_bytes: bytes, n_pages: int, deadline: float) -> tuple[list[dict], list[int], list[int]]:
    """(legend rows that name a family, sheets with a legend, sheets not read in time). Every row carries its
    legend box and family."""
    from .legend_rows import suggest_legend_rows
    from .sheet_zones import read_zones
    rows: list[dict] = []
    with_legend: list[int] = []
    not_read: list[int] = []
    for p in range(1, n_pages + 1):
        if time.monotonic() > deadline:
            not_read.append(p)
            continue
        zones = read_zones(pdf_bytes, p).get("zones") or []
        if not any(isinstance(z, dict) and z.get("kind") == "legenda" for z in zones):
            continue
        with_legend.append(p)
        for leg in suggest_legend_rows(pdf_bytes, p, zones).get("legends") or []:
            for r in leg.get("rows") or []:
                fam = family_of(r.get("text"))
                if not fam or not r.get("countable", True) or not r.get("glyph_bbox_pct"):
                    continue
                rows.append({"row_id": str(r.get("row_id") or ""), "page": int(p), "glyph_kind": r.get("glyph_kind"),
                             "glyph_bbox_pct": list(r["glyph_bbox_pct"]), "text": str(r.get("text") or "")[:200],
                             "glyph_text": r.get("glyph_text"), "countable": True,
                             "legend_bbox_pct": list(leg.get("bbox_pct") or []) or None, "seima": fam})
    return rows, with_legend, not_read


def _dedupe_copies(rows: list[dict]) -> list[dict]:
    """One legend printed on two sheets (objektas_a p7 and p8; b p5 and p7) is one row: the counter already counts
    every sheet that carries the row's text, so the copy would count the same symbols twice. Same family and the
    same folded text → the first sheet's row."""
    seen: set[tuple[str, str]] = set()
    out = []
    for r in rows:
        k = (r["seima"], fold(r["text"]).replace(" ", ""))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


_STATED = re.compile(r"[-–—:]\s*(\d{1,3})\s*vnt\b", re.IGNORECASE)


def stated_count(text) -> int | None:
    """The count a legend row writes itself („Priglaistomas šviestuvas - 13 vnt."), or None. One number only."""
    hits = _STATED.findall(str(text or ""))
    if len(hits) != 1:
        return None
    n = int(hits[0])
    return n if n >= 1 else None


def auto_legend_counts(pdf_bytes: bytes, *, budget_s: float = AUTO_BUDGET_S, min_score: float = 0.70) -> dict:
    """The reading's legend counts — PROPOSALS, never a confirmed count:

        {status: ok|be_legendos|failed, lapai_su_legenda: [page…], neperskaityta: [page…], sekundes,
         seimos: {family: {kiekis, saltinis: vektoriai|rastras|tekstas|mixed, tekstas, lapai: [page…],
                  eilutes: [{row_id, page, tekstas, kiekis, saltinis, score_floor, lapai, dalinai, sakinys}]}},
         eilutes_be_kiekio: [{page, tekstas, seima, priezastis}]}

    A family appears only when at least one of its rows counted ≥ 1 symbol; a row that answered no count is listed
    in `eilutes_be_kiekio` with the counter's own sentence. Never raises."""
    started = time.monotonic()
    out = {"status": "ok", "lapai_su_legenda": [], "neperskaityta": [], "seimos": {}, "eilutes_be_kiekio": [],
           "sekundes": 0.0}
    try:
        from .cv_match import _mediabox_geometry
        geo = _mediabox_geometry(pdf_bytes)
        rows, with_legend, not_read = _auto_rows(pdf_bytes, len(geo), started + budget_s / 2)
        out["lapai_su_legenda"], out["neperskaityta"] = with_legend, not_read
        rows = _dedupe_copies(rows)
        if not rows:
            out["status"] = "be_legendos" if not with_legend else "ok"
            return out
        remaining = max(1.0, budget_s - (time.monotonic() - started))
        answers = count_rows(pdf_bytes, rows, list(range(1, len(geo) + 1)), geo, min_score=min_score,
                             route_budget_s=remaining, vector_budget_s=min(AUTO_VECTOR_BUDGET_S, remaining))
        fams: dict[str, dict] = {}
        for r, a in zip(rows, answers):
            n = int(a.get("count") or 0)
            stated = stated_count(r["text"])
            if stated is not None:
                # the designer wrote the count in the legend row itself („Priglaistomas šviestuvas - 13 vnt.",
                # objektas_i): that is the drawing's own number; the symbols counted on the plan stay beside it
                pages = sorted({int(i["page"]) for i in a.get("instances") or []})
                f = fams.setdefault(r["seima"], {"kiekis": 0, "eilutes": [], "lapai": [], "saltiniai": set()})
                f["kiekis"] += stated
                f["saltiniai"].add("tekstas_legendoje")
                f["lapai"] = sorted(set(f["lapai"]) | {r["page"]})
                f["eilutes"].append({"row_id": r["row_id"], "page": r["page"], "tekstas": r["text"], "kiekis": stated,
                                     "saltinis": "tekstas_legendoje", "plane_rasta": n if a.get("status") == "ok" else None,
                                     "score_floor": a.get("score_floor"), "lapai": pages, "dalinai": False,
                                     "sakinys": f"Legendos eilutėje parašyta: {stated} vnt."
                                                + (f" Plane rasta ženklų: {n}." if a.get("status") == "ok" else "")})
                continue
            if a.get("status") != "ok" or n < 1:
                out["eilutes_be_kiekio"].append({"page": r["page"], "tekstas": r["text"], "seima": r["seima"],
                                                 "priezastis": a.get("sentence_lt")})
                continue
            pages = sorted({int(i["page"]) for i in a.get("instances") or []})
            f = fams.setdefault(r["seima"], {"kiekis": 0, "eilutes": [], "lapai": [], "saltiniai": set()})
            f["kiekis"] += n
            f["saltiniai"].add(a.get("saltinis"))
            f["lapai"] = sorted(set(f["lapai"]) | set(pages))
            f["eilutes"].append({"row_id": r["row_id"], "page": r["page"], "tekstas": r["text"], "kiekis": n,
                                 "saltinis": a.get("saltinis"), "score_floor": a.get("score_floor"),
                                 "lapai": pages, "dalinai": bool(a.get("partial")), "sakinys": a.get("sentence_lt")})
        for f in fams.values():
            src = sorted(s for s in f.pop("saltiniai") if s)
            f["saltinis"] = src[0] if len(src) == 1 else "mixed"
            f["tekstas"] = "; ".join(e["tekstas"] for e in f["eilutes"])
        out["seimos"] = fams
    except Exception:  # noqa: BLE001 — the reading never sinks on a count
        log.warning("automatic legend counts failed", exc_info=True)
        out["status"] = "failed"
    finally:
        out["sekundes"] = round(time.monotonic() - started, 2)
    return out


# ── what the rows take: his confirmed counts first, then the reading's proposals ────────────────────────────

CONFIRMED_KEY = "_legendos_kiekiai"   # written by the frontend (lib/legendCounts.js) from his count types


def _confirmed(parsed: dict) -> dict[str, dict]:
    store = parsed.get(CONFIRMED_KEY) if isinstance(parsed, dict) else None
    out: dict[str, dict] = {}
    if not isinstance(store, dict):
        return out
    for kind, hit in store.items():
        if not isinstance(hit, dict):
            continue
        try:
            n = int(float(hit.get("kiekis")))
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[str(kind)] = {"n": n, "tekstas": str(hit.get("tekstas") or "").strip(), "page": hit.get("page")}
    return out


def _pages_lt(pages) -> str:
    ps = [int(p) for p in (pages or []) if isinstance(p, (int, float))]
    if not ps:
        return ""
    return ("lapas " if len(ps) == 1 else "lapai ") + ", ".join(str(p) for p in ps)


def counts_for_rows(parsed: dict) -> dict[str, dict]:
    """{family: {n, patvirtinta, tekstas, sakinys, saltinis}} — the counts the per-piece rows take. A count he
    confirmed with the count tool (`_legendos_kiekiai`, keyed by the frontend's kinds) wins over the reading's
    proposal for every family that folds into that kind (`CONFIRMED_KIND`); otherwise the proposal
    (`_meta.legendos_siulymai`), which the sentence presents as one to confirm. Pure, never raises."""
    out: dict[str, dict] = {}
    try:
        conf = _confirmed(parsed)
        prop = proposals(parsed)
        fams = (prop.get("seimos") if isinstance(prop, dict) else None) or {}
        for fam, f in fams.items():
            if not isinstance(f, dict) or CONFIRMED_KIND.get(fam, fam) in conf:
                continue
            try:
                n = int(f.get("kiekis") or 0)
            except (TypeError, ValueError):
                continue
            if n < 1:
                continue
            where = _pages_lt(f.get("lapai"))
            stated_all = f.get("saltinis") == "tekstas_legendoje"
            sak = (f"{'Brėžinio legendoje parašyta' if stated_all else 'Pasiūlymas iš brėžinio legendos'}: "
                   f"„{str(f.get('tekstas') or '')[:120]}“ — {n} vnt."
                   + (f" ({where})" if where else "") + ". Patvirtinkite įrankiu „Ženklai“ (Pažymėti legendą): "
                   "patvirtintas skaičius pakeis šį.")
            if f.get("saltinis") in ("rastras", "mixed"):
                sak += " Dalis ženklų rasta pagal formą — peržiūrėkite kiekvieną vietą."
            out[fam] = {"n": n, "patvirtinta": False, "tekstas": f.get("tekstas"), "sakinys": sak,
                        "saltinis": f.get("saltinis")}
        for kind, c in conf.items():
            out[kind] = {"n": c["n"], "patvirtinta": True, "tekstas": c["tekstas"], "saltinis": "jusu",
                         "sakinys": f"Suskaičiuota brėžinyje pagal legendos eilutę „{c['tekstas'][:120]}“: "
                                    f"{c['n']} vnt. (jūsų patvirtinta)."}
    except Exception:  # noqa: BLE001
        log.warning("counts_for_rows failed", exc_info=True)
    return out


def no_count_reason(parsed: dict, what_lt: str) -> str:
    """The blank row's sentence when no legend count exists for it: no legend at all, or a legend without that
    symbol (or its symbol not found on the plan)."""
    prop = proposals(parsed)
    if isinstance(prop, dict) and prop.get("lapai_su_legenda"):
        return (f"Brėžinio legendoje {what_lt} ženklo neradau arba jo nepavyko suskaičiuoti plane — suskaičiuokite "
                "įrankiu „Ženklai“ arba įrašykite kiekį pagal planą.")
    return (f"Brėžinyje nėra legendos, pagal kurią būtų galima suskaičiuoti {what_lt} — suskaičiuokite įrankiu "
            "„Ženklai“ arba įrašykite kiekį pagal planą.")

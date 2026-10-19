"""A schedule's tags on the plan — „D-1", „L2" … — counted where the drawing writes them (Pathon v3 W5-D, D10).

A door or window schedule lists each type with its code and how many; the plan writes the code beside every
opening of that type. This reader counts each code where it stands as a word of its own on the sheets, outside
the schedule itself and outside every legend, table and title-block zone (extractor/sheet_zones.py) — €0, the
PDF's text layer through PDFium (under PDFIUM_LOCK). The comparison with the schedule's own count becomes a
Patikra question (extractor/project_questions.py `lentele_zymos`); nothing here changes a quantity.

    count_schedule_tags(pdf_bytes, record) -> {kodas: {"kiekis": int, "puslapiai": [p…],
                                                       "vietos": [{page, box_pct}]}} | None

`record` is a schedule record (`_duru_ziniarastis` / `_langu_ziniarastis`) with `lentele.eilutes[].kodas`. None when
the record has no coded rows or the PDF cannot be read. Never raises.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("samatu.schedule_tags")

ZONE_KINDS_WITHOUT_TAGS = ("legenda", "lentele", "antspaudas")
MAX_CODES = 40
MAX_PAGES = 80
MAX_HITS_PER_CODE = 200
_CODE_RE = re.compile(r"^[A-ZĄČĘĖĮŠŲŪŽ]{1,3}[-.]?\d{1,3}[a-z]?$")


def _codes(record: dict | None) -> list[str]:
    table = (record or {}).get("lentele") if isinstance(record, dict) else None
    out: list[str] = []
    for row in (table or {}).get("eilutes") or []:
        code = str((row or {}).get("kodas") or "").strip()
        if code and _CODE_RE.match(code) and code not in out:
            out.append(code)
    return out[:MAX_CODES]


def _inside(box, x: float, y: float) -> bool:
    return bool(box) and len(box) == 4 and box[0] <= x <= box[2] and box[1] <= y <= box[3]


def count_schedule_tags(pdf_bytes: bytes, record: dict | None) -> dict | None:
    codes = _codes(record)
    if not codes or not pdf_bytes:
        return None
    try:
        return _count(pdf_bytes, record, codes)
    except Exception as exc:  # noqa: BLE001 — a tag count never sinks its caller
        log.warning("schedule tag count failed: %r", exc)
        return None


def _count(pdf_bytes: bytes, record: dict, codes: list[str]) -> dict:
    import pypdfium2 as pdfium

    from .pdf_vectors import _to_display
    from .pdfium_guard import PDFIUM_LOCK
    from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at

    table = record.get("lentele") or {}
    # the schedule's own rows (and the table's box) are where the codes are LISTED, not where they stand
    own = [(int(r.get("page") or table.get("page") or 0), r.get("bbox_pct")) for r in table.get("eilutes") or []
           if isinstance(r, dict)]
    if table.get("bbox_pct"):
        own.append((int(table.get("page") or 0), table["bbox_pct"]))

    hits: dict[str, list[dict]] = {c: [] for c in codes}
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            n = min(len(doc), MAX_PAGES)
            for p in range(1, n + 1):
                page = doc[p - 1]
                try:
                    W, H = (float(v) for v in page.get_size())
                    k = (int(page.get_rotation() or 0) // 90) % 4
                    Wu, Hu = (H, W) if k in (1, 3) else (W, H)
                    tp = page.get_textpage()
                    try:
                        for code in codes:
                            searcher = tp.search(code, match_case=True, match_whole_word=True)
                            try:
                                while len(hits[code]) < MAX_HITS_PER_CODE:
                                    occ = searcher.get_next()
                                    if not occ:
                                        break
                                    idx, cnt = occ
                                    boxes = [tp.get_charbox(i) for i in range(idx, idx + cnt)]
                                    pts = [_to_display(x, y, Wu, Hu, k) for x, y in
                                           ((min(b[0] for b in boxes), min(b[1] for b in boxes)),
                                            (max(b[2] for b in boxes), max(b[3] for b in boxes)))]
                                    x0, x1 = sorted((pts[0][0], pts[1][0]))
                                    y0, y1 = sorted((pts[0][1], pts[1][1]))
                                    hits[code].append({"page": p, "box_pct": [round(x0 / W, 5), round(y0 / H, 5),
                                                                              round(x1 / W, 5), round(y1 / H, 5)]})
                            finally:
                                searcher.close()
                    finally:
                        tp.close()
                finally:
                    page.close()
        finally:
            doc.close()

    zones: dict[int, list] = {}
    out: dict[str, dict] = {}
    for code, found in hits.items():
        kept = []
        for h in found:
            b = h["box_pct"]
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if any(pg == h["page"] and _inside(box, cx, cy) for pg, box in own):
                continue
            if h["page"] not in zones:
                zones[h["page"]] = read_zones(pdf_bytes, h["page"], table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
            z = zone_at(zones[h["page"]], cx, cy)
            if z is not None and z.get("kind") in ZONE_KINDS_WITHOUT_TAGS:
                continue
            kept.append(h)
        out[code] = {"kiekis": len(kept), "puslapiai": sorted({h["page"] for h in kept}), "vietos": kept}
    return out

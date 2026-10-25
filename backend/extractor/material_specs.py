"""extractor.material_specs — the designer's material specs for ONE room, read from the sheets' TEXT (v4 Phase 3c-2).

On-demand (a click in the room card), never part of the reading. Pages targeted: „VIRTUVĖS SPALVOS", „VAIKŲ VONIOS
SPALVOS", the room's „… IŠKLOTINĖS" — paint codes, tile formats, floorboards.

Until v4 3c-2 one model call per room LOOKED at those sheets (~€0,20) and wrote the specs out. Now the sheets' text
layer is read (local OCR behind `SAMATU_OCR` for a sheet without one):

  · deterministic first — a tile format „60x120" / „600×1200 mm", a paint code „HC-98" / „NCS S 0502-Y" / „RAL 9016",
    the line each stands on kept as `raw_text`;
  · with a client, the same TEXT may be structured by text/schema_llm.py into the schema below — every value must
    stand in the text as written, else it is refused (plan R3). The model never sees a sheet.

Returns {paint, sienos_plyteles, grindys_plyteles, grindys_medines, _meta}; a field the text does not give is None.
Cached at project level by the caller. Never raises.
"""
from __future__ import annotations

import re
import time

__all__ = ["extract_room_material_specs"]

_TILE = re.compile(r"(?<!\d)(\d{2,4})\s*[x×X]\s*(\d{2,4})(?:\s*[x×X]\s*(\d{1,2}))?\s*(mm|cm)?", re.IGNORECASE)
_PAINT = re.compile(r"\b(?:NCS\s*S?\s*\d{4}-[A-Z]\d{0,2}[A-Z]?|RAL\s*\d{4}|[A-Z]{1,3}-\d{2,4}|SW\s*\d{4})\b")
_WOOD = re.compile(r"\b(parket|grindlent|lentos|ąžuol|azuol|oak)\w*", re.IGNORECASE)
_FLOOR = re.compile(r"\bgrind", re.IGNORECASE)
_WALL = re.compile(r"\bsien", re.IGNORECASE)


def _empty(meta: dict) -> dict:
    return {"paint": None, "sienos_plyteles": None, "grindys_plyteles": None, "grindys_medines": None, "_meta": meta}


def _page_lines(pdf_bytes: bytes, page: int) -> list[str]:
    try:
        from extractor.pdf_page_cache import page_texts
        texts = page_texts(pdf_bytes)
        t = texts[page - 1] if 1 <= page <= len(texts) else ""
    except Exception:  # noqa: BLE001
        t = ""
    if len((t or "").strip()) < 8:
        try:
            from text.ocr import ocr_enabled, ocr_page
            if ocr_enabled():
                _w, _h, words = ocr_page(pdf_bytes, page)
                t = " ".join(w.text for w in words)
        except Exception:  # noqa: BLE001
            pass
    return [ln.strip() for ln in (t or "").splitlines() if ln.strip()]


def _tile(line: str) -> dict | None:
    m = _TILE.search(line)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if (m.group(4) or "").lower() == "cm":
        a, b = a * 10, b * 10
    if not (50 <= min(a, b) and max(a, b) <= 3200):
        return None
    return {"brand": None, "model": None, "size_mm": f"{a}x{b}",
            "storis_mm": float(m.group(3)) if m.group(3) else None, "spalva": None, "raw_text": line[:200]}


def extract_room_material_specs(pdf_bytes: bytes, pages_to_inspect: list[int], room_pavadinimas: str,
                                client=None) -> dict:
    """The specs for one room from its sheets' text. `client` is used only for text/schema_llm.py."""
    t0 = time.time()
    pages = sorted({int(p) for p in (pages_to_inspect or []) if int(p) >= 1})
    if not pages:
        return _empty({"elapsed_s": 0, "pages_inspected": []})
    lines: list[str] = []
    for p in pages:
        lines += _page_lines(pdf_bytes, p)
    meta = {"elapsed_s": 0.0, "pages_inspected": pages, "saltinis": "tekstas", "input_tokens": 0, "output_tokens": 0}
    out = _empty(meta)
    if not lines:
        meta["_error"] = "no_text"
        meta["elapsed_s"] = round(time.time() - t0, 2)
        return out
    for ln in lines:
        tile = _tile(ln)
        if tile and "plytel" in ln.lower():
            key = "grindys_plyteles" if _FLOOR.search(ln) and not _WALL.search(ln) else "sienos_plyteles"
            if out[key] is None:
                out[key] = tile
        if out["paint"] is None and ("daž" in ln.lower() or "daz" in ln.lower() or _PAINT.search(ln)):
            m = _PAINT.search(ln)
            if m:
                out["paint"] = {"brand": None, "code": m.group(0), "name": None, "where": None, "raw_text": ln[:200]}
        if out["grindys_medines"] is None and _WOOD.search(ln) and _FLOOR.search(ln + " grind"):
            out["grindys_medines"] = {"brand": None, "model": None, "finish": None, "supplier": None,
                                      "raw_text": ln[:200]}
    if client is not None:
        _schema_fill(out, "\n".join(lines), room_pavadinimas, client, meta)
    meta["elapsed_s"] = round(time.time() - t0, 2)
    return out


def _schema_fill(out: dict, text: str, room: str, client, meta: dict) -> None:
    """Brand / model / colour names the regexes cannot tell apart, from the TEXT (schema_llm, substring-guarded)."""
    from text.schema_llm import structure
    fields = {"kas": ["paint", "sienos_plyteles", "grindys_plyteles", "grindys_medines"], "brand": "text",
              "model": "text", "code": "text", "spalva": "text", "size_mm": "text", "raw_text": "text"}
    res = structure(text, fields=fields, key="kas", client=client,
                    instruction=(f"Patalpa: {room}. Iš teksto ištrauk šios patalpos medžiagų specifikacijas: "
                                 "dažai (paint), sienų plytelės, grindų plytelės, medinės grindys. Kiekvienai — "
                                 "gamintojas (brand), modelis, kodas, spalva, dydis mm ir visa eilutė (raw_text)."))
    meta["input_tokens"] = int((res.get("_meta") or {}).get("input_tokens") or 0)
    meta["output_tokens"] = int((res.get("_meta") or {}).get("output_tokens") or 0)
    meta["schema_llm"] = {"status": res.get("status"), "atmesta": len(res.get("refused") or [])}
    for it in res.get("items") or []:
        key = it.get("kas")
        if key not in out:
            continue
        rec = dict(out[key] or {})
        for f in ("brand", "model", "code", "spalva", "size_mm", "raw_text"):
            if it.get(f) and not rec.get(f):
                rec[f] = it[f]
        out[key] = rec

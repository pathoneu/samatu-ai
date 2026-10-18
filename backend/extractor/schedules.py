"""Schedules — which ruled table on the drawing is a door, window, finish or tile schedule, and its rows with the
values they state and the box each row stands in (Pathon v3, track C). €0, no model.

The generic table reader (extractor/table_reader.py) gives every ruled table with its header text and every row
with its cells and box. This module maps a table's HEADER to roles — the way the eksplikacija reader maps
Nr | Pavadinimas | Plotas, by the header words, never by column order — and reads each row's values:

  durys, langai  kodas · plotis · aukštis (or one „dydis" cell „910x2100") · tipas · kiekis · pastaba
                 a door table and a window table share the header; the title („Durų žiniaraštis", „Langų
                 specifikacija") or, without one, the codes (D-1… doors, L-1… windows) say which; a table listing
                 both is split by code
  apdaila        patalpa (its number and/or name) · grindys · sienos · lubos · grindjuostės (the finish schedule —
                 „apdailos lentelė" / „apdailos žiniaraštis")
  plyteles       vieta · formatas · gamintojas (+ kodas, kiekis) — the tile specification as a table
  eksplikacija   the room table, by the eksplikacija reader's own header map (`_detect_header`) — listed so its
                 sum can be checked against the rooms; the rooms themselves stay the eksplikacija reader's

Numbers go through the eksplikacija reader's `_parse_number_preserving_decimals` (LT decimals, units at either
end); sizes are millimetres — a header that says „m" or „cm" is converted, a header that says nothing is read by
size (a door is 400–4000 mm wide; a value under 10 is metres). A table continued on a later sheet — no header of
its own, the same columns — continues the schedule; a code already listed is not listed twice.

Every row carries `page` and `bbox_pct` in the PDFium DISPLAY frame (see table_reader), so the evidence crop of
`(page, bbox_pct)` is that row on the drawing.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterable

from .pdfplumber_eksplikacija import (_detect_header, _fold_header, _parse_number_preserving_decimals,
                                      _try_parse_total_row)
from .table_reader import read_pages_tables

log = logging.getLogger("samatu.schedules")

SCHEDULES_VERSION = 1
KINDS = ("durys", "langai", "apdaila", "plyteles", "eksplikacija")
MAX_PAGES = 24               # sheets read for tables in one pass (the candidates come from the text layer)

# a sheet that may carry a schedule: its text names one
CANDIDATE_RE = re.compile(r"žiniarašt|ziniarast|specifikac|lentel|eksplikac|apdailos|sąrašas|sarasas", re.IGNORECASE)

# header words per role — matched against the folded header (lower case, LT letters folded); a token matches a
# word that STARTS with it, a token with a space matches as a phrase. Earlier tokens are stronger.
OPENING_ROLES: dict[str, tuple[str, ...]] = {
    "kodas": ("kodas", "zymuo", "zymejimas", "zymeklis", "markiruote", "zenklas", "pozicija", "poz", "nr"),
    "plotis": ("plotis",),
    "aukstis": ("aukstis",),
    "dydis": ("dydis", "matmenys", "gabaritai", "matmuo"),
    "tipas": ("tipas", "kryptis", "atidarym", "varstym", "aprasymas", "konstrukcij", "apvad", "rusis"),
    "kiekis": ("kiekis", "vnt", "skaicius"),
    "pastaba": ("pastab", "komentar"),
}
FINISH_ROLES: dict[str, tuple[str, ...]] = {
    "nr": ("patalpos nr", "patalpu nr", "nr", "eil nr", "numeris"),
    "patalpa": ("patalpa", "patalpos", "patalpu", "pavadinimas", "paskirtis"),
    "grindjuostes": ("grindjuost", "cokol", "plintus"),
    "grindys": ("grind", "grindu danga"),
    "sienos": ("sien",),
    "lubos": ("lub",),
}
TILE_ROLES: dict[str, tuple[str, ...]] = {
    "vieta": ("vieta", "naudojimo vieta", "patalpa", "patalpos", "kur"),
    "formatas": ("formatas", "dydis", "matmenys", "plyteliu dydis"),
    "gamintojas": ("gamintojas", "kolekcija", "prekes zenklas", "tiekejas", "pavadinimas"),
    "kodas": ("kodas", "zymuo", "zymejimas", "nr"),
    "kiekis": ("kiekis", "plotas"),
}
# a column about the wall, not the opening: its „plotis" is the wall's thickness
_NOT_OPENING_SIZE = re.compile(r"\b(pertvar|sien|staktos gylis)")
_OPENING_SIZE_PREFER = re.compile(r"\b(ang|dur|lang|stakt)")
_DOOR_TITLE = re.compile(r"dur")
_WINDOW_TITLE = re.compile(r"lang|vitrin")
_FINISH_TITLE = re.compile(r"apdail")
_TILE_WORD = re.compile(r"plytel")
# codes: D-1, D1, VD-2, ID-3, DV-1 doors; L-1, L1, LG-2, LA-1 windows (LD-1 is a ceiling or niche detail)
_DOOR_CODE = re.compile(r"^(?:D|VD|ID|DV)\s?-?\s?\d{1,3}[a-zA-Z]?\*?$")          # door_schedule._CODE_RE's set
_WINDOW_CODE = re.compile(r"^(?:L|LG|LA|LV)\s?-?\s?\d{1,3}[a-zA-Z]?\*?$")
_ANY_CODE = re.compile(r"^[A-ZĄČĘĖĮŠŲŪŽ]{1,3}\s?[-.]?\s?\d{1,3}[a-zA-Z]?\*?$")
_ROOM_NR = re.compile(r"^(\d{1,3}(?:[.\-]\d{1,3})?)\.?\s*(.*)$")
_SIZE_RE = re.compile(r"(?<!\d)(\d{1,4}(?:[.,]\d{1,2})?)\s*[x×X*]\s*(\d{1,4}(?:[.,]\d{1,2})?)(?!\d)")
_KIEKIS_RE = re.compile(r"^\s*(\d{1,3})\s*(?:vnt\.?)?\s*$", re.IGNORECASE)
_VNT_RE = re.compile(r"\b(\d{1,2})\s*vnt", re.IGNORECASE)
MIN_MM, MAX_MM = 300, 6000
_AREA_ONLY = {"m2", "m 2", "kv m"}      # a room table's area column headed by its unit alone (objektas_h)


def _words(fold: str) -> list[str]:
    return fold.split()


def _matches(fold: str, token: str) -> bool:
    if not fold:
        return False
    if " " in token:
        return f" {token}" in f" {fold}"
    return any(w.startswith(token) for w in _words(fold))


def _assign(header_fold: list[str], roles: dict[str, tuple[str, ...]], *, kind: str | None = None) -> dict[str, int]:
    """role → column index; a column takes at most one role, a role at most one column (its strongest match;
    sizes prefer the column about the opening over one about the wall)."""
    out: dict[str, int] = {}
    taken: set[int] = set()
    for role, tokens in roles.items():
        best: tuple[int, int, int] | None = None              # (token rank, preference, column)
        for col, fold in enumerate(header_fold):
            if col in taken or not fold or len(fold) > 60:
                continue
            rank = next((i for i, t in enumerate(tokens) if _matches(fold, t)), None)
            if rank is None:
                continue
            pref = 0
            if role in ("plotis", "aukstis"):
                if _NOT_OPENING_SIZE.search(fold):
                    continue
                pref = 0 if _OPENING_SIZE_PREFER.search(fold) else 1
            if role == "kodas" and (_matches(fold, "plotis") or _matches(fold, "aukstis")):
                continue
            cand = (rank, pref, col)
            if best is None or cand < best:
                best = cand
        if best is not None:
            out[role] = best[2]
            taken.add(best[2])
    return out


def _unit(fold: str) -> str | None:
    words = _words(fold)
    for u in ("mm", "cm", "m"):
        if u in words:
            return u
    return None


def _mm(text: str | None, unit: str | None) -> int | None:
    """A size cell → millimetres, or None when it is not a plausible opening size."""
    val, _raw = _parse_number_preserving_decimals(text or "")
    if val is None or val <= 0:
        return None
    if unit == "m" or (unit is None and val < 10):
        val *= 1000
    elif unit == "cm":
        val *= 10
    mm = int(round(val))
    return mm if MIN_MM <= mm <= MAX_MM else None


def _pair_mm(text: str | None, unit: str | None) -> tuple[int | None, int | None]:
    m = _SIZE_RE.search(text or "")
    if not m:
        return None, None
    return _mm(m.group(1), unit), _mm(m.group(2), unit)


def _cell(row: dict, col: int | None) -> str:
    if col is None:
        return ""
    cells = row.get("cells") or []
    return str(cells[col] if col < len(cells) else "").strip()


def _code(text: str) -> str | None:
    t = " ".join(text.split()).rstrip("*").strip()
    return t if _ANY_CODE.match(t + "") else None


# ── one table → a schedule kind ─────────────────────────────────────────────


def classify_table(table: dict) -> tuple[str | None, dict[str, int]]:
    """(kind, role → column) for a table read by table_reader, or (None, {})."""
    header = [str(h or "") for h in table.get("header") or []]
    fold = [_fold_header(h) for h in header]
    title = _fold_header(table.get("title") or "")
    everything = " ".join([title] + fold)
    if not any(fold):
        return None, {}
    eks = _detect_header(header) or _detect_header(["plotas" if f in _AREA_ONLY else h for h, f in zip(header, fold)])
    if eks:
        return "eksplikacija", eks
    roles = _assign(fold, OPENING_ROLES)
    if "kodas" in roles and ({"plotis", "aukstis"} & set(roles) or "dydis" in roles):
        codes = [c for c in (_code(_cell(r, roles["kodas"])) for r in table.get("rows") or []) if c]
        doors = sum(1 for c in codes if _DOOR_CODE.match(c))
        windows = sum(1 for c in codes if _WINDOW_CODE.match(c))
        opening = None
        if codes and _WINDOW_TITLE.search(title) and not _DOOR_TITLE.search(title):
            opening = "langai"
        elif codes and _DOOR_TITLE.search(title) and not _WINDOW_TITLE.search(title):
            opening = "durys"
        elif doors or windows:
            opening = "durys" if doors >= windows else "langai"
        if opening:
            return opening, roles
        # coded and sized, but no door or window: a tile or finish table with a code column — read on
    if _TILE_WORD.search(everything):
        roles = _assign(fold, TILE_ROLES)
        if ({"formatas", "gamintojas"} & set(roles)) and ({"vieta", "kodas"} & set(roles)):
            return "plyteles", roles
    roles = _assign(fold, FINISH_ROLES)
    if ({"patalpa", "nr"} & set(roles)) and len({"grindys", "sienos", "lubos"} & set(roles)) >= 2:
        return "apdaila", roles
    return None, {}


# ── a table's rows → schedule rows ──────────────────────────────────────────


def _base_row(table: dict, row: dict) -> dict:
    return {"page": int(table.get("page") or 0), "table_id": table.get("table_id"), "row_idx": row.get("row_idx"),
            "bbox_pct": row.get("bbox_pct"), "cells": list(row.get("cells") or [])}


def _opening_row(table: dict, row: dict, roles: dict[str, int], units: dict[str, str | None]) -> dict | None:
    from .door_schedule import _row_type
    code = _code(_cell(row, roles.get("kodas")))
    if not code:
        return None
    w = _mm(_cell(row, roles.get("plotis")), units.get("plotis")) if "plotis" in roles else None
    h = _mm(_cell(row, roles.get("aukstis")), units.get("aukstis")) if "aukstis" in roles else None
    if (w is None or h is None) and "dydis" in roles:
        pw, ph = _pair_mm(_cell(row, roles["dydis"]), units.get("dydis"))
        w, h = (w if w is not None else pw), (h if h is not None else ph)
    others = [c for i, c in enumerate(row.get("cells") or []) if i != roles.get("kodas") and str(c or "").strip()]
    text = " ".join(" ".join(str(c).split()) for c in others)
    kiekis = None
    if "kiekis" in roles:
        m = _KIEKIS_RE.match(_cell(row, roles["kiekis"]))
        kiekis = int(m.group(1)) if m else None
    if kiekis is None:
        m = _VNT_RE.search(text)
        kiekis = int(m.group(1)) if m else None
    tipas_text = _cell(row, roles.get("tipas")) if "tipas" in roles else ""
    return {**_base_row(table, row), "kodas": code, "plotis_mm": w, "aukstis_mm": h,
            "tipas": _row_type(text), "tipas_tekstas": tipas_text or None, "kiekis": kiekis,
            "pastaba": _cell(row, roles.get("pastaba")) or None, "tekstas": text[:160]}


def _finish_row(table: dict, row: dict, roles: dict[str, int]) -> dict | None:
    from .floor_coverings import classify_line
    nr = _cell(row, roles.get("nr")) if "nr" in roles else ""
    name = _cell(row, roles.get("patalpa")) if "patalpa" in roles else ""
    if not nr and name:
        m = _ROOM_NR.match(name)
        if m and m.group(2):
            nr, name = m.group(1), m.group(2).strip()
    finishes = {k: (_cell(row, roles.get(k)) or None) for k in ("grindys", "sienos", "lubos", "grindjuostes") if k in roles}
    if not (nr or name) or not any(finishes.values()):
        return None
    return {**_base_row(table, row), "nr": nr or None, "pavadinimas": name or None, **finishes,
            "grindu_danga": classify_line(finishes.get("grindys")) if finishes.get("grindys") else None}


def _tile_row(table: dict, row: dict, roles: dict[str, int], units: dict[str, str | None]) -> dict | None:
    values = {k: (_cell(row, roles.get(k)) or None) for k in TILE_ROLES if k in roles}
    if not any(values.get(k) for k in ("vieta", "formatas", "gamintojas")):
        return None
    w, h = _pair_mm(values.get("formatas"), units.get("formatas") or "mm")
    return {**_base_row(table, row), **values, "formatas_mm": [w, h] if w and h else None}


def _room_row(table: dict, row: dict, roles: dict[str, int]) -> dict | None:
    nr = _cell(row, roles.get("nr")) if "nr" in roles else ""
    name = _cell(row, roles.get("pavadinimas")) if "pavadinimas" in roles else ""
    area, raw = _parse_number_preserving_decimals(_cell(row, roles.get("plotas")))
    if area is None or not (nr or name):
        return None
    return {**_base_row(table, row), "nr": nr or None, "pavadinimas": name or None, "plotas_m2": round(area, 2),
            "plotas_raw": raw}


def schedule_rows(table: dict, kind: str, roles: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """(rows, total rows) of `table` read as `kind` with the role → column map `roles`."""
    header = [str(h or "") for h in table.get("header") or []]
    units = {role: _unit(_fold_header(header[col])) if col < len(header) else None for role, col in roles.items()}
    rows: list[dict] = []
    totals: list[dict] = []
    for row in table.get("rows") or []:
        if kind in ("durys", "langai"):
            got = _opening_row(table, row, roles, units)
            if got and kind == "durys" and _WINDOW_CODE.match(got["kodas"]) and not _DOOR_CODE.match(got["kodas"]):
                got = None                                     # a window listed in a mixed table goes to the windows
            if got and kind == "langai" and _DOOR_CODE.match(got["kodas"]):
                got = None
        elif kind == "apdaila":
            got = _finish_row(table, row, roles)
        elif kind == "plyteles":
            got = _tile_row(table, row, roles, units)
        else:
            # the table's own sum („Iš viso", „Bendras plotas") first — it is not a room
            total = _try_parse_total_row(list(row.get("cells") or []), int(row.get("row_idx") or 0),
                                         int(table.get("page") or 0), columns=roles)
            if total:
                totals.append({**total, "bbox_pct": row.get("bbox_pct"), "table_id": table.get("table_id")})
                continue
            got = _room_row(table, row, roles)
        if got:
            rows.append(got)
    return rows, totals


# ── the drawing ─────────────────────────────────────────────────────────────


def _key_of(kind: str, row: dict) -> str:
    if kind in ("durys", "langai"):
        return str(row.get("kodas") or "")
    if kind in ("apdaila", "eksplikacija"):
        return f"{row.get('nr') or ''}|{row.get('pavadinimas') or ''}"
    return "|".join(str(row.get(k) or "") for k in ("kodas", "vieta", "formatas"))


def _schedule(kind: str, table: dict, roles: dict[str, int]) -> dict:
    header = [str(h or "") for h in table.get("header") or []]
    return {"kind": kind, "title": table.get("title"), "page": int(table.get("page") or 0),
            "pages": [int(table.get("page") or 0)], "table_ids": [table.get("table_id")],
            "bbox_pct": table.get("bbox_pct"), "cols": int(table.get("cols") or 0),
            "columns": {role: header[col] for role, col in roles.items() if col < len(header)},
            "_roles": dict(roles), "rows": [], "totals": [], "tesinys": False}


def _add(sched: dict, rows: list[dict], totals: list[dict]) -> int:
    have = {_key_of(sched["kind"], r) for r in sched["rows"]}
    n = 0
    for r in rows:
        k = _key_of(sched["kind"], r)
        if k and k in have:
            continue
        have.add(k)
        sched["rows"].append(r)
        n += 1
    seen = {(t.get("value"), t.get("label")) for t in sched["totals"]}
    for t in totals:
        if (t.get("value"), t.get("label")) not in seen:      # the same table on every sheet sums once
            seen.add((t.get("value"), t.get("label")))
            sched["totals"].append(t)
    return n


def _as_continuation(table: dict) -> dict:
    """A table that may continue a schedule: its header rows (if the reader took a first data row for a
    header) are rows again."""
    rows = [{"row_idx": -1 - i, "cells": h.get("cells"), "bbox_pct": h.get("bbox_pct"),
             "cell_bboxes": h.get("cell_bboxes")} for i, h in enumerate(table.get("header_cells") or [])]
    return {**table, "rows": rows + list(table.get("rows") or [])}


def candidate_pages(pdf_bytes: bytes) -> list[int]:
    """Sheets whose text layer names a schedule or a table (cheap: the shared page-text cache)."""
    try:
        from .pdf_page_cache import page_texts
        texts = page_texts(pdf_bytes)
    except Exception:  # noqa: BLE001
        return []
    return [i + 1 for i, t in enumerate(texts) if CANDIDATE_RE.search(t or "")]


def read_schedules(pdf_bytes: bytes, pages: Iterable[int] | None = None, *, max_objects: int | None = None,
                   max_pages: int = MAX_PAGES) -> dict:
    """{versija, status: ok|nera|no_text, detail, lapai, praleisti: {page: detail}, lenteles: {"<page>": [table]},
    ziniarasciai: {kind: schedule | None}, sekundes}. `pages` None = the candidate sheets of the text layer.
    Never raises."""
    t0 = time.time()
    out = {"versija": SCHEDULES_VERSION, "status": "nera", "detail": None, "lapai": [], "praleisti": {},
           "lenteles": {}, "ziniarasciai": {k: None for k in KINDS}, "sekundes": 0.0}
    try:
        want = sorted({int(p) for p in (pages if pages is not None else candidate_pages(pdf_bytes)) if int(p) >= 1})
        if len(want) > max_pages:
            out["detail"] = f"lentelių ieškota {max_pages} lapuose iš {len(want)}, kuriuose minimos lentelės"
            want = want[:max_pages]
        read = read_pages_tables(pdf_bytes, want, max_objects=max_objects) if want else {}
        no_text = 0
        for page in want:
            res = read.get(page) or {}
            out["lapai"].append(page)
            if res.get("status") != "ok":
                out["praleisti"][str(page)] = res.get("detail") or res.get("status")
                no_text += res.get("status") == "no_text"
                continue
            tables = res.get("tables") or []
            if tables:
                out["lenteles"][str(page)] = tables
            for table in tables:
                kind, roles = classify_table(table)
                if kind is None:
                    # a continued table: no header of its own, the columns of a schedule already open
                    for k, sched in out["ziniarasciai"].items():
                        if sched is None or sched["cols"] != table.get("cols") or page <= max(sched["pages"]):
                            continue
                        cont = _as_continuation(table)
                        rows, totals = schedule_rows(cont, k, sched["_roles"])
                        if rows and _add(sched, rows, totals):
                            sched["pages"].append(page)
                            sched["table_ids"].append(table.get("table_id"))
                            sched["tesinys"] = True
                            table["schedule"] = k
                            break
                    continue
                table["schedule"] = kind
                rows, totals = schedule_rows(table, kind, roles)
                kinds = [kind]
                if kind in ("durys", "langai"):
                    other = "langai" if kind == "durys" else "durys"
                    other_rows, _ = schedule_rows(table, other, roles)
                    if other_rows:
                        kinds.append(other)                    # a table of doors AND windows feeds both
                for k in kinds:
                    k_rows = rows if k == kind else schedule_rows(table, k, roles)[0]
                    if not k_rows and k == kind and kind != "eksplikacija":
                        continue
                    sched = out["ziniarasciai"].get(k)
                    if sched is None:
                        sched = out["ziniarasciai"][k] = _schedule(k, table, roles)
                        _add(sched, k_rows, totals if k == kind else [])
                    elif _add(sched, k_rows, totals if k == kind else []):
                        if page not in sched["pages"]:
                            sched["pages"].append(page)
                        sched["table_ids"].append(table.get("table_id"))
                        sched["tesinys"] = sched["tesinys"] or page != sched["page"]
        for sched in out["ziniarasciai"].values():
            if sched is not None:
                sched["eilutes"] = len(sched["rows"])
                sched.pop("_roles", None)
        if any(out["ziniarasciai"].values()):
            out["status"] = "ok"
        elif want and no_text == len(want):
            out["status"] = "no_text"
            out["detail"] = out["detail"] or "brėžinio lapai be teksto sluoksnio — lentelių perskaityti negalima"
    except Exception as exc:  # noqa: BLE001 — a schedule we cannot read is no schedule, never a failed read
        log.warning("schedules read failed: %r", exc)
        out["status"] = "nera"
        out["detail"] = "lentelių perskaityti nepavyko"
    out["sekundes"] = round(time.time() - t0, 2)
    return out


# ── the records a project stores (api/free_reread.py, the „lentelės" stage) ──


def _lt(n: int, one: str, few: str, many: str) -> str:
    """„1 langas", „3 langai", „11 langų" (api/detect_run._lt, lib/ltPlural.js)."""
    last, last_two = n % 10, n % 100
    word = many if (10 <= last_two <= 19 or last == 0) else one if last == 1 else few
    return f"{n} {word}"


def _size(r: dict) -> str:
    return f"{r['plotis_mm']}×{r['aukstis_mm']}" if r.get("plotis_mm") and r.get("aukstis_mm") else ""


def _pages_word(pages: list[int]) -> str:
    return (f"{pages[0]} lapas" if len(pages) == 1 else "lapai " + ", ".join(str(p) for p in pages))


_ROW_KEYS = {
    "langai": ("kodas", "plotis_mm", "aukstis_mm", "tipas_tekstas", "kiekis", "pastaba", "page", "bbox_pct"),
    "apdaila": ("nr", "pavadinimas", "grindys", "sienos", "lubos", "grindjuostes", "grindu_danga", "page", "bbox_pct"),
}


def _no_table(res: dict, what: str) -> str:
    if res.get("status") == "no_text":
        return "Brėžinio lapuose nėra teksto sluoksnio — lentelių programa perskaityti negali."
    return f"{what} brėžinyje nerasta."


def windows_record(res: dict, pdf_bytes: bytes | None = None) -> dict:
    """`_langu_ziniarastis`: {status: lentele|nera, pages, lentele: {page, bbox_pct, pages, saltinis, eilutes:
    [{kodas, plotis_mm, aukstis_mm, tipas_tekstas, kiekis, kiekis_saltinis, pastaba, page, bbox_pct}]}, kiekis,
    sakinys}. A row without a count column is counted where its code stands on the drawing (door_schedule's
    rule); a code standing nowhere counts once."""
    sched = (res.get("ziniarasciai") or {}).get("langai")
    if not sched or not sched.get("rows"):
        return {"status": "nera", "pages": [], "lentele": None, "kiekis": 0,
                "sakinys": _no_table(res, "Langų žiniaraščio")}
    texts: list[str] = []
    if pdf_bytes is not None:
        try:
            from .pdf_page_cache import page_texts
            texts = [t or "" for t in page_texts(pdf_bytes)]
        except Exception:  # noqa: BLE001
            texts = []
    rows = []
    for r in sched["rows"]:
        row = {k: r.get(k) for k in _ROW_KEYS["langai"]}
        row["kiekis_saltinis"] = "lentele" if row.get("kiekis") is not None else "planas"
        if row.get("kiekis") is None:
            from .door_schedule import _count_on_plans
            row["kiekis"] = max(1, _count_on_plans(str(row["kodas"]), texts, int(row.get("page") or 0))) if texts else 1
        rows.append(row)
    total = sum(int(r.get("kiekis") or 0) for r in rows)
    parts = [" ".join(x for x in (r["kodas"], _size(r), f"×{r['kiekis']}") if x) for r in rows]
    sentence = (f"Langų žiniaraštyje ({_pages_word(sched['pages'])}): " + ", ".join(parts)
                + f" — iš viso {_lt(total, 'langas', 'langai', 'langų')}.")
    return {"status": "lentele", "pages": list(sched["pages"]),
            "lentele": {"page": sched["page"], "pages": list(sched["pages"]), "bbox_pct": sched.get("bbox_pct"),
                        "saltinis": "lentele", "pavadinimas": sched.get("title"), "eilutes": rows},
            "kiekis": total, "sakinys": sentence}


def finish_record(res: dict) -> dict:
    """`_apdailos_lentele`: {status: lentele|nera, pages, lentele: {page, bbox_pct, pages, saltinis, eilutes: [{nr,
    pavadinimas, grindys, sienos, lubos, grindjuostes, grindu_danga, page, bbox_pct}]}, sakinys}."""
    sched = (res.get("ziniarasciai") or {}).get("apdaila")
    if not sched or not sched.get("rows"):
        return {"status": "nera", "pages": [], "lentele": None, "sakinys": _no_table(res, "Apdailos lentelės")}
    rows = [{k: r.get(k) for k in _ROW_KEYS["apdaila"]} for r in sched["rows"]]
    said = [lt for key, lt in (("grindys", "grindys"), ("sienos", "sienos"), ("lubos", "lubos"),
                               ("grindjuostes", "grindjuostės")) if any(r.get(key) for r in rows)]
    sentence = (f"Apdailos lentelėje ({_pages_word(sched['pages'])}) — {_lt(len(rows), 'patalpa', 'patalpos', 'patalpų')}"
                + (": " + ", ".join(said) + "." if said else "."))
    return {"status": "lentele", "pages": list(sched["pages"]),
            "lentele": {"page": sched["page"], "pages": list(sched["pages"]), "bbox_pct": sched.get("bbox_pct"),
                        "saltinis": "lentele", "pavadinimas": sched.get("title"), "eilutes": rows},
            "sakinys": sentence}


def tables_meta(res: dict) -> dict:
    """`_meta.lenteles`: what the stage read — every table found (a summary: where it stands, its title and header,
    which schedule it is) and every schedule with its rows and boxes."""
    tables = {}
    for page, ts in (res.get("lenteles") or {}).items():
        tables[page] = [{"table_id": t.get("table_id"), "page": t.get("page"), "bbox_pct": t.get("bbox_pct"),
                         "title": t.get("title"), "header": t.get("header"), "cols": t.get("cols"),
                         "eilutes": len(t.get("rows") or []), "ziniarastis": t.get("schedule")} for t in ts]
    schedules = {}
    for kind, s in (res.get("ziniarasciai") or {}).items():
        if not s:
            continue
        schedules[kind] = {k: s.get(k) for k in ("kind", "title", "page", "pages", "table_ids", "bbox_pct", "columns",
                                                 "tesinys", "eilutes", "rows", "totals")}
    return {"versija": res.get("versija", SCHEDULES_VERSION), "status": res.get("status"), "detail": res.get("detail"),
            "lapai": list(res.get("lapai") or []), "praleisti": dict(res.get("praleisti") or {}),
            "lenteles": tables, "ziniarasciai": schedules, "sekundes": res.get("sekundes")}


# ── a room's row in a table (room facts, Patikra questions) ─────────────────


def _nr_key(v) -> str:
    return str(v or "").strip().upper()


def row_for_room(rows: list[dict], room: dict) -> dict | None:
    """The one table row that names this room: by its number (01 = 1), else by its name when the table gives
    no numbers. Two rows that both fit say nothing — None, never a guess."""
    from .universal_rules import fold_room_label
    nr = _nr_key(room.get("nr"))
    rows = [r for r in rows or [] if isinstance(r, dict)]
    if nr:
        hits = [r for r in rows if _nr_key(r.get("nr")) == nr]
        if not hits and nr.lstrip("0"):
            hits = [r for r in rows if _nr_key(r.get("nr")).lstrip("0") == nr.lstrip("0") and _nr_key(r.get("nr"))]
        if len(hits) == 1:
            return hits[0]
        if hits:
            return None
    name = fold_room_label(str(room.get("pavadinimas") or ""))
    if not name:
        return None
    hits = [r for r in rows if not _nr_key(r.get("nr")) and fold_room_label(str(r.get("pavadinimas") or "")) == name]
    return hits[0] if len(hits) == 1 else None


def finish_row_for(project: dict, room: dict) -> dict | None:
    """This room's row of the finish schedule (`_apdailos_lentele`), or None."""
    rec = project.get("_apdailos_lentele") if isinstance(project.get("_apdailos_lentele"), dict) else {}
    return row_for_room(((rec.get("lentele") or {}).get("eilutes") or []), room)


def room_table_row_for(project: dict, room: dict) -> dict | None:
    """This room's row of the room table as the „lentelės" stage read it (`_meta.lenteles`), or None."""
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    eks = ((meta.get("lenteles") or {}).get("ziniarasciai") or {}).get("eksplikacija") or {}
    return row_for_room(eks.get("rows") or [], room)


def finish_sentence(row: dict) -> str:
    """„Apdailos lentelėje (2 lapas): grindys — Keraminės plytelės; sienos — Dažomos; lubos — Dažomos."""
    parts = [f"{lt} — {row[key]}" for key, lt in (("grindys", "grindys"), ("sienos", "sienos"), ("lubos", "lubos"),
                                                    ("grindjuostes", "grindjuostės")) if row.get(key)]
    return f"Apdailos lentelėje ({row.get('page')} lapas): " + "; ".join(parts) + "."


__all__ = ["CANDIDATE_RE", "KINDS", "SCHEDULES_VERSION", "candidate_pages", "classify_table", "finish_record",
           "finish_row_for", "finish_sentence", "read_schedules", "room_table_row_for", "row_for_room",
           "schedule_rows", "tables_meta", "windows_record"]

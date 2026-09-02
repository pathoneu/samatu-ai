"""Kainynai (price lists) — xlsx import + durable per-user storage.

Task 5 of the 2026-09-02 contractor batch. Two jobs:

1. ``POST /api/price-lists/parse-xlsx`` — the contractor keeps his €/vnt list in
   Excel, not CSV. openpyxl reads the first sheet, finds the header row within
   the first few rows using the SAME column vocabulary as the frontend CSV
   parser (``pages/PriceLists.jsx``), and returns items in that parser's exact
   shape so both importers feed one storage format and one matcher.

2. CRUD for the lists themselves. They used to live only in localStorage, so a
   cleared browser or a second device lost hours of typing; the SQLite table is
   now the source of truth and the frontend store writes through to it.

Ownership: every route is auth-gated and owner-scoped exactly like the project
routes (admins may read across users; writes are always checked against the
row's owner, NULL-owner rows included — the 2026-06-19 write-barrier lesson).
"""

from __future__ import annotations

import io
import logging
import unicodedata
import uuid
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile

import auth as _auth
import db as _db

log = logging.getLogger("pathon.price_lists")

router = APIRouter(prefix="/api/price-lists", tags=["price-lists"])

# A kainynas is a few thousand short rows at the very most; 5 MB of xlsx is
# already an order of magnitude more than that and keeps a malicious upload from
# turning into an openpyxl memory bomb.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000
# Header row must appear near the top — a real kainynas has at most a title and
# a blank line above it.
HEADER_SCAN_ROWS = 5
MAX_ITEMS_PER_LIST = 50_000

# Same vocabulary as the CSV parser's `headerMap` in pages/PriceLists.jsx, keyed
# by the diacritics-folded, punctuation-stripped form so "Aprašymas", "APRASYMAS"
# and "Aprašymas:" all land on the same column.
_HEADER_MAP: dict[str, str] = {
    "skyrius": "skyrius",
    "kategorija": "skyrius",
    "aprasymas": "aprasymas",
    "pavadinimas": "aprasymas",
    "darbas": "aprasymas",
    "vnt": "mato_vnt",
    "matovnt": "mato_vnt",
    "matas": "mato_vnt",
    "matovienetas": "mato_vnt",
    "unit": "mato_vnt",
    "kaina": "kaina",
    "kainaeur": "kaina",
    "kainaeurvnt": "kaina",
    "ikaina": "kaina",
    "price": "kaina",
}


def _norm_header(value: Any) -> str:
    """Fold a header cell to its comparison key: lowercase, accents dropped,
    everything that is not a letter or digit removed."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value)).lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return "".join(ch for ch in s if ch.isalnum())


def _parse_price(value: Any) -> float | None:
    """Read a price cell. Excel gives a real number when the cell is numeric and
    a string when the contractor typed "12,50 €" — both must work, and the LT
    decimal comma is the common case."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if f == f and abs(f) != float("inf") else None
    s = str(value).strip()
    if not s:
        return None
    # "1 234,56 €" → "1234.56". Thin/non-breaking spaces are what Excel actually
    # emits for a thousands separator, so strip them explicitly.
    s = s.replace(" ", "").replace(" ", "").replace(" ", "")
    if "," in s and "." in s:
        # Both present: the LAST one is the decimal separator.
        s = s.replace(".", "") if s.rindex(",") > s.rindex(".") else s.replace(",", "")
    s = s.replace(",", ".")
    s = "".join(ch for ch in s if ch.isdigit() or ch in ".-")
    if not s or s in {"-", ".", "-."}:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f or abs(f) == float("inf"):
        return None
    return f


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_xlsx_items(data: bytes) -> dict[str, Any]:
    """Parse an xlsx workbook into the CSV parser's item shape.

    Returns ``{items, skipped_rows, header_row, sheet}``. Raises HTTPException
    with a Lithuanian message on anything the user has to fix themselves.
    """
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        log.error("openpyxl unavailable: %r", exc)
        raise HTTPException(status_code=500,
                            detail="Excel skaitytuvas neprieinamas serveryje") from exc

    try:
        # read_only + data_only: we want the CALCULATED values, never formulas,
        # and we never want the whole styled workbook in memory.
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - openpyxl raises a zoo of types
        log.info("xlsx parse failed: %r", exc)
        raise HTTPException(
            status_code=400,
            detail="Nepavyko nuskaityti „Excel“ failo. Įsitikinkite, kad tai "
                   ".xlsx failas (senas .xls formatas nepalaikomas — "
                   "išsaugokite kaip .xlsx).",
        ) from exc

    try:
        ws = wb.worksheets[0] if wb.worksheets else None
        if ws is None:
            raise HTTPException(status_code=400, detail="„Excel“ faile nėra lapų")
        # Read the title BEFORE the finally closes the read-only workbook —
        # afterwards the sheet object no longer has a live reader behind it.
        sheet_title = ws.title

        rows_iter = ws.iter_rows(values_only=True)
        head: list[tuple[Any, ...]] = []
        for row in rows_iter:
            head.append(row)
            if len(head) >= HEADER_SCAN_ROWS:
                break

        col_idx: dict[str, int] = {}
        header_row = -1
        for r, row in enumerate(head):
            candidate: dict[str, int] = {}
            for i, cell in enumerate(row or ()):
                mapped = _HEADER_MAP.get(_norm_header(cell))
                if mapped and mapped not in candidate:
                    candidate[mapped] = i
            if "aprasymas" in candidate and "kaina" in candidate:
                col_idx = candidate
                header_row = r
                break

        if header_row < 0:
            raise HTTPException(
                status_code=400,
                detail="Nerasta antraštės eilutė. Pirmose 5 eilutėse turi būti "
                       "stulpeliai: skyrius, aprašymas, vnt, kaina.",
            )

        items: list[dict[str, Any]] = []
        skipped = 0
        row_count = 0

        def _consume(row: tuple[Any, ...] | None) -> None:
            nonlocal skipped
            if not row or all(c is None or str(c).strip() == "" for c in row):
                return
            aprasymas = _cell_text(row[col_idx["aprasymas"]]
                                   if col_idx["aprasymas"] < len(row) else None)
            if not aprasymas:
                skipped += 1
                return
            kaina = _parse_price(row[col_idx["kaina"]]
                                 if col_idx["kaina"] < len(row) else None)
            if kaina is None:
                skipped += 1
                return
            sk_i = col_idx.get("skyrius")
            vnt_i = col_idx.get("mato_vnt")
            items.append({
                "skyrius": (_cell_text(row[sk_i]) if sk_i is not None and sk_i < len(row)
                            else "") or "Kiti darbai",
                "aprasymas": aprasymas[:400],
                "mato_vnt": (_cell_text(row[vnt_i])
                             if vnt_i is not None and vnt_i < len(row) else ""),
                "kaina": kaina,
            })

        for row in head[header_row + 1:]:
            row_count += 1
            _consume(row)
        for row in rows_iter:
            row_count += 1
            if row_count > MAX_ROWS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Per daug eilučių (daugiau nei {MAX_ROWS}). "
                           "Suskaidykite kainyną į kelis failus.")
            _consume(row)
    finally:
        try:
            wb.close()
        except Exception:  # noqa: BLE001 - close is best-effort
            pass

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Faile nerasta nė vienos tinkamos eilutės (reikia aprašymo "
                   "ir kainos).")

    return {
        "items": items,
        "skipped_rows": skipped,
        "header_row": header_row + 1,   # 1-based, as the user sees it in Excel
        "sheet": sheet_title,
    }


@router.post("/parse-xlsx")
async def api_parse_xlsx(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse an uploaded .xlsx kainynas. Stateless — the client decides whether
    to save the result, exactly like the CSV path does."""
    _auth.require_user(request)          # 401 when not logged in
    name = (file.filename or "").lower()
    if name.endswith(".xls"):
        raise HTTPException(
            status_code=400,
            detail="Senas .xls formatas nepalaikomas — „Excel“ programoje "
                   "pasirinkite „Įrašyti kaip“ → .xlsx.")
    try:
        data = await file.read()
    except Exception as exc:  # noqa: BLE001
        log.warning("price list upload read failed: %r", exc)
        raise HTTPException(status_code=400, detail="Nepavyko nuskaityti failo") from exc
    if not data:
        raise HTTPException(status_code=400, detail="Failas tuščias")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Failas per didelis (daugiau nei {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    # xlsx is a zip container; anything else fails openpyxl anyway, but saying so
    # up front beats a stack-trace-shaped error message.
    if not data[:2] == b"PK":
        raise HTTPException(
            status_code=400,
            detail="Netinkamas failo formatas — įkelkite .xlsx failą.")
    return parse_xlsx_items(data)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def _owner_filter(user: dict) -> str | None:
    """Admins read across users; everyone else is scoped to their own rows."""
    return None if user.get("is_admin") else user["id"]


@router.get("")
def api_list_price_lists(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    try:
        return {"price_lists": _db.list_price_lists(user_id=user["id"])}
    except Exception as exc:  # noqa: BLE001
        log.error("price list read failed for user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko nuskaityti kainynų") from exc


@router.put("/{price_list_id}")
def api_upsert_price_list(request: Request, price_list_id: str,
                          payload: dict = Body(...)) -> dict[str, Any]:
    user = _auth.require_user(request)
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Tuščias užklausos turinys")
    try:
        uuid.UUID(str(price_list_id))
    except ValueError:
        # Ids are generated with crypto.randomUUID() client-side; refusing
        # anything else keeps the primary key from becoming a free-text sink.
        raise HTTPException(status_code=400, detail="Netinkamas kainyno ID")
    items = payload.get("items")
    if items is not None and not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Laukas „items“ turi būti sąrašas")
    if isinstance(items, list) and len(items) > MAX_ITEMS_PER_LIST:
        raise HTTPException(
            status_code=413,
            detail=f"Kainyne per daug eilučių (daugiau nei {MAX_ITEMS_PER_LIST})")
    try:
        return _db.upsert_price_list(price_list_id, payload, user_id=user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("price list write failed id=%s user=%s: %r",
                  price_list_id, user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko išsaugoti kainyno") from exc


@router.delete("/{price_list_id}")
def api_delete_price_list(request: Request, price_list_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    try:
        deleted = _db.delete_price_list(price_list_id, user_id=_owner_filter(user))
    except Exception as exc:  # noqa: BLE001
        log.error("price list delete failed id=%s: %r", price_list_id, exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko ištrinti kainyno") from exc
    if not deleted:
        # 404 rather than 403 — never leak that someone else's list exists.
        raise HTTPException(status_code=404, detail="Kainynas nerastas")
    return {"deleted": price_list_id}

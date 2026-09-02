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
import zipfile
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

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

# ── Decompression budget (2026-09-02 review, F3) ─────────────────────────────
# The 5 MB upload cap bounds the ZIP, not what comes OUT of it. openpyxl does
# not stream xl/sharedStrings.xml — it decompresses the whole member — so a
# 647 KB workbook whose sharedStrings deflates to 580 MB returned HTTP 200 in
# 8.7 s having taken half a gigabyte of RSS with it. At the 5 MB cap that is
# ~4.5 GB, i.e. an OOM kill of the single uvicorn worker.
#
# The fix is to read the ZIP's CENTRAL DIRECTORY first (`infolist()` decompresses
# nothing) and refuse anything whose declared uncompressed sizes blow a budget.
# An under-declared size is not an escape hatch: CPython's zipfile truncates a
# member's output at the declared `file_size`, so the declaration is an upper
# bound on what can actually be read either way.
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
# A workbook is a couple of dozen parts; hundreds means someone is trying to
# make the *count* the bomb instead of the size.
MAX_ZIP_MEMBERS = 512

# Widest column we will look at. The header vocabulary lives in the first
# handful of columns, and without this openpyxl pads every row out to whatever
# `<dimension>` declares — a forged `A1:XFD1048576` turned a 4.8 KB upload into
# 4.8 s of CPU building 16384-wide tuples before the row cap fired.
MAX_COLS = 64
# Hard stop for the row iterator, one row past what we would accept anyway, so
# the 413 below still fires but openpyxl never walks a forged million-row sheet.
MAX_SCAN_ROWS = MAX_ROWS + HEADER_SCAN_ROWS + 1

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


def _rate_limit(request: Request, endpoint: str) -> None:
    """Key the shared sliding-window limiter by a NON-spoofable client key.

    Parsing a workbook is CPU work behind a login, so the size caps alone do not
    stop one account from looping it. The key comes from `main._client_key`, NOT
    `request.client.host`: production runs uvicorn with
    ``--forwarded-allow-ips='*'``, which makes `.host` the LEFTMOST
    X-Forwarded-For value — client-controlled, and rotating it walks straight
    past a per-IP bucket. `_client_key` takes the rightmost (trusted-proxy) hop.

    Imported lazily — main includes this router. Best-effort: a limiter hiccup
    must never block a legitimate upload.
    """
    try:
        from main import _check_rate_limit, _client_key
    except Exception:  # noqa: BLE001 - limiter unavailable in unit-test apps
        return
    _check_rate_limit(_client_key(request), f"price-lists-{endpoint}")


def _rate_limit_user(user: dict, endpoint: str) -> None:
    """Per-ACCOUNT bucket for the CRUD writes.

    An IP bucket is the wrong shape here: every write serialises against the
    process-global `_DB_LOCK` in db.py, and a loop of large-`items` PUTs from
    one logged-in account is a self-inflicted stall no matter which address it
    arrives from (and behind NAT an IP bucket punishes the office next door).
    Key on the user id — the one thing an authenticated caller cannot rotate.
    """
    try:
        from main import _check_rate_limit
    except Exception:  # noqa: BLE001 - limiter unavailable in unit-test apps
        return
    _check_rate_limit(f"user:{user.get('id') or 'unknown'}", f"price-lists-{endpoint}")


def _check_zip_budget(data: bytes) -> None:
    """Refuse a workbook whose members would decompress past the budget.

    Reads only the ZIP central directory — no member is decompressed — so this
    is microseconds regardless of how big the bomb claims to be. See the
    MAX_UNCOMPRESSED_BYTES note above for why the declared sizes are trustworthy
    as an upper bound.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except Exception as exc:  # noqa: BLE001 - BadZipFile and friends
        log.info("xlsx container unreadable: %r", exc)
        raise HTTPException(
            status_code=400,
            detail="Netinkamas failo formatas — įkelkite .xlsx failą.") from exc

    too_big = HTTPException(
        status_code=413,
        detail=(f"„Excel“ failas išskleistas užima per daug vietos (daugiau nei "
                f"{MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB). Palikite tik "
                "kainyno lapą ir įrašykite failą iš naujo."))
    if len(infos) > MAX_ZIP_MEMBERS:
        log.warning("xlsx rejected: %d zip members", len(infos))
        raise too_big
    total = 0
    for info in infos:
        size = int(getattr(info, "file_size", 0) or 0)
        if size > MAX_MEMBER_UNCOMPRESSED_BYTES:
            log.warning("xlsx rejected: member %r declares %d B", info.filename, size)
            raise too_big
        total += size
        if total > MAX_UNCOMPRESSED_BYTES:
            log.warning("xlsx rejected: members total %d B", total)
            raise too_big


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

    # BEFORE load_workbook: openpyxl reads sharedStrings whole, so the budget
    # has to be settled from the central directory first (F3).
    _check_zip_budget(data)

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

        # Explicit max_col/max_row: read-only openpyxl otherwise sizes every row
        # from the sheet's own `<dimension>`, which the uploader writes. See the
        # MAX_COLS note — a forged dimension is a CPU vector, not a hint.
        rows_iter = ws.iter_rows(values_only=True,
                                 max_col=MAX_COLS, max_row=MAX_SCAN_ROWS)
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
    _rate_limit(request, "parse-xlsx")
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
    # OFF the event loop. `parse_xlsx_items` is seconds of synchronous CPU on a
    # hostile workbook and railway.toml starts ONE uvicorn worker, so running it
    # here froze /health, every login and every in-flight /extract-interior
    # stream for the duration. (F3, 2026-09-02 review.)
    return await run_in_threadpool(parse_xlsx_items, data)


# ── CRUD ─────────────────────────────────────────────────────────────────────

# NOTE: unlike the project routes, admins get NO cross-user access here. The
# project routes grant it because the admin dashboard needs it; there is no
# admin view of price lists, so every verb below is scoped to the caller's own
# rows. Least privilege, and it keeps list/delete symmetric — an asymmetry there
# is exactly how an IDOR gets written by accident later.


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
        deleted = _db.delete_price_list(price_list_id, user_id=user["id"])
    except Exception as exc:  # noqa: BLE001
        log.error("price list delete failed id=%s: %r", price_list_id, exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko ištrinti kainyno") from exc
    if not deleted:
        # 404 rather than 403 — never leak that someone else's list exists.
        raise HTTPException(status_code=404, detail="Kainynas nerastas")
    return {"deleted": price_list_id}

"""Kainynai (price lists) — xlsx import + durable per-user storage.

Task 5 of the 2026-09-02 contractor batch. Two jobs:

1. ``POST /api/price-lists/parse-xlsx`` — the contractor keeps his €/vnt list in
   Excel, not CSV. openpyxl reads the first sheet, finds the header row within
   the first few rows using the SAME column vocabulary as the frontend CSV
   parser (``lib/priceListCsv.js``), and returns items in that parser's exact
   shape so both importers feed one storage format and one matcher.

2. CRUD for the lists themselves. They used to live only in localStorage, so a
   cleared browser or a second device lost hours of typing; the SQLite table is
   now the source of truth and the frontend store writes through to it.

Ownership: every route is auth-gated and scoped to the CALLER's own rows —
no cross-user read, admins included (see the CRUD note below). Writes are
checked against the row's owner, NULL-owner rows included — the 2026-06-19
write-barrier lesson.
"""

from __future__ import annotations

import io
import json
import logging
import re
import unicodedata
import uuid
import zipfile
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
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
HEADER_SCAN_ROWS = 20   # a contractor's sąmata carries a title block before its header (2026-09-15)
MAX_ITEMS_PER_LIST = 50_000
# Rows named back to the user for an unreadable price cell. The count of
# skipped rows stays exact; only the list of names is bounded.
MAX_PROBLEM_ROWS = 200

# Per-row bounds for a PUT. `aprasymas` matches what the importer already
# truncates to (see parse_xlsx_items); the rest are new — a PUT body is
# attacker-shaped in a way a spreadsheet cell is not.
_ITEM_STR_CAPS: dict[str, int] = {
    "skyrius": 200,
    "aprasymas": 400,
    "mato_vnt": 32,
}
MAX_ITEM_VALUE_LEN = 200      # any field we do not know by name
MAX_ITEM_KEY_LEN = 64
MAX_ITEM_KEYS = 16
MAX_NAME_LEN = 200            # db.upsert_price_list truncates `name` to this too
MAX_CREATED_DATE_LEN = 64     # an ISO-8601 timestamp, not a free-text column

# Ceiling for a PUT body. MAX_ITEMS_PER_LIST rows of the shape above serialise
# to roughly 150-200 B each, so a full-size legitimate kainynas lands near 10 MB
# and this leaves headroom without letting the endpoint buffer arbitrarily.
MAX_PUT_BODY_BYTES = 16 * 1024 * 1024

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

# Same vocabulary as the CSV parser's `HEADER_MAP` in lib/priceListCsv.js, keyed
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


# ── Bounded request bodies (2026-09-02 review, F6) ───────────────────────────
_UPLOAD_CHUNK = 256 * 1024
# A multipart part carries a boundary line plus two short headers around the
# file. 8 KB of slack keeps a file sitting exactly on the cap from being
# refused for its own wrapper.
_MULTIPART_SLACK = 8 * 1024

_TOO_LARGE_LT = ("Failas per didelis (daugiau nei "
                 f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")


async def _read_upload_capped(request: Request, file: UploadFile) -> bytes:
    """Read the uploaded part, refusing to buffer more than MAX_UPLOAD_BYTES.

    Same shape as `main._read_body_capped`: check the declared Content-Length
    first (cheap reject, don't even start), then bound the actual read, because
    the header can be absent on a chunked transfer or simply wrong. The previous
    `await file.read()` materialised the WHOLE part and only then measured it —
    the cap could not fire until the memory was already spent.
    """
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            if int(cl) > MAX_UPLOAD_BYTES + _MULTIPART_SLACK:
                raise HTTPException(status_code=413, detail=_TOO_LARGE_LT)
        except ValueError:
            pass  # malformed header — the stream-level guard below still holds

    chunks: list[bytes] = []
    total = 0
    while True:
        try:
            chunk = await file.read(_UPLOAD_CHUNK)
        except Exception as exc:  # noqa: BLE001
            log.warning("price list upload read failed: %r", exc)
            raise HTTPException(status_code=400,
                                detail="Nepavyko nuskaityti failo") from exc
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=_TOO_LARGE_LT)
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_json_body_capped(request: Request, cap: int) -> Any:
    """Bounded JSON body. `payload: dict = Body(...)` parsed the whole thing
    into a dict BEFORE any of our limits ran, so MAX_ITEMS_PER_LIST could only
    fire once the memory had been spent. Reuses main's streaming reader."""
    try:
        from main import _read_body_capped
    except Exception as exc:  # noqa: BLE001 - no safe uncapped fallback exists
        log.error("body reader unavailable: %r", exc)
        raise HTTPException(status_code=500,
                            detail="Serverio klaida — bandykite vėliau") from exc
    raw = await _read_body_capped(request, cap)
    if not raw:
        raise HTTPException(status_code=400, detail="Tuščias užklausos turinys")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400,
                            detail="Netinkamas užklausos turinys") from exc


def _sanitize_items(items: list[Any]) -> list[dict[str, Any]]:
    """Bound every value in a price-list row before it is serialised and stored.

    MAX_ITEMS_PER_LIST bounds the COUNT only — one row carrying a 15 MB
    `aprasymas` walks straight past it, gets json.dumps'd into SQLite under the
    process-global _DB_LOCK, and comes back out on every GET /api/price-lists.
    Bound the row the way the xlsx importer already bounds what it produces.

    Unknown keys are KEPT (capped): `applyPriceList.unitOf` still reads a legacy
    `vnt` alongside `mato_vnt`, so silently dropping what we do not recognise
    would quietly un-unit an old list. Nested values are refused — no importer
    has ever produced one, and unbounded nesting is the whole problem.
    """
    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise HTTPException(
                status_code=400,
                detail="Netinkama kainyno eilutė — laukiama „aprašymas“ ir "
                       "„kaina“ laukų.")
        if len(raw) > MAX_ITEM_KEYS:
            raise HTTPException(
                status_code=400,
                detail=f"Kainyno eilutėje per daug laukų (daugiau nei "
                       f"{MAX_ITEM_KEYS}).")
        item: dict[str, Any] = {}
        for key, value in raw.items():
            k = str(key)[:MAX_ITEM_KEY_LEN]
            if isinstance(value, str):
                item[k] = value[:_ITEM_STR_CAPS.get(k, MAX_ITEM_VALUE_LEN)]
            elif value is None or isinstance(value, bool):
                item[k] = value
            elif isinstance(value, (int, float)):
                f = float(value)
                # NaN/inf survive json.loads via Python's lenient parser and then
                # json.dumps writes them back as bare NaN/Infinity — invalid JSON
                # that no browser can read. Drop them to null.
                item[k] = value if f == f and abs(f) != float("inf") else None
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Netinkama kainyno eilutės reikšmė — laukiamas "
                           "tekstas arba skaičius.")
        out.append(item)
    return out


# Substring synonyms for headers that are not a bare word — a contractor's own
# sąmata reads „Darbų aprašymai", „Darbų kaina € be PVM", „Medžiagų kaina € be
# PVM" (a two-row header whose „vnt. / viso" sub-cells sit UNDER those). The
# exact map above stays first; these run when it finds nothing. Order matters:
# the material price is recognised before the plain „kaina" substring so it is
# never mistaken for the work price.
_HEADER_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("medziag", "medziagu_kaina"),     # „Medžiagų kaina" — kept as an extra field
    ("aprasym", "aprasymas"),
    ("pavadinim", "aprasymas"),
    ("matovnt", "mato_vnt"),
    ("matovien", "mato_vnt"),
    ("ikain", "kaina"),
    ("kaina", "kaina"),                 # „Darbų kaina € be PVM", „Vnt. kaina"
)


def _map_header(cell: Any) -> str | None:
    key = _norm_header(cell)
    if not key:
        return None
    mapped = _HEADER_MAP.get(key)
    if mapped:
        return mapped
    if "kiek" in key or "suma" in key or "viso" in key:
        return None                     # quantities and totals are never a price list column
    for needle, field in _HEADER_SUBSTRINGS:
        if needle in key:
            if field == "medziagu_kaina" and "kain" not in key:
                continue                # „Medžiagos" alone is a section, not a price column
            return field
    return None


def _norm_header(value: Any) -> str:
    """Fold a header cell to its comparison key: lowercase, accents dropped,
    everything that is not a letter or digit removed."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value)).lower()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return "".join(ch for ch in s if ch.isalnum())


# A typed price cell: the number FIRST, then at most a currency and a unit.
# 2026-09-30 (exports-money-3): the old reader kept every digit in the cell, so
# "15 €/m2" became 152, "8 €/m3" 83 and "12,50 €/m2" 12.502 — the unit's own
# digit glued onto the price. Now the leading number is read on its own and the
# rest must be a currency and/or a unit, or the row is refused and named.
_SPACES = "\u00a0\u202f\u2009 "      # NBSP, narrow NBSP (what Excel emits), thin, plain
_PRICE_NUMBER_RE = re.compile(rf"^[+-]?\d[\d.,{_SPACES}]*")
_PRICE_TAIL_RE = re.compile(
    r"^(?:(?:€|eur(?:ų|u|ai)?)\.?)?\s*"                  # €, EUR, Eur, eur., eurų
    r"(?:(?:/\s*|už\s+)?"                                # "/m2", "/ m", "už m3"
    r"(m²|m³|m2|m3|m|vnt|kompl|kg|t|l|val|h|d\.d)(\.?))?$",
    re.IGNORECASE,
)


def _read_number(text: str) -> float | None:
    """The leading number of a price cell, LT decimal comma first."""
    s = text.strip().rstrip(".," + _SPACES)
    for sp in _SPACES:
        s = s.replace(sp, " ")
    if " " in s:
        # A space is only ever a thousands separator: "1 234,56", never "15 2".
        if not re.fullmatch(r"[+-]?\d{1,3}(?: \d{3})+(?:[.,]\d+)?", s):
            return None
        s = s.replace(" ", "")
    if "," in s and "." in s:
        # Both present: the LAST one is the decimal separator.
        s = s.replace(".", "") if s.rindex(",") > s.rindex(".") else s.replace(",", "")
    s = s.replace(",", ".")
    try:
        f = float(s)
    except ValueError:
        return None
    if f != f or abs(f) == float("inf"):
        return None
    return f


def _read_price_cell(value: Any) -> tuple[float | None, str | None, str]:
    """Read a price cell → ``(price, unit_written_in_the_cell, status)``.

    ``status`` is ``"ok"``, ``"empty"`` (nothing typed) or ``"unreadable"``
    (something typed that is not a price — „sutartinė", a range, words after
    the number, a date). Excel gives a real number when the cell is numeric and
    a string when the contractor typed "12,50 €/m²" — both must work, and the
    LT decimal comma is the common case.
    """
    if value is None:
        return None, None, "empty"
    if isinstance(value, bool):
        return None, None, "unreadable"
    if isinstance(value, (int, float)):
        f = float(value)
        if f == f and abs(f) != float("inf"):
            return f, None, "ok"
        return None, None, "unreadable"
    s = str(value).strip()
    if not s:
        return None, None, "empty"
    m = _PRICE_NUMBER_RE.match(s)
    if not m:
        return None, None, "unreadable"
    tail = _PRICE_TAIL_RE.match(s[m.end():].strip())
    price = _read_number(m.group(0))
    if tail is None or price is None:
        return None, None, "unreadable"
    unit = (tail.group(1) + tail.group(2)) if tail.group(1) else None
    return price, unit, "ok"


def _parse_price(value: Any) -> float | None:
    """The price in a cell, or None when there is none or it is not readable."""
    return _read_price_cell(value)[0]


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_xlsx_items(data: bytes) -> dict[str, Any]:
    """Parse an xlsx workbook into the CSV parser's item shape.

    Returns ``{items, skipped_rows, problem_rows, header_row, sheet}``;
    ``problem_rows`` names each row skipped for an unreadable price cell
    (``{row, aprasymas, kaina}``, row 1-based as in Excel). Raises HTTPException
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
                mapped = _map_header(cell)
                if mapped and mapped not in candidate:
                    candidate[mapped] = i
            if "aprasymas" in candidate and "kaina" in candidate:
                col_idx = candidate
                header_row = r
                break
        # A two-row header („Darbų kaina" over „vnt. | viso"): the unit price
        # sits in the header's own column, the total one to the right — the
        # sub-row carries no new columns, so it is consumed as a data row and
        # skipped for lacking a price. Nothing to do here; noted for the reader.

        if header_row < 0:
            raise HTTPException(
                status_code=400,
                detail="Nerasta antraštės eilutė. Pirmose 5 eilutėse turi būti "
                       "stulpeliai: skyrius, aprašymas, vnt, kaina.",
            )

        items: list[dict[str, Any]] = []
        skipped = 0
        row_count = 0
        # Rows whose price cell holds something that is not a price. Skipped
        # like any priceless row, but NAMED, so the user can fix the cell
        # instead of wondering where the line went.
        problems: list[dict[str, Any]] = []
        # A sąmata names its sections on their own rows („Skyrius | Gipso
        # kartono montavimas", or just the name in the description column with
        # no price); they are carried onto the rows below instead of skipped.
        current_section = ""

        def _consume(row: tuple[Any, ...] | None, excel_row: int) -> None:
            nonlocal skipped, current_section
            if not row or all(c is None or str(c).strip() == "" for c in row):
                return
            cells = [_cell_text(c) for c in row]
            aprasymas = cells[col_idx["aprasymas"]] if col_idx["aprasymas"] < len(cells) else ""
            kaina_cell = row[col_idx["kaina"]] if col_idx["kaina"] < len(row) else None
            kaina, cell_unit, status = _read_price_cell(kaina_cell)
            sk_i = col_idx.get("skyrius")
            vnt_i = col_idx.get("mato_vnt")
            if kaina is None:
                texts = [c for c in cells if c]
                # „Skyrius | <name>" or a lone name: a section row
                if texts and (_norm_header(texts[0]) == "skyrius" and len(texts) >= 2):
                    current_section = texts[1][:200]
                elif aprasymas and len(texts) == 1:
                    current_section = aprasymas[:200]
                if status == "unreadable" and aprasymas and len(problems) < MAX_PROBLEM_ROWS:
                    problems.append({"row": excel_row, "aprasymas": aprasymas[:120],
                                     "kaina": _cell_text(kaina_cell)[:40]})
                skipped += 1
                return
            if not aprasymas:
                skipped += 1
                return
            section = (cells[sk_i] if sk_i is not None and sk_i < len(cells) else "") or current_section
            item = {
                "skyrius": section or "Kiti darbai",
                "aprasymas": aprasymas[:400],
                # The unit column first; a unit written in the price cell
                # („12,5 Eur/m²") fills it only when the column is empty.
                "mato_vnt": (cells[vnt_i] if vnt_i is not None and vnt_i < len(cells) else "")
                            or (cell_unit or ""),
                "kaina": kaina,
            }
            mk_i = col_idx.get("medziagu_kaina")
            if mk_i is not None and mk_i < len(row):
                mk = _parse_price(row[mk_i])
                if mk is not None and mk > 0:
                    item["medziagu_kaina"] = mk
            items.append(item)

        # `excel_row` is 1-based, as the user sees it in Excel.
        for row in head[header_row + 1:]:
            row_count += 1
            _consume(row, header_row + 1 + row_count)
        for row in rows_iter:
            row_count += 1
            if row_count > MAX_ROWS:
                raise HTTPException(
                    status_code=413,
                    detail=f"Per daug eilučių (daugiau nei {MAX_ROWS}). "
                           "Suskaidykite kainyną į kelis failus.")
            _consume(row, header_row + 1 + row_count)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - openpyxl raises a zoo of types
        # `load_workbook` above only parses the workbook SHELL. In read-only
        # mode the sheet is parsed lazily, during the iteration here, so a
        # truncated sheetData, a malformed <v>, or a shared-string index past
        # the end of the table all raise past the load and used to escape this
        # function as an unhandled 500. It is a bad file, not a broken server.
        log.info("xlsx sheet read failed: %r", exc)
        raise HTTPException(
            status_code=400,
            detail="„Excel“ failo turinio nepavyko perskaityti — failas gali "
                   "būti sugadintas. Atidarykite jį „Excel“ programoje ir "
                   "įrašykite iš naujo kaip .xlsx.",
        ) from exc
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
        "problem_rows": problems,
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
    data = await _read_upload_capped(request, file)
    if not data:
        raise HTTPException(status_code=400, detail="Failas tuščias")
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
    # A GET returns every item of every list the caller owns — a megabyte-scale
    # response served from SQLite, so it gets a bucket like the writes do.
    _rate_limit_user(user, "read")
    try:
        return {"price_lists": _db.list_price_lists(user_id=user["id"])}
    except Exception as exc:  # noqa: BLE001
        log.error("price list read failed for user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko nuskaityti kainynų") from exc


@router.put("/{price_list_id}")
async def api_upsert_price_list(request: Request,
                                price_list_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    try:
        uuid.UUID(str(price_list_id))
    except ValueError:
        # Ids are generated with crypto.randomUUID() client-side; refusing
        # anything else keeps the primary key from becoming a free-text sink.
        raise HTTPException(status_code=400, detail="Netinkamas kainyno ID")

    # Read + parse the body OURSELVES rather than through `payload: dict =
    # Body(...)`, which buffered and parsed every byte before a single limit of
    # ours could fire. (F6.)
    payload = await _read_json_body_capped(request, MAX_PUT_BODY_BYTES)
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Tuščias užklausos turinys")

    items = payload.get("items")
    if items is not None and not isinstance(items, list):
        raise HTTPException(status_code=400, detail="Laukas „items“ turi būti sąrašas")
    if isinstance(items, list):
        if len(items) > MAX_ITEMS_PER_LIST:
            raise HTTPException(
                status_code=413,
                detail=f"Kainyne per daug eilučių (daugiau nei {MAX_ITEMS_PER_LIST})")
        payload["items"] = _sanitize_items(items)

    # The scalar fields land in TEXT columns verbatim; bound them here so the
    # row cannot become a storage sink either.
    for field, cap in (("name", MAX_NAME_LEN),
                       ("company_name", MAX_NAME_LEN),
                       ("created_date", MAX_CREATED_DATE_LEN),
                       ("created_at", MAX_CREATED_DATE_LEN)):
        value = payload.get(field)
        if isinstance(value, str):
            payload[field] = value[:cap]
        elif value is not None and field in ("name", "company_name"):
            raise HTTPException(
                status_code=400,
                detail=f"Laukas „{field}“ turi būti tekstas")

    _rate_limit_user(user, "write")
    try:
        # SQLite write behind the process-global _DB_LOCK — off the event loop,
        # since this handler had to become async to read its own body.
        return await run_in_threadpool(
            _db.upsert_price_list, price_list_id, payload, user["id"])
    except PermissionError as exc:
        # 404, not 403: `str(exc)` used to leak db.py's English
        # "User X does not own price list Y", which both broke the LT-only rule
        # and answered "does this id exist?" for a stranger. DELETE already
        # 404s for exactly that reason — keep the pair symmetric. (F13b.)
        log.warning("price list write refused id=%s user=%s: %s",
                    price_list_id, user.get("id"), exc)
        raise HTTPException(status_code=404, detail="Kainynas nerastas") from exc
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
    _rate_limit_user(user, "write")
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

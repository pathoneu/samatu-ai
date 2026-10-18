"""How the Excel sąmata is grouped — Togal's Screen View / Full Export on Pathon's lines (togal-v2 W8,
docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md §8).

    skyriai       today's layout: skyrius → lines (the default; nothing here runs for it)
    patalpos      room → that room's share of each line, then „Nepriskirta patalpoms"
    seimos        the Kiekiai panel's tree: one group per line (its skyrius in the heading) → the rooms
    lapai         sheet → the shares of the rooms drawn on it, then „Be lapo"
    be_grupavimo  Togal's Full Export: one flat row per line × room, no headings, every attribute a column
    aukstai       floor → the shares of its rooms, then „Aukštas nenurodytas", then „Nepriskirta patalpoms"
    butai         apartment (a room's `butas`) → its rooms' shares, then „Butas nenurodytas", unassigned last

Rules this module keeps (and tests/test_export_grouping.py asserts):
  * Nothing is recomputed. A line's quantity is the server's `kiekis`; the rooms' shares are the server's
    `contributions[].value` (sent by the browser as `dalys`, already × the floor count). When the shares do
    not add up to the line (an anchor, a cap, a line no room produced) the difference is its own row,
    labelled — so every grouping's Σ kiekis per line equals the line, to the cent.
  * Money too: a line split into shares keeps its amount ROUND(kiekis × kaina, 2) — the shares' amounts are
    allocated by largest remainder and written as values (`_suma`), so the grouped workbook's total is the
    default layout's total exactly.
  * Every row says how it was obtained (`_kaip_gauta`): the program's reading with its confidence, or
    the person's own number. Pure: dicts in, dicts out.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

DEFAULT_GROUPING = "skyriai"
GROUPINGS = ("skyriai", "patalpos", "seimos", "lapai", "be_grupavimo", "aukstai", "butai")
GROUPING_LABELS = {
    "skyriai": "Skyrius",
    "patalpos": "Patalpas",
    "seimos": "Darbų šeimas",
    "lapai": "Lapus",
    "be_grupavimo": "Be grupavimo",
    "aukstai": "Aukštus",
    "butai": "Butus",
}

UNASSIGNED_ROOMS = "Nepriskirta patalpoms"
UNASSIGNED_SHEET = "Be lapo"
# aukstai / butai (v3 W7-A M5, 2026-10-18): a room is put on a floor only from
# what the project says — its own `aukstas`, or a room number that names the
# floor („2F-05", „II-12", „X.2"); a bare „05" names none, so it is not guessed.
# A room's `butas` (apartment) is used as written; nothing reads it off a
# drawing yet, so the dialog offers „Butus" only when some room carries one.
UNKNOWN_FLOOR = "Aukštas nenurodytas"
UNKNOWN_FLAT = "Butas nenurodytas"
REMAINDER_LABEL = "kiekio dalis, nepriskirta patalpai"
OVERSHOOT_LABEL = "patalpų dalių suma viršija eilutės kiekį — pataisa"

# What a row's number is, in the contractor's words (lib/confidence.js CONFIDENCE_LABELS).
_CONFIDENCE_WORDS = {
    "zalia": "skaityta tiesiogiai",
    "geltona": "patikrinti",
    "raudona": "būtina patikrinti",
}
_CONFIDENCE_ALIASES = {
    "high": "zalia", "green": "zalia", "zalia": "zalia", "žalia": "zalia",
    "medium": "geltona", "amber": "geltona", "yellow": "geltona", "geltona": "geltona",
    "low": "raudona", "red": "raudona", "raudona": "raudona",
}

_EPS = 0.005  # half a cent of a unit: below the 2-decimal print


def normalize_grouping(value: Any) -> str:
    """The grouping a request asked for; '' / None → the default. Unknown → ValueError (a 400)."""
    raw = str(value or "").strip().lower()
    if not raw:
        return DEFAULT_GROUPING
    if raw not in GROUPINGS:
        raise ValueError(f"Nežinomas grupavimas: {value}")
    return raw


def _num(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = float(str(value).replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError:
        return None
    return out if out == out and abs(out) != float("inf") else None


def _cents(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def kaip_gauta(line: dict) -> str:
    """„Programa — patikrinti" / „Pataisyta jūsų" / „Įvesta jūsų" — the provenance column."""
    origin = str(line.get("kilme") or "").strip()
    if origin == "jusu":
        return "Įvesta jūsų"
    if origin == "pataisyta":
        return "Pataisyta jūsų"
    tier = _CONFIDENCE_ALIASES.get(str(line.get("confidence") or "").strip().lower(), "geltona")
    if not str(line.get("confidence") or "").strip():
        tier = "zalia"  # unstamped legacy rows (lib/confidence.js normalizeConfidence)
    return f"Programa — {_CONFIDENCE_WORDS[tier]}"


def _parts(line: dict) -> list[dict]:
    out = []
    for d in line.get("dalys") or []:
        if not isinstance(d, dict):
            continue
        v = _num(d.get("value"))
        if v is None:
            continue
        page = d.get("page")
        try:
            page = int(page) if page not in (None, "") else None
        except (TypeError, ValueError):
            page = None
        out.append({
            "room_nr": str(d.get("room_nr") or "").strip(),
            "room_name": str(d.get("room_name") or "").strip(),
            "page": page,
            "value": v,
        })
    return out


def _split(line: dict) -> list[dict]:
    """The line as shares: one per room part, plus the remainder that makes Σ = kiekis.
    Each share: {room_nr, room_name, page, value, remainder: None|'under'|'over'}."""
    kiekis = _num(line.get("kiekis")) or 0.0
    parts = _parts(line)
    if not parts:
        return [{"room_nr": "", "room_name": "", "page": None, "value": kiekis, "remainder": "whole"}]
    shares = [{**p, "remainder": None} for p in parts]
    rest = kiekis - sum(p["value"] for p in parts)
    if abs(rest) >= _EPS:
        shares.append({"room_nr": "", "room_name": "", "page": None, "value": rest,
                       "remainder": "under" if rest > 0 else "over"})
    elif shares:
        shares[-1]["value"] += rest  # float dust: the last share closes the line exactly
    return shares


def _allocate_money(line: dict, shares: list[dict]) -> list[float | None]:
    """Each share's amount so that Σ = ROUND(kiekis × kaina, 2) exactly (largest remainder, in cents).
    None for a line without a usable price (the sheet writes its usual formula then)."""
    kaina = _num(line.get("kaina"))
    kiekis = _num(line.get("kiekis"))
    if kaina is None or kiekis is None:
        return [None] * len(shares)
    total = _cents(kiekis * kaina)
    if len(shares) == 1:
        return [float(total)]
    raw = [Decimal(str(s["value"])) * Decimal(str(kaina)) for s in shares]
    floor = [r.quantize(Decimal("0.01"), rounding="ROUND_FLOOR") for r in raw]
    left = int(((total - sum(floor)) * 100).to_integral_value())
    order = sorted(range(len(shares)), key=lambda i: (raw[i] - floor[i]), reverse=(left > 0))
    step = Decimal("0.01") if left > 0 else Decimal("-0.01")
    for k in range(abs(left)):
        floor[order[k % len(order)]] += step
    return [float(v) for v in floor]


def _room_label(nr: str, name: str) -> str:
    return " ".join(p for p in (nr, name) if p) or "Patalpa"


def _sheet_label(page: int | None, sheet_names: dict[int, str]) -> str:
    if page is None:
        return UNASSIGNED_SHEET
    name = sheet_names.get(page)
    return f"Lapas {page} — {name}" if name else f"Lapas {page}"


def _row(line: dict, share: dict, amount: float | None, *, group: str, description: str,
         sheet_names: dict[int, str], split: bool) -> dict:
    out = dict(line)
    out.pop("dalys", None)
    out["skyrius"] = group
    out["aprasymas"] = description
    out["kiekis"] = share["value"]
    if split and amount is not None:
        out["_suma"] = amount
    out["_kaip_gauta"] = kaip_gauta(line)
    out["_eilute"] = str(line.get("aprasymas") or "")
    out["_skyrius"] = str(line.get("skyrius") or "")
    out["_patalpa"] = _room_label(share["room_nr"], share["room_name"]) if share["room_nr"] or share["room_name"] else ""
    out["_lapas"] = _sheet_label(share["page"], sheet_names) if share["page"] is not None else ""
    out["_dalis"] = share["remainder"]
    return out


def _remainder_text(share: dict) -> str:
    return OVERSHOOT_LABEL if share["remainder"] == "over" else REMAINDER_LABEL


_BARE_NUMBER = re.compile(r"^\d{1,4}[a-zA-Z]?$")


def room_floor(room: dict | None) -> int | None:
    """The floor a room is on, when the project says so; None otherwise."""
    if not isinstance(room, dict):
        return None
    explicit = room.get("aukstas")
    if explicit is not None and not isinstance(explicit, bool):
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass
    nr = str(room.get("nr") or "").strip()
    if not nr or _BARE_NUMBER.fullmatch(nr):
        return None
    from extractor.universal_rules import room_aukstas_from_nr  # read-only use of the engine's rule
    return room_aukstas_from_nr(nr)


def floor_label(floor: int | None) -> str:
    if floor is None:
        return UNKNOWN_FLOOR
    return "Rūsys (0 aukštas)" if floor == 0 else f"{floor} aukštas"


def room_flat(room: dict | None) -> str | None:
    if not isinstance(room, dict):
        return None
    flat = str(room.get("butas") or "").strip()
    return flat[:40] or None


def has_flats(rooms: Iterable[dict] | None) -> bool:
    return any(room_flat(r) for r in rooms or [])


def group_export_lines(lines: Iterable[dict], grouping: str, *, rooms: Iterable[dict] | None = None,
                       sheets: Iterable[dict] | None = None) -> list[dict]:
    """The export rows in print order for `grouping` (see the module docstring).

    `lines`: what /generate-excel prints (`eilutes`, after renumbering), each optionally with `dalys`
    [{room_nr, room_name, page, value}] and `kilme`, `confidence`. `rooms`: plan order (patalpos).
    `sheets`: [{nr, pavadinimas}] (project.puslapiai) for sheet headings.

    Each output row is the line's dict with `skyrius` = the group heading (the sheet writer prints a
    heading whenever it changes — '' for no headings), `kiekis` = the share, and `_suma` (fixed amount)
    on split lines. For 'skyriai' the lines come back unchanged apart from `_kaip_gauta`.
    """
    mode = normalize_grouping(grouping)
    lines = [ln for ln in (lines or []) if isinstance(ln, dict)]
    sheet_names: dict[int, str] = {}
    for s in sheets or []:
        try:
            sheet_names[int(s.get("nr"))] = str(s.get("pavadinimas") or "").strip()
        except (TypeError, ValueError, AttributeError):
            continue

    if mode == "skyriai":
        return [{**{k: v for k, v in ln.items() if k != "dalys"}, "_kaip_gauta": kaip_gauta(ln)} for ln in lines]

    room_order = {}
    room_by_nr: dict[str, dict] = {}
    for i, r in enumerate(rooms or []):
        if isinstance(r, dict):
            room_order.setdefault(str(r.get("nr") or "").strip(), i)
            room_by_nr.setdefault(str(r.get("nr") or "").strip(), r)

    split_lines = []
    for ln in lines:
        shares = _split(ln)
        split_lines.append((ln, shares, _allocate_money(ln, shares)))

    def label(ln: dict) -> str:
        return str(ln.get("aprasymas") or "")

    if mode == "seimos":
        out = []
        for ln, shares, money in split_lines:
            section = str(ln.get("skyrius") or "").strip()
            group = f"{section} · {label(ln)}" if section else label(ln)
            for sh, amount in zip(shares, money):
                if sh["remainder"] == "whole":
                    desc = label(ln)
                elif sh["remainder"]:
                    desc = _remainder_text(sh)
                else:
                    desc = _room_label(sh["room_nr"], sh["room_name"])
                out.append(_row(ln, sh, amount, group=group, description=desc, sheet_names=sheet_names,
                                split=len(shares) > 1))
        return out

    if mode == "be_grupavimo":
        out = []
        for ln, shares, money in split_lines:
            for sh, amount in zip(shares, money):
                desc = label(ln) if not sh["remainder"] or sh["remainder"] == "whole" else f"{label(ln)} — {_remainder_text(sh)}"
                out.append(_row(ln, sh, amount, group="", description=desc, sheet_names=sheet_names,
                                split=len(shares) > 1))
        return out

    # patalpos / lapai / aukstai / butai: buckets in plan order, unassigned last
    buckets: dict[tuple, list[dict]] = {}
    for li, (ln, shares, money) in enumerate(split_lines):
        for sh, amount in zip(shares, money):
            assigned = not sh["remainder"]
            if mode in ("aukstai", "butai"):
                room = room_by_nr.get(sh["room_nr"]) if assigned else None
                if mode == "aukstai":
                    fl = room_floor(room) if assigned else None
                    known = fl is not None
                    key = (0, fl, "") if known else ((1, 0, "") if assigned else (2, 0, ""))
                    group = floor_label(fl) if assigned else UNASSIGNED_ROOMS
                else:
                    flat = room_flat(room) if assigned else None
                    known = flat is not None
                    key = ((0, int(flat) if flat.isdigit() else 10**6, flat) if known
                           else ((1, 0, "") if assigned else (2, 0, "")))
                    group = f"Butas {flat}" if known else (UNKNOWN_FLAT if assigned else UNASSIGNED_ROOMS)
                if sh["remainder"] in ("under", "over"):
                    desc = f"{label(ln)} — {_remainder_text(sh)}"
                elif assigned:
                    desc = f"{label(ln)} — {_room_label(sh['room_nr'], sh['room_name'])}"
                else:
                    desc = label(ln)
                buckets.setdefault(key, []).append(
                    (li, _row(ln, sh, amount, group=group, description=desc, sheet_names=sheet_names,
                              split=len(shares) > 1)))
                continue
            if mode == "patalpos":
                key = ((0, room_order.get(sh["room_nr"], len(room_order)), sh["room_nr"]) if assigned
                       else (1, 0, ""))
                group = _room_label(sh["room_nr"], sh["room_name"]) if assigned else UNASSIGNED_ROOMS
            else:
                key = (0, sh["page"], "") if assigned and sh["page"] is not None else (1, 0, "")
                group = _sheet_label(sh["page"], sheet_names) if key[0] == 0 else UNASSIGNED_SHEET
            if sh["remainder"] in ("under", "over"):
                desc = f"{label(ln)} — {_remainder_text(sh)}"
            elif mode == "lapai" and assigned:
                desc = f"{label(ln)} — {_room_label(sh['room_nr'], sh['room_name'])}"
            else:
                desc = label(ln)
            buckets.setdefault(key, []).append(
                (li, _row(ln, sh, amount, group=group, description=desc, sheet_names=sheet_names,
                          split=len(shares) > 1)))
    out = []
    for key in sorted(buckets, key=lambda k: (k[0], k[1] if k[1] is not None else -1, str(k[2]))):
        out.extend(row for _, row in sorted(buckets[key], key=lambda t: t[0]))
    return out


def totals_by_line(rows: Iterable[dict]) -> dict[str, float]:
    """Σ kiekis per source line number — the invariant every grouping keeps (tests)."""
    out: dict[str, float] = {}
    for r in rows:
        key = str(r.get("nr") or "")
        out[key] = out.get(key, 0.0) + (_num(r.get("kiekis")) or 0.0)
    return out


def preview(rows: list[dict], limit: int = 20) -> dict:
    """The first `limit` rows as the sheet will print them, headings included, for the export dialog."""
    out, last = [], None
    for r in rows:
        heading = str(r.get("skyrius") or "")
        if heading and heading != last:
            out.append({"kind": "heading", "label": heading})
        last = heading
        kiekis = _num(r.get("kiekis"))
        kaina = _num(r.get("kaina"))
        suma = r.get("_suma")
        if suma is None and kiekis is not None and kaina is not None:
            suma = float(_cents(kiekis * kaina))
        out.append({
            "kind": "row",
            "nr": str(r.get("nr") or ""),
            "aprasymas": str(r.get("aprasymas") or ""),
            "mato_vnt": str(r.get("mato_vnt") or ""),
            "kiekis": round(kiekis, 2) if kiekis is not None else None,
            "kaina": kaina,
            "suma": suma,
            "kaip_gauta": r.get("_kaip_gauta") or kaip_gauta(r),
            "programos": not str(r.get("_kaip_gauta") or "").endswith("jūsų"),
            "dalis": r.get("_dalis"),
        })
        if len([x for x in out if x["kind"] == "row"]) >= limit:
            break
    return {"rows": out, "row_count": len(rows),
            "groups": len({str(r.get("skyrius") or "") for r in rows if str(r.get("skyrius") or "")})}


# ── the sheet: extra columns beside /generate-excel's six ───────────────────────────────────────────────

SUBTOTAL_LABELS = {
    "patalpos": "Patalpos suma:",
    "seimos": "Eilutės suma:",
    "lapai": "Lapo suma:",
}
TITLE_SUFFIX = {
    "patalpos": "pagal patalpas",
    "seimos": "pagal darbų šeimas",
    "lapai": "pagal lapus",
    "be_grupavimo": "visos eilutės be grupavimo",
}


def _has_price_split(lines) -> bool:
    return any(isinstance(ln, dict) and (ln.get("kaina_darbo") is not None
                                         or ln.get("kaina_medziagu") is not None)
               for ln in (lines or []))


def extra_columns(grouping: str, internal_copy: bool = False, *, lines=None,
                  kodas: bool = False) -> list[tuple[str, str, int]]:
    """(header, row key, width) of the columns after „Suma €". For a grouped sheet: provenance always; the
    flat export also names the line's skyrius, room and sheet (so Excel's filter does the grouping); the
    assumption text only in his internal copy (it is his note, not the client's). In every layout, his
    internal copy also shows the darbo + medžiagų split of a price when any line carries one (togal-v2 W9,
    from a rinkinys or a kainynas material column) — the client's copy never does."""
    mode = normalize_grouping(grouping)
    cols: list[tuple[str, str, int]] = []
    if mode != DEFAULT_GROUPING:
        cols = [("Kaip gauta", "_kaip_gauta", 26)]
        if mode == "be_grupavimo":
            cols = [("Skyrius", "_skyrius", 26), ("Patalpa", "_patalpa", 22), ("Lapas", "_lapas", 26)] + cols
        if internal_copy:
            cols.append(("Prielaida", "prielaida", 50))
    if kodas:
        # „Kodas" (togal-v2 W9): his optional cost-code column, first after „Suma €", off by default.
        cols.insert(0, ("Kodas", "kodas", 11))
    if internal_copy and _has_price_split(lines):
        cols += [("Darbo kaina €", "kaina_darbo", 13), ("Medžiagų kaina €", "kaina_medziagu", 15)]
    return cols


def make_row_hook(ws, columns: list[tuple[str, str, int]], *, header_row: int, first_col: int, style):
    """Write the extra headers now and return `hook(ws, r, row)` for /generate-excel's row writer.
    `style(cell, header: bool)` applies the sheet's own look (passed in, so this module stays openpyxl-free
    apart from the column letters)."""
    from openpyxl.utils import get_column_letter

    from extractor.spreadsheet_safety import sanitize_spreadsheet_cell as _safe

    for i, (label, _key, width) in enumerate(columns):
        c = ws.cell(row=header_row, column=first_col + i, value=label)
        style(c, True)
        ws.column_dimensions[get_column_letter(first_col + i)].width = width

    def hook(sheet, r, row):
        for i, (_label, key, _w) in enumerate(columns):
            value = row.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                # Money stays a number his Excel can sum (the price split).
                c = sheet.cell(row=r, column=first_col + i, value=float(value))
                style(c, False)
                c.number_format = "#,##0.00"
                continue
            c = sheet.cell(row=r, column=first_col + i, value=_safe(str(value)) if value not in (None, "") else None)
            style(c, False)
    return hook

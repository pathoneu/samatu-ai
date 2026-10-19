"""Measurements on sąmata rows — the ledger contribution kind `matavimas` (Pathon v3 W4-A M1).

A length, a perimeter, an area or a whole count type the contractor measured in the viewer is attached to ONE
row of `darbu_sarasas` by the row's `id`, and says how (`kaip`): `kiekis` (the measured number is the row's
quantity, instead of the program's), `pridėti` (added to it) or `atimti` (taken away). The browser measures —
only it knows the sheets' scales — and sends each linked measurement in the recompute context as

    {"key": "m:<id>" | "type:<count type id>", "eilute_id": "<row id>", "kaip": "pridėti",
     "value": 4.2 | null, "unit": "m", "pages": [1], "pavadinimas"?: "Siena", "tekstas"?: "…"}

and `/recompute-interior` applies them to the rows it rebuilt, so its answer already carries them:

    row["kiekis"]            = the program's number ± the measurements, never below 0
    row["kiekis_programos"]  = the program's own number
    row["matavimai"]         = [{key, kaip, value, unit, pages, tekstas, taikoma, priezastis?}] — the ledger lines
                               („+ matavimas 4,20 m (lapas 1)"); `taikoma` false with the reason when a line is
                               listed but not counted (no scale on its sheet, another unit, a quantity he typed)
    row["roll_up"]          += one step per counted line, op "matavimas", value = the running result — so the
                               chain still ends on `kiekis` (extractor/ledger.py's rule; `replay` walks it)

This is ledger ASSEMBLY, not a formula: the builder's numbers are untouched, a measurement is what he measured
and never a default, and a row nobody linked comes back byte-identical. The browser's twin is
`frontend/src/lib/measuredRows.js` (`applyMeasuredRows`); `frontend/src/lib/measuredRows.cases.json` holds the
cases both run. Pure; no I/O.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

KAIP = ("kiekis", "pridėti", "atimti")
ROLL_UP_OP = "matavimas"
MAX_CONTRIBUTIONS = 500
MAX_TEXT = 200
MAX_PAGES = 50

_KIND_ORDER = {"kiekis": 0, "pridėti": 1, "atimti": 2}
_SIGN = {"kiekis": "", "pridėti": "+ ", "atimti": "− "}
_UNIT_FOLD = {"m2": "m²", "m²": "m²", "m3": "m³", "m³": "m³", "m": "m", "vnt": "vnt.", "vnt.": "vnt."}


def round2(v: float) -> float:
    """Half-up to the cent, the way the browser's Math.round does it (Python's round() is half-even)."""
    return math.floor(v * 100 + 0.5) / 100


def _num(v) -> float | None:
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _out_num(v: float):
    """A whole number as an int — the JSON the browser compares reads 40, not 40.0."""
    return int(v) if float(v).is_integer() else v


def fold_unit(unit) -> str:
    raw = str(unit if unit is not None else "").strip()
    return _UNIT_FOLD.get(raw.lower(), raw)


def unit_of_row(row: dict) -> str:
    return fold_unit(row.get("mato_vnt") or row.get("vnt"))


def lt_fixed(value: float, digits: int = 2) -> str:
    """„1 234,50" — LT decimal comma, a no-break space between thousands."""
    n = float(value)
    text = f"{abs(n):.{digits}f}"
    whole, _, frac = text.partition(".")
    grouped = re.sub(r"\B(?=(\d{3})+(?!\d))", " ", whole)
    return f"{'−' if n < 0 else ''}{grouped}{(',' + frac) if frac else ''}"


def _digits_for(unit) -> int:
    return 0 if fold_unit(unit) == "vnt." else 2


def _quantity_text(value: float, unit) -> str:
    return f"{lt_fixed(value, _digits_for(unit))} {fold_unit(unit)}"


def _pages_text(pages) -> str:
    items = [p for p in (pages or []) if _num(p) is not None]
    if not items:
        return ""
    return f" (lapas {items[0]})" if len(items) == 1 else f" (lapai {', '.join(str(p) for p in items)})"


def line_text(c: dict) -> str:
    """The ledger line: „+ matavimas „Siena“ 4,20 m (lapas 1)". A producer's own `tekstas` is used as given."""
    sign = _SIGN.get(c.get("kaip"), "")
    own = c.get("tekstas")
    if isinstance(own, str) and own.strip():
        return f"{sign}{own.strip()}"
    name = c.get("pavadinimas")
    name_text = f" „{name.strip()}“" if isinstance(name, str) and name.strip() else ""
    v = _num(c.get("value"))
    value = "be mastelio" if v is None else _quantity_text(v, c.get("unit"))
    return f"{sign}matavimas{name_text} {value}{_pages_text(c.get('pages'))}"


def _is_typed(row: dict) -> bool:
    return row.get("manual_override") is True or row.get("quantity_source") == "manual_override"


def _not_counted_because(c: dict, row_unit: str, typed: bool) -> str | None:
    if typed:
        return "Kiekį įrašėte ranka — matavimas į jį neįtrauktas."
    if _num(c.get("value")) is None:
        pages = c.get("pages") or []
        if pages:
            return f"{pages[0]} lape nenustatytas mastelis — nustatykite jį, ir matavimas bus įtrauktas."
        return "Lape nenustatytas mastelis — nustatykite jį, ir matavimas bus įtrauktas."
    if row_unit and fold_unit(c.get("unit")) != fold_unit(row_unit):
        return f"Eilutė skaičiuojama {row_unit}, o matavimas — {fold_unit(c.get('unit'))}: į kiekį neįtrauktas."
    return None


def _combine(base, lines: list[dict]) -> float:
    counted = [ln for ln in lines or [] if ln.get("taikoma") and _num(ln.get("value")) is not None]
    instead = [ln for ln in counted if ln.get("kaip") == "kiekis"]
    v = sum(_num(ln["value"]) for ln in instead) if instead else (_num(base) or 0.0)
    for ln in counted:
        if ln.get("kaip") == "pridėti":
            v += _num(ln["value"])
        elif ln.get("kaip") == "atimti":
            v -= _num(ln["value"])
    return round2(max(0.0, v))


def _program_number(row: dict) -> float | None:
    """The program's own number: `kiekis_programos` while `kiekis` is still what the stored lines made of it,
    else `kiekis` (a rebuild wrote a new number — the measurements ride on that)."""
    if isinstance(row.get("matavimai"), list) and "kiekis_programos" in row:
        expected = _combine(row.get("kiekis_programos"), row["matavimai"])
        if abs((_num(row.get("kiekis")) or 0.0) - expected) <= 0.005:
            return _num(row.get("kiekis_programos"))
    return _num(row.get("kiekis"))


def _stripped(roll_up):
    return [s for s in roll_up if not (isinstance(s, dict) and s.get("op") == ROLL_UP_OP)] \
        if isinstance(roll_up, list) else roll_up


def _sum_flag(row: dict, kiekis: float | None) -> bool:
    cs = row.get("contributions") if isinstance(row.get("contributions"), list) else []
    if not cs or kiekis is None:
        return False
    return abs(round2(sum((_num(c.get("value")) or 0.0) for c in cs if isinstance(c, dict))) - kiekis) <= 0.01


def _with_quantity(row: dict, kiekis: float) -> dict:
    out = {**row, "kiekis": _out_num(kiekis)}
    kaina = _num(row.get("kaina"))
    if kaina is not None:
        out["suma"] = _out_num(round2(kiekis * kaina))
    if isinstance(row.get("contributions_sum_to_total"), bool):
        out["contributions_sum_to_total"] = _sum_flag(row, kiekis)
    return out


def _released(row: dict) -> dict:
    base = {k: v for k, v in row.items() if k not in ("matavimai", "kiekis_programos")}
    if "roll_up" in row:
        base["roll_up"] = _stripped(row["roll_up"])
    if _is_typed(row):
        return base
    return _with_quantity(base, _program_number(row) or 0.0)


def _applied(row: dict, contributions: list[dict]) -> dict:
    row_unit = unit_of_row(row)
    typed = _is_typed(row)
    ordered = [c for _, c in sorted(enumerate(contributions),
                                    key=lambda ic: (_KIND_ORDER.get(ic[1].get("kaip"), 9), ic[0]))]
    lines = []
    for c in ordered:
        why = _not_counted_because(c, row_unit, typed)
        v = _num(c.get("value"))
        line = {"key": c.get("key"), "kaip": c.get("kaip"), "value": None if v is None else _out_num(v),
                "unit": fold_unit(c.get("unit")), "pages": list(c.get("pages") or []),
                "tekstas": line_text(c), "taikoma": why is None}
        if why:
            line["priezastis"] = why
        lines.append(line)
    chain = _stripped(row.get("roll_up"))
    if typed:
        out = {k: v for k, v in row.items() if k != "kiekis_programos"}
        out["matavimai"] = lines
        if "roll_up" in row:
            out["roll_up"] = chain
        return out
    base = _program_number(row)
    kiekis = _combine(base, lines)
    out = _with_quantity({**row, "kiekis_programos": None if base is None else _out_num(base),
                          "matavimai": lines}, kiekis)
    if isinstance(chain, list) and chain:
        steps = list(chain)
        running = base or 0.0
        instead_started = False
        unit = row_unit or ""
        for ln in (x for x in lines if x["taikoma"]):
            value = float(ln["value"])
            if ln["kaip"] == "kiekis":
                running = running + value if instead_started else value
                note = (f"+{lt_fixed(value, _digits_for(unit))} {unit}".strip() if instead_started
                        else f"vietoj programos kiekio {_quantity_text(base or 0.0, unit)}".strip())
                instead_started = True
            elif ln["kaip"] == "pridėti":
                running += value
                note = f"+{lt_fixed(value, _digits_for(ln['unit']))} {ln['unit']}"
            else:
                running -= value
                note = f"−{lt_fixed(value, _digits_for(ln['unit']))} {ln['unit']}"
            steps.append({"op": ROLL_UP_OP, "label": ln["tekstas"], "value": _out_num(round2(running)),
                          "note": note})
        if len(steps) > len(chain):
            steps[-1] = {**steps[-1], "value": _out_num(kiekis)}
        out["roll_up"] = steps
    elif "roll_up" in row:
        out["roll_up"] = chain
    return out


def _same(a: dict, b: dict) -> bool:
    return json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) == \
        json.dumps(b, sort_keys=True, ensure_ascii=False, default=str)


def apply_measured_rows(rows: list, contributions: list) -> list:
    """Rows with the measurements applied. Pure and idempotent: a row nothing touches is the same object, and a
    row that carried measurements and has none now gets the program's number back."""
    if not isinstance(rows, list):
        return rows
    by_row: dict[str, list[dict]] = {}
    for c in contributions or []:
        if not isinstance(c, dict) or not c.get("eilute_id") or c.get("kaip") not in KAIP:
            continue
        by_row.setdefault(str(c["eilute_id"]), []).append(c)
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        mine = by_row.get(str(row["id"])) if row.get("id") is not None else None
        nxt = row
        if mine:
            nxt = _applied(row, mine)
        elif isinstance(row.get("matavimai"), list):
            nxt = _released(row)
        out.append(row if nxt is not row and _same(nxt, row) else nxt)
    return out


def clean_contributions(raw) -> list[dict]:
    """The request's list, bounded and typed: anything that is not a well-formed contribution is dropped, text
    is cut to a sane length, a value must be a finite number ≥ 0 (or null — listed, not counted)."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for c in raw[:MAX_CONTRIBUTIONS]:
        if not isinstance(c, dict):
            continue
        eilute_id = c.get("eilute_id")
        kaip = c.get("kaip")
        if not isinstance(eilute_id, str) or not eilute_id.strip() or kaip not in KAIP:
            continue
        v = _num(c.get("value"))
        if v is not None and v < 0:
            continue
        pages = [int(p) for p in (c.get("pages") or [])[:MAX_PAGES]
                 if _num(p) is not None and float(p).is_integer() and int(p) >= 1] \
            if isinstance(c.get("pages"), list) else []
        item: dict[str, Any] = {
            "key": str(c.get("key") or "")[:MAX_TEXT],
            "eilute_id": eilute_id.strip()[:MAX_TEXT],
            "kaip": kaip,
            "value": v,
            "unit": str(c.get("unit") or "")[:16],
            "pages": pages,
        }
        for k in ("pavadinimas", "tekstas"):
            if isinstance(c.get(k), str) and c[k].strip():
                item[k] = c[k].strip()[:MAX_TEXT]
        out.append(item)
    return out

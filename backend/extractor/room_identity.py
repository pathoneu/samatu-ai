"""Room identity comes from the drawing, never from the model (Pathon v4, Phase 3a — 2026-10-25).

The room TABLE the drawing prints (its text layer: `pdfplumber_eksplikacija`, including several units' stacked
tables, `stacked_unit_rooms`) numbers the rooms. When it returns rows, those rows ARE the room list: number as
drawn (`<unit>-<nr>` when the sheet holds several units), name, area, `_vienetas`, `_nr_brezinyje`. The reading
model's rooms may only supply what the table does not say — a name where the row has none, and the readings that
live on a room (openings, heights, finishes, its box on the plan) — and may never invent a key. A model room that
matches no row by number or by name is dropped, with a note the screen shows.

Why (contractor's project objektas_i, 2026-10-24): the model numbered the rooms K1…K8 / D1…D9 while the drawing
numbers them 1–8 and 1–9 in two units. Joining the table INTO the model's rooms kept the invented keys, the unit
never reached the geometry lane, and the badge „3" could not tell which unit it stood in: 14 of 17 rooms placed in
the app against 17 of 17 by the cold runner.

How a model room finds its row — passes in this order, each pairing only when the pair is unique both ways among
the rooms and rows still free (two twins with one area stay unpaired rather than swapped):
  1. the same number, unless the two names flatly contradict each other (the old join's row guard);
  2. the same name (case, accents, punctuation and a bracketed remark ignored — „Koridorius (kairysis korpusas)"
     is „Koridorius") and the same area within 0,005 m²;
  3. names that agree (`eksplikacija_guard.names_agree`: a shared word, the wet-room family) and the same area
     within 0,005 m²;
  4. the same name and an area within AREA_NEAR (2 %);
  5. the same name, one candidate each way (the old join's name fallback).

A table whose rows matched fewer than half of the model's rooms is not taken as the room list (`identity_from_table`
answers None): a bundled drawing's other building, or a table the reader misparsed, must not replace the rooms.
The caller then keeps the old join.

Where no text-layer table exists the model's list stands — no source in the drawing names the rooms — and every
room carries `_pavadinimas_saltinis = "modelis"` so the sheet can say its name and number are the model's reading.

Pure: no I/O, no model, no PDF. Used by `vision_call.extract_interior` (Step 2.4), by the free re-read
(`api/free_reread.py`, re-keying a stored project) and by the cold runner (`scripts/cold_run/run_cold.py`).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence

from .eksplikacija_guard import names_agree, row_contradicts

TEXT_LAYER_SOURCES = frozenset({"pdfplumber_table", "ocr_table"})   # the drawing's own table — not a model reading
AREA_SAME_M2 = 0.005             # two areas printed from one table cell
AREA_NEAR = 0.02                 # …or one rounding apart (2 %)
MIN_MATCHED_SHARE = 0.5          # rows must find at least this share of the model's rooms to be the room list
MODEL = "modelis"                # `_pavadinimas_saltinis` when the name / number is the model's reading
NOT_IN_TABLE_CODE = "room_not_in_table"

# What the table decides on a room (the identity); everything else on a matched model room stays its reading.
IDENTITY_KEYS = ("nr", "_vienetas", "_nr_brezinyje")


def is_text_layer_table(eks: dict | None) -> bool:
    """True when the room table came from the drawing's text (or, flag on, local OCR of the sheet) — not from the
    model's eksplikacija reader."""
    if not isinstance(eks, dict) or not eks.get("patalpos"):
        return False
    return str((eks.get("_meta") or {}).get("source") or "") in TEXT_LAYER_SOURCES


def core_name(s: str | None) -> str:
    """The name for comparison: lower case, no accents, no bracketed remark, letters and digits only."""
    s = re.sub(r"\([^)]*\)", " ", str(s or ""))
    s = unicodedata.normalize("NFKD", s.strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def _area(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _area_within(a, b, *, abs_tol: float = 0.0, rel_tol: float = 0.0) -> bool:
    fa, fb = _area(a), _area(b)
    if fa is None or fb is None:
        return False
    return abs(fa - fb) <= max(abs_tol, rel_tol * max(fa, fb)) + 1e-9


def _nr(v) -> str:
    return str(v if v is not None else "").strip()


def _p_number(room: dict, row: dict) -> bool:
    return bool(_nr(room.get("nr"))) and _nr(room.get("nr")) == _nr(row.get("nr")) and not row_contradicts(room, row)


def _p_name_same_area(room: dict, row: dict) -> bool:
    c = core_name(row.get("pavadinimas"))
    return bool(c) and c == core_name(room.get("pavadinimas")) and _area_within(room.get("plotas_m2"), row.get("plotas_m2"), abs_tol=AREA_SAME_M2)


def _p_agree_same_area(room: dict, row: dict) -> bool:
    return names_agree(room.get("pavadinimas"), row.get("pavadinimas")) and _area_within(
        room.get("plotas_m2"), row.get("plotas_m2"), abs_tol=AREA_SAME_M2)


def _p_name_near_area(room: dict, row: dict) -> bool:
    c = core_name(row.get("pavadinimas"))
    return bool(c) and c == core_name(room.get("pavadinimas")) and _area_within(room.get("plotas_m2"), row.get("plotas_m2"), rel_tol=AREA_NEAR)


def _p_name(room: dict, row: dict) -> bool:
    c = core_name(row.get("pavadinimas"))
    return bool(c) and c == core_name(room.get("pavadinimas"))


PASSES = (("nr", _p_number), ("pavadinimas_plotas", _p_name_same_area), ("pavadinimas_plotas", _p_agree_same_area),
          ("pavadinimas_plotas", _p_name_near_area), ("pavadinimas", _p_name))


def match_rooms_to_rows(rooms: Sequence[dict], rows: Sequence[dict]) -> dict[int, tuple[int, str]]:
    """{row index: (room index, how)} — every pair unique both ways within its pass (see the module text)."""
    free_rooms = set(range(len(rooms)))
    free_rows = set(range(len(rows)))
    out: dict[int, tuple[int, str]] = {}
    for how, pred in PASSES:
        changed = True
        while changed:
            changed = False
            cand_rooms = {j: [i for i in sorted(free_rooms) if pred(rooms[i], rows[j])] for j in sorted(free_rows)}
            for j, cands in cand_rooms.items():
                if len(cands) != 1:
                    continue
                i = cands[0]
                if i not in free_rooms or j not in free_rows:
                    continue
                back = [jj for jj in free_rows if pred(rooms[i], rows[jj])]
                if back != [j]:
                    continue
                out[j] = (i, how)
                free_rooms.discard(i)
                free_rows.discard(j)
                changed = True
    return out


def _plan_page(rooms: Iterable[dict]) -> int | None:
    pages: dict[int, int] = {}
    for r in rooms:
        try:
            p = int(r.get("puslapio_nr"))
        except (TypeError, ValueError):
            continue
        pages[p] = pages.get(p, 0) + 1
    return max(pages, key=lambda p: (pages[p], -p)) if pages else None


def room_from_row(row: dict, model_room: dict | None, how: str | None, plan_page: int | None) -> dict:
    """One room of the list: the table's identity, name and area on the matched model room's readings (a copy)."""
    room = dict(model_room) if model_room else {}
    model_nr = _nr(model_room.get("nr")) if model_room else ""
    room["nr"] = _nr(row.get("nr"))
    for k in ("_vienetas", "_nr_brezinyje"):
        if row.get(k) is not None:
            room[k] = row[k]
    if row.get("pavadinimas"):
        # a room joined by its number keeps the name it was read with (the old join never touched it); one
        # joined by name and area, or a row alone, takes the table's
        if not (how == "nr" and room.get("pavadinimas")):
            room["pavadinimas"] = row["pavadinimas"]
    elif model_room and model_room.get("pavadinimas"):
        room["_pavadinimas_saltinis"] = MODEL
    if model_room is None:
        room["_tik_lenteleje"] = True
        if plan_page is not None:
            room.setdefault("puslapio_nr", plan_page)
    if model_nr and model_nr != room["nr"]:
        room["_modelio_nr"] = model_nr
    if how:
        room["plotas_match"] = how
    return room


def identity_from_table(model_rooms: Sequence[dict], eks: dict | None) -> dict | None:
    """The room list from a text-layer table, or None when there is no such table or it does not belong to these
    rooms. Returns {"rooms": [...], "pairs": [(row, room|None, how|None)], "dropped": [model rooms], "matched": n,
    "renamed": {model nr: drawn nr}}. The rooms carry identity + name only; the area, perimeter and evidence stamps
    are the caller's join (vision_call keeps its own statement-for-statement)."""
    if not is_text_layer_table(eks):
        return None
    rows = [r for r in eks.get("patalpos") or [] if isinstance(r, dict) and _nr(r.get("nr"))]
    if not rows:
        return None
    rooms = [r for r in model_rooms or [] if isinstance(r, dict)]
    pairs = match_rooms_to_rows(rooms, rows)
    if rooms and len(pairs) < MIN_MATCHED_SHARE * len(rooms):
        return None
    page = _plan_page(rooms)
    out_rooms, out_pairs, renamed = [], [], {}
    for j, row in enumerate(rows):
        i, how = pairs.get(j, (None, None))
        m = rooms[i] if i is not None else None
        out_rooms.append(room_from_row(row, m, how, page))
        out_pairs.append((row, m, how))
        if m is not None and _nr(m.get("nr")) and _nr(m.get("nr")) != _nr(row.get("nr")):
            renamed[_nr(m.get("nr"))] = _nr(row.get("nr"))
    used = {i for i, _h in pairs.values()}
    dropped = [r for k, r in enumerate(rooms) if k not in used]
    return {"rooms": out_rooms, "pairs": out_pairs, "dropped": dropped, "matched": len(pairs), "renamed": renamed}


def stamp_row_evidence(room: dict, eks_row: dict, eks: dict | None) -> None:
    """The table row's own provenance on the room joined to it (row index, its box and page size — pdfplumber
    only — and the page the row was read on). The body of `vision_call._stamp_eksplikacija_evidence`, moved here
    2026-10-25 so the cold runner joins exactly as the paid reading does."""
    room["eksplikacija_row_idx"] = eks_row.get("row_idx")
    for key in ("eksplikacija_row_bbox", "eksplikacija_page_width_pdf", "eksplikacija_page_height_pdf"):
        if eks_row.get(key):
            room[key] = eks_row[key]
    page = eks_row.get("page") or (eks or {}).get("eksplikacija_source_page")
    if page:
        room["eksplikacija_source_page"] = page


def join_rows(ident: dict, eks: dict | None) -> int:
    """Each room of `identity_from_table`'s list takes its row's area and perimeter (a table figure) and the row's
    evidence — the paid reading's eksplikacija join, statement for statement. Returns the rooms joined."""
    n = 0
    for room, (row, _m, _how) in zip(ident["rooms"], ident["pairs"]):
        if row.get("plotas_m2"):
            room["plotas_m2"] = row["plotas_m2"]
            room["plotas_saltinis"] = "eksplikacija"
        if row.get("perimetras_m"):
            room["perimetras_m"] = row["perimetras_m"]
            room["perimetras_saltinis"] = "eksplikacija"     # a table figure — the dimension lane must not touch it
        stamp_row_evidence(room, row, eks)
        n += 1
    return n


def dropped_room_warning(room: dict) -> dict:
    """The note for a model room no table row confirms — what to check, in his words."""
    from .universal_rules import lt_num
    name = str(room.get("pavadinimas") or "").strip() or "be pavadinimo"
    area = _area(room.get("plotas_m2"))
    size = f" ({lt_num(area, 2)} m²)" if area else ""
    return {
        "level": "WARN",
        "code": NOT_IN_TABLE_CODE,
        "message": (f"Patalpa „{name}“{size} nerasta brėžinio patalpų lentelėje, todėl į sąrašą neįtraukta. "
                    "Jei tokia patalpa yra, pridėkite ją Patikros žingsnyje."),
    }


def mark_model_list(rooms: Iterable[dict]) -> int:
    """No table in the drawing: the model's list stands, and every room says so. Returns how many it marked."""
    n = 0
    for r in rooms:
        if isinstance(r, dict):
            r["_pavadinimas_saltinis"] = MODEL
            n += 1
    return n


def rekey_stored_rooms(stored: Sequence[dict], eks: dict | None) -> dict | None:
    """The free re-read's re-keying of a STORED project (api/free_reread.py): the stored rooms matched to the
    text-layer table, each matched room's number rewritten to the drawn one (with `_vienetas`, `_nr_brezinyje`,
    `_modelio_nr`) — nothing else on it changes, no room is added or dropped (his list is his). None when there is
    no table, it does not belong to these rooms, or every number already is the drawn one. Returns
    {"rooms": [copies], "map": {old: new}, "unmatched": [old nr]}."""
    res = identity_from_table(stored, eks)
    if res is None or not res["renamed"]:
        return None
    by_id = {id(m): row for row, m, _h in res["pairs"] if m is not None}
    rooms, mapping, unmatched = [], {}, []
    taken = {_nr(row.get("nr")) for row in by_id.values()}
    for r in stored:
        if not isinstance(r, dict):
            rooms.append(r)
            continue
        row = by_id.get(id(r))
        if row is None:
            unmatched.append(_nr(r.get("nr")))
            if _nr(r.get("nr")) in taken:            # an unmatched room already wearing a drawn number: never twice
                return None
            rooms.append(r)
            continue
        new = dict(r)
        old, drawn = _nr(r.get("nr")), _nr(row.get("nr"))
        new["nr"] = drawn
        for k in ("_vienetas", "_nr_brezinyje"):
            if row.get(k) is not None:
                new[k] = row[k]
        if old != drawn:
            new["_modelio_nr"] = old
            mapping[old] = drawn
        rooms.append(new)
    return {"rooms": rooms, "map": mapping, "unmatched": unmatched}

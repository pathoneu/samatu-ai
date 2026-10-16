"""What the estimator SELECTED, as a block for the project chat (togal-v2 W11, Togal capability J).

The chat already gets the whole project (main._build_chat_context, cached). This adds the rooms and rows he
picked as pills — built from what the program read, nothing new: each room's check-sheet facts with their
„iš kur" sentences (extractor/room_facts.build_room_facts, read only) and each row's own ledger
(`contributions / excluded / roll_up`). The block goes into the LAST user turn, after the cached context, so
the two cache breakpoints hold and a new selection never re-sends the project.

`given` says exactly what the model was handed (and what was left out over the caps), so the panel can show
the pills it really sent.
"""
from __future__ import annotations

import logging
from typing import Any

from extractor.room_facts import build_room_facts

log = logging.getLogger("samatu.chat_selection")

MAX_ROOMS = 12
MAX_ROWS = 30
_MAX_ID = 64

_STATUS = {"read": "perskaityta", "assumed": "prielaida", "missing": "nėra duomenų"}
_FACT_NAMES = {"plotas": "plotas", "perimetras": "perimetras", "aukstis": "lubų aukštis", "apdaila": "apdaila",
               "angos": "angos", "grindys": "grindys"}


def _n(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value) if value not in (None, "") else "—"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.2f}".replace(".", ",")


def _ids(raw: Any) -> list[str]:
    """Strings, trimmed, de-duplicated in order; anything else dropped."""
    out: list[str] = []
    for v in raw if isinstance(raw, list) else []:
        if isinstance(v, (str, int)) and not isinstance(v, bool):
            s = str(v).strip()[:_MAX_ID]
            if s and s not in out:
                out.append(s)
    return out


def _rows(project: dict) -> list[dict]:
    return [r for r in (project.get("darbu_sarasas") or project.get("pozicijos") or []) if isinstance(r, dict)]


def _row_ids(row: dict) -> list[str]:
    return [str(k) for k in (row.get("id"), row.get("_id"), f"{row.get('eil_nr', '')}-{row.get('aprasymas', '')}") if k]


def _unit(u: Any) -> str:
    return {"m2": "m²", "m3": "m³"}.get(str(u or ""), str(u or ""))


def _room_lines(facts: dict) -> list[str]:
    room = facts.get("room") or {}
    head = f"Patalpa {room.get('nr')}" + (f" · {room['name']}" if room.get("name") else "")
    if room.get("page"):
        head += f" (lapas {room['page']})"
    lines = [head]
    for f in facts.get("facts") or []:
        name = _FACT_NAMES.get(f.get("key"), f.get("key"))
        value = f"{_n(f.get('value'))} {_unit(f.get('unit'))}".strip() if f.get("value") is not None else "—"
        status = _STATUS.get(f.get("status"), f.get("status") or "")
        sentence = (f.get("sentence") or "").strip()
        lines.append(f"  - {name}: {value} ({status}{', įrašė vartotojas' if f.get('yours') else ''})"
                     + (f" — {sentence}" if sentence else ""))
    qs = facts.get("quantities") or []
    if qs:
        lines.append("  Šios patalpos dalis sąmatos eilutėse:")
        for q in qs:
            formula = (q.get("formula") or "").strip()
            lines.append(f"  - {q.get('aprasymas')}: {_n(q.get('value'))} {_unit(q.get('unit'))}"
                         + (f" — {formula}" if formula else ""))
    for e in facts.get("excluded") or []:
        why = (e.get("excluded_because") or "").strip()
        lines.append(f"  - neįtraukta į „{e.get('aprasymas')}“" + (f": {why}" if why else ""))
    return lines


def _row_lines(row: dict) -> list[str]:
    unit = _unit(row.get("mato_vnt") or row.get("vnt"))
    head = f"Eilutė „{row.get('aprasymas')}“"
    if row.get("skyrius"):
        head += f" (skyrius „{row['skyrius']}“)"
    lines = [f"{head}: {_n(row.get('kiekis'))} {unit}".rstrip()]
    if row.get("manual_override") or row.get("quantity_source") == "manual_override":
        lines.append(f"  - kiekį įrašė vartotojas; iš brėžinio buvo {_n(row.get('ai_kiekis_original'))} {unit}".rstrip())
    elif row.get("user_verified_at"):
        lines.append("  - vartotojas patvirtino šį kiekį")
    contributions = [c for c in row.get("contributions") or [] if isinstance(c, dict)]
    if contributions:
        lines.append("  Iš kur (patalpomis):")
        for c in contributions:
            why = (c.get("included_because") or "").strip()
            lines.append(f"  - {c.get('room_nr')} {c.get('room_name') or ''}".rstrip()
                         + f": {_n(c.get('value'))} {_unit(c.get('unit'))}".rstrip() + (f" ({why})" if why else ""))
    for e in [e for e in row.get("excluded") or [] if isinstance(e, dict)]:
        why = (e.get("excluded_because") or "").strip()
        lines.append(f"  - neįtraukta: {e.get('room_nr')} {e.get('room_name') or ''}".rstrip() + (f" — {why}" if why else ""))
    roll_up = [s for s in row.get("roll_up") or [] if isinstance(s, dict)]
    if roll_up:
        lines.append("  Eiga: " + " → ".join(f"{s.get('label')} = {_n(s.get('value'))}" for s in roll_up))
    if not contributions and not roll_up:
        lines.append("  - šios eilutės skaičiavimo eiga neįrašyta")
    return lines


def build_chat_selection(project: dict, selection: Any) -> tuple[str | None, dict]:
    """(the block's text or None when nothing usable was selected, `given`).

    `given` = {rooms: [{nr, name}], rows: [{id, aprasymas}], left_out: {rooms: [...], rows: [...]},
    not_found: {rooms: [...], rows: [...]}} — exactly what the model was handed."""
    sel = selection if isinstance(selection, dict) else {}
    room_ids, row_ids = _ids(sel.get("rooms")), _ids(sel.get("rows"))
    given: dict = {"rooms": [], "rows": [], "left_out": {"rooms": room_ids[MAX_ROOMS:], "rows": row_ids[MAX_ROWS:]},
                   "not_found": {"rooms": [], "rows": []}}
    blocks: list[str] = []

    for nr in room_ids[:MAX_ROOMS]:
        try:
            facts = build_room_facts(project, nr)
        except Exception as exc:  # noqa: BLE001 — a malformed legacy room is left out, never a 500
            log.warning("chat selection: room %s facts failed: %r", nr, exc)
            facts = None
        if not facts:
            given["not_found"]["rooms"].append(nr)
            continue
        given["rooms"].append({"nr": facts["room"]["nr"], "name": facts["room"].get("name") or ""})
        blocks.append("\n".join(_room_lines(facts)))

    by_id: dict[str, dict] = {}
    for row in _rows(project):
        for key in _row_ids(row):
            by_id.setdefault(key, row)
    for rid in row_ids[:MAX_ROWS]:
        row = by_id.get(rid)
        if row is None:
            given["not_found"]["rows"].append(rid)
            continue
        given["rows"].append({"id": rid, "aprasymas": row.get("aprasymas") or ""})
        blocks.append("\n".join(_row_lines(row)))

    if not blocks:
        return None, given
    notes = []
    if given["left_out"]["rooms"]:
        notes.append(f"Pažymėta daugiau patalpų, nei pateikiama: čia tik pirmos {MAX_ROOMS}; neįtrauktos: "
                     + ", ".join(given["left_out"]["rooms"]) + ".")
    if given["left_out"]["rows"]:
        notes.append(f"Pažymėta daugiau eilučių, nei pateikiama: čia tik pirmos {MAX_ROWS}; neįtrauktos — "
                     f"{len(given['left_out']['rows'])}.")
    if given["not_found"]["rooms"] or given["not_found"]["rows"]:
        notes.append("Dalies pažymėtų dalykų projekte neradau: "
                     + ", ".join(given["not_found"]["rooms"] + given["not_found"]["rows"]) + ".")
    header = ("PASIRINKTA — vartotojas pažymėjo šias patalpas ir eilutes. Žemiau — tai, ką programa apie jas "
              "perskaitė iš brėžinio ir apskaičiavo:")
    text = "\n\n".join([header, *blocks, *notes])
    return text, given

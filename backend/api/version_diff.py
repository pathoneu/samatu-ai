"""What changed between two saved states of a project, in Lithuanian sentences (togal-v2 W10).

Pure: two project blobs in, a structured diff out, where every item already
carries the sentence the „Istorija" panel prints („Patalpa 03 Vonia: perimetras
36,56 → 38,10 m (kontūras pataisytas)"). In the spirit of
frontend/src/lib/rereadDiffText.js — engine codes never reach the screen, a line
whose old and new value read the same is left out, numbers use a decimal comma.

Three parts:
  * patalpos — rooms added, removed, changed (which facts, old → new), keyed by `nr`;
  * eilutes — priced rows (`darbu_sarasas`) added, deleted, kiekis / kaina changed,
    keyed by the row `id` (label as a fallback for old rows without one);
  * prielaidos — the assumptions the recompute reads (`_overrides`, `_apimtis`).

It compares what is stored; it computes nothing and imports nothing from the
engine. `a` is the older state, `b` the newer one.
"""
from __future__ import annotations

import math
from typing import Any

NBSP = " "

ROOM_NUMBERS = (("plotas_m2", "plotas", "m²"), ("perimetras_m", "perimetras", "m"),
                ("lubu_aukstis_m", "lubų aukštis", "m"))
ROOM_TEXTS = (("pavadinimas", "pavadinimas"), ("paskirtis", "paskirtis"),
              ("grindu_danga", "grindų danga"))
DOOR_KINDS = {"duris", "pasleptos_duris"}
USER_POLYGON_SOURCES = {"corrected", "manual"}

PASKIRTIS_LT = {
    "gyvenamoji": "gyvenamoji", "miegamoji": "miegamoji", "virtuve": "virtuvė",
    "valgomasis": "valgomasis", "vonia": "vonia", "wc": "WC", "koridorius": "koridorius",
    "holas": "holas", "drabuzine": "drabužinė", "sandeliukas": "sandėliukas",
    "tamburas": "tambūras", "tambūras": "tambūras", "garazas": "garažas",
    "katiline": "katilinė", "skalbykla": "skalbykla", "kabinetas": "kabinetas",
    "san": "san. mazgas", "pirtis": "pirtis", "baseinas": "baseinas", "laiptine": "laiptinė",
    "rubine": "rūbinė", "techpatalpa": "techninė patalpa", "terasa": "terasa / balkonas",
}
FLOOR_LT = {"plyteles": "plytelės", "minksta": "parketas arba laminatas", "be_dangos": "be dangos"}

# Assumptions he sets in Prielaidos / „Ką skaičiuoti", by the key the recompute reads.
ASSUMPTION_LT = {
    "paint_class": ("dažymo klasė", ""),
    "sienos_storis_m": ("sienų storis", "m"),
    "bathroom_tile_height_m": ("plytelių aukštis vonioje", "m"),
    "kitchen_backsplash_height_m": ("plytelių juosta virtuvėje", "m"),
    "openings_threshold_m2": ("neatimamų angų riba", "m²"),
    "default_door_area_m2": ("durų plotas pagal nutylėjimą", "m²"),
    "default_window_area_m2": ("lango plotas pagal nutylėjimą", "m²"),
    "count_inner_corners": ("vidiniai kampai", ""),
    "count_outer_corners": ("išoriniai kampai", ""),
    "glaistas_q_lygis": ("glaistymo lygis", ""),
    "glaistas_storis_mm": ("glaisto storis", "mm"),
    "tile_method": ("plytelių skaičiavimas", ""),
    "lubos": ("lubos", ""),
    "sienos_angos": ("angos sienose", ""),
    "rotband": ("sienų lyginimas", ""),
    "rotband_dalis": ("lyginamų sienų dalis", ""),
    "kampai": ("kampai", ""),
    "patalpos_ne": ("neskaičiuojamos patalpos", ""),
    "darbai_ne": ("neskaičiuojami darbai", ""),
}
CODE_LT = {
    "dazomos": "dažomos", "ne_musu": "ne mūsų darbas", "itempiamos": "įtempiamos",
    "atimti": "atimamos", "neatimti": "neatimamos", "dalis": "dalis sienų", "visos": "visos sienos",
    "nera": "nėra", "su_vidiniais": "su vidiniais", "be_vidiniu": "be vidinių",
    "tikslus": "tikslus", "praktinis": "praktinis",
}


# ── formatting ──────────────────────────────────────────────────────────────

def lt_number(value: float, digits: int = 2) -> str:
    """1234.5 → „1 234,50" (no-break space between thousands, decimal comma)."""
    s = f"{float(value):,.{digits}f}"
    return s.replace(",", NBSP).replace(".", ",")


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _same_num(a: float | None, b: float | None, tol: float = 0.005) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) < tol)


def _qty(v: float | None, unit: str = "", digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{lt_number(v, digits)}{NBSP + unit if unit else ''}"


def _code(v: Any) -> str:
    return str(v if v is not None else "").strip().lower()


def _text_value(key: str, v: Any) -> str:
    if v is None or v == "":
        return "—"
    if key == "paskirtis":
        return PASKIRTIS_LT.get(_code(v), str(v))
    if key == "grindu_danga":
        return FLOOR_LT.get(_code(v), str(v))
    return str(v)


def _assumption_value(v: Any, unit: str) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, bool):
        return "taip" if v else "ne"
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v) if v else "nėra"
    n = _num(v)
    if n is not None:
        digits = 0 if float(n).is_integer() and not unit else 2
        return _qty(n, unit, digits)
    return CODE_LT.get(_code(v), str(v).replace("_", " "))


# ── rooms ───────────────────────────────────────────────────────────────────

def _rooms(blob: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, r in enumerate(blob.get("patalpos") or []):
        if not isinstance(r, dict):
            continue
        nr = str(r.get("nr")).strip() if r.get("nr") is not None else f"#{i + 1}"
        out.setdefault(nr, r)
    return out


def _openings(room: dict) -> tuple[int, int]:
    durys = langai = 0
    for el in room.get("elementai") or []:
        if not isinstance(el, dict):
            continue
        n = _num(el.get("kiekis"))
        k = int(n) if n is not None else 1
        kind = _code(el.get("tipas"))
        if kind in DOOR_KINDS:
            durys += k
        elif kind == "langas":
            langai += k
    return durys, langai


def _outline(room: dict) -> tuple:
    pts = room.get("polygon_pct")
    if not isinstance(pts, list):
        return ()
    out = []
    for p in pts:
        if isinstance(p, (list, tuple)) and len(p) >= 2 and _num(p[0]) is not None and _num(p[1]) is not None:
            out.append((round(float(p[0]), 4), round(float(p[1]), 4)))
    return tuple(out)


def _room_label(nr: str, room: dict) -> str:
    name = str(room.get("pavadinimas") or "").strip()
    return f"Patalpa {nr}" + (f" {name}" if name else "")


def room_changes(a: dict, b: dict) -> list[dict]:
    """[{key, label, from, to, text}] — one item per fact that reads differently."""
    out: list[dict] = []
    for key, label, unit in ROOM_NUMBERS:
        x, y = _num(a.get(key)), _num(b.get(key))
        if not _same_num(x, y) and _qty(x, unit) != _qty(y, unit):
            out.append({"key": key, "label": label, "from": x, "to": y,
                        "text": f"{label} {_qty(x, unit)} → {_qty(y, unit)}"})
    for key, label in ROOM_TEXTS:
        x, y = _text_value(key, a.get(key)), _text_value(key, b.get(key))
        if x != y:
            out.append({"key": key, "label": label, "from": a.get(key), "to": b.get(key),
                        "text": f"{label} „{x}“ → „{y}“"})
    (da, la), (db, lb) = _openings(a), _openings(b)
    if da != db:
        out.append({"key": "durys", "label": "durys", "from": da, "to": db,
                    "text": f"durys {da} → {db} vnt."})
    if la != lb:
        out.append({"key": "langai", "label": "langai", "from": la, "to": lb,
                    "text": f"langai {la} → {lb} vnt."})
    xa, xb = bool(a.get("_neskaiciuoti")), bool(b.get("_neskaiciuoti"))
    if xa != xb:
        out.append({"key": "neskaiciuoti", "label": "skaičiavimas", "from": xa, "to": xb,
                    "text": "nebeskaičiuojama" if xb else "vėl skaičiuojama"})
    return out


def _outline_note(a: dict, b: dict) -> str | None:
    if _outline(a) == _outline(b) and _code(a.get("polygon_source")) == _code(b.get("polygon_source")):
        return None
    if not _outline(b):
        return "kontūras pašalintas"
    if not _outline(a):
        return "kontūras nubrėžtas"
    if _code(b.get("polygon_source")) in USER_POLYGON_SOURCES:
        return "kontūras pataisytas"
    return "kontūras pakeistas"


def diff_rooms(a_blob: dict, b_blob: dict) -> dict:
    ra, rb = _rooms(a_blob), _rooms(b_blob)
    added, removed, changed = [], [], []
    for nr, room in rb.items():
        if nr not in ra:
            area = _num(room.get("plotas_m2"))
            tail = f" ({_qty(area, 'm²')})" if area is not None else ""
            added.append({"nr": nr, "pavadinimas": room.get("pavadinimas"),
                          "text": f"Pridėta: {_room_label(nr, room)}{tail}"})
    for nr, room in ra.items():
        if nr not in rb:
            removed.append({"nr": nr, "pavadinimas": room.get("pavadinimas"),
                            "text": f"Pašalinta: {_room_label(nr, room)}"})
    for nr, old in ra.items():
        new = rb.get(nr)
        if new is None:
            continue
        facts = room_changes(old, new)
        note = _outline_note(old, new)
        if not facts and not note:
            continue
        body = "; ".join(f["text"] for f in facts)
        if note:
            body = f"{body} ({note})" if body else note
        changed.append({"nr": nr, "pavadinimas": new.get("pavadinimas"), "laukai": facts,
                        "konturas": note, "text": f"{_room_label(nr, new)}: {body}"})
    return {"pridetos": added, "pasalintos": removed, "pakeistos": changed}


# ── rows ────────────────────────────────────────────────────────────────────

def _row_key(row: dict, i: int) -> str:
    rid = row.get("id")
    if rid:
        return f"id:{rid}"
    label = str(row.get("aprasymas") or row.get("pavadinimas") or "").strip().lower()
    return f"lbl:{label}" if label else f"#{i}"


def _rows(blob: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, r in enumerate(blob.get("darbu_sarasas") or []):
        if isinstance(r, dict):
            out.setdefault(_row_key(r, i), r)
    return out


def _row_label(row: dict) -> str:
    return str(row.get("aprasymas") or row.get("pavadinimas") or "be pavadinimo").strip()


def _unit(row: dict) -> str:
    return str(row.get("mato_vnt") or row.get("vnt") or "").strip()


def diff_rows(a_blob: dict, b_blob: dict) -> dict:
    ra, rb = _rows(a_blob), _rows(b_blob)
    added, deleted, changed = [], [], []
    for key, row in rb.items():
        if key not in ra:
            q = _num(row.get("kiekis"))
            tail = f" ({_qty(q, _unit(row))})" if q is not None else ""
            added.append({"id": row.get("id"), "aprasymas": _row_label(row),
                          "text": f"Pridėta eilutė „{_row_label(row)}“{tail}"})
    for key, row in ra.items():
        if key not in rb:
            deleted.append({"id": row.get("id"), "aprasymas": _row_label(row),
                            "text": f"Ištrinta eilutė „{_row_label(row)}“"})
    for key, old in ra.items():
        new = rb.get(key)
        if new is None:
            continue
        parts, fields = [], []
        qa, qb = _num(old.get("kiekis")), _num(new.get("kiekis"))
        unit = _unit(new) or _unit(old)
        if not _same_num(qa, qb) and _qty(qa, unit) != _qty(qb, unit):
            fields.append({"key": "kiekis", "from": qa, "to": qb})
            parts.append(f"kiekis {_qty(qa, unit)} → {_qty(qb, unit)}")
        pa, pb = _num(old.get("kaina")), _num(new.get("kaina"))
        if not _same_num(pa, pb) and _qty(pa, '€') != _qty(pb, '€'):
            fields.append({"key": "kaina", "from": pa, "to": pb})
            parts.append(f"kaina {_qty(pa, '€')} → {_qty(pb, '€')}")
        if not parts:
            continue
        changed.append({"id": new.get("id"), "aprasymas": _row_label(new), "laukai": fields,
                        "text": f"Eilutė „{_row_label(new)}“: {', '.join(parts)}"})
    return {"pridetos": added, "istrintos": deleted, "pakeistos": changed}


# ── assumptions ─────────────────────────────────────────────────────────────

def _assumptions(blob: dict) -> dict[str, Any]:
    """Flat {path: value} over `_overrides` and `_apimtis` (the latter wins on a
    clash, it is what the scope step reads)."""
    flat: dict[str, Any] = {}

    def walk(prefix: str, d: Any) -> None:
        if not isinstance(d, dict):
            return
        for k, v in d.items():
            path = f"{prefix}{k}"
            if isinstance(v, dict):
                walk(f"{path}.", v)
            else:
                flat[path] = v

    ov = blob.get("_overrides")
    if isinstance(ov, dict):
        walk("", {k: v for k, v in ov.items() if k != "apimtis"})
        walk("", ov.get("apimtis") if isinstance(ov.get("apimtis"), dict) else {})
    walk("", blob.get("_apimtis") if isinstance(blob.get("_apimtis"), dict) else {})
    return flat


def _assumption_sentence(path: str, old: Any, new: Any) -> str | None:
    head, _, tail = path.partition(".")
    if head == "lubu_auksciai" and tail:
        return (f"Patalpa {tail}: lubų aukštis prielaidose "
                f"{_assumption_value(old, 'm')} → {_assumption_value(new, 'm')}")
    if head == "patalpu_sritys_ne" and tail:
        return (f"Patalpa {tail}: neskaičiuojami darbai "
                f"{_assumption_value(old, '')} → {_assumption_value(new, '')}")
    if head.endswith("_painted") and not tail:
        room = head[: -len("_painted")]
        label = PASKIRTIS_LT.get(room, room.replace("_", " "))
        return f"Ar dažoma: {label} — {_assumption_value(old, '')} → {_assumption_value(new, '')}"
    label, unit = ASSUMPTION_LT.get(tail or head, (None, ""))
    if label is None:
        return None
    a, b = _assumption_value(old, unit), _assumption_value(new, unit)
    return None if a == b else f"Prielaida „{label}“: {a} → {b}"


def diff_assumptions(a_blob: dict, b_blob: dict) -> dict:
    fa, fb = _assumptions(a_blob), _assumptions(b_blob)
    items, other = [], 0
    for path in sorted(set(fa) | set(fb)):
        old, new = fa.get(path), fb.get(path)
        if old == new or (_num(old) is not None and _same_num(_num(old), _num(new))):
            continue
        text = _assumption_sentence(path, old, new)
        if text is None:
            other += 1
            continue
        items.append({"key": path, "from": old, "to": new, "text": text})
    if other:
        items.append({"key": None, "from": None, "to": None,
                      "text": f"Pakeista kitų skaičiavimo nustatymų: {other}"})
    return {"pakeistos": items}


# ── whole diff ──────────────────────────────────────────────────────────────

def diff_projects(a_blob: dict, b_blob: dict) -> dict:
    """{patalpos, eilutes, prielaidos, sakiniai, tuscia}. `sakiniai` is every
    sentence in reading order: rooms, rows, assumptions."""
    a = a_blob if isinstance(a_blob, dict) else {}
    b = b_blob if isinstance(b_blob, dict) else {}
    rooms, rows, assumptions = diff_rooms(a, b), diff_rows(a, b), diff_assumptions(a, b)
    sentences = [x["text"] for part in (rooms["pridetos"], rooms["pasalintos"], rooms["pakeistos"],
                                        rows["pridetos"], rows["istrintos"], rows["pakeistos"],
                                        assumptions["pakeistos"]) for x in part]
    return {"patalpos": rooms, "eilutes": rows, "prielaidos": assumptions,
            "sakiniai": sentences, "tuscia": not sentences}

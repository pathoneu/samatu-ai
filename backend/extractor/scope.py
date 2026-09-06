"""Apimtis — what the contractor calculates and what he does not (item 4, 2026-09-06).

WHY. The same drawing is priced by different contractors for different work:
one does the bathrooms and the walls only (objektas_g), another everything but
the ceilings, a third only the rooms the client has not finished himself. The
engine used to answer one question — „what is in this drawing" — and every
contractor had to delete rows by hand. The founder's rule: many free-form
choices of what to count and what not, never odd yes/no questions.

WHAT A SCOPE IS (`_apimtis` on the project, sent as `rules_override.apimtis`):

    {"patalpos_ne": ["07"],                 # rooms he does not do — kept on the
                                            #   sheet, marked, out of every row
     "darbai_ne": ["plyteles"],             # work families he does not do
     "patalpu_sritys_ne": {"03": ["grindys"]},   # families off in ONE room
                                            #   (apdaila / grindys / plyteles —
                                            #   the room-driven ones)
     "lubos": "dazomos"|"ne_musu"|"itempiamos",   # project default for ceilings
     "sienos_angos": "atimti"|"neatimti",   # wall area with or without openings
     "rotband": "dalis"|"nera"|"visos",     # wall levelling: a share, none, all
     "rotband_dalis": 30}                   #   the share in %, when "dalis"

Everything absent means „as the drawing says". A per-room choice already made
elsewhere (Prielaidos: a room's own ceiling flag) wins over the project default.

HOW IT IS ENFORCED — server side, so exports and the template see the same
numbers as the screen:
  · an excluded room is MARKED (`_neskaiciuoti`), its computed quantities are
    zeroed, and the builder / totals / ceiling anchor skip it; it stays in
    `patalpos` so the sheet can show the switch and the ledger says why it is
    out („Neįtraukta jūsų pasirinkimu");
  · a family that is off drops its rows after the build (same rule as the
    upload screen's `workFamilies.js`: only recognised sections, materials
    follow their work, unrecognised sections always stay);
  · ceilings „ne mūsų" zero every room's painted ceiling that has no explicit
    per-room flag; „įtempiamos" marks every room stretch unless the room says
    otherwise (`vision_call._stretch_ceiling_nrs`);
  · walls without openings: the openings deduction is switched off through the
    room rules (`universal_rules` `deduct_openings`).
Stateless: derived from `_apimtis` on every compute — switching a choice back
restores the drawing's numbers, nothing is written into the rooms for keeps.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

__all__ = [
    "FAMILIES", "ROOM_FAMILIES", "LUBOS_CHOICES", "SIENOS_ANGOS_CHOICES", "ROTBAND_CHOICES",
    "ROTBAND_DEFAULT_SHARE", "EXCLUDED_BECAUSE", "CEILING_NOT_OURS", "COMPUTED_ROOM_FIELDS",
    "FAMILY_ROOM_FIELDS", "normalize_apimtis", "section_family", "is_room_excluded",
    "room_families_off", "family_on_in_room", "mark_rooms", "rooms_in_scope",
    "filter_rows_by_families", "apply_ceiling_choice", "rotband_share",
]

FAMILIES = ("apdaila", "grindys", "plyteles", "santechnika", "elektra")
# The families a single room can switch off: the ones the builder derives from
# the room's own quantities. Santechnika and elektra are counted per project
# (symbol counts), so they are project-level choices only.
ROOM_FAMILIES = ("apdaila", "grindys", "plyteles")
LUBOS_CHOICES = ("dazomos", "ne_musu", "itempiamos")
SIENOS_ANGOS_CHOICES = ("atimti", "neatimti")
ROTBAND_CHOICES = ("dalis", "nera", "visos")
# Levelling plaster goes on masonry, not on GKP partitions. Without a wall-type
# read the engine can only ASSUME a share; the number below is a stated
# assumption the contractor is told to replace, not a fact of any drawing.
ROTBAND_DEFAULT_SHARE = 0.30

EXCLUDED_BECAUSE = "Neįtraukta jūsų pasirinkimu"
CEILING_NOT_OURS = "Lubos ne jūsų darbas — neįtrauktos jūsų pasirinkimu"

# Mirror of frontend/src/lib/workFamilies.js — matched case-insensitively
# against the row's section. Deliberately narrow: a section no pattern is sure
# about belongs to no family and survives every choice.
_SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "apdaila": ("sien", "lub", "glaist", "dažym", "dazym", "gkp", "gipso", "tapet"),
    "grindys": ("grind", "parket", "laminat"),
    "plyteles": ("plytel",),
    "santechnika": ("santechnik",),
    "elektra": ("elektr",),
}

# Per-room quantities the builder consumes, by the family they feed. Zeroed on
# an excluded room (all of them) or for a family switched off in one room, so
# no consumer (builder, frontend sums, validators) sees a stale number; a
# recompute that includes the room again recalculates every one of them from
# the geometry.
FAMILY_ROOM_FIELDS: dict[str, tuple[str, ...]] = {
    "apdaila": (
        "walls_paintable_m2", "ceiling_paintable_m2", "dazymo_plotas_m2", "dazai_l",
        "kampu_metrai", "kampai_pusiniai_m", "kampai_perimetras_m", "kampai_opening_reveals_m",
        "kampai_inner_m", "angokrasciu_gkp_m", "nisu_metrai", "lubu_karnizo_m", "molio_tinko_m2",
        "glaistas_kg", "gruntas_l", "gkp_lubu_standart_m2", "gkp_lubu_virs_3m_m2",
    ),
    "grindys": ("grindjuosciu_m", "_grindjuosciu_baze_m", "_grindjuosciu_duru_m",
                "pvc_grindys_m2", "isliginamasis_m2"),
    "plyteles": ("plyteles_sienos_m2", "plyteles_grindys_m2", "hidroizoliacija_m2"),
}
COMPUTED_ROOM_FIELDS = tuple(f for fam in ROOM_FAMILIES for f in FAMILY_ROOM_FIELDS[fam])


def _nr(v: Any) -> str:
    return str(v if v is not None else "").strip()


def section_family(section: Any) -> str | None:
    """The work family a section belongs to, or None when it belongs to none."""
    s = str(section or "").lower()
    if not s:
        return None
    for family in FAMILIES:
        if any(p in s for p in _SECTION_PATTERNS[family]):
            return family
    return None


def normalize_apimtis(raw: Any) -> dict | None:
    """A clean scope dict, or None when the raw value carries no choice at all."""
    if not isinstance(raw, dict):
        return None
    rooms = raw.get("patalpos_ne")
    darbai = raw.get("darbai_ne")
    per_room_raw = raw.get("patalpu_sritys_ne")
    per_room: dict[str, list[str]] = {}
    if isinstance(per_room_raw, dict):
        for nr, fams in per_room_raw.items():
            if not _nr(nr) or not isinstance(fams, (list, tuple, set)):
                continue
            kept = [f for f in ROOM_FAMILIES if f in fams]
            if kept:
                per_room[_nr(nr)] = kept
    share = None
    try:
        if raw.get("rotband_dalis") is not None:
            share = max(0.0, min(100.0, float(raw.get("rotband_dalis"))))
    except (TypeError, ValueError):
        share = None
    out: dict[str, Any] = {
        "patalpos_ne": sorted({_nr(x) for x in rooms if _nr(x)}) if isinstance(rooms, (list, tuple, set)) else [],
        "darbai_ne": [f for f in FAMILIES if isinstance(darbai, (list, tuple, set)) and f in darbai],
        "patalpu_sritys_ne": dict(sorted(per_room.items())),
        "lubos": raw.get("lubos") if raw.get("lubos") in LUBOS_CHOICES else None,
        "sienos_angos": raw.get("sienos_angos") if raw.get("sienos_angos") in SIENOS_ANGOS_CHOICES else None,
        "rotband": raw.get("rotband") if raw.get("rotband") in ROTBAND_CHOICES else None,
        "rotband_dalis": share,
    }
    if (not out["patalpos_ne"] and not out["darbai_ne"] and not out["patalpu_sritys_ne"]
            and out["lubos"] in (None, "dazomos") and out["sienos_angos"] in (None, "atimti")
            and out["rotband"] in (None,) and out["rotband_dalis"] is None):
        return None
    return out


def room_families_off(apimtis: dict | None, nr: Any) -> list[str]:
    """The room-driven families switched off in this one room (plus every
    family that is off for the whole project)."""
    if not apimtis:
        return []
    off = set(f for f in (apimtis.get("darbai_ne") or []) if f in ROOM_FAMILIES)
    off |= set((apimtis.get("patalpu_sritys_ne") or {}).get(_nr(nr)) or [])
    return [f for f in ROOM_FAMILIES if f in off]


def family_on_in_room(apimtis: dict | None, nr: Any, family: str) -> bool:
    return family not in room_families_off(apimtis, nr)


def rotband_share(apimtis: dict | None, overrides: dict | None = None) -> tuple[float, str]:
    """(share of the painted walls that gets levelling plaster, source).

    source: "pasirinkimas" — his choice (apimtis); "prielaida" — nothing
    chosen, the stated default. The older `rules_override.rotband_share`
    number (Prielaidos) counts as his choice too."""
    a = apimtis or {}
    if a.get("rotband") == "nera":
        return 0.0, "pasirinkimas"
    if a.get("rotband") == "visos":
        return 1.0, "pasirinkimas"
    if a.get("rotband") == "dalis" or a.get("rotband_dalis") is not None:
        pct = a.get("rotband_dalis")
        if pct is not None:
            return max(0.0, min(1.0, float(pct) / 100.0)), "pasirinkimas"
    legacy = (overrides or {}).get("rotband_share")
    if legacy is not None:
        try:
            return max(0.0, min(1.0, float(legacy))), "pasirinkimas"
        except (TypeError, ValueError):
            pass
    return ROTBAND_DEFAULT_SHARE, "prielaida"


def is_room_excluded(apimtis: dict | None, nr: Any) -> bool:
    return bool(apimtis) and _nr(nr) in set(apimtis.get("patalpos_ne") or [])


def _zero(r: dict, fields: Iterable[str]) -> None:
    for f in fields:
        if f in r:
            r[f] = 0.0


def mark_rooms(rooms: Sequence[dict], apimtis: dict | None) -> list[str]:
    """Mark the rooms the contractor does not do and the families he does not
    do in a room; clear the marks on the rest. Returns the numbers of the rooms
    fully marked. Mutates the room dicts: an excluded room loses every computed
    quantity; a room with a family off loses that family's quantities and says
    why in the predicate fields the ledger reads (`_walls_unpainted_reason`,
    `_ceiling_paint_source`, `_grindjuosciu_praleista`)."""
    marked: list[str] = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        r.pop("_neskaiciuoti", None)
        r.pop("_neskaiciuoti_kodel", None)
        r.pop("_neskaiciuoti_sritys", None)
        if is_room_excluded(apimtis, r.get("nr")):
            r["_neskaiciuoti"] = True
            r["_neskaiciuoti_kodel"] = "pasirinkimas"
            _zero(r, COMPUTED_ROOM_FIELDS)
            marked.append(_nr(r.get("nr")))
            continue
        off = room_families_off(apimtis, r.get("nr"))
        if not off:
            continue
        r["_neskaiciuoti_sritys"] = off
        for fam in off:
            _zero(r, FAMILY_ROOM_FIELDS[fam])
        if "apdaila" in off:
            r["_walls_unpainted_reason"] = "pasirinkimas"
            r["_ceiling_paint_source"] = "pasirinkimas"
        if "grindys" in off:
            r["_grindjuosciu_praleista"] = "pasirinkimas"
    return marked


def rooms_in_scope(rooms: Iterable[dict] | None) -> list[dict]:
    return [r for r in (rooms or []) if isinstance(r, dict) and not r.get("_neskaiciuoti")]


def filter_rows_by_families(rows: Sequence[dict] | None, apimtis: dict | None) -> list[dict]:
    """Drop the rows of the families he does not do — and the materials bought
    for those rows (`susijes_darbas`). Unrecognised sections always stay."""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    off = set((apimtis or {}).get("darbai_ne") or [])
    if not off:
        return rows
    dropped: set[str] = set()
    kept: list[dict] = []
    for r in rows:
        fam = section_family(r.get("skyrius") or r.get("kategorija"))
        if fam in off:
            dropped.add(str(r.get("aprasymas") or "").strip().lower())
        else:
            kept.append(r)
    if not dropped:
        return kept
    return [r for r in kept
            if str(r.get("susijes_darbas") or "").strip().lower() not in dropped]


def apply_ceiling_choice(rooms: Sequence[dict], apimtis: dict | None) -> int:
    """„Lubos ne mūsų": no painted ceiling in any room that carries no explicit
    per-room flag of its own. Returns how many rooms it touched. „Įtempiamos"
    is applied by the builder's stretch set; „dažomos" changes nothing."""
    if not apimtis or apimtis.get("lubos") != "ne_musu":
        return 0
    n = 0
    for r in rooms:
        if not isinstance(r, dict) or r.get("_neskaiciuoti"):
            continue
        if r.get("ceiling_paint_override") is not None:
            continue                       # his per-room choice wins
        if float(r.get("ceiling_paintable_m2") or 0) > 0 or r.get("_ceiling_paint_source") != "pasirinkimas":
            r["ceiling_paintable_m2"] = 0.0
            r["_ceiling_paint_source"] = "pasirinkimas"
            n += 1
    return n

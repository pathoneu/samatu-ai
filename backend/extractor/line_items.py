"""Per-line-item quantity helpers (Week 2 of canonical plan).

Why this file exists separately from `universal_rules.py`:
  Each LT-specific formula gets its own test surface so we can debug a single
  line item without re-running the full project calculator. The canonical
  `calc_room_quantities` in `universal_rules.py` calls into these helpers.

What's covered:
  - opening_reveal_lm / opening_reveal_area_m2 (replaces conflated `kampai`)
  - plaster_corners_lm (inner corners only, no opening trim)
  - hidroizoliacija_m2 (real m², replaces integer wet-room count)
  - hidden_door_count / hidden_door_frame_lm (no longer always 0)
  - silikonas_lm, plyteliu_45_suleidimas_lm, plyteliu_profiliai_lm (Week 4 microworks)

Defaults reflect rangovas mid-market Kaunas reality + LT STR norms (R4 research).
"""
from __future__ import annotations

from typing import Iterable

DEFAULT_DOOR_W_M = 0.90
DEFAULT_DOOR_H_M = 2.05
DEFAULT_WINDOW_W_M = 1.20
DEFAULT_WINDOW_H_M = 1.50
DEFAULT_WALL_THICKNESS_M = 0.10
DEFAULT_HYDRO_WALL_TURNUP_M = 0.20  # STR 2.04.01 default

WET_ROOM_PASKIRTIS = {
    "vonia", "wc", "san", "katiline", "skalbykla", "dušas", "prausykla",
}


def _get(d: dict, key: str, default=None):
    """Tolerant dict accessor: handles both dict and pydantic model-like inputs."""
    if hasattr(d, key):
        v = getattr(d, key)
        return v if v is not None else default
    return d.get(key, default)


def _as_float(value, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return f


_LT_TO_EN_OPENING_TYPE = {
    "duris": "door",
    "durys": "door",
    "pasleptos_duris": "hidden_door",
    "pasleptos_durys": "hidden_door",
    "paslepta_duris": "hidden_door",
    "paslepta_durys": "hidden_door",
    "hidden_door": "hidden_door",
    "langas": "window",
    "stoglangis": "window",
    "window": "window",
    "door": "door",
}


def _opening_type(op) -> str:
    raw = (_get(op, "type") or _get(op, "tipas") or "unknown").lower()
    return _LT_TO_EN_OPENING_TYPE.get(raw, raw)


def _opening_dims(op) -> tuple[float, float, int]:
    """Return (width_m, height_m, count) with LT default fallbacks per type."""
    t = _opening_type(op)
    # Accept metres OR millimetres (Vision returns plotis_mm/aukstis_mm).
    w = _get(op, "width_m") or _get(op, "plotis_m")
    h = _get(op, "height_m") or _get(op, "aukstis_m")
    if w is None:
        mm = _get(op, "width_mm") or _get(op, "plotis_mm")
        if mm:
            w = _as_float(mm) / 1000.0
    if h is None:
        mm = _get(op, "height_mm") or _get(op, "aukstis_mm")
        if mm:
            h = _as_float(mm) / 1000.0
    count = int(_get(op, "count") or _get(op, "kiekis") or 1)
    if t in ("door", "hidden_door"):
        return (
            _as_float(w, DEFAULT_DOOR_W_M),
            _as_float(h, DEFAULT_DOOR_H_M),
            count,
        )
    if t == "window":
        return (
            _as_float(w, DEFAULT_WINDOW_W_M),
            _as_float(h, DEFAULT_WINDOW_H_M),
            count,
        )
    return (_as_float(w, DEFAULT_DOOR_W_M),
            _as_float(h, DEFAULT_DOOR_H_M),
            count)


def opening_reveal_lm(openings: Iterable, window_sides: int = 3) -> float:
    """Reveal perimeter length per opening, summed.

    Default LT mode: 3-sided for both doors and windows. Window sill (palangė)
    is a separate line item priced per linear metre, NOT folded into reveal
    area. Set window_sides=4 only when caller explicitly disables the separate
    sill line.
    """
    if window_sides not in (3, 4):
        raise ValueError(f"window_sides must be 3 or 4, got {window_sides}")
    total = 0.0
    for op in openings or []:
        t = _opening_type(op)
        w, h, count = _opening_dims(op)
        if t in ("door", "hidden_door"):
            total += count * (2 * h + w)
        elif t == "window":
            sides = 2 * h + w if window_sides == 3 else 2 * h + 2 * w
            total += count * sides
    return round(total, 3)


def opening_reveal_area_m2(
    openings: Iterable,
    wall_thickness_m: float = DEFAULT_WALL_THICKNESS_M,
    window_sides: int = 3,
) -> float:
    """Reveal area = reveal_lm × wall_thickness_m. The 2026-05-10 split moves
    this OUT of `kampai` into its own line item (`angokrasciai_m2`)."""
    return round(
        opening_reveal_lm(openings, window_sides=window_sides)
        * _as_float(wall_thickness_m, DEFAULT_WALL_THICKNESS_M),
        3,
    )


def plaster_corners_lm(room: dict | object, fallback_corners: int = 4) -> float:
    """Inner-corner length only.

    Reveal perimeters used to be added here, conflating two concepts. Now they
    live in `opening_reveal_lm`. This function returns ONLY the inner corner
    contribution, derived from the polygon vertex count when available, else
    a 4-corner fallback.
    """
    polygon = _get(room, "polygon_pct") or _get(room, "polygon")
    if polygon and len(polygon) >= 3:
        n_corners = len(polygon)
    else:
        n_corners = fallback_corners
    h = _as_float(
        _get(room, "ceiling_height_m") or _get(room, "lubu_aukstis_m"),
        2.82,
    )
    return round(n_corners * h, 3)


def _is_wet_room(room: dict | object) -> bool:
    if bool(_get(room, "wet_room", False)):
        return True
    paskirtis = (_get(room, "paskirtis") or "").lower()
    return paskirtis in WET_ROOM_PASKIRTIS


def hidroizoliacija_m2(
    rooms: Iterable,
    default_wall_turnup_m: float = DEFAULT_HYDRO_WALL_TURNUP_M,
) -> tuple[float, list[str]]:
    """Hidroizoliacijos plotas, m² — never vnt.

    STR 2.04.01: floor area + 200mm wall turn-up around perimeter, plus any
    explicit shower/bath hydro zones. Returns (total_m², warnings[]).

    When `hydro_zones` are not provided we fall back to floor + perimeter ×
    turn-up and emit a yellow warning so the UI can show explicit fallback
    provenance.
    """
    total = 0.0
    warnings: list[str] = []
    for room in rooms or []:
        if not _is_wet_room(room):
            continue
        zones = _get(room, "hydro_zones") or []
        if zones:
            total += sum(_as_float(_get(z, "area_m2", 0)) for z in zones)
        else:
            floor = _as_float(_get(room, "area_m2") or _get(room, "plotas_m2"))
            cokolis = (
                _as_float(_get(room, "perimeter_m") or _get(room, "perimetras_m"))
                * _as_float(default_wall_turnup_m, DEFAULT_HYDRO_WALL_TURNUP_M)
            )
            total += floor + cokolis
            rid = _get(room, "id") or _get(room, "nr") or _get(room, "name") or "?"
            warnings.append(
                f"Room {rid}: hydro_zones not provided; used STR 2.04.01 default "
                f"(floor + {default_wall_turnup_m}m perimeter turn-up)."
            )
    return round(total, 3), warnings


def hidden_door_count(openings: Iterable) -> int:
    return sum(
        int(_get(op, "count") or _get(op, "kiekis") or 1)
        for op in openings or []
        if _opening_type(op) == "hidden_door"
    )


def hidden_door_frame_lm(openings: Iterable) -> float:
    """Linear metres of paslėptų durų staktos (3-sided per komplektas).

    Pre-2026-05-10 this field was always 0 because no detector populated it.
    Vision now classifies `type='hidden_door'` when the schedule labels durys
    as "paslėpta" / "nematoma stakta" — see `prompts/floor_plan.py`.
    """
    total = 0.0
    for op in openings or []:
        if _opening_type(op) != "hidden_door":
            continue
        w, h, count = _opening_dims(op)
        total += count * (2 * h + w)
    return round(total, 3)


def silikonas_lm(rooms: Iterable) -> float:
    """Inside_corners × room_height + floor-wall perimeter, wet rooms with tiles only."""
    total = 0.0
    for room in rooms or []:
        if not _is_wet_room(room):
            continue
        if not _get(room, "tile_zones"):
            continue
        h = _as_float(
            _get(room, "ceiling_height_m") or _get(room, "lubu_aukstis_m"),
            2.82,
        )
        polygon = _get(room, "polygon_pct") or _get(room, "polygon")
        corners = len(polygon) if (polygon and len(polygon) >= 3) else 4
        perim = _as_float(_get(room, "perimeter_m") or _get(room, "perimetras_m"))
        total += corners * h + perim
    return round(total, 3)


def plyteliu_45_suleidimas_lm(rooms: Iterable) -> float:
    """Sum of explicit miter_45_lm across tile zones. Never inferred."""
    total = 0.0
    for room in rooms or []:
        for zone in _get(room, "tile_zones") or []:
            total += _as_float(_get(zone, "miter_45_lm", 0))
    return round(total, 3)


def plyteliu_profiliai_lm(rooms: Iterable) -> float:
    """Sum of explicit edge_profile_lm across tile zones."""
    total = 0.0
    for room in rooms or []:
        for zone in _get(room, "tile_zones") or []:
            total += _as_float(_get(zone, "edge_profile_lm", 0))
    return round(total, 3)

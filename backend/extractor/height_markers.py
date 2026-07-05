"""Deterministic ceiling-height marker scanner.

LT projektiniai pjūviai (sections) annotate vertical levels with markers like
`+0.000` (floor reference), `+2.800` / `+3.000` (ceiling slab top), `+5.700`
(2nd floor ceiling or ridge). When Vision misses these on the cover/section
page, the system falls back to the 2.80 m default — burying real ceilings
above 3 m and skewing every wall-paint quantity downstream.

This scanner reads the PDF text layer (no Vision call) and surfaces the
plausible ceiling-height candidates so the extractor can use them as a
deterministic fallback. Reference: docs/2026-05-07-launch-status.md §3.
"""
from __future__ import annotations

import io
import re

# +3.000 / +2,800 / ±0.000 / + 3.000 — sign followed by decimal value.
# Capture group 1 is the numeric portion (handles both `.` and `,` decimals).
_HEIGHT_MARKER_RE = re.compile(r'[+±]\s*(\d+[.,]\d{1,3})')

# Plausible ceiling height range for LT residential / commercial buildings.
# Below 2.0 m is impractical (post-2000 modern minimum is 2.5–2.65 m); above
# 4.5 m is more likely a ridge / roof / mansard apex than a ceiling slab.
MIN_CEILING_M = 2.0
MAX_CEILING_M = 4.5


def scan_page_height_markers(
    pdf_bytes: bytes,
    page_nrs: tuple[int, ...] = (1,),
) -> list[dict]:
    """Scan the given PDF pages for elevation/ceiling-height markers.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_nrs: 1-indexed page numbers to scan. Defaults to (1,) because
            the cover/section is almost always page 1 of LT interior projects.

    Returns:
        List of {"page": int, "raw": str, "value_m": float} dicts for each
        plausible match within MIN/MAX_CEILING_M. Order preserves page order
        and within-page text order. Empty list on any pdfplumber error
        (defensive — caller treats absence as "no signal", not as failure).
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    out: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pn in page_nrs:
                if pn < 1 or pn > len(pdf.pages):
                    continue
                try:
                    text = pdf.pages[pn - 1].extract_text() or ""
                except Exception:
                    continue
                for m in _HEIGHT_MARKER_RE.finditer(text):
                    raw = m.group(0)
                    val_str = m.group(1).replace(',', '.')
                    try:
                        val = float(val_str)
                    except ValueError:
                        continue
                    if MIN_CEILING_M <= val <= MAX_CEILING_M:
                        out.append({"page": pn, "raw": raw, "value_m": val})
    except Exception:
        return []
    return out


def best_ceiling_candidate(markers: list[dict]) -> dict | None:
    """Pick the largest in-range marker as the most likely ceiling height.

    LT pjūviai typically annotate (in ascending order): `±0.000` floor,
    `+2.400`–`+2.500` beam undersides, `+2.800`–`+3.200` ceiling slab top,
    `+5.700`+ second-floor ceiling or ridge. The largest value still inside
    [MIN_CEILING_M, MAX_CEILING_M] is — within a single floor — almost
    always the actual ceiling slab top.

    For multi-floor buildings the caller should rerun per-floor; the
    universal fallback uses the largest single-floor candidate.
    """
    if not markers:
        return None
    return max(markers, key=lambda m: m["value_m"])


# 2026-05-11 W2: salvage heights from Vision warnings[] narrative.
#
# Even with the imperative prompt iteration that fixed projektas_1
# (commit be422a7), Vision still narrates rather than structures on
# some PDFs — specifically when there's value-ambiguity ("švarus
# lubų aukštis" = clean/finished vs raw) or room-mapping ambiguity
# ("3200mm visose voniose" — which bathrooms exactly). This salvage
# pass mines the free-text warnings for known height patterns and
# applies them deterministically.

# "300cm", "320cm", "294cm" — centimetres
_HEIGHT_CM_RE = re.compile(r'(\d{3})\s*cm\b')
# "3.20m", "2,82 m", "5,7m" — explicit metres
_HEIGHT_M_RE = re.compile(r'(\d[.,]\d{1,2})\s*m\b')
# "3200mm", "2800mm" — millimetres
_HEIGHT_MM_RE = re.compile(r'(\d{4})\s*mm\b')
# "+3000", "+3.000", "+3,000" — drafting marker
_HEIGHT_MARKER_RE = re.compile(r'\+\s*(\d[.,]?\d{1,3})')


def _to_metres(raw: str, unit: str) -> float | None:
    """Convert raw numeric string + unit to metres. Returns None if outside
    plausible ceiling range to keep noise out of structured data."""
    try:
        val = float(raw.replace(',', '.'))
    except ValueError:
        return None
    if unit == "cm":
        val = val / 100.0
    elif unit == "mm":
        val = val / 1000.0
    elif unit == "marker":
        # "+3000" → 3.000 m; "+3.000" → 3.000 m; "+3,2" → 3.2 m
        if val > 100:        # bare integer like 3000
            val = val / 1000.0
    if not (MIN_CEILING_M <= val <= MAX_CEILING_M):
        return None
    return val


def salvage_heights_from_warnings(
    warnings: list,
    rooms: list[dict],
) -> dict:
    """Mine height info out of Vision's free-text warnings when the
    structured `lubu_auksciai` / `lubu_auksciai_by_nr` fields stayed
    empty.

    Strategy: for each warning text, scan for room names (from
    `rooms[].pavadinimas`) that co-occur with a height pattern within
    the same warning. If a clear pairing exists, write into the
    returned dict.

    Conservative: only emits a mapping when room name + height appear
    in the SAME warning text. We don't try to be clever across multiple
    warnings or rooms.
    """
    if not warnings or not rooms:
        return {}
    result: dict[str, float] = {}

    # Index room names (case-insensitive, longest first to win against
    # partial overlaps like "Vonia" vs "Vaikų vonia").
    room_names = sorted(
        {(r.get("pavadinimas") or "").strip() for r in rooms if r.get("pavadinimas")},
        key=lambda n: -len(n),
    )

    # 2026-07-04 fix (Rangovas B GKP height-split): compound room names like
    # "Svetainė/valgomasis/virtuvė" never substring-matched warnings that name
    # only one component ("… svetainė ~3000mm iš vizualizacijos"), so the
    # narrated height was silently dropped and the room kept the 2.82 default —
    # zeroing the virš-3m GKP/paint split. Index each "/"-separated component
    # (≥5 chars, compound-separator split only — NOT whitespace, to avoid
    # generic-word false positives) as an alias for the canonical name.
    name_variants: list[tuple[str, str]] = []
    for name in room_names:
        lc = name.lower()
        name_variants.append((lc, name))
        for part in re.split(r"[/,+]", lc):
            part = part.strip()
            if len(part) >= 5 and part != lc:
                name_variants.append((part, name))
    name_variants.sort(key=lambda t: -len(t[0]))

    for w in warnings:
        if isinstance(w, dict):
            text = " ".join(filter(None, [
                w.get("message"),
                w.get("code"),
            ])) or ""
        else:
            text = str(w)
        if not text:
            continue

        # Collect every plausible height value from this single warning
        heights: list[float] = []
        for m in _HEIGHT_MARKER_RE.finditer(text):
            v = _to_metres(m.group(1), "marker")
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_M_RE.finditer(text):
            v = _to_metres(m.group(1), "m")
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_CM_RE.finditer(text):
            v = _to_metres(m.group(1), "cm")
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_MM_RE.finditer(text):
            v = _to_metres(m.group(1), "mm")
            if v is not None:
                heights.append(v)

        if not heights:
            continue

        # Pick the height most likely to be the "main" reading in this
        # warning: max value (since the bug being salvaged is
        # always "Vision saw a non-default height" — the default 2.82
        # would not have been worth narrating).
        height = max(heights)

        # Find every room name mentioned in this warning text.
        # Apply the height to all rooms named here. If none named,
        # try paskirtis-based generic phrases ("vonios", "gyvenamosios").
        text_lc = text.lower()
        matched_rooms: list[str] = []
        for variant, canonical in name_variants:
            if variant in text_lc and canonical not in matched_rooms:
                matched_rooms.append(canonical)

        # Paskirtis-based fallback. Generic phrases like "visose voniose"
        # or "gyvenamoms patalpoms" map to all rooms with the matching
        # paskirtis. Order matters: more-specific phrases first.
        if not matched_rooms:
            paskirtis_phrases = {
                "vonia": ["voniose", "vonios", "vonioje", "vonioms",
                          "san. mazgu", "san. mazguose"],
                "wc": ["wc", "tualet"],
                "virtuve": ["virtuv"],
                "gyvenamoji": ["gyvenamiems patalp", "gyvenamomis", "gyvenamose"],
                "miegamoji": ["miegam"],
                "koridorius": ["koridor"],
                "skalbykla": ["skalb"],
                "garazas": ["garaž"],
            }
            for canonical_p, triggers in paskirtis_phrases.items():
                if not any(t in text_lc for t in triggers):
                    continue
                for room in rooms:
                    name = (room.get("pavadinimas") or "").strip()
                    room_p = (room.get("paskirtis") or "").lower()
                    if not name or name in result:
                        continue
                    # Match by paskirtis OR by name keyword (e.g.
                    # "vonia" room named "Vaikų san. mazgas" has
                    # paskirtis "vonia" or "san_mazgas")
                    if canonical_p in room_p or any(
                        t in name.lower() for t in triggers
                    ):
                        matched_rooms.append(name)

        for name in matched_rooms:
            # First match wins per room — keep the height from the
            # warning that explicitly named it.
            result.setdefault(name, height)

    return result

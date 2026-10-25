"""Row provenance — no sąmata row may carry a quantity a model guessed or a default invented (v4 Phase 3b).

Plan: docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md §1 R1–R3, R7. Inventory:
docs/superpowers/research/2026-10-25-row-provenance-inventory.md.

Every row the builder emits gets a class in `_kilme`:

    drawing   — read off the drawing: the text layer (room table, legends, notes, height markers, door
                schedule), the geometry lane (outlines, perimeters summed from dimension strings, drawn
                openings, floor coverings), the vector symbol counter — or the person's own entry;
    derived   — a formula over drawing facts with a named convention (waste, material norms, one lump per
                project, a scope choice he can change);
    model-3c  — a reader of a table or a text image (apdailos, doors, sanitary fixtures, wall elevations)
                that Phase 3c reduces to the text layer; left as it is in 3b;
    blank     — no legal source: kiekis None, the row stays in the sąmata with „—" and a reason sentence
                that says what to check (`_assumption`, and the same sentence in `_tuscia_priezastis`).

`model` and `default` are never left on a row with a number: the builder blanks them (this module's
`blank`), and `test_kill_model_rows_2026_10_25` asserts it over the cold run of objektas_i and the corpus.

A room's two inputs that most rows rest on are classified here too: its perimeter (`perimeter_class`) and
its height (`height_class`). A per-room row is blanked while any room behind it has an input that is not
legal — the reason names those rooms and says what the read rooms add up to.

Pure, no I/O, never raises on odd input.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

KILME_KEY = "_kilme"
REASON_KEY = "_tuscia_priezastis"
DRAWING, DERIVED, MODEL_3C, BLANK = "drawing", "derived", "model-3c", "blank"
# the two classes a row with a number may never carry (the guard test reads these)
ILLEGAL = ("model", "default")
BLANK_SALTINIS = "checklist"          # the existing shape of a row he fills in (export drops it unfilled)

# ── perimeter ──────────────────────────────────────────────────────────────
# Read: the plan's dimension strings (summed or paired), the room table, an outline the lane traced or he
# drew, his own entry. An outline's length (`konturo_ivertis`, an open space's share) is geometry, not a
# guess. Anything else — Pass-1's figure, a zoomed re-read, the square from the area — is not.
READ_PERIMETERS = frozenset({
    "matmenu_eilutes", "plano_matmenys", "eksplikacija", "sienu_konturas", "user_override", "manual",
    "konturo_ivertis", "atviros_erdves_ivertis",
})
# ── height ─────────────────────────────────────────────────────────────────
# Read: an altitude printed inside the room, a height the plan states, his own entry. `section_average`
# is legal only when the project height it copies was read from the drawing's text (the section marker).
READ_HEIGHTS = frozenset({"ceiling_plan_marker", "plano_uzrasas", "user_override", "manual"})
PROJECT_HEIGHT_FROM_TEXT = "pjuvio_zymuo"                    # parsed["_lubu_aukstis_saltinis"]
SECTION_MARKER_WARNING = "ceiling_height_from_section_marker"
SAME_AS_OTHERS = "kaip_kitose"                                # room["lubu_aukstis_saltinis"] the fill writes


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def lt2(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",")


def _rooms_list(nrs: list[str], limit: int = 8) -> str:
    shown = nrs[:limit]
    return ", ".join(shown) + ("…" if len(nrs) > limit else "")


def perimeter_class(room: dict) -> str:
    """DRAWING when the room's wall length comes from the drawing or from him, else `model` (a figure with
    no source: Pass-1's, a zoomed re-read) or `default` (nothing at all — the square from the area)."""
    src = str(room.get("perimetras_saltinis") or "").strip().lower()
    if src in READ_PERIMETERS and (_f(room.get("perimetras_m")) or 0) > 0:
        return DRAWING
    if (_f(room.get("_perimetras_ivertis_m")) or 0) > 0:
        return DRAWING                      # the outline's own length, the lane's estimate to accept
    if (_f(room.get("perimetras_m")) or 0) > 0:
        return "model"
    return "default"


def project_height_read(parsed: dict) -> bool:
    """Was the project-wide height read from the drawing's text (a section marker)?"""
    if str(parsed.get("_lubu_aukstis_saltinis") or "") == PROJECT_HEIGHT_FROM_TEXT:
        return True
    for w in parsed.get("warnings") or []:
        if isinstance(w, dict) and w.get("code") == SECTION_MARKER_WARNING:
            return True
    return False


def own_heights(parsed: dict) -> dict[str, float]:
    """His per-room heights (`_overrides.lubu_auksciai`), by room number."""
    raw = ((parsed.get("_overrides") or {}).get("lubu_auksciai") or {}) if isinstance(parsed.get("_overrides"), dict) else {}
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            x = _f(v)
            if x and x > 0:
                out[str(k).strip()] = x
    return out


def height_class(room: dict, parsed: dict, read_values: Iterable[float] | None = None) -> str:
    """DRAWING when the room's height was read (an altitude in the room, the plan's statement, a section
    marker the project took) or he typed it; DERIVED when the room takes the height read in the other rooms
    („imu tokį pat kaip kitose"); else `model` (Pass-1's own height, a zoom) or `default` (the 2,82 m
    constant)."""
    nr = _nr(room)
    if nr and nr in own_heights(parsed):
        return DRAWING
    src = str(room.get("lubu_aukstis_saltinis") or "").strip().lower()
    h = _f(room.get("lubu_aukstis_m"))
    if src in READ_HEIGHTS and h:
        return DRAWING
    if src == "section_average" and h and project_height_read(parsed):
        return DRAWING
    if src == SAME_AS_OTHERS and h:
        return DERIVED
    vals = [v for v in (read_values or []) if v]
    if h and vals and abs(h - Counter(round(v, 2) for v in vals).most_common(1)[0][0]) < 0.005:
        return DERIVED                     # same as the rooms where it was read
    if src in ("section_pjuvis", "ceiling_plan_annotation", "per_room", "zoom") and h:
        return "model"
    return "default"


def read_heights(rooms: list[dict], parsed: dict) -> list[float]:
    """Heights read off the drawing (or typed) in this project's rooms."""
    out = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        if height_class(r, parsed, None) == DRAWING:
            h = own_heights(parsed).get(_nr(r)) or _f(r.get("lubu_aukstis_m"))
            if h:
                out.append(h)
    return out


def fill_heights_from_read(rooms: list[dict], parsed: dict) -> int:
    """The paid reading's height pass (2026-10-25): a room whose height was not read takes the height read in
    the other rooms („imu tokį pat kaip kitose", the existing question); with no height read anywhere the room
    keeps no height at all — the walls wait for his answer. Returns the number of rooms changed."""
    vals = read_heights(rooms, parsed)
    common = Counter(round(v, 2) for v in vals).most_common(1)[0][0] if vals else None
    n = 0
    for r in rooms:
        if not isinstance(r, dict):
            continue
        cls = height_class(r, parsed, None)
        if cls == DRAWING:
            continue
        if common is not None:
            if _f(r.get("lubu_aukstis_m")) != common or r.get("lubu_aukstis_saltinis") != SAME_AS_OTHERS:
                r["lubu_aukstis_m"] = common
                r["lubu_aukstis_saltinis"] = SAME_AS_OTHERS
                n += 1
        elif r.get("lubu_aukstis_m") is not None or r.get("lubu_aukstis_saltinis") != "nera":
            if r.get("lubu_aukstis_m") is not None:
                r.setdefault("_lubu_aukstis_modelio", r.get("lubu_aukstis_m"))
            r["lubu_aukstis_m"] = None
            r["lubu_aukstis_saltinis"] = "nera"
            n += 1
    return n


# ── blanking ───────────────────────────────────────────────────────────────

_LEDGER = ("contributions", "excluded", "roll_up", "contributions_sum_to_total")
_MATERIAL = ("medziagos_aprasymas", "medziagos_kiekis", "medziagos_vnt", "_medziagos")


def blank(row: dict, reason: str, why_by_room: dict[str, str] | None = None) -> dict:
    """The row stays, its quantity goes: kiekis None, „—" on screen, the reason says what to check.

    Its ledger stays as evidence without a number: no contribution (a room's share of an unknown total is not
    shown), every room that was behind the row listed under `excluded` with why (`why_by_room[nr]`, else the
    row's reason), an empty `roll_up`. Its materials stay as names with no quantity (`medziagos_kiekis` None,
    `_medziagos[].kiekis` None) — the Medžiagos rows keep their place, their id and his price."""
    rooms = [c for c in (row.get("contributions") or []) if isinstance(c, dict)]
    excluded = [dict(e) for e in (row.get("excluded") or []) if isinstance(e, dict)]
    seen = {str(e.get("room_nr") or "") for e in excluded}
    for c in rooms:
        nr = str(c.get("room_nr") or "")
        if nr in seen:
            continue
        seen.add(nr)
        excluded.append({"room_nr": nr, "room_name": c.get("room_name") or "",
                         "excluded_because": (why_by_room or {}).get(nr) or reason})
    row["kiekis"] = None
    row["saltinis"] = BLANK_SALTINIS
    row["confidence"] = "low"
    row[KILME_KEY] = BLANK
    row[REASON_KEY] = reason
    row["_assumption"] = reason
    row.pop("_confidence_reason", None)
    row["contributions"] = []
    row["excluded"] = excluded
    row["roll_up"] = []
    row["contributions_sum_to_total"] = False
    if row.get("medziagos_aprasymas"):
        row["medziagos_kiekis"] = None
    else:
        row.pop("medziagos_kiekis", None)
    if isinstance(row.get("_medziagos"), list):
        row["_medziagos"] = [{**m, "kiekis": None} for m in row["_medziagos"] if isinstance(m, dict)]
    return row


def tag(row: dict, kilme: str) -> dict:
    row[KILME_KEY] = kilme
    return row


# Rows whose quantity is a per-room sum over the room's perimeter and/or height (inventory B rows 1, 2, 6, 7,
# 10, 11, 17-walls, 19, 20, 24, 43). Matched by label prefix after the paint consolidation.
PERIMETER_AND_HEIGHT = (
    "Sienų glaistymas/dažymas", "Sienų šlifavimas", "Sienų lyginimas Knauf Rotband", "Dažymo kampų montavimas",
)
PERIMETER_ONLY = (
    "Grindjuosčių sumontavimas", "Grindjuosčių dažymas", "Lubų karnizo sumontavimas", "Lubų karnizo dažymas",
    "Silikonavimas tarp plytelių zonos", "Plytelių vidinių kampų silikonavimas", "Plytelių 45° pjovimas",
    "Plytelių grindjuosčių supjovimas", "Vonios sienų plytelių", "Virtuvės atatvaro plytelių", "Kitų sienų plytelių",
    "Hidroizoliacinė juosta kampams",       # rules/rows.hidro_two_rows: the wet rooms' gross perimeter
)
HEIGHT_ONLY = (
    "Pastolių nuoma", "Lubų glaistymas/dažymas (virš 3", "Lubų glaistymas/dažymas (iki 3",
)


def _deps(label: str) -> tuple[bool, bool] | None:
    if label.startswith(PERIMETER_AND_HEIGHT):
        return True, True
    if label.startswith(PERIMETER_ONLY):
        return True, False
    if label.startswith(HEIGHT_ONLY):
        return False, True
    return None


# Perimeter classes a per-room row may not rest on: Pass-1's figure and the zoomed re-read are a model
# reading pixels (R2), the square from the area a default (R7). A room with no outline and no strings
# keeps its rows blank until the lane or he gives the walls.
ILLEGAL_PERIMETERS = ("model", "default")


def gate_room_inputs(pozicijos: list[dict], rooms: list[dict], parsed: dict,
                     rooms_for: Any = None) -> int:
    """Blank every per-room row while a room behind it rests on a perimeter or height the drawing did not
    give. `rooms_for(row)` → the room numbers behind a row (default: its ledger's contributions). A row
    anchored on the drawing's own total (a legend, `_kilme` already DRAWING) is left alone. Returns the
    number of rows blanked."""
    by_nr = {_nr(r): r for r in rooms if isinstance(r, dict)}
    read_h = read_heights(rooms, parsed)
    n = 0
    for p in pozicijos:
        if not isinstance(p, dict) or p.get(KILME_KEY) == BLANK:
            continue
        label = str(p.get("aprasymas") or "")
        tier = "(iki 3" in label or "(virš 3" in label
        if p.get(KILME_KEY) == DRAWING and not tier:
            continue                         # the drawing's own total, no height split in it
        kiekis = p.get("kiekis")
        if not isinstance(kiekis, (int, float)) or isinstance(kiekis, bool):
            continue
        deps = _deps(label)
        if deps is None:
            continue
        need_p, need_h = deps
        if p.get(KILME_KEY) == DRAWING:
            # a drawing total split into height tiers: the total is read, the split rests on the heights
            need_p, need_h = False, True
        nrs = rooms_for(p) if rooms_for else [str(c.get("room_nr") or "") for c in (p.get("contributions") or [])]
        bad_p, bad_h, good = [], [], []
        for nr in nrs:
            r = by_nr.get(nr)
            if r is None:
                continue
            pc = perimeter_class(r) if need_p else DRAWING
            hc = height_class(r, parsed, read_h) if need_h else DRAWING
            if pc in ILLEGAL_PERIMETERS:
                bad_p.append(nr)
            if hc not in (DRAWING, DERIVED):
                bad_h.append(nr)
            if pc not in ILLEGAL_PERIMETERS and hc in (DRAWING, DERIVED):
                good.append(nr)
        if not bad_p and not bad_h:
            tag(p, DERIVED)
            continue
        parts = []
        if bad_p:
            parts.append(f"patalpose {_rooms_list(bad_p)} perimetras neperskaitytas — nubrėžkite kontūrą "
                         "arba įveskite sienų ilgį")
        if bad_h:
            if len(bad_h) == len([x for x in nrs if x in by_nr]) and not read_h:
                parts.append("lubų aukščio brėžinyje neradau — atsakykite klausimą „Kokio aukščio lubos?“")
            else:
                parts.append(f"patalpose {_rooms_list(bad_h)} aukštis neperskaitytas — įrašykite lubų aukštį")
        reason = "; ".join(parts)
        reason = reason[0].upper() + reason[1:] + ". Kol to nėra, kiekio neskaičiuoju."
        why: dict[str, str] = {}
        for nr in good:
            why[nr] = "Šios patalpos įvestys iš brėžinio, bet eilutė laukia kitų patalpų"
        for nr in bad_h:
            why[nr] = "Aukštis neperskaitytas — įrašykite lubų aukštį"
        for nr in bad_p:
            why[nr] = "Perimetras neperskaitytas — nubrėžkite kontūrą arba įveskite sienų ilgį"
        blank(p, reason, why)
        n += 1
    return n


def blank_followers(pozicijos: list[dict], skip_prefixes: tuple[str, ...] = ()) -> int:
    """A row bought FOR a blanked work row (`susijes_darbas` names it) is blank with it — unless it is
    counted on its own (`skip_prefixes`)."""
    gone = {str(p.get("aprasymas") or "").strip() for p in pozicijos
            if isinstance(p, dict) and p.get(KILME_KEY) == BLANK}
    n = 0
    for p in pozicijos:
        if not isinstance(p, dict) or p.get(KILME_KEY) == BLANK:
            continue
        if skip_prefixes and str(p.get("aprasymas") or "").startswith(skip_prefixes):
            if str(p.get("susijes_darbas") or "").strip() in gone:
                p.pop("susijes_darbas", None)       # its own count stays where he reads it, not under a blank row
            continue
        parent = str(p.get("susijes_darbas") or "").strip()
        if parent and parent in gone and isinstance(p.get("kiekis"), (int, float)):
            blank(p, f"Kiekis seka eilutę „{parent}“ — kol ji tuščia, šios eilutės kiekio nėra; įrašykite jį pagal tą eilutę.")
            n += 1
    return n


# `saltinis` values that ARE a provenance statement: a count by room type is a default, the plumbing
# reader's count is a 3c reader.
_SALTINIS_CLASS = {"paskirtis_default": "default", "project_assumption": "default"}


def stamp_remaining(pozicijos: list[dict]) -> None:
    """Every row the builder did not classify itself: a number with a stated source is `derived`
    (a formula over drawing facts) unless its `saltinis` says it is a room-type default; a row with no
    number is `blank`."""
    for p in pozicijos:
        if not isinstance(p, dict) or p.get(KILME_KEY):
            continue
        k = p.get("kiekis")
        if k is None:
            p[KILME_KEY] = BLANK
        else:
            p[KILME_KEY] = _SALTINIS_CLASS.get(str(p.get("saltinis") or ""), DERIVED)


def illegal_rows(pozicijos: list[dict]) -> list[dict]:
    """Rows that still carry a number while classed `model` or `default` — must be empty."""
    return [p for p in pozicijos if isinstance(p, dict) and p.get(KILME_KEY) in ILLEGAL
            and p.get("kiekis") is not None]


# ── sentences of the rows that are blank by construction (plain LT, say what to check) ──────────────────

LED_NO_LEGEND_LT = ("LED nišų ilgio brėžinio legendoje neradau — įrašykite ilgį pagal lubų planą "
                    "(nišos užuolaidoms ir LED juostoms).")
DUCTS_LT = "Ortakių trasų ilgio brėžinyje nėra — įrašykite ilgį ir skersmenį pagal vėdinimo planą."
DUCTS_INSULATION_LT = "Izoliuojamų ortakių ilgio brėžinyje nėra — įrašykite pagal vėdinimo planą."
DUCTS_FIXING_LT = "Ortakių tvirtinimų kiekio brėžinyje nėra — įrašykite pagal ortakių ilgį."
RUBBISH_LT = "Statybinių atliekų kiekio brėžinys nenurodo — įrašykite, kiek m³ išvešite."


def protection_lt(floor_m2: float) -> str:
    return ("Kiek ploto dengsite apsauginėmis dangomis, brėžinys nenurodo — įrašykite plotą. "
            f"Visų patalpų grindų plotas — {lt2(floor_m2)} m².")


def _fold(s: Any) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "").lower()) if not unicodedata.combining(c))


def led_legend_length(parsed: dict) -> dict | None:
    """The LED strip length the drawing's legend states (`_autoriaus_kiekiai`, family „led", metres), without
    the plastered-in („priglaistoma") strip, which the sentence names apart. None when the legend states none."""
    figs = [f for f in (parsed.get("_autoriaus_kiekiai") or [])
            if isinstance(f, dict) and f.get("family") == "led" and f.get("unit") == "m" and _f(f.get("value"))]
    main = [f for f in figs if "priglaist" not in _fold(f.get("label"))]
    flush = [f for f in figs if "priglaist" in _fold(f.get("label"))]
    if not main:
        return None
    seen: set[tuple] = set()
    total = 0.0
    parts = []
    for f in main:
        key = (_fold(f.get("label")).strip(" -–;:"), round(float(f["value"]), 2))
        if key in seen:
            continue
        seen.add(key)
        total += float(f["value"])
        label = str(f.get("label") or "").strip(" -–;:")
        parts.append(f"„{label} – {lt2(f['value'])} m“ (lapas {f.get('page')})")
    sakinys = "Ilgis — iš brėžinio legendos: " + "; ".join(parts) + "."
    if flush:
        g = flush[0]
        sakinys += (f" Legendoje atskirai: „{str(g.get('label') or '').strip(' -–;:')}“ — {lt2(g['value'])} m; "
                    "jei ir ją glaistote nišoje, pridėkite.")
    return {"m": round(total, 2), "sakinys": sakinys}

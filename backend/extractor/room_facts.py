"""The room check sheet — six facts the pipeline read, and what they cost.

WHY (2026-09-04, founder direction after the council): *"We may never reach
100 % accuracy, so perfect the CHECKING so it still saves time — not with AI
dots, with normal explanations showing how, where, what."* A confidence dot
tells a contractor nothing he can act on. A crop of the eksplikacija row next
to the sentence „Iš eksplikacijos lentelės, eilutė 110" tells him everything in
one glance, and he either nods or fixes it.

So this module answers, for ONE room, two questions:

    1. What did you read?  — six facts (plotas, perimetras, aukštis, apdaila,
       angos, grindys), each with the value, a plain-Lithuanian source
       sentence, the page, and the rectangle whose pixels back it up.
    2. What does that cost? — every sąmata line this room contributes to,
       straight out of the contribution ledger, with the formula in real
       numbers.

TWO RULES THIS MODULE EXISTS TO KEEP
────────────────────────────────────
**Nothing is reverse-engineered.** The quantities come from
`darbu_sarasas[].contributions`, which the BUILDER emitted (`extractor/
ledger.py`). We never re-derive which rooms a line covers by matching words in
its label — that is exactly how the retired `interior_v8/_build_trace_links`
drifted, and the ledger docstring says so. A family with no ledger is reported
as having none, not guessed at.

**`source.kind` and `source.page` answer different questions.** `kind` is where
the VALUE came from. `page` + `rect_pct` are where the contractor should LOOK.
They are usually the same place, and deliberately are not for openings: the
sizes come from the durų žinynas, but the count is checked on the room's own
plan, so `kind` says `duru_zinynas` while the crop frames the room. Conflating
them would either hide the provenance or show him the wrong sheet.

WHAT THE DRAWING CANNOT ANSWER (stated, never faked)
────────────────────────────────────────────────────
· Openings carry no coordinates anywhere in the pipeline — `elementai` is
  `{tipas, kiekis, plotis_mm, aukstis_mm}`. The crop is the room, not the
  opening.
· A finish has a page but never a rectangle. Since 2026-09-04 the apdailos
  merge stamps `_apdailos_page` on each room it updates; before that only the
  project-level `_meta.apdailos_page` existed, and older blobs fall back to
  the first classified `finish_schedule` / `wall_elevation` sheet.
· The floor finish is not read at all: it is `ROOM_TYPE_RULES[paskirtis]
  ["floor"]`. That fact is therefore `assumed` on every room that has no
  explicit override, and the sentence says so.
"""
from __future__ import annotations

from typing import Any

from .page_classifier import canonical_tipas

# ── the six facts, in the order the check sheet walks them ──────────────────
FACT_KEYS = ("plotas", "perimetras", "aukstis", "apdaila", "angos", "grindys")

SOURCE_KINDS = ("eksplikacija", "planas", "pjuvis", "apdailos_lentele",
                "duru_zinynas", "grindu_planas", "prielaida", "nera")
STATUSES = ("read", "assumed", "missing")

# How far around a single printed marker to crop, as a fraction of the page.
# A height marker is a five-character string; ±6 % of the page around it shows
# the marker AND the room number it belongs to, which is what makes it
# checkable rather than merely visible.
MARKER_MARGIN_PCT = 0.06
# Same idea for a room whose only anchor is its printed number.
ROOM_MARKER_MARGIN_PCT = 0.10


def lt_num(v: float | int | None, digits: int = 2) -> str:
    """`165.61` → `165,61` — LT decimal comma, for strings the user reads."""
    if v is None:
        return "—"
    return f"{float(v):.{digits}f}".replace(".", ",")


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ── geometry ────────────────────────────────────────────────────────────────

def normalize_polygon(poly: Any) -> list[list[float]] | None:
    """`polygon_pct` in either shape → `[[x, y], …]`.

    Two producers disagree: Vision emits `[{"x":…, "y":…}, …]` (its own
    schema), while the flood-fill and the bbox synthesiser emit pairs. Callers
    downstream index positionally, so a dict-shaped polygon raises `KeyError`
    deep inside them. Normalise once, here.
    """
    if not isinstance(poly, (list, tuple)) or not poly:
        return None
    out: list[list[float]] = []
    for p in poly:
        if isinstance(p, dict):
            x, y = _f(p.get("x")), _f(p.get("y"))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            x, y = _f(p[0]), _f(p[1])
        else:
            continue
        if x is None or y is None:
            continue
        out.append([x, y])
    return out if len(out) >= 3 else None


def _marker_xy(room: dict) -> tuple[float, float] | None:
    m = room.get("marker_pct")
    if isinstance(m, (list, tuple)) and len(m) >= 2:
        x, y = _f(m[0]), _f(m[1])
        if x is not None and y is not None:
            return x, y
    return None


def room_region_pct(room: dict) -> list[float] | None:
    """The rectangle that frames this room on its own page, in page-percent.

    Preference order mirrors what the drawing can actually support: a traced
    outline, else the printed room number ± a margin, else the coarse Vision
    box. `None` means we cannot point at this room at all — the check sheet
    must say that rather than crop an arbitrary corner.
    """
    poly = normalize_polygon(room.get("polygon_pct"))
    if poly:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return [min(xs), min(ys), max(xs), max(ys)]
    mk = _marker_xy(room)
    if mk:
        x, y = mk
        m = ROOM_MARKER_MARGIN_PCT
        return [x - m, y - m, x + m, y + m]
    bb = room.get("bbox_pct")
    if isinstance(bb, dict):
        x, y = _f(bb.get("x")), _f(bb.get("y"))
        w, h = _f(bb.get("w")), _f(bb.get("h"))
        if None not in (x, y, w, h):
            return [x, y, x + w, y + h]
    return None


def _clamp_rect(rect: list[float] | None) -> list[float] | None:
    if not rect or len(rect) != 4:
        return None
    x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in rect)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def region_on_page(room: dict, page: Any, region: list[float] | None
                   ) -> list[float] | None:
    """`region`, but ONLY if `page` is the page it was measured on.

    A rectangle is meaningless on a different sheet. Handing the room's own
    outline to a crop of the pjūvis or the apdailų lentelė would frame an
    arbitrary corner of an unrelated drawing — the precise failure the
    browser-side highlight had in 2026-05. When the pages differ the caller
    gets `None` and the crop falls back to the whole sheet, which is honest:
    "read this drawing", not "look exactly here".
    """
    if region is None or page is None:
        return None
    room_page = room.get("puslapio_nr")
    if room_page is None:
        return None
    try:
        if int(page) != int(room_page):
            return None
    except (TypeError, ValueError):
        return None
    return region


def _bbox_pdf_to_pct(bbox: Any, w: Any, h: Any) -> list[float] | None:
    """`eksplikacija_row_bbox` → page-percent.

    The bbox is a raw `pdfplumber Table.rows[i].bbox`, i.e. `[x0, top, x1,
    bottom]` in PDF points measured from the page TOP — the same origin
    pdf2image rasterises from, so the conversion is a plain division and no
    y-flip. (The 2026-05 browser-side attempt got this wrong in the other
    direction and flashed highlights in arbitrary spots.)
    """
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    W, H = _f(w), _f(h)
    if not W or not H:
        return None
    x0, top, x1, bottom = (_f(v) for v in bbox)
    if None in (x0, top, x1, bottom):
        return None
    return _clamp_rect([x0 / W, top / H, x1 / W, bottom / H])


# ── page lookups ────────────────────────────────────────────────────────────

def first_page_of_type(project: dict, *tipai: str) -> int | None:
    """The first classified page whose canonical type is one of `tipai`."""
    wanted = {canonical_tipas(t) for t in tipai}
    for p in project.get("puslapiai") or []:
        if not isinstance(p, dict):
            continue
        if canonical_tipas(p.get("tipas")) in wanted:
            nr = _f(p.get("nr"))
            if nr:
                return int(nr)
    return None


def _eksplikacija_page(project: dict, room: dict | None = None) -> int | None:
    """The page the room table was actually READ from.

    Preference order matters. The room's own `eksplikacija_source_page` (since
    2026-09-04) travels with its row bbox; `_eksplikacija`'s is the same
    deterministic reader's. The TOP-LEVEL `eksplikacija_source_page` is
    Vision's separate guess and is the last resort — on one corpus project it
    says 1 where the reader read 2, so trusting it first would crop the wrong
    sheet with a rectangle that still looked plausible.
    """
    if room is not None:
        nr = _f(room.get("eksplikacija_source_page"))
        if nr:
            return int(nr)
    eks = project.get("_eksplikacija")
    if isinstance(eks, dict):
        nr = _f(eks.get("eksplikacija_source_page"))
        if nr:
            return int(nr)
    nr = _f(project.get("eksplikacija_source_page"))
    if nr:
        return int(nr)
    return first_page_of_type(project, "eksplikacija")


def _eksplikacija_row(project: dict, room: dict) -> dict | None:
    """The parsed table row this room was joined to, if we can still find it.

    `eksplikacija_row_idx` is the join the merge recorded; the row carries its
    own `page`, which is the only per-row page the pipeline has.
    """
    eks = project.get("_eksplikacija")
    if not isinstance(eks, dict):
        return None
    rows = eks.get("patalpos") or []
    idx = room.get("eksplikacija_row_idx")
    if idx is not None:
        for r in rows:
            if isinstance(r, dict) and r.get("row_idx") == idx:
                return r
    nr = str(room.get("nr") or "").strip()
    if nr:
        for r in rows:
            if isinstance(r, dict) and str(r.get("nr") or "").strip() == nr:
                return r
    return None


def _row_page(project: dict, room: dict, row: dict | None) -> int | None:
    """The eksplikacija page for THIS room, best source first.

    The room's own `eksplikacija_source_page` wins because it was stamped at
    merge time against the row this room was actually joined to. `row` here is
    a re-join by `row_idx`, falling back to `nr` — and a project with repeated
    room numbers can re-join to a different row than the merge did.
    """
    stamped = _f(room.get("eksplikacija_source_page"))
    if stamped:
        return int(stamped)
    if isinstance(row, dict):
        page = _f(row.get("page"))
        if page:
            return int(page)
    return _eksplikacija_page(project, room)


# ── one fact ────────────────────────────────────────────────────────────────

def _fact(key: str, value: Any, unit: str | None, status: str,
          kind: str, page: int | None, rect: list[float] | None,
          sentence: str, editable: dict | None,
          **extra: Any) -> dict:
    return {
        "key": key,
        "value": value,
        "unit": unit,
        "status": status,
        "source": {"kind": kind, "page": page, "rect_pct": _clamp_rect(rect)},
        "sentence": sentence,
        "crop_url": None,          # filled by `attach_crop_urls`
        "editable": editable,
        **extra,
    }


# ── plotas ──────────────────────────────────────────────────────────────────

def _fact_plotas(project: dict, room: dict, region: list[float] | None) -> dict:
    value = _f(room.get("plotas_m2"))
    saltinis = (room.get("plotas_saltinis") or "").strip().lower()
    row = _eksplikacija_row(project, room)
    rect = _bbox_pdf_to_pct(room.get("eksplikacija_row_bbox"),
                            room.get("eksplikacija_page_width_pdf"),
                            room.get("eksplikacija_page_height_pdf"))
    label = str(room.get("nr") or room.get("pavadinimas") or "").strip()

    if value is None:
        return _fact("plotas", None, "m²", "missing", "nera",
                     room.get("puslapio_nr"), region,
                     "Ploto brėžinyje neradau — įrašykite jį patys.",
                     {"field": "plotas_m2", "kind": "number"})

    if saltinis == "eksplikacija" or (room.get("plotas_source") == "eksplikacija"):
        page = _row_page(project, room, row)
        sentence = ("Iš patalpų eksplikacijos lentelės"
                    + (f", eilutė {label}." if label else "."))
        return _fact("plotas", round(value, 2), "m²", "read", "eksplikacija",
                     page, rect or region_on_page(room, page, region), sentence,
                     {"field": "plotas_m2", "kind": "number"})

    if saltinis == "inline_label":
        return _fact("plotas", round(value, 2), "m²", "read", "planas",
                     room.get("puslapio_nr"), region,
                     "Plotas užrašytas plane šalia patalpos.",
                     {"field": "plotas_m2", "kind": "number"})

    if saltinis == "wall_dim_calc":
        return _fact("plotas", round(value, 2), "m²", "read", "planas",
                     room.get("puslapio_nr"), region,
                     "Plotas suskaičiuotas iš plane pažymėtų matmenų.",
                     {"field": "plotas_m2", "kind": "number"})

    return _fact("plotas", round(value, 2), "m²", "assumed", "prielaida",
                 room.get("puslapio_nr"), region,
                 f"Ploto lentelėje neradau — skaičiuoju su {lt_num(value)} m². "
                 "Įrašykite tikrą.",
                 {"field": "plotas_m2", "kind": "number"})


# ── perimetras ──────────────────────────────────────────────────────────────

def _fact_perimetras(project: dict, room: dict,
                     region: list[float] | None) -> dict:
    measured = _f(room.get("perimetras_m"))
    used = _f(room.get("_walls_perimetras_m"))
    floored = bool(room.get("_perimetras_floor_applied"))
    editable = {"field": "perimetras_m", "kind": "number"}
    row = _eksplikacija_row(project, room)
    from_table = isinstance(row, dict) and _f(row.get("perimetras_m")) is not None

    # The wall paint is billed off `_walls_perimetras_m`, which is a longer,
    # rectangle-shaped floor whenever the AREA itself was synthetic. He is
    # billed for that number, so he is told it — in the sentence, not in a
    # footnote.
    tail = ""
    if floored and used and measured and abs(used - measured) > 0.01:
        tail = (f" Sienų plotui naudoju {lt_num(used)} m — patalpos kontūras "
                "brėžinyje nepažymėtas, todėl imu stačiakampio perimetrą.")

    if measured is None:
        if used is None:
            return _fact("perimetras", None, "m", "missing", "nera",
                         room.get("puslapio_nr"), region,
                         "Perimetro brėžinyje neradau — įrašykite jį patys.",
                         editable)
        return _fact("perimetras", round(used, 2), "m", "assumed", "prielaida",
                     room.get("puslapio_nr"), region,
                     f"Perimetro brėžinyje neradau — skaičiuoju iš ploto "
                     f"({lt_num(used)} m). Įrašykite tikrą.", editable)

    if from_table:
        page = _row_page(project, room, row)
        rect = _bbox_pdf_to_pct(room.get("eksplikacija_row_bbox"),
                                room.get("eksplikacija_page_width_pdf"),
                                room.get("eksplikacija_page_height_pdf"))
        return _fact("perimetras", round(measured, 2), "m", "read",
                     "eksplikacija", page,
                     rect or region_on_page(room, page, region),
                     "Iš patalpų eksplikacijos lentelės." + tail, editable)

    return _fact("perimetras", round(measured, 2), "m", "read", "planas",
                 room.get("puslapio_nr"), region,
                 "Perimetras — pagal patalpos kontūrą plane." + tail, editable)


# ── aukštis ─────────────────────────────────────────────────────────────────

# What each `lubu_aukstis_saltinis` means for the contractor. `read` = a
# reader, a table or the user produced it; `assumed` = we chose a default.
_HEIGHT_SOURCES: dict[str, tuple[str, str, str]] = {
    "ceiling_plan_marker": ("read", "planas",
                            "Aukštis — iš lubų plane užrašytos altitudės."),
    "ceiling_plan_annotation": ("read", "planas",
                                "Aukštis — iš lubų plane užrašytos altitudės."),
    "section_pjuvis": ("read", "pjuvis", "Aukštis — iš pjūvio."),
    "per_room": ("read", "planas", "Aukštis užrašytas prie šios patalpos."),
    "user_override": ("read", "prielaida", "Šį aukštį įrašėte patys."),
    "section_average": ("assumed", "pjuvis",
                        "Prie šios patalpos aukščio neradau — imu tokį pat "
                        "kaip kitose patalpose. Įrašykite tikrą."),
    "height_gate_reattributed": ("assumed", "prielaida",
                                 "Prie šios patalpos aukščio neradau — imu "
                                 "tokį pat kaip kitose patalpose. Įrašykite "
                                 "tikrą."),
    "height_gate_clamped": ("assumed", "prielaida",
                            "Prie šios patalpos aukščio neradau — imu tokį "
                            "pat kaip kitose patalpose. Įrašykite tikrą."),
    "default_fallback": ("assumed", "prielaida", ""),
}


def _fact_aukstis(project: dict, room: dict,
                  region: list[float] | None) -> dict:
    value = _f(room.get("lubu_aukstis_m"))
    saltinis = (room.get("lubu_aukstis_saltinis") or "").strip().lower()
    editable = {"field": "lubu_auksciai", "kind": "number"}
    ev = room.get("_height_marker_evidence")

    page = None
    rect = None
    if isinstance(ev, dict):
        p = _f(ev.get("page"))
        page = int(p) if p else None
        pts = ev.get("points") or []
        pt = pts[0] if isinstance(pts, list) and pts and isinstance(pts[0], dict) else None
        if pt is not None:
            x, y = _f(pt.get("x_pct")), _f(pt.get("y_pct"))
            if x is not None and y is not None:
                m = MARKER_MARGIN_PCT
                rect = [x - m, y - m, x + m, y + m]

    status, kind, sentence = _HEIGHT_SOURCES.get(
        saltinis, ("assumed", "prielaida", ""))
    if page is None:
        page = (first_page_of_type(project, "section")
                if kind == "pjuvis"
                else first_page_of_type(project, "ceiling_plan", "section"))
        page = page or room.get("puslapio_nr")

    # The marker rectangle belongs to the marker's page; the room outline only
    # to the room's own. Never mix them.
    rect = rect or region_on_page(room, page, region)
    if value is None:
        return _fact("aukstis", None, "m", "missing", "nera", page, rect,
                     "Lubų aukščio brėžinyje neradau — įrašykite jį patys.",
                     editable)
    if not sentence:
        sentence = (f"Lubų aukščio brėžinyje neradau — skaičiuoju su "
                    f"{lt_num(value)} m. Įrašykite tikrą.")
    return _fact("aukstis", round(value, 2), "m", status, kind, page,
                 rect, sentence, editable)


# ── apdaila ─────────────────────────────────────────────────────────────────

_FINISH_LT = {
    "dazymas_share": "dažoma",
    "plyteles_share": "plytelės",
    "tapetai_share": "tapetai",
    "plokste_share": "plokštė",
    "veidrodis_share": "veidrodis",
    "molio_tinkas_share": "molio tinkas",
    "kita_danga_share": "kita danga",
}

# `_tile_read_source` → (status, source kind, what the sentence opens with)
_TILE_SOURCE = {
    "elevation": ("read", "planas", "Sienų apdaila — iš sienų išklotinių."),
    "apdailos": ("read", "apdailos_lentele", "Sienų apdaila — iš apdailų lentelės."),
    "vision_height": ("read", "planas", "Sienų apdaila — perskaityta iš brėžinio."),
    "paskirtis_default": ("assumed", "prielaida",
                          "Sienų apdailos brėžinyje neradau — parinkta pagal "
                          "patalpos paskirtį."),
    "none": ("assumed", "prielaida",
             "Sienų apdailos brėžinyje neradau — parinkta pagal patalpos "
             "paskirtį."),
}


def _walls_description(room: dict) -> str:
    """What this room's walls get — and it MUST agree with the sąmata.

    The billed truth is `walls_paintable_m2`: when it is zero the ledger
    excludes the room from every wall line, so the check sheet may not print
    „dažoma" beside it. A finish share the reader saw is shown on top of that,
    never instead of it.
    """
    if room.get("_walls_full_tile"):
        return "plytelės"
    paintable = _f(room.get("walls_paintable_m2"))
    factor = _f(room.get("_walls_paint_factor"))
    unpainted = ((paintable is not None and paintable <= 0)
                 or (factor is not None and factor <= 0))
    breakdown = room.get("sienu_apdailos_breakdown")
    parts: list[str] = []
    if isinstance(breakdown, dict):
        for key, lt in _FINISH_LT.items():
            share = _f(breakdown.get(key)) or 0.0
            if share >= 0.01:
                parts.append(f"{lt} {share * 100:.0f} %")
    if unpainted:
        return ("nedažomos (" + ", ".join(parts) + ")") if parts else "nedažomos"
    if parts:
        return ", ".join(parts)
    tile_h = _f(room.get("plyteliu_aukstis_m")) or 0.0
    if tile_h > 0:
        return f"dažoma, plytelės iki {lt_num(tile_h)} m"
    return "dažoma"


def _ceiling_description(room: dict) -> str:
    src = (room.get("_ceiling_paint_source") or "").strip().lower()
    if room.get("_stretch_ceiling") or (room.get("lubu_tipas") or "") == "itempiamos":
        return "įtempiamos"
    if src in ("override_off", "unfinished_room_standard"):
        return "nedažomos"
    paint = _f(room.get("ceiling_paintable_m2"))
    if paint is not None and paint <= 0:
        return "nedažomos"
    return "dažomos"


def _fact_apdaila(project: dict, room: dict,
                  region: list[float] | None) -> dict:
    tile_src = (room.get("_tile_read_source") or "").strip().lower()
    status, kind, opening = _TILE_SOURCE.get(
        tile_src, ("assumed", "prielaida",
                   "Sienų apdailos brėžinyje neradau — parinkta pagal "
                   "patalpos paskirtį."))
    # A breakdown on the room means the apdailų lentelė WAS read for it. On a
    # blob saved before `_tile_read_source` existed that is the only signal
    # left, and calling a read finish „parinkta pagal paskirtį" would put a
    # visible lie next to a number he can see came off the table.
    if status != "read" and isinstance(room.get("sienu_apdailos_breakdown"), dict):
        status, kind, opening = _TILE_SOURCE["apdailos"]
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    page = None
    if kind == "apdailos_lentele":
        # Per room since 2026-09-04; the project-level field is the fallback
        # for every blob written before that.
        p = _f(room.get("_apdailos_page")) or _f(meta.get("apdailos_page"))
        page = int(p) if p else None
    page = page or first_page_of_type(project, "finish_schedule", "wall_elevation")
    page = page or room.get("puslapio_nr")

    value = (f"Sienos: {_walls_description(room)}; "
             f"lubos: {_ceiling_description(room)}")
    sentence = opening
    if status == "read":
        sentence += " Lubos — patikrinkite lubų plane."
    else:
        sentence += " Patikrinkite išklotinėse arba apdailų lentelėje."
    # No per-room rectangle exists for a finish anywhere in the pipeline. When
    # the finish sheet happens to BE the room's own page the outline still
    # frames it usefully; otherwise the crop is the whole sheet and the
    # sentence says which one to read.
    return _fact("apdaila", value, None, status, kind, page,
                 region_on_page(room, page, region), sentence,
                 {"field": "walls_paint_override", "kind": "choice"})


# ── angos ───────────────────────────────────────────────────────────────────

# (singular after 1, plural after 2–9, genitive plural after 0 and 10+) —
# `durys` is plurale tantum in Lithuanian, so it never changes.
_ELEMENT_LT: dict[str, tuple[str, str, str]] = {
    "duris": ("durys", "durys", "durų"),
    "pasleptos_duris": ("paslėptos durys", "paslėptos durys", "paslėptų durų"),
    "langas": ("langas", "langai", "langų"),
    "stoglangis": ("stoglangis", "stoglangiai", "stoglangių"),
}
_OPENING_TIPAI = tuple(_ELEMENT_LT)


def element_label(tipas: str, n: int) -> str:
    forms = _ELEMENT_LT.get(tipas)
    if not forms:
        return str(tipas)
    one, few, many = forms
    tail, hundred = abs(n) % 10, abs(n) % 100
    if tail == 1 and hundred != 11:
        return one
    if 2 <= tail <= 9 and not (11 <= hundred <= 19):
        return few
    return many


def _fact_angos(project: dict, room: dict, region: list[float] | None) -> dict:
    elems = [e for e in (room.get("elementai") or [])
             if isinstance(e, dict) and (e.get("tipas") or "") in _OPENING_TIPAI]
    details = []
    per_type: dict[str, int] = {}
    total = 0
    anchored = False
    schedule_page = None
    for e in elems:
        tipas = e.get("tipas") or ""
        n = int(_f(e.get("kiekis")) or 1)
        total += n
        per_type[tipas] = per_type.get(tipas, 0) + n
        anchored = anchored or bool(e.get("_schedule_anchored"))
        # Recorded per element since 2026-09-04; older blobs fall back to the
        # classified `door_window_schedule` sheet below.
        schedule_page = schedule_page or _f(e.get("_schedule_page"))
        details.append({
            "tipas": tipas,
            "pavadinimas": element_label(tipas, n),
            "kiekis": n,
            "plotis_mm": _f(e.get("plotis_mm")),
            "aukstis_mm": _f(e.get("aukstis_mm")),
            "is_zinyno": bool(e.get("_schedule_anchored")),
        })
    editable = {"field": "elementai", "kind": "count"}

    if not details:
        return _fact("angos", 0, "vnt.", "missing", "nera",
                     room.get("puslapio_nr"), region,
                     "Durų ir langų šioje patalpoje neradau — jei jų yra, "
                     "įrašykite.", editable, details=[])

    # Summed per type, not per element: two door rows of one door each read as
    # „2 durys", the way he would say it.
    counts = ", ".join(f"{n} {element_label(t, n)}" for t, n in per_type.items())
    if anchored:
        zin = (int(schedule_page) if schedule_page
               else first_page_of_type(project, "door_window_schedule"))
        sentence = ("Durys ir langai suskaičiuoti plane; matmenys — iš "
                    "žiniaraščio"
                    + (f", psl. {zin}." if zin else "."))
        kind = "duru_zinynas"
    else:
        sentence = ("Durys ir langai suskaičiuoti plane. Brėžinys jų vietos "
                    "nenurodo, todėl pažymėti negaliu — perskaičiuokite "
                    "patalpoje.")
        kind = "planas"
    # Deliberately the ROOM's page and region, not the žiniaraštis: the count
    # is what he checks, and he checks it on his own room.
    return _fact("angos", total, "vnt.", "read", kind,
                 room.get("puslapio_nr"), region,
                 f"{counts}. {sentence}", editable, details=details)


# ── grindys ─────────────────────────────────────────────────────────────────

def _fact_grindys(project: dict, room: dict,
                  region: list[float] | None) -> dict:
    tile = _f(room.get("plyteles_grindys_m2")) or 0.0
    soft = _f(room.get("pvc_grindys_m2")) or 0.0
    override = (room.get("plyteles_grindys_m2_override") is not None
                or room.get("tile_floor_override") is not None)
    if tile > 0:
        value = "plytelės"
    elif soft > 0:
        value = "parketas arba laminatas"
    else:
        value = "betonas, be dangos"
    page = first_page_of_type(project, "floor_plan") or room.get("puslapio_nr")
    editable = {"field": "paskirtis", "kind": "choice"}
    paskirtis = (room.get("paskirtis") or "").strip()

    rect = region_on_page(room, page, region)
    if override:
        return _fact("grindys", value, None, "read", "grindu_planas", page,
                     rect, "Grindų danga pažymėta šiai patalpai.", editable)
    # Honest: no lane reads a floor finish. It follows the room's purpose.
    sentence = ("Grindų danga parinkta pagal patalpos paskirtį"
                + (f" („{paskirtis}“)." if paskirtis else ".")
                + " Patikrinkite grindų plane.")
    return _fact("grindys", value, None, "assumed", "prielaida", page, rect,
                 sentence, editable)


# ── quantities, straight out of the ledger ──────────────────────────────────

# A roll-up step that moves the number AFTER the rooms have been added up. It
# has to reach the sentence in both branches: a room's own arithmetic can be
# perfectly explained and still not be what the line bills, and a contractor
# who is shown „= 16,50 m" while the sąmata carries less has been misled.
_ROLL_UP_NOTE = {
    "cap": "bendra eilutė apribota, todėl į sąmatą patenka mažiau",
    "anchor": "bendras kiekis imamas iš eksplikacijos lentelės",
    "share": "eilutė padalinta pagal aukštį",
}


def _roll_up_note(row: dict) -> str:
    for step in (row.get("roll_up") or []):
        note = _ROLL_UP_NOTE.get((step or {}).get("op"))
        if note:
            return f" ({note})"
    return ""


def formula_sentence(contribution: dict, row: dict) -> str | None:
    """The room's own arithmetic, in real numbers, in Lithuanian.

    With `terms` this is the actual addition the engine performed —
    „vidiniai kampai 11,20 + angų atbrailos 15,00 + perimetras 13,50 =
    48,10 m". Without them (the paint family emits none today) it states the
    share honestly instead of inventing a decomposition.
    """
    value = _f(contribution.get("value"))
    if value is None:
        return None
    unit = contribution.get("unit") or ""
    unit = {"m2": "m²", "b/m": "m"}.get(unit, unit)
    tail = _roll_up_note(row)
    terms = contribution.get("terms")
    if isinstance(terms, dict) and terms:
        pieces = []
        for i, (label, raw) in enumerate(terms.items()):
            v = _f(raw)
            if v is None:
                continue
            sign = "−" if v < 0 else ("+" if i else "")
            joiner = f" {sign} " if sign else ""
            pieces.append(f"{joiner}{label} {lt_num(abs(v))}")
        if pieces:
            return (f"{''.join(pieces).strip()} = {lt_num(value)} "
                    f"{unit}{tail}").strip()

    total = _f(row.get("kiekis"))
    if total is None:
        return None
    return (f"Iš šios patalpos {lt_num(value)} {unit}; "
            f"visa eilutė {lt_num(total)} {unit}{tail}").strip()


def _ledgered_rows(project: dict) -> list[dict]:
    return [r for r in (project.get("darbu_sarasas") or [])
            if isinstance(r, dict) and r.get("roll_up")]


def room_quantities(project: dict, room_nr: str) -> tuple[list[dict], list[dict]]:
    """(`quantities`, `excluded`) for one room, from `darbu_sarasas` only.

    Never from `pozicijos`: the compat emit MOVES the ledger onto
    `darbu_sarasas` and strips it off `pozicijos`, so a stored blob has none
    there. And never re-derived from labels — see the module docstring.
    """
    target = str(room_nr).strip()
    quantities: list[dict] = []
    excluded: list[dict] = []
    for row in _ledgered_rows(project):
        for c in (row.get("contributions") or []):
            if not isinstance(c, dict):
                continue
            if str(c.get("room_nr") or "").strip() != target:
                continue
            quantities.append({
                "row_id": row.get("id"),
                "aprasymas": row.get("aprasymas"),
                "unit": row.get("vnt") or row.get("mato_vnt"),
                "value": _f(c.get("value")),
                "terms": c.get("terms") or None,
                "formula": formula_sentence(c, row),
                "geometry": c.get("geometry") or "none",
                "included_because": c.get("included_because"),
            })
        for e in (row.get("excluded") or []):
            if not isinstance(e, dict):
                continue
            if str(e.get("room_nr") or "").strip() != target:
                continue
            excluded.append({
                "row_id": row.get("id"),
                "aprasymas": row.get("aprasymas"),
                "reason": e.get("excluded_because"),
            })
    return quantities, excluded


# ── the payload ─────────────────────────────────────────────────────────────

def find_room(project: dict, room_nr: str) -> dict | None:
    target = str(room_nr).strip()
    for r in (project.get("patalpos") or []):
        if isinstance(r, dict) and str(r.get("nr") or "").strip() == target:
            return r
    return None


def attach_crop_urls(payload: dict, project_id: str, dpi: int | None = None) -> dict:
    """Fill every fact's `crop_url` from its own page + rectangle.

    A fact with a page but no rectangle still gets a URL — the whole sheet.
    That is the honest answer for a finish or an opening: we know which
    drawing to read, we do not know where on it.
    """
    from api.evidence import DEFAULT_DPI, evidence_url
    d = int(dpi or DEFAULT_DPI)
    for fact in payload.get("facts") or []:
        src = fact.get("source") or {}
        page = src.get("page")
        rect = src.get("rect_pct") or ([0.0, 0.0, 1.0, 1.0] if page else None)
        fact["crop_url"] = evidence_url(project_id, page, rect, d)
    return payload


def build_room_facts(project: dict, room_nr: str) -> dict | None:
    """The whole check sheet for one room, or None when there is no such room."""
    room = find_room(project, room_nr)
    if room is None:
        return None
    region = room_region_pct(room)
    facts = [
        _fact_plotas(project, room, region),
        _fact_perimetras(project, room, region),
        _fact_aukstis(project, room, region),
        _fact_apdaila(project, room, region),
        _fact_angos(project, room, region),
        _fact_grindys(project, room, region),
    ]
    quantities, excluded = room_quantities(project, room_nr)
    return {
        "room": {
            "nr": str(room.get("nr") or "").strip(),
            "name": (room.get("pavadinimas") or "").strip(),
            "page": room.get("puslapio_nr"),
            "polygon_pct": normalize_polygon(room.get("polygon_pct")),
            "marker_pct": (list(_marker_xy(room)) if _marker_xy(room) else None),
            "region_pct": region,
        },
        "facts": facts,
        "quantities": quantities,
        "excluded": excluded,
        # False on a project extracted or last recomputed before the ledger
        # shipped (2026-09-02). The check sheet must then say „kiekių kilmė
        # bus matoma perskaičiavus" rather than „šis kambarys nieko neduoda",
        # which is a different and untrue statement.
        "ledger_available": bool(_ledgered_rows(project)),
    }

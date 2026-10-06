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
# `lt_num` lives in universal_rules since 2026-10-06 — the rule engine's notes
# need it too, and universal_rules cannot import this module. project_questions
# still imports it from here.
from .universal_rules import REMOVED_OPENINGS_KEY, kiekis_units, lt_num, paskirtis_label

# ── the six facts, in the order the check sheet walks them ──────────────────
FACT_KEYS = ("plotas", "perimetras", "aukstis", "apdaila", "angos", "grindys")

SOURCE_KINDS = ("eksplikacija", "planas", "pjuvis", "apdailos_lentele",
                "duru_zinynas", "grindu_planas", "sienu_angos", "prielaida", "nera")
STATUSES = ("read", "assumed", "missing")

# How far around a single printed marker to crop, as a fraction of the page.
# A height marker is a five-character string; ±6 % of the page around it shows
# the marker AND the room number it belongs to, which is what makes it
# checkable rather than merely visible.
MARKER_MARGIN_PCT = 0.06
# Same idea for a room whose only anchor is its printed number.
ROOM_MARKER_MARGIN_PCT = 0.10


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
    # 2026-09-19: the geometry lane finds the room's PRINTED number (or its area
    # label) in the text layer. That is the room's place on the plan; Vision's
    # box is a guess and is not.
    v = room.get("_vieta")
    if isinstance(v, dict) and v.get("saltinis") in ("zenkliukas", "plotas_uzrasas"):
        x, y = _f(v.get("cx")), _f(v.get("cy"))
        page, own = v.get("page"), room.get("puslapio_nr")
        if x is not None and y is not None and (own is None or page is None or int(page) == int(own)):
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

    if saltinis in ("user_override", "manual") or room.get("plotas_source") in ("manual", "manual_polygon"):
        # He typed it on the sheet or drew the outline himself (2026-09-13:
        # the sheet marks its edits, and a re-read of the drawing keeps them).
        sentence = ("Plotas — iš jūsų pataisyto kontūro."
                    if room.get("plotas_source") == "manual_polygon" else "Šį plotą įrašėte patys.")
        return _fact("plotas", round(value, 2), "m²", "read", "prielaida",
                     room.get("puslapio_nr"), region, sentence,
                     {"field": "plotas_m2", "kind": "number"})

    if saltinis == "eksplikacija" or (room.get("plotas_source") == "eksplikacija"):
        page = _row_page(project, room, row)
        sentence = ("Iš patalpų eksplikacijos lentelės"
                    + (f", eilutė {label}." if label else "."))
        return _fact("plotas", round(value, 2), "m²", "read", "eksplikacija",
                     page, rect or region_on_page(room, page, region), sentence,
                     {"field": "plotas_m2", "kind": "number"})

    if saltinis == "plano_uzrasas":
        # 2026-09-06: the designer's own area label, read from the text layer
        # (extractor/plan_area_annotations.py). The crop is the label itself.
        uz = room.get("_plotas_uzrasas") or {}
        page = uz.get("page") or room.get("puslapio_nr")
        label_rect = _bbox_pdf_to_pct(uz.get("bbox"), uz.get("page_width"), uz.get("page_height"))
        if label_rect:
            m = MARKER_MARGIN_PCT
            label_rect = [max(0.0, label_rect[0] - m), max(0.0, label_rect[1] - m),
                          min(1.0, label_rect[2] + m), min(1.0, label_rect[3] + m)]
        prior = _f(room.get("_plotas_pries_uzrasa_m2"))
        sentence = "Plotas — užrašytas prie patalpos plane."
        if prior:
            sentence += f" Skaitant planą buvo {lt_num(prior)} m² — imu užrašytą."
        return _fact("plotas", round(value, 2), "m²", "read", "planas",
                     page, label_rect or region_on_page(room, page, region), sentence,
                     {"field": "plotas_m2", "kind": "number"})

    if room.get("_area_unconfirmed"):
        # Other rooms on this drawing have their area written next to them;
        # this one has none — the contractor decides whether it exists. When
        # its outline lies over another room that DOES own the label, say so:
        # it is most likely the same room returned twice.
        reason = str(room.get("_area_unconfirmed_reason") or "")
        other = room.get("_plotas_uzrasas_kitas")
        if reason.startswith("duplicate_of:"):
            of = reason.split(":", 1)[1]
            sentence = (f"Ši patalpa plane persidengia su patalpa {of}, o ploto užrašas ten "
                        f"vienas — greičiausiai ta pati patalpa antrą kartą. Kol kas skaičiuoju su "
                        f"{lt_num(value)} m²; jei ji nereikalinga, išjunkite.")
        elif reason == "label_differs" and isinstance(other, dict) and _f(other.get("value_m2")):
            # A label DOES stand in this room's place — too far from its area to be its own
            # (plan_area_annotations, `_plotas_uzrasas_kitas`): say which, crop where it is written,
            # the same words as the warning (lane_warnings) — not „no label found" (2026-10-05).
            page = other.get("page") or room.get("puslapio_nr")
            label_rect = _bbox_pdf_to_pct(other.get("bbox"), other.get("page_width"), other.get("page_height"))
            if label_rect:
                m = MARKER_MARGIN_PCT
                label_rect = [max(0.0, label_rect[0] - m), max(0.0, label_rect[1] - m),
                              min(1.0, label_rect[2] + m), min(1.0, label_rect[3] + m)]
            where = f" ({page} psl.)" if other.get("page") else ""
            sentence = (f"Šios patalpos vietoje plane{where} užrašyta {lt_num(_f(other['value_m2']))} m², "
                        f"o skaičiuoju su {lt_num(value)} m² — skirtumas per didelis, kad tai būtų tas pats "
                        "plotas. Patikrinkite, kurios patalpos tai užrašas, ir įrašykite tikrą plotą.")
            return _fact("plotas", round(value, 2), "m²", "assumed", "prielaida",
                         page, label_rect or region_on_page(room, page, region), sentence,
                         {"field": "plotas_m2", "kind": "number"})
        else:
            sentence = (f"Plane prie šios patalpos ploto užrašo neradau, nors kitos "
                        f"patalpos jį turi — skaičiuoju su {lt_num(value)} m². "
                        "Patikrinkite, ar patalpa yra ir ar ji nesidubliuoja.")
        return _fact("plotas", round(value, 2), "m²", "assumed", "prielaida",
                     room.get("puslapio_nr"), region, sentence,
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

_NOT_AN_OUTLINE = ("", "synthesized_from_bbox", "bbox_fallback", "manual_needed")


def _perimeter_drawing(room: dict) -> dict:
    """What the drawing pane shows for the perimeter: the traced OUTLINE, every
    wall of it with the strings that state its length (each with its place on
    the sheet it is written on), and for an open plan the shared outline.
    Vision's box is not an outline: no outline, no walls, and the reason why."""
    kont = room.get("_konturas") if isinstance(room.get("_konturas"), dict) else {}
    page = kont.get("page") or room.get("puslapio_nr")
    traced = str(room.get("polygon_source") or "") not in _NOT_AN_OUTLINE
    poly = normalize_polygon(room.get("polygon_pct")) if traced else None
    outline: dict | None = {"page": page, "polygon_pct": poly} if poly else None
    if outline is not None and isinstance(kont.get("menamos"), list) and kont["menamos"]:
        # the boundary a person drew through a shared space: an edge of the outline, not a wall — drawn dashed
        outline["menamos"] = [[[_f(a[0]), _f(a[1])], [_f(b[0]), _f(b[1])]] for a, b in kont["menamos"]]
        # whose boundary it is: the program's (2026-09-23, geometry_lane — he may draw it elsewhere) or his own
        outline["riba"] = "programos" if kont.get("saltinis") == "padalinta_programos" else "jusu"
    space = room.get("_atvira_erdve")
    shared = normalize_polygon(space.get("polygon_pct")) if isinstance(space, dict) else None
    if shared:
        outline = outline or {"page": space.get("page") or page, "polygon_pct": None}
        outline["open_space"] = {"nariai": [str(n) for n in (space.get("nariai") or [])], "polygon_pct": shared,
                                 "perimetras_m": _f(space.get("perimetras_m")), "page": space.get("page") or page}
    walls = []
    if poly:
        for w in room.get("_sienos") or []:
            if not isinstance(w, dict) or not isinstance(w.get("edge_pct"), (list, tuple)) or len(w["edge_pct"]) != 2:
                continue
            walls.append({"page": page, "edge_pct": [[_f(c[0]), _f(c[1])] for c in w["edge_pct"]],
                          "ilgis_m": _f(w.get("ilgis_m")), "saltinis": w.get("saltinis"), "kontrole_m": _f(w.get("kontrole_m")),
                          "dalys": [dict(part) for part in (w.get("dalys") or []) if isinstance(part, dict)],
                          "eilutes": [{"text": str(e.get("text")), "page": e.get("page"), "line_pct": e.get("line_pct")}
                                      for e in (w.get("eilutes") or []) if isinstance(e, dict)]})
    out = {"outline": outline, "walls": walls}
    if outline is None and room.get("_konturo_priezastis"):
        out["outline_reason"] = str(room["_konturo_priezastis"])
    cand = room.get("_konturo_siulymas")
    if not (outline and outline.get("polygon_pct")) and isinstance(cand, dict) and normalize_polygon(cand.get("polygon_pct")):
        # 2026-09-23: what the walls close around the room's number when the table disagrees — PROPOSED on the
        # drawing (the question list: „Tinka" takes it, a click elsewhere replaces it), never asserted
        out["outline_proposal"] = {"page": cand.get("page") or page, "polygon_pct": normalize_polygon(cand["polygon_pct"]),
                                   "plotas_m2": _f(cand.get("plotas_m2")), "perimetras_m": _f(cand.get("perimetras_m")),
                                   "paklaida": _f(cand.get("paklaida")),
                                   "plotas_uzrasas_m2": _f(cand.get("plotas_uzrasas_m2")) or _f(room.get("plotas_m2")),
                                   "taskas_pct": [_f(cand["taskas_pct"][0]), _f(cand["taskas_pct"][1])]
                                   if isinstance(cand.get("taskas_pct"), (list, tuple)) and len(cand["taskas_pct"]) == 2 else None}
    return out


def _open_space_rect_pct(room: dict) -> list[float] | None:
    """The shared outline of the open plan this room is part of — its evidence box."""
    space = room.get("_atvira_erdve")
    poly = space.get("polygon_pct") if isinstance(space, dict) else None
    if not isinstance(poly, list) or len(poly) < 3:
        return None
    try:
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
    except (TypeError, ValueError, IndexError):
        return None
    m = MARKER_MARGIN_PCT / 2
    return _clamp_rect([min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m])


def _outline_rect_pct(room: dict) -> list[float] | None:
    """The traced outline's box with a margin — the crop for a fact that is
    about the room's walls. Sheets of one plan share the frame, so the same
    box frames the room on the sheet the wall lengths were read from. Vision's
    box is not an outline."""
    poly = room.get("polygon_pct")
    if str(room.get("polygon_source") or "") in ("", "synthesized_from_bbox") or not isinstance(poly, list) or len(poly) < 3:
        return None
    try:
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
    except (TypeError, ValueError, IndexError):
        return None
    m = MARKER_MARGIN_PCT / 2
    return _clamp_rect([min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m])


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
        if room.get("_perimetras_floor_reason") == "geometrinis_minimumas":
            # the read figure is impossible for the area — say so, and what is billed
            tail = (f" Tokio ploto patalpa negali turėti trumpesnio perimetro nei "
                    f"{lt_num(used)} m (kvadratas) — sienų plotui imu {lt_num(used)} m. "
                    "Patikrinkite perimetrą.")
        else:
            tail = (f" Sienų plotui naudoju {lt_num(used)} m — patalpos kontūras "
                    "brėžinyje nepažymėtas, todėl imu stačiakampio perimetrą.")

    # 2026-09-20: an outline he POINTED AT on the check sheet (api/room_outline.py). Whose outline it is
    # gets said; a disagreement with the table is shown — it no longer stops the walls from being added.
    kont = room.get("_konturas") if isinstance(room.get("_konturas"), dict) else {}
    whose = ""                                                 # said whether the walls were added or not
    if kont.get("saltinis") == "parodyta":
        dev = _f(kont.get("paklaida"))
        if dev is not None and dev > 0.08 and _f(kont.get("plotas_m2")) and _f(kont.get("plotas_uzrasas_m2")):
            whose = (f" Patalpą brėžinyje parodėte patys: kontūro plotas {lt_num(_f(kont.get('plotas_m2')))} m², "
                     f"lentelėje užrašyta {lt_num(_f(kont.get('plotas_uzrasas_m2')))} m².")
        else:
            whose = " Patalpą brėžinyje parodėte patys."
    elif kont.get("saltinis") == "pasiulyta":
        # 2026-09-23: the face the walls close around the number, proposed because the table disagreed — he said „Tinka"
        dev = _f(kont.get("paklaida"))
        whose = " Kontūrą pasiūliau pagal sienas prie patalpos numerio — patvirtinote."
        if dev is not None and dev > 0.08 and _f(kont.get("plotas_m2")) and _f(kont.get("plotas_uzrasas_m2")):
            whose += (f" Kontūro plotas {lt_num(_f(kont.get('plotas_m2')))} m², lentelėje užrašyta "
                      f"{lt_num(_f(kont.get('plotas_uzrasas_m2')))} m² — plotui imamas užrašas, kontūras tik sienoms.")
    elif kont.get("saltinis") == "padalinta":
        # 2026-09-21: one side of a line he drew through a space two rooms share (api/room_outline.py)
        others = ", ".join(str(n) for n in (kont.get("su") or []))
        whose = (f" Bendrą erdvę su patalpa {others} padalijote patys" if others else " Bendrą erdvę padalijote patys")
        whose += " — riba tarp jų menama (sienos ten nėra), į perimetrą neįskaičiuota."
        dev = _f(kont.get("paklaida"))
        if dev is not None and dev > 0.08 and _f(kont.get("plotas_m2")) and _f(kont.get("plotas_uzrasas_m2")):
            whose += (f" Šios dalies kontūro plotas {lt_num(_f(kont.get('plotas_m2')))} m², "
                      f"lentelėje užrašyta {lt_num(_f(kont.get('plotas_uzrasas_m2')))} m².")
    elif kont.get("saltinis") == "padalinta_programos":
        # 2026-09-23: one side of the boundary the LANE proposed through a shared space (geometry_lane) — the
        # founder: „o koks tau skirtumas, kur riba?" — none to the wall total, so it is taken, said, and changeable
        others = ", ".join(str(n) for n in (kont.get("su") or []))
        where = ("per sienos galą, kur su ja sutinka lentelės plotai" if kont.get("pagal") == "kampas"
                 else "ten, kur plotai pasidalija lentelės santykiu")
        whose = (f" Bendrą erdvę su patalpa {others} padalijau pats — riba {where}." if others
                 else f" Bendrą erdvę padalijau pats — riba {where}.")
        whose += " Riba ne siena: į perimetrą neįskaičiuota, sienų sumai įtakos neturi. Pakeisti galite čia — „Padalinti erdvę“."
    tail += whose

    estimated = str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis")
    if (measured is None or estimated) and _f(room.get("_perimetras_ivertis_m") if measured is None else measured):
        # 2026-09-19: the geometry lane could not ADD this room's wall lengths.
        # The room carries the outline's length so the rows can be computed —
        # but it was not READ, so the sheet shows a blank, says why, and offers
        # the number: one click to accept, or type the real one.
        est = round(float(room["_perimetras_ivertis_m"] if measured is None else measured), 2)
        why = str(room.get("_perimetras_priezastis") or "ne visos sienos plane turi matmenį").rstrip(".")
        page = (room.get("_konturas") or {}).get("page") or room.get("puslapio_nr")
        if room.get("_perimetras_ivertis_saltinis") == "atviros_erdves_konturas":
            sentence = (f"Perimetro nesudėjau: {why}. Šiai patalpai tenka {lt_num(est)} m — priimkite arba įrašykite "
                        f"tikrą. Kol neįrašyta, sienas skaičiuoju su {lt_num(est)} m.")
        else:
            sentence = (f"Perimetro nesudėjau: {why}. Pagal sienų kontūrą brėžinyje būtų {lt_num(est)} m — "
                        f"priimkite arba įrašykite tikrą. Kol neįrašyta, sienas skaičiuoju su {lt_num(est)} m.")
        return _fact("perimetras", None, "m", "missing", "nera", page,
                     _outline_rect_pct(room) or _open_space_rect_pct(room) or region_on_page(room, page, region),
                     sentence + whose, editable, suggestion={"value": est, "label": f"Priimti {lt_num(est)} m"})

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

    if room.get("perimetras_saltinis") in ("user_override", "manual"):
        est = _f(room.get("_perimetras_ivertis_m"))
        if est is not None and abs(est - measured) < 0.005:
            # he took the number the sheet offered — say which number that was, not „you typed it"
            why = str(room.get("_perimetras_priezastis") or "").rstrip(".")
            head = ("Priėmėte šiai patalpai tenkančią bendros erdvės sienų dalį"
                    if room.get("_perimetras_ivertis_saltinis") == "atviros_erdves_konturas"
                    else "Priėmėte įvertį pagal sienų kontūrą brėžinyje")
            sentence = head + (f" (plane sienų ilgių nesudėjau: {why})." if why else ".")
            page = (room.get("_konturas") or {}).get("page") or room.get("puslapio_nr")
            return _fact("perimetras", round(measured, 2), "m", "read", "prielaida", page,
                         _outline_rect_pct(room) or _open_space_rect_pct(room) or region_on_page(room, page, region),
                         sentence + tail, editable)
        return _fact("perimetras", round(measured, 2), "m", "read", "prielaida",
                     room.get("puslapio_nr"), region,
                     "Šį perimetrą įrašėte patys." + tail, editable)

    if (room.get("perimetras_saltinis") == "plano_matmenys"
            and isinstance(room.get("_perimetras_matmenys"), dict)):
        m = room["_perimetras_matmenys"]
        from .plan_dimensions import dimension_rect_pct
        page = m.get("page") or room.get("puslapio_nr")
        w, l = _f(m.get("plotis_m")), _f(m.get("ilgis_m"))
        scale = f" (M 1:{int(m['mastelis'])})" if m.get("mastelis") else ""
        sentence = (f"Perimetras — iš plane užrašytų matmenų{scale}: 2 × ({lt_num(w, 3)} + {lt_num(l, 3)}) "
                    f"= {lt_num(measured)} m. Sandauga {lt_num(_f(m.get('sandauga_m2')))} m² "
                    f"sutampa su plotu {lt_num(_f(m.get('plotas_m2')))} m².")
        prev = _f(room.get("_perimetras_pries_matmenis"))
        if prev is not None and abs(prev - measured) > 0.05:
            sentence += f" Skaitant planą buvo {lt_num(prev)} m — imu užrašytus matmenis."
        return _fact("perimetras", round(measured, 2), "m", "read", "planas", page,
                     dimension_rect_pct(room) or region_on_page(room, page, region),
                     sentence + tail, editable)

    if room.get("perimetras_saltinis") == "matmenu_eilutes" and isinstance(room.get("_perimetras_suma"), dict):
        # 2026-09-19: „perskaityti skaičius ir sudėti" — every wall's written
        # length, in the order the walls go round the room, on the sheet they
        # were read from. The outline only checked the sum; it is said too.
        suma = room["_perimetras_suma"]
        terms: list[str] = []
        for wall in room.get("_sienos") or []:
            if wall.get("saltinis") == "konturas":
                terms.append(lt_num(_f(wall.get("ilgis_m"))))
            elif isinstance(wall.get("dalys"), list) and wall["dalys"] and wall.get("saltinis") == "eilute":
                # 2026-09-21: a chain whose holes were filled — every part in the order it lies along the wall,
                # a door's width said to be a door's, so the sum he reads adds up
                for part in wall["dalys"]:
                    if part.get("text") is not None:
                        terms.append(str(part["text"]))
                    elif part.get("anga_m") is not None:
                        terms.append(f"{lt_num(_f(part['anga_m']))} (durų anga)")
                    elif part.get("trumpa_m") is not None:
                        terms.append(lt_num(_f(part["trumpa_m"])))
            else:
                terms.extend(str(e.get("text")) for e in (wall.get("eilutes") or []))
        if not terms:
            terms = [str(t) for t in (suma.get("eilutes") or [])]
        shown = terms if len(terms) <= 14 else terms[:13] + ["…"]
        pages = [int(p) for p in (suma.get("lapai") or [])]
        page = pages[0] if pages else ((room.get("_konturas") or {}).get("page") or room.get("puslapio_nr"))
        where = f" ({', '.join(str(p) for p in pages)} psl.)" if pages else ""
        sentence = (f"Perimetras — sudėjau plane užrašytus šios patalpos sienų ilgius{where}: "
                    f"{' + '.join(shown)} = {lt_num(measured)} m. "
                    f"Sienų kontūras brėžinyje rodo {lt_num(_f(suma.get('kontrole_m')))} m — sutampa.")
        repeated = int(suma.get("pakartota") or 0)
        if repeated:
            sentence += (" Viena siena plane užrašyta tik iš vienos pusės — priešingai, tokio pat ilgio sienai ėmiau tą patį skaičių."
                         if repeated == 1 else
                         f" {repeated} sienos plane užrašytos tik iš vienos pusės — priešingoms, tokio pat ilgio sienoms ėmiau tuos pačius skaičius.")
        from_openings = _f(suma.get("angos_m")) or 0.0
        if from_openings > 0:
            sentence += f" Durų angų pločio ({lt_num(from_openings)} m) planas neužrašo — paėmiau jį iš sienų brėžinio."
        from_outline = _f(suma.get("is_konturo_m")) or 0.0
        if from_outline > 0:
            sentence += f" {lt_num(from_outline)} m trumpų atkarpų be užrašo paėmiau iš kontūro."
        return _fact("perimetras", round(measured, 2), "m", "read", "planas", page,
                     _outline_rect_pct(room) or region_on_page(room, page, region), sentence + tail, editable)

    if (room.get("perimetras_saltinis") == "sienu_konturas"
            and isinstance(room.get("_konturas"), dict)):
        # 2026-09-13: the outline traced from the wall geometry, checked
        # against the printed area — the crop is the outline's own box.
        from .wall_outline import outline_rect_pct
        k = room["_konturas"]
        page = k.get("page") or room.get("puslapio_nr")
        dev = _f(k.get("paklaida"))
        dev_txt = f" ({'+' if (_f(k.get('plotas_m2')) or 0) >= (_f(k.get('plotas_uzrasas_m2')) or 0) else '−'}{lt_num(dev * 100, 1)} %)" if dev is not None else ""
        sentence = (f"Perimetras — pagal sienų kontūrą, atsektą iš brėžinio: {lt_num(measured)} m. "
                    f"Kontūro plotas {lt_num(_f(k.get('plotas_m2')))} m², užrašyta "
                    f"{lt_num(_f(k.get('plotas_uzrasas_m2')))} m²{dev_txt}. Plotui imamas užrašas.")
        prev = _f(room.get("_perimetras_pries_kontura"))
        if prev is not None and abs(prev - measured) > 0.05:
            sentence += f" Skaitant planą buvo {lt_num(prev)} m — imu kontūrą."
        return _fact("perimetras", round(measured, 2), "m", "read", "planas", page,
                     outline_rect_pct(room) or region_on_page(room, page, region),
                     sentence + tail, editable)

    if str(room.get("perimetras_saltinis") or "") == "zoom":
        # vision_call.ZOOM_SOURCE (2026-09-29): the zoomed re-read replaced the figure — the program's
        # own reading of a close-up, checked by nothing printed. Amber, on every kind of drawing — and before
        # the table: a row of this number the room was NOT joined to (its area contradicted) does not make
        # the zoom's number the table's.
        return _fact("perimetras", round(measured, 2), "m", "assumed", "prielaida",
                     room.get("puslapio_nr"), region,
                     "Perimetrą programa įvertino iš padidinto plano vaizdo — brėžinyje užrašytais "
                     "matmenimis nepatikrintas. Palikite arba įrašykite tikrą." + tail, editable)

    if from_table:
        page = _row_page(project, room, row)
        rect = _bbox_pdf_to_pct(room.get("eksplikacija_row_bbox"),
                                room.get("eksplikacija_page_width_pdf"),
                                room.get("eksplikacija_page_height_pdf"))
        return _fact("perimetras", round(measured, 2), "m", "read",
                     "eksplikacija", page,
                     rect or region_on_page(room, page, region),
                     "Iš patalpų eksplikacijos lentelės." + tail, editable)

    if isinstance((project.get("_meta") or {}).get("geometrija"), dict):
        # 2026-09-19: the geometry lane ran on this project and could neither add
        # this room's wall lengths nor trace its outline — so the figure is what
        # the program estimated from the picture of the plan, checked by nothing.
        # An amber row with the number in the field, not a quiet „read" one.
        return _fact("perimetras", round(measured, 2), "m", "assumed", "prielaida",
                     room.get("puslapio_nr"), region,
                     "Perimetras — programos įvertis iš plano vaizdo, brėžinyje užrašytais "
                     "matmenimis nepatikrintas. Palikite arba įrašykite tikrą." + tail, editable)

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
    "plano_uzrasas": ("read", "planas", "Aukštis — užrašytas plane (visam aukštui)."),
    "user_override": ("read", "prielaida", "Šį aukštį įrašėte patys."),
    # vision_call.ZOOM_SOURCE: the program's own reading of a close-up of the plan, checked by nothing printed
    "zoom": ("assumed", "planas",
             "Aukštį programa įvertino iš padidinto plano vaizdo — prie patalpos užrašyto aukščio neradau. "
             "Įrašykite tikrą."),
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


# The questions an assumed fact opens with — the default is offered, not
# asserted. A read fact never gets one.
_ASK_HEIGHT = "Koks šios patalpos lubų aukštis?"
_ASK_FLOOR = "Kokia čia grindų danga?"


def _height_is_a_question(project: dict, room: dict) -> bool:
    """Does this room's height still wait for an answer — a default of ours (or nothing at all), which
    neither a reader nor he has replaced?"""
    own = ((project.get("_overrides") or {}).get("lubu_auksciai") or {})
    if str(room.get("nr") or "").strip() in {str(k).strip() for k in own}:
        return False
    if _f(room.get("lubu_aukstis_m")) is None:
        return True
    saltinis = (room.get("lubu_aukstis_saltinis") or "").strip().lower()
    return _HEIGHT_SOURCES.get(saltinis, ("assumed", "", ""))[0] == "assumed"


def _same_height_question(project: dict, room: dict) -> list[str]:
    """The OTHER rooms that ask the same thing (2026-09-20). A drawing that writes no storey height
    leaves every room with the question; he knows the answer once, for the whole flat."""
    me = str(room.get("nr") or "").strip()
    if not _height_is_a_question(project, room):
        return []
    out = []
    for r in project.get("patalpos") or []:
        nr = str(r.get("nr") or "").strip() if isinstance(r, dict) else ""
        if nr and nr != me and _height_is_a_question(project, r):
            out.append(nr)
    return out


def _asked_elsewhere(rooms: list[str]) -> str:
    if not rooms:
        return ""
    n = len(rooms)
    where = "patalpoje" if n % 10 == 1 and n % 100 != 11 else "patalpose"
    shown = ", ".join(rooms if n <= 12 else rooms[:11] + ["…"])
    return f" Tas pats klausimas dar {n} {where} ({shown}) — atsakyti galite visoms iš karto."


def _fact_aukstis(project: dict, room: dict,
                  region: list[float] | None) -> dict:
    value = _f(room.get("lubu_aukstis_m"))
    same = _same_height_question(project, room)
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
    uz = room.get("_lubu_aukstis_uzrasas")
    if saltinis == "plano_uzrasas" and isinstance(uz, dict):
        # the statement itself is the evidence — crop it on its own page
        page = int(_f(uz.get("page")) or 0) or page
        label_rect = _bbox_pdf_to_pct(uz.get("bbox"), uz.get("page_width"), uz.get("page_height"))
        if label_rect:
            m = MARKER_MARGIN_PCT
            rect = [max(0.0, label_rect[0] - m), max(0.0, label_rect[1] - m),
                    min(1.0, label_rect[2] + m), min(1.0, label_rect[3] + m)]
        if uz.get("text"):
            sentence = f"Aukštis — užrašytas plane: „{uz.get('text')}\"."
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
                     "Lubų aukščio brėžinyje neradau — įrašykite jį patys." + _asked_elsewhere(same),
                     editable, same_question=same)
    if not sentence:
        sentence = (f"Lubų aukščio brėžinyje neradau — skaičiuoju su "
                    f"{lt_num(value)} m. Įrašykite tikrą.")
    if status == "assumed":
        # A default is a QUESTION on the sheet, not a statement (council
        # verdict 4, 2026-09-13): the row opens with the field showing, the
        # sentence asks, and the reason we chose this number follows.
        sentence = f"{_ASK_HEIGHT} {sentence}" + _asked_elsewhere(same)
    return _fact("aukstis", round(value, 2), "m", status, kind, page,
                 rect, sentence, editable, same_question=same if status == "assumed" else [])


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


def _kept_out_by_choice(room: dict, family: str) -> bool:
    """The contractor's own choice keeps this room — or this family in it —
    out of the sąmata. Its quantities are zeroed by `scope.mark_rooms`; its
    READING is not, and the check sheet must keep showing the reading
    („dažoma 4,25 m², plytelės 18,15 m²"), not the zero („nedažomos")."""
    if room.get("_neskaiciuoti"):
        return True
    return family in (room.get("_neskaiciuoti_sritys") or [])


_KEPT_OUT_SENTENCE = "Į sąmatą neįtraukta jūsų pasirinkimu — rodau, ką perskaičiau."


def _m2(v: float) -> str:
    return f"{lt_num(v)} m²"


# Finishes the reader can see on the walls but the engine bills no area for:
# named, so he knows they were seen, without a number nobody computed.
_UNBILLED_FINISHES = ("tapetai_share", "plokste_share", "veidrodis_share",
                      "molio_tinkas_share", "kita_danga_share")


def _walls_description(room: dict) -> str:
    """What this room's walls get — in the m² the sąmata bills for it.

    Until 2026-09-20 this was a list of shares („dažoma 92 %, plytelės 8 %"),
    and a bare „dažoma" for a bathroom whose tiles were read by their height —
    beside a sąmata that billed 21,5 m² of tiles for it. A share of an unnamed
    whole is nothing a contractor can check; the two areas are the very numbers
    in his estimate (`walls_paintable_m2`, `plyteles_sienos_m2`), so the sheet
    and the sąmata cannot disagree. A room kept out by choice shows what the
    choice took off (`scope.excluded_quantity`), not the zero.
    """
    from .scope import excluded_quantity
    paint = excluded_quantity(room, "walls_paintable_m2")
    tiles = excluded_quantity(room, "plyteles_sienos_m2")
    breakdown = room.get("sienu_apdailos_breakdown")
    shares = breakdown if isinstance(breakdown, dict) else {}
    others = [_FINISH_LT[k] for k in _UNBILLED_FINISHES if (_f(shares.get(k)) or 0.0) >= 0.01]

    if room.get("_walls_full_tile"):
        return ", ".join([f"plytelės {_m2(tiles)}" if tiles > 0 else "plytelės"] + others)

    if _kept_out_by_choice(room, "apdaila") and paint <= 0 and tiles <= 0:
        # an older blob: the choice zeroed the areas and nothing remembered
        # them — the READING is still not „nedažomos"
        names = [lt for key, lt in _FINISH_LT.items() if (_f(shares.get(key)) or 0.0) >= 0.01]
        return ", ".join(names) if names else "dažoma"

    computed = room.get("walls_paintable_m2") is not None or room.get("_walls_paint_factor") is not None
    factor = _f(room.get("_walls_paint_factor"))
    unpainted = computed and (paint <= 0 or (factor is not None and factor <= 0))
    parts: list[str] = []
    if unpainted:
        parts.append("nedažomos")
    elif paint > 0:
        parts.append(f"dažoma {_m2(paint)}")
    else:
        parts.append("dažoma")                    # never recomputed: no area to state yet
    if tiles > 0:
        parts.append(f"plytelės {_m2(tiles)}")
    return ", ".join(parts + others)


def _ceiling_description(room: dict) -> str:
    from .scope import excluded_quantity
    area = excluded_quantity(room, "ceiling_paintable_m2")
    src = (room.get("_ceiling_paint_source") or "").strip().lower()
    if room.get("_stretch_ceiling") or (room.get("lubu_tipas") or "") == "itempiamos":
        return f"įtempiamos {_m2(area)}" if area > 0 else "įtempiamos"
    if src in ("override_off", "unfinished_room_standard"):
        return "nedažomos"
    paint = _f(room.get("ceiling_paintable_m2"))
    if paint is not None and paint <= 0 and not _kept_out_by_choice(room, "apdaila"):
        return "nedažomos"
    return f"dažomos {_m2(area)}" if area > 0 else "dažomos"


DESIGNER_TOTAL_TOL = 0.03        # the designer's own total and ours „agree" within this share


def _designer_wall_total(project: dict) -> dict | None:
    """The designer's OWN total for painted walls, written on the drawing (`_autoriaus_kiekiai`, family
    `sienu_dazymas`, m²), beside the sum of our rooms: {ours, theirs, page, rect_pct, agrees}. A second
    reading of the same drawing to compare against — never a value we take."""
    figures = [f for f in (project.get("_autoriaus_kiekiai") or [])
               if isinstance(f, dict) and f.get("family") == "sienu_dazymas"
               and str(f.get("unit") or "").lower().replace("²", "2") == "m2" and (_f(f.get("value")) or 0) > 0]
    if not figures:
        return None
    theirs = round(sum(_f(f.get("value")) or 0.0 for f in figures), 2)
    ours = round(sum(_f(r.get("walls_paintable_m2")) or 0.0 for r in (project.get("patalpos") or []) if isinstance(r, dict)), 2)
    if theirs <= 0 or ours <= 0:
        return None
    first = figures[0]
    page = _f(first.get("page"))
    return {"ours": ours, "theirs": theirs, "page": int(page) if page else None,
            "rect_pct": _bbox_pdf_to_pct(first.get("bbox"), first.get("page_width"), first.get("page_height")),
            "agrees": abs(ours - theirs) / theirs <= DESIGNER_TOTAL_TOL}


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
    rect = None
    # 2026-09-20: a finish chosen by the room's PURPOSE stops being a question when the designer's own
    # total for painted walls agrees with the sum of our rooms — the sąmata bills that total, and the
    # drawing confirms it (objektas_h: 320 m² written, 320,28 m² ours; nine amber rows asked him to
    # check išklotinės the drawing does not have).
    total = _designer_wall_total(project) if status != "read" else None
    if total and total["agrees"] and total["page"]:
        status, kind, page = "read", "planas", total["page"]
        m = MARKER_MARGIN_PCT
        if total["rect_pct"]:
            x0, y0, x1, y1 = total["rect_pct"]
            rect = [max(0.0, x0 - m), max(0.0, y0 - m), min(1.0, x1 + m), min(1.0, y1 + m)]
        sentence = (f"Sienų apdaila — pagal patalpos paskirtį. Visų patalpų dažomų sienų suma {_m2(total['ours'])} sutampa su "
                    f"projekto autoriaus užrašyta {_m2(total['theirs'])} ({total['page']} psl.) — kiekvienos patalpos "
                    f"atskirai tikrinti nereikia. Lubos — patikrinkite lubų plane.")
    elif status == "read":
        sentence += " Lubos — patikrinkite lubų plane."
    else:
        sentence += " Patikrinkite išklotinėse arba apdailų lentelėje."
    if _kept_out_by_choice(room, "apdaila"):
        sentence += " " + _KEPT_OUT_SENTENCE
    # No per-room rectangle exists for a finish anywhere in the pipeline. When
    # the finish sheet happens to BE the room's own page the outline still
    # frames it usefully; otherwise the crop is the whole sheet and the
    # sentence says which one to read.
    return _fact("apdaila", value, None, status, kind, page,
                 rect or region_on_page(room, page, region), sentence,
                 {"field": "walls_paint_override", "kind": "choice"})


# ── angos ───────────────────────────────────────────────────────────────────

# (singular after 1, plural after 2–9, genitive plural after 0 and 10+) —
# `durys` is plurale tantum in Lithuanian, so it never changes.
_ELEMENT_LT: dict[str, tuple[str, str, str]] = {
    "duris": ("durys", "durys", "durų"),
    "pasleptos_duris": ("paslėptos durys", "paslėptos durys", "paslėptų durų"),
    "langas": ("langas", "langai", "langų"),
    "stoglangis": ("stoglangis", "stoglangiai", "stoglangių"),
    # a door element the walls pass marked `_praejimas` (2026-09-24): an opening without a door
    "praejimas": ("praėjimas", "praėjimai", "praėjimų"),
}
_OPENING_TIPAI = ("duris", "pasleptos_duris", "langas", "stoglangis")


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


# What the WALLS show (geometry lane, `_angos_sienose`): the fact marks those
# openings on the drawing and says whether the counted list agrees with them.
_DOOR_TIPAI = ("duris", "pasleptos_duris")
_STANDARD_DOOR_H_MM = 2100
_STANDARD_WINDOW_H_MM = 1500


def _anga_word(n: int) -> str:
    tail, hundred = n % 10, n % 100
    if tail == 1 and hundred != 11:
        return "anga"
    if 2 <= tail <= 9 and not (11 <= hundred <= 19):
        return "angos"
    return "angų"


def _leads_to(i: str) -> str:
    if i == "laukas":
        return "į lauką"
    if i == "vidus":
        return "į gretimą patalpą"
    return f"į patalpą {i}"


def _wall_openings(room: dict) -> tuple[int | None, list[dict]]:
    """(the sheet they are marked on, the openings the wall solid shows in this room's walls)."""
    rec = room.get("_angos_sienose")
    if not isinstance(rec, dict):
        return None, []
    items = []
    for a in rec.get("angos") or []:
        line = a.get("line_pct") if isinstance(a, dict) else None
        width = _f(a.get("plotis_m")) if isinstance(a, dict) else None
        if not (isinstance(line, (list, tuple)) and len(line) == 2 and width):
            continue
        try:
            pts = [[float(line[0][0]), float(line[0][1])], [float(line[1][0]), float(line[1][1])]]
        except (TypeError, ValueError, IndexError):
            continue
        i = str(a.get("i") or "vidus")
        items.append({"line_pct": pts, "plotis_m": round(width, 2), "i": i, "lauko": i == "laukas"})
    page = _f(rec.get("page"))
    return (int(page) if page else None), items


def _suggestion(tipas: str, opening: dict) -> dict:
    """One click adds this opening: the width the wall shows (to the nearest 10 cm), the standard height."""
    width_mm = int(round(opening["plotis_m"] * 10)) * 100
    height_mm = _STANDARD_DOOR_H_MM if tipas == "duris" else _STANDARD_WINDOW_H_MM
    what = "duris" if tipas == "duris" else "langą"
    return {"tipas": tipas, "plotis_mm": width_mm, "aukstis_mm": height_mm, "i": opening["i"], "plotis_m": opening["plotis_m"],
            "label": (f"Pridėti {what} {lt_num(width_mm / 1000)} × {lt_num(height_mm / 1000)} m — "
                      f"anga {_leads_to(opening['i'])}"),
            "line_pct": opening["line_pct"]}


def _listed_beyond(project: dict, room: dict, openings: list[dict]) -> set[int]:
    """The openings (by index) whose door is already in the list of the room BEYOND them (2026-09-23): a
    door between the corridor and a bedroom stands in one of the two lists — proposing it again from the
    other side doubled the reveals and the frameless-door row on objektas_h (70 → 100 m after six adds).
    A neighbour's interior door of the opening's width (±16 cm) claims it, each door once."""
    out: set[int] = set()
    by_nr = {str(r.get("nr") or "").strip(): r for r in (project.get("patalpos") or []) if isinstance(r, dict)}
    mine = str(room.get("nr") or "").strip()
    claimed: dict[tuple[str, int], int] = {}
    for idx, o in enumerate(openings):
        other = by_nr.get(str(o.get("i") or ""))
        if other is None or str(o.get("i")) == mine:
            continue
        for j, el in enumerate(other.get("elementai") or []):
            if not isinstance(el, dict) or (el.get("tipas") or "") not in _DOOR_TIPAI or el.get("_exterior"):
                continue
            leads = str(el.get("_is_sienu_angos") or el.get("_anga_i") or "").strip()
            if leads and leads != mine:
                continue                                       # that door leads somewhere else
            # a door stood toward this room (the walls pass, or added from the opening) claims by its side
            # alone — a width he typed on it (800 in a 1,40 opening) is his business, not a second door
            w = _f(el.get("plotis_mm"))
            if leads != mine and w and abs(w / 1000.0 - float(o["plotis_m"])) > 0.16:
                continue
            units = kiekis_units(_f(el.get("kiekis")))       # a door he removed (0) claims nothing
            if claimed.get((str(o.get("i")), j), 0) >= units:
                continue
            claimed[(str(o.get("i")), j)] = claimed.get((str(o.get("i")), j), 0) + 1
            out.add(idx)
            break
    return out


def _stood_in_walls(elems: list[dict]) -> dict | None:
    """What the walls pass (universal_rules.reconcile_openings_with_walls) recorded on this room's elements:
    the openings its units stand in, the passages, the doors no opening backs — or None for a room the
    pass has not seen (an older blob), which keeps the count-only cross-check below."""
    if not any(e.get("_anga_ks") or e.get("_be_angos") or e.get("_praejimas") or e.get(REMOVED_OPENINGS_KEY)
               for e in elems):
        return None
    consumed: set[int] = set()
    removed: list[dict] = []                                   # openings he emptied (universal_rules._hold_removed_openings)
    passages: set[int] = set()
    unbacked = 0
    added: list[dict] = []                                     # what the pass added because the drawing shows it
    converted: list[dict] = []                                 # a listed window that stands in a drawn door
    for e in elems:
        ks = [int(k) for k in (e.get("_anga_ks") or []) if isinstance(k, (int, float))]
        consumed.update(ks)
        if e.get("_praejimas"):
            passages.update(ks)
        if e.get("_be_angos") and (e.get("tipas") or "") in _DOOR_TIPAI:
            unbacked += kiekis_units(_f(e.get("kiekis")))
        for t in e.get(REMOVED_OPENINGS_KEY) or []:
            if isinstance(t, dict) and isinstance(t.get("k"), int):
                consumed.add(t["k"])
                removed.append({"tipas": e.get("tipas") or "", "plotis_m": _f(t.get("w")) or 0.0, "i": str(t.get("i") or "")})
        if e.get("_pridėta_pagal_sienas") and e.get("_nupiesta") and not e.get("_praejimas"):
            added.append({"tipas": e.get("tipas") or "", "plotis_m": (_f(e.get("plotis_mm")) or 0) / 1000.0,
                          "i": str(e.get("_anga_i") or e.get("_is_sienu_angos") or ""), "nupiesta": e.get("_nupiesta"),
                          "lauko": bool(e.get("_exterior"))})
        if e.get("_tipas_pagal_brezini"):
            converted.append({"plotis_m": (_f(e.get("plotis_mm")) or 0) / 1000.0, "i": str(e.get("_anga_i") or "")})
    return {"consumed": consumed, "passages": passages, "unbacked": unbacked, "added": added, "converted": converted,
            "removed": removed}


def _drawn_said(stood: dict) -> str:
    """What the drawing showed in the openings the pass filled by itself (2026-09-25): a glazed opening became
    a window, a swing arc a door; a listed window standing in the one drawn door became that door."""
    parts = []
    for a in stood.get("added") or []:
        what = ("langas" if a["tipas"] == "langas"
                else "lauko durys" if a.get("lauko") else "durys")
        why = "nupieštas stiklas" if a["nupiesta"] == "langas" else "nupieštas durų lankas"
        parts.append(f"{what} {lt_num(a['plotis_m'])} m {_leads_to(a['i'])} ({why})")
    said = ""
    if parts:
        said = " Pagal brėžinį pridėta: " + "; ".join(parts) + "."
    gone = [f"{'langas' if r['tipas'] == 'langas' else 'durys'} {lt_num(r['plotis_m'])} m {_leads_to(r['i'])}"
            for r in stood.get("removed") or []]
    if gone:
        # his removal on the room sheet (universal_rules._hold_removed_openings): the opening stays empty
        said += (" Jūs pašalinote: " + "; ".join(gone) + (" — sienose anga matoma" if len(gone) == 1
                 else " — sienose angos matomos") + ", bet sąmatoje neskaičiuojama.")
    for c in stood.get("converted") or []:
        said += (f" Sąraše buvo langas, o angoje {_leads_to(c['i'])} nupieštos durys su lanku — "
                 f"įrašytos lauko durys {lt_num(c['plotis_m'])} m.")
    return said


def _against_the_walls_stood(openings: list[dict], listed_beyond: set[int], stood: dict,
                             is_passage=None) -> tuple[str, bool, list[dict]]:
    """(what to say, does the list need a look, what one click could add) — for a room whose counted doors
    and windows the walls pass has stood in the openings: an opening nobody stands in is offered (a door to a
    room, a window to the outside, a passage is named), a door no opening backs is named for a look."""
    beyond = set(listed_beyond or ())
    consumed = set(stood.get("consumed") or ())
    passages = set(stood.get("passages") or ())
    unbacked = int(stood.get("unbacked") or 0)
    n = len(openings)
    listed = ", ".join(f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for o in openings)
    beyond_open = [(k, o) for k, o in enumerate(openings) if k in beyond and k not in consumed]
    # what stands beyond is said by its kind: a passage the room beyond lists is no door of theirs
    beyond_pass = [o for k, o in beyond_open if is_passage and is_passage(o["plotis_m"], o["i"])]
    beyond_doors = [o for k, o in beyond_open if o not in beyond_pass]
    tail_beyond = ""
    if beyond_doors:
        tail_beyond += " Durys " + ", ".join(f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for o in beyond_doors) + " įrašytos prie tos patalpos."
    if beyond_pass:
        tail_beyond += (" Praėjimas " if len(beyond_pass) == 1 else " Praėjimai ") + ", ".join(
            f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for o in beyond_pass) + (
            " įrašytas prie tos patalpos." if len(beyond_pass) == 1 else " įrašyti prie tos patalpos.")
    open_rest = [(k, o) for k, o in enumerate(openings) if k not in consumed and k not in beyond]
    suggestions, named = [], []
    for k, o in open_rest:
        if o["lauko"]:
            if o["plotis_m"] >= 0.5:
                suggestions.append(_suggestion("langas", o))
        elif is_passage and is_passage(o["plotis_m"], o["i"]):
            named.append(f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m) — praėjimas be durų")
        else:
            suggestions.append(_suggestion("duris", o))
    parts = [f"Sienose {n} {_anga_word(n)}: {listed}."]
    if passages:
        parts.append("Praėjimai be durų: " + ", ".join(
            f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for k, o in enumerate(openings) if k in passages) + ".")
    if suggestions:
        m = len(suggestions)
        parts.append(f"{m} {'angoje niekas nestovi' if m == 1 else 'angose niekas nestovi'} — patikrinkite brėžinyje ir pridėkite.")
    if named:
        parts.append("Be durų: " + "; ".join(named) + ".")
    if unbacked:
        parts.append(f"{unbacked} {'durys sąraše, kurioms' if unbacked == 1 else 'durys sąraše, kurioms'} angos sienose nematau — patikrinkite patalpoje.")
    if not suggestions and not unbacked and not named and not stood.get("removed"):
        parts = [f"Sienose tiek pat angų: {listed} — pažymėtos brėžinyje."]
    return " ".join(parts) + _drawn_said(stood) + tail_beyond, bool(suggestions or unbacked), suggestions


def _against_the_walls(per_type: dict[str, int], openings: list[dict], listed_beyond: set[int] | None = None
                       ) -> tuple[str, bool, list[dict]]:
    """(what to say about the walls' openings, does the list look short, what one click could add).

    Only the total is compared — an entrance door is an opening to the outside, so doors and windows
    cannot be matched side by side. The walls never show everything (a window behind a sill fill, a
    glazed wall), so FEWER openings in the walls is said without alarm; MORE means the list is short.
    An add is offered only where nothing else could be meant: no door counted and an opening to another
    room, no window counted and an opening to the outside. An opening whose door the room beyond already
    lists (`listed_beyond`) is neither short nor offered — it is said to be there."""
    beyond = set(listed_beyond or ())
    said_beyond = ", ".join(f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for k, o in enumerate(openings) if k in beyond)
    openings = [o for k, o in enumerate(openings) if k not in beyond]
    tail_beyond = f" Durys {said_beyond} įrašytos prie tos patalpos." if said_beyond else ""
    n = len(openings)
    listed = ", ".join(f"{_leads_to(o['i'])} ({lt_num(o['plotis_m'])} m)" for o in openings)
    doors = sum(v for t, v in per_type.items() if t in _DOOR_TIPAI)
    windows = per_type.get("langas", 0)
    counted = doors + windows                                   # a roof window is not in a wall
    inside = [o for o in openings if not o["lauko"]]
    outside = [o for o in openings if o["lauko"]]
    if n == 0 and said_beyond:
        return f"Sienose angos: {said_beyond} — durys įrašytos prie tos patalpos.", False, []
    if n == counted:
        return f"Sienose tiek pat angų: {listed} — pažymėtos brėžinyje.{tail_beyond}", False, []
    if n < counted:
        return (f"Sienose matyti {n} {_anga_word(n)}: {listed}; kitų angų sienos nerodo — "
                f"patikrinkite patalpoje.{tail_beyond}"), False, []
    suggestions = []
    gaps = []
    if doors == 0 and inside:
        suggestions += [_suggestion("duris", o) for o in inside]
        gaps.append(f"Durų nesuskaičiuota, nors sienoje yra anga {_leads_to(inside[0]['i'])}")
    if windows == 0 and outside:
        suggestions += [_suggestion("langas", o) for o in outside]
        gaps.append(f"Langų nesuskaičiuota, nors sienoje yra anga {_leads_to(outside[0]['i'])}")
    if counted == 0:
        return (f"Durų ir langų nesuskaičiuota, o sienose yra {n} {_anga_word(n)}: {listed}. "
                f"Patikrinkite brėžinyje ir pridėkite."), True, suggestions
    tail = (". ".join(gaps) + " — patikrinkite brėžinyje ir pridėkite." if gaps
            else "Patikrinkite brėžinyje, ar sąraše netrūksta durų ar lango.")
    return f"Sienose angų daugiau — {n}: {listed}. {tail}{tail_beyond}", True, suggestions


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
        n = kiekis_units(_f(e.get("kiekis")))                  # the 0 he stepped down to shows as 0
        total += n
        # a passage is counted as what it is — „2 langai, 2 praėjimai", not „1 paslėptos durys, 1 durys"
        counted_as = "praejimas" if e.get("_praejimas") else tipas
        per_type[counted_as] = per_type.get(counted_as, 0) + n
        anchored = anchored or bool(e.get("_schedule_anchored"))
        # Recorded per element since 2026-09-04; older blobs fall back to the
        # classified `door_window_schedule` sheet below.
        schedule_page = schedule_page or _f(e.get("_schedule_page"))
        details.append({
            "tipas": tipas,
            "pavadinimas": element_label(counted_as, n),
            "kiekis": n,
            "plotis_mm": _f(e.get("plotis_mm")),
            "aukstis_mm": _f(e.get("aukstis_mm")),
            "is_zinyno": bool(e.get("_schedule_anchored")),
            "_dydis_user": bool(e.get("_dydis_user")),
            # 2026-09-23: the walls pass (universal_rules.reconcile_openings_with_walls) — the width is the
            # wall opening's, the door was added because the room had none, the door stands in no opening
            "plotis_pagal_sienas": e.get("_plotis_pagal") == "sienos",
            "pridėta_pagal_sienas": bool(e.get("_pridėta_pagal_sienas")),
            "be_angos": bool(e.get("_be_angos")),
            "praejimas": bool(e.get("_praejimas")),
            # 2026-09-25: what the drawing shows in the element's opening (glazing / a swing arc), and a kind
            # that follows the drawing rather than the list
            "nupiesta": e.get("_nupiesta") if e.get("_nupiesta") in ("langas", "durys") else None,
            "tipas_pagal_brezini": bool(e.get("_tipas_pagal_brezini")),
        })
    editable = {"field": "elementai", "kind": "count"}
    walls_page, openings = _wall_openings(room)
    if openings:
        # the sheet the room's outline is drawn on: there the openings can be marked
        stood = _stood_in_walls(elems)
        if stood is not None:
            from .universal_rules import _is_passage
            by_nr = {str(r.get("nr") or "").strip(): r for r in (project.get("patalpos") or []) if isinstance(r, dict)}
            walls_said, short, suggestions = _against_the_walls_stood(
                openings, _listed_beyond(project, room, openings), stood,
                is_passage=lambda w, i: _is_passage(w, i, room, by_nr))
        else:
            walls_said, short, suggestions = _against_the_walls(per_type, openings, _listed_beyond(project, room, openings))
        shown = {"openings": {"page": walls_page, "items": openings}, "suggestions": suggestions}
        where = (walls_page, _outline_rect_pct(room))
    else:
        walls_said, short, suggestions = None, False, []
        shown = {"openings": None, "suggestions": []}
        where = (room.get("puslapio_nr"), region)

    if not details:
        # 2026-09-23: nothing listed here, but every opening the walls show is a door the room BEYOND lists —
        # that door is counted there (universal_rules.mark_shared_doors); this room has nothing to add
        if openings and not short and not suggestions and "prie tos patalpos" in (walls_said or ""):
            return _fact("angos", 0, "vnt.", "read", "sienu_angos", where[0], where[1], walls_said, editable, details=[], **shown)
        return _fact("angos", 0, "vnt.", "missing", "sienu_angos" if openings else "nera",
                     where[0], where[1],
                     walls_said or "Durų ir langų šioje patalpoje neradau — jei jų yra, įrašykite.",
                     editable, details=[], **shown)

    # Summed per type, not per element: two door rows of one door each read as
    # „2 durys", the way he would say it.
    counts = ", ".join(f"{n} {element_label(t, n)}" for t, n in per_type.items() if n) or "Durų ir langų neliko"
    zin = None
    if anchored:
        zin = (int(schedule_page) if schedule_page
               else first_page_of_type(project, "door_window_schedule"))
    if openings:
        sizes = ("Matmenys — iš žiniaraščio" + (f", psl. {zin}. " if zin else ". ")) if anchored else ""
        return _fact("angos", total, "vnt.", "assumed" if short else "read", "sienu_angos",
                     where[0], where[1], f"{counts}. {sizes}{walls_said}", editable, details=details, **shown)
    if anchored:
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
                 f"{counts}. {sentence}", editable, details=details, **shown)


# ── grindys ─────────────────────────────────────────────────────────────────

# `grindu_danga` → the words the sheet uses for it
_FLOOR_LT = {
    "plyteles": "plytelės",
    "minksta": "parketas arba laminatas",
    "be_dangos": "betonas, be dangos",
}


def _floor_by_rule(room: dict) -> str:
    """The floor finish the calculator would give this room — read off the
    same purpose rule, for a room whose floor quantities a choice zeroed."""
    from .universal_rules import FLOOR_COVERINGS, ROOM_TYPE_RULES, normalize_paskirtis
    danga = str(room.get("grindu_danga") or "").strip().lower()
    if danga in FLOOR_COVERINGS:
        return _FLOOR_LT[danga]
    if room.get("tile_floor_override") is not None:
        return "plytelės" if room.get("tile_floor_override") else "parketas arba laminatas"
    if (_f(room.get("plyteles_grindys_m2_override")) or 0) > 0:
        return "plytelės"
    rule = ROOM_TYPE_RULES.get(normalize_paskirtis(room.get("paskirtis") or "")) or {}
    if rule.get("tile_floor") or rule.get("floor") == "tile":
        return "plytelės"
    if rule.get("floor") == "concrete":
        return "betonas, be dangos"
    return "parketas arba laminatas"


def _floor_sheet_page(project: dict) -> int | None:
    """The floor-covering sheet the geometry lane found by its title, if any."""
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    lapai = ((meta.get("geometrija") or {}).get("grindu_dangos") or {}).get("lapai") or []
    try:
        return int(lapai[0]) if lapai else None
    except (TypeError, ValueError):
        return None


def _fact_grindys(project: dict, room: dict,
                  region: list[float] | None) -> dict:
    """Which floor covering this room gets — READ off the floor plan when the
    plan says it (extractor/floor_coverings.py: written in the room, or hatched
    in a legend line's colour), his own choice when he made one, otherwise the
    purpose rule as a QUESTION. The answer is a direct choice of covering
    (`grindu_danga`); until 2026-09-20 the only way to answer was to change the
    room's purpose, which moves its walls and ceiling too."""
    tile = _f(room.get("plyteles_grindys_m2")) or 0.0
    soft = _f(room.get("pvc_grindys_m2")) or 0.0
    danga = str(room.get("grindu_danga") or "").strip().lower()
    saltinis = str(room.get("grindu_danga_saltinis") or "").strip().lower()
    kept_out = (_kept_out_by_choice(room, "grindys")
                or _kept_out_by_choice(room, "plyteles"))
    if danga in _FLOOR_LT:
        value = _FLOOR_LT[danga]
    elif kept_out:
        # the floor quantities are zeroed by the choice; the finish still
        # follows the room's purpose
        value = _floor_by_rule(room)
    elif tile > 0:
        value = "plytelės"
    elif soft > 0:
        value = "parketas arba laminatas"
    else:
        value = "betonas, be dangos"
    editable = {"field": "grindu_danga", "kind": "choice"}
    tail = (" " + _KEPT_OUT_SENTENCE) if kept_out else ""

    ev = room.get("_grindu_danga")
    if danga in _FLOOR_LT and saltinis == "user_override":
        sentence = "Grindų dangą šiai patalpai pasirinkote patys."
        if isinstance(ev, dict) and ev.get("page"):
            # the place on the floor sheet stays the place to look at — and when
            # the plan draws something else, the sheet says so rather than hide it
            page = int(ev["page"])
            rect = ev.get("rect_pct") if isinstance(ev.get("rect_pct"), list) and len(ev["rect_pct"]) == 4 else None
            drawn = str(ev.get("danga") or "").strip().lower()
            if drawn in _FLOOR_LT and drawn != danga:
                verb = "parašyta" if ev.get("irodymas") == "uzrasas" else "nubraižyta"
                sentence += f" Grindų plane ({page} psl.) {verb} kitaip: {_FLOOR_LT[drawn]}."
            return _fact("grindys", value, None, "read", "prielaida", page, rect, sentence + tail, editable)
        page = _floor_sheet_page(project) or first_page_of_type(project, "floor_plan") or room.get("puslapio_nr")
        return _fact("grindys", value, None, "read", "prielaida", page, region_on_page(room, page, region),
                     sentence + tail, editable)

    if danga in _FLOOR_LT and saltinis == "grindu_planas" and isinstance(ev, dict) and ev.get("page"):
        page = int(ev["page"])
        quote = str(ev.get("tekstas") or "").strip()
        if ev.get("irodymas") == "uzrasas":
            sentence = f"Grindų plane ({page} psl.) šioje patalpoje parašyta: „{quote}“."
        else:
            sentence = (f"Grindų plane ({page} psl.) ši patalpa nubraižyta tuo pačiu raštu ir spalva kaip "
                        f"legendos eilutė „{quote}“.")
        rect = ev.get("rect_pct") if isinstance(ev.get("rect_pct"), list) and len(ev["rect_pct"]) == 4 else None
        return _fact("grindys", value, None, "read", "grindu_planas", page, rect, sentence + tail, editable)

    override = (room.get("plyteles_grindys_m2_override") is not None
                or room.get("tile_floor_override") is not None)
    page = _floor_sheet_page(project) or first_page_of_type(project, "floor_plan") or room.get("puslapio_nr")
    rect = region_on_page(room, page, region)
    if override:
        return _fact("grindys", value, None, "read", "grindu_planas", page,
                     rect, "Grindų danga pažymėta šiai patalpai." + tail, editable)

    # the purpose by the label he picks it by on this sheet, never the code
    label = paskirtis_label(room.get("paskirtis"))
    by_purpose = "parinkta pagal patalpos paskirtį" + (f" („{label}“)" if label else "")
    two = room.get("_grindu_dangos_dvi")
    if isinstance(two, dict) and len(two.get("tekstai") or []) >= 2:
        page = int(two.get("page") or page or 0) or page
        quotes = " ir ".join(f"„{str(t).strip()}“" for t in two["tekstai"][:3])
        sentence = (f"{_ASK_FLOOR} Grindų plane ({page} psl.) šioje patalpoje parašytos dvi dangos: {quotes}. "
                    f"Skaičiuoju visą plotą kaip „{value}“ — pasirinkite pagrindinę dangą, o kitos plotą "
                    "pataisykite sąmatoje.")
        return _fact("grindys", value, None, "assumed", "prielaida", page,
                     region_on_page(room, page, region), sentence + tail, editable)

    sheet = _floor_sheet_page(project)
    if sheet:
        sentence = (f"{_ASK_FLOOR} Grindų plane ({sheet} psl.) šiai patalpai dangos neradau — {by_purpose}. "
                    "Patikrinkite grindų plane ir pasirinkite.")
    else:
        sentence = f"{_ASK_FLOOR} Brėžinys nesako — {by_purpose}. Patikrinkite grindų plane ir pasirinkite."
    return _fact("grindys", value, None, "assumed", "prielaida", page, rect,
                 sentence + tail, editable)


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


_HIS_SOURCES = ("user_override", "manual")


def _is_yours(project: dict, room: dict, key: str) -> bool:
    """Whether this fact's value is the CONTRACTOR's — typed, chosen, accepted or
    drawn by him — so the sheet can badge it „jūsų" (2026-09-20: a corrected fact
    differed from a read one only by a sentence; looking down a room nothing
    marked what was his). The same signals a re-read of the drawing keeps
    (frontend/src/lib/mergeReextract.js `roomTouched`)."""
    src = lambda v: str(v or "").strip().lower()      # noqa: E731
    nr = str(room.get("nr") or "").strip()
    overrides = project.get("_overrides") if isinstance(project.get("_overrides"), dict) else {}

    def per_room(name: str) -> bool:
        table = overrides.get(name)
        return isinstance(table, dict) and table.get(nr) is not None

    if key == "plotas":
        return src(room.get("plotas_saltinis")) in _HIS_SOURCES or src(room.get("plotas_source")) in ("manual", "manual_polygon")
    if key == "perimetras":
        return src(room.get("perimetras_saltinis")) in _HIS_SOURCES
    if key == "aukstis":
        return src(room.get("lubu_aukstis_saltinis")) == "user_override" or per_room("lubu_auksciai")
    if key == "apdaila":
        return room.get("_walls_paint_override") is not None or per_room("walls_paint_override")
    if key == "angos":
        return bool(room.get("_angos_user_at")) or any(
            isinstance(e, dict) and e.get("_dydis_user") for e in (room.get("elementai") or []))
    if key == "grindys":
        return src(room.get("grindu_danga_saltinis")) == "user_override" and bool(room.get("grindu_danga"))
    return False


def build_room_facts(project: dict, room_nr: str) -> dict | None:
    """The whole check sheet for one room, or None when there is no such room."""
    room = find_room(project, room_nr)
    if room is None:
        return None
    region = room_region_pct(room)
    facts = [
        _fact_plotas(project, room, region),
        {**_fact_perimetras(project, room, region), **_perimeter_drawing(room)},
        _fact_aukstis(project, room, region),
        _fact_apdaila(project, room, region),
        _fact_angos(project, room, region),
        _fact_grindys(project, room, region),
    ]
    for fact in facts:
        fact["yours"] = _is_yours(project, room, fact["key"])
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

"""Reminders for the whole project — what an estimator commonly forgets, said once, in plain Lithuanian.

Pathon v3 W5-E (E8, E9; plan docs/superpowers/plans/2026-10-18-pathon-v3-wave5-7-plan.md). The list that
`main._merge_interior_results` built in 2026 (hidroizoliacija, gruntas, glaistymas, deformacinė siūlė,
kampų profiliai, GK sandarinimas, LED transformatoriai, gaisro davikliai) lived in a function nothing
called (coverage Table 2.4), so not one of them ever reached the screen. They come back here as NOTICES —
never as quantity rows, never a number added to the estimate — for Patikra and the Sąmata, together with
the CLAUDE.md §1.8 / §8 items nothing else covers:

  · GK „tikslus / praktinis" (§1.8) — both wall sheet counts in the sentence, so he picks one;
  · a wall longer than 8 m (§8.6, deformacinė siūlė);
  · fire-rated assemblies and firestops (§8.9, §8.10) — a specific notice when the drawing's text says
    EI… / „ugniai atspari", otherwise one general reminder;
  · the touch-up buffer on rough walls (§8.13, the paint class for rough walls);
  · the commonly-missed list (§8 „The app should WARN users") — each item only where the sąmata lacks it;
  · two room outlines lying over each other (§8.5) — the same floor or wall counted twice (E9).

A pure function of the stored project (and of the text-layer hits the route found, passed in): no model,
no drawing read here, €0, saves nothing. Every sentence says what to check; a reminder that comes from the
drawing carries the page and the box it stands in (`evidence`).
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any, Iterable

from .scope import is_room_excluded, normalize_apimtis
from .universal_rules import WET_ROOM_PASKIRTYS, gkp_sheet_count, lt_num

_log = logging.getLogger("samatu.reminders")

PATIKRA = "patikra"
SAMATA = "samata"

LONG_WALL_M = 8.0                 # a wall longer than this gets the deformation-joint reminder
ROUGH_PAINT_CLASS = 3             # vision_call._PAINT_CLASS_PROFILES: 3 = rough / fresh-plaster walls
TOUCH_UP_LT = "10–20 %"           # CLAUDE.md §8.13
OVERLAP_MIN_M2 = 0.5              # two outlines must share at least this much floor…
OVERLAP_MIN_SHARE = 0.05          # …and this share of the smaller room, to be a double count, not a shared wall line
EVIDENCE_PAD_PCT = 0.01

# The order the notice lists them in: what can change the estimate most first.
ORDER = ("konturai_uzeina", "ugniai_atsparios", "gk_tikslus_praktinis", "deformacine_siule",
         "dazu_atsarga", "silpnu_sroviu_lizdai", "hidroizoliacija", "gruntas", "glaistymas", "kampu_profiliai",
         "gk_sandarinimas", "led_transformatoriai", "dumu_davikliai")

# Words in the drawing's text layer that mark a fire-rated assembly (EI30, EI 60, REI 90, „ugniai atspari").
FIRE_TERMS_RE = re.compile(r"\b(R?EI\s?(?:15|20|30|45|60|90|120|180))\b|ugniai\s+atspar\w*|ugniaatspar\w*",
                           re.IGNORECASE)

_BEDROOM_CLASSES = ("miegamoji", "miegamasis", "vaiku")


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────

def _f(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) else 0.0


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _name(room: dict) -> str:
    return str(room.get("pavadinimas") or "").strip()


def _label(room: dict) -> str:
    return f"{_nr(room)} {_name(room)}".strip()


def _join_lt(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " ir " + items[-1]


def _rect_of(points: Iterable[Iterable[float]], pad: float = EVIDENCE_PAD_PCT) -> list[float] | None:
    pts = [(float(p[0]), float(p[1])) for p in points or [] if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [round(max(0.0, min(xs) - pad), 5), round(max(0.0, min(ys) - pad), 5),
            round(min(1.0, max(xs) + pad), 5), round(min(1.0, max(ys) + pad), 5)]


def _room_page(room: dict) -> int | None:
    k = room.get("_konturas") if isinstance(room.get("_konturas"), dict) else {}
    for v in (k.get("page"), room.get("puslapio_nr")):
        try:
            if v is not None and int(v) >= 1:
                return int(v)
        except (TypeError, ValueError):
            continue
    return None


def counted_rooms(project: dict) -> list[dict]:
    """The rooms of the estimate: not merged into another, not left out („Neskaičiuoju")."""
    apimtis = normalize_apimtis(project.get("_apimtis"))
    return [r for r in (project.get("patalpos") or [])
            if isinstance(r, dict) and _nr(r) and not r.get("_sujungta_i") and not r.get("_neskaiciuoti")
            and not is_room_excluded(apimtis, _nr(r))]


def samata_rows(project: dict) -> list[dict]:
    """The rows the sąmata shows: `darbu_sarasas` (the table he edits), else the engine's `pozicijos`."""
    rows = project.get("darbu_sarasas")
    if not isinstance(rows, list) or not rows:
        rows = project.get("pozicijos")
    return [r for r in rows or [] if isinstance(r, dict)]


def _row_text(row: dict) -> str:
    # the row's own words, not its section's: „Sienų glaistymas dažymas" is the heading over the painting
    # row too, and would answer „glaistymas is there" for a sąmata that has none
    return " ".join(str(row.get(k) or "") for k in ("aprasymas", "medziagos_aprasymas")).lower()


def _has_row(rows: list[dict], *needles: str) -> bool:
    return any(any(n in _row_text(r) for n in needles) for r in rows)


def _quantity_rows(rows: list[dict], *needles: str) -> list[dict]:
    return [r for r in rows if any(n in str(r.get("aprasymas") or "").lower() for n in needles)
            and _f(r.get("kiekis")) > 0]


def _reminder(rid: str, sentence: str, *, vieta: Iterable[str] = (PATIKRA, SAMATA),
              rooms: list[dict] | None = None, evidence: dict | None = None, tone: str = "info",
              **extra: Any) -> dict:
    return {"id": rid, "kind": rid, "tone": tone, "vieta": list(vieta), "sentence": sentence,
            "rooms": [{"nr": _nr(r), "name": _name(r)} for r in rooms or []], "evidence": evidence, **extra}


# ── one builder per reminder ──────────────────────────────────────────────────────────────────────────

def _gk_tikslus_praktinis(rooms: list[dict], rows: list[dict]) -> dict | None:
    """CLAUDE.md §1.8: „tikslus" (openings deducted) and „praktinis" (measured straight through, the cut-outs
    are waste) — both counts in one sentence; he picks. Only where the estimate already works with GKP."""
    if not _has_row(rows, "gkp", "gipso kartono", "gipskarton"):
        return None
    gross = round(sum(_f(r.get("walls_gross_m2")) for r in rooms), 2)
    if gross <= 0:
        return None
    openings = sum(_f(r.get("windows_deducted_m2")) + _f(r.get("doors_deducted_m2")) for r in rooms)
    net = round(max(0.0, gross - openings), 2)
    tikslus, praktinis = gkp_sheet_count(net), gkp_sheet_count(gross)
    wall_rows = _quantity_rows(rows, "gkp lapai sienoms")
    if wall_rows:
        have = int(sum(_f(r.get("kiekis")) for r in wall_rows))
        head = f"Sąmatoje sienų GKP lapų — {have} vnt.; skaičiuojant tiksliai"
        tail = "patikrinkite, kurį skaičiavimą renkatės."
    else:
        head = "Jei sienos bus apkalamos gipso kartonu, lapų reikės: tiksliai"
        tail = "sąmatoje sienų GKP lapų eilutės nėra — pridėkite tą skaičių, kurį renkatės."
    sentence = (f"{head} (atėmus langus ir duris) — {tikslus} vnt., praktiškai (angų neatimant, išpjovos lieka "
                f"atliekoms) — {praktinis} vnt. (1,2 × 2,5 m lapai, +10 % atliekų); {tail}")
    return _reminder("gk_tikslus_praktinis", sentence, tikslus_vnt=tikslus, praktinis_vnt=praktinis,
                     sienos_m2=gross, sienos_be_angu_m2=net)


def _long_walls(rooms: list[dict]) -> dict | None:
    """CLAUDE.md §8.6: deformation joints in long walls — a wall read longer than 8 m."""
    found: list[tuple[float, dict, dict]] = []
    for r in rooms:
        walls = [w for w in (r.get("_sienos") or []) if isinstance(w, dict) and _f(w.get("ilgis_m")) > LONG_WALL_M]
        if walls:
            w = max(walls, key=lambda x: _f(x.get("ilgis_m")))
            found.append((_f(w.get("ilgis_m")), r, w))
    if not found:
        return None
    found.sort(key=lambda t: -t[0])
    parts = [f"{_label(r)} ({lt_num(m, 1)} m)" for m, r, _w in found[:4]]
    if len(found) > 4:
        parts.append(f"dar {len(found) - 4}")
    where = "Patalpoje" if len(found) == 1 else "Patalpose"
    sentence = (f"{where} {_join_lt(parts)} yra ilgesnė nei {lt_num(LONG_WALL_M, 0)} m siena — tokioje sienoje "
                f"dažnai daroma deformacinė siūlė; patikrinkite projekte ir, jei ji reikalinga, pridėkite eilutę.")
    if len(found) > 1:
        sentence = sentence.replace("yra ilgesnė nei", "yra ilgesnių nei").replace("siena — tokioje sienoje",
                                                                                   "sienų — tokiose sienose")
    _m, room, wall = found[0]
    page = _room_page(room)
    rect = _rect_of(wall.get("edge_pct") or [])
    evidence = {"page": page, "rect_pct": rect} if page and rect else None
    return _reminder("deformacine_siule", sentence, rooms=[r for _m2, r, _w in found], evidence=evidence)


def _fire(rows: list[dict], fire_hits: list[dict] | None) -> dict:
    """CLAUDE.md §8.9 + §8.10: fire-rated assemblies and the firestops of the pipes and cables through them."""
    has_fire_rows = _has_row(rows, "ugniai atspar", "priešgaisrin", "ugniaatspar")
    hits = [h for h in fire_hits or [] if isinstance(h, dict) and h.get("page")]
    if hits:
        first = hits[0]
        pages = sorted({int(h["page"]) for h in hits})
        terms = []
        for h in hits:
            t = str(h.get("text") or "").strip()
            if t and t.lower() not in {x.lower() for x in terms}:
                terms.append(t)
        said = ", ".join(f"„{t}“" for t in terms[:3]) or "ugniai atsparią konstrukciją"
        page_txt = (f"{pages[0]} lape" if len(pages) == 1
                    else "lapuose " + ", ".join(str(p) for p in pages[:5]))
        rows_txt = ("sąmatoje tokių eilučių yra — patikrinkite, ar jos apima visas vietas."
                    if has_fire_rows else "sąmatoje tokių eilučių nėra — pridėkite, jei jos reikalingos.")
        sentence = (f"Brėžinyje ({page_txt}) parašyta {said} — ugniai atspariai pertvarai ar luboms reikia ugniai "
                    f"atsparių GKP plokščių, o vamzdžių ir kabelių praėjimams per jas — priešgaisrinio "
                    f"sandarinimo; {rows_txt}")
        evidence = {"page": int(first["page"]), "rect_pct": first.get("box_pct"), "text": first.get("text")}
        return _reminder("ugniai_atsparios", sentence, evidence=evidence, tone="warning", specific=True)
    sentence = ("Jei kuri nors siena ar lubos turi būti atsparios ugniai, joms reikia ugniai atsparių GKP plokščių, "
                "o vamzdžių ir kabelių praėjimams — priešgaisrinio sandarinimo; brėžinio tekste to neradau, "
                "patikrinkite projekto aiškinamąjį raštą.")
    return _reminder("ugniai_atsparios", sentence, specific=False)


def _touch_up(project: dict, rooms: list[dict]) -> dict | None:
    """CLAUDE.md §8.13: rough walls need 10–20 % more paint than the usual waste."""
    rough = [r for r in rooms if int(_f(r.get("_paint_class"))) == ROUGH_PAINT_CLASS]
    if not rough and int(_f(project.get("paint_class"))) != ROUGH_PAINT_CLASS:
        return None
    sentence = (f"Sienos skaičiuojamos kaip šiurkščios (3 dažų klasė) — tokioms sienoms pataisymams dažų paprastai "
                f"reikia {TOUCH_UP_LT} daugiau, nei įprastai lieka atliekų; patikrinkite dažų kiekį Medžiagose.")
    return _reminder("dazu_atsarga", sentence, rooms=rough)


def _is_wet(room: dict) -> bool:
    cls = str(room.get("paskirtis") or "").strip().lower()
    if cls in WET_ROOM_PASKIRTYS:
        return True
    low = _name(room).lower()
    return any(k in low for k in ("vonia", "vonios", "wc", "dušas", "dušo", "san. mazgas", "skalbykl"))


def _commonly_missed(project: dict, rooms: list[dict], rows: list[dict]) -> list[dict]:
    """The old forgotten-items list, each only where the sąmata has no row for it."""
    out: list[dict] = []
    painted = _has_row(rows, "dažym", "dažai")
    wet = [r for r in rooms if _is_wet(r)]
    if wet and not _has_row(rows, "hidroizoliac"):
        out.append(_reminder(
            "hidroizoliacija",
            f"Drėgnose patalpose ({_join_lt([_label(r) for r in wet[:4]])}) sąmatoje nėra hidroizoliacijos — "
            "grindims, sienų apačiai (0,3 m nuo grindų) ir dušo sienoms iki lubų ji paprastai reikalinga; "
            "pridėkite, jei taip.",
            rooms=wet, tone="warning"))
    if painted and not _has_row(rows, "gruntav", "gruntas"):
        out.append(_reminder("gruntas", "Sąmatoje yra dažymas, bet nėra gruntavimo — gruntas prieš dažymą "
                                        "skaičiuojamas atskira eilute; pridėkite, jei jo reikia."))
    if painted and not _has_row(rows, "glaist"):
        out.append(_reminder("glaistymas", "Sąmatoje yra dažymas, bet nėra glaistymo — paviršiaus paruošimas "
                                           "skaičiuojamas atskira eilute; pridėkite, jei jo reikia."))
    outer = [r for r in rooms if _f(r.get("kampai_isoriniai_m")) > 0]
    reveals = any(_f(r.get("angokrasciai_lm")) > 0 for r in rooms)
    if (outer or reveals) and not _has_row(rows, "kampų", "kampu ", "kampuot", "kampo profil"):
        out.append(_reminder("kampu_profiliai", "Sąmatoje nėra kampų profilių — išoriniams kampams ir "
                                                "angokraščiams jų paprastai reikia; pridėkite, jei taip.",
                             rooms=outer))
    if _has_row(rows, "gkp", "gipso kartono") and not _has_row(rows, "sandarinimo juost"):
        out.append(_reminder("gk_sandarinimas", "Sąmatoje nėra sandarinimo juostos GKP profiliams prie sienų ir "
                                                "lubų — ji dedama po pakraščio profiliais; patikrinkite, ar jos "
                                                "reikia."))
    led = _has_row(rows, "led juost", "led niš") or any(_f(r.get("nisu_metrai")) > 0 for r in rooms)
    if led and not _has_row(rows, "transformator", "maitinimo blok"):
        out.append(_reminder("led_transformatoriai", "Sąmatoje yra LED juostos, bet nėra jų maitinimo blokų "
                                                     "(transformatorių) — patikrinkite, kiek jų reikia ir kur jie "
                                                     "bus paslėpti."))
    bedrooms = [r for r in rooms if str(r.get("paskirtis") or "").strip().lower() in _BEDROOM_CLASSES
                or any(k in _name(r).lower() for k in ("miegam", "vaiko", "vaikų"))]
    if bedrooms and not _has_row(rows, "dūmų", "dumu davikl", "gaisro davikl", "gaisro detektor"):
        out.append(_reminder("dumu_davikliai", "Sąmatoje nėra dūmų daviklių — patikrinkite elektros planą ir, "
                                               "jei jie numatyti miegamuosiuose ar koridoriuje, pridėkite eilutę.",
                             rooms=bedrooms))
    return out


# ── E9: two outlines over each other ──────────────────────────────────────────────────────────────────

# An outline the quantities stand on: the lane's or his own (`_konturas`), or one he corrected or drew. A
# flood-fill or a box synthesised around a label only marks where the room is — its floor comes from the
# room table — so two of them lying over each other count nothing twice.
_MEASURING_SOURCES = ("corrected", "manual")
_MARKER_SOURCES = ("synthesized_from_bbox", "manual_needed")


def outline_measures(room: dict) -> bool:
    src = str(room.get("polygon_source") or "")
    if src in _MARKER_SOURCES:
        return False
    return isinstance(room.get("_konturas"), dict) or src in _MEASURING_SOURCES


def _polygon(room: dict):
    from shapely.geometry import Polygon
    if not outline_measures(room):
        return None
    pts = [(float(p[0]), float(p[1])) for p in room.get("polygon_pct") or []
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:  # noqa: BLE001 — a malformed stored outline asks nothing
        return None
    return poly if (not poly.is_empty and poly.area > 0) else None


def _room_m2(room: dict) -> float:
    k = room.get("_konturas") if isinstance(room.get("_konturas"), dict) else {}
    return _f(k.get("plotas_m2")) or _f(room.get("plotas_m2"))


def outline_overlaps(rooms: list[dict]) -> list[dict]:
    """Pairs of rooms on the same sheet whose outlines share floor — each with the shared m² (from the
    smaller room's own area: the share of its outline the other covers) and the shared box."""
    by_page: dict[int, list[tuple[dict, Any]]] = {}
    for r in rooms:
        page = _room_page(r)
        poly = _polygon(r) if page else None
        if poly is not None:
            by_page.setdefault(page, []).append((r, poly))
    pairs: list[dict] = []
    for page, items in sorted(by_page.items()):
        for i in range(len(items)):
            ra, pa = items[i]
            for j in range(i + 1, len(items)):
                rb, pb = items[j]
                if not pa.intersects(pb):
                    continue
                try:
                    inter = pa.intersection(pb)
                except Exception:  # noqa: BLE001
                    continue
                if inter.is_empty or inter.area <= 0:
                    continue
                small_room, small_poly = (ra, pa) if pa.area <= pb.area else (rb, pb)
                share = inter.area / small_poly.area
                m2 = share * _room_m2(small_room)
                if share < OVERLAP_MIN_SHARE or m2 < OVERLAP_MIN_M2:
                    continue
                x0, y0, x1, y1 = inter.bounds
                pairs.append({"page": page, "a": ra, "b": rb, "m2": round(m2, 2), "share": round(share, 3),
                              "rect_pct": _rect_of([(x0, y0), (x1, y1)])})
    pairs.sort(key=lambda p: -p["m2"])
    return pairs


def _overlaps(rooms: list[dict]) -> list[dict]:
    out = []
    for p in outline_overlaps(rooms):
        a, b = p["a"], p["b"]
        sentence = (f"Patalpų {_label(a)} ir {_label(b)} kontūrai brėžinyje užeina vienas ant kito (apie "
                    f"{lt_num(p['m2'], 1)} m²) — tos pačios grindys ar sienos gali būti suskaičiuotos du kartus; "
                    f"patikrinkite abiejų patalpų kontūrus.")
        out.append(_reminder("konturai_uzeina", sentence, vieta=(PATIKRA,), rooms=[a, b], tone="warning",
                             evidence={"page": p["page"], "rect_pct": p["rect_pct"]}, plotas_m2=p["m2"]))
        out[-1]["id"] = f"konturai_uzeina:{_nr(a)}:{_nr(b)}"
    return out


# ── data and TV outlets (E4, CLAUDE.md §1.13) ─────────────────────────────────────────────────────────

ELECTRIC_SECTION = "Elektros instaliacijos darbai"
# (kind, the words of a legend row / a sąmata row that name it, the blank row offered when none exists)
OUTLET_KINDS = (
    ("interneto", re.compile(r"internet|duomen|kompiuter|\brj ?45\b|\blan\b|\bcat ?[56]", re.IGNORECASE),
     "Interneto lizdų montavimas", "interneto"),
    ("tv", re.compile(r"\btv\b|televiz|anten", re.IGNORECASE), "TV lizdų montavimas", "TV"),
)


def outlet_kind(text: str | None) -> str | None:
    """`interneto` / `tv` for a legend or sąmata row text that names a data or TV outlet, else None."""
    t = str(text or "")
    if not re.search(r"lizd|rozet|jungtis|taškas|taskas|outlet|socket", t, re.IGNORECASE):
        return None
    hits = [k for k, rx, _row, _lt in OUTLET_KINDS if rx.search(t)]
    return hits[0] if len(hits) == 1 else None


def _outlets(rows: list[dict], legend_rows: list[dict] | None) -> list[dict]:
    """One reminder per outlet kind the sąmata has no row for. With the legend's row („Interneto lizdas")
    it says to count it with „Kiekis"; without one it asks whether there will be any. Either way it offers
    a blank row (kiekis empty) he adds himself — a count reaches the row through the legend count, never
    from here. `legend_rows` None = no legend accepted for the project yet."""
    present = {outlet_kind(_row_text(r)) for r in rows}
    in_legend: dict[str, str] = {}
    for lr in legend_rows or []:
        if not isinstance(lr, dict):
            continue
        text = str(lr.get("name") or lr.get("text") or "")
        k = outlet_kind(text)
        if k and k not in in_legend:
            in_legend[k] = text.strip()
    out = []
    for kind, _rx, row_name, lt in OUTLET_KINDS:
        if kind in present:
            continue
        blank = {"aprasymas": row_name, "mato_vnt": "vnt", "kiekis": None, "skyrius": ELECTRIC_SECTION}
        if kind in in_legend:
            sentence = (f"Brėžinio legendoje yra „{in_legend[kind]}“, o sąmatoje tokios eilutės nėra — suskaičiuokite "
                        f"juos įrankiu „Kiekis“ ir įrašykite kiekį į eilutę „{row_name}“.")
        elif legend_rows:
            sentence = (f"Brėžinio legendoje {lt} lizdų nėra — ar jų bus? Jei taip, pridėkite eilutę "
                        f"„{row_name}“ ir įrašykite kiekį.")
        else:   # no legend marked yet: say only what the sąmata lacks
            sentence = (f"Sąmatoje {lt} lizdų nėra — ar jų bus? Jei taip, pridėkite eilutę "
                        f"„{row_name}“ ir įrašykite kiekį (juos galima suskaičiuoti elektros plane įrankiu „Kiekis“).")
        r = _reminder("silpnu_sroviu_lizdai", sentence, vieta=(SAMATA,), add_row=blank,
                      legendoje=kind in in_legend)
        r["id"] = f"silpnu_sroviu_lizdai:{kind}"
        out.append(r)
    return out


# ── the whole project ─────────────────────────────────────────────────────────────────────────────────

def build_reminders(project: dict, *, fire_hits: list[dict] | None = None,
                    legend_rows: list[dict] | None = None) -> dict:
    """{reminders: [...], count} — see the module docstring. `fire_hits`: where the drawing's text layer
    names a fire-rated assembly ([{page, box_pct, text}], the route reads them; None = not read)."""
    if not isinstance(project, dict):
        return {"reminders": [], "count": 0}
    rooms = counted_rooms(project)
    rows = samata_rows(project)
    out: list[dict] = []
    builders = (
        lambda: _overlaps(rooms),
        lambda: [_fire(rows, fire_hits)] if rooms else [],
        lambda: [_gk_tikslus_praktinis(rooms, rows)],
        lambda: [_long_walls(rooms)],
        lambda: [_touch_up(project, rooms)],
        lambda: _outlets(rows, legend_rows) if rooms else [],
        lambda: _commonly_missed(project, rooms, rows),
    )
    for build in builders:
        try:
            out.extend(x for x in build() if x)
        except Exception as exc:  # noqa: BLE001 — one malformed field never takes the list down
            _log.warning("reminder skipped: %r", exc)
    # the general fire reminder (nothing in the drawing's text) says the least — it goes last
    out.sort(key=lambda r: len(ORDER) if (r["kind"] == "ugniai_atsparios" and not r.get("specific"))
             else ORDER.index(r["kind"]))
    return {"reminders": out, "count": len(out)}


def find_fire_terms(pages_text: Iterable[tuple[int, str]]) -> list[str]:
    """The fire-rating words in plain page texts — [(page, text)] → the matched words (tests, the route's
    fallback when PDFium gives no boxes)."""
    found: list[str] = []
    for _page, text in pages_text:
        for m in FIRE_TERMS_RE.finditer(text or ""):
            found.append(m.group(0))
    return found

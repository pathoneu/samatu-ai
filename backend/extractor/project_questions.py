"""Patikra as a short list of QUESTIONS for the whole project — „programa siūlo, jūs patvirtinate".

Founder, 2026-09-21, after walking a real project on the check sheet: „viskas pasižymi labai gerai ir
tiksliai… bet per daug veiksmų visokių būtų rangovui". Measured on that project: 66 facts on screen
(11 rooms × 6), 22 of them wait for a person — and those 22 are THREE kinds of question. The sheet
showed all 66 with equal weight and gave every kind of fix its own interaction.

Nothing is read anew here. Every question is made of the very facts the room sheet shows
(`room_facts.build_room_facts`) whose status is not `read`; this module only GROUPS them — one question
per kind for the whole project — and gives each the program's own proposed answer, so the usual action
is „Tinka". A pure function of the stored project: no drawing, no Vision, fast enough to ask again
after every answer (an answer settles other questions: a room he points at gets its walls read and
leaves the perimeter list by itself).

Order (`ORDER`) is the order that lets one answer settle the next: the height first (one number, most
rows depend on it), then what re-reads walls (an outline, a shared space), then the numbers, then the
openings and the finishes.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from .room_facts import _DOOR_TIPAI, _FLOOR_LT, _anga_word, _f, build_room_facts, element_label, lt_num
from .scope import is_room_excluded, normalize_apimtis
from .universal_rules import DOOR_WIDTH_TOL_M

_log = logging.getLogger("samatu.project_questions")

ORDER = ("aukstis", "konturas", "erdve", "perimetras", "plotas", "angos", "durys", "lentele_durys", "lentele_langai",
         "lentele_zymos", "grindys", "lentele_apdaila", "apdaila", "lentele_suma")
# The drawing's schedules against what was read elsewhere (Pathon v3 W3-A, `build_questions(lenteles=True)`):
# `lentele_durys` / `lentele_langai` — the schedule's count against the openings drawn in the walls (answer
# `reconcile`, proposal = drawn; the answer is his record `_lenteliu_sprendimai[id]`, the estimate is not
# changed by it); `lentele_apdaila` — the finish schedule's floor against the floor plan's (answer `choices` on
# `grindu_danga`, proposal = the plan); `lentele_suma` — a table's own sum against the rooms' (answer `info`).
RECONCILE_KINDS = ("lentele_durys", "lentele_langai", "lentele_zymos", "lentele_apdaila", "lentele_suma")
DECISIONS_KEY = "_lenteliu_sprendimai"
_RECONCILE_CHOICES = ("brezinys", "ziniarastis")
SUM_TOL_M2 = 0.5                 # a table's sum and the rooms' agree within this…
SUM_TOL_SHARE = 0.005            # …or this share of the sum

_WALLS_CHOICES = [{"value": 1, "label": "dažomos"}, {"value": 0, "label": "nedažomos"}]
_DOORS_CHOICES = [{"value": 1, "label": "beapvadinės (paslėpta stakta)"}, {"value": 0, "label": "su apvadais"}]
# the frame-type sources that need no confirming: his own choice, the drawing's door schedule or a
# governing note (universal_rules.settle_frameless_default)
_DOORS_SETTLED = ("jusu", "ziniarastis", "ziniarastis_misrus", "pastaba")


def _nr(room: dict) -> str:
    return str(room.get("nr") or "").strip()


def _name(room: dict) -> str:
    return " ".join(part for part in (_nr(room), str(room.get("pavadinimas") or "").strip()) if part)


def _rooms_word(n: int) -> str:
    """„1 patalpą", „2 patalpas", „10 patalpų" — the accusative the titles need."""
    if n % 10 == 1 and n % 100 != 11:
        return "patalpą"
    if n % 10 in range(2, 10) and n % 100 not in range(12, 20):
        return "patalpas"
    return "patalpų"


def _in_rooms(n: int) -> str:
    return "patalpoje" if n % 10 == 1 and n % 100 != 11 else "patalpose"


def _item(room: dict, fact: dict, **extra: Any) -> dict:
    return {"room_nr": _nr(room), "room_name": str(room.get("pavadinimas") or "").strip(),
            "field": (fact.get("editable") or {}).get("field"), "unit": fact.get("unit"),
            "sentence": fact.get("sentence") or "", "page": (fact.get("source") or {}).get("page"), **extra}


def _q(kind: str, answer: str, title: str, why: str, items: list[dict], *, qid: str | None = None,
       unit: str | None = None, **extra: Any) -> dict:
    return {"id": qid or kind, "kind": kind, "answer": answer, "title": title, "why": why, "unit": unit,
            "items": items, "manual": [], **extra}


# ── one builder per kind: (rooms with their facts) → a question, or None ─────────────────────────────

def _ask_aukstis(rows: list[tuple[dict, dict]], everyone: list[tuple[dict, dict]]) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == "aukstis"]
    if not asked:
        return None
    items = [_item(r, f, proposed=_f(f.get("value"))) for r, f in asked]
    in_use = Counter(i["proposed"] for i in items if i["proposed"] is not None)
    proposed = in_use.most_common(1)[0][0] if in_use else None
    # where a height WAS read — the reason the others are computed with it
    written = [(r, f) for r, f in everyone
               if f["key"] == "aukstis" and f["status"] == "read" and not f.get("yours") and _f(f.get("value"))]
    n = len(items)
    if proposed is None:
        why = "Lubų aukščio brėžinyje neradau — be jo sienų ploto suskaičiuoti negaliu."
    elif written:
        same = [r for r, f in written if abs(_f(f["value"]) - proposed) < 0.005] or [r for r, _ in written]
        where = ", ".join(_nr(r) for r in same[:6]) + ("…" if len(same) > 6 else "")
        others = "Kitai patalpai" if n == 1 else f"Kitoms {n} patalpoms"
        why = (f"Aukštį radau užrašytą tik {_in_rooms(len(same))} {where}: {lt_num(proposed)} m. "
               f"{others} imu tiek pat. Pagal jūsų skaičių perskaičiuosiu sienų plotus.")
    else:
        why = f"Lubų aukščio brėžinyje neradau — skaičiuoju su {lt_num(proposed)} m. Pagal jūsų skaičių perskaičiuosiu sienų plotus."
    return _q("aukstis", "number_all", "Kokio aukščio lubos?", why, items, unit="m", proposed=proposed)


def _proposal_sentence(nr: str, cand: dict) -> str:
    """2026-09-23 (objektas_h tambūras): what the walls close around the number is shown and offered — with
    the reason the program did not take it itself, and the two ways round it."""
    area, table, perim = _f(cand.get("plotas_m2")), _f(cand.get("plotas_uzrasas_m2")), _f(cand.get("perimetras_m"))
    pct = ""
    if area is not None and table:
        pct = f" ({'+' if area >= table else '−'}{lt_num(abs(area - table) / table * 100, 0)} %)"
    walls = f" (sienų {lt_num(perim)} m)" if perim else ""
    return (f"Prie numerio {nr} sienos uždaro {lt_num(area)} m²{walls}, lentelėje {lt_num(table)} m²{pct} — todėl "
            "kontūro pats nepriėmiau. Jei tai visa patalpa — „Tinka“. Jei patalpa didesnė, spustelėkite kitoje jos "
            "vietoje brėžinyje. Arba įrašykite sienų ilgį ranka.")


def _ask_konturas(rows: list[tuple[dict, dict]]) -> dict | None:
    items = []
    for r, f in rows:
        # a room whose walls gave it no outline — and that does not share its space (a click inside a
        # shared space would only find the shared space again: that is the `erdve` question)
        if f["key"] != "perimetras" or f.get("outline") is not None or not f.get("outline_reason"):
            continue
        extra: dict[str, Any] = {"proposed": None, "reason": str(f["outline_reason"]),
                                 "page": (r.get("_vieta") or {}).get("page") or r.get("puslapio_nr"),
                                 # the number the rows are computed with today — the field „Sienų ilgis ranka" opens on it
                                 "perimetras_dabar": _f(r.get("perimetras_m"))}
        cand = f.get("outline_proposal")
        if isinstance(cand, dict) and cand.get("polygon_pct"):
            extra["proposed_outline"] = cand
            extra["sentence"] = _proposal_sentence(_nr(r), cand)
        items.append(_item(r, f, **extra))
    if not items:
        return None
    n = len(items)
    title = (f"Parodykite patalpą {_name(_room_of(rows, items[0]['room_nr']))} brėžinyje" if n == 1
             else f"Parodykite {n} {_rooms_word(n)} brėžinyje")
    why = ("Šios patalpos ribų brėžinyje neradau. Spustelėkite jos viduje — kontūrą pagal sienas nubrėšiu pats ir "
           "perskaitysiu sienų ilgius." if n == 1 else
           "Šių patalpų ribų brėžinyje neradau. Spustelėkite kiekvienos viduje — kontūrą pagal sienas nubrėšiu pats ir "
           "perskaitysiu sienų ilgius.")
    return _q("konturas", "outline", title, why, items)


def _room_of(rows: list[tuple[dict, dict]], nr: str) -> dict:
    return next(r for r, _ in rows if _nr(r) == nr)


def _ask_erdves(rows: list[tuple[dict, dict]], by_nr: dict[str, dict]) -> list[dict]:
    out, seen = [], set()
    for r, f in rows:
        outline = f.get("outline") if f["key"] == "perimetras" else None
        space = outline.get("open_space") if isinstance(outline, dict) else None
        if not isinstance(space, dict) or outline.get("polygon_pct"):
            continue
        members = sorted(str(n) for n in (space.get("nariai") or []))
        key = "+".join(members)
        if len(members) != 2 or key in seen or not all(m in by_nr for m in members):
            continue
        seen.add(key)
        a, b = (by_nr[m] for m in members)
        areas = [_f(x.get("plotas_m2")) for x in (a, b)]
        # 2026-09-23: asked only when the lane could NOT propose the boundary itself (geometry_lane divides a
        # two-room space by its own proposal); the founder: „o koks tau skirtumas, kur riba?" — said plainly
        by_area = (f" Plotus imu iš lentelės ({lt_num(areas[0])} ir {lt_num(areas[1])} m²) — jų neperskaičiuoju."
                   if all(areas) else " Plotus imu iš lentelės — jų neperskaičiuoju.")
        why = ("Sienos tarp šių patalpų nėra, o ribos pats pasiūlyti negalėjau — nubrėžkite ją." + by_area
               + " Riba reikalinga tik sienų ilgiams paskirstyti tarp dviejų patalpų: abiejų sienų suma nuo jos "
               "nesikeičia, milimetrų tikslumo nereikia.")
        items = [{"room_nr": m, "room_name": str(by_nr[m].get("pavadinimas") or "").strip(), "field": None,
                  "unit": "m²", "proposed": _f(by_nr[m].get("plotas_m2")), "sentence": "",
                  "page": space.get("page") or by_nr[m].get("puslapio_nr")} for m in members]
        out.append(_q("erdve", "split", f"Kur riba tarp patalpų {_name(a)} ir {_name(b)}?", why, items,
                      qid=f"erdve:{key}"))
    return out


def _ask_numbers(kind: str, rows: list[tuple[dict, dict]], one: str, many: str, why: str) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == kind]
    if not asked:
        return None
    items = []
    for r, f in asked:
        # a blank shows the number the rows are computed with as a suggestion; an assumption shows it as the value
        proposed = _f(f.get("value")) if f.get("value") is not None else _f((f.get("suggestion") or {}).get("value"))
        items.append(_item(r, f, proposed=proposed))
    n = len(items)
    title = one.format(room=_name(asked[0][0])) if n == 1 else many.format(n=n)
    return _q(kind, "numbers", title, why, items, unit=asked[0][1].get("unit"))


CHECKED_OPENINGS_KEY = "_angos_patikrinta_at"   # room: he answered its door and window count on the question card


def _opening_check(fact: dict) -> tuple[str, str]:
    """(what does not match — one or two short sentences; the room sheet's full account, for a second look) for a
    room whose doors and windows no one click can settle.

    2026-10-06, contractor walkthrough on objektas_h: the question printed the fact's own sentence — every
    opening with its width, then „2 durys sąraše, kurioms angos sienose nematau" — and he could not tell what
    was wrong or what to do. The mismatch is now said first, in his terms (the list against the walls); the
    full account stays beside it for a second look. Counted off the fact's own element rows, so the numbers
    are the ones the room sheet shows.

    2026-10-19 (founder, first walk of v3: „negaliu iškart vietoje pataisyti to, ką reikia"): the card answers
    the count itself (`_opening_numbers` — the fields „Durų" / „Langų" pre-filled with what the walls show), so
    the sentence no longer sends him to the room: it says what does not match, the card says what „Tinka" does.

    2026-10-06: leftover openings held back from the one-click list because a listed window (or door) of
    that kind stands in no opening (`fact["withheld"]`, room_facts._against_the_walls_stood) are said with
    both widths — the listed unit and the openings left, most likely the same one at another width."""
    said = str(fact.get("sentence") or "").strip()
    listed = unbacked = 0
    for d in fact.get("details") or []:
        if not isinstance(d, dict) or (d.get("tipas") or "") not in _DOOR_TIPAI:
            continue
        n = int(_f(d.get("kiekis")) or 0)
        if d.get("be_angos"):                     # a door the walls show no opening for (universal_rules)
            unbacked += n
        if not d.get("praejimas"):                # a passage is no door of the list
            listed += n
    # the held-back sentence without its „go and fix it on the room sheet" tail — the card fixes it
    held = {str(w.get("tipas") or ""): str(w.get("sentence") or "").split(" Patikrinkite brėžinyje;")[0].strip()
            for w in fact.get("withheld") or [] if isinstance(w, dict) and w.get("sentence")}
    heads = []
    if held.get("duris"):
        heads.append(held["duris"])               # names the doors no opening backs and the openings left
    elif unbacked:
        doors = f"Sąraše {listed} {element_label('duris', listed)}"
        fits = max(0, listed - unbacked)
        heads.append(f"{doors}, o sienose — tik {fits} {_anga_word(fits)} durims: {unbacked} durų sienose neradau."
                     if fits else f"{doors}, bet sienose angų joms neradau.")
    if held.get("langas"):
        heads.append(held["langas"])
    elif int(_f(fact.get("langai_be_angos")) or 0) > 0:
        # listed windows no opening took, none left beside them (2026-10-06: his „+" is kept, not cut)
        loose = int(_f(fact.get("langai_be_angos")) or 0)
        windows = sum(int(_f(d.get("kiekis")) or 0) for d in fact.get("details") or []
                      if isinstance(d, dict) and d.get("tipas") == "langas")
        fits = max(0, windows - loose)
        lango = "lango" if loose % 10 == 1 and loose % 100 != 11 else "langų"
        heads.append(f"Sąraše {windows} {element_label('langas', windows)}, o sienose — tik {fits} {_anga_word(fits)} "
                     f"langams: {loose} {lango} sienose neradau." if fits
                     else f"Sąraše {windows} {element_label('langas', windows)}, bet sienose "
                     + ("angos jam neradau." if element_label("langas", windows) == "langas" else "angų jiems neradau."))
    if heads:
        return " ".join(heads), said
    if not fact.get("details") and not (fact.get("openings") or {}).get("items"):
        return "Durų ir langų šioje patalpoje neradau — šios patalpos sienų brėžinyje neperskaičiau.", ""
    if fact.get("status") == "assumed":
        # the walls show more openings than the list has doors and windows, and none of them is one a click
        # could add (a door to a room that has its doors, a window to a room that has its windows)
        return "Sienose matau daugiau angų, nei sąraše yra durų ir langų.", said
    return said, ""


def _opening_proposal(numbers: dict) -> dict:
    """What the card's fields open on: as drawn — except that a room whose listed doors the walls show NO
    opening for at all keeps one of them. Every room has a way in; walls with no door opening at all mean the
    walls missed it (the walls pass keeps such a door for the same reason), not that the room has none."""
    d, w = numbers["durys"], numbers["langai"]
    doors = d["sienose"] if d["sienose"] or not d["sarase"] else 1
    return {"durys": doors, "langai": w["sienose"]}


def _opening_numbers(room: dict, fact: dict) -> dict:
    """The two numbers per kind the question card shows for a room to check (2026-10-19): how many doors
    (windows) the list has, how many the walls show — the listed units an opening backs plus the openings
    of that kind held back from the one-click list (`withheld`: most likely the same units at another
    width) — and those free openings themselves, which the card's answer stands the units in. The proposal
    is the walls' number (as drawn, the schedule reconcile's rule). Nothing is changed here.

    Counted the walls pass's way (room_facts._stood_in_walls): a door marked `_be_angos` stands in no
    opening, a window's units beyond its `_anga_ks` stand in none; a room the pass has not seen (an older
    blob, or no walls read) shows the list's own numbers on both sides."""
    from .universal_rules import kiekis_units
    els = [e for e in (room.get("elementai") or []) if isinstance(e, dict)]
    stood = any(e.get("_anga_ks") or e.get("_be_angos") or e.get("_praejimas") for e in els)
    doors = [e for e in els if (e.get("tipas") or "") in _DOOR_TIPAI and not e.get("_praejimas")]
    windows = [e for e in els if (e.get("tipas") or "") == "langas"]
    units = lambda e: kiekis_units(_f(e.get("kiekis")))  # noqa: E731
    listed_d = sum(units(e) for e in doors)
    backed_d = listed_d - (sum(units(e) for e in doors if e.get("_be_angos")) if stood else 0)
    listed_w = sum(units(e) for e in windows)
    backed_w = sum(min(units(e), len(e.get("_anga_ks") or [])) for e in windows) if stood else listed_w
    held = {str(w.get("tipas") or ""): w for w in fact.get("withheld") or [] if isinstance(w, dict)}

    def free(tipas: str) -> list[dict]:
        return [{"plotis_m": _f(o.get("plotis_m")), "i": str(o.get("i") or "")}
                for o in (held.get(tipas) or {}).get("openings") or [] if isinstance(o, dict) and _f(o.get("plotis_m"))]

    free_d, free_w = free("duris"), free("langas")
    return {"durys": {"sarase": listed_d, "sienose": backed_d + len(free_d), "laisvos": free_d},
            "langai": {"sarase": listed_w, "sienose": backed_w + len(free_w), "laisvos": free_w},
            "sienos": isinstance(room.get("_angos_sienose"), dict),
            "angos_brezinyje": len(((fact.get("openings") or {}).get("items")) or [])}


def _offered_from_beyond(offered: list[dict], nr: str, s: dict) -> bool:
    """The same opening already offered from the room on its other side (2026-10-06, objektas_a: the bedroom
    and the bathroom each offered a door into the one 1,57 m opening between them — one hole, two ticks, and
    „Tinka" would have listed that door in both rooms). Neither room lists a door for it, so each room's sheet
    offers it; the question offers it once — from the room asked first — each offer pairing with one.
    Remembers the doors offered so far in `offered`."""
    if s.get("tipas") not in _DOOR_TIPAI:
        return False
    toward, width = str(s.get("i") or ""), _f(s.get("plotis_m"))
    for o in offered:
        if (not o["paired"] and o["nr"] == toward and o["i"] == nr and width is not None and o["w"] is not None
                and abs(o["w"] - width) <= DOOR_WIDTH_TOL_M):
            o["paired"] = True
            return True
    offered.append({"nr": nr, "i": toward, "w": width, "paired": False})
    return False


def _ask_angos(rows: list[tuple[dict, dict]]) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == "angos"]
    if not asked:
        return None
    items, manual = [], []
    offered: list[dict] = []
    for r, f in asked:
        suggestions = [s for s in (f.get("suggestions") or []) if isinstance(s, dict)]
        for s in suggestions:
            if _offered_from_beyond(offered, _nr(r), s):
                continue
            items.append(_item(r, f, proposed=True, tipas=s.get("tipas"), plotis_mm=s.get("plotis_mm"),
                               aukstis_mm=s.get("aukstis_mm"), i=s.get("i"), plotis_m=s.get("plotis_m"),
                               label=s.get("label"), line_pct=s.get("line_pct"),
                               page=((f.get("openings") or {}).get("page") or (f.get("source") or {}).get("page"))))
        # a room whose leftover openings were held back (2026-10-06) is named for a look even when it also
        # has an opening to offer — the held-back ones are said nowhere else in the question
        if (not suggestions or f.get("withheld")) and not r.get(CHECKED_OPENINGS_KEY):
            # a room whose count he answered on the card (`_angos_patikrinta_at`) is answered — asking again
            # would be a question about OUR evidence, not about his estimate
            sentence, details = _opening_check(f)
            numbers = _opening_numbers(r, f)
            src = f.get("source") or {}
            manual.append({"room_nr": _nr(r), "room_name": str(r.get("pavadinimas") or "").strip(),
                           "sentence": sentence, "details": details, "page": src.get("page"),
                           "rect_pct": src.get("rect_pct"), **numbers,
                           "proposed": _opening_proposal(numbers)})
    n = len(items)
    if n:
        anga = "angą, kurios" if n % 10 == 1 and n % 100 != 11 else "angas, kurių" if n % 10 in range(2, 10) and n % 100 not in range(12, 20) else "angų, kurių"
        title = f"Sienose matau {n} {anga} nėra durų ir langų sąraše"
        why = ("Plotį paėmiau iš sienų brėžinio, aukštį — standartinį (durys 2,10 m, langas 1,50 m). "
               "Plotį, aukštį ir rūšį galite pataisyti čia pat; nuimkite varnelę, jei tai ne durys ir ne langas.")
    else:
        m = len(manual)
        if not m:
            return None
        title = f"Durys ir langai: patikrinkite {m} {_rooms_word(m)}"
        # 2026-10-19: the count is answered on the card — the sentence says what the answer does
        why = ("Įrašykite, kiek durų ir langų yra " + ("šioje patalpoje" if m == 1 else "kiekvienoje patalpoje")
               + " — siūlau tiek, kiek nubraižyta sienose. Pagal jūsų skaičių perskaičiuosiu angokraščius, "
               "dažomą sienų plotą ir grindjuostes.")
    q = _q("angos", "openings", title, why, items, unit="vnt.")
    q["manual"] = manual
    return q


def _ask_durys(project: dict, rooms: list[dict]) -> dict | None:
    """ONE question for the whole project (2026-09-23): are the interior doors frameless (beapvadinės) or
    with casings? A frameless door draws exactly like a framed one, so the plan's symbols cannot settle it —
    only the drawing's TEXT (a door schedule, a note, the openings annotated for frameless doors, the door
    products on a finish board) or the person can. Asked while the frame type rests on the symbols alone or
    on nothing (universal_rules.settle_frameless_default: `brezinys`, `nera_pozymiu`), on evidence that
    names only some doors (`anotacija`, `gaminiai`), or on a door schedule some rows of which name both types
    (`ziniarastis_neaiskus` — then the question is about those doors); the proposal is what the estimate
    computes with now. The answer lands as `_overrides.vidaus_durys_beapvadines`."""
    from copy import deepcopy
    from .universal_rules import settle_frameless_default, _is_interior_door
    interior = [el for r in rooms for el in (r.get("elementai") or []) if _is_interior_door(el)]
    if not interior:
        return None
    try:
        settled = settle_frameless_default(deepcopy(rooms), overrides=project.get("_overrides") or {},
                                           door_types=project.get("_door_types"), schedule=project.get("_duru_ziniarastis"))
    except Exception:  # noqa: BLE001 — a malformed blob asks nothing rather than breaking the list
        return None
    if settled.get("source") in _DOORS_SETTLED:
        return None
    proposed = 1 if settled.get("value") else 0
    n = sum(int(el.get("kiekis") or 1) for el in interior)
    name = "Visos vidaus durys"
    why = ("Beapvadinės durys plane piešiamos taip pat kaip su apvadais, todėl iš simbolio to nustatyti negalima. "
           "Nuo atsakymo priklauso eilutė „Durų angų paruošimas beapvadinėms durims“: su apvadais ji nereikalinga. "
           "Lauko durys čia neįskaitomos.")
    if settled.get("source") == "ziniarastis_neaiskus":
        # the schedule settles its clear rows itself; the answer is about the doors its unclear rows list
        sch = project.get("_duru_ziniarastis") or {}
        codes = [str(c) for c in (sch.get("neaiskus_kodai") or []) if c]
        name = ("Durys " + ", ".join(codes)) if codes else "Neaiškaus tipo žiniaraščio durys"
        n = int(_f(sch.get("neaiskios")) or 0) or n
        why = (f"Durų žiniaraštyje šių durų {'eilutėse' if len(codes) > 1 else 'eilutėje'} užrašyta ir „be apvadų“, "
               "ir „su apvadais“, todėl jų tipo iš brėžinio nustatyti negalima. Nuo atsakymo priklauso, ar jos įeina "
               "į eilutę „Durų angų paruošimas beapvadinėms durims“; kitos žiniaraščio durys skaičiuojamos taip, "
               "kaip ten užrašyta.")
    item = {"room_nr": "", "room_name": name, "field": "vidaus_durys_beapvadines", "unit": None,
            "sentence": str(settled.get("sakinys") or ""), "page": None, "proposed": proposed,
            "proposed_label": _DOORS_CHOICES[0]["label"] if proposed else _DOORS_CHOICES[1]["label"],
            "choices": _DOORS_CHOICES, "count": n}
    return _q("durys", "choices", "Vidaus durys — beapvadinės ar su apvadais?", why, [item])


def _ask_grindys(rows: list[tuple[dict, dict]]) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == "grindys"]
    if not asked:
        return None
    by_label = {label: value for value, label in _FLOOR_LT.items()}
    choices = [{"value": value, "label": label} for value, label in _FLOOR_LT.items()]
    items = [_item(r, f, proposed=by_label.get(str(f.get("value") or "")), proposed_label=str(f.get("value") or ""),
                   choices=choices) for r, f in asked]
    n = len(items)
    title = (f"Kokia grindų danga patalpoje {_name(asked[0][0])}?" if n == 1 else f"Kokia grindų danga šiose {n} patalpose?")
    return _q("grindys", "choices", title,
              # a plan that writes TWO coverings in a room asks too — the item's own sentence says which
              ("Brėžinys šių patalpų dangos vienareikšmiškai nepasako — parinkau pagal patalpos paskirtį." if n > 1 else
               "Brėžinys šios patalpos dangos vienareikšmiškai nepasako — parinkau pagal patalpos paskirtį.")
              + " Pagal jūsų pasirinkimą perskaičiuosiu grindų dangos eilutes.", items)


def _ask_apdaila(rows: list[tuple[dict, dict]]) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == "apdaila"]
    if not asked:
        return None
    items = []
    for r, f in asked:
        painted = 0 if "nedažomos" in str(f.get("value") or "").split(";")[0] else 1
        items.append(_item(r, f, proposed=painted, proposed_label=str(f.get("value") or ""), choices=_WALLS_CHOICES))
    n = len(items)
    title = (f"Ar dažomos patalpos {_name(asked[0][0])} sienos?" if n == 1 else f"Ar dažomos šių {n} patalpų sienos?")
    return _q("apdaila", "choices", title,
              "Sienų apdailos brėžinyje neradau — parinkau pagal patalpos paskirtį. Nedažomų sienų plotą išimsiu iš "
              "dažymo eilučių.",
              items)


# ── the drawing's schedules against what was read elsewhere (Pathon v3 W3-A) ──────────────────────────

def _decided(project: dict, qid: str) -> bool:
    dec = project.get(DECISIONS_KEY) if isinstance(project.get(DECISIONS_KEY), dict) else {}
    return dec.get(qid) not in (None, "")


def _doors_word(n: int) -> str:
    """„1 durys", „3 durys", „7 durų" — durys has no singular."""
    return "durų" if (n % 10 == 0 or 11 <= n % 100 <= 19) else "durys"


def _windows_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "langas"
    if n % 10 in range(2, 10) and n % 100 not in range(12, 20):
        return "langai"
    return "langų"


def _drawn_openings(rooms: list[dict]) -> dict[str, dict]:
    """Per room whose walls were read (`_angos_sienose`): the doors and windows drawn in them — a door between
    two such rooms is counted once, from the lower number (api/detect_run.openings_count's rule)."""
    outlined = {_nr(r) for r in rooms if isinstance(r.get("_angos_sienose"), dict)}
    per: dict[str, dict] = {}
    for r in rooms:
        rec = r.get("_angos_sienose") if isinstance(r.get("_angos_sienose"), dict) else None
        if rec is None:
            continue
        d = {"durys": 0, "durys_vidaus": 0, "langai": 0, "page": rec.get("page")}
        for a in rec.get("angos") or []:
            if not isinstance(a, dict):
                continue
            beyond = str(a.get("i") or "")
            if a.get("nupiesta") == "durys":
                if beyond in outlined and beyond < _nr(r):
                    continue
                d["durys"] += 1
                d["durys_vidaus"] += beyond != "laukas"
            elif a.get("nupiesta") == "langas":
                d["langai"] += 1
        per[_nr(r)] = d
    return per


def _ask_lentele_angos(project: dict, rooms: list[dict], kind: str) -> dict | None:
    """„Durų žiniaraštyje — 7 durys, sienose rasta 5. Kurios teisingos?" — the schedule's units against the
    openings drawn in the walls. Proposal: as drawn. Asked only where walls were read and the counts differ."""
    from .universal_rules import fold_room_label
    qid = f"lentele_{kind}"
    if _decided(project, qid):
        return None
    rec = project.get("_duru_ziniarastis" if kind == "durys" else "_langu_ziniarastis")
    table = (rec or {}).get("lentele") if isinstance(rec, dict) else None
    rows = [r for r in ((table or {}).get("eilutes") or []) if isinstance(r, dict)]
    if not rows:
        return None
    per = _drawn_openings(rooms)
    if not per:
        return None
    title_text = fold_room_label(str((table or {}).get("pavadinimas") or ""))
    field = "langai" if kind == "langai" else ("durys_vidaus" if ("vidin" in title_text or "vidaus" in title_text) else "durys")
    listed = sum(int(r.get("kiekis") or 1) for r in rows)
    drawn = sum(int(d[field]) for d in per.values())
    if drawn == listed:
        return None
    word = _doors_word if kind == "durys" else _windows_word
    what = "durų" if kind == "durys" else "langų"
    by_nr = {_nr(r): r for r in rooms}
    items = []
    for nr in sorted(per, key=lambda n: (len(n), n)):
        n = int(per[nr][field])
        items.append({"room_nr": nr, "room_name": str(by_nr[nr].get("pavadinimas") or "").strip(), "field": DECISIONS_KEY,
                      "unit": "vnt.", "page": per[nr].get("page"), "drawn": n,
                      "sentence": (f"Sienose nubraižyta: {n} {word(n)}." if n else f"Sienose {what} nenubraižyta.")})
    listed_text = ", ".join(" ".join(x for x in (str(r.get("kodas") or ""), f"×{int(r.get('kiekis') or 1)}") if x)
                            for r in rows)
    page = table.get("page")
    head = "Durų žiniaraštyje" if kind == "durys" else "Langų žiniaraštyje"
    why = (f"{head} ({page} lapas) surašyta: {listed_text}. Sienose suskaičiuotos nubraižytos "
           + ("durų angos (durys tarp dviejų patalpų — vieną kartą)" if kind == "durys" else "langų angos")
           + ". Siūlau laikyti teisingu tai, kas nubraižyta. Jūsų atsakymas įsimenamas; sąmatos kiekiai nuo jo "
           "nesikeičia — jie skaičiuojami pagal kiekvienos patalpos " + ("durų" if kind == "durys" else "langų")
           + " sąrašą.")
    walls_missing = sum(1 for r in rooms if _nr(r) not in per)
    if walls_missing:
        why += (f" Sienos perskaitytos {len(per)} iš {len(rooms)} patalpų — kitose {what} nesuskaičiuota.")
    if field == "durys_vidaus":
        why += " Žiniaraštis — vidaus durų, todėl lauko durys neskaičiuotos."
    choices = [{"value": "brezinys", "label": f"Kaip nubraižyta sienose — {drawn}"},
               {"value": "ziniarastis", "label": f"Kaip žiniaraštyje — {listed}"}]
    title = f"{head} — {listed} {word(listed)}, sienose rasta {drawn}. Kurie teisingi?" if kind == "langai" else \
        f"{head} — {listed} {word(listed)}, sienose rasta {drawn}. Kurios teisingos?"
    return _q(qid, "reconcile", title, why, items, unit="vnt.", proposed="brezinys",
              proposed_label=choices[0]["label"], choices=choices, field=DECISIONS_KEY, listed=listed, drawn=drawn,
              lentele={"page": page, "rect_pct": table.get("bbox_pct"), "sentence": str(rec.get("sakinys") or "")})


def _ask_lentele_zymos(project: dict) -> dict | None:
    """„Žiniaraštyje D-1 — 3, plane parašyta 2" (Pathon v3 W5-D, D10): each schedule code's count against the times
    the plan writes that code (extractor/schedule_tags.py, `zymos_plane` on the schedule record). Asked only when a
    code differs. Answer `reconcile` — his record (`_lenteliu_sprendimai`); the estimate is not changed by it."""
    qid = "lentele_zymos"
    if _decided(project, qid):
        return None
    items, listed_total, drawn_total, first = [], 0, 0, None
    for key, head in (("_duru_ziniarastis", "Durų"), ("_langu_ziniarastis", "Langų")):
        rec = project.get(key) if isinstance(project.get(key), dict) else {}
        tags = rec.get("zymos_plane") if isinstance(rec.get("zymos_plane"), dict) else None
        table = rec.get("lentele") if isinstance(rec.get("lentele"), dict) else None
        if not tags or not table:
            continue
        for row in table.get("eilutes") or []:
            code = str((row or {}).get("kodas") or "").strip()
            hit = tags.get(code) if code else None
            if not isinstance(hit, dict):
                continue
            listed, drawn = int(row.get("kiekis") or 1), int(hit.get("kiekis") or 0)
            if listed == drawn:
                continue
            listed_total += listed
            drawn_total += drawn
            first = first or table
            pages = ", ".join(str(p) for p in hit.get("puslapiai") or [])
            items.append({"room_nr": code, "room_name": f"{head} žiniaraštis", "field": DECISIONS_KEY, "unit": "vnt.",
                          "page": (hit.get("puslapiai") or [table.get("page")])[0], "drawn": drawn, "listed": listed,
                          "sentence": (f"Žiniaraštyje — {listed} vnt., plane žymė „{code}“ parašyta {drawn} k."
                                       + (f" ({pages} lapas)." if pages else "."))})
    if not items:
        return None
    why = ("Kiekvienos žiniaraščio eilutės žymė (pvz. „D-1“) suskaičiuota ten, kur plane parašyta šalia angos — "
           "ne pačiame žiniaraštyje, ne legendoje ir ne antspaude. Kur skaičiai skiriasi, verta pažiūrėti: gal žymė "
           "plane praleista, gal žiniaraštis pasenęs. Jūsų atsakymas įsimenamas; sąmatos kiekiai nuo jo nesikeičia.")
    choices = [{"value": "brezinys", "label": f"Kaip parašyta plane — {drawn_total}"},
               {"value": "ziniarastis", "label": f"Kaip žiniaraštyje — {listed_total}"}]
    title = f"Žiniaraščio žymės plane: {len(items)} {'eilutė nesutampa' if len(items) == 1 else 'eilutės nesutampa'}"
    return _q(qid, "reconcile", title, why, items, unit="vnt.", proposed="ziniarastis", proposed_label=choices[1]["label"],
              choices=choices, field=DECISIONS_KEY, listed=listed_total, drawn=drawn_total,
              lentele={"page": first.get("page"), "rect_pct": first.get("bbox_pct"), "sentence": ""})


def _ask_lentele_apdaila(project: dict, rooms: list[dict]) -> dict | None:
    """„Apdailos lentelė: patalpa 04 grindys — plytelės, plane — laminatas" — the finish schedule against the
    floor plan's reading, room by room. Proposal: the plan. Rooms whose floor he chose himself ask nothing."""
    from .schedules import finish_row_for
    items = []
    for r in rooms:
        row = finish_row_for(project, r)
        table = str((row or {}).get("grindu_danga") or "")
        plan = str(r.get("grindu_danga") or "").strip().lower()
        if not row or table not in _FLOOR_LT or str(r.get("grindu_danga_saltinis") or "").lower() != "grindu_planas":
            continue
        if plan not in _FLOOR_LT or plan == table:
            continue
        choices = [{"value": plan, "label": f"{_FLOOR_LT[plan]} — kaip grindų plane"},
                   {"value": table, "label": f"{_FLOOR_LT[table]} — kaip apdailos lentelėje"}]
        items.append({"room_nr": _nr(r), "room_name": str(r.get("pavadinimas") or "").strip(), "field": "grindu_danga",
                      "unit": None, "page": row.get("page"), "rect_pct": row.get("bbox_pct"),
                      "sentence": (f"Apdailos lentelėje ({row.get('page')} lapas) grindys — „{row.get('grindys')}“, "
                                   f"grindų plane — {_FLOOR_LT[plan]}."),
                      "proposed": plan, "proposed_label": choices[0]["label"], "choices": choices})
    if not items:
        return None
    n = len(items)
    first = items[0]
    title = (f"Apdailos lentelė: patalpos {first['room_nr']} grindys — {_FLOOR_LT[first['choices'][1]['value']]}, "
             f"plane — {_FLOOR_LT[first['proposed']]}. Kuri danga teisinga?" if n == 1 else
             f"Apdailos lentelė ir grindų planas nurodo skirtingas grindis {n} patalpose. Kurios teisingos?")
    return _q("lentele_apdaila", "choices", title,
              "Siūlau taip, kaip nubraižyta grindų plane. Jei teisinga apdailos lentelė — pasirinkite jos dangą: ją "
              "įrašysiu patalpai ir perskaičiuosiu grindų kiekius.", items)


def _ask_lentele_suma(project: dict) -> dict | None:
    """„Eksplikacijos suma 143,27 m², patalpų plotų suma 141,80 m²" — information only: the room table's own
    sum (as the „lentelės" stage read it) against the project's rooms."""
    if _decided(project, "lentele_suma"):
        return None
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    eks = ((meta.get("lenteles") or {}).get("ziniarasciai") or {}).get("eksplikacija") or {}
    totals = [t for t in (eks.get("totals") or []) if isinstance(t, dict) and _f(t.get("value"))]
    rooms = [r for r in (project.get("patalpos") or []) if isinstance(r, dict) and _nr(r) and not r.get("_sujungta_i")]
    ours = round(sum(_f(r.get("plotas_m2")) or 0.0 for r in rooms), 2)
    if not totals or not ours:
        return None
    table_rows = round(sum(_f(r.get("plotas_m2")) or 0.0 for r in eks.get("rows") or []), 2)
    pick = min(totals, key=lambda t: abs(float(t["value"]) - (table_rows or ours)))
    total = round(float(pick["value"]), 2)
    diff = round(total - ours, 2)
    if abs(diff) <= max(SUM_TOL_M2, SUM_TOL_SHARE * total):
        return None
    label = str(pick.get("label") or "Iš viso").strip()
    page = pick.get("page") or eks.get("page")
    why = (f"Patalpų eksplikacijoje ({page} lapas) parašyta „{label}“ — {lt_num(total)} m², o projekto patalpų plotų "
           f"suma — {lt_num(ours)} m² (skirtumas {lt_num(abs(diff))} m²).")
    if table_rows and abs(table_rows - total) > SUM_TOL_M2:
        why += f" Pačios lentelės eilučių suma — {lt_num(table_rows)} m²."
    why += (" Tai tik informacija: patikrinkite, ar įtrauktos visos patalpos ir ar plotai perrašyti teisingai. "
            "„Supratau“ pažymi, kad matėte — kiekiai nuo to nesikeičia.")
    item = {"room_nr": "", "room_name": label, "field": None, "unit": "m²", "page": page,
            "rect_pct": pick.get("bbox_pct"), "sentence": why, "lentele": total, "musu": ours}
    return _q("lentele_suma", "info", "Eksplikacijos suma ir patalpų plotų suma skiriasi", why, [item], unit="m²",
              field=DECISIONS_KEY, lentele={"page": page, "rect_pct": pick.get("bbox_pct"), "sentence": why})


def _floor_from_table(project: dict, question: dict | None, by_nr: dict[str, dict]) -> None:
    """A room the floor plan says nothing about, whose floor the finish schedule names: the floor question
    proposes the schedule's covering and says where it is written (instead of the room's purpose)."""
    from .schedules import finish_row_for
    if not question:
        return
    for item in question.get("items") or []:
        room = by_nr.get(str(item.get("room_nr") or ""))
        row = finish_row_for(project, room) if room else None
        if not row or row.get("grindu_danga") not in _FLOOR_LT:
            continue
        item["proposed"] = row["grindu_danga"]
        item["proposed_label"] = _FLOOR_LT[row["grindu_danga"]]
        item["sentence"] = (f"Apdailos lentelėje ({row.get('page')} lapas) šiai patalpai parašyta: „{row.get('grindys')}“ — "
                            "siūlau tai.")
        item["lentele"] = {"page": row.get("page"), "rect_pct": row.get("bbox_pct")}


# ── the whole project ────────────────────────────────────────────────────────────────────────────────

def build_questions(project: dict, *, lenteles: bool = False) -> dict:
    """{questions: [...], asked, read, rooms} — see the module docstring. Rooms left out of the estimate
    („Neskaičiuoju") ask nothing. `lenteles`: also the drawing's schedules against what was read elsewhere
    (RECONCILE_KINDS) and the floor question proposing the finish schedule's covering — off until the check
    sheet can answer the new kinds (the route's `?lenteles=1`)."""
    apimtis = normalize_apimtis(project.get("_apimtis"))
    rooms = [r for r in (project.get("patalpos") or [])
             if isinstance(r, dict) and _nr(r) and not is_room_excluded(apimtis, _nr(r))]
    everyone: list[tuple[dict, dict]] = []
    for r in rooms:
        payload = build_room_facts(project, _nr(r))
        for fact in (payload or {}).get("facts") or []:
            everyone.append((r, fact))
    waiting = [(r, f) for r, f in everyone if f.get("status") != "read"]
    by_nr = {_nr(r): r for r in rooms}

    questions: list[dict] = []
    for q in (
        _ask_aukstis(waiting, everyone),
        # an outline is asked for only while the room's perimeter still waits for him: a number he typed
        # himself (or the table states) is an answer — asking him to point at the room as well would be a
        # question about OUR evidence, not about his estimate
        _ask_konturas(waiting),
        *_ask_erdves(waiting, by_nr),
        _ask_numbers("perimetras", waiting, "Patalpos {room} sienų ilgiai plane neužrašyti",
                     "{n} patalpų sienų ilgiai plane neužrašyti",
                     "Paėmiau juos iš sienų kontūro brėžinyje arba iš ploto. Jei žinote tiksliau — įrašykite: pagal jūsų "
                     "skaičių perskaičiuosiu dažomą sienų plotą ir grindjuostes."),
        _ask_numbers("plotas", waiting, "Patalpos {room} ploto plane neradau", "{n} patalpų ploto plane neradau",
                     "Skaičiuoju su plotu, kurį pavyko nustatyti iš plano vaizdo. Jei reikia, įrašykite tikrą: pagal jį "
                     "perskaičiuosiu grindis ir lubas."),
        _ask_angos(waiting),
        _ask_durys(project, rooms),
        _ask_grindys(waiting),
        _ask_apdaila(waiting),
    ):
        if q:
            questions.append(q)
    if lenteles:
        try:
            _floor_from_table(project, next((q for q in questions if q["kind"] == "grindys"), None), by_nr)
            for q in (_ask_lentele_angos(project, rooms, "durys"), _ask_lentele_angos(project, rooms, "langai"),
                      _ask_lentele_zymos(project), _ask_lentele_apdaila(project, rooms), _ask_lentele_suma(project)):
                if q:
                    questions.append(q)
        except Exception as exc:  # noqa: BLE001 — a malformed schedule record asks nothing, never breaks the list
            _log.warning("schedule questions skipped: %r", exc)
    questions.sort(key=lambda q: ORDER.index(q["kind"]))
    return {"questions": questions, "asked": len(waiting), "read": len(everyone) - len(waiting), "rooms": len(rooms)}

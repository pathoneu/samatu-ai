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

from collections import Counter
from typing import Any

from .room_facts import _FLOOR_LT, _f, build_room_facts, lt_num
from .scope import is_room_excluded, normalize_apimtis

ORDER = ("aukstis", "konturas", "erdve", "perimetras", "plotas", "angos", "durys", "grindys", "apdaila")

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
               f"{others} imu tiek pat.")
    else:
        why = f"Lubų aukščio brėžinyje neradau — skaičiuoju su {lt_num(proposed)} m."
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


def _ask_angos(rows: list[tuple[dict, dict]]) -> dict | None:
    asked = [(r, f) for r, f in rows if f["key"] == "angos"]
    if not asked:
        return None
    items, manual = [], []
    for r, f in asked:
        suggestions = [s for s in (f.get("suggestions") or []) if isinstance(s, dict)]
        for s in suggestions:
            items.append(_item(r, f, proposed=True, tipas=s.get("tipas"), plotis_mm=s.get("plotis_mm"),
                               aukstis_mm=s.get("aukstis_mm"), i=s.get("i"), plotis_m=s.get("plotis_m"),
                               label=s.get("label"), line_pct=s.get("line_pct"),
                               page=((f.get("openings") or {}).get("page") or (f.get("source") or {}).get("page"))))
        if not suggestions:
            manual.append({"room_nr": _nr(r), "room_name": str(r.get("pavadinimas") or "").strip(),
                           "sentence": f.get("sentence") or ""})
    n = len(items)
    if n:
        anga = "angą, kurios" if n % 10 == 1 and n % 100 != 11 else "angas, kurių" if n % 10 in range(2, 10) and n % 100 not in range(12, 20) else "angų, kurių"
        title = f"Sienose matau {n} {anga} nėra durų ir langų sąraše"
        why = ("Plotį paėmiau iš sienų brėžinio, aukštį — standartinį (durys 2,10 m, langas 1,50 m). "
               "Plotį, aukštį ir rūšį galite pataisyti čia pat; nuimkite varnelę, jei tai ne durys ir ne langas.")
    else:
        m = len(manual)
        title = f"Durys ir langai: patikrinkite {m} {_rooms_word(m)}"
        why = "Šiose patalpose durų ir langų sąrašo vienu paspaudimu papildyti negaliu — pažiūrėkite patalpos lape."
    q = _q("angos", "openings", title, why, items, unit="vnt.")
    q["manual"] = manual
    return q


def _ask_durys(project: dict, rooms: list[dict]) -> dict | None:
    """ONE question for the whole project (2026-09-23): are the interior doors frameless (beapvadinės) or
    with casings? A frameless door draws exactly like a framed one, so the plan's symbols cannot settle it —
    only the drawing's TEXT (a door schedule, a note, the openings annotated for frameless doors, the door
    products on a finish board) or the person can. Asked while the frame type rests on the symbols alone or
    on nothing (universal_rules.settle_frameless_default: `brezinys`, `nera_pozymiu`), or on evidence that
    names only some doors (`anotacija`, `gaminiai`); the proposal is what the estimate computes with now.
    The answer lands as `_overrides.vidaus_durys_beapvadines`."""
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
    item = {"room_nr": "", "room_name": "Visos vidaus durys", "field": "vidaus_durys_beapvadines", "unit": None,
            "sentence": str(settled.get("sakinys") or ""), "page": None, "proposed": proposed,
            "proposed_label": _DOORS_CHOICES[0]["label"] if proposed else _DOORS_CHOICES[1]["label"],
            "choices": _DOORS_CHOICES, "count": n}
    why = ("Beapvadinės durys plane piešiamos taip pat kaip su apvadais, todėl iš simbolio to nustatyti negalima. "
           "Nuo atsakymo priklauso eilutė „Durų angų paruošimas beapvadinėms durims“: su apvadais ji nereikalinga. "
           "Lauko durys čia neįskaitomos.")
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
              "Brėžinys šių patalpų dangos vienareikšmiškai nepasako — parinkau pagal patalpos paskirtį." if n > 1 else
              "Brėžinys šios patalpos dangos vienareikšmiškai nepasako — parinkau pagal patalpos paskirtį.", items)


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
              "Sienų apdailos brėžinyje neradau — parinkau pagal patalpos paskirtį. Plytelių plotus taisykite patalpos lape.",
              items)


# ── the whole project ────────────────────────────────────────────────────────────────────────────────

def build_questions(project: dict) -> dict:
    """{questions: [...], asked, read, rooms} — see the module docstring. Rooms left out of the estimate
    („Neskaičiuoju") ask nothing."""
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
                     "Paėmiau juos iš sienų kontūro brėžinyje arba iš ploto. Jei žinote tiksliau — įrašykite."),
        _ask_numbers("plotas", waiting, "Patalpos {room} ploto plane neradau", "{n} patalpų ploto plane neradau",
                     "Skaičiuoju su plotu, kurį pavyko nustatyti iš plano vaizdo. Patikrinkite ir, jei reikia, įrašykite tikrą."),
        _ask_angos(waiting),
        _ask_durys(project, rooms),
        _ask_grindys(waiting),
        _ask_apdaila(waiting),
    ):
        if q:
            questions.append(q)
    questions.sort(key=lambda q: ORDER.index(q["kind"]))
    return {"questions": questions, "asked": len(waiting), "read": len(everyone) - len(waiting), "rooms": len(rooms)}

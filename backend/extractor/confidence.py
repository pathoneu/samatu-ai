"""Per-pozicija confidence post-pass (2026-06-11 experiments follow-up).

Measured problem: FALSE-GREEN RATE was 50% (Objektas A) / 60% (Rangovas B) — over
half of the quantities the UI presented as trustworthy were >10% wrong, and
voting-disagreement flags caught only ~40% of errors because SYSTEMATIC errors
agree across runs. Confidence therefore cannot come from run-agreement alone.

Three stacked signals, worst wins (žalia < geltona < raudona):
 1. CLASS CALIBRATION — quantity classes with measured systematic bias on the
    two contractor-anchored projects default to geltona, with the measured bias
    in the reason. (Calibration data: docs/superpowers/research/
    2026-06-11-experiments-results.md; anchors = Objektas A + Rangovas B.)
 2. FINISH PROVENANCE — finish-derived lines (glaistymas/dažymas, plytelės,
    Rotband, molio) demote to geltona when the apdailos reader self-reported
    guessing (`_apdailos_confidence == "low"`) on any contributing room.
 3. VOTING FLAGS — geometry-derived lines demote when the N-pass voter recorded
    run-disagreement on contributing rooms (100% precision when firing on the
    anchor projects); kampai goes raudona when the adjacency pass produced no
    partition walls at all.

Lines not matched by any rule stay žalia — the class table is the contract:
when an anchor project shows a class >10% off, it gets a row here. One
exception does not need a measurement (2026-10-03): a line whose `saltinis`
says the count is the ROOM TYPE's (`ROOM_DEFAULT_SOURCES`) is never green —
nothing was read, so there is nothing to be confident about.
"""
from __future__ import annotations

ZALIA, GELTONA, RAUDONA = "zalia", "geltona", "raudona"
_SEVERITY = {ZALIA: 0, GELTONA: 1, RAUDONA: 2}

# What „Dažymo kampų montavimas" really adds up — one sentence, shared by the
# row reason here and every other place the formula is told (2026-10-03).
KAMPAI_REASON = (
    "Kampų ilgis sudėtas iš patalpos perimetro (sienų ir lubų sandūra), vidinių "
    "kampų (kampų skaičius × aukštis), angų kraštų (standartinio dydžio durys ir "
    "langai, ne brėžinio matmenys) ir pertvarų sandūrų (× aukštis). Suskaičiuokite "
    "dažomus kampus plane ir palyginkite.")

# Row sources that mean „the count is the room type's, nothing was counted on
# the drawing" (vision_call `saltinis`). Such a row is never green, whatever
# the class table says: CLAUDE.md §7 — a value estimated from room-type
# defaults is the fallback tier. (audit 2026-09-29 vision-pipeline-7: the
# sanitary rows were room-type counts shown green.)
ROOM_DEFAULT_SOURCES = frozenset({"paskirtis_default", "room_type_assumption"})
ROOM_DEFAULT_REASON = (
    "Kiekis priskirtas pagal patalpų paskirtį — brėžinyje nesuskaičiuotas. "
    "Patikrinkite pagal santechnikos planą.")

# (substring of aprasymas, confidence, measured reason) — 2-anchor calibration
CLASS_RULES: list[tuple[str, str, str]] = [
    # USER-FACING STRINGS (rewritten 2026-08-31). The founder caught the old
    # ones on screen: they quoted benchmark error pairs ("−61%/−64% vs rangovo
    # samatas (2 projektai)"), named a CLIENT project (Objektas A) and spoke in
    # internal jargon ("Simbolių recall"). That is methodology confession, not
    # guidance — it tells a contractor "this number is tuned on someone else's
    # job and we don't trust it", and leaks another customer's project name
    # into every future user's screen. The calibration facts now live HERE as
    # comments; the string the user sees says what the number is based on and
    # what to check. Never put client names, benchmark counts, error
    # percentages or pipeline jargon in the third tuple element — the
    # vocabulary guard test enforces this.
    #
    # (calibration: hidden doors under-read −61%/−64% on both anchor projects)
    ("beapvadinėms durims", GELTONA,
     "Paslėptos (beapvadinės) durys brėžinyje sunkiai įžiūrimos — dalis jų "
     "dažnai lieka nesuskaičiuota. Palyginkite su durų specifikacija."),
    # (calibration: −39%/−68% under-read)
    ("silikonavimas", GELTONA,
     "Silikonavimo ilgis dažnai būna didesnis, nei matyti plane — patikrinkite "
     "pagal sanitarinės įrangos ir plytelių sandūras."),
    # (calibration: symbol recall −11%/−21%)
    ("skylių gręžimas plytelėse", GELTONA,
     "Skylių skaičius priklauso nuo santechnikos taškų — suskaičiuokite pagal "
     "įrangos išdėstymą plane."),
    # (calibration: unstable +15%/−63%)
    ("45° pjovimas", GELTONA,
     "Pjovimo ilgis priklauso nuo vidinių kampų išdėstymo plytelių zonose — "
     "patikrinkite pagal išklotines."),
    # (calibration: symbol counts −20%/+33%)
    # 2026-10-03: the number is a per-shower default (`lentyneliu_per_vonia`)
    # times the showers — no shelf is read off the drawing, so the old „iš
    # simbolių" wording claimed a reading that never happened.
    ("lentynėlių", GELTONA,
     "Lentynėlių skaičius priimtas po kelias kiekvienam dušui — patikrinkite "
     "sienų išklotinėse."),
    # (calibration: ±40%)
    ("praustuvės", GELTONA,
     "Skaičius nustatytas iš simbolių plane — patikrinkite pagal santechnikos "
     "planą."),
    # (calibration: 0%/−40%)
    ("klozeto montavimas", GELTONA,
     "Skaičius nustatytas iš simbolių plane — patikrinkite pagal santechnikos "
     "planą."),
    # 2026-07-29: bidė is read for the first time. LT brėžiniuose the word
    # „bidė" is usually absent — the reader identifies it by POSITION (next to
    # the klozetas) and altitude (~1000-1100 mm), so the count is a genuine
    # inference, not a label read. Never green.
    ("bidė dušiuko", GELTONA,
     "Bidė dušiukas atpažįstamas iš vietos prie klozeto ir altitudės — brėžinyje "
     "žodis „bidė“ dažniausiai neparašytas; kiekį patikrinkite"),
    # The bathtub mixer rides on the reader's tub-only count because the symbol
    # summary lumps vonias with dušo padėklais; a mis-called tray bills the
    # wrong fixture, so the line asks to be verified.
    ("vonios maišytuvo", GELTONA,
     "Vonia ir dušo padėklas brėžinyje atrodo panašiai — patikrinkite, ar patalpoje "
     "tikrai yra vonia, ne dušas"),
    # (calibration: formula fitted to ONE contractor samata incl. the disputed
    #  half-corner + perimeter term; unvalidated beyond it — keep that fact
    #  here, not on the contractor's screen)
    # 2026-10-03 (audit calc-engine-5): the sentence used to say „išoriniai
    # kampai × aukštis" — the math (universal_rules.calc_room_quantities) is
    # the ceiling perimeter + the room's own corners × H (when counted) + every
    # opening's edges at a FIXED door/window size + partition junctions × H.
    # The words now name those four terms; the math is unchanged.
    ("kampų montavimas", GELTONA, KAMPAI_REASON),
    ("rotband", GELTONA,
     "Apskaičiuota kaip dalis sienų ploto (30%) — faktinis kiekis priklauso "
     "nuo sienų būklės."),
    # (calibration: −15%/+1% between projects)
    ("angokraščių", GELTONA,
     "Angokraščių ilgis priklauso nuo angų matmenų — palyginkite su durų ir "
     "langų sąrašu."),
    # Floor-covering ASSIGNMENT (kuri patalpa plytelės vs parketas vs guma) is
    # paskirtis-heuristic-driven and missed garažas/tambūras floors on both
    # anchor projects (−20%…−100% per-room; parketas +29%).
    ("grindų plytel", GELTONA,
     "Dangos tipas patalpai parinktas pagal jos paskirtį — patikrinkite, "
     "kuriose patalpose numatytos plytelės."),
]

# OVER-BILLING / app-added scope (reconciliation 2026-06-17 vs Rangovas A samata):
# lines the app adds that may have NO contractor counterpart — a TRUST risk worse
# than under-reads (the contractor disputes the sąmata). These ALWAYS apply, even
# over an upstream reason, because "is this line even in scope?" outranks any
# extraction-confidence note. Never present app-added scope as a confident green.
_OVERBILLING_RULES: list[tuple[str, str, str]] = [
    # Grindų danga: the contractor includes it on SOME projects, not all (founder
    # 2026-06-17). Keep the line — flag it geltona to verify per-project, not red.
    ("parketo / laminato", GELTONA,
     "Grindų danga įtraukiama ne visada — patikrinkite, ar šiame projekte ji yra rangovo apimtyje"),
    ("laminato klojimas", GELTONA,
     "Grindų danga įtraukiama ne visada — patikrinkite pagal šio projekto apimtį"),
    ("grindų dangos pamušalas", GELTONA, "Grindų dangos dalis — patikrinkite, ar įeina į šio projekto apimtį"),
    ("grindų išlyginamasis", GELTONA, "Grindų dangos dalis — patikrinkite, ar įeina į šio projekto apimtį"),
    # Lubų karnizas: used to mount curtains — not always present (founder doubts it).
    ("lubų karnizo", GELTONA, "Lubų karnizas (užuolaidoms) įrengiamas ne visada — patikrinkite pagal projektą"),
    ("apsauginės dangos", GELTONA, "Automatinė prielaida (grindų apsauga statybų metu)"),
    # NOTE: grindjuostės is NOT here — the app correctly computes full perimeter
    # minus door gaps minus wet/tile/concrete rooms (= the contractor's convention).
]

# Finish-derived lines: demote when apdailos self-reported guessing.
_FINISH_PATTERNS = ("glaistymas", "dažymas", "molio tinku", "rotband",
                    "plytelių", "plytelės", "fugavimas", "šlifavimas")

# Geometry-derived lines: demote on voting disagreement flags.
_GEOMETRY_PATTERNS = ("glaistymas/dažymas", "kampų montavimas", "grindjuosčių",
                      "karnizo", "lyginimas")


def _worse(a: str | None, b: str) -> str:
    a = a or ZALIA
    return a if _SEVERITY.get(a, 0) >= _SEVERITY[b] else b


def _normalize_existing(p: dict) -> str | None:
    """Map legacy per-line confidence strings to the LT scheme."""
    c = (p.get("confidence") or "").lower()
    return {"high": ZALIA, "zalia": ZALIA, "medium": GELTONA, "geltona": GELTONA,
            "low": RAUDONA, "raudona": RAUDONA}.get(c)


_OPENING_TIPAI = ("duris", "pasleptos_duris", "langas", "stoglangis")


def _rooms_with_unread_opening_dims(rooms: list[dict]) -> list[str]:
    """Rooms where an opening (door/window) has no readable W/H. calc_room_quantities
    SILENTLY skips these in the angokraščiai (reveal) calc — surface the gap so the
    reveal length is disclosed as possibly incomplete rather than dropped invisibly.
    Returns the room labels (nr or name), de-duplicated, in order."""
    out: list[str] = []
    for r in rooms:
        for el in (r.get("elementai") or []):
            if (el.get("tipas") or "").lower() in _OPENING_TIPAI:
                w = float(el.get("plotis_mm") or 0)
                h = float(el.get("aukstis_mm") or 0)
                if not (w > 0 and h > 0):
                    label = str(r.get("nr") or r.get("pavadinimas") or "?")
                    if label not in out:
                        out.append(label)
                    break
    return out


def apply_confidence(parsed: dict) -> dict:
    """Stamp confidence + a reason on every pozicija. Worst signal wins.

    CONTRACT: call ONCE on freshly-built pozicijos. The additive signals
    (apdailos / voting / unread-dims) append to ``_confidence_reason`` and are
    NOT idempotent if run again on already-stamped pozicijos. In production this
    is safe: ``_build_pozicijos_from_rooms`` rebuilds ``pozicijos = []`` from
    scratch on every call (including the assumptions-panel recompute at
    main.py:4840), so each pozicija reaches this pass clean. Do not call this on
    a parsed dict whose pozicijos already carry a computed ``_confidence_reason``.
    """
    rooms = parsed.get("patalpos") or []
    apdailos_low = any(r.get("_apdailos_confidence") == "low" for r in rooms)
    voting_flags = ((parsed.get("_voting") or {}).get("low_confidence_fields") or [])
    npw_total = sum(int(r.get("n_partition_walls") or 0) for r in rooms)
    unread_dim_rooms = _rooms_with_unread_opening_dims(rooms)

    for p in parsed.get("pozicijos") or []:
        label = (p.get("aprasymas") or "").lower()
        conf = _normalize_existing(p) or ZALIA
        reasons: list[str] = []

        # An upstream-specific reason (e.g. the door-type reconciliation:
        # "rasta 7 beapvadinių durų, pradinis rado 2 — patikrink") is more current
        # and precise than a static class-bias note. Preserve it and skip the
        # class rule for this line — the reconciliation already addressed the bias.
        upstream_reason = p.get("_confidence_reason")
        # A room-type count („1 per bathroom") is not a reading: never green,
        # and the class note — which for the fixture lines says the number came
        # from symbols — would describe a reading that did not happen, so the
        # room-type sentence stands in for it (2026-10-03).
        room_default = str(p.get("saltinis") or "").lower() in ROOM_DEFAULT_SOURCES
        if room_default:
            conf = _worse(conf, GELTONA)
        if upstream_reason:
            reasons.append(upstream_reason)
        elif room_default:
            reasons.append(ROOM_DEFAULT_REASON)
        else:
            for needle, klass_conf, reason in CLASS_RULES:
                if needle in label:
                    conf = _worse(conf, klass_conf)
                    reasons.append(reason)
                    break

        if apdailos_low and any(s in label for s in _FINISH_PATTERNS):
            conf = _worse(conf, GELTONA)
            reasons.append("Apdailos planas neaiškiai įskaitomas — dalies patalpų apdaila nustatyta su prielaidomis; patikrinkite apdailų lentelę")

        if voting_flags and any(s in label for s in _GEOMETRY_PATTERNS):
            conf = _worse(conf, GELTONA)
            reasons.append(f"AI skaitymai nesutarė dėl {len(voting_flags)} patalpų matmenų — patikrinkite tų patalpų plotus ir perimetrus")

        if "kampų montavimas" in label and npw_total == 0:
            conf = _worse(conf, RAUDONA)
            reasons.append("Pertvarų išdėstymo atpažinti nepavyko — kampų suma greičiausiai PER MAŽA. Suskaičiuokite dažomus kampus plane rankiniu būdu")

        # Per-project recall gap: an opening whose dims Vision didn't read is
        # silently skipped in the reveal calc. Surface it on the angokraščiai line.
        if unread_dim_rooms and "angokrašči" in label:
            conf = _worse(conf, GELTONA)
            reasons.append(
                f"{len(unread_dim_rooms)} angos be nuskaitytų matmenų "
                f"(patalpos: {', '.join(unread_dim_rooms)}) — angokraščiai gali būti nepilni")

        # OVER-BILLING flag — ALWAYS applies, even over an upstream reason.
        # App-added scope (flooring, karnizas, full-perimeter grindjuostės) is a
        # trust risk that must never read green; surface "verify against contract".
        for needle, ob_conf, ob_reason in _OVERBILLING_RULES:
            if needle in label:
                conf = _worse(conf, ob_conf)
                if ob_reason not in reasons:
                    reasons.append(ob_reason)
                break

        p["confidence"] = conf
        if reasons:
            p["_confidence_reason"] = "; ".join(reasons)
    return parsed

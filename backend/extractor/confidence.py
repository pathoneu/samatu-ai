"""Per-pozicija confidence post-pass (2026-06-11 experiments follow-up).

Measured problem: FALSE-GREEN RATE was 50% (Beržų) / 60% (Bacevičiaus) — over
half of the quantities the UI presented as trustworthy were >10% wrong, and
voting-disagreement flags caught only ~40% of errors because SYSTEMATIC errors
agree across runs. Confidence therefore cannot come from run-agreement alone.

Three stacked signals, worst wins (žalia < geltona < raudona):
 1. CLASS CALIBRATION — quantity classes with measured systematic bias on the
    two contractor-anchored projects default to geltona, with the measured bias
    in the reason. (Calibration data: docs/superpowers/research/
    2026-06-11-experiments-results.md; anchors = Beržų + Bacevičiaus.)
 2. FINISH PROVENANCE — finish-derived lines (glaistymas/dažymas, plytelės,
    Rotband, molio) demote to geltona when the apdailos reader self-reported
    guessing (`_apdailos_confidence == "low"`) on any contributing room.
 3. VOTING FLAGS — geometry-derived lines demote when the N-pass voter recorded
    run-disagreement on contributing rooms (100% precision when firing on the
    anchor projects); kampai goes raudona when the adjacency pass produced no
    partition walls at all.

Lines not matched by any rule stay žalia — the class table is the contract:
when an anchor project shows a class >10% off, it gets a row here.
"""
from __future__ import annotations

ZALIA, GELTONA, RAUDONA = "zalia", "geltona", "raudona"
_SEVERITY = {ZALIA: 0, GELTONA: 1, RAUDONA: 2}

# (substring of aprasymas, confidence, measured reason) — 2-anchor calibration
CLASS_RULES: list[tuple[str, str, str]] = [
    ("beapvadinėms durims", GELTONA,
     "Vision nepastebi paslėptų durų: −61%/−64% vs rangovo samatas (2 projektai)"),
    ("silikonavimas", GELTONA, "Sisteminis trūkumas: −39%/−68% vs rangovą (2 projektai)"),
    ("skylių gręžimas plytelėse", GELTONA, "Simbolių recall: −11%/−21% (2 projektai)"),
    ("45° pjovimas", GELTONA, "Nestabili formulė: +15%/−63% (2 projektai)"),
    ("lentynėlių", GELTONA, "Skaičius iš simbolių: −20%/+33% (2 projektai)"),
    ("praustuvės", GELTONA, "Simbolių skaičiavimas: ±40% (2 projektai)"),
    ("klozeto montavimas", GELTONA, "Simbolių/bide skaičiavimas: 0%/−40% (2 projektai)"),
    ("kampų montavimas", GELTONA,
     "Formulė kalibruota pagal 1 rangovo samatą (Beržų) — apima ginčytiną "
     "pusinių kampų ir perimetro dedamąją; tikslumas nepatvirtintas (reikia daugiau etalonų)"),
    ("rotband", GELTONA, "Dalis nuo sienų ploto (0.30) — priklauso nuo apdailos tikslumo"),
    ("angokraščių", GELTONA, "Nestabilu tarp projektų: −15%/+1% (2 projektai)"),
    # Floor-covering ASSIGNMENT (kuri patalpa plytelės vs parketas vs guma) is
    # paskirtis-heuristic-driven and missed garažas/tambūras floors on both
    # anchor projects (−20%…−100% per-room; parketas +29%).
    ("grindų plytel", GELTONA, "Dangos priskyrimas pagal paskirtį: −20%/−100% kai kurioms patalpoms (2 projektai)"),
]

# OVER-BILLING / app-added scope (reconciliation 2026-06-17 vs Rangovas A samata):
# lines the app adds that may have NO contractor counterpart — a TRUST risk worse
# than under-reads (the contractor disputes the sąmata). These ALWAYS apply, even
# over an upstream reason, because "is this line even in scope?" outranks any
# extraction-confidence note. Never present app-added scope as a confident green.
_OVERBILLING_RULES: list[tuple[str, str, str]] = [
    ("parketo / laminato", RAUDONA,
     "Grindų danga pridėta automatiškai — patikrinkite, ar įeina į sutarties apimtį (rangovo samatoje jos gali nebūti)"),
    ("laminato klojimas", RAUDONA, "Grindų danga pridėta automatiškai — patikrinkite, ar įeina į sutartį"),
    ("grindų dangos pamušalas", RAUDONA, "Grindų danga pridėta automatiškai — patikrinkite pagal sutartį"),
    ("grindų išlyginamasis", RAUDONA, "Grindų išlyginimas pridėtas automatiškai — patikrinkite pagal sutartį"),
    ("lubų karnizo", GELTONA, "Lubų karnizas pridėtas automatiškai — patikrinkite pagal lubų planą (rangovo samatoje gali nebūti)"),
    ("grindjuosčių", GELTONA, "Skaičiuota pagal visą patalpų perimetrą; rangovas gali skaičiuoti tik plytelių juostą — patikrinkite"),
    ("apsauginės dangos", GELTONA, "Automatinė prielaida (grindų apsauga statybų metu)"),
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
        if upstream_reason:
            reasons.append(upstream_reason)
        else:
            for needle, klass_conf, reason in CLASS_RULES:
                if needle in label:
                    conf = _worse(conf, klass_conf)
                    reasons.append(reason)
                    break

        if apdailos_low and any(s in label for s in _FINISH_PATTERNS):
            conf = _worse(conf, GELTONA)
            reasons.append("Apdailos planas neaiškus — apdailos skaitytuvas pažymėjo 'low confidence' daliai patalpų")

        if voting_flags and any(s in label for s in _GEOMETRY_PATTERNS):
            conf = _worse(conf, GELTONA)
            reasons.append(f"Ekstrakcijos paleidimai nesutarė dėl {len(voting_flags)} patalpų geometrijos")

        if "kampų montavimas" in label and npw_total == 0:
            conf = _worse(conf, RAUDONA)
            reasons.append("Gretimybės analizė nerado pertvarų — kampų suma be pusinių kampų (žinomai per maža)")

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

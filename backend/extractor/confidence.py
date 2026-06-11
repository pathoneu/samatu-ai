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
    ("kampų montavimas", GELTONA, "Geometrinė suma: −18%/+17% (2 projektai)"),
    ("rotband", GELTONA, "Dalis nuo sienų ploto (0.30) — priklauso nuo apdailos tikslumo"),
    ("angokraščių", GELTONA, "Nestabilu tarp projektų: −15%/+1% (2 projektai)"),
    # Floor-covering ASSIGNMENT (kuri patalpa plytelės vs parketas vs guma) is
    # paskirtis-heuristic-driven and missed garažas/tambūras floors on both
    # anchor projects (−20%…−100% per-room; parketas +29%).
    ("grindų plytel", GELTONA, "Dangos priskyrimas pagal paskirtį: −20%/−100% kai kurioms patalpoms (2 projektai)"),
    ("laminato klojimas", GELTONA, "Dangos priskyrimas pagal paskirtį: +29% (anchor projektas)"),
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


def apply_confidence(parsed: dict) -> dict:
    rooms = parsed.get("patalpos") or []
    apdailos_low = any(r.get("_apdailos_confidence") == "low" for r in rooms)
    voting_flags = ((parsed.get("_voting") or {}).get("low_confidence_fields") or [])
    npw_total = sum(int(r.get("n_partition_walls") or 0) for r in rooms)

    for p in parsed.get("pozicijos") or []:
        label = (p.get("aprasymas") or "").lower()
        conf = _normalize_existing(p) or ZALIA
        reasons: list[str] = []

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

        p["confidence"] = conf
        if reasons:
            p["_confidence_reason"] = "; ".join(reasons)
    return parsed

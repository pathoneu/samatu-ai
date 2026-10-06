"""Statistical LED-niche fallback for rooms the Vision pipeline missed.

The niche_locator does best-effort extraction from ceiling plans;
when it returns nothing for a room type that typically HAS LED, we
fill in an estimate based on per-room-type ratios derived from
Objektas A's contractor-validated data:

    paskirtis      LED-per-perimeter
    -----------    -----------------
    koridorius      0.55
    skalbykla       0.41
    valgomasis      0.39  (open plan kitchen/dining/living)
    gyvenamoji      0.40
    san/vonia/wc    0.27  (bathrooms)
    miegamoji       0.17  (bedrooms)
    kabinetas       0.18  (office)
    tamburas        0.00  (no LED)
    garazas         0.00
    drabuzine       0.00  (closets)
    rubine          0.00  (storage)

The fallback only fires when:
  • the room currently has 0 nisa_LED elementai (Vision returned nothing)
  • the room's paskirtis ratio is > 0.15 (room types that empirically
    have LED — skip closets, storage, garages)

Estimates are marked _source='statistical_inference', _confidence='low'
so downstream consumers can distinguish them from extractor output.

Validated impact (benchmark eval, verified 2026-06-05):
  objektas_a       no change (all 0-LED rooms have ratio=0; LED -0.99%)
  objektas_b 26.61m → 44.97m (truth 54.98; -52% → -18.2%)
  objektas_c      14.50m → 18.95m (truth 16.84; -13.9% → +12.5% — over-bills)

The objektas_c case shows the risk: when a 0-LED room ACTUALLY has 0
LED (not just "Vision missed it"), this fallback over-bills. Here it
fires on exactly 2 'san' wet rooms (perim × 0.27 = +4.45m) the
contractor never billed, flipping -13.9% UNDER → +12.5% OVER. The
ratios cannot simply be lowered to fix it: the same san=0.27 HELPS
objektas_b (+6.26m), and dropping san/vonia/wc regresses
objektas_b to -29.6% (verified). The clean asymmetric fix is to
gate inference on per-room locator coverage (suppress only when the
locator demonstrably imaged the room's ceiling plan and found 0),
which needs a coverage map not yet persisted in the extract. Until
then, route over-bills through the contractor /calibrate UI.

2026-10-06 (founder decision): the ratios were fitted on one contractor's
sąmata, and the engine may not learn from a sąmata — so an estimate is no
longer BILLED unless he accepts it (`LED_ESTIMATE_OPT_IN` below). The
inference still runs and the estimate is still shown: as a blank row naming
the rooms and metres, and as a choice in Nustatymai.
"""
from __future__ import annotations

import re

from .universal_rules import normalize_paskirtis

# Empirical LED-per-perimeter-meter ratios computed from Objektas A's
# contractor-validated room data (the only project with both clean
# niche-locator output and verified per-room LED truth).
LED_RATIO_BY_PASKIRTIS: dict[str, float] = {
    "koridorius":  0.55,
    "skalbykla":   0.41,
    "valgomasis":  0.39,
    "gyvenamoji":  0.40,
    "san":         0.27,
    "vonia":       0.27,
    "wc":          0.27,
    "miegamoji":   0.17,
    "kabinetas":   0.18,
    # Room types with no LED in Objektas A (and unlikely elsewhere)
    "tamburas":    0.00,
    "garazas":     0.00,
    "drabuzine":   0.00,
    "rubine":      0.00,
    "techpatalpa": 0.00,
    # 2026-08-23 vocabulary sweep — classes the normaliser can now produce
    # that Objektas A never contained. All 0.00 ON PURPOSE: inferring LED metres
    # into a room type we have zero contractor evidence for is exactly the
    # fabrication the objektas_c over-bill taught us to avoid (see module
    # docstring). `holas` and `laiptine` are the two that plausibly DO carry
    # LED in premium projects — raise them only against measured truth, not
    # intuition.
    "holas":       0.00,
    "laiptine":    0.00,
    "sandeliukas": 0.00,
    "katiline":    0.00,
    "terasa":      0.00,
    "pirtis":      0.00,
    "baseinas":    0.00,
    "virtuve":     0.00,
}

MIN_INFERENCE_RATIO = 0.15  # below this, treat as "no LED expected"

# The `_source` every inferred niche carries — the one marker the rows, the
# gate below and the disclosure read (2026-10-03).
INFERRED_SOURCE = "statistical_inference"

# ── Disclosure on the billed rows (2026-10-03, audit vision-pipeline-1) ──────
# The ratios above were fitted on one contractor's sąmata (that fact stays in
# this file, never on his screen). An estimated length is billed on three rows
# — GKP framing, putty, paint — and those rows used to show green like a
# measured one. Every row fed by an estimate now says so, names the rooms and
# their metres, and is never green: geltona when part of the length was read,
# raudona when none of it was (CLAUDE.md §7 — a room-type default is the
# fallback tier).
LED_ESTIMATE_ROOM_SENTENCE = (
    "Nišos ilgis įvertintas pagal patalpos tipą — brėžinyje neišmatuotas. "
    "Patikrinkite lubų plane, ar čia yra LED niša, ir įrašykite tikrą ilgį.")

# ── The estimate is HIS choice (2026-10-06, founder decision) ────────────────
# Re-applied from docs/superpowers/patches/2026-10-03-round12-led-optin.patch.
# On: an estimated length is NOT billed until he accepts it in Nustatymai
# (`_overrides[LED_ESTIMATE_CHOICE_KEY] = True`). The three LED rows carry the
# metres read off the drawing; one blank row („LED nišos — suveskite ilgį")
# names the rooms where no niche length was read with the estimate for each.
# Accepted, the estimate is billed exactly as before, with the disclosure
# above. Off (False): the 2026-10-03 behaviour — billed and disclosed.
# Measured 2026-10-03 (and again 2026-10-06, see the round report): on the
# corpus the estimate is closer to the contractor's billed length than a blank
# (objektas_b LED −18 % → −52 %, objektas_d −2,5 % → −47 %); the founder chose
# the rule over the closer number.
LED_ESTIMATE_OPT_IN = True
LED_ESTIMATE_CHOICE_KEY = "led_nisu_ivertinimas"
# Per room: the estimated metres held back from `nisu_metrai` while he has not
# accepted them. Absent when nothing is held back.
HELD_ESTIMATE_KEY = "_nisu_ivertinta_m"
# The condition the blank row exists under: both merges (api/recompute_quantities,
# frontend mergeDarbuSarasas) drop it un-edited once he accepts, instead of
# carrying it back as a stale row.
WAITING_ROW_CONDITION = "led_nisu_ivertinimas_laukia"
WAITING_ROW_LABEL = "LED nišos — suveskite ilgį"


def estimate_accepted(overrides: dict | None) -> bool:
    """Is an estimated niche length billed? Always with LED_ESTIMATE_OPT_IN
    off; with it on, only once he chose „Priimti įvertinimą"."""
    if not LED_ESTIMATE_OPT_IN:
        return True
    v = overrides.get(LED_ESTIMATE_CHOICE_KEY) if isinstance(overrides, dict) else None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v >= 0.5
    return str(v).strip().lower() in ("true", "1", "priimti")


def _lt(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",")


def estimated_niche_m(room: dict) -> float:
    """Metres of LED niche in this room ESTIMATED from its room type (not read)."""
    total = 0.0
    for e in room.get("elementai") or []:
        if (isinstance(e, dict) and (e.get("tipas") or "").lower() == "nisa_led"
                and e.get("_source") == INFERRED_SOURCE):
            try:
                total += max(0.0, float(e.get("ilgis_m") or 0))
            except (TypeError, ValueError):
                continue
    return round(total, 2)


def held_estimate_m(room: dict) -> float:
    """Estimated metres this room holds back from its billed length (0 = none)."""
    try:
        return max(0.0, float(room.get(HELD_ESTIMATE_KEY) or 0))
    except (TypeError, ValueError, AttributeError):
        return 0.0


def billed_estimate_m(room: dict) -> float:
    """Metres of this room's BILLED niche length (`nisu_metrai`) that are an
    estimate: none while the estimate waits for his answer, else the estimate
    capped at what the room bills (a room its scope zeroed bills none)."""
    if held_estimate_m(room) > 0:
        return 0.0
    try:
        billed = float(room.get("nisu_metrai") or 0)
    except (TypeError, ValueError):
        billed = 0.0
    return round(min(estimated_niche_m(room), billed), 2)


def led_estimated_rooms(rooms: list[dict]) -> list[tuple[dict, float]]:
    """(room, estimated metres) for every room whose billed niche length
    (`nisu_metrai`) holds an estimate. Capped at what the room bills, so a
    room its scope zeroed is not named."""
    out: list[tuple[dict, float]] = []
    for r in rooms or []:
        if not isinstance(r, dict):
            continue
        est = billed_estimate_m(r)
        if est > 0:
            out.append((r, est))
    return out


def _room_label(room: dict) -> str:
    return str(room.get("nr") or room.get("pavadinimas") or "?").strip()


def led_estimate_disclosure(estimated: list[tuple[dict, float]], total_m: float) -> dict:
    """The fields every LED-niche row carries when part of its length is an
    estimate: tier, the reason (what to check, in which rooms) and the
    assumption. Empty dict when every metre was read."""
    if not estimated:
        return {}
    est_m = round(sum(m for _, m in estimated), 2)
    where = ", ".join(f"{_room_label(r)} ({_lt(m)} m)" for r, m in estimated)
    all_estimated = est_m >= float(total_m or 0) - 0.005
    check = ("Patikrinkite lubų plane, ar šiose patalpose yra LED nišos, ir "
             "įrašykite tikrą ilgį.")
    if all_estimated:
        reason = (f"Nišų ilgis įvertintas pagal patalpos tipą, ne išmatuotas brėžinyje — "
                  f"patalpose {where}. {check}")
    else:
        reason = (f"Dalis nišų ilgio — {_lt(est_m)} m iš {_lt(total_m)} m — įvertinta pagal "
                  f"patalpos tipą, ne išmatuota brėžinyje: patalpose {where}. {check}")
    return {
        "confidence": "low" if all_estimated else "medium",
        "_confidence_reason": reason,
        "_assumption": (f"{_lt(est_m)} m nišų ilgio — įvertinimas pagal patalpos tipą "
                        "(patalpos perimetras × tokio tipo patalpoms būdinga dalis), "
                        "ne brėžinio matmuo."),
        "_led_ivertinta_m": est_m,
    }


def led_estimate_waiting(rooms: list[dict]) -> list[tuple[dict, float]]:
    """(room, estimated metres) for every room whose estimate waits for his
    answer. A room whose finishing his „ką skaičiuoti" took out is not named —
    its billed metres are zeroed by the same choice (extractor/scope.py)."""
    out: list[tuple[dict, float]] = []
    for r in rooms or []:
        if not isinstance(r, dict) or r.get("_neskaiciuoti"):
            continue
        if "apdaila" in (r.get("_neskaiciuoti_sritys") or []):
            continue
        m = round(held_estimate_m(r), 2)
        if m > 0:
            out.append((r, m))
    return out


def led_estimate_waiting_row(waiting: list[tuple[dict, float]]) -> dict | None:
    """The blank row (no quantity: he fills it in, or accepts the estimate in
    Nustatymai) that names the rooms where no niche length was read and the
    estimate for each. None when nothing waits. The section is the caller's."""
    if not waiting:
        return None
    total = round(sum(m for _, m in waiting), 2)
    where = ", ".join(f"{_room_label(r)} (įvertinimas {_lt(m)} m)" for r, m in waiting)
    return {
        "aprasymas": WAITING_ROW_LABEL,
        "vnt": "m", "kiekis": None, "saltinis": "checklist", "confidence": "low",
        "_only_while": WAITING_ROW_CONDITION,
        "_led_ivertinta_m": total,
        "_confidence_reason": (
            f"Nišų ilgio brėžinyje neperskaičiau patalpose {where}. Patikrinkite lubų "
            "plane, ar šiose patalpose yra LED nišos."),
        "_assumption": (
            f"Pagal patalpos tipą įvertinta iš viso {_lt(total)} m — tai ne brėžinio matmuo, "
            "todėl į nišų eilutes neįtraukta. Jei įvertinimas tinka, per mygtuką „Nustatymai“ "
            "prie „LED nišos be perskaityto ilgio“ pasirinkite „Priimti įvertinimą“ — šie "
            "metrai bus pridėti prie nišų eilučių. Jei ilgį išmatavote patys, įrašykite jį "
            "šioje eilutėje."),
    }

# ── Enumerated-exclusion gate (2026-08-04) ────────────────────────────────────
# The docstring above asks for "a coverage map not yet persisted in the
# extract" before inference can be suppressed safely. A cheaper anchor IS
# persisted: when Vision reads the ceiling plan well enough to ENUMERATE which
# rooms have LED niches ("LED nišos kambariuose 01, 03, 04, 05"), that warning
# is positive evidence about every room NOT on the list. Inferring a niche
# into an excluded room contradicts a read we already trust elsewhere.
#
# Measured on the saved corpus (scripts/_diag_led.py, 2026-08-03): objektas_c
# carried two fabricated bathroom niches exactly this warning excludes —
# LED +33.31% → −7.9%, project MAE 13.801 → 7.462, corpus 9.311 → 7.820.
# objektas_a / objektas_b / objektas_d emit no enumerating warning and are
# bit-identical, which is also the fail-closed contract: no enumeration →
# this gate does nothing.

_LED_CTX = re.compile(r"led|niš|nis[uų]", re.IGNORECASE)
_ROOM_LIST = re.compile(
    r"kambari(?:uose|ai|ų)\s*((?:\d+[.\d]*\s*,\s*)+\d+[.\d]*)", re.IGNORECASE)


def enumerated_led_rooms(warnings) -> set[str] | None:
    """Return the room-nr set from the first warning that BOTH mentions LED
    niches AND enumerates room numbers — or None when no warning does.

    Both conditions are required on the SAME warning: an LED mention alone
    ("LED nišų ilgiai apytiksliai") carries no room evidence, and a room list
    alone may be about something else entirely. Warnings arrive as dicts
    ({message}) or bare strings depending on pipeline age; handle both.
    """
    for w in warnings or []:
        text = w.get("message") if isinstance(w, dict) else str(w)
        if not text or not _LED_CTX.search(text):
            continue
        m = _ROOM_LIST.search(text)
        if m:
            return {x.strip() for x in m.group(1).split(",")}
    return None


def drop_unenumerated_inferred_niches(parsed: dict) -> int:
    """Remove statistical-inference nisa_LED rows from rooms an enumerating
    warning excludes. Returns how many were dropped (0 = gate never fired).

    Deliberately narrow, in both directions:
      • Only `_source == "statistical_inference"` rows are touchable — a niche
        Vision actually READ in an excluded room is a disagreement between two
        reads, not a fabrication, and stays.
      • No enumerating warning → nothing happens. A blanket "no inferred
        niches" was simulated and REJECTED (2026-08-03): it moves objektas_b
        LED −18.2% → −51.6% and objektas_d −2.5% → −46.7% — the inference lane
        earns its keep everywhere the drawing doesn't say otherwise.
    """
    allowed = enumerated_led_rooms(parsed.get("warnings"))
    if not allowed:
        return 0
    dropped = 0
    for room in parsed.get("patalpos") or []:
        if str(room.get("nr") or "").strip() in allowed:
            continue
        keep = []
        for e in room.get("elementai") or []:
            if ((e.get("tipas") or "").lower() == "nisa_led"
                    and e.get("_source") == INFERRED_SOURCE):
                dropped += 1
                continue
            keep.append(e)
        if len(keep) != len(room.get("elementai") or []):
            room["elementai"] = keep
    return dropped


def infer_missing_niches(rooms: list[dict]) -> int:
    """For each room with zero nisa_LED and a paskirtis that typically
    has LED, inject a single statistical-inference nisa_LED row.
    Returns the count of rooms that got an inferred niche.
    """
    n_added = 0
    for room in rooms:
        elementai = room.get("elementai") or []
        # Skip if room already has any non-zero nisa_LED
        existing_led = sum(
            float(e.get("ilgis_m") or 0)
            for e in elementai
            if (e.get("tipas") or "").lower() == "nisa_led"
        )
        if existing_led > 0:
            continue
        # Normalised, not raw-lowercased (2026-08-23): a foreign extract that
        # labels the room "Koridorius 1" or "Tambūras" used to miss the table
        # entirely and get ratio 0.0 by accident. Corpus paskirtys are already
        # canonical, so this is a no-op on the benchmark. A room with NO
        # paskirtis at all keeps ratio 0.0 — normalize_paskirtis() defaults
        # empty input to "gyvenamoji" (0.40), and inferring LED into a room
        # nobody classified would be inference on top of inference.
        raw_paskirtis = (room.get("paskirtis") or "").strip()
        paskirtis = normalize_paskirtis(raw_paskirtis) if raw_paskirtis else ""
        ratio = LED_RATIO_BY_PASKIRTIS.get(paskirtis, 0.0)
        if ratio < MIN_INFERENCE_RATIO:
            continue
        perim = float(room.get("perimetras_m") or 0)
        if perim <= 0:
            continue
        inferred_m = round(perim * ratio, 2)
        # Strip any zero-length nisa_LED placeholder entries first so
        # the inferred row is the only one
        room["elementai"] = [
            e for e in elementai
            if not ((e.get("tipas") or "").lower() == "nisa_led"
                    and not float(e.get("ilgis_m") or 0))
        ]
        room["elementai"].append({
            "tipas": "nisa_LED",
            "kiekis": 1,
            "ilgis_m": inferred_m,
            "_niche_type": "ceiling_led",
            "_source": INFERRED_SOURCE,
            "_confidence": "low",
            "_paskirtis_ratio": ratio,
        })
        n_added += 1
    return n_added

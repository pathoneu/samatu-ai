"""Statistical LED-niche fallback for rooms the Vision pipeline missed.

The niche_locator does best-effort extraction from ceiling plans;
when it returns nothing for a room type that typically HAS LED, we
fill in an estimate based on per-room-type ratios derived from
Beržų's contractor-validated data:

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
  berzas       no change (all 0-LED rooms have ratio=0; LED -0.99%)
  bacveviciaus 26.61m → 44.97m (truth 54.98; -52% → -18.2%)
  ciurliu      14.50m → 18.95m (truth 16.84; -13.9% → +12.5% — over-bills)

The ciurliu case shows the risk: when a 0-LED room ACTUALLY has 0
LED (not just "Vision missed it"), this fallback over-bills. Here it
fires on exactly 2 'san' wet rooms (perim × 0.27 = +4.45m) the
contractor never billed, flipping -13.9% UNDER → +12.5% OVER. The
ratios cannot simply be lowered to fix it: the same san=0.27 HELPS
bacveviciaus (+6.26m), and dropping san/vonia/wc regresses
bacveviciaus to -29.6% (verified). The clean asymmetric fix is to
gate inference on per-room locator coverage (suppress only when the
locator demonstrably imaged the room's ceiling plan and found 0),
which needs a coverage map not yet persisted in the extract. Until
then, route over-bills through the contractor /calibrate UI.
"""
from __future__ import annotations

# Empirical LED-per-perimeter-meter ratios computed from Beržų's
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
    # Room types with no LED in Beržų (and unlikely elsewhere)
    "tamburas":    0.00,
    "garazas":     0.00,
    "drabuzine":   0.00,
    "rubine":      0.00,
    "techpatalpa": 0.00,
}

MIN_INFERENCE_RATIO = 0.15  # below this, treat as "no LED expected"


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
        paskirtis = (room.get("paskirtis") or "").lower()
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
            "_source": "statistical_inference",
            "_confidence": "low",
            "_paskirtis_ratio": ratio,
        })
        n_added += 1
    return n_added

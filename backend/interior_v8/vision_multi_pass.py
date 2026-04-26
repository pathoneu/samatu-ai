"""
Multi-pass Vision (skill A.3).

3 nepriklausomi Vision call'ai → median per kambarį.
+7-15% accuracy (Iterative Consensus Ensemble research). 3× brangiau.

Aplikacija: vartotojas Setup Wizard'e gali įjungti "Premium accuracy mode".
Default — single-pass (mūsų dabartinis V7).
"""
from __future__ import annotations
import statistics
from typing import Any


def merge_multi_pass_results(results: list[dict]) -> dict:
    """Sumerge'inti N nepriklausomus Vision rezultatus per consensus voting.

    Per kambarį (matching by `nr` arba `pavadinimas`):
    - Plotas, perimetras, dazymo_plotas, kampai → MEDIAN
    - Pavadinimas, paskirtis → MAJORITY VOTE
    - Variance >20% per metric → flag low confidence

    Args:
        results: list of V7 parsed outputs (po _call_opus_v7)

    Returns:
        Sumerge'intas rezultatas su confidence indikatoriais
    """
    if not results:
        return {"patalpos": [], "_multi_pass": False}

    if len(results) == 1:
        # Single pass — nieko nemerge'inam
        out = dict(results[0])
        out["_multi_pass"] = False
        out["_passes_count"] = 1
        return out

    # Surenkam visus kambarius iš visų pass'ų
    # Key per kambarį = (nr) jei yra, kitaip pavadinimas
    rooms_by_key = {}  # key → list of room dicts (vienas per pass)
    for pass_result in results:
        for room in pass_result.get("patalpos", []):
            key = room.get("nr") or room.get("pavadinimas", "")
            if not key:
                continue
            rooms_by_key.setdefault(key, []).append(room)

    # Per kambarį — sumergē'inti
    merged_rooms = []
    confidence_flags = []

    NUMERIC_FIELDS = [
        "plotas_m2", "perimetras_m", "lubu_aukstis_m",
        "dazymo_plotas_m2", "kampu_metrai", "angokrasciu_gkp_m",
        "pasleptu_duru_staktu_m", "pvc_grindys_m2",
        "plyteles_grindys_m2", "plyteles_sienos_m2",
        "isliginamasis_m2", "grindjuosciu_m",
    ]
    TEXT_FIELDS = ["pavadinimas", "paskirtis", "lubu_tipas"]

    for key, room_versions in rooms_by_key.items():
        # Tik kambariai, kurie yra >50% pass'ų — kiti drop'inami (per neaiškūs)
        if len(room_versions) < len(results) / 2:
            confidence_flags.append({
                "level": "INFO",
                "room": key,
                "message": f"Patalpa '{key}' aptikta tik {len(room_versions)}/{len(results)} pass'ų — praleista (per neaiški).",
            })
            continue

        merged = {}

        # Tekstiniai laukai — majority vote
        for field in TEXT_FIELDS:
            values = [r.get(field) for r in room_versions if r.get(field)]
            if values:
                # Most common
                from collections import Counter
                merged[field] = Counter(values).most_common(1)[0][0]

        # Numeriniai laukai — median + variance check
        for field in NUMERIC_FIELDS:
            values = [r.get(field) or 0 for r in room_versions if r.get(field) is not None]
            values = [v for v in values if v > 0]  # Atimam nulius
            if not values:
                continue
            median_val = statistics.median(values)
            merged[field] = round(median_val, 2)

            # Variance check
            if len(values) >= 2:
                avg = statistics.mean(values)
                if avg > 0:
                    max_dev = max(abs(v - avg) for v in values)
                    variance_pct = max_dev / avg * 100
                    if variance_pct > 20:
                        confidence_flags.append({
                            "level": "INFO",
                            "room": merged.get("pavadinimas") or key,
                            "field": field,
                            "values": values,
                            "median": median_val,
                            "message": (f"'{merged.get('pavadinimas') or key}' {field}: "
                                        f"variance {variance_pct:.0f}% per pass'us "
                                        f"({values}). Naudojam median {median_val}."),
                        })

        # Pridedam nepakitusius laukus (nr, etc.)
        for field in ("nr", "puslapio_nr", "bbox_pct"):
            for r in room_versions:
                if r.get(field):
                    merged[field] = r[field]
                    break

        merged_rooms.append(merged)

    # Globalūs laukai (durys, langai, nišos, archetipas)
    base = dict(results[0])
    base["patalpos"] = merged_rooms
    base["_multi_pass"] = True
    base["_passes_count"] = len(results)
    base["_confidence_flags"] = confidence_flags

    return base


def run_multi_pass_vision(call_fn, n_passes: int = 3) -> dict:
    """Paleisti Vision N kartų ir merge'inti rezultatus.

    Args:
        call_fn: function() → V7 parsed result. Kviečiama N kartų.
        n_passes: kiek pass'ų (default 3, recommend 3-5)

    Returns:
        Merged result su _multi_pass=True
    """
    results = []
    for i in range(n_passes):
        try:
            r = call_fn()
            if r and not r.get("_parse_error"):
                results.append(r)
        except Exception as e:
            print(f"[multi_pass] pass {i+1} failed: {e}")
            continue

    if not results:
        return {"_parse_error": "Visi pass'ai nepavyko"}

    return merge_multi_pass_results(results)

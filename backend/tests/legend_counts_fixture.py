"""Test helper (v4 3c-2): plumbing counts as the drawing's legend proposes them (`_meta.legendos_siulymai`).

Since 3c-2 the santechnika rows take their counts from the legend rows (extractor/legend_counts.py) — the old
model plumbing reading (`_meta.fixtures_status` + `detected_symbols_summary`) is no source. Tests that built rows on
those counts describe the same counts as a legend proposal through `legend_meta`.
"""
from __future__ import annotations

PLUMBING_FAMILIES = ("klozetai", "praustuves", "plautuves", "dusai", "wc_remai", "bide", "vonios_kubilai", "trapai",
                     "sviestuvai", "sviestuvai_pakabinami", "rozetes", "jungikliai", "termostatai")


def legend_meta(symbols: dict | None, **meta) -> dict:
    """`_meta` with a legend proposal per family in `symbols` (count ≥ 1); other keys of `symbols` are ignored."""
    seimos = {}
    for k, v in (symbols or {}).items():
        try:
            n = int(float(v or 0))
        except (TypeError, ValueError):
            continue
        if k in PLUMBING_FAMILIES and n > 0:
            seimos[k] = {"kiekis": n, "tekstas": k, "lapai": [1], "saltinis": "vektoriai"}
    return {**meta, "legendos_siulymai": {"status": "ok", "lapai_su_legenda": [1], "seimos": seimos}}

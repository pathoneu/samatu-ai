"""LT invoice bundling rules (Week 4 Task 4.2 — D5 verdict).

Default mode collapses glaistymas + dažymas + gruntavimas into a single
`glaistymas_dazymas_bundle` line at ~14 €/m² (rangovas mid-market Kaunas,
verified across P2-P5 in R4 research). Advanced mode keeps the per-Q-level
breakdown for engineers who want it.

Why: invoice reality across LT residential interior rarely lists each kg of
putty separately. Estimators bid one m² rate for "sienų + lubų glaistymas +
dažymas". Splitting the line (as the legacy pipeline did) doesn't match the
contractor's mental model and inflates audit complexity.
"""
from __future__ import annotations

from copy import deepcopy

BUNDLE_GLAISTYMAS_DAZYMAS = "glaistymas_dazymas_bundle"
DEFAULT_BUNDLED_PRICE_EUR = 14.0  # R4 research: rangovas P2-P5 bundled rate

# Member line codes that collapse into the bundle in default mode.
BUNDLE_MEMBERS = {
    BUNDLE_GLAISTYMAS_DAZYMAS: {
        "glaistymas_q1_m2", "glaistymas_q2_m2", "glaistymas_q3_m2", "glaistymas_q4_m2",
        "dazymas_sienos_m2", "dazymas_lubos_m2", "gruntavimas_m2",
        "sienu_paruosimas_m2",
    },
}


def collapse_to_bundled(raw: dict, mode: str = "default_bundled") -> dict:
    """Collapse member lines into a single bundled line.

    Args:
        raw: dict with `lines` array (and optionally other top-level keys
            like `totals`, `warnings` — preserved unchanged).
        mode: "default_bundled" (collapse) | "advanced_split" (pass through).

    Returns:
        Deep copy with member lines replaced by the bundle. Other lines
        preserved verbatim.
    """
    if mode not in ("default_bundled", "advanced_split"):
        raise ValueError(f"mode must be 'default_bundled' or 'advanced_split', got {mode}")
    if mode == "advanced_split":
        return deepcopy(raw)

    out = deepcopy(raw)
    bundled_qty = 0.0
    survivors: list[dict] = []
    for line in out.get("lines", []):
        if line["code"] in BUNDLE_MEMBERS[BUNDLE_GLAISTYMAS_DAZYMAS]:
            bundled_qty += float(line.get("quantity", 0))
        else:
            survivors.append(line)
    if bundled_qty > 0:
        survivors.append({
            "code": BUNDLE_GLAISTYMAS_DAZYMAS,
            "label_lt": "Sienų + lubų glaistymas + dažymas (bundled)",
            "unit": "m²",
            "quantity": round(bundled_qty, 2),
            "unit_price_eur_be_pvm": DEFAULT_BUNDLED_PRICE_EUR,
            "confidence": "green",
            "source": "rule",
            "formula": "Σ(member glaistymas/dažymas/gruntavimas lines)",
        })
    out["lines"] = survivors
    return out


# Q-level coefficients (legacy universal_rules constants kept here so the
# bundling helper is self-contained and importable without pulling in the
# whole rules engine).
Q_KG_PER_M2_PER_MM = {"Q1": 0.8, "Q2": 1.0, "Q3": 1.2, "Q4": 1.5}
Q_THICK_MM = {"Q1": 1.2, "Q2": 1.25, "Q3": 1.75, "Q4": 2.5}


def expand_to_q_level(bundled_qty_m2: float, q_level: str) -> list[dict]:
    """Advanced-mode helper: explode bundled m² into per-Q-level material lines.

    Q4 additionally produces a `slifavimas_m2` line item per DIN 18363 (full
    surface 80–120-grit raking-light sanding). The R4 research notes most LT
    contractors don't price this separately on the invoice — but for material
    truth-telling it should appear when the user opts into advanced mode.
    """
    if q_level not in Q_KG_PER_M2_PER_MM:
        return []
    total_kg = bundled_qty_m2 * Q_THICK_MM[q_level] * Q_KG_PER_M2_PER_MM[q_level]
    out: list[dict] = [{
        "code": "glaistas_kg",
        "label_lt": f"Glaistas ({q_level})",
        "unit": "kg",
        "quantity": round(total_kg, 1),
        "confidence": "green",
        "source": "rule",
        "formula": f"qty_m2 × thickness_mm × kg/m²/mm ({q_level})",
    }]
    if q_level == "Q4":
        out.append({
            "code": "slifavimas_m2",
            "label_lt": "Q4 šlifavimas (DIN 18363)",
            "unit": "m²",
            "quantity": round(bundled_qty_m2, 2),
            "confidence": "yellow",
            "source": "rule",
            "formula": "Q4 only: full-surface 80-120 grit raking-light sanding",
        })
    return out

"""Sąmatų AI interior takeoff evaluation harness.

Usage:
    python eval_harness.py --use-gt-inputs            # bypass Vision, feed GT primitives
    python eval_harness.py --use-gt-inputs --project objektas_a
    python eval_harness.py --replay <extract.json>    # diff a saved extractor output
    python eval_harness.py --vision                   # call the real Vision pipeline ($$)

Stop condition (Phase 1): `python eval_harness.py --use-gt-inputs` succeeds, prints
per-category absolute / percentage error vs contractor truth, and writes an HTML report.

Registry: each entry maps `project_id` → `ground_truth/<project_id>/truth.json`.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent
GROUND_TRUTH_ROOT = REPO_ROOT / "ground_truth"
EVAL_RUNS_ROOT = REPO_ROOT / "eval_runs"

# ── Registry ───────────────────────────────────────────────────────────────────
REGISTRY: dict[str, dict[str, str]] = {
    "objektas_a": {
        "name": "Objektas A",
        "truth_path": "ground_truth/objektas_a/truth.json",
        "pdf_path": "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf",
        # Cached known-good Vision extract used by --replay if Vision is not called.
        "replay_path": "docs/superpowers/fixtures/2026-05-26-objektas-a/app-output-to-the-dot.json",
    },
}

# Backend import path setup
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _merge_registry_yaml() -> None:
    """W1.2: fold ground_truth/registry.yaml projects into REGISTRY so
    single-project modes (``--project objektas_c --vision``) reach every
    benchmark project, not just the hardcoded objektas_a entry. The YAML key
    ``project_pdf`` maps to the in-file ``pdf_path``. Hardcoded entries win
    (objektas_a keeps its replay_path)."""
    reg_path = GROUND_TRUTH_ROOT / "registry.yaml"
    if not reg_path.exists():
        return
    try:
        import yaml
        reg = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # malformed registry — single-project objektas_a still works
        print(f"  ⚠ registry.yaml not merged: {exc}")
        return
    for entry in reg.get("projects") or []:
        slug = entry.get("slug")
        if not slug or slug in REGISTRY or not entry.get("truth_path"):
            continue
        merged: dict[str, str] = {
            "name": entry.get("name", slug),
            "truth_path": entry["truth_path"],
        }
        if entry.get("project_pdf"):
            merged["pdf_path"] = entry["project_pdf"]
        # Carry the exclusion flags through. run_totals_only_multi reads them
        # straight off the YAML, but the single-project paths (--rescore in
        # particular) only see REGISTRY — which is how romainiai's
        # registry-excluded score got hand-averaged into a "corpus MAE".
        for flag in ("scope_mismatch", "scope_mismatch_reason",
                     "blocked_for_vision_extraction", "blocked_partial_input",
                     "blocked_reason", "ablation_of", "out_of_sample"):
            if entry.get(flag):
                merged[flag] = entry[flag]
        REGISTRY[slug] = merged


_merge_registry_yaml()


# Metrics that are printed but never pooled into an MAE (2026-09-05, founder
# rule: „daryk atskirai lubas ir sienas"). The contractor's combined
# „Sienų, lubų glaistymas/dažymas" line is the SUM of two quantities we score
# separately; averaging it in let a walls error and a ceilings error cancel
# — which is exactly how a double-billed bathroom wall stayed invisible on
# objektas_c/d until the first out-of-sample runs. It stays in the table
# (it is his row) and in the row scorecard (which pairs his one row with our
# two), but the headline number is walls and ceilings on their own.
INFORMATIONAL_METRICS = frozenset({"dazymo_walls_plus_ceilings_combined_m2"})


# ── Metric mapping: contractor truth field → extractor output field/extractor ──
# Each entry: truth_key → (label, accessor(parsed_extractor_output) → float)
#
# Literal copy of `extractor.vision_call.SK_MEDZIAGOS`. Copied rather than
# imported because this module is loaded before `backend/` is on sys.path.
_MEDZIAGOS_SKYRIUS = "Medžiagos"


def _santrauka_get(parsed: dict, key: str) -> float:
    return float((parsed.get("santrauka") or {}).get(key) or 0.0)


def _sum_room_field(parsed: dict, field: str) -> float:
    return float(sum((r.get(field) or 0) for r in (parsed.get("patalpos") or [])))


def _gkp_lubu_only_for_type(parsed: dict, field: str) -> float:
    """Sum a per-room GKP-ceiling field only across rooms whose ceiling type
    is actually GKP / tempiamos — the calculator already gates this, but make
    it explicit here for the truth diff."""
    total = 0.0
    for r in (parsed.get("patalpos") or []):
        if (r.get("lubu_tipas") or "").lower() in ("gkp", "tempiamos"):
            total += float(r.get(field) or 0)
    return round(total, 2)


def _pozicijos_sum(parsed: dict, substr: str) -> float | None:
    """Sum kiekis over pozicijos whose aprašymas contains ``substr``
    (case-insensitive). Returns None when no matching pozicija exists —
    the metric then scores as "missing", not as 0.

    2026-07-04 mapping fix: several contractor truth lines (e.g. "Sienų
    lyginimas Rotband") ARE produced by the pipeline — as pozicijos[]
    line items, not santrauka keys — but the eval never read them, so
    they scored as missing coverage on every project.

    2026-09-02: MATERIAL rows are excluded. The builder now lifts every
    auto-computed material into its own "Medžiagos" section, and a material's
    name repeats its work's ("Rotband (~10 kg/m² …)" under "Sienų lyginimas
    Knauf Rotband"). Summed together, the m² of wall being levelled and the kg
    of Rotband levelling it would land in one number — 125.73 m² would have
    scored as 1 383.03. A work metric may only ever read work rows."""
    total = 0.0
    found = False
    for item in (parsed.get("pozicijos") or []):
        if (item.get("skyrius") or "") == _MEDZIAGOS_SKYRIUS or item.get("_medziaga"):
            continue
        if substr in (item.get("aprasymas") or "").lower():
            total += float(item.get("kiekis") or 0)
            found = True
    return round(total, 2) if found else None


def _santrauka_else_pozicijos(parsed: dict, key: str,
                              substr: str) -> float | None:
    """Read a santrauka total, falling back to the matching pozicijos line
    when that santrauka key is empty.

    2026-07-29 (romainiai): ``pasleptu_duru_staktu_m_total`` is a DEAD
    santrauka key — universal_rules only ever accumulates it from a per-room
    ``pasleptu_duru_staktu_m`` field that nothing writes (prompt.py forbids
    Vision from emitting it: it is a computed quantity). It reads 0.0 on all
    five benchmark projects. The quantity itself is real and IS produced —
    vision_call builds it project-wide from the ``pasleptos_duris`` elements
    and emits it as the pozicija "Durų angų paruošimas beapvadinėms durims".
    Scoring the santrauka key therefore guaranteed a −100% "collapse" on
    every project that has this truth line, measuring nothing but the dead
    key. Same class as the 2026-07-04 rotband mapping fix above."""
    from_santrauka = _santrauka_get(parsed, key)
    if from_santrauka:
        return from_santrauka
    return _pozicijos_sum(parsed, substr)


METRICS: dict[str, dict[str, Any]] = {
    "dazymo_walls_plus_ceilings_combined_m2": {
        # Truth 584.81 is samata items 16+17 (sienos + lubos paint, excluding
        # garažas which the contractor bills under separate items with
        # different unit prices). Compare against the app's matching slice.
        "label": "Dažymo plotas (samata items 16+17, excl garažas)",
        "accessor": lambda p: _santrauka_get(p, "dazymo_excl_garazas_total_m2"),
        "unit": "m²",
        "tier": "headline",
    },
    "walls_paint_total_m2": {
        "label": "Sienų dažomas plotas",
        # 2026-09-13: measure what is BILLED, like the ceilings. The Sienų rows
        # follow the sienų apdailos plano legend when the drawing states the
        # painted area (objektas_g: rooms 298,66 m², legend 220 m², act 239,4);
        # Σ room fields is the per-room paintable sum before that anchor.
        # Falls back to the per-room sum on an extract that emits no Sienų row.
        "accessor": lambda p: (
            _pozicijos_sum(p, "sienų glaistymas/dažymas")
            if _pozicijos_sum(p, "sienų glaistymas/dažymas") is not None
            else round(_sum_room_field(p, "walls_paintable_m2"), 2)),
        "unit": "m²",
        "tier": "headline",
    },
    "ceiling_paint_total_m2": {
        "label": "Lubų dažomas plotas",
        # 2026-09-05: measure what is BILLED. The Lubų rows are anchored to
        # the eksplikacija total (founder rule „lubos visada kaip iš
        # eksplikacijos"), while Σ room fields carries the table's own
        # rounding (objektas_a: rows 165,64 vs printed 165,61). Falls back to
        # the per-room sum on an extract that emits no Lubų row.
        "accessor": lambda p: (
            _pozicijos_sum(p, "lubų glaistymas/dažymas")   # substr is matched lower-cased
            if _pozicijos_sum(p, "lubų glaistymas/dažymas") is not None
            else round(_sum_room_field(p, "ceiling_paintable_m2"), 2)),
        "unit": "m²",
        "tier": "headline",
    },
    "led_nisos_m": {
        "label": "LED nišų ilgis",
        "accessor": lambda p: _santrauka_get(p, "nisu_metrai_total"),
        "unit": "m",
        "tier": "headline",
    },
    "floor_total_m2": {
        "label": "Bendras plotas",
        "accessor": lambda p: round(_sum_room_field(p, "plotas_m2"), 2),
        "unit": "m²",
        "tier": "headline",
    },
    "plyteles_grindys_total_m2": {
        "label": "Plytelės grindyse",
        "accessor": lambda p: _santrauka_get(p, "plyteles_grindys_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "plyteles_sienos_total_m2": {
        "label": "Plytelės sienose",
        "accessor": lambda p: _santrauka_get(p, "plyteles_sienos_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "gkp_lubu_iki_3m_m2": {
        "label": "GKP lubos iki 3m",
        "accessor": lambda p: _santrauka_get(p, "gkp_lubu_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "gkp_lubu_virs_3m_m2": {
        "label": "GKP lubos virš 3m",
        "accessor": lambda p: _santrauka_get(p, "gkp_lubu_virs_3m_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "kampu_metrai_m": {
        "label": "Dažymo kampai",
        "accessor": lambda p: _santrauka_get(p, "kampai_m_total"),
        "unit": "m",
        "tier": "category",
    },
    "rotband_lyginimas_m2": {
        # 2026-07-04: WAS accessor None ("not emitted as a single total") —
        # but the pipeline emits it as the pozicija "Sienų lyginimas Knauf
        # Rotband" (kiekis = 30% of walls_paint by default, override via
        # _overrides.rotband_share). All 4 benchmark truths carry this line;
        # the eval just never read it.
        "label": "Sienų lyginimas Rotband",
        "accessor": lambda p: _pozicijos_sum(p, "rotband"),
        "unit": "m²",
        "tier": "category",
    },
    # ── 2026-07-04 mapping-layer additions ────────────────────────────────
    # Produced santrauka/pozicijos totals that contractor truths bill under
    # per-project key names (wired in each ground_truth/<slug>/truth.json).
    "plyteles_sienos_grindys_combined_m2": {
        # Rangovas A bills wall+floor tiling as combined m² lines (per tile
        # format). Compare against our grindys+sienos sum. Projects with
        # per-surface truth (objektas_a) keep the split metrics above instead.
        "label": "Plytelės (sienos+grindys kartu)",
        "accessor": lambda p: round(
            _santrauka_get(p, "plyteles_grindys_m2_total")
            + _santrauka_get(p, "plyteles_sienos_m2_total"), 2),
        "unit": "m²",
        "tier": "category",
    },
    "pvc_grindys_m2": {
        # Engine bucket = non-tile finished floor covering (rt_rules floor ==
        # "parquet" family: PVC / parketas / laminatas). Truth wires the
        # project's covering line (objektas_c/objektas_d: PVC; objektas_b: parketas).
        # 2026-09-13: measure what is BILLED — the row follows the grindų plano
        # legend when the drawing states the covering area (objektas_g: rooms
        # 79,50 m², legend 76,65 m²); the santrauka total is the per-room sum.
        "label": "Grindų danga (PVC/parketas)",
        "accessor": lambda p: (
            _pozicijos_sum(p, "parketo / laminato klojimas")
            if _pozicijos_sum(p, "parketo / laminato klojimas") is not None
            else _santrauka_get(p, "pvc_grindys_m2_total")),
        "unit": "m²",
        "tier": "category",
    },
    "isliginamasis_grindys_m2": {
        "label": "Išlyginamasis grindims",
        "accessor": lambda p: _santrauka_get(p, "isliginamasis_m2_total"),
        "unit": "m²",
        "tier": "category",
    },
    "grindjuostes_total_m": {
        "label": "Grindjuostės (viso)",
        # 2026-09-13: the billed row (anchored to the grindų plano legend when
        # the drawing states the skirting length), else the per-room sum.
        "accessor": lambda p: (
            _pozicijos_sum(p, "grindjuosčių sumontavimas")
            if _pozicijos_sum(p, "grindjuosčių sumontavimas") is not None
            else _santrauka_get(p, "grindjuosciu_m_total")),
        "unit": "m",
        "tier": "category",
    },
    "plyteliu_grindjuostes_m": {
        # Tile skirting — the metres cut from the floor tiles along painted
        # walls (objektas_g act row „Plytelės - grindjuostės" 26,87 m; the
        # drawing's legend 24,97 m). A separate line from the MDF skirting.
        "label": "Plytelių grindjuostės",
        "accessor": lambda p: _pozicijos_sum(p, "plytelių grindjuosčių"),
        "unit": "m",
        "tier": "category",
    },
    "pasleptu_duru_staktos_m": {
        "label": "Paslėptų durų staktos",
        "accessor": lambda p: _santrauka_else_pozicijos(
            p, "pasleptu_duru_staktu_m_total", "beapvadinėms"),
        "unit": "m",
        "tier": "category",
    },
    "sienu_molio_tinkas_m2": {
        # Produced per-room (molio_tinko_m2, split out of walls_paintable by
        # the 2026-06-11 apdailos molio fix) but never summed into santrauka.
        "label": "Sienų molio tinkas",
        "accessor": lambda p: round(_sum_room_field(p, "molio_tinko_m2"), 2),
        "unit": "m²",
        "tier": "category",
    },
    "angokrasciu_m": {
        "label": "Angokraščiai",
        "accessor": lambda p: _santrauka_get(p, "angokrasciu_gkp_m_total"),
        "unit": "m",
        "tier": "category",
    },
    # The following truth fields don't have a current extractor output — they
    # surface as "MISSING" in the report and signal the next gap to close
    # (unbuilt readers: symbol counts + waste volume).
    "rozetes_jungtukai_count": {
        "label": "Rozetės + jungtukai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "sviestuvai_priglaistomi_count": {
        "label": "Priglaistomi šviestuvai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "difuzoriai_count": {
        "label": "Difūzoriai",
        "accessor": lambda p: None,
        "unit": "vnt",
        "tier": "counts",
    },
    "siuksles_m3": {
        "label": "Šiukšlių išvežimas",
        "accessor": lambda p: None,
        "unit": "m³",
        "tier": "counts",
    },
}


# ── Pipeline drivers ───────────────────────────────────────────────────────────
def _apply_exterior_heuristic_in_place(rooms: list[dict]) -> int:
    """Mirror of scripts/infer_exterior_openings rules. Applied to a list of
    room dicts on the fly so the eval can A/B the heuristic without mutating
    truth.json on disk. Returns count of openings flagged."""
    count = 0
    for room in rooms:
        paskirtis = (room.get("paskirtis") or "").lower()
        is_garage = paskirtis in ("garazas", "garažas")
        for el in room.get("elementai") or []:
            tipas = (el.get("tipas") or "").lower()
            if el.get("_exterior"):
                continue
            w = el.get("plotis_mm") or 0
            if tipas in ("duris", "pasleptos_duris"):
                if is_garage or w >= 1500:
                    el["_exterior"] = True
                    count += 1
            elif tipas in ("langas", "stoglangis"):
                if w >= 2000:
                    el["_exterior"] = True
                    count += 1
    return count


def _apply_perimeter_correction(rooms: list[dict], factor: float) -> int:
    """Scale every room's perimetras_m by the per-project correction factor.
    Returns count of rooms modified."""
    n = 0
    for room in rooms:
        if "perimetras_m" not in room:
            continue
        old = float(room["perimetras_m"])
        room["perimetras_m"] = round(old * factor, 4)
        n += 1
    return n


def _load_project_calibration(project_id: str) -> dict[str, Any]:
    """Read backend/data/calibrations/{project_id}.json if present."""
    p = REPO_ROOT / "backend" / "data" / "calibrations" / f"{project_id}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run_pipeline_use_gt_inputs(
    truth: dict, *,
    estimate_exterior: bool = False,
    apply_calibration: dict | None = None,
) -> dict:
    """Bypass Vision: feed GT primitives straight into the deterministic engine.

    Strips the `_dim_confidence` annotation from each room (calculator-side fields
    only) before invoking the engine; the rest of the GT room dict is exactly
    the primitive schema the calculator already consumes in production.

    Parameters
    ----------
    estimate_exterior : bool
        When True, apply the principled exterior-opening heuristic (garage
        doors, ≥1500mm doors, ≥2000mm windows) to gt_dimensions in memory
        before invoking the calculator. truth.json on disk is NOT modified.
    """
    vc = importlib.import_module("extractor.vision_call")
    _recompute_per_room = vc._recompute_per_room_via_python
    _recompute_santrauka = vc._recompute_santrauka

    rooms_in: list[dict] = []
    for r in truth["gt_dimensions"]:
        room = {k: v for k, v in r.items() if not k.startswith("_dim")}
        # Deep copy elementai to avoid mutating the loaded truth dict
        if room.get("elementai"):
            room["elementai"] = [dict(e) for e in room["elementai"]]
        rooms_in.append(room)

    flagged = 0
    if estimate_exterior:
        flagged = _apply_exterior_heuristic_in_place(rooms_in)

    perim_correction_applied = None
    if apply_calibration:
        factor = apply_calibration.get("perimeter_correction_factor")
        if isinstance(factor, (int, float)) and factor and abs(factor - 1.0) > 1e-6:
            n = _apply_perimeter_correction(rooms_in, float(factor))
            perim_correction_applied = {"factor": float(factor), "rooms_affected": n}

    parsed = {
        "patalpos": rooms_in,
        "archetipas": "dideli_namu_premium",
        "bendras_plotas_m2": truth.get("floor_total_sanity_check_m2") or 0,
        "_meta": {
            "mode": "use_gt_inputs",
            "harness": "eval_harness.py",
            "estimate_exterior": estimate_exterior,
            "openings_flagged_by_heuristic": flagged,
            "perimeter_correction_applied": perim_correction_applied,
        },
    }
    parsed = _recompute_per_room(parsed, _harness_rules_override())
    parsed = _recompute_santrauka(parsed)
    return parsed


def _harness_rules_override(parsed: dict | None = None) -> dict:
    """The rules_override the harness feeds the deterministic engine.

    2026-07-28: previously every harness entry point passed ``None`` while
    production (`NewProject.jsx`) posts a Setup-Wizard prefs dict. The two
    happened to agree numerically, but nothing enforced it — so the eval was
    measuring a configuration no user could actually get. Now BOTH sides
    start from the same backend-owned defaults
    (`universal_rules.default_paint_prefs`), and a rescored run additionally
    replays whatever overrides that run was actually produced with.
    """
    from extractor.universal_rules import default_paint_prefs
    merged = default_paint_prefs()
    stored = (parsed or {}).get("_overrides") if isinstance(parsed, dict) else None
    if isinstance(stored, dict):
        merged.update(stored)
    return merged


def run_pipeline_replay(extract_path: Path) -> dict:
    """Load a previously-recorded full extractor output and diff its totals.

    Useful for offline iteration without burning Vision credits. The recorded
    output is treated as if produced by the current pipeline.
    """
    with extract_path.open() as f:
        return json.load(f)


def run_pipeline_vision(pdf_path: Path) -> dict:
    """Full Vision pipeline (Phase 2 stop condition)."""
    vc = importlib.import_module("extractor.vision_call")
    pdf_bytes = pdf_path.read_bytes()
    # Same defaults a real user gets — see _harness_rules_override().
    return vc.extract_interior(pdf_bytes, rules_override=_harness_rules_override())


# ── Eval core ──────────────────────────────────────────────────────────────────
@dataclass
class MetricResult:
    truth_key: str
    label: str
    unit: str
    tier: str
    truth_value: float | None
    truth_confidence: str
    actual_value: float | None
    abs_error: float | None
    pct_error: float | None
    status: str          # "ok" | "warn" | "fail" | "missing" | "no_truth"

    @property
    def color(self) -> str:
        return {
            "ok": "🟢", "warn": "🟡", "fail": "🔴",
            "missing": "⬜", "no_truth": "⬛",
        }[self.status]


# Per-class bands (ok%, warn%) replace the old flat 0.5%/3.0%. A 0.5% green bar
# was threshold theater — no Vision-read perimeter is accurate to 0.5%, and it
# manufactured over-tuning pressure (e.g. the Garažas 0.7988 four-decimal factor
# chased a 0.9% residual that's inside the noise floor). Honest per-unit bands:
_BANDS = {
    "area":   (3.0, 8.0),    # m²  — areas read to ~few %
    "linear": (8.0, 15.0),   # m   — pattern items (kampai, silikonavimas) jitter more
    "count":  (2.0, 12.0),   # vnt — essentially exact (±1 on a count of ~50 ≈ 2%)
}


def _band_for_unit(unit: str | None) -> str:
    u = (unit or "").lower().strip()
    if "m²" in u or "m2" in u:
        return "area"
    if u == "m" or "lm" in u:
        return "linear"
    return "count"  # vnt, kompl, t, etc.


def _classify(pct: float | None, truth_conf: str | None = None,
              unit: str | None = "m²") -> str:
    if pct is None:
        return "missing"
    # When the truth itself is partial/incomplete, downgrade severity:
    # mismatches in those metrics are documentation gaps, not extraction
    # errors. Surfaced as ⬛ (no_truth-equivalent) so they don't dominate
    # the headline MAE.
    if truth_conf in ("incomplete", "partial"):
        return "no_truth"
    abs_pct = abs(pct)
    ok_t, warn_t = _BANDS[_band_for_unit(unit)]
    if abs_pct <= ok_t:
        return "ok"
    if abs_pct <= warn_t:
        return "warn"
    return "fail"


def evaluate(parsed: dict, truth: dict) -> list[MetricResult]:
    results: list[MetricResult] = []
    gt_totals = truth.get("gt_totals", {})
    for key, meta in METRICS.items():
        spec = gt_totals.get(key)
        truth_val: float | None
        truth_conf = "n/a"
        if spec is None:
            truth_val = None
            truth_conf = "absent"
        elif isinstance(spec, dict):
            v = spec.get("value")
            # Skip multi-value (e.g. led_nisos_breakdown) — handled separately
            if isinstance(v, list):
                continue
            truth_val = float(v) if v is not None else None
            truth_conf = spec.get("confidence", "n/a")
        else:
            truth_val = float(spec) if spec is not None else None

        actual_val = meta["accessor"](parsed)
        if actual_val is None and truth_val is None:
            status = "no_truth"
            abs_err = pct_err = None
        elif actual_val is None:
            status = "missing"
            abs_err = pct_err = None
        elif truth_val is None:
            status = "no_truth"
            abs_err = pct_err = None
        else:
            abs_err = round(actual_val - truth_val, 3)
            pct_err = round((abs_err / truth_val) * 100.0, 3) if truth_val else None
            status = _classify(pct_err, truth_conf=truth_conf, unit=meta.get("unit"))

        results.append(MetricResult(
            truth_key=key,
            label=meta["label"],
            unit=meta["unit"],
            tier=meta["tier"],
            truth_value=truth_val,
            truth_confidence=truth_conf,
            actual_value=actual_val if isinstance(actual_val, (int, float)) else None,
            abs_error=abs_err,
            pct_error=pct_err,
            status=status,
        ))
    return results


def evaluate_per_room(parsed: dict, truth: dict) -> list[dict]:
    """Diff per-room contractor-given values where present."""
    gt_per_room = truth.get("gt_per_room") or {}
    rooms_by_nr = {str(r.get("nr")): r for r in (parsed.get("patalpos") or [])}

    rows: list[dict] = []
    for nr, fields in gt_per_room.items():
        actual_room = rooms_by_nr.get(str(nr))
        if not actual_room:
            rows.append({"nr": nr, "missing": True})
            continue
        for field_key, spec in fields.items():
            truth_val = float(spec["value"])
            actual_val = float(actual_room.get(field_key) or 0)
            abs_err = round(actual_val - truth_val, 3)
            pct_err = round((abs_err / truth_val) * 100.0, 3) if truth_val else None
            rows.append({
                "nr": nr,
                "pavadinimas": actual_room.get("pavadinimas"),
                "field": field_key,
                "truth": truth_val,
                "actual": actual_val,
                "abs_error": abs_err,
                "pct_error": pct_err,
                "status": _classify(pct_err),
                "source": spec.get("source", ""),
            })
    return rows


# ── Reporting ──────────────────────────────────────────────────────────────────
def _fmt_num(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:>10.2f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "    —"
    return f"{v:+7.2f}%"


def print_report(project_id: str, mode: str, results: list[MetricResult],
                 per_room: list[dict]) -> None:
    print()
    print("═" * 96)
    print(f"  Project: {project_id}   |   mode: {mode}")
    print("═" * 96)
    print(f"  {'metric':<40} {'truth':>10} {'actual':>10}   {'Δ':>10}   {'pct':>8}   conf  status")
    print("  " + "─" * 92)
    for r in results:
        if r.status == "no_truth":
            continue
        line = (
            f"  {r.label[:38]:<40} {_fmt_num(r.truth_value):>10} "
            f"{_fmt_num(r.actual_value):>10}   {_fmt_num(r.abs_error):>10}   "
            f"{_fmt_pct(r.pct_error):>8}   {r.truth_confidence[:5]:<5} {r.color}"
        )
        print(line)

    if per_room:
        print()
        print("  Per-room (contractor-validated rows):")
        print("  " + "─" * 92)
        for row in per_room:
            if row.get("missing"):
                print(f"    nr={row['nr']}: ⬛ room not in extract")
                continue
            color = {"ok": "🟢", "warn": "🟡", "fail": "🔴", "missing": "⬜"}[row["status"]]
            print(
                f"  nr={row['nr']:<4} {row.get('pavadinimas','')[:20]:<22} "
                f"{row['field']:<22} truth={row['truth']:>8.2f} "
                f"actual={row['actual']:>8.2f} Δ={row['abs_error']:>+7.2f} "
                f"({row['pct_error']:>+6.2f}%) {color}"
            )

    summary = _summarize(results)
    excluded = summary.get("excluded_incomplete_truth") or []
    if excluded:
        print()
        print("  ⬛ EXCLUDED from MAE — truth documented as incomplete/partial")
        print("  " + "─" * 92)
        for e in excluded:
            print(f"  {e['label'][:38]:<40} {_fmt_num(e['truth']):>10} "
                  f"{_fmt_num(e['actual']):>10}   {'':>10}   "
                  f"{_fmt_pct(e['pct_error']):>8}   {e['truth_confidence'][:11]:<11} "
                  f"[{e['tier']}]")
        print("    (these measure the truth's own documentation gap, not the "
              "extractor — see _summarize)")

    print()
    print("  ── Summary ────────────────────────────────────────────────────────────────")
    print(f"    Headline MAE %:        {summary['headline_mae_pct']:6.3f}%")
    print(f"    Headline max |error| %:{summary['headline_max_pct']:6.3f}%")
    print(f"    Headline rooms ok:     {summary['headline_ok']} / {summary['headline_total']}")
    print(f"    Category MAE %:        {summary['category_mae_pct']:6.3f}%")
    print("═" * 96)


def _incomplete_truth_rows(results: list[MetricResult]) -> list[MetricResult]:
    """Rows whose TRUTH is documented as incomplete/partial but which still
    produced a pct_error. Excluded from every MAE (see _summarize) and
    reported separately so the exclusion is never silent."""
    return [r for r in results
            if r.status == "no_truth" and r.pct_error is not None]


def _summarize(results: list[MetricResult]) -> dict:
    """Aggregate the scored metrics.

    2026-07-29 (romainiai): this used to select on ``pct_error is not None``
    alone, which silently re-admitted the rows ``_classify`` had already
    demoted to ``no_truth`` because their TRUTH carries
    ``confidence: incomplete|partial``. That contradicted _classify's own
    stated intent ("so they don't dominate the headline MAE") and — worse —
    ``print_report`` skips no_truth rows, so the biggest contributor to the
    number was invisible in the table above it.

    Concretely: romainiai read 112.947% headline MAE, of which 79% came from
    ``dazymo_walls_plus_ceilings_combined_m2`` (+178.18% against a truth its
    own truth.json annotates "AI will over-extract vs this number — flagged
    scope_mismatch in registry"). Nobody could reproduce the number from the
    printed report because that row was never printed. Selection now keys on
    status, and the excluded rows are printed as a footnote instead of
    vanishing."""
    scored = [r for r in results if r.pct_error is not None
              and r.status != "no_truth"]

    def _pct_values(tier: str) -> list[float]:
        # INFORMATIONAL_METRICS are printed but never averaged (2026-09-05).
        return [abs(r.pct_error) for r in scored
                if r.tier == tier and r.truth_key not in INFORMATIONAL_METRICS]

    head_pcts = _pct_values("headline")
    cat_pcts = _pct_values("category")
    head_ok = sum(1 for r in results if r.tier == "headline" and r.status == "ok")
    head_total = sum(1 for r in scored if r.tier == "headline")

    return {
        "headline_mae_pct": (sum(head_pcts) / len(head_pcts)) if head_pcts else 0.0,
        "headline_max_pct": max(head_pcts) if head_pcts else 0.0,
        "headline_ok": head_ok,
        "headline_total": head_total,
        "category_mae_pct": (sum(cat_pcts) / len(cat_pcts)) if cat_pcts else 0.0,
        "excluded_incomplete_truth": [
            {"truth_key": r.truth_key, "label": r.label, "tier": r.tier,
             "truth": r.truth_value, "actual": r.actual_value,
             "pct_error": r.pct_error, "truth_confidence": r.truth_confidence}
            for r in _incomplete_truth_rows(results)
        ],
    }


def _load_calibration_for_html(project_id: str) -> dict[str, float]:
    """Return {santrauka_key: calibrated_value} for the eval report.

    The calibrator stores per-metric ``factor = user_value / ai_value``.
    For each saved override, the eval HTML can render a "Calibrated"
    column showing what the user's target was.
    """
    calib_path = REPO_ROOT / "backend" / "data" / "calibrations" / f"{project_id}.json"
    if not calib_path.exists():
        return {}
    try:
        record = json.loads(calib_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    # Map calibrator metric keys → truth_key in the eval METRICS table
    KEY_MAP = {
        "angokrasciai_m":           "angokrasciai_m",
        "dazymo_plotas_m2":         "dazymo_walls_plus_ceilings_combined_m2",
        "dazymo_excl_garazas_m2":   "dazymo_walls_plus_ceilings_combined_m2",
        "plyteles_sienose_m2":      "plyteles_sienos_total_m2",
        "plyteles_grindyse_m2":     "plyteles_grindys_total_m2",
        "kampu_metrai_m":           "kampu_metrai_m",
        "gkp_lubu_iki_3m_m2":       "gkp_lubu_iki_3m_m2",
        "led_nisos_m":              "led_nisos_m",
    }
    out: dict[str, float] = {}
    for k, v in (record.get("overrides") or {}).items():
        if isinstance(v, (int, float)) and k in KEY_MAP:
            out[KEY_MAP[k]] = float(v)
    return out


def write_html_report(out_path: Path, project_id: str, mode: str,
                      results: list[MetricResult], per_room: list[dict],
                      summary: dict) -> None:
    calibrated_overrides = _load_calibration_for_html(project_id)
    rows_html = []
    for r in results:
        if r.status == "no_truth":
            continue
        calibrated = calibrated_overrides.get(r.truth_key)
        calibrated_cell = (
            f"<span class='calibrated'>{_fmt_num(calibrated)} {r.unit}</span>"
            if calibrated is not None else "<span class='muted'>—</span>"
        )
        rows_html.append(
            f"<tr class='row-{r.status}'>"
            f"<td>{r.label}</td>"
            f"<td class='num'>{_fmt_num(r.truth_value)} {r.unit}</td>"
            f"<td class='num'>{_fmt_num(r.actual_value)} {r.unit}</td>"
            f"<td class='num'>{calibrated_cell}</td>"
            f"<td class='num'>{_fmt_num(r.abs_error)}</td>"
            f"<td class='num'>{_fmt_pct(r.pct_error)}</td>"
            f"<td>{r.truth_confidence}</td>"
            f"<td>{r.color}</td>"
            f"</tr>"
        )

    per_room_html = ""
    if per_room:
        per_room_rows = []
        for row in per_room:
            if row.get("missing"):
                per_room_rows.append(f"<tr><td>{row['nr']}</td><td colspan=6>missing</td></tr>")
                continue
            per_room_rows.append(
                f"<tr class='row-{row['status']}'>"
                f"<td>{row['nr']}</td><td>{row.get('pavadinimas','')}</td>"
                f"<td>{row['field']}</td>"
                f"<td class='num'>{row['truth']:.2f}</td>"
                f"<td class='num'>{row['actual']:.2f}</td>"
                f"<td class='num'>{row['abs_error']:+.2f}</td>"
                f"<td class='num'>{row['pct_error']:+.2f}%</td>"
                f"</tr>"
            )
        per_room_html = (
            "<h3>Per-room (contractor-validated)</h3>"
            "<table><thead><tr><th>nr</th><th>room</th><th>field</th>"
            "<th>truth</th><th>actual</th><th>Δ</th><th>pct</th></tr></thead><tbody>"
            + "".join(per_room_rows) + "</tbody></table>"
        )

    html = f"""<!doctype html>
<html lang="lt"><head><meta charset="utf-8">
<title>Eval — {project_id} — {mode}</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 1080px; margin: 24px auto; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 24px; }}
  .summary {{ background: #f6f5f2; border-left: 4px solid #2a6fb5; padding: 12px 16px; margin: 16px 0 32px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-bottom: 24px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #eee; text-align: left; }}
  th {{ background: #fafafa; font-weight: 600; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  tr.row-ok    {{ background: rgba(72, 187, 120, 0.05); }}
  tr.row-warn  {{ background: rgba(237, 137, 54, 0.07); }}
  tr.row-fail  {{ background: rgba(229, 62, 62, 0.10); }}
  tr.row-missing {{ color: #999; }}
  .calibrated {{ color: #92400e; font-weight: 600; }}
  .muted {{ color: #cbd5e1; }}
</style>
</head><body>
<h1>Eval report — {project_id}</h1>
<div class="meta">mode={mode} &middot; generated {_dt.datetime.now().isoformat(timespec='seconds')}</div>
<div class="summary">
  Headline MAE: <b>{summary['headline_mae_pct']:.3f}%</b> &middot;
  Max headline |Δ|: <b>{summary['headline_max_pct']:.3f}%</b> &middot;
  Headline ok: <b>{summary['headline_ok']}/{summary['headline_total']}</b> &middot;
  Category MAE: <b>{summary['category_mae_pct']:.3f}%</b>
</div>
<h3>Headline + category metrics</h3>
<table>
  <thead><tr><th>metric</th><th>truth</th><th>AI</th><th>Calibrated</th><th>Δ (AI−truth)</th><th>pct</th><th>conf</th><th>status</th></tr></thead>
  <tbody>{''.join(rows_html)}</tbody>
</table>
{per_room_html}
</body></html>
"""
    out_path.write_text(html, encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────────────────────────
def _load_truth(project_id: str) -> dict:
    entry = REGISTRY.get(project_id)
    if not entry:
        raise SystemExit(f"Unknown project '{project_id}'. Known: {list(REGISTRY)}")
    path = REPO_ROOT / entry["truth_path"]
    with path.open() as f:
        return json.load(f)


def _append_drift_row(project_id: str, mode: str, summary: dict,
                       results: list[MetricResult]) -> None:
    """Append-only per-run snapshot for cross-commit drift detection.

    Format: one JSON object per line in eval_runs/drift.jsonl. Each row
    carries (timestamp, git_sha, project, mode, MAE, per-metric pct).
    Append-only — never edit or compact this file. To inspect drift,
    diff the last N rows or feed them to a notebook.
    """
    import subprocess
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sha = "unknown"
    row = {
        "ts": _dt.datetime.now().isoformat(timespec="seconds"),
        "git_sha": sha,
        "project_id": project_id,
        "mode": mode,
        "mae_pct": summary.get("mae_pct"),
        "metrics": {r.label: r.pct_error for r in results
                    if r.tier == "headline" and r.pct_error is not None},
    }
    drift_path = EVAL_RUNS_ROOT / "drift.jsonl"
    drift_path.parent.mkdir(parents=True, exist_ok=True)
    with drift_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  Drift logged → {drift_path}")


def _print_extraction_timeline(parsed: dict) -> None:
    """Print a per-step timeline derived from intermediate artefacts the
    extractor leaves on ``parsed``. Used by --verbose."""
    print("\n  ─── Extraction step timeline ───")
    meta = parsed.get("_meta") or {}
    steps: list[tuple[str, str, str]] = []  # (label, status, detail)
    # Vision pass 1
    if meta.get("page_count"):
        steps.append(("pdf→images", "OK",
                      f"{meta.get('page_count')} pages, "
                      f"{meta.get('vendor_pages_skipped', 0)} vendor-skipped"))
    if parsed.get("_eksplikacija"):
        eks = parsed["_eksplikacija"]
        src = eks.get("eksplikacija_source_page")
        n_rooms = len(eks.get("patalpos") or [])
        status = "OK" if n_rooms > 0 else "EMPTY"
        steps.append(("eksplikacija_reader", status,
                      f"src_page={src}, {n_rooms} rooms"))
    if parsed.get("_adjacency_applied"):
        adj = parsed["_adjacency_applied"]
        steps.append(("adjacency_extractor", "OK",
                      f"page={adj.get('page_used')}, "
                      f"matched={adj.get('summary', {}).get('n_rooms_matched')}, "
                      f"${adj.get('cost_usd', 0):.3f}"))
    if parsed.get("_height_fusion"):
        hf = parsed["_height_fusion"]
        steps.append(("height_fusion", "OK",
                      f"source={hf['result']['chosen_source']}, "
                      f"value={hf['result']['primary_m']}m, "
                      f"updated={hf.get('rooms_summary', {}).get('n_updated', 0)}"))
    if parsed.get("_elevation_pass"):
        ep = parsed["_elevation_pass"]
        steps.append(("wall_elevation", "OK",
                      f"pages={ep.get('pages')}, "
                      f"rooms_updated={ep.get('rooms_updated')}, "
                      f"${ep.get('cost_usd', 0):.3f}"))
    if parsed.get("_elevation_second_pass"):
        e2 = parsed["_elevation_second_pass"]
        steps.append(("elevation_second_pass", "OK",
                      f"repaired={e2.get('rooms_repaired')}, "
                      f"${e2.get('cost_usd', 0):.3f}"))
    if parsed.get("_ceiling_pass"):
        cp = parsed["_ceiling_pass"]
        steps.append(("ceiling_plan_niches", "OK",
                      f"pages={cp.get('pages_scanned')}, "
                      f"niches_added={cp.get('n_niches_added')}, "
                      f"${cp.get('cost_usd', 0):.3f}"))
    if parsed.get("_paint_above_tile_pass"):
        pat = parsed["_paint_above_tile_pass"]
        steps.append(("paint_above_tile", "OK",
                      f"flagged={len(pat.get('rooms_flagged') or [])} rooms"))
    if parsed.get("_perimeter_validation"):
        pv = parsed["_perimeter_validation"]
        steps.append(("perimeter_validator",
                      "OK" if pv.get("n_needs_reextraction", 0) == 0 else "FLAG",
                      f"{pv.get('n_pass')}/{pv.get('n_total')} pass, "
                      f"{pv.get('n_needs_reextraction')} need_reextraction"))
    if parsed.get("_consistency_checks"):
        cc = parsed["_consistency_checks"]
        steps.append(("consistency_checker",
                      "OK" if (cc.get("n_warn", 0) + cc.get("n_fail", 0)) == 0 else "WARN",
                      f"warn={cc.get('n_warn')}, fail={cc.get('n_fail')}"))
    warnings = parsed.get("warnings") or []
    if warnings:
        steps.append(("warnings", "INFO", f"{len(warnings)} warning(s) emitted"))
    if not steps:
        print("  (no intermediate step artefacts on parsed — extract_interior")
        print("   may not have populated _meta/_eksplikacija/etc.)")
        return
    name_w = max(len(s[0]) for s in steps)
    status_w = max(len(s[1]) for s in steps)
    for name, status, detail in steps:
        print(f"  · {name:<{name_w}}  [{status:<{status_w}}]  {detail}")
    print()


def run_debug_project(slug: str) -> int:
    """Run the AI extract pipeline on a single project and dump every
    intermediate data structure to a timestamped folder for inspection.

    Use this when debugging a project's accuracy — gives you all the
    intermediates (ai_extract, adjacency, height_fusion, consistency,
    eksplikacija, wall_elevations) without re-running Vision.
    """
    import shutil
    ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = EVAL_RUNS_ROOT / f"debug_{slug}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        print(f"  No ai_extract.json for slug={slug!r} — nothing to debug")
        return 2
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    # Dump top-level
    shutil.copy(ai_path, out_dir / "ai_extract.json")
    truth_path = REPO_ROOT / "ground_truth" / slug / "truth.json"
    if truth_path.exists():
        shutil.copy(truth_path, out_dir / "truth.json")

    # Pull each intermediate that's embedded in the extract
    intermediates = {
        "santrauka.json": ai.get("santrauka"),
        "patalpos.json": ai.get("patalpos"),
        "puslapiai.json": ai.get("puslapiai"),
        "_eksplikacija.json": ai.get("_eksplikacija"),
        "_wall_elevations.json": ai.get("_wall_elevations"),
        "_adjacency_applied.json": ai.get("_adjacency_applied"),
        "_height_fusion.json": ai.get("_height_fusion"),
        "_consistency_checks.json": ai.get("_consistency_checks"),
        "_perimeter_validation.json": ai.get("_perimeter_validation"),
        "_elevation_pass.json": ai.get("_elevation_pass"),
        "_elevation_second_pass.json": ai.get("_elevation_second_pass"),
        "_ceiling_pass.json": ai.get("_ceiling_pass"),
        "_paint_above_tile_pass.json": ai.get("_paint_above_tile_pass"),
        "_meta.json": ai.get("_meta"),
        "warnings.json": ai.get("warnings"),
    }
    for fname, data in intermediates.items():
        if data is None:
            continue
        (out_dir / fname).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Adjacency raw output (separate file)
    adj_path = REPO_ROOT / "ground_truth" / slug / "adjacency.json"
    if adj_path.exists():
        shutil.copy(adj_path, out_dir / "adjacency.json")

    # Run the analyzer on this single project for human-readable diff
    diff_lines = []
    diff_lines.append(f"DEBUG REPORT — {slug} @ {ts}\n")
    diff_lines.append(f"\nIntermediate files dumped:")
    written = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    for name in written:
        size = (out_dir / name).stat().st_size
        diff_lines.append(f"  {size:>8} B  {name}")
    diff_lines.append(f"\nai_extract top-level keys: {sorted(ai.keys())[:30]}")
    diff_lines.append(f"\nnumber of rooms: {len(ai.get('patalpos') or [])}")
    diff_lines.append(f"number of warnings: {len(ai.get('warnings') or [])}")
    diff_lines.append(f"number of pages: {len(ai.get('puslapiai') or [])}")
    if ai.get("_consistency_checks"):
        cc = ai["_consistency_checks"]
        diff_lines.append(f"\nconsistency: ok={cc.get('n_ok',0)} warn={cc.get('n_warn')} fail={cc.get('n_fail')}")
        for chk in cc.get("checks") or []:
            if chk.get("status") != "PASS":
                diff_lines.append(f"  [{chk['status']}] {chk['name']}: {chk['message']}")
    (out_dir / "DEBUG_REPORT.txt").write_text("\n".join(diff_lines), encoding="utf-8")
    print(f"  Debug dump → {out_dir.relative_to(REPO_ROOT)}")
    print(f"  {len(written)} files written; see DEBUG_REPORT.txt for index")
    return 0


def _extra_calls_breakdown(meta: dict) -> dict:
    """Per-sub-reader €/USD breakdown of ``meta["extra_calls"]`` for auditing.

    Each extra_call carries a ``reader`` tag (apdailos / doors / door_type /
    fixtures / zoom / eksplikacija / niche / …) set at its merge point — group
    by it so the run report can attribute the true-cost premium to the exact
    sub-Vision calls that drove it. Untagged calls fall into ``"unknown"``.
    Priced per-call at its OWN model (calc_claude_cost_usd), mirroring
    pricing.calc_extra_calls_cost_usd so the breakdown sums to the same total.
    The cache_ttl is left at the pricing default ("5m" since the 2026-07-28
    telemetry audit) precisely so this stays in lockstep — hard-coding "1h"
    here made the breakdown over-count cache writes by 60% relative to the
    total it was supposed to decompose.
    """
    from pricing import calc_claude_cost_usd, USD_TO_EUR  # backend/ on sys.path
    groups: dict[str, dict] = {}
    for c in (meta.get("extra_calls") or []):
        reader = c.get("reader") or "unknown"
        model = c.get("model") or ""
        usd = calc_claude_cost_usd(
            input_tokens=int(c.get("input_tokens") or 0),
            output_tokens=int(c.get("output_tokens") or 0),
            cache_read_tokens=int(c.get("cache_read_tokens") or 0),
            cache_write_tokens=int(c.get("cache_write_tokens") or 0),
            model=model,
        )
        g = groups.setdefault(reader, {"n_calls": 0, "cost_usd": 0.0,
                                       "models": set()})
        g["n_calls"] += 1
        g["cost_usd"] += usd
        if model:
            g["models"].add(model)
    return {
        reader: {
            "n_calls": g["n_calls"],
            "cost_usd": round(g["cost_usd"], 4),
            "cost_eur": round(g["cost_usd"] * USD_TO_EUR, 4),
            "models": sorted(g["models"]),
        }
        for reader, g in sorted(groups.items())
    }


def _meta_rollup(parsed: dict, wall_time_s: float,
                 model_requested: str | None) -> dict:
    """W1.2: per-project cost/token roll-up for the model benchmark.

    Reads the pipeline's ``_meta`` and prices the COMPLETE per-project cost via
    backend/pricing.py (model-aware): Pass-1 (or mixed-model voting rounds) PLUS
    every sub-Vision call captured in ``_meta["extra_calls"]`` (2026-07-04
    sub-call metering fix — apdailos/doors/door_type/fixtures/zoom/eksplikacija/
    niche). ``cost_eur`` is therefore the TRUE €/project, not Pass-1-only.

    ``cost_eur_pass1`` retains the Pass-1(+voting)-only cost so the run report
    can show the true/Pass-1 multiplier, and ``extra_calls_breakdown`` attributes
    the premium per sub-reader. ``raw_meta`` passes the whole _meta through
    (extra_calls included) so results.json stays fully auditable.
    """
    meta = (parsed.get("_meta") or {}) if isinstance(parsed, dict) else {}
    model = meta.get("model") or model_requested
    tokens = {
        "input_tokens": int(meta.get("input_tokens") or 0),
        "output_tokens": int(meta.get("output_tokens") or 0),
        "cache_read_tokens": int(meta.get("cache_read_tokens") or 0),
        "cache_write_tokens": int(meta.get("cache_write_tokens") or 0),
    }
    cost_usd = cost_eur = None
    cost_usd_pass1 = cost_eur_pass1 = None
    extra_calls_cost_eur = None
    extra_calls_breakdown: dict = {}
    pricing_note = None
    if model or meta.get("voting_models"):
        try:
            # calc_meta_cost_usd is mixed-model-voting AND sub-call aware
            # (2026-07-04): voting_models rounds price at their own model each;
            # extra_calls sub-Vision calls are summed ON TOP, also per-model.
            from pricing import calc_meta_cost_usd  # backend/ on sys.path
            # Pass-1(+voting)-only — deliberately WITHOUT extra_calls, for the
            # true/Pass-1 multiplier the pricing analysis reports.
            cost_usd_pass1 = round(calc_meta_cost_usd(
                {**tokens, "model": model,
                 "voting_models": meta.get("voting_models")}), 4)
            cost_eur_pass1 = round(cost_usd_pass1 * 0.93, 4)
            # TRUE per-project cost — pass the WHOLE _meta so extra_calls are
            # priced too (each sub-call at its own model). This is the number
            # db.record_usage ledgers in production.
            cost_usd = round(calc_meta_cost_usd(meta), 4)
            cost_eur = round(cost_usd * 0.93, 4)  # same USD→EUR as db.py
            extra_calls_cost_eur = round(cost_eur - cost_eur_pass1, 4)
            extra_calls_breakdown = _extra_calls_breakdown(meta)
        except Exception as exc:  # unknown model rate etc. — keep run scored
            pricing_note = f"cost unavailable: {exc}"
    return {
        "model": model,
        **tokens,
        "cost_usd": cost_usd,
        "cost_eur": cost_eur,
        "cost_usd_pass1": cost_usd_pass1,
        "cost_eur_pass1": cost_eur_pass1,
        "extra_calls_cost_eur": extra_calls_cost_eur,
        "extra_calls_breakdown": extra_calls_breakdown,
        "pricing_note": pricing_note,
        "wall_time_s": round(wall_time_s, 1),
        "raw_meta": meta,
    }


# ── Experiments (2026-07-04 accuracy deep-dive #5-7) ──────────────────────────
# Each experiment is an opt-in env var read by the pipeline at call time.
# _apply_experiment_env sets it BEFORE the (lazy) pipeline import in
# run_pipeline_vision, and returns a filesystem-safe tag for the run dir.
_EXPERIMENT_ENVS = ("SAMATU_PDF_NATIVE", "SAMATU_ZOOM_AGENTIC",
                    "SAMATU_VOTING_MODELS")


def _apply_experiment_env(spec: str) -> str:
    """Translate an --experiment spec into pipeline env vars.

    Specs:
      native-pdf          → SAMATU_PDF_NATIVE=1   (pass-1 document block)
      agentic-zoom        → SAMATU_ZOOM_AGENTIC=1 (model-driven crop loop)
      mixed-vote:<m1,m2>  → SAMATU_VOTING_MODELS=<m1,m2> (model per round)

    Returns the run-dir tag (eval_runs/<model-or-config>__<tag>/).
    """
    if spec == "native-pdf":
        os.environ["SAMATU_PDF_NATIVE"] = "1"
        return "native-pdf"
    if spec == "agentic-zoom":
        os.environ["SAMATU_ZOOM_AGENTIC"] = "1"
        return "agentic-zoom"
    if spec.startswith("mixed-vote:"):
        models = spec.split(":", 1)[1].strip()
        if not models or not [m for m in models.split(",") if m.strip()]:
            raise SystemExit(
                "--experiment mixed-vote needs a model list, e.g. "
                "--experiment mixed-vote:claude-fable-5,claude-fable-5,claude-opus-4-8")
        os.environ["SAMATU_VOTING_MODELS"] = models
        return "mixed-vote_" + models.replace(",", "+").replace(" ", "")
    raise SystemExit(
        f"unknown --experiment {spec!r} — expected native-pdf | agentic-zoom "
        f"| mixed-vote:<m1,m2,...>")


def run_one(project_id: str, mode: str, *, estimate_exterior: bool = False,
            apply_calibration: bool = False, track_drift: bool = False,
            verbose: bool = False, model: str | None = None,
            experiment: str | None = None) -> int:
    truth = _load_truth(project_id)
    entry = REGISTRY[project_id]

    calibration = _load_project_calibration(project_id) if apply_calibration else None

    import time as _time
    t0 = _time.monotonic()
    if mode == "use_gt_inputs":
        parsed = run_pipeline_use_gt_inputs(
            truth,
            estimate_exterior=estimate_exterior,
            apply_calibration=calibration,
        )
    elif mode == "replay":
        parsed = run_pipeline_replay(REPO_ROOT / entry["replay_path"])
    elif mode == "vision":
        parsed = run_pipeline_vision(REPO_ROOT / entry["pdf_path"])
    else:
        raise SystemExit(f"Unknown mode {mode!r}")
    wall_time_s = _time.monotonic() - t0

    if verbose:
        _print_extraction_timeline(parsed)

    results = evaluate(parsed, truth)
    per_room = evaluate_per_room(parsed, truth)
    summary = _summarize(results)
    print_report(project_id, mode, results, per_room)

    meta_rollup = _meta_rollup(parsed, wall_time_s, model)

    ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # W1.2: benchmark runs (--model) are namespaced per model so Opus and
    # Fable runs can never overwrite or be confused with each other.
    # Experiments (2026-07-04) are additionally tagged:
    # eval_runs/<model-or-config>__<experiment>/ — an experiment run can
    # never be confused with a baseline run of the same model.
    if experiment:
        base_dir = EVAL_RUNS_ROOT / f"{model or 'default-config'}__{experiment}"
    elif model:
        base_dir = EVAL_RUNS_ROOT / model
    else:
        base_dir = EVAL_RUNS_ROOT
    run_dir = base_dir / f"{ts}_{project_id}_{mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
    (run_dir / "results.json").write_text(json.dumps({
        "project": project_id,
        "mode": mode,
        "model": meta_rollup["model"],
        "experiment": experiment,
        "summary": summary,
        "meta_rollup": meta_rollup,
        "metrics": [r.__dict__ for r in results],
        "per_room": per_room,
    }, ensure_ascii=False, indent=2))
    write_html_report(run_dir / "report.html", project_id, mode, results, per_room, summary)
    print(f"\n  Report → {run_dir / 'report.html'}")

    if track_drift:
        _append_drift_row(project_id, mode, summary, results)

    # Exit code: 1 if any headline metric is "fail", 0 otherwise.
    failing = [r for r in results if r.tier == "headline" and r.status == "fail"]
    return 1 if failing else 0


def _print_collapsed_footnote(per_project_summary: list[dict]) -> None:
    """Loudly list any FRESH-production (ai_extract) headline metrics that
    collapsed to 0.0 against a real >0 truth. These ARE counted in the MAE
    (as ~-100% fails) but a single dilution-resistant average can still bury
    a total collapse, so we name them explicitly. Without this, a non-objektas_a
    project silently emitting 0 for combined paint would vanish from the
    honest score (the old behaviour this replaces)."""
    flagged = [(s["slug"], s.get("metrics_collapsed") or [])
               for s in per_project_summary
               if s.get("status") == "ok" and (s.get("metrics_collapsed"))]
    if not flagged:
        return
    print(f"\n  ⚠ COLLAPSED METRICS (fresh production emitted 0.0 vs a real "
          f">0 truth — counted as -100% fails, NOT hidden):")
    for slug, labels in flagged:
        for lab in labels:
            print(f"      🔴 {slug}: {lab}")


def _print_summary_table(per_project_summary: list[dict], overall_mae) -> None:
    """Compact 5-line table — the default for multi-project mode.

    Columns: Project | Combined Paint | Walls | Ceilings | MAE
    Where Combined Paint / Walls / Ceilings are signed % error vs truth
    and MAE is the mean absolute % error across the project's scored
    metrics. Skipped/blocked projects show '—' in every numeric column.
    """
    def _metric(s: dict, label_starts_with: str):
        for m in s.get("metrics", []):
            if (m.get("label") or "").startswith(label_starts_with):
                return m.get("pct_error")
        return None

    def _fmt(v):
        return "—" if v is None else f"{v:+.2f}%"

    print(f"\n  {'Project':<14} {'Combined(info)':>15} {'Walls':>9} {'Ceilings':>10} {'MAE':>8}  {'engine':<9}")
    print("  " + "─" * 71)
    for s in per_project_summary:
        if s.get("status") != "ok":
            print(f"  {s['slug']:<14} {'—':>15} {'—':>9} {'—':>10} {'—':>8}  {'—':<9}")
            continue
        combined = _metric(s, "Dažymo plotas")
        walls    = _metric(s, "Sienų dažomas plotas")
        ceiling  = _metric(s, "Lubų dažomas plotas")
        mae      = s.get("mae_pct")
        # "live" = deterministic tail re-run against today's formulas.
        # "FROZEN" = the saved extract's own numbers, however old they are —
        # shouted, because a frozen row can neither show a fix nor catch a
        # regression (see run_totals_only_multi's docstring).
        engine = "live" if s.get("recomputed") else "FROZEN"
        # Out-of-sample rows are scored like the rest but wear a tag and stay
        # out of the Average below (see run_totals_only_multi).
        if s.get("out_of_sample"):
            engine += " OOS"
        print(f"  {s['slug']:<14} {_fmt(combined):>15} {_fmt(walls):>9} "
              f"{_fmt(ceiling):>10} "
              f"{('—' if mae is None else f'{mae:.2f}%'):>8}  {engine:<9}")
    print("  " + "─" * 71)
    avg_line = "—" if overall_mae is None else f"{overall_mae:.2f}%"
    print(f"  {'Average':<14} {'':>15} {'':>9} {'':>10} {avg_line:>8}  (in-sample; OOS rows excluded)")
    # The generalisation number, from the same metric observations, never
    # blended with the line above.
    oos = [(s["mae_pct"], s.get("metrics_scored") or 0) for s in per_project_summary
           if s.get("out_of_sample") and s.get("status") == "ok" and s.get("mae_pct") is not None]
    n_oos = sum(n for _, n in oos)
    if n_oos:
        slugs = ", ".join(s["slug"] for s in per_project_summary if s.get("out_of_sample"))
        pooled = sum(m * n for m, n in oos) / n_oos      # same pooling as the corpus MAE
        print(f"  {'Out-of-sample':<14} {'':>15} {'':>9} {'':>10} {pooled:>7.2f}%  "
              f"(n={n_oos} obs. on {slugs}; never tuned on)")
    if any(s.get("status") == "ok" and not s.get("recomputed")
           for s in per_project_summary):
        print("\n  ⚠ FROZEN rows score the numbers saved in ai_extract.json, not "
              "today's engine.\n    Re-run with --recompute for the live "
              "figures (still zero API spend).")


def _partition_headline_metrics(results, ai_mode):
    """Split headline MetricResults into (scored, not_emitted, collapsed).

    Zero-vs-truth handling — DIFFERENT meaning per AI side (2026-06-09):

      • ai_mode == "replay" (legacy cached santrauka): a 0.0 against a >0
        truth genuinely means "this cached santrauka schema never tracked the
        field". A documentation gap, not a wrong answer — EXCLUDE from MAE,
        surface as not_emitted.

      • ai_mode == "ai_extract" (FRESH production output from
        scripts/regenerate_truth_extracts.py): a 0.0 against a >0 truth is a
        REAL metric collapse — production actually produced zero where the
        contractor measured something. SCORE it (lands as a ~-100% fail) AND
        flag it in `collapsed` so it can never hide behind the project
        average. Silently dropping it (the old behaviour) would let a
        non-objektas_a project's collapsed headline metric vanish from the honest
        MAE — see docs/superpowers/research/2026-06-09-benchmark-honesty-regen.md.

    Any other ai_mode (e.g. use_gt_inputs) scores everything as-is.
    """
    scored, not_emitted, collapsed = [], [], []
    for r in results:
        if r.tier != "headline" or r.pct_error is None:
            continue
        # Same rule as _summarize: a truth marked incomplete/partial cannot
        # measure the extractor, so it never enters an MAE. (No project in
        # the current registry has an incomplete HEADLINE truth, so this is
        # a guard against the next one, not a number change today.)
        if r.status == "no_truth":
            continue
        is_zero_vs_truth = (r.actual_value == 0.0
                            and r.truth_value and r.truth_value > 0.5)
        if is_zero_vs_truth and ai_mode == "replay":
            not_emitted.append(r.label)
            continue
        if is_zero_vs_truth and ai_mode == "ai_extract":
            collapsed.append(r.label)   # keep in `scored` — counts as a real fail
        scored.append(r)
    return scored, not_emitted, collapsed


def run_totals_only_multi(registry_path: Path, *, detailed: bool = False,
                          recompute: bool = False) -> int:
    """Iterate every project in ground_truth/registry.yaml and run the
    AI-vs-truth diff on its gt_totals block (no per-room work).

    A project contributes to the aggregate MAE only when an AI extract
    is available — either via REGISTRY[project_id].replay_path (cached)
    or by feeding gt_dimensions through the calculator. Projects with
    neither are reported as 'no_ai_side' so the gap is explicit.

    ⚠ FROZEN vs RECOMPUTED (2026-07-29). The ai_extract / replay branches
    load a saved JSON **verbatim** — ``run_pipeline_replay`` is a
    ``json.load``, nothing more. So the default run scores the numbers that
    were frozen into that file on the day it was written, NOT what today's
    formula code would produce. A formula fix landed an hour ago is invisible
    here, and an engine REGRESSION cannot be detected at all — the totals
    would sit there unchanged while production broke.

    That bit for real: on 2026-07-29 this table still reported objektas_b
    ceilings at +56.44% after the unfinished-ceiling gate had already pulled
    it to +25.71%, and the stale corpus average (13.97%) was ~8 pp worse than
    the truth. Pass ``--recompute`` to re-run the deterministic tail on the
    saved Vision reads — same zero-API cost, but it measures the CURRENT
    engine. The per-project mode is printed in the table so a frozen number
    can never again be mistaken for a live one.

    Output: a compact 5-line table by default (one row per project with
    combined paint / walls / ceilings / MAE percentages). Pass
    ``detailed=True`` to print the legacy 5-column per-project table.
    """
    import yaml

    reg = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    projects = reg.get("projects") or []
    if not projects:
        print(f"  registry has no projects: {registry_path}")
        return 2

    per_project_summary: list[dict] = []
    all_pct_errors: list[float] = []
    # Row scorecard, collected alongside the headline metrics off the SAME
    # `parsed` dicts (read-only) so both numbers describe one engine and the
    # recompute is not paid for twice.
    rows_scored: list[tuple[str, Any]] = []
    rows_excluded: list[tuple[str, Any, str]] = []

    ts = _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = EVAL_RUNS_ROOT / f"{ts}_multi_totals_only"
    run_dir.mkdir(parents=True, exist_ok=True)

    # OUT-OF-SAMPLE (2026-09-05): projects the engine was never tuned on. They
    # are scored exactly like the others but their errors never enter the
    # corpus mean — that mean is the in-sample number a rule change is gated
    # on, and folding a fresh project into it would let one bad new PDF look
    # like a regression of the fix and one lucky one hide a real regression.
    # Their own mean is printed as a separate line: the generalisation number.
    oos_pct_errors: list[float] = []
    oos_slugs: list[str] = []
    for entry in projects:
        slug = entry["slug"]
        # Per-registry exclusions: scope_mismatch, blocked_for_vision_extraction,
        # blocked_partial_input projects are visible but NOT included in MAE.
        if entry.get("scope_mismatch"):
            per_project_summary.append({
                "slug": slug, "status": "excluded_scope_mismatch",
                "reason": (entry.get("scope_mismatch_reason") or
                           "scope mismatch documented in registry"),
                "metrics": [], "excluded_from_mae": True,
            })
            continue
        if entry.get("blocked_for_vision_extraction"):
            per_project_summary.append({
                "slug": slug, "status": "excluded_blocked",
                "reason": entry.get("blocked_reason") or "missing input PDF",
                "metrics": [], "excluded_from_mae": True,
            })
            continue
        if entry.get("blocked_partial_input"):
            per_project_summary.append({
                "slug": slug, "status": "excluded_partial_input",
                "reason": (entry.get("blocked_reason") or
                           "input PDF lacks required pages"),
                "metrics": [], "excluded_from_mae": True,
            })
            continue
        # ABLATIONS (2026-08-22): synthetic variants of a corpus project that
        # share its truth file. Scored individually (--project X --vision),
        # never averaged — four Objektas A variants would quadruple its weight and
        # turn the corpus MAE into an Objektas A MAE.
        if entry.get("ablation_of"):
            per_project_summary.append({
                "slug": slug, "status": "excluded_ablation",
                "reason": f"ablation of {entry['ablation_of']} — scored individually",
                "metrics": [], "excluded_from_mae": True,
            })
            continue
        truth_path = REPO_ROOT / entry["truth_path"]
        if not truth_path.exists():
            per_project_summary.append({
                "slug": slug, "status": "missing_truth", "reason": str(truth_path),
                "metrics": [],
            })
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))

        # Pick the cheapest available AI side. Order of preference:
        #   1. ground_truth/<slug>/ai_extract.json — fresh production-pipeline
        #      output from scripts/run_vision_on_truth_set.py
        #   2. REGISTRY[slug].replay_path — legacy cached extract
        #   3. gt_dimensions feed through --use-gt-inputs
        parsed = None
        ai_mode = None
        fresh_extract = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
        if fresh_extract.exists():
            parsed = run_pipeline_replay(fresh_extract)
            ai_mode = "ai_extract"
        elif slug in REGISTRY and "replay_path" in REGISTRY[slug]:
            replay_path = REPO_ROOT / REGISTRY[slug]["replay_path"]
            if replay_path.exists():
                parsed = run_pipeline_replay(replay_path)
                ai_mode = "replay"
        # Both replay branches loaded frozen JSON. Re-run the deterministic
        # tail so the score reflects TODAY's formulas (see the docstring's
        # frozen-vs-recomputed warning). use_gt_inputs below already runs the
        # live engine, so it needs no such pass.
        #
        # ai_mode is deliberately NOT suffixed here: _partition_headline_metrics
        # dispatches on `ai_mode == "ai_extract"` / `== "replay"` by exact
        # equality to decide whether a 0.0-vs-truth is a real collapse or a
        # schema gap. Appending "+recomputed" would match neither branch and
        # silently stop flagging collapsed headline metrics. Recompute changes
        # the FORMULAS applied, not the provenance of the Vision reads, so the
        # provenance string must stay untouched.
        recomputed = False
        if parsed is not None and recompute:
            print(f"  ↻ {slug}: recomputing deterministic tail")
            parsed = _rerun_deterministic_tail(parsed, slug)
            recomputed = True
        if parsed is None and truth.get("gt_dimensions"):
            parsed = run_pipeline_use_gt_inputs(truth)
            ai_mode = "use_gt_inputs"

        if parsed is None:
            per_project_summary.append({
                "slug": slug,
                "status": "no_ai_side",
                "reason": ("no cached extract AND no gt_dimensions — "
                           "Vision spend required before this project can score"),
                "metrics": [],
            })
            continue

        results = evaluate(parsed, truth)
        scored, not_emitted, collapsed = _partition_headline_metrics(results, ai_mode)
        # Printed, not pooled — see INFORMATIONAL_METRICS.
        pooled = [r for r in scored if r.truth_key not in INFORMATIONAL_METRICS]
        mae = (sum(abs(r.pct_error) for r in pooled) / len(pooled)
               if pooled else None)
        worst = max((abs(r.pct_error) for r in pooled), default=None)
        per_project_summary.append({
            "slug": slug,
            "name": entry.get("name", slug),
            "status": "ok",
            "ai_mode": ai_mode,
            "recomputed": recomputed,
            "metrics_scored": len(pooled),
            "metrics_not_emitted": not_emitted,
            "metrics_collapsed": collapsed,
            "mae_pct": round(mae, 3) if mae is not None else None,
            "worst_pct": round(worst, 3) if worst is not None else None,
            "metrics": [
                {"label": r.label, "truth": r.truth_value,
                 "actual": r.actual_value, "pct_error": r.pct_error,
                 "status": r.status}
                for r in scored
            ],
        })
        if entry.get("out_of_sample"):
            per_project_summary[-1]["out_of_sample"] = True
            per_project_summary[-1]["excluded_from_mae"] = True
            oos_slugs.append(slug)
            for r in pooled:
                oos_pct_errors.append(abs(r.pct_error))
        else:
            for r in pooled:
                all_pct_errors.append(abs(r.pct_error))

        # Read-only second instrument on the same `parsed`. It cannot move the
        # headline numbers above (already computed) and it never rebuilds rows.
        sc = _score_rows_of(parsed, slug)
        if sc is not None:
            per_project_summary[-1]["row_scorecard"] = sc.as_dict()
            if entry.get("out_of_sample"):
                rows_excluded.append((slug, sc, "OUT-OF-SAMPLE — not in the mean"))
            elif slug != ROW_SCORECARD_HOLDOUT:
                rows_scored.append((slug, sc))
            else:
                rows_excluded.append((slug, sc, "HOLDOUT"))

    # Projects the headline table skipped: named with their reason (outside the
    # mean) so a registry exclusion never silently hides a whole sąmata.
    # Not re-scored here — `--rows` does that; this block must not add a second
    # recompute pass to the default run.
    _EXCL_NOTE = {
        "excluded_scope_mismatch": "registry: scope mismatch — see --rows",
        "excluded_blocked": "registry: blocked",
        "excluded_partial_input": "registry: partial input",
        "excluded_ablation": "ablation",
        "missing_truth": "no truth",
        "no_ai_side": "no extract",
    }
    for s in per_project_summary:
        if s.get("status") == "ok" or _contractor_samata(s["slug"]) is None:
            continue
        note = _EXCL_NOTE.get(s["status"], s["status"])
        if s["slug"] == ROW_SCORECARD_HOLDOUT:
            note = f"HOLDOUT — {note}"
        rows_excluded.append((s["slug"], None, note))

    overall_mae = (sum(all_pct_errors) / len(all_pct_errors)
                   if all_pct_errors else None)
    oos_mae = (sum(oos_pct_errors) / len(oos_pct_errors)
               if oos_pct_errors else None)
    baseline = {
        "ts": ts,
        "registry": str(registry_path.relative_to(REPO_ROOT)),
        "overall_mae_pct": round(overall_mae, 3) if overall_mae is not None else None,
        "n_metric_observations": len(all_pct_errors),
        # The generalisation number — never blended with the line above.
        "out_of_sample_mae_pct": round(oos_mae, 3) if oos_mae is not None else None,
        "out_of_sample_projects": oos_slugs,
        "n_out_of_sample_observations": len(oos_pct_errors),
        # The contractor-facing number, alongside (never instead of) the MAE.
        "rows_within_10_share_mean": (
            round(sum(sc.within_10_share for _, sc in rows_scored)
                  / len(rows_scored), 2) if rows_scored else None),
        "rows_holdout": ROW_SCORECARD_HOLDOUT,
        "projects": per_project_summary,
    }
    out_json = run_dir / "baseline_multi.json"
    out_json.write_text(json.dumps(baseline, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    if detailed:
        print(f"\n  Cross-project totals-only baseline — {len(projects)} project(s)")
        print(f"  {'slug':<14} {'AI side':<14} {'scored':>7} {'MAE %':>9} {'worst %':>10}")
        print("  " + "─" * 60)
        for s in per_project_summary:
            if s["status"] != "ok":
                print(f"  {s['slug']:<14} {s['status']:<14} {'—':>7} {'—':>9} {'—':>10}")
                continue
            print(f"  {s['slug']:<14} {s['ai_mode']:<14} {s['metrics_scored']:>7} "
                  f"{s['mae_pct']:>8.3f} {s['worst_pct']:>9.3f}")
        print(f"\n  overall MAE: {overall_mae if overall_mae is None else f'{overall_mae:.3f}%'}  "
              f"(n={len(all_pct_errors)} metric observations)")
        if oos_slugs:
            print(f"  OUT-OF-SAMPLE MAE: {oos_mae if oos_mae is None else f'{oos_mae:.3f}%'}  "
                  f"(n={len(oos_pct_errors)} observations on {', '.join(oos_slugs)} — "
                  f"never in the corpus mean)")
        _print_collapsed_footnote(per_project_summary)
        _print_rows_block(rows_scored, rows_excluded, recomputed=recompute)
        print(f"  Saved → {out_json}")
    else:
        _print_summary_table(per_project_summary, overall_mae)
        _print_collapsed_footnote(per_project_summary)
        _print_rows_block(rows_scored, rows_excluded, recomputed=recompute)
        print(f"  Saved → {out_json}")

    # Exit 1 only if at least one OK project broke the 2.0% per-project cap.
    breached = [s for s in per_project_summary
                if s["status"] == "ok" and (s.get("worst_pct") or 0) > 2.0]
    return 1 if breached else 0


def _infer_slug_from_run_name(name: str) -> str | None:
    """Infer the project slug from a run-dir name like
    ``2026-07-03_11-16-18_objektas_a_vision``. Longest slug wins so future
    slugs that contain another slug as a substring can't mis-match."""
    hits = [slug for slug in REGISTRY if f"_{slug}_" in f"_{name}_"]
    return max(hits, key=len) if hits else None


GEOMETRY_LANE = False        # set by --geometry


def _rerun_deterministic_tail(parsed: dict, slug: str | None = None) -> dict:
    """Re-run the deterministic (zero-API) tail of the pipeline on a saved
    extract's primitives:

      1. positioned ceiling-altitude markers → per-room heights (needs the
         source PDF; skipped when it is not on disk),
      2. height salvage from warnings[] (same gate as production — only when
         the model structured no per-room heights),
      3. height plausibility gate,
      4. per-room recompute (calc_room_quantities via primitives),
      5. santrauka recompute,
      6. pozicijos rebuild.

    This is exactly what a saved run would produce under the CURRENT
    formula code — the honest way to measure formula fixes against
    already-paid-for Vision reads without any API spend."""
    vc = importlib.import_module("extractor.vision_call")
    rooms = parsed.get("patalpos") or []

    # Step 1 reads the text layer of the ceiling plan, so unlike the rest of
    # the tail it needs the source PDF. The fixture PDFs are untracked (client
    # names + pricing), so a checkout without them must still rescore — it
    # just measures the other steps. Silence here would be dishonest, so the
    # skip is printed.
    pdf_rel = (REGISTRY.get(slug) or {}).get("pdf_path") if slug else None
    if pdf_rel:
        pdf_path = REPO_ROOT / pdf_rel
        if pdf_path.exists():
            try:
                from extractor.height_markers import (
                    apply_positioned_marker_heights)
                parsed = apply_positioned_marker_heights(
                    parsed, pdf_path.read_bytes())
                lane = parsed.get("_height_marker_lane") or {}
                if lane.get("ok"):
                    ch = lane.get("changed") or []
                    print(f"  ⤴ height markers ({lane.get('method')}): "
                          f"{len(ch)} raised, {len(lane.get('confirmed') or [])} "
                          f"confirmed" + (f" — {ch}" if ch else ""))
                elif lane:
                    print(f"  · height-marker lane inactive: {lane.get('reason')}")
            except Exception as exc:
                print(f"  ⚠ height-marker lane failed during rescore: {exc}")
            # Same contract for the symbol-legend scan (2026-07-29): it reads
            # the text layer only, runs in production right after the marker
            # lane, and gates un-anchored symbol counts in the pozicijos
            # rebuild below. Mirrored here so the free rescore measures the
            # same pipeline production runs.
            try:
                from extractor.symbol_legend import scan_symbol_legend
                parsed["_symbol_legend"] = scan_symbol_legend(
                    pdf_path.read_bytes())
                leg = parsed["_symbol_legend"]
                print(f"  ⤴ symbol legend: text_layer_ok="
                      f"{leg.get('text_layer_ok')} difuzoriai_defined="
                      f"{(leg.get('difuzoriai') or {}).get('defined')}")
            except Exception as exc:
                print(f"  ⚠ symbol-legend scan failed during rescore: {exc}")
            # The geometry lane (2026-09-19, Step 2.44d in production): room
            # outlines from the vector walls and perimeters ADDED from the
            # plan's dimension strings. Zero API, needs the PDF. Behind
            # --geometry so a run can be scored with and without it.
            if GEOMETRY_LANE:
                try:
                    from extractor.geometry_lane import apply_geometry
                    g = apply_geometry(parsed, pdf_path.read_bytes())
                    print(f"  ⤴ geometry lane: {g.get('status')} — kontūrai {g.get('konturai')}, "
                          f"atviros erdvės {g.get('atviros_erdves')}, perimetrai sudėti "
                          f"{g.get('perimetrai_sudeti')}, tušti su įverčiu {g.get('perimetrai_tusti')} "
                          f"({g.get('seconds')} s)")
                except Exception as exc:
                    print(f"  ⚠ geometry lane failed during rescore: {exc}")
            # The drawing's door schedule (2026-09-23, Step 2.43 in production): frame type and the
            # door list's reconciliation with the table. Zero API, needs the PDF; a cache written
            # before the scan existed gets it here, the way production's free re-read gives it.
            if "_duru_ziniarastis" not in parsed:
                try:
                    from extractor.door_schedule import scan_door_schedule
                    parsed["_duru_ziniarastis"] = scan_door_schedule(pdf_path.read_bytes())
                    print(f"  ⤴ durų žiniaraštis: {parsed['_duru_ziniarastis'].get('status')} — "
                          f"{parsed['_duru_ziniarastis'].get('sakinys')}")
                except Exception as exc:
                    print(f"  ⚠ door schedule scan failed during rescore: {exc}")
        else:
            print(f"  · height-marker lane skipped: {pdf_rel} not on disk")

    if rooms and not (parsed.get("lubu_auksciai") or {}):
        from extractor.height_markers import salvage_heights_from_warnings
        salvaged = salvage_heights_from_warnings(parsed.get("warnings") or [], rooms)
        for r in rooms:
            h = salvaged.get(r.get("pavadinimas"))
            if h is None:
                continue
            old = float(r.get("lubu_aukstis_m") or 0)
            # Upward-only, same spirit as production's asymmetric guard:
            # salvage exists because "Vision saw a non-default height".
            if h > old:
                r["lubu_aukstis_m"] = float(h)
                r["lubu_aukstis_saltinis"] = "warning_salvage_rescore"

    try:
        from extractor.universal_rules import apply_height_plausibility_gate
        apply_height_plausibility_gate(rooms)
    except Exception as exc:
        print(f"  ⚠ plausibility gate failed during rescore: {exc}")

    parsed = vc._recompute_per_room_via_python(parsed, _harness_rules_override(parsed))
    parsed = vc._recompute_santrauka(parsed)
    parsed = vc._build_pozicijos_from_rooms(parsed)
    return parsed


# ── Row-level scorecard (2026-09-04) ──────────────────────────────────────────
# The headline table above scores ~22 aggregated metrics. The contractor judges
# every billed row in HIS vocabulary. `backend/extractor/row_scorecard.py` is
# that second instrument; everything here is presentation + which projects count.
#
# `sernu` is the HOLDOUT: its sąmata is parsed but never averaged in, so the
# four-week target can be claimed on a project the work was not tuned against.
ROW_SCORECARD_HOLDOUT = "sernu"


def _contractor_samata(slug: str) -> list[dict] | None:
    # The PRICED parse (gitignored — his unit prices never enter the repo) wins
    # when present: same rows, plus `prices`, which turns the count-weighted
    # scorecard into a €-weighted one. The tracked price-free file is the
    # fallback, so the metric always exists.
    priced = GROUND_TRUTH_ROOT / slug / "contractor_samata_priced.json"
    path = priced if priced.exists() else GROUND_TRUTH_ROOT / slug / "contractor_samata_parsed.json"
    if not path.exists():
        return None
    return (json.loads(path.read_text(encoding="utf-8")).get("line_items")
            or [])


def _score_rows_of(parsed: dict, slug: str):
    """Score one already-built extract. READ-ONLY over `parsed` — it must never
    rebuild pozicijos, or the headline metrics scored from the same dict could
    move. Returns a `Scorecard`, or None when either side is unavailable."""
    items = _contractor_samata(slug)
    if not items:
        return None
    app_rows = parsed.get("pozicijos") or parsed.get("darbu_sarasas") or []
    if not app_rows:
        return None
    from extractor.row_scorecard import score_rows
    return score_rows(items, app_rows)


def _rows_for_slug(slug: str, *, recompute: bool):
    """Load `ground_truth/<slug>/ai_extract.json` and score it through the SAME
    recompute path the headline table uses, so both numbers describe one engine.

    Returns (scorecard, status) where status is None on success or a short
    reason string ('no extract', 'no sąmata', 'no rows')."""
    if _contractor_samata(slug) is None:
        return None, "no sąmata"
    extract = GROUND_TRUTH_ROOT / slug / "ai_extract.json"
    if not extract.exists():
        return None, "no extract"
    parsed = run_pipeline_replay(extract)
    if recompute:
        parsed = _rerun_deterministic_tail(parsed, slug)
    sc = _score_rows_of(parsed, slug)
    return (sc, None) if sc is not None else (None, "no rows")


def _rows_row(slug: str, sc, note: str = "") -> str:
    b = sc.buckets
    eur = sc.eur_within_10_share
    eur_s = f"{eur:>7.1f}%" if eur is not None else f"{'—':>8}"
    return (f"  {slug:<14} {sc.n_scored:>5} "
            f"{sc.within_10_share:>8.1f}% {eur_s} {b['within_25']:>8} {b['way_off']:>8} "
            f"{b['missing']:>8} {b['unmapped']:>9}  {note}")


def _print_rows_block(scored: list[tuple[str, Any]],
                      extra: list[tuple[str, Any, str]],
                      *, recomputed: bool) -> None:
    """Compact per-project row scorecard + the corpus mean of the ±10 % share.

    `scored` — (slug, Scorecard) pairs that COUNT toward the mean.
    `extra`  — (slug, Scorecard|None, note) reported but never averaged.
    """
    if not scored and not extra:
        return
    print(f"\n  Rangovo eilutės — kiek JO eilučių atkartojame "
          f"({'live' if recomputed else 'FROZEN'} engine)")
    print(f"  {'Project':<14} {'rows':>5} {'within10':>9} {'€±10':>8} {'within25':>8} "
          f"{'way_off':>8} {'missing':>8} {'unmapped':>9}")
    print("  " + "─" * 80)
    for slug, sc in scored:
        print(_rows_row(slug, sc))
    for slug, sc, note in extra:
        if sc is None:
            print(f"  {slug:<14} {'—':>5} {'—':>9} {'—':>8} {'—':>8} {'—':>8} "
                  f"{'—':>8} {'—':>9}  {note}")
        else:
            print(_rows_row(slug, sc, note))
    print("  " + "─" * 80)
    if scored:
        mean = sum(sc.within_10_share for _, sc in scored) / len(scored)
        eurs = [sc.eur_within_10_share for _, sc in scored if sc.eur_within_10_share is not None]
        eur_mean = f"{sum(eurs) / len(eurs):>7.1f}%" if len(eurs) == len(scored) else f"{'—':>8}"
        print(f"  {'Corpus mean':<14} {'':>5} {mean:>8.1f}% {eur_mean}   "
              f"(n={len(scored)} projects; {ROW_SCORECARD_HOLDOUT} held out; "
              f"€ column needs the priced parse — gitignored, present on {len(eurs)}/{len(scored)})")
    gran = sum(sc.granularity_rows for _, sc in scored)
    if gran:
        print(f"\n  · {gran} row(s) are `missing` only because he bills the "
              f"family on more rows than we emit —\n    the family total is "
              f"scored separately (see --rows for the per-family view).")


def run_rows_scorecard(registry_path: Path, *, recompute: bool = False,
                       detailed: bool = False) -> int:
    """`--rows`: score every cached extract against the contractor's own sąmata,
    row by row, through the frozen concept table. Zero API spend.

    This is the contractor-facing accuracy number. The headline MAE says how
    close ~22 aggregated totals are; this says how many of the rows he actually
    bills he could find in our list with a number he can accept.
    """
    import yaml

    reg = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    scored: list[tuple[str, Any]] = []
    extra: list[tuple[str, Any, str]] = []
    details: list[tuple[str, Any]] = []
    for entry in reg.get("projects") or []:
        slug = entry["slug"]
        if _contractor_samata(slug) is None:
            continue
        if recompute and (GROUND_TRUTH_ROOT / slug / "ai_extract.json").exists():
            print(f"  ↻ {slug}: recomputing deterministic tail")
        sc, status = _rows_for_slug(slug, recompute=recompute)
        if sc is None:
            extra.append((slug, None, status or "no rows"))
            continue
        details.append((slug, sc))
        note = ""
        if slug == ROW_SCORECARD_HOLDOUT:
            note = "HOLDOUT — never in the mean"
        elif entry.get("out_of_sample"):
            note = "OUT-OF-SAMPLE — not in the mean"
        elif entry.get("scope_mismatch"):
            note = "registry: scope mismatch — not in the mean"
        elif entry.get("blocked_for_vision_extraction") or entry.get(
                "blocked_partial_input") or entry.get("ablation_of"):
            note = "registry-excluded — not in the mean"
        (extra.append((slug, sc, note)) if note else scored.append((slug, sc)))

    _print_rows_block(scored, extra, recomputed=recompute)

    # The coverage gap: his families no concept covers. This list — not a
    # better reader — is the input for the family-template work.
    unmapped: dict[str, list[str]] = {}
    for slug, sc in details:
        for name in sc.unmapped_families:
            unmapped.setdefault(name, []).append(slug)
    if unmapped:
        print(f"\n  UNMAPPED — jo eilutės, kurių koncepto lentelė nepažįsta "
              f"({len(unmapped)} šeimos):")
        for name in sorted(unmapped, key=lambda n: (-len(unmapped[n]), n)):
            print(f"      {name[:66]:<66} {', '.join(sorted(unmapped[name]))}")

    if detailed:
        for slug, sc in details:
            print(f"\n  {'=' * 92}\n  {slug} — {sc.n_rows} eilutės "
                  f"({sc.n_scored} vertinamos)\n  {'=' * 92}")
            print(f"  {'nr':>4}  {'rangovo eilutė':<44} {'vnt':<7} "
                  f"{'jo':>9} {'mūsų':>9} {'Δ':>9}  bucket / kodėl")
            for r in sc.rows:
                pct = "—" if r.pct_error is None else f"{r.pct_error:+.1f}%"
                ours = "—" if r.app_quantity is None else f"{r.app_quantity:g}"
                why = r.bucket if r.pct_error is not None else (
                    f"{r.bucket}: {r.reason or ''}")
                print(f"  {str(r.nr or ''):>4}  {r.name[:44]:<44} "
                      f"{str(r.unit or ''):<7} "
                      f"{('—' if r.quantity is None else f'{r.quantity:g}'):>9} "
                      f"{ours:>9} {pct:>9}  {why[:46]}")
            print(f"    · šeimų sutapimas (Σ vs Σ, granuliaciją ignoruojant): "
                  f"{sc.families_within_10}/{sc.families_scored} ±10 %")
            print(f"    · mūsų eilutės be jo atitikmens: {len(sc.app_extra)}")
    return 0


def _print_registry_exclusion_banner(slug: str | None) -> None:
    """Warn loudly when a single-project run scores a project the registry
    excludes from the corpus MAE.

    2026-07-29: run_totals_only_multi has always skipped scope_mismatch /
    blocked projects, but --rescore never consulted the registry — so
    romainiai's per-project headline MAE looked like a corpus member and got
    hand-averaged in with the other four. Its own registry entry says not to."""
    entry = REGISTRY.get(slug or "") or {}
    reasons: list[tuple[str, str]] = []
    if entry.get("scope_mismatch"):
        reasons.append(("scope_mismatch",
                        entry.get("scope_mismatch_reason")
                        or "scope mismatch documented in registry"))
    if entry.get("blocked_for_vision_extraction"):
        reasons.append(("blocked_for_vision_extraction",
                        entry.get("blocked_reason") or "missing input PDF"))
    if entry.get("blocked_partial_input"):
        reasons.append(("blocked_partial_input",
                        entry.get("blocked_reason")
                        or "input PDF lacks required pages"))
    if not reasons:
        return
    print()
    print("  " + "!" * 92)
    print(f"  !! {slug} is EXCLUDED from the corpus MAE by ground_truth/registry.yaml.")
    print("  !! The score below is diagnostic only — do NOT average it with the "
          "other projects.")
    for flag, reason in reasons:
        print(f"  !!   {flag}:")
        for line in str(reason).strip().splitlines():
            print(f"  !!     {line.strip()}")
    print("  " + "!" * 92)


def run_rescore(path_arg: str, project_id: str | None, *,
                recompute: bool = False) -> int:
    """Offline re-score of a SAVED run against the current truth mappings.

    NO API calls, ever: reads <run_dir>/parsed.json, evaluates it against
    the current METRICS + ground_truth/<slug>/truth.json, and writes
    results_rescored.json (or results_rescored_recomputed.json with
    --recompute) alongside the original. The original results.json is
    never touched."""
    path = Path(path_arg)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if path.is_dir():
        run_dir, parsed_path = path, path / "parsed.json"
    else:
        run_dir, parsed_path = path.parent, path
    if not parsed_path.exists():
        raise SystemExit(f"--rescore: no parsed.json at {parsed_path}")

    slug = project_id or _infer_slug_from_run_name(run_dir.name)
    if not slug:
        raise SystemExit(
            f"--rescore: cannot infer project slug from {run_dir.name!r}; "
            f"pass --project explicitly")

    _print_registry_exclusion_banner(slug)

    truth = _load_truth(slug)
    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    stage = "rescored_recomputed" if recompute else "rescored"
    if recompute:
        parsed = _rerun_deterministic_tail(parsed, slug)

    results = evaluate(parsed, truth)
    per_room = evaluate_per_room(parsed, truth)
    summary = _summarize(results)
    print_report(slug, f"rescore({stage})", results, per_room)

    out_path = run_dir / f"results_{stage}.json"
    out_path.write_text(json.dumps({
        "project": slug,
        "mode": stage,
        "rescore_of": str(parsed_path.relative_to(REPO_ROOT)),
        "recompute": recompute,
        "rescored_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "metrics": [r.__dict__ for r in results],
        "per_room": per_room,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Rescore → {out_path}")
    return 0


THAW_N = 3  # human-confirmed values needed before a frozen formula may re-derive


def human_corpus_summary() -> dict:
    """The SECOND oracle: the human-confirmed corrections accumulating via the
    viewer correction workspace (read by build_ground_truth from the project
    blob). One human-confirmed value beats the entire AI-parsed contractor
    samata. Reports, per quantity_class, how many confirmed values exist and
    whether a frozen formula (kampai/rotband/silikonavimas) may legitimately
    thaw — N>=THAW_N confirmed values before re-deriving, so we never N=1/N=2
    fit. Until then the flags stay; the counter tells us WHEN the freeze lifts."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_ground_truth", REPO_ROOT / "scripts" / "build_ground_truth.py")
    bgt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bgt)
    db = REPO_ROOT / "backend" / "data" / "samatu.db"
    corpus = (bgt.build_corpus(db) if db.exists()
              else {"quantity_truth": [], "stats": {}})
    by_class: dict[str, int] = {}
    for q in corpus.get("quantity_truth", []):
        by_class[q["quantity_class"]] = by_class.get(q["quantity_class"], 0) + 1
    classes = {k: {"confirmed": n, "thaw_eligible": n >= THAW_N}
               for k, n in sorted(by_class.items())}
    return {
        "classes": classes,
        "polygon_confirmed": corpus.get("stats", {}).get("polygon_confirmed", 0),
        "quantity_confirmed": corpus.get("stats", {}).get("quantity_confirmed", 0),
        "frozen_status": {
            f: ("THAW-ELIGIBLE" if classes.get(f, {}).get("thaw_eligible") else
                f"frozen ({classes.get(f, {}).get('confirmed', 0)}/{THAW_N})")
            for f in ("kampai", "rotband", "silikonavimas")
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Sąmatų AI evaluation harness")
    ap.add_argument("--project", default=None,
                    help="project id in REGISTRY (default: objektas_a; for "
                         "--rescore it is inferred from the run-dir name)")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--use-gt-inputs", action="store_true",
                     help="bypass Vision; feed GT primitives into the deterministic engine")
    grp.add_argument("--replay", action="store_true",
                     help="reuse cached extractor output (registry.replay_path)")
    grp.add_argument("--vision", action="store_true",
                     help="run the full Vision pipeline (costs API $$)")
    grp.add_argument("--totals-only", action="store_true",
                     help="multi-project mode: iterate ground_truth/registry.yaml, "
                          "diff AI totals (cached or use-gt-inputs) against each "
                          "project's gt_totals; emit baseline_multi.json")
    grp.add_argument("--rows", action="store_true",
                     help="row-level scorecard: score every cached extract "
                          "against the contractor's own parsed sąmata through "
                          "the FROZEN concept table — how many of HIS billed "
                          "rows we reproduce within ±10 %%. Zero API spend. "
                          "Combine with --recompute for the live engine and "
                          "--detailed for the per-row table.")
    grp.add_argument("--rescore", metavar="RUN_DIR_OR_PARSED_JSON",
                     help="offline re-score a saved run's parsed.json against "
                          "the CURRENT truth mappings — zero API calls. Writes "
                          "results_rescored.json alongside (never overwrites "
                          "results.json). Project slug is inferred from the "
                          "run-dir name or taken from --project.")
    ap.add_argument("--all", action="store_true",
                    help="alias for --totals-only (spec compatibility)")
    ap.add_argument("--recompute", action="store_true",
                    help="with --rescore or --totals-only: re-run the "
                         "deterministic tail (height salvage + plausibility "
                         "gate + per-room recompute + santrauka + pozicijos) "
                         "on the saved primitives before scoring — measures "
                         "CURRENT formula code against saved Vision reads, no "
                         "API. WITHOUT it, --totals-only scores the numbers "
                         "frozen in ai_extract.json and cannot see a fix or a "
                         "regression")
    ap.add_argument("--geometry", action="store_true",
                    help="with --recompute: also run the geometry lane (outlines "
                         "from the vector walls, perimeters added from the plan's "
                         "dimension strings) on the fixture PDF before the "
                         "recompute — zero API. Compare a run with and without it.")
    ap.add_argument("--estimate-exterior", action="store_true",
                    help="apply the principled exterior-opening heuristic to "
                         "gt_dimensions in memory before invoking the calculator "
                         "(truth.json not modified)")
    ap.add_argument("--apply-calibration", action="store_true",
                    help="apply the per-project calibration from "
                         "backend/data/calibrations/{project_id}.json before "
                         "invoking the calculator (currently honours "
                         "perimeter_correction_factor)")
    ap.add_argument("--track-drift", action="store_true",
                    help="append a per-run snapshot to eval_runs/drift.jsonl "
                         "so accuracy regressions across commits become visible")
    ap.add_argument("--verbose", action="store_true",
                    help="print a timeline of every extraction step "
                         "with duration, status, and any cost incurred")
    ap.add_argument("--detailed", action="store_true",
                    help="multi-project: emit the full per-project per-metric "
                         "diff table (default is the compact 5-line summary)")
    # --summary-only is the default for multi-project mode; flag exposed for
    # CI / script clarity. No-op alongside --detailed (detailed wins).
    ap.add_argument("--summary-only", action="store_true",
                    help="multi-project: compact 5-line table (default)")
    ap.add_argument("--debug-project", default=None, metavar="SLUG",
                    help="run only the named project and dump every "
                         "intermediate data structure to "
                         "eval_runs/debug_<slug>_<ts>/ for manual inspection")
    ap.add_argument("--human-corpus", action="store_true",
                    help="report the human-confirmed correction corpus (2nd "
                         "oracle) + per-class confirmed counts + frozen-formula "
                         "thaw status")
    ap.add_argument("--model", default=None, metavar="MODEL_ID",
                    help="W1.2 benchmark axis: force the whole pipeline onto "
                         "this Claude model (sets MODEL_OVERRIDE before the "
                         "pipeline is imported). REQUIRES --vision — cached "
                         "extracts were produced by a different model and "
                         "scoring them under this label would corrupt the "
                         "benchmark. Output lands in eval_runs/<model>/...")
    ap.add_argument("--experiment", default=None, metavar="SPEC",
                    help="2026-07-04 accuracy A/B axis: "
                         "native-pdf | agentic-zoom | mixed-vote:<m1,m2,...>. "
                         "Sets the experiment env var BEFORE the (lazy) "
                         "pipeline import. REQUIRES --vision (same guard as "
                         "--model: experiments must be FRESH reads). Output "
                         "lands in eval_runs/<model-or-config>__<experiment>/")
    args = ap.parse_args()
    global GEOMETRY_LANE
    GEOMETRY_LANE = bool(args.geometry)

    if args.model:
        # FAIL LOUDLY on any cache-reading mode: --replay reuses a saved
        # extract, --totals-only/--all/--debug-project read ai_extract.json,
        # and --use-gt-inputs (also the implicit default) never calls Vision
        # at all. A cached Opus extract scored under a --model claude-fable-5
        # label would corrupt the benchmark.
        if not args.vision:
            raise SystemExit(
                "--model requires --vision: benchmark runs must be FRESH "
                "Vision extractions. Cached/replayed/GT-input modes "
                "(--replay, --use-gt-inputs, --totals-only, --all, "
                "--debug-project, or no mode flag) would score an extract "
                "produced by a different model under this label."
            )
        # Set BEFORE the pipeline is imported/instantiated (run_pipeline_vision
        # imports extractor.vision_call lazily, and models_config.model_for
        # resolves env at call time — belt and suspenders).
        os.environ["MODEL_OVERRIDE"] = args.model
        print(f"  MODEL_OVERRIDE={args.model} (fresh --vision run; "
              f"output → eval_runs/{args.model}/)")

    experiment_tag = None
    if args.experiment:
        # Same guard as --model: a cached extract was produced WITHOUT the
        # experiment env, so scoring it under an experiment label would
        # corrupt the A/B. Fresh Vision reads only.
        if not args.vision:
            raise SystemExit(
                "--experiment requires --vision: experiment runs must be "
                "FRESH Vision extractions. Cached/replayed/GT-input modes "
                "would score a non-experiment extract under this label."
            )
        # Set env BEFORE run_one → run_pipeline_vision lazily imports
        # extractor.vision_call, whose experiment gates read env at call time.
        experiment_tag = _apply_experiment_env(args.experiment)
        print(f"  EXPERIMENT {args.experiment} (fresh --vision run; output → "
              f"eval_runs/{args.model or 'default-config'}__{experiment_tag}/)")

    if args.human_corpus:
        import json as _json
        print(_json.dumps(human_corpus_summary(), ensure_ascii=False, indent=2))
        return 0

    if args.debug_project:
        return run_debug_project(args.debug_project)

    if args.rows:
        return run_rows_scorecard(
            GROUND_TRUTH_ROOT / "registry.yaml",
            recompute=args.recompute,
            detailed=args.detailed,
        )

    if args.rescore:
        return run_rescore(args.rescore, args.project, recompute=args.recompute)

    if args.totals_only or args.all:
        return run_totals_only_multi(
            GROUND_TRUTH_ROOT / "registry.yaml",
            detailed=args.detailed,
            recompute=args.recompute,
        )

    if args.use_gt_inputs:
        mode = "use_gt_inputs"
    elif args.replay:
        mode = "replay"
    elif args.vision:
        mode = "vision"
    else:
        mode = "use_gt_inputs"  # default: cheapest, safest
    return run_one(args.project or "objektas_a", mode,
                   estimate_exterior=args.estimate_exterior,
                   apply_calibration=args.apply_calibration,
                   track_drift=args.track_drift,
                   verbose=args.verbose,
                   model=args.model,
                   experiment=experiment_tag)


if __name__ == "__main__":
    sys.exit(main())

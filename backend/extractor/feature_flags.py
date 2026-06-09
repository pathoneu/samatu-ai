"""Feature flags read from environment variables.

Each flag controls one accuracy-affecting code path so we can A/B test
and one-line-revert if needed. Defaults to False (off) for safety.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §8.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# (env_var_name, default_when_unset)
_FLAG_DEFINITIONS = {
    "per_room_ceiling":      ("ENABLE_PER_ROOM_CEILING", True),          # Sprint 0 Fix 4 → default ON 2026-05-06 (per-room aukštis virš 3m extraction)
    "paint_class_inference": ("ENABLE_PAINT_CLASS_INFERENCE", False),    # Sprint 0 Fix 5
    "verify_pass":           ("ENABLE_VERIFY_PASS", False),              # Sprint 3
    # Sprint 4 Block B: activated default-on after wall_adjacency
    # validated on P1+P3+P5 (grindjuostės ratio drops to 0.5-0.6 m/m²
    # from 0.98 broken double-count). Override with ENABLE_POLYGON_PREPASS=0
    # if regression suspected.
    "polygon_prepass":       ("ENABLE_POLYGON_PREPASS", True),           # Sprint 2 → 4
    "sonnet_pass1":          ("ENABLE_SONNET_PASS1", False),             # Sprint 4
    "grid_overlay":          ("ENABLE_GRID_OVERLAY", False),             # Sprint 3
    "proxy_gt":              ("ENABLE_PROXY_GT", False),                 # Sprint 4
    # 2026-06-06: collapse the per-coat glaistymas/dažymas split (Q1/Q2/sluoksnis,
    # walls+ceilings) into the contractor's combined "Sienų, lubų glaistymas/
    # dažymas (iki/virš 3m)" line (Rangovas A samata items 16/17). Display-only;
    # santrauka totals unchanged. Disable: ENABLE_CONSOLIDATE_PAINT_LINES=0
    "consolidate_paint_lines": ("ENABLE_CONSOLIDATE_PAINT_LINES", True),
    # 2026-06-05: floor SYNTHETIC square perimeters (perim ≈ 4·√area) on plans
    # with NO eksplikacija table, for the wall-paint path only. Gated on
    # plotas_saltinis so eksplikacija/inline_label rooms are NEVER touched →
    # zero regression on read-from-table projects (verified: berzas, bacveviciaus,
    # romainiai → 0 rooms fire). Recovers no-eksplikacija paint: ciurliu
    # -20.3%→-13.5%, lazunu -14.0%→-5.4%. Disable: ENABLE_PERIMETER_FLOOR_SYNTHETIC=0
    "perimeter_floor_synthetic": ("ENABLE_PERIMETER_FLOOR_SYNTHETIC", True),
}


def _resolve(env_value: str, default: bool) -> bool:
    v = (env_value or "").strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return default


def get_flags() -> dict[str, bool]:
    """Return current feature flag state as {flag_name: bool}.

    Reads from environment variables; defaults per-flag (most are False;
    polygon_prepass defaults True after Sprint 4 Block B validation).
    Truthy: "1"/"true"/"yes"/"on". Falsy: "0"/"false"/"no"/"off".
    Any other value (incl. empty) → flag's default.
    """
    return {
        name: _resolve(os.environ.get(env, ""), default)
        for name, (env, default) in _FLAG_DEFINITIONS.items()
    }


# Back-compat alias for any old code reading _FLAG_ENV_NAMES
_FLAG_ENV_NAMES = {name: env for name, (env, _default) in _FLAG_DEFINITIONS.items()}

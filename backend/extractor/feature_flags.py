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
    # zero regression on read-from-table projects (verified: berzas, objektas_b,
    # romainiai → 0 rooms fire). Recovers no-eksplikacija paint: ciurliu
    # -20.3%→-13.5%, lazunu -14.0%→-5.4%. Disable: ENABLE_PERIMETER_FLOOR_SYNTHETIC=0
    "perimeter_floor_synthetic": ("ENABLE_PERIMETER_FLOOR_SYNTHETIC", True),
    # 2026-06-09: run the high-variance Pass-1 (+ adjacency) N times and
    # median-vote into one consensus extraction. Stabilises kampai (the
    # pusiniai term survives a single adjacency-bail run) and wires the
    # adjacency pass into production so n_partition_walls is populated on
    # real uploads (not just the offline benchmark).
    # → DEFAULT ON after the live A/B on berzas (2026-06-09): voted vs single-pass
    #   moved combined paint −5.4%→+2.3%, kampai −32%→−10.6%, recovered per-room
    #   ceiling heights [2.8,3.0,3.4] and n_partition_walls 0→34, at only +13%
    #   wall-clock (once-only downstream passes dominate; consensus already carried
    #   heights so zoom skipped). Disable: ENABLE_EXTRACTION_VOTING=0.
    #   Rounds: VOTING_N (default 3, 2-5).
    "extraction_voting": ("ENABLE_EXTRACTION_VOTING", True),
    # 2026-07-29: run the Pass-1 voting rounds CONCURRENTLY instead of one
    # after another. Measured on the 17-page production run that took 1613 s
    # end to end: the three rounds are ~220 s each and ran strictly serially,
    # so they alone were ~660 s — 41% of the whole extraction — spent waiting
    # on calls that do not depend on one another.
    #
    # ACCURACY IS UNCHANGED BY CONSTRUCTION: identical prompts, identical
    # model, identical round count, and the results are re-ordered back into
    # round order before voting, so the median sees exactly the same input it
    # sees today. What changes is only how long we wait.
    #
    # The cost is prompt cache: today round 1 writes the image prefix and
    # rounds 2-3 read it at 0.1x. Fired together, all three pay full price.
    # PARALLEL_VOTING_WARM=1 keeps round 1 alone first (cache warm, rounds 2..n
    # then concurrent) — less latency won, no extra spend.
    # DEFAULT OFF until measured on a real PDF. Enable: ENABLE_PARALLEL_VOTING=1
    "parallel_voting": ("ENABLE_PARALLEL_VOTING", False),
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


def voting_n(default: int = 3) -> int:
    """Number of Pass-1 rounds to run when extraction_voting is on.

    Read from VOTING_N; clamped to [2, 5] (1 defeats the purpose, >5 burns
    budget with diminishing returns). Invalid/unset → default (3).
    """
    try:
        n = int(os.environ.get("VOTING_N", "").strip() or default)
    except (ValueError, TypeError):
        n = default
    return max(2, min(5, n))

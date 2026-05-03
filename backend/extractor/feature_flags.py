"""Feature flags read from environment variables.

Each flag controls one accuracy-affecting code path so we can A/B test
and one-line-revert if needed. Defaults to False (off) for safety.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §8.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}

_FLAG_ENV_NAMES = {
    "per_room_ceiling": "ENABLE_PER_ROOM_CEILING",         # Sprint 0 Fix 4
    "paint_class_inference": "ENABLE_PAINT_CLASS_INFERENCE",  # Sprint 0 Fix 5
    "verify_pass": "ENABLE_VERIFY_PASS",                   # Sprint 3
    "polygon_prepass": "ENABLE_POLYGON_PREPASS",           # Sprint 2
    "sonnet_pass1": "ENABLE_SONNET_PASS1",                 # Sprint 4
    "grid_overlay": "ENABLE_GRID_OVERLAY",                 # Sprint 3
    "proxy_gt": "ENABLE_PROXY_GT",                         # Sprint 4
}


def get_flags() -> dict[str, bool]:
    """Return current feature flag state as {flag_name: bool}.

    Reads from environment variables; each flag defaults to False.
    Truthy values: "1", "true", "yes", "on" (case-insensitive).
    All other values (including empty string) = False.
    """
    return {
        name: os.environ.get(env, "").strip().lower() in _TRUTHY
        for name, env in _FLAG_ENV_NAMES.items()
    }

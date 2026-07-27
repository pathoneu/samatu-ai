"""GET /api/config — exposes feature flags + active model IDs to frontend."""
from fastapi import APIRouter, Request
from extractor.feature_flags import get_flags
from models_config import model_for, resolved_models

import auth as _auth

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config(request: Request) -> dict:
    """Return feature flag state and active model IDs.

    Used by frontend to:
    - Show/hide experimental features based on flag state
    - Know which models are active (for logging, analytics)
    - Verify backend connectivity

    `models` is the LIVE role → model map from models_config (resolved at
    request time, so MODEL_OVERRIDE / SAMATU_MODEL_* env changes show up
    immediately). `pass1`/`pass2` keys are kept for backward compat with
    the pre-W1.1 payload shape.

    Returns:
        {
            "flags": {...},
            "models": {
                "pass1": "<model>", "pass2": "<model>",   # legacy aliases
                "vision_pass1": "...", "doors": "...", ...  # full role map
            }
        }
    """
    # 2026-07-27 (pre-prod audit): this was unauthenticated. It hands any
    # anonymous caller our internal feature-flag map and the exact model IDs in
    # production — free reconnaissance for probing flag-gated code paths, and a
    # competitive tell. There are zero frontend callers, so gating it costs
    # nothing; matches the require_user convention of every other /api router.
    _auth.require_user(request)
    models = resolved_models()
    return {
        "flags": get_flags(),
        "models": {
            **models,
            # Legacy aliases (pre-W1.1 payload shape)
            "pass1": model_for("vision_pass1"),
            "pass2": model_for("vision_pass2"),
        },
    }

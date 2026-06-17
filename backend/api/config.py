"""GET /api/config — exposes feature flags + active model IDs to frontend."""
from fastapi import APIRouter
from extractor.feature_flags import get_flags

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config() -> dict:
    """Return feature flag state and active model IDs.

    Used by frontend to:
    - Show/hide experimental features based on flag state
    - Know which models are active (for logging, analytics)
    - Verify backend connectivity

    Returns:
        {
            "flags": {
                "per_room_ceiling": bool,
                "paint_class_inference": bool,
                ...
            },
            "models": {
                "pass1": "claude-opus-4-8",
                "pass2": "claude-opus-4-8",
            }
        }
    """
    return {
        "flags": get_flags(),
        "models": {
            "pass1": "claude-opus-4-8",
            "pass2": "claude-opus-4-8",
        },
    }

"""Vision extraction of roof geometry from LT brėžiniai (Phase 1 T7-T8).

Two prompts:
  - `extract_stogo_planas_dims` — top-down roof plan: footprint, eaves,
    wall thickness, chimney/rooflight/window counts, roof type hint.
  - `extract_pjuvis_dims` — section/pjūvis: slope angles + ridge height.

Caller composes both outputs into a `RoofInput` and runs the matching
strategy. Designed to be iterated against `ground_truth/*_roof.yaml`
fixtures — each prompt's accuracy is measured per-field, not just
yes/no.

Default model is Opus 4.7 per user policy ("strongest model for LT
brėžinių tasks"). Override via `model=` kwarg for cheap dry-runs.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from extractor.page_classifier import OPUS_MODEL
from extractor.roof.strategies import RoofInput


_DEFAULT_WALL_THICKNESS_M = 0.25  # LT blokeliai typical (per CLAUDE.md §2)


# ---------------------------------------------------------------------------
# Prompt 1 — stogo planas (roof plan)
# ---------------------------------------------------------------------------

_STOGO_PLANAS_SYSTEM = """You are extracting roof geometry from a Lithuanian
construction drawing labelled "STOGO PLANAS" (roof plan, top-down view).

LT antspaudas conventions you MUST respect:
- All linear dimensions on LT brėžiniai are labelled AXIS-TO-AXIS, NOT
  outer-face-to-outer-face. Return what you ACTUALLY SEE on the drawing
  (axis dimensions). The downstream code adds the wall thickness to get
  the outer-to-outer footprint — do not do that arithmetic yourself.
- Long side → `axis_to_axis_length_m`. Short side → `axis_to_axis_width_m`.
  If the drawing shows multiple axis segments (e.g. "380 + 490 = 870 cm"),
  SUM them and report the total. All values in metres.
- Eaves overhang (karnizo iškyša) is annotated from the wall axis to the
  drip edge. Return `eaves_overhang_from_axis_m` literally — the downstream
  code subtracts wall_thickness/2 to get the from-outer-wall value.
- Wall thickness is shown in section details OR called out in a
  "MEDŽIAGŲ ŽINIARAŠTIS" (materials list). Common LT exterior walls:
  blokeliai 0.20-0.25m, blokeliai+EPS 0.30-0.50m. If not visible, set to
  null and explain in `notes`.
- Roof type from the plan shape:
    * Single rectangle with ONE ridge running long-side, two gables → dvislaitis
    * Single rectangle with FOUR hip slopes meeting at central ridge → keturslaitis
    * Single rectangle with ONE sloped plane (one high wall, one low) → vienslaitis
    * Multiple intersecting roof masses → sudetinis (mark as unknown)
- Slope angles (nuolydžiai) are OFTEN annotated directly on the STOGO
  PLANAS near each slope's surface — usually as a small triangle marker
  with a number (e.g. "22°", "25°", "i=30°", "i=1:2"). List all distinct
  values you see in `visible_slope_angles_deg`. Convert ratios/percents
  to degrees (1:2 = arctan(1/2) ≈ 26.57°, 30% ≈ 16.70°). Order:
  long-side angle first if you can distinguish them.

Object counts — be CONSERVATIVE and distinguish carefully:
- A chimney (kaminėlis) on the roof plan looks like a small SOLID
  rectangle in the centre of a slope, often with extra hatching or a
  symbol overlay. Count only ones you're confident about.
- A rooflight / skylight (stoglangis) is a small clear rectangle
  outlined like a window, usually labelled "ST.L" or "SL" or shown
  with a glass-pane symbol.
- A roof window means a vertical window in the gable end (only on
  dvislaitis / mansardinis), NOT on a slope.
- If you see ambiguous small marks (could be vents, antennas, ridge
  tiles), set the count to 0 and mention them in `notes`.

Return strict JSON matching the provided schema. If a value isn't
confidently readable from the drawing, set it to null and add a short
explanation in `notes`. NEVER guess dimensions — null is honest.

Units:
- All lengths in metres (m).
- All counts are integers.
"""

_STOGO_PLANAS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "roof_type",
        "axis_to_axis_length_m",
        "axis_to_axis_width_m",
        "eaves_overhang_from_axis_m",
        "wall_thickness_m",
        "visible_slope_angles_deg",
        "chimney_count",
        "rooflight_count",
        "windows_count",
        "confidence",
        "notes",
    ],
    "properties": {
        "roof_type": {
            "type": "string",
            "enum": [
                "dvislaitis",
                "keturslaitis",
                "vienslaitis",
                "mansardinis",
                "plokscias",
                "unknown",
            ],
        },
        # Axis-to-axis = what's annotated on LT drawings (between wall
        # centrelines). Downstream code adds wall_thickness for the
        # outer-to-outer footprint.
        "axis_to_axis_length_m": {"type": ["number", "null"]},
        "axis_to_axis_width_m": {"type": ["number", "null"]},
        "eaves_overhang_from_axis_m": {"type": ["number", "null"]},
        "wall_thickness_m": {"type": ["number", "null"]},
        # Slope angles annotated on the roof plan itself (LT studios
        # commonly mark each slope's angle next to the slope surface).
        # Empty list if no angles visible — pjūvis is then the source.
        "visible_slope_angles_deg": {
            "type": "array",
            "items": {"type": "number"},
        },
        "chimney_count": {"type": "integer"},
        "rooflight_count": {"type": "integer"},
        "windows_count": {"type": "integer"},
        "confidence": {"type": "number"},
        "notes": {"type": "string"},
    },
}


def extract_stogo_planas_dims(
    image_b64: str,
    *,
    client: anthropic.Anthropic | None = None,
    model: str = OPUS_MODEL,
) -> dict:
    """Run Vision extraction on a rendered STOGO PLANAS page.

    Returns the raw JSON dict per `_STOGO_PLANAS_SCHEMA`. Caller is
    responsible for deriving `eaves_overhang_from_outer_wall_m`
    (= axis − wall_thickness/2) and merging into a `RoofInput`.
    """
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=600,
        system=[{
            "type": "text",
            "text": _STOGO_PLANAS_SYSTEM,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract roof geometry from this STOGO PLANAS page:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
            ],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _STOGO_PLANAS_SCHEMA,
            },
        },
    )
    return json.loads(resp.content[0].text)


# ---------------------------------------------------------------------------
# Prompt 2 — pjūvis (section)
# ---------------------------------------------------------------------------

_PJUVIS_SYSTEM = """You are extracting roof slope information from a
Lithuanian construction drawing labelled "PJŪVIS" (vertical cross-section).

The slope (nuolydis) may be shown in any of these formats:
  - Degrees:    "30°" or "25°"
  - Ratio:      "1:2" (rise:run) — convert to degrees: arctan(1/2) ≈ 26.57°
  - Percent:    "30%" → arctan(0.30) ≈ 16.70°

Return ALL distinct slopes visible. For an asymmetric keturšlaitis, you
will typically see two angles (long-side and short-side). For a
symmetric dvišlaitis, you will see one angle.

Slope angles are usually labelled near the roof apex with a small
triangle marker. Cross-check with the rafter (gegnė) length annotation
if visible.

Heights (+X.XXX markers from datum):
  - `ridge_height_m`: top of roof apex
  - `eaves_height_m`: lowest edge of roof (where gutter sits)
  - `eaves_to_ground_m` = `eaves_height_m` − floor level (usually ±0.000)

Wall thickness (sienos storis) — often dimensioned in the section with
a small horizontal dimension across the wall (e.g. "250" mm, "300" mm).
Return in metres (e.g. 0.25). Common LT values: 0.20-0.25m (blokeliai),
0.30-0.50m (blokeliai + EPS insulation). If not shown in the section,
return null — the downstream code will fall back to a default.

Return strict JSON. If a value isn't confidently readable, set null
and explain in `notes`. NEVER guess slope angles or thicknesses — null
is honest.
"""

_PJUVIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "slope_angles_deg",
        "slope_format_seen",
        "ridge_height_m",
        "eaves_height_m",
        "wall_thickness_m",
        "confidence",
        "notes",
    ],
    "properties": {
        "slope_angles_deg": {
            "type": "array",
            "items": {"type": "number"},
        },
        "slope_format_seen": {
            "type": "string",
            "enum": ["degrees", "ratio", "percent", "unknown", "none"],
        },
        "ridge_height_m": {"type": ["number", "null"]},
        "eaves_height_m": {"type": ["number", "null"]},
        "wall_thickness_m": {"type": ["number", "null"]},
        "confidence": {"type": "number"},
        "notes": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Merger — combine stogo planas + pjūvis JSON into a RoofInput
# ---------------------------------------------------------------------------

def build_roof_input(
    stogo: dict,
    pjuvis: dict | None = None,
    *,
    default_wall_thickness_m: float = _DEFAULT_WALL_THICKNESS_M,
) -> tuple[RoofInput, list[str]]:
    """Merge Vision JSON outputs into a `RoofInput` ready for strategy dispatch.

    Returns the input plus a list of warnings (fields that fell back to
    defaults or were cross-validated with disagreement).

    Field provenance:
      - `roof_type`: stogo planas (cross-checked against pjūvis if angles count).
      - `building_length_m`/`width_m`: axis + wall_thickness (outer-to-outer).
      - `eaves_overhang_m`: axis value − wall_thickness/2 (from-outer-wall).
      - `slopes_deg`: stogo planas annotations first; fall back to pjūvis.
      - `wall_thickness_m`: pjūvis section first; default if both missing.
      - Counts: stogo planas directly.
    """
    warnings: list[str] = []

    # 1. Wall thickness — pjūvis is the canonical source; stogo planas
    # rarely has it. Fall back to a documented default.
    wt = (pjuvis or {}).get("wall_thickness_m") or stogo.get("wall_thickness_m")
    if wt is None:
        wt = default_wall_thickness_m
        warnings.append(
            f"wall_thickness_m not visible in either page — using LT default {wt}m"
        )

    # 2. Footprint — axis + wall = outer-to-outer.
    axis_len = stogo.get("axis_to_axis_length_m")
    axis_wid = stogo.get("axis_to_axis_width_m")
    if axis_len is None or axis_wid is None:
        raise ValueError(
            "axis_to_axis_length_m / axis_to_axis_width_m missing — "
            "stogo planas extraction failed"
        )
    building_length_m = axis_len + wt
    building_width_m = axis_wid + wt

    # 3. Eaves overhang — axis-to-edge minus half a wall.
    eaves_axis = stogo.get("eaves_overhang_from_axis_m")
    if eaves_axis is None:
        raise ValueError("eaves_overhang_from_axis_m missing")
    eaves_outer = eaves_axis - wt / 2

    # 4. Slope angles — prefer stogo planas (often shows both per side).
    stogo_slopes = stogo.get("visible_slope_angles_deg") or []
    pjuvis_slopes = (pjuvis or {}).get("slope_angles_deg") or []
    if stogo_slopes:
        slopes = stogo_slopes
        if pjuvis_slopes:
            # Cross-check: pjūvis should match at least one stogo planas angle.
            for ps in pjuvis_slopes:
                if not any(abs(ps - ss) <= 1.5 for ss in stogo_slopes):
                    warnings.append(
                        f"pjūvis reports {ps}° not present in stogo planas {stogo_slopes}"
                    )
    elif pjuvis_slopes:
        slopes = pjuvis_slopes
        warnings.append("slope_angles fell back to pjūvis (stogo planas had none)")
    else:
        raise ValueError("no slope angles found in either page")

    # 5. Roof type from stogo planas.
    roof_type = stogo.get("roof_type", "unknown")
    if roof_type == "unknown":
        warnings.append("roof_type is 'unknown' — strategy dispatch will refuse")

    return (
        RoofInput(
            roof_type=roof_type,
            building_length_m=building_length_m,
            building_width_m=building_width_m,
            eaves_overhang_m=eaves_outer,
            slopes_deg=slopes,
            wall_thickness_m=wt,
            chimney_count=stogo.get("chimney_count", 0),
            rooflight_count=stogo.get("rooflight_count", 0),
            windows_count=stogo.get("windows_count", 0),
        ),
        warnings,
    )


def extract_pjuvis_dims(
    image_b64: str,
    *,
    client: anthropic.Anthropic | None = None,
    model: str = OPUS_MODEL,
) -> dict:
    """Run Vision extraction on a rendered PJŪVIS page.

    Returns the raw JSON dict per `_PJUVIS_SCHEMA`.
    """
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        system=[{
            "type": "text",
            "text": _PJUVIS_SYSTEM,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract slope angles from this PJŪVIS page:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
            ],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _PJUVIS_SCHEMA,
            },
        },
    )
    return json.loads(resp.content[0].text)

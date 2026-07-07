"""Central Claude model configuration (W1.1, 2026-07-03).

Single source of truth for WHICH model each pipeline role uses. Every call
site resolves its model via ``model_for(role)`` at CALL time (os.getenv on
every invocation) so a harness that sets ``MODEL_OVERRIDE`` before running
the pipeline steers every reader without re-imports.

Exact model IDs (authoritative — never append date suffixes):
  - ``claude-opus-4-8``  — current production default for every role.
  - ``claude-fable-5``   — W1 benchmark candidate. Fable 5 API facts:
      thinking is always on (send NO ``thinking`` param — an explicit
      ``disabled`` 400s), no assistant prefill, 128K max output, same
      tokenizer as Opus 4.8, requires 30-day data retention, safety
      classifiers may return ``stop_reason="refusal"`` (HTTP 200) — check
      ``stop_reason`` before reading content.

NO-TEMPERATURE RULE: never add ``temperature``, ``top_p``, or ``top_k`` to
any Anthropic call anywhere in this codebase — all three return 400 on both
Opus 4.8 and Fable 5. Determinism comes from strict JSON schemas + voting,
not sampling parameters.

Resolution chain for ``model_for(role)`` (first match wins):
  1. ``SAMATU_MODEL_<ROLE>``  — per-role env (e.g. SAMATU_MODEL_DOORS)
  2. ``MODEL_OVERRIDE``       — global env; set by ``eval_harness.py --model``
  3. legacy envs (backward compat):
       ``VISION_MODEL``      — every drawing-reading role (all except
                               "extraction" and "chat")
       ``EXTRACTION_MODEL``  — the "extraction" (KŽ text fallback) role
  4. ``ROLES[role]`` default

Roles:
  vision_pass1     — Pass-1 full-PDF interior extraction (vision_call.py),
                     vision_call_v2 strict-schema helper, the vision/
                     sub-readers (dimensions, adjacency, bboxes, niches,
                     elevations, heights, schedules, built-ins, room graph,
                     page dispatch), roof extractors, main.py legacy vision.
  vision_pass2     — Pass-2 zoom re-reads (per-room high-DPI measurement)
                     and the advisory verify pass.
  doors            — doors_reader + door_type_reader.
  apdailos         — apdailos_reader (finish shares from išklotinės).
  sanitary         — sanitary_fixture_reader.
  legend           — legend_injection.extract_legend.
  page_classifier  — page_classifier (all former Haiku/Sonnet/Opus tiers).
  symbols          — extractor/vision/symbol_detector + interior_v9.
  extraction       — main.py KŽ text-extraction Claude fallback.
  chat             — main.py project chat endpoint.
"""
from __future__ import annotations

import os

DEFAULT_MODEL = "claude-opus-4-8"

ROLES: dict[str, str] = {
    "vision_pass1": DEFAULT_MODEL,
    "vision_pass2": DEFAULT_MODEL,
    "doors": DEFAULT_MODEL,
    "apdailos": DEFAULT_MODEL,
    "sanitary": DEFAULT_MODEL,
    "legend": DEFAULT_MODEL,
    "page_classifier": DEFAULT_MODEL,
    "symbols": DEFAULT_MODEL,
    "extraction": DEFAULT_MODEL,
    "chat": DEFAULT_MODEL,
}

# Roles historically steered by the legacy VISION_MODEL env — everything
# that reads drawings. "extraction" keeps EXTRACTION_MODEL; "chat" has no
# legacy env.
_VISION_ROLES = frozenset(ROLES) - {"extraction", "chat"}


def model_for(role: str) -> str:
    """Resolve the model ID for a pipeline role. Resolves env vars at CALL
    time (not import time) so MODEL_OVERRIDE set by a harness applies to
    every subsequent call without re-imports."""
    if role not in ROLES:
        raise KeyError(
            f"unknown model role {role!r} (known: {', '.join(sorted(ROLES))})"
        )
    per_role = os.getenv(f"SAMATU_MODEL_{role.upper()}")
    if per_role:
        return per_role
    override = os.getenv("MODEL_OVERRIDE")
    if override:
        return override
    if role in _VISION_ROLES:
        legacy = os.getenv("VISION_MODEL")
        if legacy:
            return legacy
    elif role == "extraction":
        legacy = os.getenv("EXTRACTION_MODEL")
        if legacy:
            return legacy
    return ROLES[role]


def resolved_models() -> dict[str, str]:
    """Live role → model map (resolved now, env included). Used by
    GET /api/config so the frontend/ops can see what is actually active."""
    return {role: model_for(role) for role in ROLES}

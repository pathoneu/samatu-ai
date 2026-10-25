"""Central Claude model configuration (W1.1, 2026-07-03).

Single source of truth for WHICH model each pipeline role uses. Every call
site resolves its model via ``model_for(role)`` at CALL time (os.getenv on
every invocation) so a harness that sets ``MODEL_OVERRIDE`` before running
the pipeline steers every reader without re-imports.

Exact model IDs (authoritative — never append date suffixes):
  - ``claude-opus-5``    — production default for every role since
      2026-07-28, chosen by paid bake-off on the ground-truth fixtures:
      Objektas A headline MAE 6.12% vs 7.03% (opus-4-8), category 10.49% vs
      13.41%; objektas_b headline 39.34% vs 51.23%, category ~tied.
      Same $5/$25 pricing and SAME TOKENIZER as opus-4-8 (cost baselines
      carry over). API facts: thinking ON BY DEFAULT (never send an
      explicit ``thinking`` param; ``max_tokens`` caps thinking+answer,
      so snug caps truncate — floors were raised at the cutover), safety
      classifiers may return ``stop_reason="refusal"`` (HTTP 200) — the
      call sites check ``stop_reason`` before reading content; prompt-
      cache minimum drops to 512 tokens (short system prompts now cache).
  - ``claude-opus-4-8``  — previous champion; kept as the known-good
      rollback (set MODEL_OVERRIDE=claude-opus-4-8 to restore instantly).
  - ``claude-fable-5``   — evaluated twice (2026-07-03, 2026-07-28),
      lost both times on headline MAE at 2× the price. Not used.
  - ``claude-fable-5-1`` — evaluated 2026-09-02 (same-day fresh A/B vs opus-5,
      docs/superpowers/research/2026-09-02-fable51-benchmark.md): mean MAE
      tie (29.14 vs 29.38), Objektas A (contractor truth) 10.66 vs 5.23 — worse,
      2.4× the cost, +22% wall time, doors reader 3× slower. Not used.
  - ``claude-sonnet-5``  — evaluated 2026-07-28: 24.3%/46.1% MAE on
      Objektas A, unusable for LT drawings. Never route vision roles here.

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
  text_schema      — backend/text/schema_llm.py: extracted TEXT → schema JSON, every value substring-guarded (v4
                     3c-2, the only model call a text-first reader may make; it never sees an image).
"""
from __future__ import annotations

import os

DEFAULT_MODEL = "claude-opus-5"

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
    "text_schema": DEFAULT_MODEL,
}

# Roles historically steered by the legacy VISION_MODEL env — everything
# that reads drawings. "extraction" keeps EXTRACTION_MODEL; "chat" has no
# legacy env.
_VISION_ROLES = frozenset(ROLES) - {"extraction", "chat", "text_schema"}


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

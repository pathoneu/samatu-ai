# backend/extractor/verify_pass.py
"""Sprint 3 Section 6: self-verify pass.

Calls Opus 4.7 with the Pass-1 result + asks: 'Identify quantities you'd
disagree with and explain why.' Returns advisory `corrections[]` array.

Output is NEVER auto-applied — frontend AI tab surfaces corrections as
suggestions. User can accept/reject manually.

Gated by ENABLE_VERIFY_PASS=1. When off, returns empty corrections so
caller's downstream merge is a no-op.

See spec §4.3 verify_pass.py + parent spec §10 risk register.
"""
from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from extractor.feature_flags import get_flags

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    corrections: list[dict] = field(default_factory=list)
    error: str | None = None


def _call_opus(prompt: str) -> dict:
    """Invoke Anthropic Opus 4.7 with the verify prompt. Returns parsed
    JSON response with `corrections[]` key.

    Stub for Sprint 3 — Sprint 4 wires the actual SDK call. Tests patch
    this function directly. Real call uses the existing `extractor.stream`
    helper or anthropic SDK client.
    """
    raise NotImplementedError("verify_pass real call wires in Sprint 4")


def _build_prompt(rooms: list[dict], pozicijos: list[dict]) -> str:
    summary_lines = []
    for p in pozicijos:
        summary_lines.append(
            f"- {p.get('id')} · {p.get('skyrius_label', p.get('skyrius', '-'))} · "
            f"{p.get('aprasymas', '-')} · {p.get('kiekis')} {p.get('vnt', '-')}"
        )
    rooms_summary = "\n".join(
        f"- {r.get('id')} ({r.get('pavadinimas', '-')}): {r.get('plotas_m2', '-')} m², "
        f"perim {r.get('perimetras_m', '-')} m"
        for r in rooms
    )
    return f"""You are a senior LT construction estimator reviewing AI Pass-1 output.

Rooms:
{rooms_summary}

Quantities (KŽ pozicijos):
{chr(10).join(summary_lines)}

Identify SPECIFIC quantities you would disagree with. For each, provide:
- pozicija_id
- suggested_value (numeric)
- reason (1 sentence in Lithuanian)
- confidence ("high" | "med" | "low")

Return as JSON: {{"corrections": [...]}}. If everything looks reasonable,
return {{"corrections": []}}. Be conservative — only flag genuine errors.
"""


def run_verify_pass(rooms: list[dict], pozicijos: list[dict]) -> VerifyResult:
    """Entry point. Returns VerifyResult with corrections (possibly empty)."""
    if not get_flags()["verify_pass"]:
        return VerifyResult()
    try:
        prompt = _build_prompt(rooms, pozicijos)
        response = _call_opus(prompt)
        return VerifyResult(corrections=response.get("corrections", []))
    except Exception as exc:
        log.exception("verify_pass call failed")
        return VerifyResult(error=str(exc))

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
import json
import logging
import os
from dataclasses import dataclass, field

import anthropic

from extractor.feature_flags import get_flags
from models_config import model_for

log = logging.getLogger(__name__)

_VERIFY_SYSTEM = (
    "You are a senior Lithuanian construction estimator (LT samatininkas) "
    "performing an advisory verification pass. Reply ONLY with strict JSON "
    "matching the schema {\"corrections\": [{\"pozicija_id\": str, "
    "\"suggested_value\": number, \"reason\": str, "
    "\"confidence\": \"high\"|\"med\"|\"low\"}]}. No prose, no markdown, "
    "no code fences. If everything looks reasonable return "
    "{\"corrections\": []}. Be conservative — only flag genuine errors."
)


@dataclass
class VerifyResult:
    corrections: list[dict] = field(default_factory=list)
    error: str | None = None


def _extract_text(message) -> str:
    """Concatenate text blocks from an Anthropic Messages response."""
    return "".join(
        getattr(b, "text", "") for b in (message.content or [])
        if getattr(b, "type", None) == "text"
    )


def _call_opus(prompt: str) -> dict:
    """Invoke Opus 4.7 with the verify prompt. Returns the parsed JSON
    response (always a dict; missing `corrections` defaults to []).

    Tests patch this function directly. The real call goes through the
    same anthropic SDK client used everywhere else in the extractor;
    output is constrained to the response schema by the system prompt
    and parsed defensively (model may emit a fenced block on rare bad
    days even after being told not to).
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set; cannot run verify_pass live."
        )
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model_for("vision_pass2"),
        max_tokens=4096,
        system=[{"type": "text", "text": _VERIFY_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    text = _extract_text(resp).strip()
    # Strip ```json fences if the model added them despite the system prompt.
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"verify_pass response is not a JSON object: {type(parsed)!r}")
    parsed.setdefault("corrections", [])
    return parsed


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

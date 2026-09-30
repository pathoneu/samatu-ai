"""One safe way to read text out of an Anthropic response.

`resp.content[0].text` is wrong on any model with extended thinking on by
default: block 0 is a ThinkingBlock, which has no `.text`, so the reader
dies with `'ThinkingBlock' object has no attribute 'text'`. It is
INTERMITTENT — whether a thinking block is emitted varies run to run — so
the same PDF succeeds one minute and degrades the next.

Measured 2026-07-29: the apdailos (išklotinių) reader hit this mid-run on
objektas_a. It reads per-room wall finishes, so when it dies every room falls
back to paskirtis defaults — the garažas walls (31.45 m² of real paint)
drop out entirely and `Sienų dažomas plotas` lands 31% low. Headline MAE
on that run was 12.996% against 6.116% for the same pipeline with the
reader alive.

Pass-1 and several readers already filtered blocks by type; the ones that
did not are the ones that broke. This is that filter, in one place.
"""
from __future__ import annotations

from typing import Any

__all__ = ["response_text", "stop_error", "read_answer", "usage_meta", "ModelStopped",
           "stopped_round_metas", "run_until_refused"]


def response_text(resp: Any) -> str:
    """Concatenate every text block of a response, skipping thinking blocks.

    Returns "" when the response carries no text at all (the callers all
    treat empty as "reader produced nothing" and degrade explicitly rather
    than raising). Never raises on odd block shapes — a malformed block is
    skipped, because losing one block beats losing the whole read.

    Strictly a superset of the `content[0].text` it replaces: when no block
    declares `type == "text"` we fall back to any block carrying a string
    `.text`. Real SDK blocks always declare a type, but stubs and older
    response shapes do not, and this swap must not be able to read LESS
    than the code it replaced.
    """
    blocks = getattr(resp, "content", None) or []
    typed: list[str] = []
    untyped: list[str] = []
    for b in blocks:
        text = getattr(b, "text", None)
        if not isinstance(text, str):
            continue          # thinking / tool_use / malformed → skip
        if getattr(b, "type", None) == "text":
            typed.append(text)
        else:
            untyped.append(text)
    return "".join(typed) if typed else "".join(untyped)


# ── Refusals and cut-offs (2026-09-30) ───────────────────────────────────────
# The paid read of objektas_g lost every room's doors: the doors request came
# back with stop_reason "refusal", no content blocks and 5,497 billed input
# tokens. The reader never looked at stop_reason, so it reported only "no JSON
# in response" and the billed tokens were never counted. These helpers let
# every reader name the stop and keep the usage. A refusal is never retried —
# the same request gets the same answer.


class ModelStopped(ValueError):
    """Raised by readers whose failure shape is an exception, when the answer
    was refused or cut off. ``error`` is the short reason ("refused:<category>"
    or "cut_off"); ``_meta`` carries the call's usage for the spend tally.
    A ValueError, so every existing ``except ValueError`` / ``except Exception``
    around those readers still catches it."""

    def __init__(self, error: str, meta: dict | None = None):
        super().__init__(error)
        self.error = error
        self._meta = dict(meta or {})


def stop_error(resp: Any) -> str | None:
    """"refused:<category>" (or "refused" without stop details) on a refusal,
    "cut_off" when the answer hit max_tokens, None otherwise."""
    stop = getattr(resp, "stop_reason", None)
    if stop == "refusal":
        details = getattr(resp, "stop_details", None)
        category = (details.get("category") if isinstance(details, dict)
                    else getattr(details, "category", None))
        return f"refused:{category}" if isinstance(category, str) and category else "refused"
    if stop == "max_tokens":
        return "cut_off"
    return None


def read_answer(resp: Any, *, reader: str, page: Any = None) -> tuple[str, str | None]:
    """The answer's text and ``None``, or ``""`` and the stop reason when the
    answer was refused or cut off (one log line naming the reader, the page
    and the reason)."""
    err = stop_error(resp)
    if err:
        print(f"[{reader}] page {page if page is not None else '-'}: answer {err}")
        return "", err
    return response_text(resp), None


def usage_meta(resp: Any, model: Any) -> dict:
    """The {model, input_tokens, output_tokens} block the readers put in _meta."""
    usage = getattr(resp, "usage", None)
    return {"model": model,
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None)}


def stopped_round_metas(runs: list[dict]) -> list[dict]:
    """Voted readers: the billed usage of rounds that were refused or cut off."""
    return [r["_meta"] for r in runs if r.get("status") != "ok" and r.get("_meta")]


def run_until_refused(read_once: Any, n: int) -> list[dict]:
    """Voted readers: up to n rounds, ending at the first refused round — the
    same request gets the same answer, so asking again only bills it again."""
    runs: list[dict] = []
    for _ in range(max(1, n)):
        runs.append(read_once())
        if str(runs[-1].get("_error") or "").startswith("refused"):
            break
    return runs

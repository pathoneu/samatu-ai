"""One safe way to read text out of an Anthropic response.

`resp.content[0].text` is wrong on any model with extended thinking on by
default: block 0 is a ThinkingBlock, which has no `.text`, so the reader
dies with `'ThinkingBlock' object has no attribute 'text'`. It is
INTERMITTENT — whether a thinking block is emitted varies run to run — so
the same PDF succeeds one minute and degrades the next.

Measured 2026-07-29: the apdailos (išklotinių) reader hit this mid-run on
berzas. It reads per-room wall finishes, so when it dies every room falls
back to paskirtis defaults — the garažas walls (31.45 m² of real paint)
drop out entirely and `Sienų dažomas plotas` lands 31% low. Headline MAE
on that run was 12.996% against 6.116% for the same pipeline with the
reader alive.

Pass-1 and several readers already filtered blocks by type; the ones that
did not are the ones that broke. This is that filter, in one place.
"""
from __future__ import annotations

from typing import Any

__all__ = ["response_text"]


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

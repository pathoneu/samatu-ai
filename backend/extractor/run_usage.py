"""Per-run tally of paid model calls, kept on the side so a run that DIES still
meters what it already paid for (audit follow-up 2026-09-30).

The success path is untouched: the endpoint records the result's own `_meta`
exactly as before. This tally is read only where that `_meta` never reaches
db.record_usage — extract_interior raised, or the stream ended without a done
event — and is written under the existing failed kinds.

Every paid call already reports its usage in one place: _run_pass1_once builds
its `_meta` from resp.usage, and every sub-reader's `_meta` passes through
vision_call._append_extra_call. Both also hand that block to note(). The same
block reported twice (e.g. the room-table pre-pass noted when it returns and
again when it is rolled into extra_calls) counts once.
"""
from __future__ import annotations

import contextvars
import threading

_TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
_CURRENT: contextvars.ContextVar = contextvars.ContextVar("samatu_run_usage", default=None)


class RunUsage:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[int, tuple[dict, dict]] = {}
        # Set by the endpoint once this run's usage row has been written, so a
        # later exception handler never writes a second one.
        self.recorded = False

    def note(self, meta: dict | None) -> None:
        if not isinstance(meta, dict) or not meta.get("model"):
            return
        entry = {"model": meta["model"], **{k: int(meta.get(k) or 0) for k in _TOKEN_KEYS}}
        if not any(entry[k] for k in _TOKEN_KEYS):
            return
        with self._lock:
            # Keyed by the block's identity; holding the block keeps the id unique.
            self._calls.setdefault(id(meta), (meta, entry))

    def meta(self) -> dict:
        """A `_meta` db.record_usage can price: each paid call as one extra_call
        at its own model's rate. Empty dict when nothing was paid."""
        with self._lock:
            calls = [dict(entry) for _meta, entry in self._calls.values()]
        return {"extra_calls": calls} if calls else {}


def current() -> RunUsage | None:
    return _CURRENT.get()


def note(meta: dict | None) -> None:
    usage = _CURRENT.get()
    if usage is not None:
        usage.note(meta)


def run_with(usage: RunUsage | None, fn, *args, **kwargs):
    """Call fn(*args, **kwargs) with `usage` as the current run's tally, in a
    fresh copy of the context (nothing leaks to the caller)."""
    def _call():
        _CURRENT.set(usage)
        return fn(*args, **kwargs)
    return contextvars.copy_context().run(_call)

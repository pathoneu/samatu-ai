"""extractor.stream — bridge sync extract_interior to an event generator (SM01).

The Vision pipeline is sync (synchronous SDK + threaded zoom). To stream
progress events to an HTTP client without an asyncio rewrite, we run the
pipeline on a worker thread and push progress dicts into a thread-safe queue.
A consumer iterates the queue until it sees the sentinel "_eof" event.
"""
from __future__ import annotations

import queue
import threading
from typing import Iterator

from . import run_usage
from .vision_call import extract_interior


_EOF = {"event": "_eof"}


def extract_interior_stream(
    pdf_bytes: bytes,
    rules_override: dict | None = None,
) -> Iterator[dict]:
    """Return the event generator. The run's paid-usage tally is taken from the
    caller NOW (the endpoint binds it with run_usage.run_with), before any
    thread hop — the generator body runs on executor threads that do not see
    the caller's context. A caller that binds none gets a private tally."""
    usage = run_usage.current() or run_usage.RunUsage()
    return _stream(pdf_bytes, rules_override, usage)


def _stream(
    pdf_bytes: bytes,
    rules_override: dict | None,
    usage: run_usage.RunUsage,
) -> Iterator[dict]:
    """Yield progress events while extract_interior runs on a worker thread.

    Sequence (best case):
        rendering_pdf → started → pass1_started → pass1_completed
        → zoom_started → zoom_room_started/completed (×N)
        → zoom_completed → post_processing → done

    On failure: a single `error` event followed by `done` carrying a
    {"status":"error", "_error":...} payload, so the client always sees a
    terminal `done` it can react to. That payload carries the `_meta` of every
    call the run had already paid for, so the endpoint meters it (2026-09-30).
    """
    q: queue.Queue = queue.Queue()

    def cb(ev: dict) -> None:
        q.put(ev)

    def worker() -> None:
        try:
            result = run_usage.run_with(usage, extract_interior, pdf_bytes,
                                        rules_override, progress_cb=cb)
            q.put({"event": "done", "result": result})
        except Exception as exc:
            q.put({"event": "error", "message": str(exc)})
            failed = {"status": "error", "_error": str(exc)}
            paid = usage.meta()
            if paid:
                failed["_meta"] = paid
            q.put({"event": "done", "result": failed})
        finally:
            q.put(_EOF)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        ev = q.get()
        if ev is _EOF or ev.get("event") == "_eof":
            return
        yield ev
        if ev.get("event") == "done":
            # Drain any straggling events emitted between done and _eof.
            try:
                while True:
                    extra = q.get_nowait()
                    if extra is _EOF or extra.get("event") == "_eof":
                        return
            except queue.Empty:
                return

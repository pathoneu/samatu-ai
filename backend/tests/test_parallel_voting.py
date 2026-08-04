"""Pass-1 voting rounds may run concurrently — but must VOTE in round order.

Why this exists (2026-07-29): the three voting rounds are independent, yet ran
strictly one after another. Measured on the 17-page production run that took
1613 s end to end, they were ~220 s each — ~660 s, 41% of the whole extraction,
spent waiting on calls that do not depend on each other.

The danger in fixing that is subtle. If results are collected in COMPLETION
order rather than round order, the vote silently sees a different sequence than
it does today, and `runs[0]` — the base for the voted `_meta` and the target of
the adjacency extra-call append — becomes whichever round happened to finish
first. The numbers would shift for a reason no one could reproduce, because
completion order varies run to run.

So the tests below deliberately make completion order the REVERSE of round
order, and assert the pipeline is unmoved.
"""
from __future__ import annotations

import os
import time

import pytest

from extractor import vision_call as vc


def _mk_run(nr: str, area: float):
    """Minimal parsed-shape dict a voting round returns."""
    return {
        "status": "ok",
        "patalpos": [{"nr": nr, "pavadinimas": f"R{nr}", "plotas_m2": area}],
        "_meta": {"model": "claude-opus-5", "input_tokens": 10, "output_tokens": 5,
                  "cache_read_tokens": 0, "cache_write_tokens": 0},
    }


@pytest.fixture
def staggered(monkeypatch):
    """Round i sleeps (n-i) ticks, so round 0 finishes LAST. Records the order
    calls were issued in and the order they completed in."""
    import threading
    issued, completed = [], []
    lock = threading.Lock()
    counter = {"n": 0}

    def fake_once(client, system, pages, *, native_pdf=None, model=None):
        # The real call carries no per-round argument in the single-model case,
        # so the fake hands out indices itself — under a lock, because in
        # parallel mode several threads arrive here at once and a bare `+= 1`
        # would race and make the whole fixture nondeterministic.
        with lock:
            i = counter["n"]
            counter["n"] += 1
            issued.append(i)
        time.sleep(0.30 - 0.10 * i)      # 0.30, 0.20, 0.10 → completion inverts
        with lock:
            completed.append(i)
        return _mk_run(str(100 + i), 10.0 + i)
    monkeypatch.setattr(vc, "_run_pass1_once", fake_once)
    # Neutralise everything downstream of the rounds themselves.
    monkeypatch.setattr(vc, "_resolve_floor_b64", lambda pages, runs: (None, None))
    return issued, completed


def _run(n=3):
    return vc._run_pass1_voted(object(), [], [], n, lambda ev: None)


def test_parallel_rounds_vote_in_round_order_not_completion_order(monkeypatch, staggered):
    """THE invariant. Completion order here is 2,1,0 — the exact reverse of
    round order — so any code path that trusts completion order produces a
    visibly different `voting_models` sequence."""
    issued, completed = staggered
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.delenv("PARALLEL_VOTING_WARM", raising=False)
    out = _run()

    assert completed == [2, 1, 0], "fixture must invert order or it proves nothing"
    rounds = [r["round"] for r in out["_meta"]["voting_models"]]
    assert rounds == [1, 2, 3], f"vote order leaked from completion order: {rounds}"


def test_parallel_actually_overlaps(monkeypatch, staggered):
    """Concurrency is the whole point: 3 rounds sleeping 0.30/0.20/0.10 take
    ~0.60 s serially and ~0.30 s overlapped."""
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.delenv("PARALLEL_VOTING_WARM", raising=False)
    t0 = time.time()
    _run()
    assert time.time() - t0 < 0.50, "rounds did not overlap"


def test_serial_is_the_default_and_unchanged(monkeypatch, staggered):
    """Flag off → the pre-existing behaviour, round order == issue order."""
    issued, completed = staggered
    monkeypatch.delenv("ENABLE_PARALLEL_VOTING", raising=False)
    t0 = time.time()
    out = _run()
    elapsed = time.time() - t0
    assert issued == [0, 1, 2] and completed == [0, 1, 2]
    assert elapsed >= 0.55, "serial path should NOT overlap"
    assert [r["round"] for r in out["_meta"]["voting_models"]] == [1, 2, 3]


def test_warm_mode_runs_round_one_alone_first(monkeypatch, staggered):
    """Warm mode protects the prompt cache: round 1 must COMPLETE before any
    other round is issued, otherwise every round re-pays the image prefix."""
    issued, completed = staggered
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.setenv("PARALLEL_VOTING_WARM", "1")
    out = _run()
    assert completed[0] == 0, "round 1 must finish before the others start"
    assert [r["round"] for r in out["_meta"]["voting_models"]] == [1, 2, 3]


def test_one_failing_round_is_handled_like_the_serial_path(monkeypatch):
    """A round that raises must degrade to the same 'round failed' bookkeeping
    the serial loop produces — not take the extraction down with it.

    Which ROUND gets the failure is deliberately not asserted: the real call
    carries no per-round argument, so a fake can only count its own
    invocations, and under concurrency the invocation↔round mapping is not
    fixed. The contract worth pinning is what survives — three ordered meta
    entries, exactly one of them an error, and a usable result."""
    import threading
    lock = threading.Lock()
    counter = {"n": 0}

    def fake_once(client, system, pages, *, native_pdf=None, model=None):
        with lock:
            i = counter["n"]
            counter["n"] += 1
        if i == 1:
            raise RuntimeError("boom")
        return _mk_run(str(100 + i), 10.0 + i)

    monkeypatch.setattr(vc, "_run_pass1_once", fake_once)
    monkeypatch.setattr(vc, "_resolve_floor_b64", lambda pages, runs: (None, None))
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")

    out = _run()
    assert out.get("status") != "error", "two good rounds must still produce a result"
    metas = out["_meta"]["voting_models"]
    assert [m["round"] for m in metas] == [1, 2, 3], "round order must survive a failure"
    errored = [m for m in metas if m.get("error")]
    assert len(errored) == 1 and "boom" in str(errored[0]["error"]), metas


def test_all_rounds_failing_still_reports_error(monkeypatch):
    """Unchanged contract: zero usable rounds is an error, not a silent empty."""
    def fake_once(client, system, pages, *, native_pdf=None, model=None):
        raise RuntimeError("nope")
    monkeypatch.setattr(vc, "_run_pass1_once", fake_once)
    monkeypatch.setattr(vc, "_resolve_floor_b64", lambda pages, runs: (None, None))
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    assert _run()["status"] == "error"


def test_document_payload_forces_round_one_solo(monkeypatch):
    """NATIVE-PDF SETTLEMENT: _flip_to_image_fallback mutates the SHARED
    native_pdf dict — fine serially (one rejection flips all later rounds),
    but in full-parallel every round would burn its own document attempts.
    A payload carrying "b64" must therefore force round 1 to run alone even
    WITHOUT warm mode, and the concurrent rounds must each receive their own
    shallow copy so a flip never mutates a dict a sibling thread is reading."""
    import threading
    lock = threading.Lock()
    counter = {"n": 0}
    completed, payload_ids = [], []

    def fake_once(client, system, pages, *, native_pdf=None, model=None):
        with lock:
            i = counter["n"]
            counter["n"] += 1
            payload_ids.append(id(native_pdf))
        time.sleep(0.30 - 0.10 * i)
        with lock:
            completed.append(i)
        return _mk_run(str(100 + i), 10.0 + i)

    monkeypatch.setattr(vc, "_run_pass1_once", fake_once)
    monkeypatch.setattr(vc, "_resolve_floor_b64", lambda pages, runs: (None, None))
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.delenv("PARALLEL_VOTING_WARM", raising=False)

    shared = {"b64": "doc-bytes", "text_median_chars_page": 42}
    out = vc._run_pass1_voted(object(), [], [], 3, lambda ev: None,
                              native_pdf=shared)
    assert out.get("status") != "error"
    # Round 1 settles the document question before anything else launches.
    assert completed[0] == 0, "document payload must force round 1 solo"
    # Round 1 gets the SHARED dict (so its flip propagates); the concurrent
    # rounds get copies — distinct objects from the shared one and each other.
    assert payload_ids[0] == id(shared)
    assert id(shared) not in payload_ids[1:], "concurrent rounds must not share the dict"
    assert payload_ids[1] != payload_ids[2], "each concurrent round gets its own copy"


def test_no_document_payload_keeps_full_parallel(monkeypatch):
    """Without a document payload (the normal production case) full-parallel
    must NOT degrade to solo-first — that would silently halve the win."""
    import threading
    lock = threading.Lock()
    counter = {"n": 0}
    completed = []

    def fake_once(client, system, pages, *, native_pdf=None, model=None):
        with lock:
            i = counter["n"]
            counter["n"] += 1
        time.sleep(0.30 - 0.10 * i)
        with lock:
            completed.append(i)
        return _mk_run(str(100 + i), 10.0 + i)

    monkeypatch.setattr(vc, "_run_pass1_once", fake_once)
    monkeypatch.setattr(vc, "_resolve_floor_b64", lambda pages, runs: (None, None))
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.delenv("PARALLEL_VOTING_WARM", raising=False)
    t0 = time.time()
    vc._run_pass1_voted(object(), [], [], 3, lambda ev: None, native_pdf=None)
    assert time.time() - t0 < 0.50, "no payload → all rounds overlap"
    assert completed == [2, 1, 0]

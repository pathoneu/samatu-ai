"""Telemetry / transport audit (2026-07-28) — T1, T3, T4, T5.

These fixes change NOTHING the model sees; they correct what we RECORD about a
call and bound how many times we make it. Each test below pins one finding so a
future refactor can't silently reintroduce it.

  T1 — pricing charged cache writes at the 1h rate ($10/MTok) the live path
       never uses; the live Pass-1 breakpoints are bare {"type": "ephemeral"}
       = 5m = $6.25/MTok.
  T3 — the adjacency Vision pass was paid but never merged into extra_calls.
  T4 — per-round voting telemetry was gated behind SAMATU_VOTING_MODELS, so
       production could never see which round hit the prompt cache.
  T5 — retry multiplication: SDK max_retries (default 2) multiplied by the
       app-level loop, and the doc->image fallback reset the attempt budget.

No network, no paid calls: every Anthropic client here is a fake that counts
invocations.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402
import pricing  # noqa: E402
from extractor import eksplikacija_reader, prompt, vision_call  # noqa: E402


# ─────────────────────────── fakes (no network) ────────────────────────────

class _CountingClient:
    """Stands in for anthropic.Anthropic. Every .messages.stream() raises and
    increments .calls, so a test can count exactly how many API attempts the
    retry loop would have made."""

    def __init__(self, exc_factory):
        self.calls = 0
        self._exc_factory = exc_factory

    def with_options(self, **_kw):
        return self

    @property
    def messages(self):
        return self

    def stream(self, **_kw):
        self.calls += 1
        raise self._exc_factory(self.calls)


class _FakeBadRequest(anthropic.BadRequestError):
    """anthropic.BadRequestError without the SDK's response/body plumbing —
    isinstance() is all _run_pass1_once checks."""

    def __init__(self):
        Exception.__init__(self, "fake 400 — document payload rejected")


def _pages(n=2):
    return [{"page_index": i, "image_b64": f"fakeb64page{i}"} for i in range(n)]


def _native_pdf():
    return {"b64": "fakepdfb64", "n_pages": 2, "b64_bytes": 4096}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Retry backoff must not make the suite slow."""
    monkeypatch.setattr(vision_call.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(eksplikacija_reader.time, "sleep", lambda *_a, **_k: None)


# ══════════════════════ T5a — Pass-1 attempt budget ════════════════════════

def test_doc_fallback_grants_exactly_one_extra_attempt_budget():
    """The doc->image flip may reset `attempt` at most ONCE per round.

    Budget: 2 document attempts (the 2nd trips doc_failures >= 2 and flips)
    + 3 image attempts = 5 API attempts.

    Honest note: 5 is also what the PRE-fix loop did — the reset was already
    one-shot because _flip_to_image_fallback clears `using_document`. This test
    is a ratchet, not a regression proof: it pins the budget so a future edit
    can't grow it. The measured HTTP reduction came from max_retries=1
    (5 x 3 = 15 HTTP -> 5 x 2 = 10), covered by the client test below."""
    client = _CountingClient(lambda _n: RuntimeError("boom"))
    out = vision_call._run_pass1_once(
        client, system=[{"type": "text", "text": "sys"}], pages=_pages(),
        native_pdf=_native_pdf(), model="claude-opus-4-8",
    )
    assert out["status"] == "error"
    assert client.calls == 5, (
        f"expected 2 doc + 3 image attempts, got {client.calls}")


def test_bad_request_flips_immediately_and_still_caps_the_image_branch():
    """A 400 on the document payload flips on the FIRST failure (no second doc
    attempt), and the image branch still gets its own 3-attempt cap — 4 total."""
    client = _CountingClient(lambda _n: _FakeBadRequest())
    out = vision_call._run_pass1_once(
        client, system=[{"type": "text", "text": "sys"}], pages=_pages(),
        native_pdf=_native_pdf(), model="claude-opus-4-8",
    )
    assert out["status"] == "error"
    assert client.calls == 4, f"expected 1 doc + 3 image attempts, got {client.calls}"


def test_image_only_round_is_capped_at_three_attempts():
    """No document payload → no fallback → the plain 3-attempt cap holds."""
    client = _CountingClient(lambda _n: RuntimeError("boom"))
    out = vision_call._run_pass1_once(
        client, system=[{"type": "text", "text": "sys"}], pages=_pages(),
        native_pdf=None, model="claude-opus-4-8",
    )
    assert out["status"] == "error"
    assert client.calls == 3


def test_pass1_client_is_built_with_bounded_sdk_retries(monkeypatch):
    """extract_interior must not take the SDK's default max_retries=2, which
    multiplies with the app-level loop AND with every sub-reader sharing the
    client (2 x 5 attempts = 10 HTTP calls worst case, not 15-18)."""
    seen: dict = {}

    def _fake_ctor(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(vision_call.anthropic, "Anthropic", _fake_ctor)
    # Garbage bytes: the client is constructed before pdf_to_b64_images runs,
    # so this returns the render error without ever touching the network.
    out = vision_call.extract_interior(b"not a pdf at all")
    assert out["status"] == "error"
    assert seen.get("max_retries") == 1, f"client kwargs were {seen!r}"


# ══════════════════ T5d — sub-reader constructor retry caps ════════════════

def test_every_sub_reader_constructor_bounds_sdk_retries():
    """Modules that CONSTRUCT their own client (rather than receiving the
    shared one) must also cap SDK retries — otherwise each is its own private
    3x multiplier on top of its own retry loop."""
    import re

    bare = re.compile(r"^\s*client\s*=\s*(?:client or )?anthropic\.Anthropic\(\)\s*$")
    offenders = []
    for path in sorted((ROOT / "extractor").rglob("*.py")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if bare.match(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}")
    assert not offenders, (
        "bare anthropic.Anthropic() constructors (need max_retries=1): "
        + ", ".join(offenders))


# ═════════════ T5b/T5c — eksplikacija: deterministic stop reasons ══════════

def test_eksplikacija_does_not_retry_deterministic_stop_reasons():
    """`refusal` and `max_tokens` are deterministic for an unchanged payload —
    retrying re-sends byte-identical input and re-pays for the same answer."""
    src = inspect.getsource(eksplikacija_reader)
    block = src.split('if resp.stop_reason in ("refusal", "max_tokens"):')[1][:400]
    assert "break" in block.split("\n")[3] or "break" in block[:200], (
        "refusal/max_tokens must break immediately, not sleep-and-continue")
    assert "continue" not in block[:200], (
        "found a `continue` in the deterministic stop-reason branch — that is "
        "the retry-and-re-pay path this fix removed")


def test_eksplikacija_user_content_has_a_cache_breakpoint():
    """The system prompt was cached but the heavy image payload was not, so a
    genuine transient retry re-sent every page at full price."""
    content = eksplikacija_reader._build_user_content(_pages(3))
    breakpoints = [b for b in content if b.get("cache_control")]
    assert len(breakpoints) == 1, "expected exactly one breakpoint"
    assert breakpoints[0]["type"] == "image", "breakpoint belongs on the image prefix"
    assert breakpoints[0] is content[-1], "breakpoint must close the stable prefix"


def test_eksplikacija_breakpoint_is_stable_across_identical_payloads():
    """Cache hits require byte-identical content — the builder must be pure."""
    assert eksplikacija_reader._build_user_content(_pages(3)) == \
        eksplikacija_reader._build_user_content(_pages(3))


def test_eksplikacija_no_pages_does_not_crash_the_breakpoint():
    content = eksplikacija_reader._build_user_content([])
    assert not [b for b in content if b.get("cache_control")]


# ══════════════════════ T1 — cache TTL / pricing honesty ═══════════════════

def test_pricing_defaults_to_the_ttl_the_live_path_actually_sends():
    """Bare {"type": "ephemeral"} is a 5-minute TTL per the Anthropic API, so
    cache writes bill at 1.25x input, not the 2x the old "1h" default charged."""
    assert inspect.signature(pricing.calc_claude_cost_usd).parameters[
        "cache_ttl"].default == "5m"
    assert inspect.signature(pricing.calc_meta_cost_usd).parameters[
        "cache_ttl"].default == "5m"
    # opus-4-8 input $5/MTok → 5m write = $6.25/MTok, 1h write = $10/MTok
    assert pricing.calc_claude_cost_usd(cache_write_tokens=1_000_000) == \
        pytest.approx(6.25)
    assert pricing.calc_claude_cost_usd(
        cache_write_tokens=1_000_000, cache_ttl="1h") == pytest.approx(10.0)


def test_live_pass1_breakpoints_are_bare_ephemeral():
    """If any of these ever grows an explicit ttl, the pricing default above
    becomes wrong — this test is the tripwire that links the two."""
    img = prompt.build_user_content(_pages(2))
    doc = prompt.build_user_content_pdf_native("b64", 2)
    sys_block_src = inspect.getsource(vision_call.extract_interior)

    for block in [b for b in img + doc if b.get("cache_control")]:
        assert block["cache_control"] == {"type": "ephemeral"}, (
            f"{block['type']} block now sets an explicit ttl — update "
            "pricing.calc_claude_cost_usd's default to match")
    assert '"cache_control": {"type": "ephemeral"}' in sys_block_src


def test_extra_calls_costing_is_publicly_reusable():
    """T2 needs the extra-calls slice on its own (to store it), and it must be
    the SAME helper the total uses — never a second, drifting estimate."""
    meta = {"model": "claude-opus-4-8", "input_tokens": 1_000,
            "extra_calls": [{"model": "claude-opus-4-8", "input_tokens": 2_000,
                             "output_tokens": 100}]}
    extra = pricing.calc_extra_calls_cost_usd(meta)
    total = pricing.calc_meta_cost_usd(meta)
    base = pricing.calc_claude_cost_usd(input_tokens=1_000, model="claude-opus-4-8")
    assert extra > 0
    assert total == pytest.approx(base + extra)
    assert pricing._calc_extra_calls_cost_usd is pricing.calc_extra_calls_cost_usd


# ══════════════════════ T3 — adjacency pass is metered ═════════════════════

class _FakeAdj:
    _meta = {"cache": "miss", "model": "claude-opus-4-8",
             "input_tokens": 3_000, "output_tokens": 250}


def _stub_pass1(monkeypatch, metas):
    """Make _run_pass1_once return canned rounds — no network."""
    seq = list(metas)

    def _fake(client, system, pages, *, native_pdf=None, model=None):
        m = seq.pop(0)
        return {"patalpos": [{"nr": "101", "pavadinimas": "Kambarys"}], "_meta": dict(m)}

    monkeypatch.setattr(vision_call, "_run_pass1_once", _fake)


def _stub_adjacency(monkeypatch, adj=_FakeAdj()):
    import extractor.vision.adjacency_extractor as ax
    monkeypatch.setattr(ax, "extract_adjacency", lambda **_k: adj)
    monkeypatch.setattr(ax, "apply_adjacency_to_rooms",
                        lambda *_a, **_k: {"n_rooms_matched": 1})


_ROUND = {"model": "claude-opus-4-8", "input_tokens": 20_000, "output_tokens": 2_000,
          "cache_read_tokens": 15_000, "cache_write_tokens": 5_000}


def test_adjacency_pass_lands_in_extra_calls(monkeypatch):
    """It is a real, paid, once-per-extraction Vision call. Before the fix its
    usage was captured on the result and then dropped on the floor."""
    _stub_pass1(monkeypatch, [_ROUND])
    _stub_adjacency(monkeypatch)
    out = vision_call._run_pass1_voted(
        object(), system=[], pages=_pages(1), n=1, _emit=lambda _e: None)

    calls = out["_meta"]["extra_calls"]
    adj = [c for c in calls if c.get("reader") == "adjacency"]
    assert len(adj) == 1, f"adjacency not metered: {calls!r}"
    assert adj[0]["input_tokens"] == 3_000 and adj[0]["output_tokens"] == 250
    # ...and it actually moves the recorded euro figure
    assert pricing.calc_meta_cost_usd(out["_meta"]) > pricing.calc_claude_cost_usd(
        **{k: v for k, v in _ROUND.items() if k != "model"}, model="claude-opus-4-8")


def test_cached_adjacency_costs_nothing_and_is_not_metered(monkeypatch):
    """A cache HIT carries no tokens — recording it would inflate the bill."""
    class _Hit:
        _meta = {"cache": "hit", "model": "claude-opus-4-8"}

    _stub_pass1(monkeypatch, [_ROUND])
    _stub_adjacency(monkeypatch, _Hit())
    out = vision_call._run_pass1_voted(
        object(), system=[], pages=_pages(1), n=1, _emit=lambda _e: None)
    assert not [c for c in (out["_meta"].get("extra_calls") or [])
                if c.get("reader") == "adjacency"]


def test_adjacency_failure_still_returns_a_usable_extraction(monkeypatch):
    """Metering must never be able to break an extraction."""
    import extractor.vision.adjacency_extractor as ax
    _stub_pass1(monkeypatch, [_ROUND])
    monkeypatch.setattr(ax, "extract_adjacency",
                        lambda **_k: (_ for _ in ()).throw(RuntimeError("no")))
    out = vision_call._run_pass1_voted(
        object(), system=[], pages=_pages(1), n=1, _emit=lambda _e: None)
    assert out.get("patalpos")


# ═══════════════ T4 — per-round telemetry outside the experiment ═══════════

def test_per_round_meta_is_populated_without_the_experiment_flag(monkeypatch):
    """SAMATU_VOTING_MODELS is unset in production, so this data used to be
    unreachable — exactly the signal needed to spot a cache regression."""
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    _stub_pass1(monkeypatch, [_ROUND])
    _stub_adjacency(monkeypatch)
    out = vision_call._run_pass1_voted(
        object(), system=[], pages=_pages(1), n=1, _emit=lambda _e: None)

    rounds = out["_meta"]["voting_models"]
    assert len(rounds) == 1
    assert rounds[0]["cache_read_tokens"] == 15_000
    assert rounds[0]["cache_write_tokens"] == 5_000
    assert rounds[0]["model"] == "claude-opus-4-8"
    assert out["_meta"]["voting_cost_usd"] > 0
    # the experiment-only provenance block stays experiment-only
    assert "mixed_vote" not in (out["_meta"].get("experiment") or {})


def test_attaching_voting_models_does_not_change_the_billed_amount():
    """calc_meta_cost_usd switches to a per-round branch when voting_models is
    present. Cost is linear in tokens, so for a single-model run the per-round
    sum must equal pricing the summed tokens — otherwise T4 would silently
    re-price every production extraction."""
    rounds = [dict(_ROUND, round=i + 1) for i in range(3)]
    summed = {k: sum(int(r[k] or 0) for r in rounds)
              for k in ("input_tokens", "output_tokens",
                        "cache_read_tokens", "cache_write_tokens")}

    without = pricing.calc_meta_cost_usd({**summed, "model": "claude-opus-4-8"})
    with_rounds = pricing.calc_meta_cost_usd(
        {**summed, "model": "claude-opus-4-8", "voting_models": rounds})
    assert with_rounds == pytest.approx(without)


def test_failed_rounds_are_recorded_but_never_billed(monkeypatch):
    """An errored round has no tokens to charge for; it is telemetry only."""
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    seq = [{"status": "error", "_error": "vision_call_failed: boom"},
           {"patalpos": [{"nr": "101"}], "_meta": dict(_ROUND)}]

    def _fake(client, system, pages, *, native_pdf=None, model=None):
        return seq.pop(0)

    monkeypatch.setattr(vision_call, "_run_pass1_once", _fake)
    _stub_adjacency(monkeypatch)
    out = vision_call._run_pass1_voted(
        object(), system=[], pages=_pages(1), n=2, _emit=lambda _e: None)

    rounds = out["_meta"]["voting_models"]
    assert len(rounds) == 2
    assert rounds[0]["error"].startswith("vision_call_failed")
    priced = [r for r in rounds if r.get("model") and not r.get("error")]
    assert len(priced) == 1


# ════════ T5e (2026-07-28 batch 2) — modules with their OWN retry loop ═════
# The three readers below run their own attempt loop AND call through a client
# built with max_retries=1, so the two policies MULTIPLIED: 3 attempts became
# up to 6 HTTP calls (2 x 2 = 4 for material_specs). Each must now disable the
# SDK retry for the duration of its loop via client.with_options(max_retries=0).

class _OptionsRecordingClient:
    """Records the max_retries passed to with_options and counts attempts."""

    def __init__(self):
        self.calls = 0
        self.with_options_kwargs: list[dict] = []

    def with_options(self, **kw):
        self.with_options_kwargs.append(kw)
        return self

    @property
    def messages(self):
        return self

    def stream(self, **_kw):
        self.calls += 1
        raise RuntimeError("boom")


def test_eksplikacija_disables_the_sdk_retry_inside_its_own_loop(monkeypatch):
    monkeypatch.setattr(eksplikacija_reader, "pdf_to_b64_images",
                        lambda *a, **kw: [{"page_index": 0, "image_b64": "x"}])
    c = _OptionsRecordingClient()
    out = eksplikacija_reader.read_eksplikacija(b"%PDF-1.4 not really", c)
    assert out.get("_error"), out                      # every attempt failed
    assert c.with_options_kwargs, "read_eksplikacija never called with_options"
    assert c.with_options_kwargs[0].get("max_retries") == 0, c.with_options_kwargs
    assert c.calls == 3, f"expected exactly 3 attempts, got {c.calls}"


def test_wall_elevation_disables_the_sdk_retry_inside_its_own_loop(monkeypatch):
    from extractor import wall_elevation as we
    monkeypatch.setattr(we.time, "sleep", lambda *_a, **_k: None)
    c = _OptionsRecordingClient()
    assert we._extract_one_page("fakeb64", 0, c) is None    # all attempts failed
    assert c.with_options_kwargs, "_extract_one_page never called with_options"
    assert c.with_options_kwargs[0].get("max_retries") == 0, c.with_options_kwargs
    assert c.calls == 3, f"expected exactly 3 attempts, got {c.calls}"


def test_material_specs_disables_the_sdk_retry_inside_its_own_loop(monkeypatch):
    from extractor import material_specs as ms
    monkeypatch.setattr(ms.time, "sleep", lambda *_a, **_k: None)
    # Stub the renderer: this test is about the transport policy, not poppler.
    import pdf2image

    class _Img:
        size = (100, 100)

        def resize(self, *_a):
            return self

        def save(self, buf, **_kw):
            buf.write(b"jpegbytes")
    monkeypatch.setattr(pdf2image, "convert_from_bytes",
                        lambda *a, **kw: [_Img()])

    c = _OptionsRecordingClient()
    out = ms.extract_room_material_specs(
        b"%PDF-1.4 fake", [3], "Vonia", client=c)
    assert out.get("_error"), out
    assert c.with_options_kwargs[0].get("max_retries") == 0, c.with_options_kwargs
    assert c.calls == 2, f"expected exactly 2 attempts, got {c.calls}"


def test_with_options_preserves_transport_settings_in_this_sdk():
    """The fix relies on with_options being `copy` — verify against the INSTALLED
    anthropic (0.95.0), not from memory: same base_url/timeout/default headers
    and the same httpx client, only max_retries changed."""
    c = anthropic.Anthropic(api_key="sk-ant-test", max_retries=1,
                            default_headers={"x-pathon": "1"}, timeout=42.0)
    c2 = c.with_options(max_retries=0)
    assert c2.max_retries == 0 and c.max_retries == 1     # original untouched
    assert c2.base_url == c.base_url
    assert c2.timeout == c.timeout
    assert c2.default_headers.get("x-pathon") == "1"
    assert c2._client is c._client                        # shared connection pool

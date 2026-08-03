"""The apdailos reader must not fail silently or intermittently (2026-07-29).

ROOT CAUSE of the intermittent degradation: `MAX_TOKENS = 4096` was too snug.
Opus 5 runs extended thinking BY DEFAULT and thinking counts against the same
cap, so a ~2 400-token answer plus a variable-length thinking block was a coin
flip. Four paid runs of the byte-identical berzas PDF:

    10:11  0/11 rooms  ThinkingBlock crash (fixed in 0c258e9)
    10:38 11/11 rooms  output_tokens = 2 776 of 4 096  ← thinking was short
    12:03  0/11 rooms  "Expecting ',' delimiter ... char 3 664"
    12:26  0/11 rooms  "Expecting ',' delimiter ... char 4 789"

The full answer is 6 344 chars, so 12:03 and 12:26 were cut off at 58% and 79%
of the SAME body — truncation, not a model formatting quirk. Page selection was
identical in all four runs (ruled out separately, and re-asserted below).

Every test here is offline: no network, no API key, stub clients only.
"""
import json
import types

import anthropic
import httpx
import pytest

import extractor.apdailos_reader as ar
from extractor.apdailos_reader import (
    MAX_ATTEMPTS, MAX_TOKENS, merge_apdailos_into_rooms, read_apdailos_finishes,
    _is_retryable, _salvage_patalpos)


# ── helpers ────────────────────────────────────────────────────────────────

ROOMS = [{"nr": "101", "pavadinimas": "Tambūras", "plotas_m2": 5.0},
         {"nr": "105", "pavadinimas": "Garažas", "plotas_m2": 30.0}]

# Captured before the autouse stub replaces it — the page-determinism test
# must exercise the REAL scanner.
_REAL_FIND_PAGES = ar._find_apdailos_pages


def _answer(n_rooms: int) -> str:
    """A well-formed reader answer for the first `n_rooms` of ROOMS."""
    return json.dumps({"patalpos": [
        {"nr": r["nr"], "pavadinimas": r["pavadinimas"],
         "sienu_apdaila": {"dazymas_share": 1.0, "plyteles_share": 0.0},
         "plyteliu_aukstis_m": None, "pastabos": "dažoma"}
        for r in ROOMS[:n_rooms]]}, ensure_ascii=False, indent=2)


def _resp(text: str, stop_reason: str = "end_turn", *, thinking: bool = True):
    """A response shaped like the SDK's: ThinkingBlock first, then text."""
    blocks = []
    if thinking:
        blocks.append(types.SimpleNamespace(type="thinking", thinking="hmm"))
    blocks.append(types.SimpleNamespace(type="text", text=text))
    return types.SimpleNamespace(
        content=blocks, stop_reason=stop_reason,
        usage=types.SimpleNamespace(input_tokens=58355, output_tokens=2776,
                                    cache_read_input_tokens=0,
                                    cache_creation_input_tokens=0))


class _Client:
    """Stub Anthropic client: replays a scripted list of responses/exceptions."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.max_tokens_seen = []
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        self.max_tokens_seen.append(kw.get("max_tokens"))
        item = self._script.pop(0) if self._script else self._script_last
        self._script_last = item
        if isinstance(item, Exception):
            raise item
        return item


def _conn_error():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message="connection reset", request=req)


def _bad_request():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError("bad payload",
                                     response=httpx.Response(400, request=req),
                                     body=None)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(ar, "RETRY_SLEEP_S", 0)


@pytest.fixture(autouse=True)
def _one_page(monkeypatch):
    """Skip pdfplumber/pdf2image: pretend page 4 renders."""
    monkeypatch.setattr(ar, "_find_apdailos_pages", lambda _b: [4])
    monkeypatch.setattr(ar, "_render_page_b64", lambda *_a, **_k: "QUJD")


# ── 1. the cap (the root cause) ────────────────────────────────────────────

def test_max_tokens_has_room_for_thinking_plus_the_answer():
    """4096 truncated 3 of 4 paid runs. The answer alone is ~2 400 tokens and
    thinking is unbounded-ish, so the cap must carry real headroom. Caps are
    free — billing is by actuals."""
    assert MAX_TOKENS >= 16384, (
        "regression: a snug cap silently truncates this reader's JSON and "
        "every room falls back to paskirtis defaults")


def test_cap_stays_under_the_sdk_non_streaming_ceiling():
    """The other cliff: this is a NON-STREAMING call, and the SDK raises
    ValueError client-side for a cap it predicts exceeds 10 minutes. Landing
    there would degrade the reader before any HTTP call — the same silent
    failure from a new cause. Verified against the real SDK function."""
    client = anthropic.Anthropic(api_key="sk-ant-offline-not-used")
    client._calculate_nonstreaming_timeout(MAX_TOKENS, None)   # must not raise
    with pytest.raises(ValueError, match="Streaming is required"):
        client._calculate_nonstreaming_timeout(ar.MAX_TOKENS_NONSTREAMING_CEILING + 1, None)


def test_the_configured_cap_is_the_one_actually_sent():
    client = _Client([_resp(_answer(2))])
    read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert client.max_tokens_seen == [MAX_TOKENS]


# ── 2. page selection is deterministic (the ruled-out alternative) ─────────

def test_page_pick_is_deterministic_for_identical_input(monkeypatch):
    class _Page:
        def __init__(self, t): self._t = t
        def extract_text(self): return self._t

    class _Pdf:
        def __init__(self, pages): self.pages = pages
        def __enter__(self): return self
        def __exit__(self, *a): return False

    pages = [_Page("TITULINIS"), _Page("VIZUALIZACIJA"),
             _Page("GRINDŲ APDAILOS PLANAS"), _Page("SIENŲ IŠKLOTINĖS L1"),
             _Page("SIENŲ IŠKLOTINĖS L2")]
    # Seam moved 2026-08-03: the page locator reads the shared parse in
    # extractor.pdf_page_cache rather than opening its own document. The
    # determinism contract under test is unchanged.
    monkeypatch.setattr("extractor.pdf_page_cache.page_texts",
                        lambda *_a, **_k: [p.extract_text() for p in pages])
    runs = [_REAL_FIND_PAGES(b"x") for _ in range(10)]
    assert all(r == runs[0] for r in runs)
    assert runs[0] == [4, 5, 3]  # išklotinės (prio 0) before the generic plan


# ── 3. transient failures retry; deterministic ones do not ────────────────

def test_transient_error_retries_and_succeeds():
    client = _Client([_conn_error(), _resp(_answer(2))])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "ok"
    assert client.calls == 2
    assert len(out["patalpos"]) == 2
    attempts = out["_meta"]["attempts"]
    assert [a["outcome"] for a in attempts] == ["exception", "response"]
    assert attempts[0]["error_class"] == "APIConnectionError"


def test_retries_are_bounded_and_every_attempt_is_recorded():
    client = _Client([_conn_error()] * 5)
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "error"
    assert client.calls == MAX_ATTEMPTS == 3
    assert len(out["_meta"]["attempts"]) == 3
    assert out["_meta"]["error_class"] == "APIConnectionError"
    assert "APIConnectionError" not in (out.get("patalpos") or [])


def test_deterministic_error_is_not_retried():
    """A 400 will fail identically forever — retrying it only burns time."""
    client = _Client([_bad_request()] * 3)
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "error"
    assert client.calls == 1
    assert out["_meta"]["attempts"][0]["retryable"] is False


def test_is_retryable_classifies_status_codes():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    overloaded = anthropic.APIStatusError(
        "overloaded", response=httpx.Response(529, request=req), body=None)
    rate = anthropic.RateLimitError(
        "slow down", response=httpx.Response(429, request=req), body=None)
    assert _is_retryable(overloaded) and _is_retryable(rate)
    assert _is_retryable(_conn_error())
    assert not _is_retryable(_bad_request())
    assert not _is_retryable(ValueError("bug in our own code"))


# ── 4. truncation: salvage what arrived, flag the rest ────────────────────

TRUNCATED = _answer(2)[:_answer(2).index('"105"') + 40]   # dies mid-room-2


def test_salvage_recovers_every_complete_room_from_a_cut_body():
    got = _salvage_patalpos(TRUNCATED)
    assert [p["nr"] for p in got] == ["101"]


def test_truncated_response_is_partial_not_a_total_loss():
    client = _Client([_resp(TRUNCATED, stop_reason="max_tokens")])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "partial", "8/11 rooms beats 0/11"
    assert [p["nr"] for p in out["patalpos"]] == ["101"]
    assert out["_meta"]["truncated"] is True
    assert out["_meta"]["stop_reason"] == "max_tokens"
    assert out["_error"], "a partial read must carry its reason"


def test_truncated_response_with_nothing_salvageable_is_a_loud_error():
    client = _Client([_resp('{"patalpos": [', stop_reason="max_tokens")])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "error"
    assert out["_meta"]["truncated"] is True
    assert str(MAX_TOKENS) in out["_error"]


def test_refusal_is_named_not_swallowed_as_a_parse_error():
    client = _Client([_resp("", stop_reason="refusal")])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "error"
    assert "refusal" in out["_error"]
    assert out["_meta"]["stop_reason"] == "refusal"


def test_a_billed_failure_still_reports_its_tokens():
    """A truncated call burned 16k output tokens. Not metering it hides a real
    euro (a709250: every recorded euro honest)."""
    client = _Client([_resp(TRUNCATED, stop_reason="max_tokens")])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["_meta"]["input_tokens"] == 58355
    assert out["_meta"]["output_tokens"] == 2776
    assert out["_meta"]["model"]


def test_thinking_block_does_not_break_the_read():
    """The 10:11 failure mode: block 0 is a ThinkingBlock with no .text."""
    client = _Client([_resp(_answer(2), thinking=True)])
    out = read_apdailos_finishes(b"pdf", ROOMS, client=client)
    assert out["status"] == "ok" and len(out["patalpos"]) == 2


# ── 5. the disclosure must survive every one of the above ─────────────────

def test_partial_merge_leaves_unread_rooms_visibly_unread():
    """NON-NEGOTIABLE: salvaging some rooms must not make the others LOOK read.
    A room with no breakdown still carries its `_wall_finish_assumptions` text,
    and a wet room still reports `_tile_read_missing`."""
    from extractor.universal_rules import calc_room_quantities

    def _room(nr, paskirtis):
        return {"nr": nr, "pavadinimas": paskirtis.title(), "paskirtis": paskirtis,
                "plotas_m2": 16.0, "perimetras_m": 16.0, "lubu_aukstis_m": 2.8,
                "elementai": []}

    rooms = [_room("101", "tamburas"), _room("105", "garazas"), _room("106", "vonia")]
    n = merge_apdailos_into_rooms(rooms, {
        "status": "partial",
        "patalpos": [{"nr": "101",
                      "sienu_apdaila": {"dazymas_share": 1.0, "plyteles_share": 0.0},
                      "plyteliu_aukstis_m": None, "pastabos": "dažoma"}]})
    assert n == 1, "the salvaged room IS merged (partial is not discarded)"
    read = calc_room_quantities(rooms[0])
    unread_dry = calc_room_quantities(rooms[1])
    unread_wet = calc_room_quantities(rooms[2])
    assert float(read["walls_paintable_m2"]) > 20.0            # recovered
    assert unread_dry["_walls_paint_factor"] == 0.0            # still the default
    assert unread_dry["_wall_finish_assumptions"]              # …and it says so
    assert "apdailos duomen" in unread_dry["_wall_finish_assumptions"][0]
    assert unread_wet["_tile_read_missing"] is True            # tile band assumed
    assert unread_wet["_wall_finish_assumptions"]


def test_call_site_records_the_failure_in_meta_and_still_warns():
    """The post-mortem hole: a failed reader used to leave NO `_meta.apdailos_*`
    at all, so the run artifact was indistinguishable from one where the reader
    never existed."""
    from extractor.vision_call import _record_apdailos_meta, _warn_apdailos_degraded

    parsed: dict = {}
    _record_apdailos_meta(parsed, {
        "status": "error", "page": 4, "pages": [4, 5],
        "_error": "safety refusal (stop_reason=refusal)", "_elapsed_s": 12.3,
        "_meta": {"stop_reason": "refusal", "max_tokens": MAX_TOKENS,
                  "attempts": [{"attempt": 1, "outcome": "response",
                                "stop_reason": "refusal"}],
                  "error_class": "APIStatusError", "output_tokens": 900},
    }, 0)
    _warn_apdailos_degraded(parsed, "safety refusal (stop_reason=refusal)")

    m = parsed["_meta"]
    assert m["apdailos_status"] == "error"
    assert m["apdailos_rooms_updated"] == 0        # present, not absent
    assert m["apdailos_stop_reason"] == "refusal"
    assert m["apdailos_error_class"] == "APIStatusError"
    assert m["apdailos_attempts"] and m["apdailos_max_tokens"] == MAX_TOKENS
    assert m["apdailos_pages"] == [4, 5]
    assert any("nenuskaitytas" in w["message"] for w in parsed["warnings"])


def test_partial_warning_says_partial():
    from extractor.vision_call import _warn_apdailos_degraded

    parsed: dict = {}
    _warn_apdailos_degraded(parsed, "atsakymas nutrūko", partial=True)
    msg = parsed["warnings"][0]["message"]
    assert "iš dalies" in msg and "paskirties standartus" in msg

"""The adjacency pass: a cut-off answer is asked again, and the rooms are never
left without partition walls in silence (2026-10-07).

Both paid production runs of objektas_a on 2026-10-07 had the room-adjacency
answer cut off at its 8 192-token cap (the model thinks by default and the
thinking counts against the cap; 6 334 tokens had fitted the day before). The
reader raised, the pipeline printed one line and moved on: no room got
`n_partition_walls`, the „pertvarų sandūros" term of the corner metres was 0
everywhere, and „Dažymo kampų montavimas" fell from 465,58 to ~370 m (true
493,35) with nothing on screen.

Now:
  * the first cap is 32 768; an answer cut off at it is asked ONCE more with
    64 000, and both answers' usage is metered (extra_calls and the run's side
    tally); a refusal is never asked again;
  * whatever leaves the rooms without partition walls — a refusal, a second
    cut-off, an unreadable answer, no floor page, no room matched, Pass-1
    without voting — adds one plain-LT warning to the list the screen reads.

No Anthropic call: every client below is a stub. The two end-to-end cases run
production's `extract_interior` on objektas_h through the golden replay
(tests/golden_replay.py) with the adjacency answers replaced, and skip when
that material is not on this machine.
"""
from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import os
import sys
import types
from pathlib import Path

import pytest

from extractor import run_usage
from extractor import vision_call as vc
from extractor.response_text import ModelStopped
from extractor.user_text import is_banned
from extractor.vision import adjacency_extractor as ax
from extractor.vision._cache import VisionCache, cache_key

MODEL = "claude-test"
# Two rooms sharing one wall — the answer the reader parses.
ANSWER = {"rooms": [
    {"room_name": "Svetainė", "room_nr": "101", "exterior_wall_count": 2,
     "adjacent_rooms": [{"to_room": "Virtuvė", "to_room_nr": "102",
                         "shared_wall_count": 1, "wall_types": ["interior_partition"]}],
     "confidence": "high", "evidence": "rytinė siena bendra su virtuve"},
    {"room_name": "Virtuvė", "room_nr": "102", "exterior_wall_count": 1,
     "adjacent_rooms": [{"to_room": "Svetainė", "to_room_nr": "101",
                         "shared_wall_count": 1, "wall_types": ["interior_partition"]}],
     "confidence": "high", "evidence": "vakarinė siena bendra su svetaine"},
]}


# ── stubs ─────────────────────────────────────────────────────────────────────

def _resp(text: str, stop: str = "end_turn", i: int = 3_000, o: int = 2_500, category=None):
    details = types.SimpleNamespace(category=category, type="refusal") if category else None
    content = [] if stop == "refusal" else [
        types.SimpleNamespace(type="thinking", thinking=""),
        types.SimpleNamespace(type="text", text=text)]
    return types.SimpleNamespace(content=content, stop_reason=stop, stop_details=details,
                                 usage=types.SimpleNamespace(input_tokens=i, output_tokens=o))


def _ok(i=3_000, o=2_500):
    return _resp(json.dumps(ANSWER, ensure_ascii=False), i=i, o=o)


def _cut_off(o=ax.MAX_TOKENS, i=3_000):
    return _resp('{"rooms": [{"room_name": "Svetainė", "room_nr": "10', "max_tokens", i=i, o=o)


def _refusal():
    return _resp("", "refusal", i=5_497, o=0, category="reasoning_extraction")


class _Client:
    """messages.stream stub: answers the queued responses in order (an
    Exception in the queue is raised instead) and keeps every request."""

    def __init__(self, *answers):
        self._queue = list(answers)
        self.requests: list[dict] = []
        self.messages = self

    def stream(self, **kw):
        self.requests.append(kw)
        answer = self._queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer

        class _Ctx:
            def __enter__(self_inner):
                return types.SimpleNamespace(get_final_message=lambda: answer)

            def __exit__(self_inner, *a):
                return False
        return _Ctx()

    @property
    def caps(self) -> list[int]:
        return [r["max_tokens"] for r in self.requests]


def _png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Every VisionCache the readers build lands in this test's own directory —
    never the developer's .vision_cache (golden_replay.install does the same)."""
    monkeypatch.setattr(VisionCache.__init__, "__defaults__", (tmp_path, "default"))
    monkeypatch.setenv("SAMATU_MODEL_VISION_PASS1", MODEL)
    return tmp_path


def _room(nr: str, name: str) -> dict:
    return {"nr": nr, "pavadinimas": name, "paskirtis": "gyvenamoji", "puslapio_nr": 1,
            "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7, "elementai": []}


def _voted(monkeypatch, client, *, n=3, pages=None):
    """`_run_pass1_voted` with n identical Pass-1 rounds and the REAL adjacency
    reader on `client`, inside a side tally of its own."""
    def _round(*_a, **_k):
        return {"patalpos": [_room("101", "Svetainė"), _room("102", "Virtuvė")],
                "scale_source_page": 1, "detected_symbols_summary": {},
                "_meta": {"model": MODEL, "input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr(vc, "_run_pass1_once", _round)
    if pages is None:
        pages = [{"page_index": 1, "image_b64": _png_b64()}]
    usage = run_usage.RunUsage()
    out = run_usage.run_with(usage, vc._run_pass1_voted, client, [], pages, n,
                             lambda _e: None)
    return out, usage


def _adjacency_calls(out: dict) -> list[tuple]:
    return [(c["input_tokens"], c["output_tokens"])
            for c in (out.get("_meta") or {}).get("extra_calls") or []
            if c.get("reader") == "adjacency"]


def _partition_walls(out: dict) -> dict:
    return {r["nr"]: r.get("n_partition_walls") for r in out["patalpos"]}


def _our_warnings(parsed: dict) -> list[dict]:
    return [w for w in parsed.get("warnings") or []
            if isinstance(w, dict) and w.get("code") == vc.PARTITION_WALLS_UNREAD_CODE]


# ── the cap ───────────────────────────────────────────────────────────────────

def test_the_cap_has_room_for_thinking_and_the_retry_has_more():
    # 8 192 was cut off twice on 2026-10-07 (6 334 fitted the day before); the
    # answer itself is ~2-3k tokens, the rest is the model's thinking.
    assert ax.MAX_TOKENS >= 32_768
    assert ax.RETRY_MAX_TOKENS > ax.MAX_TOKENS
    assert ax.RETRY_MAX_TOKENS <= 64_000   # every 64k-output model can take it


def test_one_answer_asks_once_at_the_cap_and_reports_exactly_its_usage(cache_dir):
    client = _Client(_ok())
    out = ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert client.caps == [ax.MAX_TOKENS]
    assert out._meta == {"cache": "miss", "key": out._meta["key"], "model": MODEL,
                         "input_tokens": 3_000, "output_tokens": 2_500}
    assert {r.room_nr: r.n_partition_walls for r in out.rooms} == {"101": 1, "102": 1}


# ── a cut-off answer is asked once more ──────────────────────────────────────

def test_cut_off_once_is_asked_again_with_more_room_and_both_answers_are_billed(cache_dir):
    client = _Client(_cut_off(i=3_000, o=ax.MAX_TOKENS), _ok(i=3_100, o=9_000))
    out = ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert client.caps == [ax.MAX_TOKENS, ax.RETRY_MAX_TOKENS]
    assert {r.room_nr: r.n_partition_walls for r in out.rooms} == {"101": 1, "102": 1}
    assert (out._meta["input_tokens"], out._meta["output_tokens"]) == (6_100, ax.MAX_TOKENS + 9_000)
    (cut,) = out._meta["truncated_attempts"]
    assert (cut["max_tokens"], cut["output_tokens"], cut["stop_reason"]) == \
        (ax.MAX_TOKENS, ax.MAX_TOKENS, "max_tokens")

    # the answer is kept under the first cap's key: the next run of the page is free
    again = _Client()
    hit = ax.extract_adjacency(image_b64=_png_b64(), client=again)
    assert again.requests == [] and hit._meta["cache"] == "hit"
    assert {r.room_nr: r.n_partition_walls for r in hit.rooms} == {"101": 1, "102": 1}


def test_an_answer_kept_under_the_old_cap_is_not_reused(cache_dir):
    """The cap is part of the cache key: an entry written under 8 192 is a miss
    (one paid call), never served as if it were this request's answer."""
    img = _png_b64()
    old_key = cache_key(base64.b64decode(img), ax._load_prompt(), MODEL, "8192")
    VisionCache(namespace="room_adjacency").put(old_key, {"rooms": []})
    client = _Client(_ok())
    out = ax.extract_adjacency(image_b64=img, client=client)
    assert len(client.requests) == 1 and out._meta["cache"] == "miss"
    assert len(out.rooms) == 2


def test_cut_off_twice_raises_with_both_answers_usage_and_caches_nothing(cache_dir):
    client = _Client(_cut_off(i=3_000, o=ax.MAX_TOKENS), _cut_off(i=3_000, o=ax.RETRY_MAX_TOKENS))
    with pytest.raises(ModelStopped) as ei:
        ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert client.caps == [ax.MAX_TOKENS, ax.RETRY_MAX_TOKENS]   # once more, never twice
    assert ei.value.error == "cut_off"
    assert (ei.value._meta["input_tokens"], ei.value._meta["output_tokens"]) == \
        (6_000, ax.MAX_TOKENS + ax.RETRY_MAX_TOKENS)
    assert len(ei.value._meta["truncated_attempts"]) == 2
    assert list(VisionCache(namespace="room_adjacency").keys()) == []


def test_a_refusal_is_not_asked_again(cache_dir):
    client = _Client(_refusal())
    with pytest.raises(ModelStopped) as ei:
        ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert len(client.requests) == 1
    assert ei.value.error == "refused:reasoning_extraction"
    assert ei.value._meta["input_tokens"] == 5_497


def test_a_retry_that_never_comes_back_still_reports_the_cut_off_answer(cache_dir):
    client = _Client(_cut_off(), ConnectionError("connection reset"))
    with pytest.raises(ConnectionError) as ei:
        ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert ei.value._meta["output_tokens"] == ax.MAX_TOKENS


def test_an_unreadable_answer_reports_its_usage_and_is_not_cached(cache_dir):
    client = _Client(_resp("Atsiprašau, plano nematau."))
    with pytest.raises(ValueError) as ei:
        ax.extract_adjacency(image_b64=_png_b64(), client=client)
    assert ei.value._meta["output_tokens"] == 2_500
    assert list(VisionCache(namespace="room_adjacency").keys()) == []


# ── in the voted Pass-1: walls set, both answers metered, outcome recorded ────

def test_voted_cut_off_once_sets_the_walls_and_meters_both_answers(cache_dir, monkeypatch):
    client = _Client(_cut_off(i=3_000, o=ax.MAX_TOKENS), _ok(i=3_100, o=9_000))
    out, usage = _voted(monkeypatch, client)
    assert client.caps == [ax.MAX_TOKENS, ax.RETRY_MAX_TOKENS]
    assert _partition_walls(out) == {"101": 1, "102": 1}
    assert out["_meta"]["adjacency"] == {"status": "applied", "page": 1, "rooms_matched": 6,
                                         "cut_off_answers": 1}
    both = (6_100, ax.MAX_TOKENS + 9_000)
    assert _adjacency_calls(out) == [both]                     # one entry, both answers
    tally = [(c["input_tokens"], c["output_tokens"]) for c in usage.meta()["extra_calls"]]
    assert tally == [both]                                      # counted once, not twice
    assert vc._warn_partition_walls_unread(out) is False and not _our_warnings(out)


def test_voted_cut_off_twice_warns_and_meters_both_answers(cache_dir, monkeypatch):
    client = _Client(_cut_off(i=3_000, o=ax.MAX_TOKENS), _cut_off(i=3_000, o=ax.RETRY_MAX_TOKENS))
    out, usage = _voted(monkeypatch, client)
    assert _partition_walls(out) == {"101": None, "102": None}
    assert out["_meta"]["adjacency"] == {"status": "failed", "page": 1, "reason": "cut_off",
                                         "cut_off_answers": 2}
    both = (6_000, ax.MAX_TOKENS + ax.RETRY_MAX_TOKENS)
    assert _adjacency_calls(out) == [both]
    assert [(c["input_tokens"], c["output_tokens"]) for c in usage.meta()["extra_calls"]] == [both]
    assert vc._warn_partition_walls_unread(out) is True
    (w,) = _our_warnings(out)
    assert w["message"] == vc.PARTITION_WALLS_UNREAD_MESSAGE and w["_reason"] == "cut_off"


def test_voted_refusal_is_not_asked_again_and_warns(cache_dir, monkeypatch):
    client = _Client(_refusal())
    out, _ = _voted(monkeypatch, client)
    assert len(client.requests) == 1
    assert out["_meta"]["adjacency"] == {"status": "failed", "page": 1,
                                         "reason": "refused:reasoning_extraction"}
    assert _adjacency_calls(out) == [(5_497, 0)]                # the refusal was billed
    assert vc._warn_partition_walls_unread(out) is True
    assert _our_warnings(out)[0]["_reason"] == "refused:reasoning_extraction"


def test_no_floor_page_warns(cache_dir, monkeypatch):
    client = _Client()
    out, _ = _voted(monkeypatch, client, pages=[])
    assert client.requests == []
    assert out["_meta"]["adjacency"] == {"status": "skipped", "reason": "no_floor_page"}
    assert vc._warn_partition_walls_unread(out) is True
    assert _our_warnings(out)[0]["_reason"] == "no_floor_page"


def test_an_answer_that_matches_no_room_warns(cache_dir, monkeypatch):
    stranger = {"rooms": [{"room_name": "Ąžuolas", "room_nr": "999", "exterior_wall_count": 1,
                           "adjacent_rooms": [], "confidence": "low", "evidence": ""}]}
    client = _Client(_resp(json.dumps(stranger, ensure_ascii=False)))
    out, _ = _voted(monkeypatch, client, n=1)
    assert out["_meta"]["adjacency"]["status"] == "no_room_matched"
    assert vc._warn_partition_walls_unread(out) is True


def test_an_unreadable_answer_is_metered_and_warns(cache_dir, monkeypatch):
    client = _Client(_resp("Atsiprašau, plano nematau.", i=3_000, o=4_000))
    out, _ = _voted(monkeypatch, client, n=1)
    assert out["_meta"]["adjacency"]["status"] == "failed"
    assert out["_meta"]["adjacency"]["reason"].startswith("ValueError")
    assert _adjacency_calls(out) == [(3_000, 4_000)]
    assert vc._warn_partition_walls_unread(out) is True


# ── the warning ───────────────────────────────────────────────────────────────

def test_the_warning_is_plain_lithuanian_for_him():
    msg = vc.PARTITION_WALLS_UNREAD_MESSAGE
    assert not is_banned(msg)
    assert "„Dažymo kampų montavimas“" in msg and msg.endswith("Patikrinkite kampus plane.")
    assert not any(word in msg.lower() for word in ("adjacency", "vision", "max_tokens", "cut"))


def test_the_warning_is_added_once_and_only_when_the_rooms_have_no_walls():
    rooms = [{"nr": "101"}, {"nr": "102"}]
    parsed = {"patalpos": rooms, "_meta": {"adjacency": {"status": "failed", "reason": "cut_off"}}}
    assert vc._warn_partition_walls_unread(parsed) is True
    assert vc._warn_partition_walls_unread(parsed) is False          # never twice
    assert len(_our_warnings(parsed)) == 1
    # the walls arrived from somewhere all the same → nothing to say
    walled = {"patalpos": [{"nr": "101", "n_partition_walls": 2}],
              "_meta": {"adjacency": {"status": "failed", "reason": "cut_off"}}}
    assert vc._warn_partition_walls_unread(walled) is False
    # applied, or a result that never recorded the pass (a stub, an older path)
    assert vc._warn_partition_walls_unread({"patalpos": rooms,
                                            "_meta": {"adjacency": {"status": "applied"}}}) is False
    assert vc._warn_partition_walls_unread({"patalpos": rooms, "_meta": {}}) is False


def test_the_warning_reaches_the_list_the_screen_reads():
    from extractor.sanity_mirror import build_lt_sanity
    parsed = {"patalpos": [{"nr": "101"}],
              "_meta": {"adjacency": {"status": "failed", "reason": "cut_off"}}}
    vc._warn_partition_walls_unread(parsed)
    (ui,) = build_lt_sanity(parsed)["warnings"]
    assert ui["message"] == vc.PARTITION_WALLS_UNREAD_MESSAGE
    assert (ui["level"], ui["severity"], ui["code"]) == ("WARNING", "med", "adjacency_unread")
    assert "_reason" not in ui                       # the reader's reason stays off the screen


# ── extract_interior: the warning is added where the run's notes are ────────

class _Stop(Exception):
    pass


def _front(monkeypatch):
    """Real extract_interior up to just after Pass-1; rendering, the room table
    and the model are stubs (tests/test_dead_runs_metered.py's front)."""
    import anthropic
    from extractor import eksplikacija_reader
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_k: object())
    monkeypatch.setattr(vc, "pdf_to_b64_images",
                        lambda _b, **_k: [{"page_index": 1, "image_b64": "x"}])
    monkeypatch.setattr(vc, "build_user_content", lambda pages: [])
    monkeypatch.setattr(eksplikacija_reader, "read_eksplikacija", lambda _b, _c: {
        "patalpos": [], "schedule_tables": {"durys": [], "langai": []}})
    seen: list[dict] = []
    real = vc._warn_partition_walls_unread

    def _spy(parsed):
        added = real(parsed)
        seen.append({"added": added, "warnings": list(parsed.get("warnings") or []),
                     "adjacency": (parsed.get("_meta") or {}).get("adjacency")})
        raise _Stop
    monkeypatch.setattr(vc, "_warn_partition_walls_unread", _spy)
    return seen


def _pass1(meta_extra=None):
    return {"patalpos": [_room("101", "Svetainė")],
            "warnings": [{"level": "INFO", "message": "modelio pastaba"}],
            "_meta": {"model": MODEL, "input_tokens": 1, "output_tokens": 1, **(meta_extra or {})}}


def test_extract_interior_without_voting_warns_that_the_pass_never_ran(monkeypatch):
    seen = _front(monkeypatch)
    monkeypatch.setenv("ENABLE_EXTRACTION_VOTING", "0")
    monkeypatch.setattr(vc, "_run_pass1_once", lambda *a, **k: _pass1())
    with pytest.raises(_Stop):
        vc.extract_interior(b"%PDF-1.4 fake")
    (s,) = seen
    assert s["adjacency"] == {"status": "skipped", "reason": "voting_off"}
    assert s["added"] is True
    assert [w.get("code") for w in s["warnings"]] == [None, vc.PARTITION_WALLS_UNREAD_CODE]


def test_extract_interior_with_voting_warns_on_a_failed_pass_only(monkeypatch):
    seen = _front(monkeypatch)
    monkeypatch.setenv("ENABLE_EXTRACTION_VOTING", "1")
    for note, added in (({"status": "failed", "reason": "cut_off"}, True),
                        ({"status": "applied", "rooms_matched": 3}, False)):
        monkeypatch.setattr(vc, "_run_pass1_voted",
                            lambda *a, _n=note, **k: _pass1({"adjacency": dict(_n)}))
        with pytest.raises(_Stop):
            vc.extract_interior(b"%PDF-1.4 fake")
        assert seen[-1]["added"] is added and seen[-1]["adjacency"] == note


# ── end to end: production's extract_interior on objektas_h (golden replay) ──

REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_PDF = REPO_ROOT / "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf"


def _golden_pdf() -> Path:
    return Path(os.environ.get("SAMATU_GOLDEN_REPLAY_PDF") or _GOLDEN_PDF)


def _harness():
    spec = importlib.util.spec_from_file_location("eval_harness_adjacency_cut_off",
                                                  REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_adjacency_cut_off"] = mod
    spec.loader.exec_module(mod)
    return mod


def _replay(tmp_path_factory, adjacency_stops: list[str | None]) -> dict:
    """Production's extract_interior on objektas_h, every call answered from the
    stored run (golden replay) — except the adjacency pass, which answers
    `adjacency_stops` in order: "max_tokens" = an answer cut off at the cap,
    None = the stored answer."""
    from tests import golden_replay as gr
    pdf = _golden_pdf()
    if not pdf.is_file():
        pytest.skip(f"objektas_h: the drawing is not on this machine ({pdf})")
    missing = gr.objektas_h_material_missing()
    if missing:
        pytest.skip(f"objektas_h: the stored answers are not on this machine — {missing}")
    frozen = json.loads(gr.OBJEKTAS_H_EXTRACT.read_text(encoding="utf-8"))
    meta_log = json.loads(gr.OBJEKTAS_H_META.read_text(encoding="utf-8"))
    eh = _harness()
    from extractor import feature_flags, pdf_page_cache

    answers = gr.objektas_h_answers(frozen, meta_log)
    (stored,) = answers["adjacency"]
    text = stored.text()
    answers["adjacency"] = [
        stored if stop is None else gr.Answer(
            text[: len(text) // 3], "synthetic", note=f"stop:{stop}",
            usage={"input_tokens": int(stored.usage.get("input_tokens") or 0),
                   "output_tokens": ax.MAX_TOKENS if k == 0 else ax.RETRY_MAX_TOKENS})
        for k, stop in enumerate(adjacency_stops)]
    client = gr.StubAnthropic(answers)
    plain_message = gr._message

    def _message(answer, model):
        msg = plain_message(answer, model)
        if answer.note.startswith("stop:"):
            msg = msg.model_copy(update={"stop_reason": answer.note[len("stop:"):]})
        return msg

    events: list[dict] = []
    with pytest.MonkeyPatch.context() as mp:
        for env in (*feature_flags._FLAG_ENV_NAMES.values(), "SAMATU_PDF_NATIVE", "SAMATU_ZOOM_AGENTIC",
                    "SAMATU_VOTING_MODELS", "MODEL_OVERRIDE", "VOTING_N", "PARALLEL_VOTING_WARM",
                    "WALL_ELEVATION_EXTRACT", "ENABLE_LEGACY_HALF_SUBTRACT"):
            mp.delenv(env, raising=False)
        gr.install(mp, client, tmp_path_factory.mktemp("vision_cache"))
        mp.setattr(gr, "_message", _message)
        pdf_page_cache.clear()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = vc.extract_interior(pdf.read_bytes(),
                                             rules_override=eh._harness_rules_override(frozen),
                                             progress_cb=events.append)
        finally:
            pdf_page_cache.clear()
    return {"result": result, "client": client, "frozen": frozen, "stored": stored}


def _stored_adjacency_call(frozen: dict) -> tuple[int, int]:
    (c,) = [c for c in frozen["_meta"]["extra_calls"] if c.get("reader") == "adjacency"]
    return int(c["input_tokens"]), int(c["output_tokens"])


@pytest.mark.integration
def test_end_to_end_cut_off_once_gives_the_stored_walls_and_bills_both(tmp_path_factory):
    run = _replay(tmp_path_factory, ["max_tokens", None])
    result, frozen = run["result"], run["frozen"]
    assert result.get("status") == "ok", result.get("_error")
    assert run["client"].calls["adjacency"] == 2 and run["client"].unexpected == []
    assert [r.get("n_partition_walls") for r in result["patalpos"]] == \
        [r.get("n_partition_walls") for r in frozen["patalpos"]]
    assert any(r.get("n_partition_walls") for r in result["patalpos"])
    stored_in, stored_out = _stored_adjacency_call(frozen)
    assert _adjacency_calls(result) == [(2 * stored_in, ax.MAX_TOKENS + stored_out)]
    assert result["_meta"]["adjacency"]["status"] == "applied"
    assert result["_meta"]["adjacency"]["cut_off_answers"] == 1
    assert not _our_warnings(result)


@pytest.mark.integration
def test_end_to_end_cut_off_twice_completes_and_warns(tmp_path_factory):
    run = _replay(tmp_path_factory, ["max_tokens", "max_tokens"])
    result, frozen = run["result"], run["frozen"]
    assert result.get("status") == "ok", result.get("_error")       # the extraction completes
    assert result["pozicijos"]
    assert run["client"].calls["adjacency"] == 2 and run["client"].unexpected == []
    rooms = result["patalpos"]
    assert not any(r.get("n_partition_walls") for r in rooms)
    assert all(float(r.get("kampai_pusiniai_m") or 0) == 0 for r in rooms)
    stored_in, _ = _stored_adjacency_call(frozen)
    assert _adjacency_calls(result) == [(2 * stored_in, ax.MAX_TOKENS + ax.RETRY_MAX_TOKENS)]
    assert result["_meta"]["adjacency"] == {"status": "failed", "page": result["_meta"]["adjacency"]["page"],
                                            "reason": "cut_off", "cut_off_answers": 2}
    (w,) = _our_warnings(result)
    assert w["_reason"] == "cut_off"
    shown = [u.get("message") for u in (result.get("lt_sanity") or {}).get("warnings") or []]
    assert shown.count(vc.PARTITION_WALLS_UNREAD_MESSAGE) == 1

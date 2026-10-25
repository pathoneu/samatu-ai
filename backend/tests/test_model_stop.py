"""Readers recognise a refused or cut-off answer (2026-09-30).

The paid read of objektas_g left every room's doors unread: the doors request
came back with stop_reason "refusal", no content blocks, 5,497 input tokens
billed and 0 output, stop details category "reasoning_extraction". The doors
reader never looked at stop_reason, so the refusal surfaced only as "no JSON
in response" and its billed input tokens were never recorded.

Every reader call covered here must now:
  * return (or raise) its existing error shape with a clear `_error`
    ("refused:<category>" or "cut_off"),
  * carry the call's usage in `_meta` so the spend tally counts it,
  * never retry a refusal,
  * return exactly what it returned before on a normal answer.

No Anthropic API call is made: every client below is a stub.
"""
from __future__ import annotations

import base64
import io
import json
import types

import pytest

from extractor.response_text import ModelStopped, read_answer, stop_error


# ── stubs ─────────────────────────────────────────────────────────────────────

def _usage(i=5497, o=0):
    return types.SimpleNamespace(input_tokens=i, output_tokens=o)


def _refusal(category="reasoning_extraction"):
    details = (types.SimpleNamespace(category=category, type="refusal")
               if category else None)
    return types.SimpleNamespace(content=[], stop_reason="refusal",
                                 stop_details=details, usage=_usage())


def _cut_off(text='{"doors": [{"id": "d1"'):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        stop_reason="max_tokens", stop_details=None, usage=_usage(900, 16384))


def _ok(text):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="thinking", thinking="..."),
                 types.SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn", stop_details=None, usage=_usage(1200, 300))


class _CreateClient:
    """messages.create stub returning the queued responses in order."""
    def __init__(self, *responses):
        self._queue = list(responses)
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


class _StreamClient:
    """messages.stream stub (context manager with get_final_message)."""
    def __init__(self, resp):
        self._resp = resp
        self.calls = 0
        self.messages = self

    def stream(self, **kw):
        self.calls += 1
        resp = self._resp

        class _Ctx:
            def __enter__(self_inner):
                return types.SimpleNamespace(get_final_message=lambda: resp)

            def __exit__(self_inner, *a):
                return False
        return _Ctx()


def _png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


# ── the shared helper ─────────────────────────────────────────────────────────

def test_stop_error_names_refusal_category_and_cut_off():
    assert stop_error(_refusal()) == "refused:reasoning_extraction"
    assert stop_error(_refusal(category=None)) == "refused"
    assert stop_error(_cut_off()) == "cut_off"
    assert stop_error(_ok("{}")) is None
    # stubs without the attribute, and MagicMock-ish objects, read as normal
    assert stop_error(types.SimpleNamespace(content=[])) is None
    from unittest.mock import MagicMock
    assert stop_error(MagicMock()) is None


def test_read_answer_logs_one_line_and_returns_no_text(capsys):
    text, err = read_answer(_refusal(), reader="doors_reader", page=2)
    assert (text, err) == ("", "refused:reasoning_extraction")
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "doors_reader" in out[0] and "2" in out[0] and "reasoning_extraction" in out[0]

    text, err = read_answer(_ok('{"a": 1}'), reader="doors_reader", page=2)
    assert (text, err) == ('{"a": 1}', None)
    assert capsys.readouterr().out == ""


def test_model_stopped_is_a_value_error_carrying_meta():
    exc = ModelStopped("cut_off", {"model": "m", "input_tokens": 1})
    assert isinstance(exc, ValueError)
    assert exc.error == "cut_off" and exc._meta["input_tokens"] == 1


# ── Item 1: the doors prompt no longer asks for a narration ──────────────────

def test_doors_prompt_asks_for_no_narration_and_keeps_counting_steps():
    from extractor import doors_reader as dr
    text = dr.build_user_text([{"nr": "01", "pavadinimas": "Holas", "plotas_m2": 5}])
    assert "audit_trail" not in text and "audit_trail" not in dr.SYSTEM_PROMPT
    assert "kelias kuriuo" not in text
    # the counting procedure is untouched
    for step in ("1. Identifikuok kiekvieno kambario kontūrą plane.",
                 "3. Po to atskirai patikrink: ar yra priekinis lauko įėjimas?",
                 "5. Suskaičiuok `total_count`."):
        assert step in text
    # the requested JSON is still well-formed once the placeholders are filled
    schema = text.split("Output JSON:")[1].split("PROCEDŪRA")[0]
    filled = (schema.replace('"standart" | "pasleptos" | "slankiojanti" | "harmonika" | "garazo"', '"x"')
                    .replace('["101", "exterior"] | ["103", "108"] | etc.', '[]')
                    .replace("number", "0"))
    assert set(json.loads(filled)) == {"doors", "total_count", "interior_count", "exterior_count"}


# ── doors_reader ──────────────────────────────────────────────────────────────

@pytest.fixture
def _doors_env(monkeypatch):
    from extractor import doors_reader as dr
    monkeypatch.setattr(dr, "_render_page_b64", lambda pdf, page, dpi=220: "AAAA")
    monkeypatch.setattr(dr, "model_for", lambda role: "claude-test")
    return dr


_ROOMS = [{"nr": "01", "pavadinimas": "Holas", "plotas_m2": 5.0, "puslapio_nr": 2}]


def test_doors_refusal_is_named_billed_and_not_retried(_doors_env):
    dr = _doors_env
    client = _CreateClient(_refusal())
    out = dr.read_doors_from_plan(b"%PDF", _ROOMS, client=client, page=2)
    assert client.calls == 1
    assert out["status"] == "error" and out["page"] == 2
    assert out["_error"] == "refused:reasoning_extraction"
    assert out["doors"] == [] and out["total_count"] == 0
    assert out["_meta"] == {"input_tokens": 5497, "output_tokens": 0, "model": "claude-test"}


def test_doors_cut_off_is_named(_doors_env):
    out = _doors_env.read_doors_from_plan(b"%PDF", _ROOMS, client=_CreateClient(_cut_off()), page=2)
    assert out["_error"] == "cut_off"
    assert out["_meta"]["output_tokens"] == 16384


def test_doors_pages_carry_the_refused_call_into_round_metas(_doors_env):
    res = _doors_env.read_doors_from_plan_pages(b"%PDF", _ROOMS, client=_CreateClient(_refusal()))
    assert res["pages_unread"] == [2]
    assert res["page_results"][0]["_error"] == "refused:reasoning_extraction"
    assert res["_round_metas"] == [{"input_tokens": 5497, "output_tokens": 0, "model": "claude-test"}]


_DOORS_JSON = {
    "doors": [{"id": "d1", "tipas": "standart", "plotis_mm": 900, "aukstis_mm": 2100,
               "between": ["01", "exterior"], "pastabos": ""}],
    "total_count": 1, "interior_count": 0, "exterior_count": 1,
}


@pytest.mark.parametrize("answer", [
    _DOORS_JSON,
    {**_DOORS_JSON, "audit_trail": "an old answer that still carries the field"},
])
def test_doors_success_shape_unchanged(_doors_env, answer):
    out = _doors_env.read_doors_from_plan(b"%PDF", _ROOMS,
                                          client=_CreateClient(_ok(json.dumps(answer))), page=2)
    out.pop("_elapsed_s")
    assert out == {
        "status": "ok", "page": 2, "doors": _DOORS_JSON["doors"],
        "total_count": 1, "exterior_count": 1, "interior_count": 0,
        "_meta": {"input_tokens": 1200, "output_tokens": 300, "model": "claude-test"},
    }


# ── door_type_reader / sanitary_fixture_reader (single + voted) ──────────────

@pytest.fixture
def _door_type_env(monkeypatch):
    from extractor import door_type_reader as m
    monkeypatch.setattr(m, "_render_page_b64", lambda pdf, page, *a, **k: "AAAA")
    monkeypatch.setattr(m, "_find_door_pages", lambda *a, **k: [3])
    monkeypatch.setattr(m, "model_for", lambda role: "claude-test")
    return m


@pytest.fixture
def _fixture_env(monkeypatch):
    from extractor import sanitary_fixture_reader as m
    monkeypatch.setattr(m, "_render_page_b64", lambda pdf, page, *a, **k: "AAAA")
    monkeypatch.setattr(m, "_find_sanitary_pages", lambda *a, **k: [3])
    monkeypatch.setattr(m, "model_for", lambda role: "claude-test")
    return m


def _door_types(m, client):
    return m.read_door_types(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}], client=client)


def _fixtures(m, client):
    return m.read_fixtures(b"%PDF", [], client, [{"nr": 3, "tipas": "plumbing"}])


def test_door_type_refusal(_door_type_env):
    client = _CreateClient(_refusal())
    out = _door_types(_door_type_env, client)
    assert client.calls == 1
    assert out["status"] == "error" and out["beapvadines_count"] == 0
    assert out["_error"] == "refused:reasoning_extraction"
    assert out["_meta"] == {"input_tokens": 5497, "output_tokens": 0, "model": "claude-test"}


def test_fixture_refusal(_fixture_env):
    out = _fixtures(_fixture_env, _CreateClient(_refusal()))
    assert out["status"] == "error"
    assert out["_error"] == "refused:reasoning_extraction"
    assert out["_meta"] == {"input_tokens": 5497, "output_tokens": 0, "model": "claude-test"}


def test_voted_door_types_stop_after_a_refusal_and_bill_every_call(_door_type_env):
    m = _door_type_env
    ok = _ok(json.dumps({"doors": [], "beapvadines_count": 2}))
    client = _CreateClient(ok, _refusal(), ok)
    out = m.read_door_types_voted(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}], client=client, n=3)
    assert client.calls == 2                      # the refused request is not asked again
    assert out["status"] == "ok" and out["beapvadines_count"] == 2
    assert [r["input_tokens"] for r in out["_round_metas"]] == [1200, 5497]


def test_voted_fixtures_all_refused_bills_the_one_call(_fixture_env):
    m = _fixture_env
    client = _CreateClient(_refusal())
    out = m.read_fixtures_voted(b"%PDF", [], client, n=3, pages_meta=[{"nr": 3, "tipas": "plumbing"}])
    assert client.calls == 1
    assert out["status"] == "error" and out["_error"] == "refused:reasoning_extraction"
    from extractor.vision_call import _reader_call_metas
    assert [r["input_tokens"] for r in _reader_call_metas(out)] == [5497]


def test_door_type_success_shape_unchanged(_door_type_env):
    ans = {"doors": [{"id": "d1"}], "beapvadines_count": 2, "standartines_count": 5,
           "stumdomos_count": 1, "bendras_tipas": "beapvadines", "pastabos": "x"}
    out = _door_types(_door_type_env, _CreateClient(_ok(json.dumps(ans))))
    out.pop("_elapsed_s")
    assert out == {"status": "ok", "pages": [3], "doors": [{"id": "d1"}],
                   "beapvadines_count": 2, "standartines_count": 5, "stumdomos_count": 1,
                   "bendras_tipas": "beapvadines", "pastabos": "x",
                   "_meta": {"input_tokens": 1200, "output_tokens": 300, "model": "claude-test"}}


def test_fixture_success_shape_unchanged(_fixture_env):
    m = _fixture_env
    ans = {f"{k}_count": 1 for k in m._FIXTURE_KEYS}
    ans["prietaisai"] = [{"tipas": "wc"}]
    out = _fixtures(m, _CreateClient(_ok(json.dumps(ans))))
    out.pop("_elapsed_s")
    assert out == {"status": "ok", "pages": [3], "counts": {k: 1 for k in m._FIXTURE_KEYS},
                   "prietaisai": [{"tipas": "wc"}],
                   "_meta": {"input_tokens": 1200, "output_tokens": 300, "model": "claude-test"}}


def test_voted_success_round_metas_unchanged(_door_type_env):
    m = _door_type_env
    ok = _ok(json.dumps({"doors": [], "beapvadines_count": 2}))
    client = _CreateClient(ok)
    out = m.read_door_types_voted(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}], client=client, n=3)
    assert client.calls == 3
    assert out["_round_metas"] == [{"input_tokens": 1200, "output_tokens": 300,
                                    "model": "claude-test"}] * 3


# ── readers whose failure shape is an exception ──────────────────────────────

def test_page_classifier_refusal_raises_model_stopped(monkeypatch):
    from extractor import page_classifier as pc
    monkeypatch.setattr(pc, "model_for", lambda role: "claude-test")
    with pytest.raises(ModelStopped) as ei:
        pc._call_haiku("AAAA", client=_CreateClient(_refusal()))
    assert ei.value.error == "refused:reasoning_extraction"
    assert ei.value._meta == {"model": "claude-test", "input_tokens": 5497, "output_tokens": 0}


# ── extractor/vision/*: raise ModelStopped, never cache a refused answer ─────

def _vision_readers():
    # v4 3b (2026-10-25): the room-geometry readers are deleted; the two Phase 3c reduces to text remain
    from extractor.vision import height_extractor, schedule_extractor
    return [
        ("height_extractor", height_extractor.extract_ceiling_height,
         height_extractor.parse_height_payload, {}),
        ("schedule_extractor", schedule_extractor.extract_schedule,
         schedule_extractor.parse_schedule_payload, {}),
    ]


_VISION_IDS = [r[0] for r in _vision_readers()]
# Readers that ask a cut-off answer once more with a larger cap (2026-10-07):
# both answers are billed, so the stop carries both answers' usage.
_RETRY_A_CUT_OFF: set[str] = set()


@pytest.mark.parametrize("idx", range(len(_VISION_IDS)), ids=_VISION_IDS)
@pytest.mark.parametrize("resp_kind", ["refusal", "cut_off"])
def test_vision_reader_stop_raises_and_caches_nothing(tmp_path, capsys, idx, resp_kind):
    from extractor.vision._cache import VisionCache
    name, fn, _parse, extra = _vision_readers()[idx]
    cache = VisionCache(root=tmp_path, namespace=name)
    resp = _refusal() if resp_kind == "refusal" else _cut_off("{")
    client = _StreamClient(resp)
    with pytest.raises(ModelStopped) as ei:
        fn(image_b64=_png_b64(), model="claude-test", cache=cache, client=client, **extra)
    asked = 2 if (resp_kind == "cut_off" and name in _RETRY_A_CUT_OFF) else 1
    assert client.calls == asked                          # a refusal is never asked again
    want = "refused:reasoning_extraction" if resp_kind == "refusal" else "cut_off"
    assert ei.value.error == want
    assert ei.value._meta["model"] == "claude-test"
    assert ei.value._meta["input_tokens"] == (5497 if resp_kind == "refusal" else 900 * asked)
    assert list(cache.keys()) == []                       # a stopped answer is never cached
    assert name in capsys.readouterr().out


def _plain(obj):
    """The parsed result without its _meta, for comparing two parses."""
    d = json.loads(json.dumps(obj, default=lambda o: getattr(o, "__dict__", repr(o))))
    d.pop("_meta", None)
    return d


def _empty_payload(name):
    return {"dimension_extractor": {"dimensions": []},
            "room_graph_extractor": {"walls": [], "openings": []}}.get(name, {})


@pytest.mark.parametrize("idx", range(len(_VISION_IDS)), ids=_VISION_IDS)
def test_vision_reader_success_unchanged(tmp_path, idx):
    from extractor.vision._cache import VisionCache
    name, fn, parse, extra = _vision_readers()[idx]
    cache = VisionCache(root=tmp_path, namespace=name)
    payload = _empty_payload(name)
    out = fn(image_b64=_png_b64(), model="claude-test", cache=cache,
             client=_StreamClient(_ok(json.dumps(payload))), **extra)
    assert _plain(out) == _plain(parse(payload))
    assert out._meta["cache"] == "miss" and out._meta["model"] == "claude-test"
    assert (out._meta["input_tokens"], out._meta["output_tokens"]) == (1200, 300)
    assert len(list(cache.keys())) == 1


# ── Item 3: extract_interior records why a doors page went unread ────────────

def test_unread_doors_page_records_its_reason():
    from extractor.vision_call import _note_doors_unread
    parsed: dict = {}
    doors_result = {"pages_unread": [2], "page_results": [
        {"status": "error", "page": 2, "_error": "refused:reasoning_extraction"},
        {"status": "ok", "page": 3},
    ]}
    _note_doors_unread(parsed, doors_result)
    assert parsed["_meta"]["doors_pages_unread"] == [2]
    assert parsed["_meta"]["doors_page_errors"] == {"2": "refused:reasoning_extraction"}
    (w,) = parsed["warnings"]
    assert w["code"] == "doors_page_unread"
    assert w["_page_errors"] == {"2": "refused:reasoning_extraction"}
    assert "refused" not in w["message"] and "reasoning" not in w["message"]
    assert w["message"].startswith("Brėžinio 2 puslapio durys nebuvo perskaičiuotos")


def test_all_doors_pages_read_records_nothing():
    from extractor.vision_call import _note_doors_unread
    parsed: dict = {}
    _note_doors_unread(parsed, {"pages_unread": [], "page_results": [{"status": "ok", "page": 2}]})
    assert parsed == {}


def test_voted_all_cut_off_bills_every_round(_door_type_env):
    m = _door_type_env
    client = _CreateClient(_cut_off())
    out = m.read_door_types_voted(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}], client=client, n=3)
    assert client.calls == 3                      # a cut-off is not a refusal: every vote runs
    assert out["status"] == "error" and out["_error"] == "cut_off"
    from extractor.vision_call import _reader_call_metas
    assert [r["input_tokens"] for r in _reader_call_metas(out)] == [900, 900, 900]


# ── material_specs (streamed, with its own two-attempt loop) ─────────────────

@pytest.fixture
def _specs_env(monkeypatch):
    from extractor import material_specs as ms
    from PIL import Image
    monkeypatch.setattr(ms, "model_for", lambda role: "claude-test")
    import pdf2image
    monkeypatch.setattr(pdf2image, "convert_from_bytes",
                        lambda *a, **k: [Image.new("RGB", (8, 8), "white")])
    return ms


def test_material_specs_refusal_is_not_retried_and_keeps_usage(_specs_env):
    client = _StreamClient(_refusal())
    out = _specs_env.extract_room_material_specs(b"%PDF", [4], "Svetainė", client=client)
    assert client.calls == 1
    assert out["_error"] == "refused:reasoning_extraction"
    assert out["paint"] is None and out["sienos_plyteles"] is None
    assert out["_meta"]["input_tokens"] == 5497 and out["_meta"]["model"] == "claude-test"


def test_material_specs_success_shape_unchanged(_specs_env):
    out = _specs_env.extract_room_material_specs(
        b"%PDF", [4], "Svetainė", client=_StreamClient(_ok('{"paint": {"x": 1}}')))
    out["_meta"].pop("elapsed_s")
    assert out == {"paint": {"x": 1}, "sienos_plyteles": None, "grindys_plyteles": None,
                   "grindys_medines": None,
                   "_meta": {"pages_inspected": [4], "input_tokens": 1200, "output_tokens": 300}}

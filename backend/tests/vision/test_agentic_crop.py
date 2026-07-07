"""EXPERIMENT Mode 2 — agentic crop loop (SAMATU_ZOOM_AGENTIC=1).

All tests run offline ($0): the Anthropic client is a fake scripted with a
sequence of canned responses; crop rendering is monkeypatched (no poppler).
Covers: parallel tool_use answered in ONE user message, pause_turn resume,
refusal abort, max-crops hard stop + final-answer nudge, invalid crop args,
turn-limit safety, and the env gate default-OFF.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import extractor.agentic_crop as ac
import extractor.vision_call as vc


# ── fakes ──────────────────────────────────────────────────────────────────────
def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use(id_, **input_):
    return SimpleNamespace(type="tool_use", id=id_, name="request_crop", input=input_)


def _resp(stop_reason, content, in_tok=100, out_tok=50):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(
            input_tokens=in_tok, output_tokens=out_tok,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        ),
    )


ZOOM_JSON = {
    "perimetras_m": 21.4, "perimetras_saltinis": "from_zoom",
    "plotas_m2": 27.9, "plotas_saltinis": "from_zoom",
    "matmenys_perskaityti": ["3600", "5200"],
    "langai": [], "durys": [], "lubu_aukstis_m": 3.0,
    "plyteles_sienos_aukstis_m": None, "nisu_metrai": None,
    "confidence_zoom": "high", "pastabos": "",
}


class _FakeClient:
    """Scripted client: each messages.create pops the next canned response;
    every request's kwargs are recorded for assertions."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def with_options(self, **kwargs):
        return self

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("fake client ran out of scripted responses")
        return self._responses.pop(0)


ROOM = {
    "nr": "5", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
    "plotas_m2": 27.5, "perimetras_m": 21.0, "lubu_aukstis_m": 3.0,
    "puslapio_nr": 2, "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3},
}


@pytest.fixture
def stub_rendering(monkeypatch):
    """No poppler in unit tests: seed crop + tool crops return fake b64."""
    monkeypatch.setattr(vc, "_crop_room_image", lambda *a, **k: "SEEDB64")
    monkeypatch.setattr(ac, "_render_crop",
                        lambda pdf, args, cache: ("CROPB64", None))


# ── happy path + parallel tool_use ────────────────────────────────────────────
def test_parallel_tool_use_answered_in_one_user_message(stub_rendering):
    client = _FakeClient([
        _resp("tool_use", [
            _text_block("žiūriu du fragmentus"),
            _tool_use("tu_1", page=2, x0=0.1, y0=0.1, x1=0.4, y1=0.4),
            _tool_use("tu_2", page=2, x0=0.5, y0=0.5, x1=0.9, y1=0.9, dpi=600),
        ]),
        _resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))]),
    ])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="test-model")

    assert result["perimetras_m"] == 21.4
    assert meta["outcome"] == "ok"
    assert meta["crops_served"] == 2
    assert meta["api_turns"] == 2
    assert meta["input_tokens"] == 200 and meta["output_tokens"] == 100

    # Both tool_use blocks answered in the SAME user message.
    second_call_msgs = client.calls[1]["messages"]
    tool_result_msgs = [m for m in second_call_msgs
                        if m["role"] == "user"
                        and isinstance(m["content"], list)
                        and any(b.get("type") == "tool_result"
                                for b in m["content"] if isinstance(b, dict))]
    assert len(tool_result_msgs) == 1
    results = [b for b in tool_result_msgs[0]["content"]
               if isinstance(b, dict) and b.get("type") == "tool_result"]
    assert {r["tool_use_id"] for r in results} == {"tu_1", "tu_2"}
    # image payloads, not errors
    assert all(r["content"][0]["type"] == "image" for r in results)


def test_direct_answer_without_crops(stub_rendering):
    client = _FakeClient([_resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))])])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result["plotas_m2"] == 27.9
    assert meta["crops_served"] == 0 and meta["api_turns"] == 1
    # tool available on the request
    assert client.calls[0]["tools"][0]["name"] == "request_crop"


# ── max-crops hard stop ────────────────────────────────────────────────────────
def test_max_crops_hard_stop_then_forced_answer(stub_rendering):
    # 5 turns × 2 parallel crops = 10 requested; limit 8 → last 2 get is_error
    # + a one-time nudge text appended to the SAME user message.
    crop_turns = [
        _resp("tool_use", [
            _tool_use(f"tu_{i}a", page=2, x0=0.0, y0=0.0, x1=0.5, y1=0.5),
            _tool_use(f"tu_{i}b", page=2, x0=0.5, y0=0.5, x1=1.0, y1=1.0),
        ])
        for i in range(5)
    ]
    client = _FakeClient(crop_turns +
                         [_resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))])])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")

    assert result is not None
    assert meta["crops_served"] == 8          # hard stop
    assert meta["outcome"] == "ok"

    final_call_msgs = client.calls[-1]["messages"]
    user_msgs = [m for m in final_call_msgs if m["role"] == "user"]

    # Turn 5's over-limit pair got is_error results (limit already reached).
    last_blocks = user_msgs[-1]["content"]
    errored = [b for b in last_blocks if isinstance(b, dict)
               and b.get("type") == "tool_result" and b.get("is_error")]
    assert len(errored) == 2

    # The final-answer nudge was appended exactly ONCE across the whole
    # conversation — on the turn where the 8th crop was served.
    nudges = [b for m in user_msgs for b in m["content"]
              if isinstance(b, dict) and b.get("type") == "text"
              and "GALUTINĮ" in b["text"]]
    assert len(nudges) == 1

    # Total crops served as image tool_results across the conversation == 8.
    image_results = [b for m in user_msgs for b in m["content"]
                     if isinstance(b, dict) and b.get("type") == "tool_result"
                     and not b.get("is_error")]
    assert len(image_results) == 8


# ── stop reasons ───────────────────────────────────────────────────────────────
def test_refusal_aborts_room_gracefully(stub_rendering):
    client = _FakeClient([_resp("refusal", [])])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is None
    assert meta["outcome"] == "refusal"
    assert meta["api_turns"] == 1


def test_pause_turn_resumes_with_echoed_content(stub_rendering):
    paused = _resp("pause_turn", [_text_block("dar dirbu...")])
    client = _FakeClient([
        paused,
        _resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))]),
    ])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is not None and meta["outcome"] == "ok"
    # second request must carry the paused assistant content back
    msgs = client.calls[1]["messages"]
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-1]["content"] is paused.content


def test_max_tokens_aborts(stub_rendering):
    client = _FakeClient([_resp("max_tokens", [_text_block("{trunc")])])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is None and meta["outcome"] == "max_tokens"


def test_turn_limit_safety(stub_rendering, monkeypatch):
    monkeypatch.setattr(ac, "MAX_API_TURNS", 3)
    spin = [_resp("tool_use",
                  [_tool_use(f"t{i}", page=2, x0=0.0, y0=0.0, x1=0.5, y1=0.5)])
            for i in range(10)]
    client = _FakeClient(spin)
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is None and meta["outcome"] == "turn_limit"
    assert meta["api_turns"] == 3


def test_json_repair_path(stub_rendering):
    almost_json = "```json\n{perimetras_m: 21.4, perimetras_saltinis: \"from_zoom\",}\n```"
    client = _FakeClient([_resp("end_turn", [_text_block(almost_json)])])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result["perimetras_m"] == 21.4
    assert meta["outcome"] == "ok"


def test_seed_crop_failure_skips_room(monkeypatch):
    monkeypatch.setattr(vc, "_crop_room_image", lambda *a, **k: None)
    client = _FakeClient([])   # must never be called
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is None and meta["outcome"] == "seed_crop_failed"
    assert client.calls == []


# ── invalid crop args ──────────────────────────────────────────────────────────
def test_invalid_crop_args_return_tool_error(monkeypatch):
    monkeypatch.setattr(vc, "_crop_room_image", lambda *a, **k: "SEEDB64")
    # real _render_crop but with bad coords → validation error before render
    client = _FakeClient([
        _resp("tool_use", [_tool_use("bad", page=2, x0=0.9, y0=0.1, x1=0.1, y1=0.5)]),
        _resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))]),
    ])
    result, meta = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    assert result is not None
    assert meta["crops_served"] == 0
    last_user = [m for m in client.calls[1]["messages"] if m["role"] == "user"][-1]
    tr = last_user["content"][0]
    assert tr["is_error"] is True and "x1 > x0" in tr["content"]


@pytest.mark.parametrize("args,frag", [
    ({"page": 0, "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5}, "page"),
    ({"page": 1, "x0": -0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5}, "0.0-1.0"),
    ({"page": 1, "x0": 0.1, "y0": 0.1, "x1": 1.5, "y1": 0.5}, "0.0-1.0"),
    ({"page": 1, "x0": 0.1, "y0": 0.6, "x1": 0.5, "y1": 0.5}, "y1 > y0"),
    ({"page": "x", "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.5}, "page"),
])
def test_validate_crop_args(args, frag):
    err = ac._validate_crop_args(args)
    assert err is not None and frag in err


def test_validate_crop_args_ok():
    assert ac._validate_crop_args(
        {"page": 2, "x0": 0.1, "y0": 0.1, "x1": 0.6, "y1": 0.9}) is None


# ── env gate ───────────────────────────────────────────────────────────────────
def test_zoom_agentic_env_gate(monkeypatch):
    monkeypatch.delenv("SAMATU_ZOOM_AGENTIC", raising=False)
    assert vc._zoom_agentic_enabled() is False
    monkeypatch.setenv("SAMATU_ZOOM_AGENTIC", "1")
    assert vc._zoom_agentic_enabled() is True
    monkeypatch.setenv("SAMATU_ZOOM_AGENTIC", "off")
    assert vc._zoom_agentic_enabled() is False


def test_agentic_output_feeds_apply_zoom_refinements(stub_rendering):
    """Contract: agentic output is a drop-in for _apply_zoom_refinements."""
    client = _FakeClient([_resp("end_turn", [_text_block(json.dumps(ZOOM_JSON))])])
    result, _ = ac.agentic_zoom_room(client, b"PDF", ROOM, model="m")
    room = dict(ROOM)
    changed = vc._apply_zoom_refinements(room, result)
    assert changed is True
    assert room["perimetras_m"] == 21.4
    assert room["plotas_m2"] == 27.9

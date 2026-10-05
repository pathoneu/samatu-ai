"""The golden-replay stub (tests/golden_replay.py): no call reaches the network,
each call is attributed to the reader that made it, and the answers rebuilt
from the stored objektas_h extract give back what the run stored. Needs only
tracked files, so it runs where the drawing is absent (CI)."""
from __future__ import annotations

import copy
import json
import socket

import pytest

from tests import golden_replay as gr


def _caller(module: str, client):
    """Call the client from a function that lives in `module`, as a reader would."""
    ns = {"__name__": module}
    exec("def read(client):\n    return client.messages.create(model='m', max_tokens=1, messages=[])", ns)
    return ns["read"](client)


def test_installed_stub_answers_every_client_and_nothing_reaches_the_network(monkeypatch, tmp_path):
    import anthropic
    import anthropic._client as real
    import httpx
    from extractor.vision._cache import VisionCache

    client = gr.StubAnthropic({"doors": [gr.Answer({"doors": []}, "synthetic", usage={"input_tokens": 7})]})
    gr.install(monkeypatch, client, tmp_path)
    assert anthropic.Anthropic(max_retries=1) is client and client.constructed == [{"max_retries": 1}]
    with pytest.raises(AssertionError, match="real Anthropic client"):
        real.Anthropic(api_key="x")
    with pytest.raises(AssertionError, match="network"):
        socket.socket().connect(("127.0.0.1", 9))
    with pytest.raises(AssertionError, match="network"):
        httpx.Client().send(httpx.Request("GET", "https://example.invalid"))
    assert VisionCache(namespace="niche_locator").root == tmp_path

    msg = _caller("extractor.doors_reader", client)
    assert json.loads(msg.content[0].text) == {"doors": []} and msg.usage.input_tokens == 7
    assert msg.stop_reason == "end_turn"
    with pytest.raises(AssertionError, match="no stored answer"):
        _caller("extractor.apdailos_reader", client)
    assert dict(client.calls) == {"doors": 1, "apdailos": 1}
    assert client.unexpected == ["apdailos (from extractor.apdailos_reader.read)"]
    assert client.log == [("doors", "extractor.doors_reader.read", "synthetic")] and client.leftover() == {}


def test_stream_calls_and_answers_chosen_by_the_request():
    client = gr.StubAnthropic({"zoom": lambda kw: gr.Answer({"nr": kw["model"]}, "stored")})
    ns = {"__name__": "extractor.vision_call"}
    exec("def _vision_zoom_room(client):\n"
         "    with client.with_options(timeout=1).messages.stream(model='07') as s:\n"
         "        return s.get_final_message()", ns)
    assert json.loads(ns["_vision_zoom_room"](client).content[0].text) == {"nr": "07"}
    assert client.calls["zoom"] == 1


def test_missing_stored_answers_are_named(monkeypatch, tmp_path):
    monkeypatch.setitem(gr.OBJEKTAS_H_CACHED, "adjacency", gr.REPO_ROOT / "nowhere" / "adjacency.json")
    assert gr.objektas_h_material_missing() == "nowhere/adjacency.json is not on this machine"


def _canon(element: dict) -> str:
    return json.dumps(element, sort_keys=True, ensure_ascii=False)


@pytest.fixture(scope="module")
def frozen():
    return json.loads(gr.OBJEKTAS_H_EXTRACT.read_text(encoding="utf-8"))


def test_the_rebuilt_pass1_rounds_vote_back_to_the_stored_rooms(frozen):
    from extractor.vision.extraction_voter import vote_extraction

    rounds = gr._pass1_rounds(frozen)
    assert len(rounds) == 3
    voted = vote_extraction(copy.deepcopy(rounds))
    assert voted["_voting"]["low_confidence_fields"] == frozen["_voting"]["low_confidence_fields"]
    for got, stored in zip(voted["patalpos"], frozen["patalpos"]):
        assert got["nr"] == stored["nr"]
        for f in ("perimetras_m", "plotas_m2", "lubu_aukstis_m"):
            assert got["_vote"][f]["values"] == stored["_vote"][f]["values"], (stored["nr"], f)
            assert got[f] == pytest.approx(sorted(stored["_vote"][f]["values"])[1]), (stored["nr"], f)
        kept = [{k: v for k, v in e.items() if k != "_exterior"} for e in stored["elementai"]
                if e.get("_source") != "statistical_inference"]
        # the voter groups a room's elements by type; incl. room 02's window it rebuilt bare
        assert sorted(map(_canon, got["elementai"])) == sorted(map(_canon, kept)), stored["nr"]
    assert "vonios_kubilai" not in rounds[0]["detected_symbols_summary"]
    assert all(set(w) <= {"level", "message", "patalpa_nr"} for w in rounds[0]["warnings"])


def test_the_rebuilt_door_list_places_exactly_the_stored_doors(frozen):
    from extractor.doors_reader import merge_doors_into_rooms

    rooms = [{**r, "elementai": [e for e in r["elementai"] if e.get("tipas") not in ("duris", "pasleptos_duris")]}
             for r in copy.deepcopy(frozen["patalpos"])]
    answer = gr._doors_answer(frozen)
    assert (answer["total_count"], answer["exterior_count"]) == (frozen["_meta"]["doors_total_count"],
                                                                  frozen["_meta"]["doors_exterior_count"])
    merge_doors_into_rooms(rooms, {"status": "ok", **answer})
    assert [r["elementai"] for r in rooms] == [r["elementai"] for r in frozen["patalpos"]]

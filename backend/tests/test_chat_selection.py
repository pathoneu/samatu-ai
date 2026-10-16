"""/chat-project with the estimator's SELECTION (togal-v2 W11, Togal capability J).

The rooms and rows he picked as pills reach the model as a block built from the read facts (room_facts
sentences) and the row ledgers — in the LAST user turn, after the two cached blocks, so the cache contract of
tests/test_chat_prompt_cache.py holds. Rooms he did not pick are not in the block. No network calls: the client
is stubbed exactly as test_chat_prompt_cache.py does.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import main  # noqa: E402
from main import app  # noqa: E402

from api.chat_selection import MAX_ROOMS, MAX_ROWS, build_chat_selection  # noqa: E402
from tests.test_chat_prompt_cache import _capture_call, _own_database  # noqa: E402,F401  (autouse fixture)


def _project():
    rooms = [
        {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "plotas_saltinis": "eksplikacija",
         "perimetras_m": 21.23, "puslapio_nr": 1},
        {"nr": "04", "pavadinimas": "Svetainė", "plotas_m2": 30.5, "plotas_saltinis": "eksplikacija",
         "perimetras_m": 24.0, "puslapio_nr": 1},
        {"nr": "07", "pavadinimas": "Sandėliukas", "plotas_m2": 2.25, "plotas_saltinis": "eksplikacija",
         "perimetras_m": 6.1, "puslapio_nr": 1},
    ]
    rows = [{
        "id": "r-walls", "aprasymas": "Sienų glaistymas/dažymas", "mato_vnt": "m²", "kiekis": 99.92,
        "skyrius": "Sienos",
        "contributions": [
            {"room_nr": "03", "room_name": "Koridorius", "value": 49.92, "unit": "m2", "included_because": "Sienos dažomos"},
            {"room_nr": "04", "room_name": "Svetainė", "value": 50.0, "unit": "m2", "included_because": "Sienos dažomos"},
        ],
        "excluded": [{"room_nr": "07", "room_name": "Sandėliukas", "excluded_because": "Nedažoma"}],
        "roll_up": [{"op": "sum", "label": "Σ 2 patalpų", "value": 99.92}],
    }, {"id": "r-floor", "aprasymas": "Grindų dažymas", "mato_vnt": "m²", "kiekis": 12.0}]
    return {"name": "T", "patalpos": rooms, "darbu_sarasas": rows}


def test_the_block_carries_the_room_sentences_and_the_row_ledger_and_nothing_else():
    text, given = build_chat_selection(_project(), {"rooms": ["03"], "rows": ["r-walls"]})
    assert text.startswith("PASIRINKTA")
    # the room's read facts with their „iš kur" sentences
    assert "Patalpa 03 · Koridorius" in text and "plotas: 10,12 m² (perskaityta)" in text
    assert "Iš patalpų eksplikacijos lentelės, eilutė 03." in text
    # the row's ledger: rooms, what was left out, the roll-up
    assert "Eilutė „Sienų glaistymas/dažymas“ (skyrius „Sienos“): 99,92 m²" in text
    assert "04 Svetainė: 50,00 m² (Sienos dažomos)" in text
    assert "neįtraukta: 07 Sandėliukas — Nedažoma" in text and "Eiga: Σ 2 patalpų = 99,92" in text
    # a room he did not pick has no room block of its own
    assert "Patalpa 04" not in text and "Patalpa 07" not in text
    assert "Grindų dažymas" not in text
    assert given["rooms"] == [{"nr": "03", "name": "Koridorius"}]
    assert given["rows"] == [{"id": "r-walls", "aprasymas": "Sienų glaistymas/dažymas"}]


def test_nothing_selected_is_no_block():
    assert build_chat_selection(_project(), None)[0] is None
    assert build_chat_selection(_project(), {"rooms": [], "rows": []})[0] is None
    assert build_chat_selection(_project(), {"rooms": "03", "rows": [{"x": 1}, True]})[0] is None
    text, given = build_chat_selection(_project(), {"rooms": ["99"]})
    assert text is None and given["not_found"]["rooms"] == ["99"]


def test_the_caps_hold_and_the_block_says_what_was_left_out():
    p = _project()
    p["patalpos"] = [{"nr": f"{i:02d}", "pavadinimas": f"P{i}", "plotas_m2": 5.0, "plotas_saltinis": "eksplikacija"}
                     for i in range(1, 16)]
    p["darbu_sarasas"] = [{"id": f"r{i}", "aprasymas": f"Eilutė {i}", "kiekis": i} for i in range(40)]
    text, given = build_chat_selection(p, {"rooms": [f"{i:02d}" for i in range(1, 16)],
                                           "rows": [f"r{i}" for i in range(40)]})
    assert len(given["rooms"]) == MAX_ROOMS == 12 and len(given["rows"]) == MAX_ROWS == 30
    assert given["left_out"] == {"rooms": ["13", "14", "15"], "rows": [f"r{i}" for i in range(30, 40)]}
    assert "čia tik pirmos 12; neįtrauktos: 13, 14, 15." in text
    assert "čia tik pirmos 30; neįtrauktos — 10." in text
    assert "Patalpa 13" not in text


def test_the_selection_rides_in_the_last_user_turn_after_the_cached_blocks(monkeypatch):
    captured = _capture_call(monkeypatch)
    main.db.upsert_project("p1", _project())
    with TestClient(app) as tc:
        body = tc.post("/chat-project", json={
            "project_id": "p1",
            "messages": [{"role": "user", "content": "ankstesnis"}, {"role": "assistant", "content": "atsakymas"},
                         {"role": "user", "content": "Kiek dažomo ploto šiose patalpose?"}],
            "selection": {"rooms": ["03", "04"], "rows": ["r-walls"]},
        }).json()
    assert body["status"] == "ok"
    assert [r["nr"] for r in body["given"]["rooms"]] == ["03", "04"]
    msgs = captured["messages"]
    # the cached context is still only the project, and still the only cached message
    assert "PASIRINKTA" not in msgs[0]["content"][0]["text"]
    breakpoints = len(captured["system"]) + sum(
        1 for m in msgs if isinstance(m["content"], list) for b in m["content"] if "cache_control" in b)
    assert breakpoints == 2
    # history untouched; the last turn = the block + his question, as a plain string
    assert [m["content"] for m in msgs[2:4]] == ["ankstesnis", "atsakymas"]
    last = msgs[-1]
    assert last["role"] == "user" and isinstance(last["content"], str)
    assert last["content"].startswith("PASIRINKTA") and last["content"].endswith("KLAUSIMAS: Kiek dažomo ploto šiose patalpose?")
    assert "Patalpa 04 · Svetainė" in last["content"] and "Patalpa 07" not in last["content"]


def test_no_selection_leaves_the_turns_exactly_as_before(monkeypatch):
    captured = _capture_call(monkeypatch)
    main.db.upsert_project("p1", _project())
    with TestClient(app) as tc:
        body = tc.post("/chat-project", json={"project_id": "p1", "question": "Kiek patalpų?"}).json()
    assert body["status"] == "ok" and body["given"]["rooms"] == [] and body["given"]["rows"] == []
    assert captured["messages"][-1] == {"role": "user", "content": "Kiek patalpų?"}


def test_the_prompt_says_to_answer_about_the_selection_and_never_to_change_a_quantity():
    p = main._CHAT_SYSTEM_PROMPT
    assert "Atsakyk PIRMIAUSIA apie pažymėtas patalpas ir eilutes" in p
    assert "Cituok bloke pateiktus skaičius" in p
    assert "pokalbis kiekių\nnekeičia" in p

"""The doors reader reads EVERY plan sheet that holds rooms (audit 2026-09-30,
vision-pipeline-6).

It used to read one floor-plan page and then replace the doors of every room
in the project, so a project whose rooms sit on two sheets (two storeys) lost
the doors of every room on the sheet it did not read. Now: one read per sheet
that holds rooms, each sheet's doors go only to the rooms on that sheet, and a
room on a sheet that was not read keeps the doors the first pass gave it.

No model is called: the page render and the client are stubs.
"""
import json
from types import SimpleNamespace

import pytest

from extractor import doors_reader


def _rooms():
    # pass-1 gave every room one door; rooms sit on sheets 1 and 2
    return [
        {"nr": "101", "pavadinimas": "Tambūras", "paskirtis": "tamburas", "puslapio_nr": 1,
         "elementai": [{"tipas": "duris", "kiekis": 1}]},
        {"nr": "102", "pavadinimas": "Koridorius", "paskirtis": "koridorius", "puslapio_nr": 1,
         "elementai": [{"tipas": "duris", "kiekis": 1}]},
        {"nr": "201", "pavadinimas": "Holas", "paskirtis": "holas", "puslapio_nr": 2,
         "elementai": [{"tipas": "duris", "kiekis": 1}]},
        {"nr": "202", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji", "puslapio_nr": 2,
         "elementai": [{"tipas": "duris", "kiekis": 1}, {"tipas": "langas", "kiekis": 1}]},
    ]


# what the stub "sees" on each sheet
_ANSWERS = {
    1: {"doors": [{"tipas": "standart", "between": ["101", "exterior"]},
                  {"tipas": "standart", "between": ["102", "101"]},
                  {"tipas": "pasleptos", "between": ["102", "101"]}],
        "total_count": 3, "exterior_count": 1},
    2: {"doors": [{"tipas": "standart", "between": ["201", "202"]},
                  {"tipas": "standart", "between": ["201", "202"]},
                  {"tipas": "standart", "between": ["201", "202"]},
                  {"tipas": "standart", "between": ["201", "202"]}],
        "total_count": 4, "exterior_count": 0},
}


class _StubClient:
    def __init__(self, fail_pages=()):
        self.fail_pages = set(fail_pages)
        self.calls = []            # (page, user_text)

    @property
    def messages(self):
        return self

    def create(self, **kw):
        content = kw["messages"][0]["content"]
        page = int(content[0]["source"]["data"].removeprefix("PAGE"))
        self.calls.append((page, content[1]["text"]))
        assert "temperature" not in kw and "top_p" not in kw and "top_k" not in kw
        if page in self.fail_pages:
            raise RuntimeError("stub: call failed")
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(_ANSWERS[page]))],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=100, output_tokens=10))


@pytest.fixture(autouse=True)
def _no_render(monkeypatch):
    monkeypatch.setattr(doors_reader, "_render_page_b64",
                        lambda pdf_bytes, page, dpi=220: f"PAGE{page}")


def _n_doors(room):
    return sum(int(e.get("kiekis") or 1) for e in room.get("elementai") or []
               if (e.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))


def test_both_plan_sheets_are_read_and_each_room_gets_its_own_sheets_doors():
    rooms = _rooms()
    client = _StubClient()
    res = doors_reader.read_doors_from_plan_pages(
        b"%PDF", rooms, page_classifications=[{"nr": 1, "tipas": "floor_plan"},
                                              {"nr": 2, "tipas": "floor_plan"}],
        client=client)

    assert [p for p, _ in client.calls] == [1, 2], "one read per sheet that holds rooms"
    # each read lists only the rooms drawn on that sheet
    listed = [text.split("Galimi exterior")[0] for _, text in client.calls]
    assert "101" in listed[0] and "201" not in listed[0]
    assert "201" in listed[1] and "101" not in listed[1]
    assert res["status"] == "ok"
    assert res["pages_read"] == [1, 2]
    assert res["total_count"] == 7
    from extractor.vision_call import _reader_call_metas
    assert len(_reader_call_metas(res)) == 2, "both paid calls are metered"

    updated = doors_reader.merge_doors_by_page(rooms, res)
    by_nr = {r["nr"]: r for r in rooms}
    assert _n_doors(by_nr["101"]) == 1
    assert _n_doors(by_nr["102"]) == 2
    assert _n_doors(by_nr["201"]) == 4
    assert _n_doors(by_nr["202"]) == 0
    assert updated == 3
    assert any(e.get("tipas") == "langas" for e in by_nr["202"]["elementai"])


def test_a_room_on_a_sheet_that_was_not_read_keeps_its_first_pass_doors():
    rooms = _rooms()
    client = _StubClient(fail_pages={2})
    res = doors_reader.read_doors_from_plan_pages(b"%PDF", rooms, client=client)

    assert res["status"] == "ok"
    assert res["pages_read"] == [1]
    assert res["pages_unread"] == [2]
    doors_reader.merge_doors_by_page(rooms, res)
    by_nr = {r["nr"]: r for r in rooms}
    # sheet 1 replaced by the reader
    assert _n_doors(by_nr["101"]) == 1 and _n_doors(by_nr["102"]) == 2
    # sheet 2 never read: the first pass's doors stay
    assert _n_doors(by_nr["201"]) == 1 and _n_doors(by_nr["202"]) == 1


def test_one_sheets_reader_cannot_erase_doors_on_another_sheet():
    """The old defect: sheet 1's doors were merged into ALL rooms, erasing the
    doors of every room on sheet 2 (whose numbers sheet 1 never names)."""
    rooms = _rooms()
    res = doors_reader.read_doors_from_plan_pages(
        b"%PDF", [r for r in rooms if r["puslapio_nr"] == 1], client=_StubClient())
    assert res["pages_read"] == [1]
    doors_reader.merge_doors_by_page(rooms, res)
    by_nr = {r["nr"]: r for r in rooms}
    assert _n_doors(by_nr["201"]) == 1 and _n_doors(by_nr["202"]) == 1


def test_a_single_sheet_project_reads_that_sheet_once():
    rooms = [r for r in _rooms() if r["puslapio_nr"] == 2]
    client = _StubClient()
    res = doors_reader.read_doors_from_plan_pages(
        b"%PDF", rooms,
        page_classifications=[{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
        client=client)
    # the sheet the rooms are on — not the first sheet classified as a plan
    assert [p for p, _ in client.calls] == [2]
    assert res["page"] == 2


def test_rooms_without_a_sheet_fall_back_to_the_one_plan_page_for_all_rooms():
    rooms = _rooms()
    for r in rooms:
        r.pop("puslapio_nr")
    client = _StubClient()
    res = doors_reader.read_doors_from_plan_pages(
        b"%PDF", rooms, page_classifications=[{"nr": 1, "tipas": "floor_plan"}], client=client)
    assert [p for p, _ in client.calls] == [1]
    doors_reader.merge_doors_by_page(rooms, res)
    by_nr = {r["nr"]: r for r in rooms}
    # the previous behaviour: that one read applies to every room
    assert _n_doors(by_nr["101"]) == 1 and _n_doors(by_nr["102"]) == 2
    assert _n_doors(by_nr["201"]) == 0 and _n_doors(by_nr["202"]) == 0


def test_every_sheet_failing_is_an_error_and_changes_nothing():
    rooms = _rooms()
    res = doors_reader.read_doors_from_plan_pages(
        b"%PDF", rooms, client=_StubClient(fail_pages={1, 2}))
    assert res["status"] == "error"
    assert res["pages_unread"] == [1, 2]
    assert doors_reader.merge_doors_by_page(rooms, res) == 0
    assert [_n_doors(r) for r in rooms] == [1, 1, 1, 1]

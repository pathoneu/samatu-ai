"""Multi-floor parsing helpers (Sprint §16, 2026-04-29)."""

from extractor.universal_rules import room_aukstas_from_nr, group_rooms_by_floor


class TestAukstasFromNr:
    def test_arabic_prefix(self):
        assert room_aukstas_from_nr("1F-01") == 1
        assert room_aukstas_from_nr("2F-05") == 2
        assert room_aukstas_from_nr("3F-02") == 3
        assert room_aukstas_from_nr("2-05") == 2

    def test_roman_prefix(self):
        assert room_aukstas_from_nr("I-01") == 1
        assert room_aukstas_from_nr("II-12") == 2
        assert room_aukstas_from_nr("III-08") == 3

    def test_cellar(self):
        assert room_aukstas_from_nr("P-01") == 0
        assert room_aukstas_from_nr("0F-01") == 0
        assert room_aukstas_from_nr("0-01") == 0

    def test_plain_numbers_default_to_1(self):
        # 2026-05-10: bare room numbers ("01", "12", "99") with no floor
        # prefix must default to floor 1. Pre-fix the function naively took
        # the first digit ("99" → floor 9) which split a real 2-storey LT
        # project into 9 phantom floors — see test_room_aukstas_from_nr.py
        # for the fuller LT-convention coverage including "X.Y" compound nrs.
        assert room_aukstas_from_nr("01") == 1
        assert room_aukstas_from_nr("12") == 1
        assert room_aukstas_from_nr("99") == 1
        # Explicit cellar prefix still wins:
        assert room_aukstas_from_nr("0F-01") == 0
        assert room_aukstas_from_nr("P-01") == 0

    def test_empty_or_none(self):
        assert room_aukstas_from_nr("") == 1
        assert room_aukstas_from_nr(None) == 1
        assert room_aukstas_from_nr(" ") == 1


class TestGroupRoomsByFloor:
    def test_explicit_aukstas_field_wins(self):
        rooms = [
            {"nr": "1F-01", "aukstas": 2},  # explicit overrides nr
            {"nr": "1F-02", "aukstas": 1},
        ]
        out = group_rooms_by_floor(rooms)
        assert sorted(out.keys()) == [1, 2]
        assert len(out[2]) == 1
        assert len(out[1]) == 1

    def test_falls_back_to_nr_parsing(self):
        rooms = [
            {"nr": "1F-01", "pavadinimas": "Holas"},
            {"nr": "2F-01", "pavadinimas": "Miegamasis"},
            {"nr": "2F-02", "pavadinimas": "Vonia"},
        ]
        out = group_rooms_by_floor(rooms)
        assert len(out[1]) == 1
        assert len(out[2]) == 2

    def test_empty_rooms(self):
        assert group_rooms_by_floor([]) == {}
        assert group_rooms_by_floor(None) == {}

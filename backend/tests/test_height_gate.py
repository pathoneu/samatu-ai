"""Height plausibility gate (2026-06-11 Bacevičiaus experiment).

Vision mis-attributed the tall ceiling: 3.5 m on a 6.8 m² wet room + 2.9 m² WC,
while the 62 m² svetainė got the 2.82 default → inverted the iki/virš-3m split
(iki +127%, virš −86%). Tall ceilings (>3m) belong to large open-plan living
spaces, never to small wet/service rooms. The gate redistributes.
"""
from extractor.universal_rules import apply_height_plausibility_gate


def _r(nr, pavadinimas, paskirtis, plotas, H):
    return {"nr": nr, "pavadinimas": pavadinimas, "paskirtis": paskirtis,
            "plotas_m2": plotas, "lubu_aukstis_m": H,
            "lubu_aukstis_saltinis": "per_room" if H > 3.0 else "section_average"}


def test_reattributes_tall_height_from_wet_room_to_living_room():
    rooms = [
        _r("1", "Svetainė/virtuvė", "gyvenamoji", 62.0, 2.82),  # the real tall zone
        _r("2", "Vaikų vonia", "vonia", 6.8, 3.5),               # Vision misread
        _r("3", "Svečių wc", "wc", 2.9, 3.5),                    # Vision misread
        _r("4", "Miegamasis", "miegamoji", 14.0, 2.82),
    ]
    corr = apply_height_plausibility_gate(rooms)
    by = {r["nr"]: r for r in rooms}
    assert by["1"]["lubu_aukstis_m"] == 3.5      # tall height moved to the svetainė
    assert by["2"]["lubu_aukstis_m"] <= 3.0      # wet room reset to plausible
    assert by["3"]["lubu_aukstis_m"] <= 3.0
    assert corr  # corrections recorded for transparency
    assert by["1"].get("_height_gate")


def test_does_not_fire_when_tall_room_is_large_living():
    # Beržų pattern: the tall room IS the large living room → leave alone.
    rooms = [
        _r("1", "Svetainė/virtuvė", "gyvenamoji", 50.5, 3.4),
        _r("2", "Tambūras", "tamburas", 5.0, 2.8),
        _r("3", "Vonia", "vonia", 6.0, 2.8),
    ]
    corr = apply_height_plausibility_gate(rooms)
    assert corr == []
    assert rooms[0]["lubu_aukstis_m"] == 3.4     # unchanged


def test_clamps_when_no_living_candidate():
    # Tall wet room but no large living room to receive it → just clamp it down.
    rooms = [
        _r("1", "Vonia", "vonia", 6.0, 3.6),
        _r("2", "Tambūras", "tamburas", 4.0, 2.8),
    ]
    corr = apply_height_plausibility_gate(rooms)
    assert rooms[0]["lubu_aukstis_m"] <= 3.0
    assert corr


def test_no_op_when_all_heights_plausible():
    rooms = [_r("1", "Svetainė", "gyvenamoji", 40.0, 2.82),
             _r("2", "Vonia", "vonia", 6.0, 2.82)]
    assert apply_height_plausibility_gate(rooms) == []

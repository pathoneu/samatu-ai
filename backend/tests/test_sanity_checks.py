"""Sprint 4 Block C: sanity checks fire/quiet correctly on synthetic data."""
from extractor.sanity_checks import (
    check_paintable_wall_to_floor,
    check_ceiling_to_floor,
    check_baseboard_perimeter,
    check_paint_quantity,
    check_gk_sheets_math,
    check_window_reveals,
    check_perimeter_geometric_minimum,
    run_all_checks,
)


def test_paintable_wall_to_floor_passes_in_band():
    rooms = [{"plotas_m2": 100, "walls_paintable_m2": 300}]  # ratio 3.0
    assert check_paintable_wall_to_floor(rooms) is None


def test_paintable_wall_to_floor_fires_below_band():
    rooms = [{"plotas_m2": 100, "walls_paintable_m2": 150}]  # ratio 1.5
    w = check_paintable_wall_to_floor(rooms)
    assert w is not None
    assert w.code == "paintable_floor_ratio"
    # LT decimal comma — these strings render verbatim in the sanity banner.
    assert "1,50" in w.actual


def test_paintable_wall_to_floor_fires_above_band():
    rooms = [{"plotas_m2": 100, "walls_paintable_m2": 500}]  # ratio 5.0
    w = check_paintable_wall_to_floor(rooms)
    assert w is not None
    assert w.severity == "high"


def test_ceiling_to_floor_passes_at_unity():
    rooms = [{"plotas_m2": 100, "ceiling_paintable_m2": 100}]
    assert check_ceiling_to_floor(rooms) is None


def test_ceiling_to_floor_passes_with_soffit_band():
    rooms = [{"plotas_m2": 100, "ceiling_paintable_m2": 92}]  # 8% under
    assert check_ceiling_to_floor(rooms) is None


def test_ceiling_to_floor_fires_when_far_off():
    rooms = [{"plotas_m2": 100, "ceiling_paintable_m2": 70}]  # 30% under
    w = check_ceiling_to_floor(rooms)
    assert w is not None
    assert w.code == "ceiling_floor_mismatch"


def test_baseboard_perimeter_passes_when_close():
    rooms = [{
        "perimetras_m": 40,
        "elementai": [{"type": "durys"}, {"type": "durys"}],
        "derived": {"grindjuostes_m": 38},  # 40 - 2*0.8 = 38.4
    }]
    assert check_baseboard_perimeter(rooms) is None


def test_baseboard_perimeter_fires_when_double_counted():
    # Double-counted grindjuostės is the bug Block B fixes
    rooms = [{
        "perimetras_m": 40,
        "elementai": [{"type": "durys"}, {"type": "durys"}],
        "derived": {"grindjuostes_m": 76},  # 2x expected
    }]
    w = check_baseboard_perimeter(rooms)
    assert w is not None
    assert w.code == "baseboard_perimeter_mismatch"


def test_paint_quantity_passes_at_typical_rate():
    rooms = [{"walls_paintable_m2": 100, "ceiling_paintable_m2": 50, "dazai_l": 33, "dazai_luboms_l": 0}]
    # 33 / 150 = 0.22 ✓
    assert check_paint_quantity(rooms) is None


def test_paint_quantity_fires_when_overconsumed():
    rooms = [{"walls_paintable_m2": 100, "dazai_l": 50}]  # 0.5 l/m² way too high
    w = check_paint_quantity(rooms)
    assert w is not None
    assert w.code == "paint_consumption_rate"


def test_window_reveals_passes_at_5m_avg():
    rooms = [{"elementai": [
        {"type": "langas", "angokrasciu_ilgis_m": 5.0},
        {"type": "langas", "angokrasciu_ilgis_m": 4.5},
    ]}]
    assert check_window_reveals(rooms) is None


def test_window_reveals_fires_when_zero():
    rooms = [{"elementai": [
        {"type": "langas"},
        {"type": "langas", "angokrasciu_ilgis_m": 0},
    ]}]
    w = check_window_reveals(rooms)
    assert w is not None
    assert w.code == "window_reveals_zero"


def test_run_all_checks_returns_list_of_dicts():
    rooms = [{"plotas_m2": 100, "walls_paintable_m2": 150, "ceiling_paintable_m2": 100, "perimetras_m": 40}]
    warnings = run_all_checks({"patalpos": rooms})
    assert isinstance(warnings, list)
    assert all(isinstance(w, dict) for w in warnings)
    # Should fire on paintable_wall_to_floor (1.5 < 2.5)
    codes = [w["code"] for w in warnings]
    assert "paintable_floor_ratio" in codes


def test_run_all_checks_handles_empty():
    assert run_all_checks({"patalpos": []}) == []


def test_run_all_checks_swallows_exceptions():
    # If a check raises, run_all_checks should NOT propagate
    bad_room = {"perimetras_m": "not-a-number"}  # Forces ValueError on float()
    result = run_all_checks({"patalpos": [bad_room]})
    assert isinstance(result, list)  # didn't raise


def test_gk_sheets_math_passes_when_pozicija_matches_formula():
    rooms = [{"gkp_lubu_standart_m2": 148.88}]
    # ceil(148.88/3.0) * 1.10 = ceil(49.6) * 1.10 = 50 * 1.10 = 55.0
    pozicijos = [{"aprasymas": "GKP lapai luboms (9.5 mm)", "vnt": "vnt", "kiekis": 55}]
    assert check_gk_sheets_math(rooms, {"pozicijos": pozicijos}) is None


def test_gk_sheets_math_fires_when_pozicija_off_by_more_than_5pct():
    rooms = [{"gkp_lubu_standart_m2": 148.88}]
    # Expected ~55, actual 70 → ~27% off → should fire.
    pozicijos = [{"aprasymas": "GKP lapai luboms (9.5 mm)", "vnt": "vnt", "kiekis": 70}]
    w = check_gk_sheets_math(rooms, {"pozicijos": pozicijos})
    assert w is not None
    assert w.code == "gk_sheets_off"


def test_gk_sheets_math_skipped_when_no_gkp_area():
    rooms = [{"gkp_lubu_standart_m2": 0}]
    pozicijos = [{"aprasymas": "GKP lapai luboms", "vnt": "vnt", "kiekis": 10}]
    assert check_gk_sheets_math(rooms, {"pozicijos": pozicijos}) is None


def test_gk_sheets_math_skipped_when_no_pozicija():
    rooms = [{"gkp_lubu_standart_m2": 100}]
    assert check_gk_sheets_math(rooms, {"pozicijos": []}) is None



def test_baseboard_check_counts_pipeline_doors_and_skips_tiled_floors():
    """Live rooms carry `tipas: duris` (× kiekis), and a tiled bathroom has no
    baseboard to expect — both were missed, so a fresh project read
    „− 0 durys" and warned against every room's perimeter (2026-09-10)."""
    from extractor.sanity_checks import check_baseboard_perimeter
    rooms = [
        {"nr": "01", "perimetras_m": 20.0, "grindjuosciu_m": 18.4,
         "elementai": [{"tipas": "duris", "kiekis": 2}]},
        {"nr": "03", "perimetras_m": 8.0, "grindjuosciu_m": 0.0, "plyteles_grindys_m2": 3.5,
         "elementai": [{"tipas": "duris", "kiekis": 1}]},
    ]
    # 18,4 against 20 − 2 × 0,8 = 18,4 → no warning (the bathroom is not expected)
    assert check_baseboard_perimeter(rooms) is None
    rooms[0]["grindjuosciu_m"] = 12.0
    w = check_baseboard_perimeter(rooms)
    assert w is not None and "2 durys" in w.message


def test_a_perimeter_below_the_square_of_its_area_is_impossible():
    # 4·√3,52 = 7,50 — Vision's 7,08 m around a 3,52 m² WC cannot exist
    rooms = [{"nr": "03", "pavadinimas": "Vonia", "plotas_m2": 3.52, "perimetras_m": 7.08},
             {"nr": "04", "pavadinimas": "Kambarys", "plotas_m2": 10.05, "perimetras_m": 12.68}]
    w = check_perimeter_geometric_minimum(rooms)
    assert w is not None and w.code == "perimeter_below_geometric_minimum"
    assert "1 patalpos" in w.message and "03 Vonia" in w.message and "7,08 m" in w.actual and "7,50" in w.actual
    assert "04" not in w.actual, "a square-ish room at exactly the minimum passes"
    assert check_perimeter_geometric_minimum([{"plotas_m2": 10.05, "perimetras_m": 12.68}]) is None
    codes = {x["code"] for x in run_all_checks({"patalpos": rooms})}
    assert "perimeter_below_geometric_minimum" in codes

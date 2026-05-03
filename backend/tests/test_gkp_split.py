"""Sprint 0 Fix 1: GKP wall (12.5mm) and ceiling (9.5mm) get separate pozicijos."""
import sys
from pathlib import Path

# Ensure backend/ is on path so extractor package imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.vision_call import build_gkp_pozicijos


def test_gkp_split_into_wall_and_ceiling_lines():
    rooms = [
        {"name": "Kambarys 1", "sienos_gkp_m2": 30.0, "lubos_gkp_m2": 12.0},
        {"name": "Kambarys 2", "sienos_gkp_m2": 20.0, "lubos_gkp_m2": 8.0},
    ]
    pozicijos = build_gkp_pozicijos(rooms)

    wall_lines = [p for p in pozicijos if "sienoms" in p["aprasymas"]]
    ceiling_lines = [p for p in pozicijos if "luboms" in p["aprasymas"]]

    assert len(wall_lines) == 1
    assert len(ceiling_lines) == 1
    assert "12.5 mm" in wall_lines[0]["aprasymas"]
    assert "9.5 mm" in ceiling_lines[0]["aprasymas"]
    # 50 m² walls → ceil(50/3.0 * 1.10) = 19 sheets
    assert wall_lines[0]["kiekis"] == 19
    # 20 m² ceilings → ceil(20/3.0 * 1.10) = 8 sheets
    assert ceiling_lines[0]["kiekis"] == 8


def test_gkp_zero_ceiling_yields_no_ceiling_line():
    rooms = [{"name": "Kambarys", "sienos_gkp_m2": 30.0, "lubos_gkp_m2": 0.0}]
    pozicijos = build_gkp_pozicijos(rooms)
    assert not any("luboms" in p["aprasymas"] for p in pozicijos)

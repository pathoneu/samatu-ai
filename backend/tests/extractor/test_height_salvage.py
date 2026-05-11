"""Salvage tests — mine height info out of Vision warnings[] text
when the structured fields stayed empty.

W2 2026-05-11: deterministic salvage pass in vision_call.py Step 2.45
calls extractor.height_markers.salvage_heights_from_warnings. These
tests pin the behaviour against the real warning text observed on
projektas_3 + projektas_4(2) corpus PDFs.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extractor.height_markers import salvage_heights_from_warnings  # noqa: E402


def test_salvage_named_room_with_metres():
    """The 'Katilinė ... 2.94m' phrasing on projektas_3 must produce
    {'Katilinė': 2.94, 'San. mazgas 4': 2.94}."""
    warnings = [{
        "message": "Katilinė ir san. mazgas 4 plane rodo 'švarus lubų aukštis 2.94m'.",
    }]
    rooms = [
        {"pavadinimas": "Katilinė", "paskirtis": "katiline"},
        {"pavadinimas": "San. mazgas 4", "paskirtis": "vonia"},
        {"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"},
    ]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out.get("Katilinė") == 2.94
    assert out.get("San. mazgas 4") == 2.94
    # Svetainė isn't named in this warning — must not get a height
    assert "Svetainė" not in out


def test_salvage_paskirtis_phrase_visose_voniose():
    """projektas_4(2): 'Lubų aukštis 3200mm visose voniose' should
    map to all rooms with paskirtis=vonia."""
    warnings = [{
        "message": "Lubų aukštis 3200mm visose voniose pažymėtas išklotinėse.",
    }]
    rooms = [
        {"pavadinimas": "Vaikų san. mazgas", "paskirtis": "vonia"},
        {"pavadinimas": "Tėvų san. mazgas", "paskirtis": "vonia"},
        {"pavadinimas": "Techninė", "paskirtis": "techpatalpa"},
    ]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out["Vaikų san. mazgas"] == 3.2
    assert out["Tėvų san. mazgas"] == 3.2
    assert "Techninė" not in out  # paskirtis doesn't match


def test_salvage_centimetre_format():
    """'300cm' must convert to 3.00 m, not stay as 300."""
    warnings = [{
        "message": "Svetainėje švarus lubų aukštis 300cm pagal pjūvį.",
    }]
    rooms = [{"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"}]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out["Svetainė"] == 3.0


def test_salvage_marker_format():
    """'+3000' or '+3.000' drafting marker should be extracted."""
    warnings = [{
        "message": "Svetainėje lubos +3000mm; kitose +2800mm.",
    }]
    rooms = [
        {"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"},
        {"pavadinimas": "Miegamasis", "paskirtis": "miegamoji"},
    ]
    out = salvage_heights_from_warnings(warnings, rooms)
    # The warning explicitly names Svetainė with the higher number
    assert out["Svetainė"] == 3.0


def test_salvage_no_height_no_output():
    """Warning without any height pattern must produce nothing."""
    warnings = [{"message": "Premium archetipas su mediniais grindiniais."}]
    rooms = [{"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"}]
    assert salvage_heights_from_warnings(warnings, rooms) == {}


def test_salvage_height_out_of_range_filtered():
    """A 'value' like 10 m or 1.5 m must NOT be salvaged — outside
    plausible ceiling range [2.0, 4.5]."""
    warnings = [{
        "message": "Svetainėje lubos 1.5m (tipo namelis); arba 10.0m.",
    }]
    rooms = [{"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"}]
    out = salvage_heights_from_warnings(warnings, rooms)
    # Both values are out of range; nothing should be salvaged
    assert out == {}


def test_salvage_empty_inputs():
    assert salvage_heights_from_warnings([], []) == {}
    assert salvage_heights_from_warnings([], [{"pavadinimas": "X"}]) == {}
    assert salvage_heights_from_warnings([{"message": "test"}], []) == {}


def test_salvage_returns_max_height_per_warning():
    """When multiple heights appear in one warning, return the highest
    (the bug being salvaged is always 'Vision saw a NON-default height'
    — defaults wouldn't be narrated)."""
    warnings = [{
        "message": "Svetainė: pjūvyje +2.40m sija, +3.20m lubos.",
    }]
    rooms = [{"pavadinimas": "Svetainė", "paskirtis": "gyvenamoji"}]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out["Svetainė"] == 3.2  # max, not the beam underside

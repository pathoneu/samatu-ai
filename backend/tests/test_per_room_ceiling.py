"""Sprint 0 Fix 4: when Vision returns per-room ceiling heights,
backend uses them; otherwise falls back to single-section average."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from extractor.vision_call import _apply_per_room_heights


def test_per_room_heights_applied_when_present(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")
    rooms = [{"name": "K1"}, {"name": "K2"}, {"name": "K3"}]
    per_room = {"K1": 2.65, "K2": 2.40}  # K3 missing → fallback
    avg = 2.70
    result = _apply_per_room_heights(rooms, per_room, avg)
    assert result[0]["lubu_aukstis_m"] == 2.65
    assert result[0]["lubu_aukstis_saltinis"] == "per_room"
    assert result[1]["lubu_aukstis_m"] == 2.40
    assert result[2]["lubu_aukstis_m"] == 2.70  # fallback to average
    assert result[2]["lubu_aukstis_saltinis"] == "section_average"


def test_flag_off_uses_average_for_all(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "0")
    rooms = [{"name": "K1"}, {"name": "K2"}]
    per_room = {"K1": 2.65}
    avg = 2.70
    result = _apply_per_room_heights(rooms, per_room, avg)
    # Flag off → all rooms use the average
    assert all(r["lubu_aukstis_m"] == 2.70 for r in result)

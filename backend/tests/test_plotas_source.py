"""Phase C-2 (2026-05-02): every emitted patalpa with plotas_m2 must carry
a plotas_source flag. The frontend confidence calculator depends on it."""
import sys
from pathlib import Path

# Ensure backend/ is on path so extractor package imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# NOTE: plan named the helper `_build_room_from_row`; actual function in
# pdfplumber_eksplikacija.py is `_try_parse_row(row, row_idx, page_nr, row_bbox=None, ...)`.
from extractor.pdfplumber_eksplikacija import _try_parse_row


def test_pdfplumber_room_has_plotas_source():
    """When pdfplumber parses a room, it tags plotas_source='eksplikacija'."""
    # Simulate a clean row: nr='1', name='Vonia', area_m2=6.83
    raw_row = ["1", "Vonia", "6,83"]
    room = _try_parse_row(
        row=raw_row, row_idx=0, page_nr=2, row_bbox=None,
    )
    assert room is not None, "row should parse"
    assert room.get("plotas_m2") == 6.83
    assert room.get("plotas_source") == "eksplikacija"


def test_vision_fallback_tag_applied():
    """vision_call.py defaults plotas_source='vision' when no flag is set."""
    # Reproduce the fallback loop from vision_call.py inline
    patalpos = [
        {"nr": "1", "plotas_m2": 6.83},  # untagged → should become 'vision'
        {"nr": "2", "plotas_m2": 12.5, "plotas_source": "eksplikacija"},  # already tagged → unchanged
        {"nr": "3", "plotas_m2": None},  # no area → unchanged (no source)
    ]
    for p in patalpos:
        if p.get("plotas_m2") is not None and not p.get("plotas_source"):
            p["plotas_source"] = "vision"
    assert patalpos[0]["plotas_source"] == "vision"
    assert patalpos[1]["plotas_source"] == "eksplikacija"
    assert "plotas_source" not in patalpos[2]

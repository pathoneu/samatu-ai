"""Ground truth schema + loader."""

import pytest
from pathlib import Path

from detector_bench.core.ground_truth import (
    GroundTruth, PageGroundTruth, load_ground_truth, save_ground_truth,
)


def test_round_trip(tmp_path):
    gt = GroundTruth(
        pdf_name="projektas_3_breziniai.pdf",
        page_nr=23,
        dpi=200,
        symbols={"rozete": 47, "jungtukas": 19, "led_strip": 8},
        confirmed_at="2026-05-02T18:00:00Z",
        confirmed_by="user",
        notes="electrical layout, 1st floor",
    )
    path = tmp_path / "p3_p23.yaml"
    save_ground_truth(gt, path)
    assert path.exists()
    loaded = load_ground_truth(path)
    assert loaded.pdf_name == gt.pdf_name
    assert loaded.page_nr == 23
    assert loaded.symbols == gt.symbols
    assert loaded.notes == gt.notes


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_ground_truth(tmp_path / "nope.yaml")


def test_symbols_must_be_int(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "pdf_name: x.pdf\npage_nr: 1\ndpi: 200\n"
        "symbols:\n  rozete: 'twelve'\n"
        "confirmed_at: '2026-05-02'\nconfirmed_by: x\n"
    )
    with pytest.raises(ValueError, match="must be int"):
        load_ground_truth(path)

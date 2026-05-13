"""Append-only writer for training-data crops. Each accept/reject from
the review panel writes one row + one image to data/symbol_training/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from extractor.training_data import record_label  # noqa: E402


def test_record_writes_image_and_jsonl_row(tmp_path, monkeypatch):
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    crop = np.full((30, 30), 200, dtype=np.uint8)
    record_label(
        klass="rozete",
        decision="accept",
        crop=crop,
        meta={"project_id": "p1", "page": 5, "bbox": [100, 200, 30, 30],
              "confidence": 0.92},
    )
    cls_dir = tmp_path / "rozete"
    assert cls_dir.exists()
    pngs = list(cls_dir.glob("*.png"))
    assert len(pngs) == 1
    log = (tmp_path / "labels.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in log.strip().splitlines()]
    assert len(rows) == 1
    assert rows[0]["klass"] == "rozete"
    assert rows[0]["decision"] == "accept"
    assert rows[0]["meta"]["confidence"] == 0.92


def test_reject_decisions_share_class_dir(tmp_path, monkeypatch):
    """Both accept and reject of the same class go in one folder so a
    future YOLO pipeline can build a balanced positives/negatives set."""
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    record_label("rozete", "accept", np.zeros((10, 10), np.uint8), {})
    record_label("rozete", "reject", np.zeros((10, 10), np.uint8), {})
    pngs = list((tmp_path / "rozete").glob("*.png"))
    assert len(pngs) == 2


def test_appends_not_overwrites_log(tmp_path, monkeypatch):
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    record_label("a", "accept", np.zeros((10, 10), np.uint8), {})
    record_label("b", "reject", np.zeros((10, 10), np.uint8), {})
    log = (tmp_path / "labels.jsonl").read_text(encoding="utf-8").strip()
    assert len(log.splitlines()) == 2


def test_filename_records_decision(tmp_path, monkeypatch):
    """Filenames carry the decision so a YOLO data-prep script can split
    positives/negatives without re-reading the JSONL."""
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    record_label("rozete", "accept", np.zeros((10, 10), np.uint8), {})
    record_label("rozete", "reject", np.zeros((10, 10), np.uint8), {})
    names = sorted(p.name for p in (tmp_path / "rozete").glob("*.png"))
    assert any("accept" in n for n in names)
    assert any("reject" in n for n in names)

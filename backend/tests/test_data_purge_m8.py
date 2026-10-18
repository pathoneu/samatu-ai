"""Data (v3 W7-A M8): symbol-training crops follow the data dir and go with
their project; account deletion also removes the per-owner architect legends.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np

import project_purge
from extractor import training_data


def _rec(project_id, klass="rozete"):
    return training_data.record_label(klass, "accept", np.zeros((6, 6), np.uint8),
                                      {"project_id": project_id})


def test_root_follows_the_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DATA_DIR", str(tmp_path))
    mod = importlib.reload(training_data)
    try:
        assert Path(mod.ROOT) == tmp_path / "symbol_training"
    finally:
        monkeypatch.delenv("SAMATU_DATA_DIR")
        importlib.reload(training_data)


def test_project_purge_removes_its_crops_and_legacy_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(training_data, "ROOT", tmp_path)
    mine = _rec("proj-a")
    other = _rec("proj-b")
    # a legacy crop at the root, logged with the project id
    legacy_dir = tmp_path / "rozete"
    legacy_dir.mkdir()
    (legacy_dir / "000001_accept_1.png").write_bytes(b"png")
    (legacy_dir / "000002_accept_1.png").write_bytes(b"png")
    (tmp_path / "labels.jsonl").write_text(
        json.dumps({"klass": "rozete", "image": "rozete/000001_accept_1.png", "meta": {"project_id": "proj-a"}}) + "\n"
        + json.dumps({"klass": "rozete", "image": "rozete/000002_accept_1.png", "meta": {"project_id": "proj-b"}}) + "\n",
        encoding="utf-8")
    assert training_data.purge_project("proj-a") == 2
    assert not mine.exists() and other.exists()
    assert not (legacy_dir / "000001_accept_1.png").exists()
    assert (legacy_dir / "000002_accept_1.png").exists()
    log = (tmp_path / "labels.jsonl").read_text(encoding="utf-8")
    assert "proj-a" not in log and "proj-b" in log
    assert training_data.purge_project("proj-a") == 0   # safe to repeat


def test_project_purge_never_leaves_the_root(monkeypatch, tmp_path):
    monkeypatch.setattr(training_data, "ROOT", tmp_path / "root")
    (tmp_path / "root").mkdir()
    outside = tmp_path / "keep.png"
    outside.write_bytes(b"x")
    (tmp_path / "root" / "labels.jsonl").write_text(
        json.dumps({"image": "../keep.png", "meta": {"project_id": "p"}}) + "\n", encoding="utf-8")
    training_data.purge_project("p")
    assert outside.exists()
    assert training_data.purge_project("../root") == 0


def test_delete_project_runs_the_training_step(monkeypatch, tmp_path):
    monkeypatch.setattr(training_data, "ROOT", tmp_path)
    crop = _rec("proj-z")
    failed = project_purge.purge_project_files("proj-z")
    assert "symbol_training" not in failed
    assert not crop.exists()


def test_account_purge_removes_the_owner_architect_folder(monkeypatch, tmp_path):
    from api import legends
    arch = tmp_path / "legends" / "architect"
    (arch / "user-1").mkdir(parents=True)
    (arch / "user-1" / "biuras.json").write_text("{}", encoding="utf-8")
    (arch / "user-2").mkdir(parents=True)
    (arch / "user-2" / "biuras.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(legends, "ARCHITECT_DIR", arch, raising=False)
    assert project_purge.purge_account_files("user-1") == []
    assert not (arch / "user-1").exists() and (arch / "user-2").exists()
    assert project_purge.purge_account_files("../legends") == []
    assert arch.exists()

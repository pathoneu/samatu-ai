"""2026-07-27 audit finding 6 — one env var roots every server-written data dir.

Annotations, calibrations, F2/F3 project lines and the local PDF store all
defaulted INSIDE the container image (backend/data/…, repo-root/data/…), so on
Render every one of them was wiped by each deploy. They now share a single knob:

    SAMATU_DATA_DIR=/data   →  /data/annotations, /data/calibrations,
                               /data/projects, /data/pdf_store

Unset (dev / CI / this suite by default) → the legacy paths, byte-for-byte.
The READERS (api/project_stats.py, api/export_excel.py) follow the same root as
the writers — otherwise prod would write to the disk and read from the image.
"""
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage  # noqa: E402

_ROOTED = [
    ("api.annotations", "DATA_ROOT", "annotations"),
    ("api.calibrate", "CALIB_ROOT", "calibrations"),
    ("api.project_stats", "ANNOTATIONS_ROOT", "annotations"),
    ("api.project_stats", "CALIB_ROOT", "calibrations"),
    ("api.export_excel", "CALIB_ROOT", "calibrations"),
    ("api.exports_v2", "PROJECTS_DIR", "projects"),
]


@pytest.fixture()
def reload_with_data_dir(monkeypatch):
    """Reload the path-owning modules under a given SAMATU_DATA_DIR, then always
    restore them to the legacy (env-unset) state so test order can't leak."""
    def _reload():
        for mod, _attr, _sub in _ROOTED:
            importlib.reload(importlib.import_module(mod))
    try:
        yield _reload
    finally:
        monkeypatch.delenv("SAMATU_DATA_DIR", raising=False)
        _reload()
        storage.reset_storage_for_test()


def test_data_path_helper_respects_env(tmp_path, monkeypatch):
    legacy = Path("/legacy/annotations")
    monkeypatch.delenv("SAMATU_DATA_DIR", raising=False)
    assert storage.data_path("annotations", legacy) == legacy
    monkeypatch.setenv("SAMATU_DATA_DIR", str(tmp_path))
    assert storage.data_path("annotations", legacy) == tmp_path / "annotations"


def test_all_four_roots_follow_the_env_var(tmp_path, monkeypatch, reload_with_data_dir):
    monkeypatch.setenv("SAMATU_DATA_DIR", str(tmp_path))
    reload_with_data_dir()
    for mod_name, attr, sub in _ROOTED:
        mod = sys.modules[mod_name]
        assert getattr(mod, attr) == tmp_path / sub, f"{mod_name}.{attr}"

    # …and the local PDF store lands there too (no LOCAL_STORAGE_DIR override).
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET", "LOCAL_STORAGE_DIR"):
        monkeypatch.delenv(k, raising=False)
    storage.reset_storage_for_test()
    s = storage.get_storage()
    assert s.name == "LocalDiskStorage"
    assert Path(s.root) == tmp_path / "pdf_store"


def test_writes_actually_land_under_the_env_root(tmp_path, monkeypatch,
                                                 reload_with_data_dir):
    """Not just the constant — a real annotation write must appear on the disk
    we pointed at, and the stats reader must find it there."""
    monkeypatch.setenv("SAMATU_DATA_DIR", str(tmp_path))
    reload_with_data_dir()
    ann = sys.modules["api.annotations"]
    stats = sys.modules["api.project_stats"]

    p = ann._path_for("proj-1")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"schema_version": 1}', encoding="utf-8")

    assert p == tmp_path / "annotations" / "proj-1.json"
    assert p.exists()
    # Reader root == writer root (the bug this test exists to prevent).
    assert stats.ANNOTATIONS_ROOT == ann.DATA_ROOT


def test_unset_keeps_legacy_paths(monkeypatch, reload_with_data_dir):
    monkeypatch.delenv("SAMATU_DATA_DIR", raising=False)
    reload_with_data_dir()
    backend = Path(__file__).resolve().parents[1]
    repo = backend.parent
    assert sys.modules["api.annotations"].DATA_ROOT == backend / "data" / "annotations"
    assert sys.modules["api.calibrate"].CALIB_ROOT == backend / "data" / "calibrations"
    assert sys.modules["api.exports_v2"].PROJECTS_DIR == repo / "data" / "projects"

    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET", "LOCAL_STORAGE_DIR"):
        monkeypatch.delenv(k, raising=False)
    storage.reset_storage_for_test()
    assert Path(storage.get_storage().root) == backend / "data" / "pdf_store"

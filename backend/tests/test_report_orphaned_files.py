"""scripts/report_orphaned_files.py — a READ-ONLY report of stored files whose
project no longer exists (2026-09-30).

Projects deleted before backend/project_purge.py existed left their drawing in
storage and their id-keyed side files on disk. The report lists them; it must
never delete anything. Temporary database, temporary local storage directory,
temporary side-store roots — invented ids only.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

import db
import storage
from api import annotations, calibrate, evidence, exports_v2, legends

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_orphaned_files.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("report_orphaned_files", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _snapshot(root: Path) -> dict[str, bytes]:
    # samatu.db-wal / -shm: the database is in WAL mode, and a read-only SQLite
    # reader creates these housekeeping files when they are absent (in
    # production the running backend already has them). Reading with
    # `immutable=1` instead would skip pages still in the WAL and could report a
    # live project as orphaned, which is worse.
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*"))
            if p.is_file() and not p.name.endswith(("-wal", "-shm"))}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Two live projects (keep-1, keep-2) and files left by three deleted ones."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "samatu.db")
    db.init_schema()
    db._migrate_schema()
    for pid in ("keep-1", "keep-2"):
        db.upsert_project(pid, {"name": f"Projektas {pid}"}, user_id=None)

    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdf_store"))
    storage.reset_storage_for_test()
    backend = storage.get_storage()
    backend.put(storage.pdf_key("keep-1"), b"%PDF-live")
    backend.put(storage.pdf_key("gone-1"), b"%PDF-gone-1")          # 11 bytes
    backend.put(storage.pdf_key("gone-2"), b"%PDF-g2")              # 7 bytes
    backend.put(storage.invoice_key("inv-1"), b"%PDF-invoice")      # not a project file

    roots = {}
    for name, mod, attr in (("annotations", annotations, "DATA_ROOT"),
                            ("calibrations", calibrate, "CALIB_ROOT"),
                            ("legends", legends, "LEGENDS_DIR"),
                            ("evidence_cache", evidence, "CACHE_ROOT"),
                            ("exports", exports_v2, "PROJECTS_DIR")):
        root = tmp_path / "side" / name
        root.mkdir(parents=True)
        monkeypatch.setattr(mod, attr, root)
        roots[name] = root
    (roots["annotations"] / "keep-1.json").write_text("{}")
    (roots["annotations"] / "gone-1.json").write_text('{"a": 1}')   # 8 bytes
    (roots["calibrations"] / "gone-2.json").write_text("{}")        # 2 bytes
    (roots["legends"] / "keep-2.json").write_text("{}")
    (roots["legends"] / "architect").mkdir()
    (roots["legends"] / "architect" / "someone.json").write_text("{}")  # aggregate, not a project
    (roots["evidence_cache"] / "gone-1").mkdir()
    (roots["evidence_cache"] / "gone-1" / "crop.png").write_bytes(b"x" * 100)
    (roots["evidence_cache"] / "gone-1" / "sub").mkdir()
    (roots["evidence_cache"] / "gone-1" / "sub" / "crop2.png").write_bytes(b"y" * 50)
    (roots["exports"] / "keep-1").mkdir()
    (roots["exports"] / "keep-1" / "lines.json").write_text("[]")
    (roots["exports"] / "gone-3").mkdir()
    (roots["exports"] / "gone-3" / "lines.json").write_text("[1]")  # 3 bytes
    yield tmp_path
    storage.reset_storage_for_test()


def test_lists_only_files_of_projects_that_no_longer_exist(world):
    report = _load_script().collect()
    found = {(o["store"], o["project_id"], o["bytes"]) for o in report["orphans"]}
    assert found == {
        ("drawings", "gone-1", 11),
        ("drawings", "gone-2", 7),
        ("annotations", "gone-1", 8),
        ("calibrations", "gone-2", 2),
        ("evidence_cache", "gone-1", 150),
        ("exports", "gone-3", 3),
    }
    assert report["projects_in_db"] == 2
    assert report["stores"]["drawings"] == {"scanned": 3, "orphaned": 2, "bytes": 18}
    assert report["stores"]["legends"] == {"scanned": 1, "orphaned": 0, "bytes": 0}
    assert report["total"] == {"orphaned": 6, "bytes": 18 + 8 + 2 + 150 + 3,
                               "project_ids": 3}


def test_nothing_is_deleted_or_created(world):
    before = _snapshot(world)
    mod = _load_script()
    assert mod.main([]) == 0
    assert mod.main(["--json"]) == 0
    assert _snapshot(world) == before


def test_text_and_json_output(world, capsys):
    mod = _load_script()
    assert mod.main([]) == 0
    text = capsys.readouterr().out
    assert "gone-1" in text and "gone-3" in text and "keep-1" not in text
    assert "nothing was deleted" in text.lower()
    assert mod.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total"]["orphaned"] == 6


def test_missing_database_is_an_error_and_is_not_created(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "nera" / "samatu.db"
    monkeypatch.setattr(db, "_DB_PATH", missing)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdf_store"))
    storage.reset_storage_for_test()
    try:
        assert _load_script().main([]) == 2
    finally:
        storage.reset_storage_for_test()
    assert not missing.exists()
    assert "database" in capsys.readouterr().err.lower()


def test_the_script_cannot_delete():
    """No delete flag and no call that removes anything — by construction."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    forbidden = {"delete", "unlink", "rmtree", "remove", "rmdir", "removedirs",
                 "delete_object", "delete_objects", "purge_project_files", "put",
                 "write_text", "write_bytes", "rename", "replace", "executescript"}
    assert not (called & forbidden), called & forbidden
    strings = [n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any(s.startswith("--") and any(w in s for w in ("delete", "purge", "remove", "clean"))
                   for s in strings)
    assert not any("DELETE" in s or "DROP" in s or "UPDATE " in s for s in strings)


def test_r2_listing_strips_this_deployments_prefix():
    class _Paginator:
        def paginate(self, Bucket, Prefix):
            assert (Bucket, Prefix) == ("b", "dev/projects/")
            yield {"Contents": [{"Key": "dev/projects/p1.pdf", "Size": 5}]}
            yield {"Contents": [{"Key": "dev/projects/p2.pdf", "Size": 7}]}
            yield {}

    class _Client:
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return _Paginator()

    r2 = storage.R2Storage.__new__(storage.R2Storage)
    r2.bucket, r2.key_prefix, r2._client = "b", "dev/", _Client()
    assert list(r2.list_keys("projects/")) == [("projects/p1.pdf", 5), ("projects/p2.pdf", 7)]

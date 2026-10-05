"""scripts/report_backup_retention.py — a READ-ONLY report of which nightly DB
backups a prune with N days would delete (2026-10-05).

The retention (SAMATU_BACKUP_KEEP_DAYS) is the founder's decision and is unset;
this script shows what a given N would do before anyone sets it. It must use
the prune's own rule and never delete anything. Temporary local storage only.
"""
from __future__ import annotations

import ast
import datetime
import importlib.util
import json
from pathlib import Path

import pytest

import backup
import storage

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_backup_retention.py"
UTC = datetime.timezone.utc


def _load_script():
    spec = importlib.util.spec_from_file_location("report_backup_retention", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._load_env = lambda: None     # hermetic: a developer's .env must not steer the test
    return mod


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Ten nightly snapshots 0..9 × 10 days old, plus keys that are not backups."""
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
              "SAMATU_BACKUP_KEEP_DAYS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    root = tmp_path / "pdf_store"
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(root))
    storage.reset_storage_for_test()
    backend = storage.get_storage()
    now = datetime.datetime.now(UTC).replace(microsecond=0)
    snaps = []
    for i in range(10):                                   # newest first
        taken = now - datetime.timedelta(days=10 * i, hours=1)
        key = backup.backup_key(taken.strftime("%Y%m%dT%H%M%SZ"))
        backend.put(key, b"S" * (100 + i))
        snaps.append(key)
    backend.put("backups/samatu-latest.db", b"hand-made copy")
    backend.put("projects/p1.pdf", b"%PDF-drawing")

    def _no_delete(*_a, **_k):
        raise AssertionError("the report deleted something")
    monkeypatch.setattr(storage.LocalDiskStorage, "delete", _no_delete)
    yield {"root": root, "snaps": snaps, "now": now}
    storage.reset_storage_for_test()


def test_lists_what_a_prune_would_delete_and_keep(store):
    report = _load_script().collect(30, now=store["now"])
    snaps = store["snaps"]
    # Ages 0h..90 d+1h, every 10 days: older than 30 days are 40..90 d (6 of
    # them) — but the newest 7 always stay, so only the 3 oldest would go.
    assert [r["key"] for r in report["would_delete"]] == snaps[7:]
    assert [r["key"] for r in report["keep"]] == snaps[:7]
    assert report["ignored"] == [{"key": "backups/samatu-latest.db", "bytes": 14}]
    assert report["total"] == {"snapshots": 10, "would_delete": 3,
                               "would_delete_bytes": 107 + 108 + 109, "keep": 7}
    assert report["storage"]["backend"] == "local"
    assert report["configured_keep_days"] is None
    assert report["keep_newest"] == 7
    # The prune's own rule, not a copy of it.
    plan = backup.retention_plan(snaps + ["backups/samatu-latest.db"], 30, now=store["now"])
    assert [r["key"] for r in report["would_delete"]] == plan["delete"]


def test_nothing_is_deleted_or_written(store):
    before = _tree(store["root"])
    mod = _load_script()
    assert mod.main(["--days", "1"]) == 0
    assert mod.main(["--days", "1", "--json"]) == 0
    assert _tree(store["root"]) == before


def test_text_and_json_output(store, capsys):
    mod = _load_script()
    assert mod.main(["--days", "30"]) == 0
    text = capsys.readouterr().out
    assert "nothing was deleted" in text.lower()
    assert "WOULD DELETE (3)" in text and "KEEP (7)" in text
    assert "samatu-latest.db" in text and "never touched" in text
    assert "SAMATU_BACKUP_KEEP_DAYS unset" in text
    assert mod.main(["--days", "30", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total"]["would_delete"] == 3 and data["days"] == 30


def test_days_come_from_the_flag_or_the_setting(store, monkeypatch, capsys):
    mod = _load_script()
    assert mod.main([]) == 2                              # neither given
    assert "--days" in capsys.readouterr().err
    for bad in ("0", "-2", "abc", "1.5"):
        assert mod.main(["--days", bad]) == 2
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "45")
    assert mod.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["days"] == 45 and data["configured_keep_days"] == 45
    assert data["total"]["would_delete"] == 3             # 50..90 d, beyond the newest 7


def test_the_script_cannot_delete():
    """No delete flag and no call that removes or writes anything — by construction."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
    forbidden = {"delete", "unlink", "rmtree", "remove", "rmdir", "removedirs",
                 "delete_object", "delete_objects", "prune_backups", "put",
                 "write_text", "write_bytes", "rename", "replace", "set_state"}
    assert not (called & forbidden), called & forbidden
    strings = [n.value for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not any(s.startswith("--") and any(w in s for w in ("delete", "prune", "remove", "clean"))
                   for s in strings)

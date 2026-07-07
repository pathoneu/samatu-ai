"""W1.1 (2026-07-03): `model TEXT` column on extractions + usage_events.

Covers: fresh-DB DDL includes the column; _migrate_schema adds it to a
pre-W1.1 DB; re-running the migration on an already-migrated DB is a no-op
(idempotence); record_usage stores model + cache-write-aware cost.
"""
import sqlite3

import pytest

import db


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "model_mig.db")


def _cols(path, table):
    con = sqlite3.connect(path)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def test_fresh_schema_has_model_columns(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    assert "model" in _cols(db._DB_PATH, "extractions")
    assert "model" in _cols(db._DB_PATH, "usage_events")


def test_migration_adds_model_to_pre_w11_db(tmp_path, monkeypatch):
    """Simulate a DB created before W1.1 (no model column) and migrate."""
    _isolate(tmp_path, monkeypatch)
    con = sqlite3.connect(tmp_path / "model_mig.db")
    con.executescript("""
        CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, password_hash TEXT,
            name TEXT, company_name TEXT, is_admin INTEGER, is_active INTEGER,
            created_at TEXT, last_login_at TEXT, google_sub TEXT, avatar_url TEXT);
        CREATE TABLE extractions (id TEXT PRIMARY KEY, project_id TEXT,
            pdf_sha256 TEXT, pdf_size_bytes INTEGER, pdf_page_count INTEGER,
            raw_response TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, elapsed_s REAL, cost_eur REAL,
            extracted_at TEXT);
        CREATE TABLE usage_events (id TEXT PRIMARY KEY, user_id TEXT, kind TEXT,
            input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, cost_eur REAL, created_at TEXT);
        CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT, name TEXT,
            company_name TEXT, tipas TEXT, archetipas TEXT, status TEXT,
            bendras_plotas_m2 REAL, vat_rate REAL, data TEXT,
            created_at TEXT, updated_at TEXT, share_token TEXT,
            share_expires_at TEXT, share_view_count INTEGER,
            share_last_viewed_at TEXT);
    """)
    con.commit()
    con.close()

    db._migrate_schema()
    assert "model" in _cols(db._DB_PATH, "extractions")
    assert "model" in _cols(db._DB_PATH, "usage_events")


def test_migration_is_idempotent(tmp_path, monkeypatch):
    """Re-running init_schema + _migrate_schema on a migrated DB must not fail."""
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db._migrate_schema()
    db._migrate_schema()  # second run — no duplicate-column error
    db.init_schema()      # DDL rerun — IF NOT EXISTS, no-op
    assert "model" in _cols(db._DB_PATH, "extractions")
    assert "model" in _cols(db._DB_PATH, "usage_events")


def test_record_usage_stores_model_and_bills_cache_writes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    resp = {"_meta": {"input_tokens": 100_000, "output_tokens": 5_000,
                      "cache_read_tokens": 50_000, "cache_write_tokens": 20_000,
                      "model": "claude-fable-5"}}
    cost = db.record_usage("u1", resp, "extract-interior")
    # Fable 5, 1h TTL: 100k*10 + 5k*50 + 50k*1 + 20k*20 (per MTok) → USD, ×0.93
    expected_usd = (100_000 * 10 + 5_000 * 50 + 50_000 * 1.0 + 20_000 * 20) / 1e6
    assert cost == pytest.approx(expected_usd * 0.93)
    with db._conn() as c:
        row = c.execute("SELECT model, cost_eur FROM usage_events").fetchone()
    assert row["model"] == "claude-fable-5"
    assert row["cost_eur"] == pytest.approx(round(expected_usd * 0.93, 4))


def test_record_usage_defaults_model_to_opus(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db.record_usage("u1", {"_meta": {"input_tokens": 1000, "output_tokens": 10}})
    with db._conn() as c:
        row = c.execute("SELECT model FROM usage_events").fetchone()
    assert row["model"] == "claude-opus-4-8"

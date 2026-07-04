"""W3 Phase 0 Task 2 — billing columns on users + consumed_trials/billing_usage
tables. Mirrors the isolation idiom in test_db_model_migration.py: monkeypatch
db._DB_PATH to a tmp file (db.py has no init_db() callable — schema init
happens via init_schema() + _migrate_schema(), both idempotent)."""
import sqlite3

import db


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "billing_mig.db")


def _cols(path, table):
    con = sqlite3.connect(path)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def _tables(path):
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_billing_columns_and_tables(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db._migrate_schema()
    ucols = _cols(db._DB_PATH, "users")
    for c in ("plan", "plan_status", "stripe_customer_id",
              "stripe_subscription_id", "current_period_end",
              "company_code", "pvm_code"):
        assert c in ucols, c
    tables = _tables(db._DB_PATH)
    assert "consumed_trials" in tables
    assert "billing_usage" in tables


def test_migration_is_idempotent(tmp_path, monkeypatch):
    """Re-running init_schema + _migrate_schema on a migrated DB must not fail."""
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db._migrate_schema()
    db._migrate_schema()  # second run — no duplicate-column / duplicate-table error
    db.init_schema()      # DDL rerun — IF NOT EXISTS, no-op
    ucols = _cols(db._DB_PATH, "users")
    assert "plan" in ucols
    assert "consumed_trials" in _tables(db._DB_PATH)
    assert "billing_usage" in _tables(db._DB_PATH)


def test_billing_column_defaults(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db._migrate_schema()
    with db._conn() as c:
        c.execute(
            "INSERT INTO users (id, email, password_hash, created_at) "
            "VALUES ('u1', 'a@b.com', 'x', '2026-07-04T00:00:00Z')"
        )
        row = c.execute(
            "SELECT plan, plan_status, stripe_customer_id FROM users WHERE id='u1'"
        ).fetchone()
    assert row["plan"] == "free"
    assert row["plan_status"] == "active"
    assert row["stripe_customer_id"] is None


def test_consumed_trials_unique_company_code(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.init_schema()
    db._migrate_schema()
    with db._conn() as c:
        c.execute(
            "INSERT INTO consumed_trials (company_code, user_id, consumed_at) "
            "VALUES ('LT123', 'u1', '2026-07-04T00:00:00Z')"
        )
    try:
        with db._conn() as c:
            c.execute(
                "INSERT INTO consumed_trials (company_code, user_id, consumed_at) "
                "VALUES ('LT123', 'u2', '2026-07-04T00:00:01Z')"
            )
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised, "company_code must be UNIQUE on consumed_trials"


def test_migration_adds_columns_to_pre_billing_db(tmp_path, monkeypatch):
    """Simulate a DB created before W3 billing (no billing columns) and migrate."""
    _isolate(tmp_path, monkeypatch)
    con = sqlite3.connect(db._DB_PATH)
    con.executescript("""
        CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, password_hash TEXT,
            name TEXT, company_name TEXT, is_admin INTEGER, is_active INTEGER,
            created_at TEXT, last_login_at TEXT, google_sub TEXT, avatar_url TEXT,
            session_version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE extractions (id TEXT PRIMARY KEY, project_id TEXT,
            pdf_sha256 TEXT, pdf_size_bytes INTEGER, pdf_page_count INTEGER,
            raw_response TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, elapsed_s REAL, cost_eur REAL,
            extracted_at TEXT, model TEXT);
        CREATE TABLE usage_events (id TEXT PRIMARY KEY, user_id TEXT, kind TEXT,
            input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, cost_eur REAL, created_at TEXT, model TEXT);
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
    ucols = _cols(db._DB_PATH, "users")
    for c in ("plan", "plan_status", "stripe_customer_id",
              "stripe_subscription_id", "current_period_end",
              "company_code", "pvm_code"):
        assert c in ucols, c
    tables = _tables(db._DB_PATH)
    assert "consumed_trials" in tables
    assert "billing_usage" in tables

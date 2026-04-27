"""SQLite-backed project storage for Sąmatų AI.

Replaces frontend localStorage as the source of truth for projects.
Frontend becomes a write-through cache: on edit, write to localStorage
(instant) AND POST to backend (durable, cross-device).

Schema:
- projects:    id, name, company_name, tipas, archetipas, status, data (JSON), created_at, updated_at
- extractions: id, project_id, pdf_sha256, pdf_size, page_count, raw_response (JSON), tokens, cost, elapsed_s
- corrections: project_id, room_nr, field_path, old_value, new_value, source, occurred_at — audit log
                for future learning-loop / prompt iteration

No auth yet — single-tenant. When auth lands, add user_id to projects.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# DB file lives outside repo root (gitignored). Override via env if needed.
_DB_PATH = Path(os.environ.get("SAMATU_DB_PATH",
                                Path(__file__).resolve().parent / "data" / "samatu.db"))
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@contextmanager
def _conn():
    """Get a SQLite connection (per-call, thread-safe via timeout + lock)."""
    with _DB_LOCK:
        c = sqlite3.connect(_DB_PATH, timeout=10.0, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
        finally:
            c.close()


def init_schema() -> None:
    """Create tables if missing. Safe to call repeatedly (idempotent)."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          TEXT,
                company_name  TEXT,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL,
                last_login_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

            CREATE TABLE IF NOT EXISTS projects (
                id           TEXT PRIMARY KEY,
                user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
                name         TEXT NOT NULL,
                company_name TEXT,
                tipas        TEXT NOT NULL,
                archetipas   TEXT,
                status       TEXT DEFAULT 'ready',
                bendras_plotas_m2 REAL,
                vat_rate     REAL DEFAULT 21,
                data         TEXT NOT NULL,            -- JSON blob
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
            -- idx_projects_user created in _migrate_schema after column exists

            CREATE TABLE IF NOT EXISTS extractions (
                id              TEXT PRIMARY KEY,
                project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                pdf_sha256      TEXT,
                pdf_size_bytes  INTEGER,
                pdf_page_count  INTEGER,
                raw_response    TEXT NOT NULL,         -- JSON blob
                input_tokens    INTEGER,
                output_tokens   INTEGER,
                cache_read_tokens INTEGER,
                elapsed_s       REAL,
                cost_eur        REAL,
                extracted_at    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_extr_project ON extractions(project_id);

            CREATE TABLE IF NOT EXISTS corrections (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                room_nr      TEXT,
                field_path   TEXT NOT NULL,
                old_value    TEXT,                      -- JSON-stringified
                new_value    TEXT,                      -- JSON-stringified
                source       TEXT,
                note         TEXT,
                occurred_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_corr_project ON corrections(project_id);
            CREATE INDEX IF NOT EXISTS idx_corr_field ON corrections(field_path);
            CREATE INDEX IF NOT EXISTS idx_corr_occurred ON corrections(occurred_at);
        """)


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: str | None = None,
                 company_name: str | None = None, is_admin: bool = False) -> dict:
    """Insert new user. Caller is responsible for password hashing."""
    import uuid
    user_id = str(uuid.uuid4())
    now = _now_iso()
    with _conn() as c:
        c.execute("""
            INSERT INTO users (id, email, password_hash, name, company_name,
                               is_admin, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (user_id, email.lower().strip(), password_hash, name, company_name,
              1 if is_admin else 0, now))
    return get_user_by_id(user_id) or {}


def get_user_by_email(email: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user_login(user_id: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_now_iso(), user_id))


def list_users(admin_only: bool = False) -> list[dict]:
    """Admin endpoint — returns user summaries (no password_hash)."""
    with _conn() as c:
        sql = """SELECT id, email, name, company_name, is_admin, is_active,
                        created_at, last_login_at
                   FROM users
               ORDER BY created_at DESC"""
        rows = c.execute(sql).fetchall()
        return [dict(r) for r in rows]


# ── Projects ──────────────────────────────────────────────────────────────────

def list_projects(user_id: str | None = None) -> list[dict]:
    """Return summary list (no full data blob).
    If user_id given — only that user's projects. None = all (admin only)."""
    with _conn() as c:
        if user_id:
            rows = c.execute("""
                SELECT id, user_id, name, company_name, tipas, archetipas, status,
                       bendras_plotas_m2, vat_rate, created_at, updated_at
                  FROM projects
                 WHERE user_id = ?
              ORDER BY updated_at DESC
            """, (user_id,)).fetchall()
        else:
            rows = c.execute("""
                SELECT id, user_id, name, company_name, tipas, archetipas, status,
                       bendras_plotas_m2, vat_rate, created_at, updated_at
                  FROM projects
              ORDER BY updated_at DESC
            """).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: str, user_id: str | None = None) -> dict | None:
    """Get project. If user_id given — enforce ownership (returns None if not match)."""
    with _conn() as c:
        if user_id:
            row = c.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?",
                            (project_id, user_id)).fetchone()
        else:
            row = c.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            data = json.loads(d.pop("data") or "{}")
        except Exception:
            data = {}
        return {**data, **{k: v for k, v in d.items() if v is not None}}


def upsert_project(project_id: str, payload: dict, user_id: str | None = None) -> dict:
    """Insert or full-replace. user_id stored on create; on update, ownership
    is checked first (raises if mismatch)."""
    now = _now_iso()
    name = payload.get("name") or "Naujas projektas"
    tipas = payload.get("tipas") or "interjeras"
    blob = json.dumps(payload, ensure_ascii=False)
    with _conn() as c:
        existing = c.execute(
            "SELECT created_at, user_id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if existing:
            if user_id and existing["user_id"] and existing["user_id"] != user_id:
                raise PermissionError(f"User {user_id} does not own project {project_id}")
            created_at = existing["created_at"]
            owner = existing["user_id"]
        else:
            created_at = payload.get("created_date") or now
            owner = user_id

        c.execute("""
            INSERT INTO projects
                (id, user_id, name, company_name, tipas, archetipas, status,
                 bendras_plotas_m2, vat_rate, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                company_name=excluded.company_name,
                tipas=excluded.tipas,
                archetipas=excluded.archetipas,
                status=excluded.status,
                bendras_plotas_m2=excluded.bendras_plotas_m2,
                vat_rate=excluded.vat_rate,
                data=excluded.data,
                updated_at=excluded.updated_at
        """, (
            project_id, owner, name,
            payload.get("company_name"), tipas, payload.get("archetipas"),
            payload.get("status", "ready"),
            payload.get("bendras_plotas_m2"), payload.get("vat_rate", 21),
            blob, created_at, now,
        ))
    return get_project(project_id) or {}


def delete_project(project_id: str, user_id: str | None = None) -> bool:
    """Delete project. If user_id given — enforce ownership."""
    with _conn() as c:
        if user_id:
            cursor = c.execute("DELETE FROM projects WHERE id = ? AND user_id = ?",
                               (project_id, user_id))
        else:
            cursor = c.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0


# ── Extractions ───────────────────────────────────────────────────────────────

def save_extraction(project_id: str, extraction_id: str, response: dict,
                     pdf_sha256: str = "", pdf_size: int = 0,
                     page_count: int = 0) -> None:
    """Archive a Vision extraction response for cost analysis + audit."""
    meta = response.get("_meta") or {}
    in_tok = meta.get("input_tokens") or 0
    out_tok = meta.get("output_tokens") or 0
    cache_tok = meta.get("cache_read_tokens") or 0
    cost_usd = (in_tok * 5e-6) + (out_tok * 25e-6) - (cache_tok * 4.5e-6)
    cost_eur = cost_usd * 0.93  # rough USD→EUR
    with _conn() as c:
        c.execute("""
            INSERT INTO extractions
                (id, project_id, pdf_sha256, pdf_size_bytes, pdf_page_count,
                 raw_response, input_tokens, output_tokens, cache_read_tokens,
                 elapsed_s, cost_eur, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            extraction_id, project_id, pdf_sha256, pdf_size, page_count,
            json.dumps(response, ensure_ascii=False),
            in_tok, out_tok, cache_tok,
            meta.get("elapsed_s") or response.get("_elapsed_s"),
            round(cost_eur, 4),
            _now_iso(),
        ))


def list_extractions(project_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT id, pdf_sha256, pdf_size_bytes, pdf_page_count,
                   input_tokens, output_tokens, cache_read_tokens,
                   elapsed_s, cost_eur, extracted_at
              FROM extractions
             WHERE project_id = ?
          ORDER BY extracted_at DESC
        """, (project_id,)).fetchall()
        return [dict(r) for r in rows]


# ── Corrections (audit log for future learning-loop) ──────────────────────────

def log_correction(project_id: str, field_path: str,
                    old_value: Any, new_value: Any,
                    source: str = "inline_edit",
                    room_nr: str | None = None,
                    note: str | None = None) -> None:
    """Track every user-driven change for later prompt iteration."""
    with _conn() as c:
        c.execute("""
            INSERT INTO corrections
                (project_id, room_nr, field_path, old_value, new_value,
                 source, note, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, room_nr, field_path,
            json.dumps(old_value, ensure_ascii=False) if old_value is not None else None,
            json.dumps(new_value, ensure_ascii=False) if new_value is not None else None,
            source, note, _now_iso(),
        ))


def list_corrections(project_id: str | None = None, limit: int = 500) -> list[dict]:
    """All corrections for a project, or globally if project_id is None."""
    with _conn() as c:
        if project_id:
            rows = c.execute("""
                SELECT * FROM corrections
                 WHERE project_id = ?
              ORDER BY occurred_at DESC LIMIT ?
            """, (project_id, limit)).fetchall()
        else:
            rows = c.execute("""
                SELECT * FROM corrections
              ORDER BY occurred_at DESC LIMIT ?
            """, (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("old_value", "new_value"):
                if d.get(k):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        pass
            out.append(d)
        return out


def corrections_summary() -> list[dict]:
    """Aggregated correction patterns — how often each field is overridden.
    Used by admin dashboard / manual prompt iteration to identify systemic
    Vision biases (eg. 'users override drabuzine_painted=false 70% of time')."""
    with _conn() as c:
        rows = c.execute("""
            SELECT field_path,
                   COUNT(*) as count,
                   COUNT(DISTINCT project_id) as projects,
                   MAX(occurred_at) as last_seen
              FROM corrections
          GROUP BY field_path
          ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]


def _migrate_schema() -> None:
    """Idempotent column additions for existing DBs created before auth.
    SQLite ALTER TABLE only supports ADD COLUMN — keep migrations append-only."""
    with _conn() as c:
        # Check if projects.user_id exists; add if not
        cols = {row["name"] for row in c.execute("PRAGMA table_info(projects)").fetchall()}
        if cols and "user_id" not in cols:
            c.execute("ALTER TABLE projects ADD COLUMN user_id TEXT")
            c.execute("CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)")


# Initialize schema on module import
init_schema()
_migrate_schema()

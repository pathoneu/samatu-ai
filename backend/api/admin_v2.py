"""Admin Dashboard v2 — the operational cockpit (owner-authorized).

A read-mostly router that turns the existing DB into an ops dashboard:
analytics time series, an accurate cost monitor ("don't go bankrupt" screen),
paginated/searchable user management with disable/enable, system health, and
CSV export. It ADDS to — never replaces — the four inline /api/admin/* endpoints
in main.py.

Two invariants baked into every money figure and query:

  1. COST = usage_events.cost_eur. That table is the COMPLETE per-call meter
     (incl. sub-readers after the 2026-07-04 fix). extractions.cost_eur is
     PASS-1-ONLY and is never summed here — a test seeds a divergent extractions
     value and asserts we ignore it.

  2. Every endpoint calls auth.require_admin(request): 401 for anon, 403 for a
     logged-in non-admin. No new auth surface — same gate as the inline admin
     endpoints.

ZERO Anthropic calls — pure aggregation over local SQLite.
"""
from __future__ import annotations

import csv
import io
import os

from fastapi import APIRouter, Request
from fastapi.responses import Response

import auth as _auth
import db
from extractor.spreadsheet_safety import sanitize_spreadsheet_cell

router = APIRouter(prefix="/api/admin/v2", tags=["admin"])


def _cost_alert_threshold_eur() -> float:
    """Per-user daily spend that trips a cost alert. Env-overridable; €5 default.
    A malformed env value falls back to the default rather than 500-ing."""
    try:
        return float(os.environ.get("SAMATU_ADMIN_COST_ALERT_EUR", "5.0"))
    except (TypeError, ValueError):
        return 5.0


def _delta(cur: float, prior: float) -> dict:
    """Absolute + percent change of `cur` vs `prior`. pct is None when prior is 0
    (avoid divide-by-zero / meaningless ∞%)."""
    abs_change = round(float(cur) - float(prior), 4)
    pct = round((cur - prior) / prior * 100, 1) if prior else None
    return {"current": cur, "prior": prior, "abs": abs_change, "pct": pct}


# ── 1. Analytics ─────────────────────────────────────────────────────────────

@router.get("/analytics")
def analytics(request: Request, days: int = 30) -> dict:
    """Daily time series over the window + totals + deltas vs the prior window.

    series[]: {date, signups, projects, extractions, cost_eur, revenue_eur}
    cost_eur = SUM(usage_events.cost_eur) per day (accurate meter);
    revenue_eur = SUM(invoices.total_eur) per day."""
    _auth.require_admin(request)
    series = db.admin_daily_series(days)
    totals = db.admin_window_totals(days)
    prior = db.admin_prior_window_totals(days)
    deltas = {k: _delta(totals[k], prior[k]) for k in totals}
    return {"days": days, "series": series, "totals": totals, "deltas": deltas}


# ── 2. Cost monitor ──────────────────────────────────────────────────────────

@router.get("/cost-monitor")
def cost_monitor(request: Request, days: int = 30) -> dict:
    """Accurate spend view — the "don't go bankrupt" screen. Everything sourced
    from usage_events.cost_eur."""
    _auth.require_admin(request)
    threshold = _cost_alert_threshold_eur()
    return {
        "days": days,
        "total_cost_eur": db.admin_cost_total_eur(days=days),
        "today_cost_eur": db.admin_cost_total_eur(today_only=True),
        "avg_cost_per_extraction_eur": db.admin_avg_cost_per_extraction_eur(days),
        "top_users": db.admin_top_users_by_spend(days=days, limit=10),
        "by_model": db.admin_cost_by_model(days),
        "alert_threshold_eur": threshold,
        "alerts": db.admin_users_over_today_threshold(threshold),
    }


# ── 3. User management ───────────────────────────────────────────────────────

@router.get("/users")
def list_users(request: Request, search: str = "", page: int = 1,
               limit: int = 25) -> dict:
    """Paginated + searchable user directory. Each row carries project_count and
    total_spend_eur (SUM usage_events). {rows, total, page, limit}."""
    _auth.require_admin(request)
    return db.admin_list_users_paginated(
        search=search.strip() or None, page=page, limit=limit)


def _toggle_active(request: Request, user_id: str, active: bool) -> dict:
    """Shared disable/enable body with the guardrails. On DISABLE only:
      - an admin may not disable THEMSELVES (would lock themselves out) → 400
      - an admin may not disable ANOTHER admin → 400
    Enabling is always allowed (re-activating an admin is safe)."""
    from fastapi import HTTPException
    caller = _auth.require_admin(request)
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Vartotojas nerastas")
    if not active:
        if target["id"] == caller["id"]:
            raise HTTPException(
                status_code=400, detail="Negalima išjungti savo paskyros")
        if target.get("is_admin"):
            raise HTTPException(
                status_code=400, detail="Negalima išjungti kito administratoriaus")
    db.set_user_active(user_id, active)
    # Audit trail: record WHO disabled/enabled WHOM, and WHEN. Written only after
    # the mutation succeeds (a guardrail-rejected call raises above and logs
    # nothing). target["email"] is preserved in `detail` so the row stays
    # readable even if that user is later deleted.
    db.record_admin_action(
        caller["id"],
        "user.disable" if not active else "user.enable",
        target_id=user_id,
        detail=target.get("email"),
    )
    return {"status": "ok", "user_id": user_id, "is_active": 1 if active else 0}


@router.post("/users/{user_id}/disable")
def disable_user(request: Request, user_id: str) -> dict:
    return _toggle_active(request, user_id, active=False)


@router.post("/users/{user_id}/enable")
def enable_user(request: Request, user_id: str) -> dict:
    return _toggle_active(request, user_id, active=True)


# ── 3b. Admin audit log (read-only) ──────────────────────────────────────────

@router.get("/audit-log")
def audit_log(request: Request, limit: int = 100) -> dict:
    """Read-only trail of state-changing admin actions, newest first. Each row:
    {id, actor_user_id, actor_email, action, target_user_id, target_email,
    detail, created_at}. {rows}."""
    _auth.require_admin(request)
    return {"rows": db.list_admin_actions(limit=limit)}


# ── 4. System health ─────────────────────────────────────────────────────────

_ERROR_LOG_NOTE = (
    "Frontend errors are sent to /api/log-error, which writes to the app logger "
    "(StreamHandler → stdout only — no persisted file). There is no on-disk error "
    "log to tail; wire a FileHandler or Sentry to populate this."
)


@router.get("/system-health")
def system_health(request: Request) -> dict:
    """Extraction volume signal + whole-table counts + DB size + recent activity
    + (empty) error-log tail. Defensive: never 500 on missing data."""
    _auth.require_admin(request)
    try:
        events_by_kind = db.admin_events_by_kind(days=30)
    except Exception:
        events_by_kind = []
    try:
        totals = db.admin_health_totals()
    except Exception:
        totals = {}
    try:
        recent = db.admin_recent_activity()
    except Exception:
        recent = {}
    return {
        "totals": totals,
        "events_by_kind": events_by_kind,
        "db_size_bytes": db.admin_db_size_bytes(),
        "recent_activity": recent,
        # No persisted error log in this app (see note) → always [].
        "error_log_tail": [],
        "note": _ERROR_LOG_NOTE,
    }


# ── 5. CSV export ────────────────────────────────────────────────────────────

def _csv_response(header: list[str], rows: list[list], filename: str) -> Response:
    """Serialize rows to a CSV download. Every cell passes through
    sanitize_spreadsheet_cell (F6/P3 CSV-injection class) so a user/AI-supplied
    string starting with = + - @ can't execute as a formula in the recipient's
    spreadsheet."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([sanitize_spreadsheet_cell(h) for h in header])
    for row in rows:
        writer.writerow([sanitize_spreadsheet_cell(cell) for cell in row])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_USERS_CSV_COLUMNS = [
    "id", "email", "name", "company_name", "company_code", "plan",
    "plan_status", "is_admin", "is_active", "created_at", "last_login_at",
    "project_count", "total_spend_eur",
]


@router.get("/export/users.csv")
def export_users_csv(request: Request, search: str = "") -> Response:
    """All users (respecting an optional search) as a sanitized CSV download."""
    _auth.require_admin(request)
    # limit high enough to export everything in one file (pagination is a UI
    # concern; the export is the full set).
    data = db.admin_list_users_paginated(
        search=search.strip() or None, page=1, limit=100000)
    rows = [[u.get(col) for col in _USERS_CSV_COLUMNS] for u in data["rows"]]
    return _csv_response(_USERS_CSV_COLUMNS, rows, "pathon-users.csv")


_COST_CSV_COLUMNS = [
    "date", "signups", "projects", "extractions", "cost_eur", "revenue_eur",
]


@router.get("/export/cost.csv")
def export_cost_csv(request: Request, days: int = 30) -> Response:
    """Per-day analytics rows (the cost time series) as a sanitized CSV."""
    _auth.require_admin(request)
    series = db.admin_daily_series(days)
    rows = [[r.get(col) for col in _COST_CSV_COLUMNS] for r in series]
    return _csv_response(_COST_CSV_COLUMNS, rows, "pathon-cost.csv")

"""W3 Phase 6 Task 14 (DB layer) — invoices table + helpers.

Covers the migration (invoices table exists), sequential numbering, insert, and
the OWNER-SCOPED get_invoice (returns None when not owned — the IDOR-safe
accessor the endpoint relies on). Isolation idiom mirrors test_billing_migration:
monkeypatch db._DB_PATH + init_schema() + _migrate_schema().
"""
import sqlite3

import db


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "invoices.db")
    db.init_schema()
    db._migrate_schema()


def _tables(path):
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_invoices_table_created(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert "invoices" in _tables(db._DB_PATH)
    cols = {r[1] for r in sqlite3.connect(db._DB_PATH).execute(
        "PRAGMA table_info(invoices)")}
    for c in ("id", "user_id", "number", "vat_mode", "total_eur", "pdf_path",
              "created_at"):
        assert c in cols, c


def test_next_invoice_number_is_monotonic(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    n1 = db.next_invoice_number()
    assert n1.startswith("PATHON-")
    db.insert_invoice(id="i1", user_id="u1", number=n1, vat_mode="reverse_charge",
                      total_eur=49.0, pdf_path="invoices/i1.pdf")
    n2 = db.next_invoice_number()
    assert n2 != n1
    # seq derived from count → strictly increasing zero-padded suffix
    assert n1.split("-")[-1] < n2.split("-")[-1]


def test_insert_and_get_invoice_owned(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.insert_invoice(id="inv1", user_id="userA", number="PATHON-2026-000001",
                      vat_mode="reverse_charge", total_eur=49.0,
                      pdf_path="invoices/inv1.pdf")
    got = db.get_invoice("inv1", user_id="userA")
    assert got is not None
    assert got["id"] == "inv1"
    assert got["user_id"] == "userA"
    assert got["pdf_path"] == "invoices/inv1.pdf"
    assert got["total_eur"] == 49.0


def test_get_invoice_returns_none_when_not_owned(tmp_path, monkeypatch):
    """The IDOR keystone: user B asking for user A's invoice → None (endpoint
    turns that into 404, no existence leak)."""
    _isolate(tmp_path, monkeypatch)
    db.insert_invoice(id="inv1", user_id="userA", number="PATHON-2026-000001",
                      vat_mode="reverse_charge", total_eur=49.0,
                      pdf_path="invoices/inv1.pdf")
    assert db.get_invoice("inv1", user_id="userB") is None
    assert db.get_invoice("does-not-exist", user_id="userA") is None


def test_list_invoices_owner_scoped(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.insert_invoice(id="a1", user_id="userA", number="PATHON-2026-000001",
                      vat_mode="standard", total_eur=59.29,
                      pdf_path="invoices/a1.pdf")
    db.insert_invoice(id="a2", user_id="userA", number="PATHON-2026-000002",
                      vat_mode="reverse_charge", total_eur=12.0,
                      pdf_path="invoices/a2.pdf")
    db.insert_invoice(id="b1", user_id="userB", number="PATHON-2026-000003",
                      vat_mode="reverse_charge", total_eur=49.0,
                      pdf_path="invoices/b1.pdf")
    a = db.list_invoices("userA")
    assert {r["id"] for r in a} == {"a1", "a2"}  # never b1
    b = db.list_invoices("userB")
    assert {r["id"] for r in b} == {"b1"}
    assert db.list_invoices("nobody") == []

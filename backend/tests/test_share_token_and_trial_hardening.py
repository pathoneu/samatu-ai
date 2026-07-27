"""2026-07-27 audit findings 9 + 11 — two guards that failed OPEN.

  9. db.get_project_by_share_token() swallowed an unparseable share_expires_at
     and treated the link as NON-expiring — a corrupt/hand-edited date turned a
     time-boxed share link into a permanent one.
 11. billing.trial.normalize_company_code() let '0123456789' claim a second free
     trial after '123456789' had consumed it, and accepted non-ASCII digits
     (str.isdigit() is True for fullwidth '１２３…'), one extra trial per script.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
from billing import trial  # noqa: E402


def _isolate(tmp_path, monkeypatch, name="hardening.db"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    db.init_schema()
    db._migrate_schema()


# ── 9. share-token expiry fails CLOSED ──────────────────────────────────────

def _project_with_expiry(expires):
    db.upsert_project("shared-1", {"name": "S", "tipas": "interjeras"}, user_id=None)
    with db._conn() as c:
        c.execute("UPDATE projects SET share_token = ?, share_expires_at = ? "
                  "WHERE id = ?", ("tok-abc", expires, "shared-1"))


def test_malformed_expiry_is_treated_as_expired(tmp_path, monkeypatch, caplog):
    _isolate(tmp_path, monkeypatch)
    _project_with_expiry("ne-data-visai")
    import logging
    with caplog.at_level(logging.WARNING, logger="pathon.db"):
        assert db.get_project_by_share_token("tok-abc") is None
    assert any("unparseable" in r.getMessage() for r in caplog.records), caplog.text


def test_valid_future_expiry_still_works(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "share_ok.db")
    _project_with_expiry("2099-01-01T00:00:00Z")
    assert db.get_project_by_share_token("tok-abc") is not None


def test_past_expiry_still_rejected(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "share_old.db")
    _project_with_expiry("2020-01-01T00:00:00Z")
    assert db.get_project_by_share_token("tok-abc") is None


def test_no_expiry_still_works(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "share_none.db")
    _project_with_expiry(None)
    assert db.get_project_by_share_token("tok-abc") is not None


# ── 11. company-code normalization ──────────────────────────────────────────

def test_leading_zeros_do_not_buy_a_second_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "trial_zeros.db")
    assert trial.consume_trial("123456789", user_id="u1") is True
    assert trial.trial_available("0123456789") is False      # was True → free trial
    assert trial.trial_available("000123456789") is False
    assert trial.consume_trial("0123456789", user_id="u2") is False


def test_normalize_collapses_leading_zeros():
    assert trial.normalize_company_code("0123456789") == "123456789"
    assert trial.normalize_company_code(" 00 302536741 ") == "302536741"


def test_non_ascii_digits_are_rejected():
    for bad in ("１２３４５６７８９",          # fullwidth
                "١٢٣٤٥٦٧٨٩",              # Arabic-Indic
                "1234５6789"):             # mixed
        with pytest.raises(ValueError):
            trial.normalize_company_code(bad)


def test_all_zero_code_is_rejected():
    with pytest.raises(ValueError):
        trial.normalize_company_code("000000000")


def test_plain_codes_unchanged():
    assert trial.normalize_company_code("302536741") == "302536741"
    assert trial.normalize_company_code("30 25 36 741") == "302536741"

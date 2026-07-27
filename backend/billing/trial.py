"""Free-trial anti-abuse: one 1-project trial per LT company code (įmonės kodas).

The Free tier is a ONE-TIME trial gated by a verified company identity that
PERSISTS across account deletion (the `consumed_trials` table is keyed by the
normalized company code, independent of the users row — deleting/recreating an
account with the same company does NOT reset the trial). See docs/pricing.md §3a.

Paid plans + purchased one-off credits are NOT trial-gated — this only bounds
the free tier. All DB access goes through db helpers so the SQL/connection style
matches the rest of the billing layer (db.py owns the schema + _conn).
"""
from __future__ import annotations

import re

import db

# LT įmonės kodas is numeric, typically 9 digits. Accept 5–11 to be lenient
# across juridinių/fizinių asmenų code variants without letting through obvious
# garbage.
_MIN_LEN = 5
_MAX_LEN = 11

# str.isdigit() is True for NON-ASCII digits ('１２３４５６７８９' fullwidth, '١٢٣'
# Arabic-Indic, superscripts…), so the old check let through codes that are a
# different byte string but the same company to a human — a second free trial per
# script variant. Require plain ASCII 0-9 (2026-07-27 audit, finding 11).
_ASCII_DIGITS_RE = re.compile(r"^[0-9]+$")


def normalize_company_code(raw) -> str:
    """Strip whitespace, keep ASCII digits, drop leading zeros, validate a
    plausible LT company-code length.

    Leading zeros are stripped because '0123456789' and '123456789' are the same
    company to the registry but were two different rows in `consumed_trials` —
    i.e. a free extra trial for anyone who padded their code (2026-07-27 audit).

    Raises ValueError on empty / non-numeric / implausible length so callers
    (the capture endpoint) can reject a bad code with a 400 rather than storing
    junk that would silently never match the trial ledger."""
    if raw is None:
        raise ValueError("Įmonės kodas privalomas")
    digits = "".join(ch for ch in str(raw) if not ch.isspace())
    if not digits:
        raise ValueError("Įmonės kodas privalomas")
    if not _ASCII_DIGITS_RE.match(digits):
        raise ValueError("Įmonės kodas turi būti sudarytas tik iš skaitmenų")
    digits = digits.lstrip("0")
    if not (_MIN_LEN <= len(digits) <= _MAX_LEN):
        raise ValueError("Neteisingas įmonės kodo ilgis")
    return digits


def trial_available(company_code) -> bool:
    """True iff this company has NOT yet consumed its free trial. An empty /
    invalid code is treated as unavailable (False) — you cannot claim a trial
    without a valid company identity."""
    try:
        code = normalize_company_code(company_code)
    except ValueError:
        return False
    return not db.trial_consumed(code)


def consume_trial(company_code, user_id: str | None) -> bool:
    """Mark this company's trial consumed (UNIQUE insert into consumed_trials).
    Returns True on a fresh consume, False if it was already consumed (or the
    code is invalid). Idempotent-safe: a second call for the same company is a
    no-op returning False."""
    try:
        code = normalize_company_code(company_code)
    except ValueError:
        return False
    return db.consume_trial(code, user_id)

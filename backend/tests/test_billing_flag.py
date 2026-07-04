import os
from billing.flag import billing_enabled

def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    assert billing_enabled() is False

def test_flag_on_only_for_exactly_1(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    assert billing_enabled() is True
    for v in ("0", "true", "yes", "", "2"):
        monkeypatch.setenv("BILLING_ENABLED", v)
        assert billing_enabled() is False

"""Feature flags infrastructure (Sprint 0 Task 1).

Tests that flags default to False and read from environment variables
respecting truthy/falsy semantics.
"""
import os
import pytest
from extractor.feature_flags import get_flags


def test_flags_default_when_unset():
    """Flags default per definition. polygon_prepass + per_room_ceiling are
    True after activation; rest are False."""
    # Clear env
    for k in ["ENABLE_PER_ROOM_CEILING", "ENABLE_PAINT_CLASS_INFERENCE",
              "ENABLE_VERIFY_PASS", "ENABLE_POLYGON_PREPASS",
              "ENABLE_SONNET_PASS1", "ENABLE_GRID_OVERLAY", "ENABLE_PROXY_GT"]:
        os.environ.pop(k, None)
    flags = get_flags()
    assert flags["per_room_ceiling"] is True   # 2026-05-06 default-on (>3m extraction)
    assert flags["paint_class_inference"] is False
    assert flags["verify_pass"] is False
    assert flags["polygon_prepass"] is True   # Sprint 4 Block B default-on
    assert flags["sonnet_pass1"] is False
    assert flags["grid_overlay"] is False
    assert flags["proxy_gt"] is False


def test_polygon_prepass_can_be_disabled_via_env(monkeypatch):
    """polygon_prepass defaults True but ENABLE_POLYGON_PREPASS=0 turns it off
    (one-line revert per Sprint 4 plan)."""
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "0")
    assert get_flags()["polygon_prepass"] is False
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "false")
    assert get_flags()["polygon_prepass"] is False


def test_flags_read_truthy_strings(monkeypatch):
    """Strings like '1', 'true', 'yes', 'on' should be read as True."""
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "true")
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "yes")
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "on")
    flags = get_flags()
    assert flags["per_room_ceiling"] is True
    assert flags["paint_class_inference"] is True
    assert flags["verify_pass"] is True
    assert flags["polygon_prepass"] is True


def test_flags_falsy_strings(monkeypatch):
    """Strings like '0', 'false', 'no', '', etc. should be read as False."""
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "0")
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "false")
    monkeypatch.setenv("ENABLE_SONNET_PASS1", "no")
    monkeypatch.setenv("ENABLE_GRID_OVERLAY", "")
    flags = get_flags()
    assert flags["per_room_ceiling"] is False
    assert flags["verify_pass"] is False
    assert flags["sonnet_pass1"] is False
    assert flags["grid_overlay"] is False


def test_flags_case_insensitive(monkeypatch):
    """Truthy strings should be case-insensitive."""
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "TRUE")
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "Yes")
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "ON")
    flags = get_flags()
    assert flags["per_room_ceiling"] is True
    assert flags["paint_class_inference"] is True
    assert flags["verify_pass"] is True


def test_flags_whitespace_stripped(monkeypatch):
    """Leading/trailing whitespace should be stripped before checking."""
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "  1  ")
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "  true  ")
    flags = get_flags()
    assert flags["per_room_ceiling"] is True
    assert flags["paint_class_inference"] is True

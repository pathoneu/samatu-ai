"""Unit tests for backend.extractor.roof.geometry."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from extractor.roof import geometry  # noqa: E402


def test_module_loads():
    """Sentinel — confirms module is importable."""
    assert geometry.__doc__ is not None

"""Shared pytest config for detector_bench tests.

Adds the repo root to sys.path so `from detector_bench.core.types import ...`
works without installing the package.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

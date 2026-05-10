"""Top-level conftest.

Why: tests import via `from main import app`, `from extractor.X import ...`,
`from api.Y import ...` — i.e. with the backend directory on sys.path.
When pytest is invoked with a specific test file (rather than discovering
from cwd), it doesn't add cwd to sys.path and the imports fail. This
conftest guarantees the backend directory is always on sys.path.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

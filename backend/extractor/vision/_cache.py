"""File-based JSON cache for Vision calls.

Cache key = sha256(image_bytes ‖ prompt_text ‖ model_id ‖ extra_params).
Files live in ``$SAMATU_VISION_CACHE`` (default: ``.vision_cache/``).

Lookups are O(1) on disk. Reads/writes are atomic (write to ``.tmp`` then
rename) so concurrent runs don't half-write a JSON.

Intended for iteration on prompts where the same image + prompt + model
should not pay for a Vision call twice. Add a ``--no-cache`` flag wherever
this matters (e.g. determinism tests should bypass the cache entirely).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

DEFAULT_CACHE_DIR = Path(
    os.environ.get("SAMATU_VISION_CACHE")
    or (Path(__file__).resolve().parents[3] / ".vision_cache")
)


def cache_key(*parts: bytes | str) -> str:
    """Stable hex digest of an ordered byte/string tuple."""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, str):
            p = p.encode("utf-8")
        h.update(p)
        h.update(b"\x1f")  # ASCII unit separator between fields
    return h.hexdigest()


@dataclass
class VisionCache:
    root: Path = DEFAULT_CACHE_DIR
    namespace: str = "default"

    def __post_init__(self) -> None:
        (self.root / self.namespace).mkdir(parents=True, exist_ok=True)

    # ── core API ──────────────────────────────────────────────────────────────
    def path(self, key: str) -> Path:
        return self.root / self.namespace / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self.path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Corrupt cache file — treat as a miss
            return None

    def put(self, key: str, value: dict[str, Any]) -> Path:
        p = self.path(key)
        # Atomic write
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False,
            dir=p.parent, prefix=p.name, suffix=".tmp",
        ) as tmp:
            json.dump(value, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)
        tmp_path.replace(p)
        return p

    def keys(self) -> Iterable[str]:
        return (f.stem for f in (self.root / self.namespace).glob("*.json"))

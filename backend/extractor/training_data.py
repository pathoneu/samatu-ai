"""Append-only crop+label store. Every user accept/reject from the
review panel calls record_label() with the cropped image. Six-digit
sequence numbers prevent filename collisions; a JSONL log next to the
class folders holds metadata.

The format is intentionally framework-agnostic — when there are 1k+
labels per class, a YOLO data-prep script reads `labels.jsonl` plus
the crops to build a training corpus. Until then the cost of storing
each label is one PNG + one log line.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1].parent / "data" / "symbol_training"

Decision = Literal["accept", "reject"]

# The class name becomes a directory under ROOT, and it comes from the caller
# (POST /api/cv/record-decision). Audit 2026-09-29: "../x" or an absolute
# name used to write outside ROOT. A strict slug only; the API enforces the
# same pattern (422) before this is ever reached.
KLASS_PATTERN = r"^[a-z0-9_-]{1,40}$"
_KLASS_RE = re.compile(KLASS_PATTERN)


def record_label(
    klass: str,
    decision: Decision,
    crop: np.ndarray,
    meta: dict,
) -> Path:
    if not isinstance(klass, str) or not _KLASS_RE.fullmatch(klass):
        raise ValueError(f"invalid class name: {klass!r}")
    cls_dir = ROOT / klass
    if not cls_dir.resolve().is_relative_to(Path(ROOT).resolve()):
        raise ValueError(f"class directory escapes the training root: {klass!r}")
    cls_dir.mkdir(parents=True, exist_ok=True)
    seq = sum(1 for _ in cls_dir.glob("*.png")) + 1
    img_name = f"{seq:06d}_{decision}_{int(time.time())}.png"
    img_path = cls_dir / img_name
    cv2.imwrite(str(img_path), crop)

    log = ROOT / "labels.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "klass": klass,
            "decision": decision,
            "image": str(img_path.relative_to(ROOT)),
            "meta": meta,
            "ts": int(time.time()),
        }, ensure_ascii=False) + "\n")
    return img_path

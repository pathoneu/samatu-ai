"""Append-only crop+label store. Every user accept/reject from the
review panel calls record_label() with the cropped image. Six-digit
sequence numbers prevent filename collisions; a JSONL log next to the
class folders holds metadata.

The format is intentionally framework-agnostic — when there are 1k+
labels per class, a YOLO data-prep script reads `labels.jsonl` plus
the crops to build a training corpus. Until then the cost of storing
each label is one PNG + one log line.

Where (v3 W7-A M8, 2026-10-18): under the data directory, so it survives a
deploy and is covered by the same rules as every other store —
`SAMATU_DATA_DIR/symbol_training` when that is set, else the legacy in-repo
`data/symbol_training` (dev, tests). A label that names its project is kept
under `<root>/<project_id>/` (its own `labels.jsonl` and class folders), so
deleting the project deletes its crops (`purge_project`). Crops written before
this layout sit at the root; `purge_project` also removes the ones whose log
line names the project, and rewrites the root log without them.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

import storage as _storage

ROOT = _storage.data_path(
    "symbol_training", Path(__file__).resolve().parents[1].parent / "data" / "symbol_training")

Decision = Literal["accept", "reject"]

# The class name becomes a directory under ROOT, and it comes from the caller
# (POST /api/cv/record-decision). Audit 2026-09-29: "../x" or an absolute
# name used to write outside ROOT. A strict slug only; the API enforces the
# same pattern (422) before this is ever reached.
KLASS_PATTERN = r"^[a-z0-9_-]{1,40}$"
_KLASS_RE = re.compile(KLASS_PATTERN)
# Project ids that may name a directory (the rule every id-keyed store uses).
_PROJECT_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
# record_label appends and purge_project rewrites the same log files.
_LOCK = threading.Lock()


def _project_dir(project_id) -> Path | None:
    if isinstance(project_id, str) and _PROJECT_RE.fullmatch(project_id):
        return Path(ROOT) / project_id
    return None


def record_label(
    klass: str,
    decision: Decision,
    crop: np.ndarray,
    meta: dict,
) -> Path:
    if not isinstance(klass, str) or not _KLASS_RE.fullmatch(klass):
        raise ValueError(f"invalid class name: {klass!r}")
    base = _project_dir((meta or {}).get("project_id")) or Path(ROOT)
    cls_dir = base / klass
    if not cls_dir.resolve().is_relative_to(Path(ROOT).resolve()):
        raise ValueError(f"class directory escapes the training root: {klass!r}")
    with _LOCK:
        cls_dir.mkdir(parents=True, exist_ok=True)
        seq = sum(1 for _ in cls_dir.glob("*.png")) + 1
        img_name = f"{seq:06d}_{decision}_{int(time.time())}.png"
        img_path = cls_dir / img_name
        cv2.imwrite(str(img_path), crop)

        log = base / "labels.jsonl"
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


def purge_project(project_id: str) -> int:
    """Delete every crop recorded for `project_id`: its own folder, and the
    legacy root-level crops whose log line names it (the root log is rewritten
    without them). Returns how many crops went. Safe to repeat."""
    root = Path(ROOT)
    removed = 0
    pdir = _project_dir(project_id)
    with _LOCK:
        if pdir is not None and pdir.is_dir() and pdir.resolve().is_relative_to(root.resolve()):
            removed += sum(1 for _ in pdir.rglob("*.png"))
            shutil.rmtree(pdir)
        log = root / "labels.jsonl"
        if not log.is_file():
            return removed
        keep: list[str] = []
        changed = False
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                keep.append(line)
                continue
            if (rec.get("meta") or {}).get("project_id") != project_id:
                keep.append(line)
                continue
            changed = True
            img = (root / str(rec.get("image") or "")).resolve()
            if img.is_relative_to(root.resolve()) and img.is_file():
                img.unlink()
                removed += 1
        if changed:
            tmp = log.with_suffix(".jsonl.tmp")
            tmp.write_text("".join(f"{ln}\n" for ln in keep), encoding="utf-8")
            tmp.replace(log)
    return removed

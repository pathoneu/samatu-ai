"""Recompute per-room + santrauka for each cached ai_extract.json so
new calculator fields (e.g., silikonavimas_m added 2026-06-05) flow
through. Zero Vision cost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka  # noqa: E402


def main() -> int:
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    for entry in reg.get("projects", []):
        slug = entry["slug"]
        path = REPO / "ground_truth" / slug / "ai_extract.json"
        if not path.exists():
            print(f"  {slug}: no ai_extract.json — skip")
            continue
        ex = json.loads(path.read_text(encoding="utf-8"))
        ex = _recompute_per_room_via_python(ex, None)
        ex = _recompute_santrauka(ex)
        path.write_text(json.dumps(ex, ensure_ascii=False, indent=2), encoding="utf-8")
        sil_total = (ex.get("santrauka") or {}).get("silikonavimas_m_total", 0)
        print(f"  {slug}: silikonavimas_m_total = {sil_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

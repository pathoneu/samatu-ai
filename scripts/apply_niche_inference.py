"""Apply niche_inference to cached ai_extract.json files + recompute santrauka."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from extractor.niche_inference import infer_missing_niches  # noqa: E402
from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka  # noqa: E402


def main() -> int:
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    for entry in reg.get("projects", []):
        slug = entry["slug"]
        path = REPO / "ground_truth" / slug / "ai_extract.json"
        if not path.exists():
            print(f"  {slug}: no extract — skip")
            continue
        ex = json.loads(path.read_text(encoding="utf-8"))
        n = infer_missing_niches(ex.get("patalpos") or [])
        ex = _recompute_per_room_via_python(ex, None)
        ex = _recompute_santrauka(ex)
        path.write_text(json.dumps(ex, ensure_ascii=False, indent=2), encoding="utf-8")
        led_total = (ex.get("santrauka") or {}).get("nisu_metrai_total", 0)
        print(f"  {slug}: inferred {n} rooms, LED total = {led_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

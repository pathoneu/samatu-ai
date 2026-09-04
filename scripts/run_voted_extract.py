"""Run a fresh VOTED extraction for one registry slug and save it to a safe
output path (NEVER overwrites the cached benchmark extract).

Usage: venv/bin/python scripts/run_voted_extract.py <slug> <out_json>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

import yaml  # noqa: E402


def main() -> int:
    slug, out_path = sys.argv[1], Path(sys.argv[2])
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text())
    entry = next(p for p in reg["projects"] if p["slug"] == slug)
    pdf = REPO / entry["project_pdf"]
    if slug == "objektas_a" and not pdf.exists():
        pdf = REPO / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    print(f"[{slug}] PDF: {pdf.name} ({pdf.stat().st_size/1e6:.1f} MB)", flush=True)

    os.environ["ENABLE_EXTRACTION_VOTING"] = "1"
    os.environ["VOTING_N"] = "3"
    from extractor.vision_call import extract_interior

    t0 = time.time()
    result = extract_interior(pdf.read_bytes(), rules_override=None)
    dt = time.time() - t0
    if result.get("status") == "error":
        print(f"[{slug}] ✗ ERROR: {result.get('_error')}", flush=True)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rooms = result.get("patalpos") or []
    npw = sum(int(r.get("n_partition_walls") or 0) for r in rooms)
    voting = result.get("_voting") or {}
    print(f"[{slug}] ✓ {dt:.0f}s · {len(rooms)} rooms · npw={npw} · "
          f"voting runs={voting.get('n_runs')} rooms/run={voting.get('n_rooms_per_run')} "
          f"low-conf flags={len(voting.get('low_confidence_fields') or [])}", flush=True)
    print(f"[{slug}] saved → {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

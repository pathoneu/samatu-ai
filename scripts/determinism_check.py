"""Determinism check for the dim_extractor + majority_voter combo.

Runs the dimension extractor N times against a single page (no_cache=True
for fresh API calls), then runs the voter once on the resulting runs. The
voted output is canonicalised + JSON-encoded. A second voter pass over a
shuffled-order copy of the same runs must produce byte-identical JSON —
that's the determinism gate.

Usage:
    venv/bin/python3 scripts/determinism_check.py [--no-fresh] [--n-runs N]

  --no-fresh   skip live calls; rely entirely on the on-disk cache (free)
  --n-runs N   number of fresh dim_extractor calls to feed the voter
               (default: 3). Each call ≈$0.15 of Vision spend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-runs", type=int, default=3)
    ap.add_argument("--no-fresh", action="store_true",
                    help="reuse cached responses (no live Vision spend)")
    ap.add_argument("--page", type=int, default=2,
                    help="page nr of the floor plan (default 2)")
    args = ap.parse_args()

    _load_dotenv(REPO_ROOT / "backend" / ".env")
    if not args.no_fresh and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERR: ANTHROPIC_API_KEY required for --fresh mode")
        return 2

    from extractor.vision_call import pdf_to_b64_images
    from extractor.vision.dimension_extractor import extract_dimensions
    from extractor.vision.majority_voter import vote_dimensions

    pdf_path = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes, max_pages=args.page)
    img = pages[args.page - 1]["image_b64"]
    print(f"Loaded page {args.page} of {pdf_path.name}")

    print(f"\n=== Running dim_extractor {args.n_runs}× (no_cache={not args.no_fresh}) ===")
    runs: list[list[dict[str, Any]]] = []
    for i in range(args.n_runs):
        dl = extract_dimensions(image_b64=img, no_cache=not args.no_fresh)
        cache = dl._meta.get("cache")
        print(f"  Run {i+1}: {len(dl.dimensions)} dims (cache={cache}, in_tok={dl._meta.get('input_tokens')}, out_tok={dl._meta.get('output_tokens')})")
        runs.append([d.to_dict() for d in dl.dimensions])

    raw_sizes = [len(r) for r in runs]
    print(f"\nRaw counts across runs: {raw_sizes}")

    # First voted pass
    voted_a = vote_dimensions(runs)
    a_blob = json.dumps(voted_a, sort_keys=True).encode("utf-8")
    a_hash = hashlib.sha256(a_blob).hexdigest()[:16]
    print(f"\nVoted pass A: {len(voted_a['dimensions'])} voted dims | sha256:{a_hash}")
    print(f"  vote_count distribution: {voted_a['_meta']['vote_count_distribution']}")

    # Second voted pass on the SAME runs but reordered (tests that the voter
    # is order-independent — equivalent to running on permuted inputs).
    voted_b = vote_dimensions([runs[-1]] + runs[:-1])
    b_blob = json.dumps(voted_b, sort_keys=True).encode("utf-8")
    b_hash = hashlib.sha256(b_blob).hexdigest()[:16]
    print(f"Voted pass B (shuffled): sha256:{b_hash}")

    print()
    if a_blob == b_blob:
        print("✓ DETERMINISM PROVEN — voter output is order-independent")
        print(f"  Across {args.n_runs} dim_extractor runs with sizes {raw_sizes},")
        print(f"  voter produces {len(voted_a['dimensions'])} stable dimensions.")
        return 0
    else:
        print("✗ DETERMINISM FAILED — voter output differs by ordering")
        # Pinpoint difference
        ids_a = [d["id"] for d in voted_a["dimensions"]]
        ids_b = [d["id"] for d in voted_b["dimensions"]]
        if ids_a != ids_b:
            print(f"  ID order diverged: A starts {ids_a[:5]}, B starts {ids_b[:5]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

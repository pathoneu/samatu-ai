"""Generate docs/api_spec.json from the live FastAPI app.

Run after any route change so the spec stays in sync with the code.
The output is committed to git as the source-of-truth contract that
the viewer rebuild consumes.

Per Task 4 (2026-06-01): the spec MUST document every endpoint the
viewer team needs (room-graph, calibrate, recompute, annotations,
project-stats, export-excel) with example JSON response bodies
where feasible. FastAPI generates the spec from Pydantic models and
route signatures; richer descriptions live in the route docstrings.

Usage:
  python scripts/generate_openapi.py            # write to docs/api_spec.json
  python scripts/generate_openapi.py --stdout   # print to stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true",
                    help="print the spec to stdout instead of writing a file")
    ap.add_argument("--out", default="docs/api_spec.json",
                    help="output path (default: docs/api_spec.json)")
    args = ap.parse_args(argv)

    # Import the FastAPI app and snapshot the spec
    import main as _main
    spec = _main.app.openapi()

    # Annotate with v1-prefix note in the description so consumers see it
    info = spec.setdefault("info", {})
    extra_note = (
        "\n\n## URL prefix\n\n"
        "Every path documented below also responds under `/api/v1/<rest>`. "
        "The viewer rebuild SHOULD prefer `/api/v1/...` for forward-"
        "compatibility; legacy `/api/...` paths remain supported "
        "indefinitely for older clients."
    )
    if extra_note not in (info.get("description") or ""):
        info["description"] = (info.get("description") or "") + extra_note

    text = json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True)

    if args.stdout:
        print(text)
    else:
        out_path = REPO_ROOT / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        n_paths = len(spec.get("paths") or {})
        n_components = len((spec.get("components") or {}).get("schemas") or {})
        print(f"  OpenAPI spec → {out_path.relative_to(REPO_ROOT)}")
        print(f"  {n_paths} paths, {n_components} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

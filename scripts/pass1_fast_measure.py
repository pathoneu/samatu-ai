"""Measurement runner for the Pass-1 fast experiment (2026-10-28).

Usage:
    ENABLE_PARALLEL_VOTING=1 ./venv/bin/python scripts/pass1_fast_measure.py objektas_h objektas_d --tag fast
    ENABLE_PARALLEL_VOTING=1 SAMATU_ZOOM_SKIP_TABLE=1 ./venv/bin/python scripts/pass1_fast_measure.py objektas_h --tag parallel_zoom
    ./venv/bin/python scripts/pass1_fast_measure.py objektas_h --dry-run

What it does
------------
For each slug:
  1. Locates the PDF via the same CORPUS mapping novision_extract_batch.py uses.
  2. Calls extractor.extract_interior(pdf_bytes, None, progress_cb) with whatever
     env flags the CALLER set (the runner itself sets none).
  3. Times the whole run and per voting round (from voting_round_started events).
  4. Writes ground_truth/<slug>/ai_extract_<tag>.json.
     NEVER overwrites ai_extract.json (the baseline) or ai_extract_meta.json.
     Refuses to run if any tracked ground_truth file is modified.
  5. Prints one table row per slug.
  6. Writes docs/superpowers/fixtures/pass1_fast_<date>/runtime.tsv.

Flags printed at startup (so logs are self-contained):
  ENABLE_PARALLEL_VOTING, PARALLEL_VOTING_WARM, SAMATU_ZOOM_SKIP_TABLE,
  SAMATU_PASS1_NARROW, SAMATU_NO_VISION_ROUTE
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

CORPUS = {
    "objektas_a": "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf",
    "objektas_b": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/TP_Objektas B_2025naujausias.pdf",
    "objektas_c": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Techninio projekto planai_20250501 (a3)_2.pdf",
    "objektas_d": "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/objektas_d_TP_bundled.pdf",
    "objektas_g": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_g/project.pdf",
    "objektas_h": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf",
}

_ENV_FLAGS = [
    "ENABLE_PARALLEL_VOTING",
    "PARALLEL_VOTING_WARM",
    "SAMATU_ZOOM_SKIP_TABLE",
    "SAMATU_PASS1_NARROW",
    "SAMATU_NO_VISION_ROUTE",
]

PROTECTED_NAMES = {"ai_extract.json", "ai_extract_meta.json"}


def _print_flags() -> None:
    print("env flags at run start:")
    for k in _ENV_FLAGS:
        print(f"  {k}={os.environ.get(k, '(unset)')}")
    print()


def _check_gt_clean() -> None:
    """Refuse to run if any tracked ground_truth file is modified."""
    result = subprocess.run(
        ["git", "status", "--short", "ground_truth"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    if lines:
        print("ERROR: tracked ground_truth files are modified:", file=sys.stderr)
        for l in lines:
            print(f"  {l}", file=sys.stderr)
        print("Commit or stash them before running the measurement.", file=sys.stderr)
        sys.exit(1)


def _baseline_elapsed(slug: str) -> str:
    p = REPO / "ground_truth" / slug / "ai_extract.json"
    if not p.exists():
        return "N/A"
    try:
        d = json.loads(p.read_text())
        v = (d.get("_meta") or {}).get("elapsed_s")
        return str(v) if v is not None else "N/A"
    except Exception:
        return "N/A"


def _run_slug(slug: str, tag: str) -> dict:
    """Run extract_interior for one slug; return a row dict."""
    from extractor import extract_interior

    pdf_path = REPO / CORPUS[slug]
    if not pdf_path.exists():
        print(f"[{slug}] MISSING {pdf_path}", flush=True)
        return {"slug": slug, "error": "pdf_missing"}

    out_path = REPO / "ground_truth" / slug / f"ai_extract_{tag}.json"
    if out_path.name in PROTECTED_NAMES:
        print(f"[{slug}] REFUSE: tag '{tag}' would overwrite a protected file",
              file=sys.stderr)
        return {"slug": slug, "error": "protected_name"}

    pdf_bytes = pdf_path.read_bytes()

    # Collect stream events with timestamps.
    events: list[dict] = []

    def _progress(ev: dict) -> None:
        ev2 = dict(ev)
        ev2["_ts"] = time.time()
        events.append(ev2)

    t0 = time.time()
    result = extract_interior(pdf_bytes, None, _progress)
    elapsed = round(time.time() - t0, 1)

    # Per-round wall-clock times from stream events.
    round_starts: dict[int, float] = {}
    round_ends: dict[int, float] = {}
    for ev in events:
        name = ev.get("event", "")
        if name == "voting_round_started":
            rnd = ev.get("round")
            if rnd is not None:
                round_starts[rnd] = ev["_ts"]
        elif name == "voting_round_completed":
            rnd = ev.get("round")
            if rnd is not None:
                round_ends[rnd] = ev["_ts"]

    per_round_s: list[float] = []
    for rnd in sorted(round_starts):
        if rnd in round_ends:
            per_round_s.append(round(round_ends[rnd] - round_starts[rnd], 1))

    # Zoom telemetry.
    zoom_ev = next(
        (ev for ev in reversed(events) if ev.get("event") == "zoom_completed"),
        {}
    )

    meta = result.get("_meta") or {}
    baseline_s = _baseline_elapsed(slug)

    # Cost fields.
    voting_cost = meta.get("voting_cost_usd")
    extra_calls = meta.get("extra_calls") or []
    extra_cost_sum = None
    if extra_calls:
        vals = [c.get("cost_usd") for c in extra_calls if c.get("cost_usd") is not None]
        if vals:
            extra_cost_sum = round(sum(vals), 4)

    row = {
        "slug":             slug,
        "baseline_elapsed": baseline_s,
        "new_elapsed":      elapsed,
        "voting_runs":      meta.get("voting_runs", "N/A"),
        "per_round_s":      per_round_s,
        "zoom_attempted":   meta.get("zoom_attempted", zoom_ev.get("attempted", "N/A")),
        "zoom_applied":     meta.get("zoom_applied",   zoom_ev.get("applied",    "N/A")),
        "zoom_elapsed_s":   meta.get("zoom_elapsed_s", zoom_ev.get("elapsed_s",  "N/A")),
        "pages_sent":       meta.get("pages_sent", "N/A"),
        "voting_cost_usd":  voting_cost if voting_cost is not None else "n/a",
        "extra_cost_usd":   extra_cost_sum if extra_cost_sum is not None else "n/a",
        "rooms":            len(result.get("patalpos") or []),
        "bendras_plotas":   result.get("bendras_plotas_m2", "N/A"),
        "status":           result.get("status", "?"),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[{slug}] written -> {out_path.relative_to(REPO)}", flush=True)
    return row


def _print_table(rows: list[dict]) -> None:
    header = (
        f"{'slug':20s}  {'baseline_s':>12}  {'new_s':>8}  {'runs':>4}  "
        f"{'per_round_s':>28}  {'zoom_att':>8}  {'zoom_app':>8}  "
        f"{'zoom_s':>6}  {'pages':>5}  {'cost_vote':>10}  "
        f"{'cost_extra':>11}  {'rooms':>5}  {'plotas':>8}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        if r.get("error"):
            print(f"{r['slug']:20s}  ERROR: {r['error']}")
            continue
        rounds_str = str(r["per_round_s"]) if r["per_round_s"] else "N/A"
        print(
            f"{r['slug']:20s}  {str(r['baseline_elapsed']):>12}  "
            f"{str(r['new_elapsed']):>8}  {str(r['voting_runs']):>4}  "
            f"{rounds_str:>28}  {str(r['zoom_attempted']):>8}  "
            f"{str(r['zoom_applied']):>8}  "
            f"{str(r['zoom_elapsed_s']):>6}  {str(r['pages_sent']):>5}  "
            f"{str(r['voting_cost_usd']):>10}  "
            f"{str(r['extra_cost_usd']):>11}  "
            f"{str(r['rooms']):>5}  {str(r['bendras_plotas']):>8}"
        )


def _write_tsv(rows: list[dict], out_dir: Path) -> None:
    tsv_path = out_dir / "runtime.tsv"
    header = "\t".join([
        "slug", "baseline_elapsed_s", "new_elapsed_s", "voting_runs",
        "per_round_s", "zoom_attempted", "zoom_applied", "zoom_elapsed_s",
        "pages_sent", "voting_cost_usd", "extra_cost_usd",
        "rooms", "bendras_plotas_m2",
    ])
    lines = [header]
    for r in rows:
        if r.get("error"):
            lines.append(f"{r['slug']}\tERROR:{r['error']}")
            continue
        lines.append("\t".join([
            r["slug"],
            str(r["baseline_elapsed"]),
            str(r["new_elapsed"]),
            str(r["voting_runs"]),
            str(r["per_round_s"]),
            str(r["zoom_attempted"]),
            str(r["zoom_applied"]),
            str(r["zoom_elapsed_s"]),
            str(r["pages_sent"]),
            str(r["voting_cost_usd"]),
            str(r["extra_cost_usd"]),
            str(r["rooms"]),
            str(r["bendras_plotas"]),
        ]))
    tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"TSV -> {tsv_path.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Pass-1 fast experiment runtime per slug.")
    parser.add_argument("slugs", nargs="+",
                        help=f"Project slugs. Known: {', '.join(CORPUS)}")
    parser.add_argument("--tag", default="fast",
                        help="Output file suffix: ai_extract_<tag>.json (default: fast)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan; make no API calls.")
    args = parser.parse_args()

    for slug in args.slugs:
        if slug not in CORPUS:
            print(f"ERROR: unknown slug '{slug}'. Known: {', '.join(CORPUS)}",
                  file=sys.stderr)
            sys.exit(1)

    if args.tag in {"", "meta"}:
        print(f"ERROR: tag '{args.tag}' is reserved.", file=sys.stderr)
        sys.exit(1)
    if f"ai_extract_{args.tag}.json" in PROTECTED_NAMES:
        print(f"ERROR: tag '{args.tag}' would produce a protected filename.",
              file=sys.stderr)
        sys.exit(1)

    _print_flags()

    if args.dry_run:
        print("DRY RUN -- plan (no API calls):")
        print(f"  tag      : {args.tag}")
        for slug in args.slugs:
            pdf = REPO / CORPUS[slug]
            out = REPO / "ground_truth" / slug / f"ai_extract_{args.tag}.json"
            print(f"  [{slug}]")
            print(f"    pdf : {pdf} ({'exists' if pdf.exists() else 'MISSING'})")
            print(f"    out : {out.relative_to(REPO)}")
            print(f"    baseline_elapsed_s: {_baseline_elapsed(slug)}")
        print()
        print("Flags the manager would set:")
        print("  ENABLE_PARALLEL_VOTING=1 [SAMATU_ZOOM_SKIP_TABLE=1]")
        print("  ./venv/bin/python scripts/pass1_fast_measure.py", " ".join(args.slugs), "--tag", args.tag)
        return

    _check_gt_clean()

    rows = []
    for slug in args.slugs:
        print(f"\n=== {slug} ===", flush=True)
        row = _run_slug(slug, args.tag)
        rows.append(row)

    print("\n=== Runtime table ===")
    _print_table(rows)

    out_dir = REPO / f"docs/superpowers/fixtures/pass1_fast_{date.today()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(rows, out_dir)


if __name__ == "__main__":
    main()

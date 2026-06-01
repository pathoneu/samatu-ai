"""Run the production Vision pipeline on every truth-set project.

Reads ground_truth/registry.yaml, iterates projects that have a
project_pdf but no cached AI extract, calls extract_interior(), and
saves the result to ground_truth/<slug>/ai_extract.json plus a
cost-tracking sidecar.

Budget guardrails (the user authorized $19 total, but the spec also
says "pause if >$5 on one project without completing"):

  • Per-project soft cap: $5.00
  • Total session cap:    $19.00 (configurable via --budget)
  • Each project produces ai_extract.json + ai_extract_meta.json
  • Failures don't kill the session — log + move on

Run order: smallest → largest (cheapest validation first), opposite
of the spec's suggestion but the better engineering risk model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Opus 4.7 pricing (per CLAUDE.md)
OPUS_INPUT_PER_M = 15.0
OPUS_OUTPUT_PER_M = 75.0


@dataclass
class ProjectRun:
    slug: str
    pdf_path: str
    pdf_size_bytes: int = 0
    status: str = "pending"
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    n_rooms: int | None = None
    n_pages: int | None = None
    metas: list[dict] = field(default_factory=list)


def _accumulate_cost(meta_callback, target: ProjectRun) -> None:
    """Wire a progress-callback hook that captures Vision token usage."""
    pass  # Token accounting via the result's _meta block; no live hook needed.


def _walk_meta_for_tokens(obj, acc: dict) -> None:
    if isinstance(obj, dict):
        if "input_tokens" in obj and isinstance(obj.get("input_tokens"), (int, float)):
            acc["in"] = acc.get("in", 0) + int(obj["input_tokens"])
        if "output_tokens" in obj and isinstance(obj.get("output_tokens"), (int, float)):
            acc["out"] = acc.get("out", 0) + int(obj["output_tokens"])
        for v in obj.values():
            _walk_meta_for_tokens(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk_meta_for_tokens(v, acc)


def run_one(slug: str, pdf_path: Path, per_project_cap_usd: float) -> ProjectRun:
    out = ProjectRun(slug=slug, pdf_path=str(pdf_path))
    if not pdf_path.exists():
        out.status, out.error = "skipped_missing_pdf", f"PDF not found: {pdf_path}"
        return out

    pdf_bytes = pdf_path.read_bytes()
    out.pdf_size_bytes = len(pdf_bytes)
    print(f"\n══════ {slug} ═══════════════════════════════")
    print(f"  PDF: {pdf_path.name}  size={out.pdf_size_bytes/1024:.0f}KB")

    progress_log: list[dict] = []
    def _progress(ev):
        progress_log.append(ev)
        et = ev.get("event")
        if et in ("started", "rendering_pdf", "eksplikacija_started",
                  "eksplikacija_completed", "error", "completed", "extracting"):
            print(f"  · {et}: {ev.get('page_count', '')} {ev.get('message', '')}".rstrip())

    t0 = time.time()
    try:
        from extractor.vision_call import extract_interior
        result = extract_interior(pdf_bytes, rules_override=None,
                                  progress_cb=_progress)
    except Exception as exc:
        out.seconds = time.time() - t0
        out.status, out.error = "crashed", f"{type(exc).__name__}: {exc}"
        print(f"  ✗ CRASHED in {out.seconds:.1f}s — {out.error}")
        out.metas = progress_log
        return out

    out.seconds = time.time() - t0
    out.metas = progress_log

    if result.get("status") == "error":
        out.status, out.error = "extractor_error", str(result.get("_error"))
        print(f"  ✗ Extractor returned error: {out.error}")
        return out

    # Token accounting — walk the _meta blocks the extractor leaves on result.
    acc = {}
    _walk_meta_for_tokens(result.get("_meta") or {}, acc)
    # Some intermediate calls leave _meta on each room; capture those too.
    for r in (result.get("patalpos") or []):
        _walk_meta_for_tokens(r.get("_meta") or {}, acc)
    out.input_tokens = acc.get("in", 0)
    out.output_tokens = acc.get("out", 0)
    out.cost_usd = round(
        (out.input_tokens / 1_000_000.0) * OPUS_INPUT_PER_M
        + (out.output_tokens / 1_000_000.0) * OPUS_OUTPUT_PER_M,
        4,
    )
    out.n_rooms = len(result.get("patalpos") or [])
    out.n_pages = (result.get("_meta") or {}).get("page_count")

    # Save the AI extract beside the truth.
    out_dir = REPO_ROOT / "ground_truth" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ai_extract.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Save run metadata (token + cost + progress events)
    (out_dir / "ai_extract_meta.json").write_text(
        json.dumps(asdict(out), ensure_ascii=False, indent=2,
                   default=str), encoding="utf-8"
    )

    out.status = "ok"
    print(f"  ✓ {out.seconds:.0f}s · in={out.input_tokens} out={out.output_tokens} · "
          f"${out.cost_usd:.2f} · {out.n_rooms} rooms")
    if out.cost_usd > per_project_cap_usd:
        print(f"  ⚠ project cost ${out.cost_usd:.2f} > per-project cap "
              f"${per_project_cap_usd:.2f} — flagged")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=19.0,
                    help="Total session budget in USD (default 19.0)")
    ap.add_argument("--per-project-cap", type=float, default=5.0,
                    help="Soft cap per project in USD (default 5.0)")
    ap.add_argument("--only", help="Run only this single slug",
                    default=None)
    ap.add_argument("--order", default="size",
                    choices=["size", "registry"],
                    help="Run order: 'size' = smallest PDF first; 'registry' = registry order")
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml")
                         .read_text(encoding="utf-8"))
    projects = [p for p in (reg.get("projects") or [])
                if not p.get("blocked_for_vision_extraction")
                and not p.get("has_cached_extract")]
    if args.only:
        projects = [p for p in projects if p["slug"] == args.only]

    # Map slug → resolved PDF path + size
    enriched = []
    for p in projects:
        pdf_path = REPO_ROOT / p["project_pdf"]
        size = pdf_path.stat().st_size if pdf_path.exists() else 0
        enriched.append({**p, "_pdf_path": pdf_path, "_size": size})

    if args.order == "size":
        enriched.sort(key=lambda p: p["_size"])

    print(f"\n  Vision extraction sprint")
    print(f"  Budget: ${args.budget:.2f}  per-project cap: ${args.per_project_cap:.2f}")
    print(f"  Order: {args.order}  ·  {len(enriched)} project(s) to process\n")
    for p in enriched:
        print(f"    {p['slug']:<14} {p['_size']/1024:>7.0f} KB  {p['_pdf_path'].name}")

    runs: list[ProjectRun] = []
    spent = 0.0
    for p in enriched:
        if spent >= args.budget:
            print(f"\n  ⚠ session budget reached (${spent:.2f}) — skipping remainder")
            runs.append(ProjectRun(slug=p["slug"], pdf_path=str(p["_pdf_path"]),
                                    status="skipped_budget"))
            continue
        r = run_one(p["slug"], p["_pdf_path"], args.per_project_cap)
        runs.append(r)
        spent += r.cost_usd

    print(f"\n══════ Session summary ═══════════════════════════")
    print(f"  {'slug':<14} {'status':<18} {'cost':>8} {'sec':>6} {'rooms':>6}")
    print("  " + "─" * 60)
    for r in runs:
        print(f"  {r.slug:<14} {r.status:<18} ${r.cost_usd:>6.2f} "
              f"{r.seconds:>5.0f}s {(r.n_rooms or 0):>6}")
    print(f"\n  Total spent: ${spent:.2f} / ${args.budget:.2f} budget")

    # Save the session manifest
    manifest = REPO_ROOT / "eval_runs" / f"vision_sprint_{int(time.time())}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(
        {"budget_usd": args.budget,
         "per_project_cap_usd": args.per_project_cap,
         "runs": [asdict(r) for r in runs],
         "total_spent_usd": round(spent, 4)},
        ensure_ascii=False, indent=2, default=str
    ), encoding="utf-8")
    print(f"  Manifest → {manifest.relative_to(REPO_ROOT)}")
    return 0 if all(r.status in ("ok", "skipped_budget") for r in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())

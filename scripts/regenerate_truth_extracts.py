"""Regenerate every cached ground_truth/<slug>/ai_extract.json by running the
CURRENT restored production pipeline LIVE, with N-pass voting ON (the default).

WHY this exists (and why run_vision_on_truth_set.py is NOT enough):
  • run_vision_on_truth_set.py FILLS IN *missing* extracts — it filters out any
    project with `has_cached_extract: true` (berzas) and so can never refresh the
    enrichment-dependent originator.
  • The cached ai_extract.json files were built (commit c91dd3b, "Beržų MAE
    3.25%→1.15%") when two now-reconstructed reader modules + the OFFLINE
    scripts/apply_adjacency.py enrichment + hand corrections existed. They are
    therefore MORE enriched than fresh production output, so eval_harness
    --totals-only (which scores against them) OVERSTATES production accuracy
    (~7.5× on berzas: honest 14.95% vs published 1.99%).
  • This script overwrites them with HONEST fresh production output so the
    benchmark measures what a real user actually gets.

The N-pass voting path (commits f26665f, 8fbb31e) already runs the adjacency
pass inline on the resolved floor page, so fresh output reproduces
n_partition_walls WITHOUT the offline apply_adjacency.py step. What it does NOT
reproduce: hand corrections (e.g. berzas vision_corrections.json). That is the
point — those are the enrichment we are removing from the benchmark.

SAFETY:
  • REFUSES to run unless the backup dir exists (see BACKUP_DIR below). The
    cached extracts are the contractor-validated baseline; back them up first:
        mkdir -p eval_runs/cached_baseline_backup_2026-06-09
        for s in berzas objektas_b ciurliu lazunu romainiai sernu; do
          mkdir -p eval_runs/cached_baseline_backup_2026-06-09/$s
          cp -p ground_truth/$s/*.json eval_runs/cached_baseline_backup_2026-06-09/$s/
        done
    (git HEAD also preserves them.)
  • Budget guardrails: $19 total session cap, $5/project soft cap (warn only).
  • Skips blocked_for_vision_extraction projects (sernu — no architectural
    floor plan in the bundle; Vision would produce garbage).
  • Only regenerates projects that ALREADY have an ai_extract.json (the set the
    benchmark scores). Use --include-missing to also fill projects lacking one.

Usage:  venv/bin/python scripts/regenerate_truth_extracts.py
        venv/bin/python scripts/regenerate_truth_extracts.py --only ciurliu
        venv/bin/python scripts/regenerate_truth_extracts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Voting MUST be on, and set BEFORE any backend import so get_flags() (which
# reads os.environ at call time) sees it. This is the production default; we
# pin it explicitly so the regenerated extracts are reproducible and the
# config is recorded in the meta sidecar.
os.environ.setdefault("ENABLE_EXTRACTION_VOTING", "1")
os.environ.setdefault("VOTING_N", "3")

import yaml  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / "backend" / ".env")

BACKUP_DIR = REPO_ROOT / "eval_runs" / "cached_baseline_backup_2026-06-09"

# Opus 4.7 pricing (per CLAUDE.md). Cost is APPROXIMATE — uncached input/output
# only, mirroring run_vision_on_truth_set.py so the numbers are comparable to
# the cached ai_extract_meta.json sidecars.
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
    voting_on: bool = True
    voting_n: int | None = None
    # quick sanity signals so we can eyeball honesty without a full eval pass
    kampai: float | None = None
    combined_paint: float | None = None
    n_partition_walls_total: int | None = None
    ceiling_heights: list = field(default_factory=list)
    apdailos_rooms_updated: int | None = None
    metas: list = field(default_factory=list)


def _walk_meta_for_tokens(obj, acc: dict) -> None:
    if isinstance(obj, dict):
        if isinstance(obj.get("input_tokens"), (int, float)):
            acc["in"] = acc.get("in", 0) + int(obj["input_tokens"])
        if isinstance(obj.get("output_tokens"), (int, float)):
            acc["out"] = acc.get("out", 0) + int(obj["output_tokens"])
        for v in obj.values():
            _walk_meta_for_tokens(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk_meta_for_tokens(v, acc)


def _kampai(result: dict) -> float:
    for p in result.get("pozicijos") or []:
        if (p.get("aprasymas") or "") == "Dažymo kampų montavimas":
            return round(float(p.get("kiekis") or 0), 2)
    return 0.0


def _combined_paint(result: dict) -> float:
    tot = 0.0
    for p in result.get("pozicijos") or []:
        a = p.get("aprasymas") or ""
        if a.startswith(("Sienų, lubų glaistymas/dažymas",
                         "Sienų glaistymas/dažymas",
                         "Lubų glaistymas/dažymas")):
            tot += float(p.get("kiekis") or 0)
    return round(tot, 2)


def _npw_total(result: dict) -> int:
    return sum(int(r.get("n_partition_walls") or 0)
               for r in (result.get("patalpos") or []))


def _ceiling_heights(result: dict) -> list:
    return sorted({round(float(r.get("lubu_aukstis_m") or 0), 2)
                   for r in (result.get("patalpos") or [])})


def run_one(slug: str, pdf_path: Path, per_project_cap_usd: float,
            voting_n_val: int) -> ProjectRun:
    out = ProjectRun(slug=slug, pdf_path=str(pdf_path),
                     voting_on=True, voting_n=voting_n_val)
    if not pdf_path.exists():
        out.status, out.error = "skipped_missing_pdf", f"PDF not found: {pdf_path}"
        return out

    pdf_bytes = pdf_path.read_bytes()
    out.pdf_size_bytes = len(pdf_bytes)
    print(f"\n══════ {slug} ═══════════════════════════════", flush=True)
    print(f"  PDF: {pdf_path.name}  size={out.pdf_size_bytes/1024:.0f}KB  "
          f"voting=ON N={voting_n_val}", flush=True)

    progress_log: list[dict] = []
    def _progress(ev):
        progress_log.append(ev)
        et = ev.get("event")
        if et in ("started", "rendering_pdf", "eksplikacija_started",
                  "eksplikacija_completed", "error", "completed"):
            print(f"  · {et}: {ev.get('page_count', '')} "
                  f"{ev.get('message', '')}".rstrip(), flush=True)

    t0 = time.time()
    try:
        from extractor.vision_call import extract_interior
        result = extract_interior(pdf_bytes, rules_override=None,
                                  progress_cb=_progress)
    except Exception as exc:
        import traceback
        out.seconds = time.time() - t0
        out.status, out.error = "crashed", f"{type(exc).__name__}: {exc}"
        print(f"  ✗ CRASHED in {out.seconds:.1f}s — {out.error}", flush=True)
        traceback.print_exc()
        out.metas = progress_log
        return out

    out.seconds = time.time() - t0
    out.metas = progress_log

    if result.get("status") == "error":
        out.status, out.error = "extractor_error", str(result.get("_error"))
        print(f"  ✗ Extractor returned error: {out.error}", flush=True)
        return out

    acc: dict = {}
    _walk_meta_for_tokens(result.get("_meta") or {}, acc)
    for r in (result.get("patalpos") or []):
        _walk_meta_for_tokens(r.get("_meta") or {}, acc)
    out.input_tokens = acc.get("in", 0)
    out.output_tokens = acc.get("out", 0)
    out.cost_usd = round(
        (out.input_tokens / 1_000_000.0) * OPUS_INPUT_PER_M
        + (out.output_tokens / 1_000_000.0) * OPUS_OUTPUT_PER_M, 4)
    out.n_rooms = len(result.get("patalpos") or [])
    out.n_pages = (result.get("_meta") or {}).get("page_count")
    out.kampai = _kampai(result)
    out.combined_paint = _combined_paint(result)
    out.n_partition_walls_total = _npw_total(result)
    out.ceiling_heights = _ceiling_heights(result)
    out.apdailos_rooms_updated = (result.get("_meta") or {}).get("apdailos_rooms_updated")

    # Stamp the voting config + a HONEST provenance marker onto the saved extract
    # so anyone reading it later knows it is fresh production, not enriched.
    result.setdefault("_meta", {})
    result["_meta"]["_regen_provenance"] = {
        "source": "scripts/regenerate_truth_extracts.py",
        "voting_on": True,
        "voting_n": voting_n_val,
        "note": "fresh live production output; NO offline apply_adjacency / "
                "hand corrections. Replaces enriched cached extract.",
    }

    out_dir = REPO_ROOT / "ground_truth" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ai_extract.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "ai_extract_meta.json").write_text(
        json.dumps(asdict(out), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")

    out.status = "ok"
    print(f"  ✓ {out.seconds:.0f}s · in={out.input_tokens} out={out.output_tokens} · "
          f"${out.cost_usd:.2f} · {out.n_rooms} rooms", flush=True)
    print(f"    kampai={out.kampai}  combined_paint={out.combined_paint}  "
          f"npw={out.n_partition_walls_total}  heights={out.ceiling_heights}  "
          f"apdailos={out.apdailos_rooms_updated}", flush=True)
    if out.cost_usd > per_project_cap_usd:
        print(f"  ⚠ project cost ${out.cost_usd:.2f} > per-project cap "
              f"${per_project_cap_usd:.2f} — flagged (soft cap, continuing)",
              flush=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=19.0)
    ap.add_argument("--per-project-cap", type=float, default=5.0)
    ap.add_argument("--only", default=None, help="regenerate only this slug")
    ap.add_argument("--include-missing", action="store_true",
                    help="also (re)generate projects that lack an ai_extract.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and exit without any Vision spend")
    args = ap.parse_args(argv)

    if not BACKUP_DIR.exists():
        print(f"✗ REFUSING TO RUN: backup dir not found:\n    {BACKUP_DIR}\n"
              f"  Back up the contractor-validated cached extracts first "
              f"(see this script's docstring).", file=sys.stderr)
        return 2

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml")
                         .read_text(encoding="utf-8"))
    candidates = []
    for p in (reg.get("projects") or []):
        slug = p["slug"]
        if p.get("blocked_for_vision_extraction"):
            print(f"  ⊘ {slug}: blocked_for_vision_extraction — "
                  f"{p.get('blocked_reason', '')[:70]}")
            continue
        has_extract = (REPO_ROOT / "ground_truth" / slug / "ai_extract.json").exists()
        if not has_extract and not args.include_missing:
            print(f"  ⊘ {slug}: no existing ai_extract.json (use --include-missing)")
            continue
        pdf_path = REPO_ROOT / p["project_pdf"]
        size = pdf_path.stat().st_size if pdf_path.exists() else 0
        candidates.append({**p, "_pdf_path": pdf_path, "_size": size,
                           "_scope_mismatch": bool(p.get("scope_mismatch"))})

    if args.only:
        candidates = [p for p in candidates if p["slug"] == args.only]
    # smallest PDF first — cheapest validation first
    candidates.sort(key=lambda p: p["_size"])

    voting_n_val = int(os.environ.get("VOTING_N", "3"))
    print(f"\n  Truth-set extract REGENERATION (honest, voting ON N={voting_n_val})")
    print(f"  Budget ${args.budget:.2f} · per-project cap ${args.per_project_cap:.2f}"
          f" · {len(candidates)} project(s)\n")
    for p in candidates:
        tag = "  [scope_mismatch: MAE-excluded]" if p["_scope_mismatch"] else ""
        print(f"    {p['slug']:<14} {p['_size']/1024:>7.0f} KB  "
              f"{p['_pdf_path'].name}{tag}")

    if args.dry_run:
        print("\n  --dry-run: no Vision spend. Exiting.")
        return 0

    runs: list[ProjectRun] = []
    spent = 0.0
    for p in candidates:
        if spent >= args.budget:
            print(f"\n  ⚠ session budget reached (${spent:.2f}) — skipping rest",
                  flush=True)
            runs.append(ProjectRun(slug=p["slug"], pdf_path=str(p["_pdf_path"]),
                                    status="skipped_budget"))
            continue
        r = run_one(p["slug"], p["_pdf_path"], args.per_project_cap, voting_n_val)
        runs.append(r)
        spent += r.cost_usd

    print(f"\n══════ Regeneration summary ═══════════════════════", flush=True)
    print(f"  {'slug':<14} {'status':<18} {'cost':>8} {'sec':>6} {'rooms':>6}"
          f" {'kampai':>8} {'paint':>8} {'npw':>5}")
    print("  " + "─" * 80)
    for r in runs:
        print(f"  {r.slug:<14} {r.status:<18} ${r.cost_usd:>6.2f} "
              f"{r.seconds:>5.0f}s {(r.n_rooms or 0):>6} "
              f"{(r.kampai or 0):>8.1f} {(r.combined_paint or 0):>8.1f} "
              f"{(r.n_partition_walls_total or 0):>5}", flush=True)
    print(f"\n  Total spent: ${spent:.2f} / ${args.budget:.2f} budget", flush=True)

    manifest = REPO_ROOT / "eval_runs" / f"regen_sprint_{int(time.time())}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(
        {"budget_usd": args.budget, "per_project_cap_usd": args.per_project_cap,
         "voting_on": True, "voting_n": voting_n_val,
         "runs": [asdict(r) for r in runs], "total_spent_usd": round(spent, 4)},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"  Manifest → {manifest.relative_to(REPO_ROOT)}", flush=True)
    return 0 if all(r.status in ("ok", "skipped_budget") for r in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())

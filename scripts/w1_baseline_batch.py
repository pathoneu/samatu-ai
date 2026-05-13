"""W1 baseline batch — run extract_interior on the full interior corpus
in parallel, dump per-project JSON + per-project quick summary, and
print an aggregate table.

Output:
  reports/baseline/<project>.json     full extraction result
  reports/baseline/<project>.summary  human-readable per-project summary

Council R2 (2026-05-11): branch trigger for W2-W4. After this batch:
  - if predominant error class = bad Vision inputs → Branch A
  - if predominant error class = formula bugs       → Branch B
  - if ~equal mix                                    → Branch C (count-correction UI)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / "backend" / ".env")

CORPUS = Path.home() / "Desktop" / "test_pdfs"
OUT_DIR = REPO_ROOT / "reports" / "baseline"


def run_one(pdf_path_str: str) -> dict:
    """Worker process. Runs full extract_interior on one PDF."""
    pdf_path = Path(pdf_path_str)
    t0 = time.time()
    try:
        from extractor import extract_interior
        result = extract_interior(pdf_path.read_bytes(), None)
        elapsed = time.time() - t0
        return {"pdf": pdf_path.name, "ok": True, "elapsed_s": elapsed, "result": result}
    except Exception as exc:
        return {
            "pdf": pdf_path.name, "ok": False,
            "elapsed_s": time.time() - t0,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def summarise(result: dict) -> dict:
    """Pull a small per-project signal vector for the aggregate table."""
    if not result.get("ok"):
        return {"pdf": result["pdf"], "ok": False, "error": result.get("error")}
    r = result["result"]
    rooms = r.get("patalpos") or []
    lubu = r.get("lubu_auksciai") or {}
    lubu_by_nr = r.get("lubu_auksciai_by_nr") or {}
    per_room_count = sum(
        1 for room in rooms if room.get("lubu_aukstis_saltinis") == "per_room"
    )
    return {
        "pdf": result["pdf"],
        "ok": True,
        "elapsed_s": round(result["elapsed_s"], 1),
        "rooms": len(rooms),
        "bendras_plotas_m2": r.get("bendras_plotas_m2"),
        "lubu_aukstis_m": r.get("lubu_aukstis_m"),
        "lubu_auksciai_count": len(lubu),
        "lubu_auksciai_by_nr_count": len(lubu_by_nr),
        "per_room_ceiling_applied": per_room_count,
        "warnings_count": len(r.get("warnings") or []),
        "pozicijos_count": len(r.get("pozicijos") or r.get("darbu_sarasas") or []),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(CORPUS.glob("*.pdf"))
    print(f"Running W1 baseline batch on {len(pdfs)} PDFs in parallel…\n")
    for p in pdfs:
        print(f"  • {p.name} ({p.stat().st_size // 1024} KB)")
    print()

    summaries: list[dict] = []
    with ProcessPoolExecutor(max_workers=min(5, len(pdfs))) as pool:
        futures = {pool.submit(run_one, str(p)): p for p in pdfs}
        for fut in as_completed(futures):
            p = futures[fut]
            res = fut.result()
            summaries.append(summarise(res))
            stem = p.stem
            (OUT_DIR / f"{stem}.json").write_text(
                json.dumps(res.get("result", {}), ensure_ascii=False, indent=2)
                if res.get("ok") else json.dumps(res, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            s = summaries[-1]
            mark = "✓" if s.get("ok") else "✗"
            print(f"  {mark} {s['pdf']:32s} {s.get('elapsed_s', '?')}s")

    print("\n=== AGGREGATE SIGNAL TABLE ===\n")
    headers = ["pdf", "rooms", "plotas", "lubu_m", "by_nr", "per_room", "pozicijos", "warns"]
    print(" | ".join(f"{h:14s}" for h in headers))
    print("-" * (16 * len(headers)))
    for s in sorted(summaries, key=lambda x: x["pdf"]):
        if not s.get("ok"):
            print(f"{s['pdf']:32s} ERROR: {s.get('error', '?')[:80]}")
            continue
        print(
            f"{s['pdf']:14s} | "
            f"{s['rooms']:14d} | "
            f"{(s.get('bendras_plotas_m2') or 0):14.1f} | "
            f"{str(s.get('lubu_aukstis_m')):14s} | "
            f"{s['lubu_auksciai_by_nr_count']:14d} | "
            f"{s['per_room_ceiling_applied']:14d} | "
            f"{s['pozicijos_count']:14d} | "
            f"{s['warnings_count']:14d}"
        )

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

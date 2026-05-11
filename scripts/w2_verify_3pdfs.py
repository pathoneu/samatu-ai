"""W2 verification — re-run projektas_3 + projektas_4(1) + projektas_4(2)
in parallel after the imperative prompt fix shipped in be422a7.

Target signal: each PDF returns lubu_auksciai_by_nr populated with > 0
entries (no narration-only output).
"""
from __future__ import annotations

import json
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
TARGETS = [
    "projektas_3_breziniai.pdf",
    "projektas_4(1)_breziniai.pdf",
    "projektas_4(2)_breziniai.pdf",
]


def run_one(pdf_path_str: str) -> dict:
    pdf_path = Path(pdf_path_str)
    t0 = time.time()
    try:
        from extractor import extract_interior
        result = extract_interior(pdf_path.read_bytes(), None)
        return {"pdf": pdf_path.name, "ok": True, "elapsed_s": time.time() - t0, "result": result}
    except Exception as exc:
        return {
            "pdf": pdf_path.name, "ok": False,
            "elapsed_s": time.time() - t0,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = [CORPUS / t for t in TARGETS]
    print(f"Re-running {len(pdfs)} PDFs in parallel after imperative prompt fix…\n")

    with ProcessPoolExecutor(max_workers=len(pdfs)) as pool:
        futures = {pool.submit(run_one, str(p)): p for p in pdfs}
        results = []
        for fut in as_completed(futures):
            p = futures[fut]
            res = fut.result()
            results.append(res)
            (OUT_DIR / f"{p.stem}.json").write_text(
                json.dumps(res.get("result", {}), ensure_ascii=False, indent=2)
                if res.get("ok") else json.dumps(res, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            mark = "✓" if res.get("ok") else "✗"
            print(f"  {mark} {res['pdf']:32s} {res.get('elapsed_s', '?'):.0f}s")

    print("\n=== POST-FIX CEILING CAPTURE ===\n")
    for res in sorted(results, key=lambda x: x["pdf"]):
        if not res.get("ok"):
            print(f"  ✗ {res['pdf']}: {res.get('error', '?')[:100]}")
            continue
        r = res["result"]
        by_nr = r.get("lubu_auksciai_by_nr") or {}
        by_name = r.get("lubu_auksciai") or {}
        rooms = r.get("patalpos") or []
        per_room = sum(1 for x in rooms if x.get("lubu_aukstis_saltinis") == "per_room")
        non_default = {k: v for k, v in by_name.items() if v != 2.82 and v != 2.8}
        mark = "🎯" if per_room == len(rooms) else ("⚠ " if per_room > 0 else "✗ ")
        print(f"{mark} {res['pdf']}")
        print(f"     rooms={len(rooms)}, per_room={per_room}/{len(rooms)}, by_nr={len(by_nr)}, by_name={len(by_name)}")
        if non_default:
            print(f"     non-2.8 heights: {non_default}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

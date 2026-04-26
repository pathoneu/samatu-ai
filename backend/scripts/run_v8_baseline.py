"""Capture CURRENT V8 pipeline accuracy on P1-P5 (THE BAR).

Architecture notes:
- Each project runs in a fresh subprocess to avoid pypdfium2 thread-state
  corruption. When detect_all_symbols_for_pdf uses ThreadPoolExecutor with
  parallel pdfplumber.to_image() calls, pypdfium2 global state gets corrupted
  for subsequent pdfplumber renders in the same process. Subprocess isolation
  replicates the HTTP-server behavior where each request is independent.
- The per-project worker (run_one_worker) is invoked with python <script> --worker N.
- P4/P5 have multiple numbered PDF files; we use the first (1) file — same as
  a user would do when uploading to the HTTP endpoint (files[0] only).

This run IS the accuracy bar — the new simplified pipeline must match or
exceed these numbers in Phase 3.

Usage (from repo root, venv active):
    venv/bin/python backend/scripts/run_v8_baseline.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
TRAINING = ROOT / "training-data"
OUT = Path(__file__).parent / "baseline_output"
OUT.mkdir(exist_ok=True)

VENV_PYTHON = str(ROOT / "venv" / "bin" / "python")
# Fallback: the venv/bin/python path used when calling subprocess
if not Path(VENV_PYTHON).exists():
    VENV_PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Per-project PDF discovery
# Supports:
#   projektas_N_breziniai.pdf   (P1, P2, P3)
#   projektas_N(K)_breziniai.pdf  (P4: (1) first numbered)
#   projektas_N(K)_breziniai.pdf  (P5: (1) first numbered)
# ---------------------------------------------------------------------------

def find_breziniai_pdf(n: int) -> Path | None:
    proj_dir = TRAINING / f"projektas_{n}"
    if not proj_dir.exists():
        return None
    # Preferred: exact name
    exact = proj_dir / f"projektas_{n}_breziniai.pdf"
    if exact.exists():
        return exact
    # Numbered variants: pick the LARGEST file. P5 has 9 separate PDFs of
    # different sizes; the smallest are 1-page detail sheets (no eksplikacija,
    # no usable plan). The largest is the main set with rooms.
    candidates = list(proj_dir.glob(f"projektas_{n}(*)*_breziniai.pdf"))
    candidates += list(proj_dir.glob(f"porjektas_{n}(*)*_breziniai.pdf"))  # typo'd file
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_size)
    return None


# ---------------------------------------------------------------------------
# Worker mode (invoked as subprocess per project)
# ---------------------------------------------------------------------------

def worker_main(n: int):
    """Run the full V8 pipeline for project N and print JSON result to stdout."""
    sys.path.insert(0, str(BACKEND))

    env_file = BACKEND / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_file))
        except ImportError:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())

    pdf_path = find_breziniai_pdf(n)
    if pdf_path is None:
        print(json.dumps({
            "status": "error",
            "_error": f"no breziniai PDF found in {TRAINING}/projektas_{n}/",
        }))
        return

    pdf_bytes = pdf_path.read_bytes()
    print(f"[worker P{n}] PDF: {pdf_path.name} ({len(pdf_bytes)//1024}KB)",
          file=sys.stderr)

    try:
        result = asyncio.run(_run_v8_pipeline(pdf_bytes))
    except Exception as exc:
        result = {
            "status": "error",
            "_error": str(exc),
            "_traceback": traceback.format_exc(),
        }

    print(json.dumps(result, ensure_ascii=False))


# ---------------------------------------------------------------------------
# V8 pipeline — full replica of /extract-interior-v8 route from main.py ~L3677
# ---------------------------------------------------------------------------

async def _run_v8_pipeline(pdf_bytes: bytes) -> dict:
    """Replicates the /extract-interior-v8 route handler body exactly.

    Import structure mirrors main.py:
        from interior_v8 import (extract_v7, extract_v8, auto_detect_scale,
                                  classify_pdf, summarize_pages, lt_validate_rooms,
                                  generate_pasiulymas)
        from interior_v8 import extract_eksplikacija_from_pdf
        from interior_v9 import detect_all_symbols_for_pdf
    """
    # These imports are done inside the function so that the worker subprocess
    # only runs them once (no cross-contamination from orchestrator process).
    from interior_v8 import (
        extract_v7,
        extract_v8, auto_detect_scale,
        classify_pdf, summarize_pages,
        lt_validate_rooms,
        generate_pasiulymas,
    )
    from interior_v8 import extract_eksplikacija_from_pdf
    from interior_v8.universal_engine import (
        _classify_trace_type, _build_trace_links, _explain_formula,
    )
    from interior_v9 import detect_all_symbols_for_pdf
    import pdfplumber

    PRIORITY_TYPES = ["floor_plan", "specification", "wall_elevation", "ceiling_plan"]
    SYMBOL_DETECTION_TIMEOUT_S = 60
    user_rules: dict = {"interior_subtype": "naujas"}
    loop = asyncio.get_running_loop()

    # ── 0.5: Page classifier ──────────────────────────────────────────────
    page_classifications = []
    pages_summary = {}
    try:
        page_classifications = classify_pdf(pdf_bytes)
        pages_summary = summarize_pages(page_classifications)
        print(f"  [page_clf] {len(page_classifications)} psl, "
              f"tipų: {dict((k, len(v)) for k, v in pages_summary.get('by_type', {}).items())}",
              file=sys.stderr)
    except Exception as e:
        print(f"  [page_clf] klaida: {e}", file=sys.stderr)

    page_filter_for_vision: list[int] = []
    if page_classifications:
        for ptype in PRIORITY_TYPES:
            for pc in page_classifications:
                if pc.get("type") == ptype:
                    pn = pc.get("page")
                    if pn and pn not in page_filter_for_vision:
                        page_filter_for_vision.append(pn)
        print(f"  [page_clf] Vision page_filter: {len(page_filter_for_vision)} psl.",
              file=sys.stderr)
    else:
        print("  [page_clf] Vision page_filter: tuščias — fallback į pirmus 20 psl.",
              file=sys.stderr)

    # ── 0.7: Eksplikacijos parser ────────────────────────────────────────
    eksplikacija_rooms: list[dict] = []
    try:
        eksplikacija_rooms = await loop.run_in_executor(
            None,
            lambda: extract_eksplikacija_from_pdf(pdf_bytes, max_pages=10),
        )
        if eksplikacija_rooms:
            total = sum(r.get("plotas_m2", 0) for r in eksplikacija_rooms)
            print(f"  [eksplik] RASTA: {len(eksplikacija_rooms)} patalpų, viso {total:.1f}m²",
                  file=sys.stderr)
        else:
            print("  [eksplik] nerasta tekstinės lentelės — naudojam Vision",
                  file=sys.stderr)
    except Exception as e:
        print(f"  [eksplik] klaida: {e}", file=sys.stderr)

    # ── 1: Vision extraction ─────────────────────────────────────────────
    ai_result = await loop.run_in_executor(
        None,
        lambda: extract_v7(
            pdf_bytes,
            page_filter=page_filter_for_vision if page_filter_for_vision else None,
            max_pages=20,
        ),
    )

    if ai_result.get("status") != "ok":
        return {**ai_result, "_pipeline_stage": "vision_failed"}

    # ── 2: Build rooms_input ─────────────────────────────────────────────
    rooms_input = []
    if eksplikacija_rooms:
        for r in eksplikacija_rooms:
            rooms_input.append({
                "nr": r.get("nr"),
                "pavadinimas": r.get("pavadinimas"),
                "paskirtis": r.get("paskirtis"),
                "puslapio_nr": r.get("page_nr"),
                "plotas_m2": r.get("plotas_m2"),
                "perimetras_m": round(4.18 * (r.get("plotas_m2", 0) ** 0.5), 1),
                "lubu_aukstis_m": 2.82,
                "_source": "eksplikacija_text",
            })
        vision_by_name = {
            (p.get("pavadinimas", "") or "").lower(): p
            for p in ai_result.get("patalpos", [])
        }
        for r in rooms_input:
            v = vision_by_name.get((r["pavadinimas"] or "").lower())
            if v:
                r["bbox_pct"] = v.get("bbox_pct")
                r["lubu_aukstis_m"] = v.get("lubu_aukstis_m") or r["lubu_aukstis_m"]
        print(f"  [rooms] iš EKSPLIKACIJOS: {len(rooms_input)}", file=sys.stderr)
    else:
        for p in ai_result.get("patalpos", []):
            rooms_input.append({
                "nr": p.get("nr"),
                "pavadinimas": p.get("pavadinimas"),
                "paskirtis": p.get("paskirtis"),
                "puslapio_nr": p.get("puslapio_nr"),
                "bbox_pct": p.get("bbox_pct"),
                "plotas_m2": p.get("plotas_m2"),
                "perimetras_m": p.get("perimetras_m"),
                "lubu_aukstis_m": p.get("lubu_aukstis_m"),
                "_source": "vision",
            })
        print(f"  [rooms] iš VISION: {len(rooms_input)}", file=sys.stderr)

    # ── 2.5: Scale auto-detection ────────────────────────────────────────
    scale_info = None
    try:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as _pdf:
                pdf_text = "\n".join(
                    (page.extract_text() or "")
                    for page in _pdf.pages[:5]
                )
        except Exception:
            pdf_text = ""
        scale_info = auto_detect_scale(
            pdf_bytes=pdf_bytes,
            pdf_text=pdf_text,
            rooms=rooms_input,
        )
        print(f"  [scale] 1:{scale_info['scale_ratio']} "
              f"({scale_info['confidence']}, src={scale_info['source']})",
              file=sys.stderr)
    except Exception as e:
        print(f"  [scale] klaida: {e}", file=sys.stderr)

    if rooms_input:
        avg_h = sum(r.get("lubu_aukstis_m") or 2.82 for r in rooms_input) / len(rooms_input)
    else:
        avg_h = 2.82

    # ── 2.7: V9 Symbol detection (60s timeout) ───────────────────────────
    detected_symbols_result = None
    try:
        sym_pages = [
            {"page": p.get("page"), "type": p.get("type", "unknown")}
            for p in (page_classifications or [])
        ]
        detected_symbols_result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: detect_all_symbols_for_pdf(
                    pdf_bytes=pdf_bytes,
                    page_classifications=sym_pages,
                    max_pages_per_type=1,
                ),
            ),
            timeout=SYMBOL_DETECTION_TIMEOUT_S,
        )
        if detected_symbols_result and detected_symbols_result.get("by_type"):
            detected_summary = {
                k: v.get("total", 0)
                for k, v in detected_symbols_result["by_type"].items()
                if v.get("total", 0) > 0
            }
            print(f"  [syms] {len(detected_summary)} tipų: {detected_summary}",
                  file=sys.stderr)
    except asyncio.TimeoutError:
        print(f"  [syms] TIMEOUT (>{SYMBOL_DETECTION_TIMEOUT_S}s) — fallback vidurkiai",
              file=sys.stderr)
        detected_symbols_result = None
    except Exception as e:
        print(f"  [syms] skip: {e}", file=sys.stderr)
        detected_symbols_result = None

    # ── 3: V8 universal engine ────────────────────────────────────────────
    v8 = extract_v8(
        rooms_input,
        ceiling_height_m=avg_h,
        rules_override=user_rules,
        detected_symbols=detected_symbols_result,
    )
    totals = v8["totals"]

    # ── 4: V5 pasiūlymas generation ───────────────────────────────────────
    v5_patalpos = []
    for r in rooms_input:
        v5_patalpos.append({
            "nr": r.get("nr"),
            "pavadinimas": r.get("pavadinimas"),
            "paskirtis": r.get("paskirtis"),
            "plotas_m2": r.get("plotas_m2"),
            "perimetras_m": r.get("perimetras_m", 0),
            "lubu_aukstis_m": r.get("lubu_aukstis_m", 2.82),
            "lubu_tipas": "gkp",
        })
    extracted_for_pasiulymas = {
        "patalpos": v5_patalpos,
        "durys": ai_result.get("durys", []),
        "langai": ai_result.get("langai", []),
        "nisos": ai_result.get("nisos", []),
        "lubu_aukstis_mm": int(avg_h * 1000),
        "archetipas": ai_result.get("archetipas", "standart"),
    }
    pasiul = generate_pasiulymas(extracted_for_pasiulymas)

    # Override with V8 universal numbers
    v8_overrides = {
        "GKP montavimas ant lubų (standart aukščio)": totals.get("gkp_lubu_standart_m2", 0),
        "GKP montavimas ant lubų (virš 3m, atvira erdvė)": totals.get("gkp_lubu_virs_3m_m2", 0),
        "Sienų, lubų glaistymas/dažymas": totals.get("dazymo_plotas_m2", 0),
        "Dažymo kampų montavimas": totals.get("kampai_m", 0),
        "PVC grindų įrengimas (ne eglute)": totals.get("pvc_grindys_m2", 0),
        "Plytelių klijavimas ant sienų ir grindų (standartinio formato)": (
            totals.get("plyteles_grindys_m2", 0) + totals.get("plyteles_sienos_m2", 0)
        ),
        "Hidroizoliacijos įrengimas": totals.get("hidroizoliacijos_vnt", 0),
        "Grindjuosčių montavimas": totals.get("grindjuostes_m", 0),
    }
    for it in pasiul.get("darbu_sarasas", []):
        nm = it.get("aprasymas", "")
        if nm in v8_overrides:
            new_val = v8_overrides[nm]
            if new_val and new_val > 0:
                it["kiekis"] = round(new_val, 2)
                it["v8_atnaujinta"] = True

    # Fill trace_type / trace_links
    try:
        for it in pasiul.get("darbu_sarasas", []):
            if "trace_type" in it:
                continue
            tt = _classify_trace_type(
                it.get("aprasymas", ""), it.get("mato_vnt", "")
            )
            it["trace_type"] = tt
            it["trace_links"] = _build_trace_links(
                {"aprasymas": it.get("aprasymas", ""), "vnt": it.get("mato_vnt", "")},
                v8["rooms"],
                detected_symbols_result,
                tt,
            )
            if tt == "formula":
                it["formula_explanation"] = _explain_formula(
                    {"aprasymas": it.get("aprasymas", ""), "kiekis": it.get("kiekis", 0)},
                    totals,
                )
    except Exception as e:
        print(f"  [trace] fill skip: {e}", file=sys.stderr)

    # Add V8 additional positions
    additional = v8.get("additional_positions", [])
    if additional:
        existing_aprasymai = {
            it.get("aprasymas", "").lower() for it in pasiul.get("darbu_sarasas", [])
        }
        max_eil = max(
            (int(it.get("eil_nr", 0) or 0) for it in pasiul.get("darbu_sarasas", [])),
            default=0,
        )
        next_nr = max_eil + 1
        for ap in additional:
            if ap["aprasymas"].lower() in existing_aprasymai:
                continue
            pasiul["darbu_sarasas"].append({
                "eil_nr": next_nr,
                "skyrius": ap["kategorija"],
                "aprasymas": ap["aprasymas"],
                "mato_vnt": ap["vnt"],
                "kiekis": ap["kiekis"],
                "kaina": 0,
                "suma": 0,
                "v8_industries_standart": True,
                "source": ap.get("source"),
                "confidence": ap.get("confidence", "medium"),
                "detected": ap.get("detected", False),
                "trace_type": ap.get("trace_type"),
                "trace_links": ap.get("trace_links", []),
                "formula_explanation": ap.get("formula_explanation"),
            })
            next_nr += 1

    # V3-style skaiciavimai overrides
    pasiul["skaiciavimai"]["dazomas_plotas"]["sienos_m2"] = round(
        max(0, totals.get("dazymo_plotas_m2", 0) - totals.get("gkp_lubu_standart_m2", 0)
              - totals.get("gkp_lubu_virs_3m_m2", 0)), 1,
    )
    pasiul["skaiciavimai"]["dazomas_plotas"]["lubos_m2"] = round(
        totals.get("gkp_lubu_standart_m2", 0) + totals.get("gkp_lubu_virs_3m_m2", 0), 2,
    )
    pasiul["skaiciavimai"]["dazomas_plotas"]["viso_m2"] = round(
        totals.get("dazymo_plotas_m2", 0), 1,
    )
    pasiul["skaiciavimai"]["dazomas_plotas"]["confidence"] = "v8_universal"
    pasiul["skaiciavimai"]["glaistymo_kampai"]["viso_m"] = round(
        totals.get("kampai_m", 0), 1,
    )
    pasiul["skaiciavimai"]["grindjuostes"]["viso_m"] = round(
        totals.get("grindjuostes_m", 0), 1,
    )

    # LT sanity validation
    lt_validation: dict = {"warnings": [], "summary": {}}
    try:
        lt_validation = lt_validate_rooms(v8["rooms"])
    except Exception as e:
        print(f"  [lt_san] klaida: {e}", file=sys.stderr)

    # Assemble final response — matches main.py /extract-interior-v8 return exactly
    pasiul["status"] = "ok"
    pasiul["v8_engine"] = True
    pasiul["v8_totals"] = totals
    pasiul["v8_rooms"] = v8["rooms"]
    pasiul["v8_scale"] = scale_info
    pasiul["v8_pages"] = page_classifications
    pasiul["v8_pages_summary"] = pages_summary
    pasiul["v8_archetipas"] = ai_result.get("archetipas")
    pasiul["interior_subtype"] = "naujas"
    pasiul["lt_sanity"] = lt_validation
    pasiul["detected_symbols"] = detected_symbols_result
    pasiul["detected_symbols_summary"] = v8.get("detected_symbols_summary", {})
    pasiul["projekto_info"] = {
        "bendras_plotas_m2": totals.get("bendras_plotas_m2", 0),
        "patalpu_skaicius": len(v8["rooms"]),
        "patalpu_saltinis": "eksplikacija" if eksplikacija_rooms else "vision",
        "duru_skaicius": len(ai_result.get("durys", [])),
        "langu_skaicius": len(ai_result.get("langai", [])),
        "nisu_skaicius": len(ai_result.get("nisos", [])),
        "ai_detected_symbol_types": len(v8.get("detected_symbols_summary") or {}),
    }
    return pasiul


# ---------------------------------------------------------------------------
# Orchestrator — spawns one subprocess per project
# ---------------------------------------------------------------------------

def run_project_subprocess(n: int) -> tuple[dict, float]:
    """Run project N in a subprocess and return (result_dict, elapsed_s)."""
    t0 = time.time()
    try:
        proc = subprocess.run(
            [VENV_PYTHON, __file__, "--worker", str(n)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max per project
            cwd=str(ROOT),
        )
        elapsed = round(time.time() - t0, 1)
        # Print worker stderr (progress messages) to our stdout
        if proc.stderr.strip():
            for line in proc.stderr.strip().split("\n"):
                print(f"  {line}")
        if proc.returncode != 0 and not proc.stdout.strip():
            return {
                "status": "error",
                "_error": f"worker exited {proc.returncode}: {proc.stderr[-500:]}",
            }, elapsed
        # Last non-empty line of stdout is the JSON result
        lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
        if not lines:
            return {"status": "error", "_error": "worker produced no output"}, elapsed
        # The last line should be the full JSON (worker may have other prints)
        # Try from last line backward
        result = None
        for line in reversed(lines):
            try:
                result = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if result is None:
            return {
                "status": "error",
                "_error": f"could not parse JSON from worker output: {proc.stdout[-500:]}",
            }, elapsed
        return result, elapsed
    except subprocess.TimeoutExpired:
        return {"status": "error", "_error": "worker timeout (>600s)"}, round(time.time() - t0, 1)
    except Exception as exc:
        return {"status": "error", "_error": str(exc)}, round(time.time() - t0, 1)


def extract_metrics(result: dict) -> dict:
    """Pull the key numbers from a V8 output dict."""
    totals = result.get("v8_totals") or {}
    skaiciavimai = result.get("skaiciavimai") or {}
    pinfo = result.get("projekto_info") or {}
    daz_obj = skaiciavimai.get("dazomas_plotas") or {}
    return {
        "rooms": pinfo.get("patalpu_skaicius") or len(result.get("v8_rooms") or []),
        "bendras_plotas_m2": pinfo.get("bendras_plotas_m2") or totals.get("bendras_plotas_m2"),
        "dazymo_total_m2": daz_obj.get("viso_m2") or totals.get("dazymo_plotas_m2"),
        "kampai_m": totals.get("kampai_m"),
        "plyteles_sienos_m2": totals.get("plyteles_sienos_m2"),
        "patalpu_saltinis": pinfo.get("patalpu_saltinis", "?"),
        "lt_warnings": len((result.get("lt_sanity") or {}).get("warnings") or []),
        "error": result.get("_error"),
    }


def main():
    print("=" * 60)
    print("V8 BASELINE CAPTURE — P1..P5  (subprocess isolation)")
    print("=" * 60)

    summary = []

    for n in range(1, 6):
        print(f"\n{'=' * 40}")
        print(f"  PROJECT P{n}")
        pdf_path = find_breziniai_pdf(n)
        if pdf_path:
            print(f"  PDF: {pdf_path.name}")
        else:
            print(f"  PDF: NOT FOUND in training-data/projektas_{n}/")
        print(f"{'=' * 40}")

        result, elapsed = run_project_subprocess(n)
        result["_elapsed_s"] = elapsed

        out_file = OUT / f"V8_P{n}.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"  -> saved {out_file.name}")

        metrics = extract_metrics(result)
        row = {
            "project": f"P{n}",
            "rooms": metrics["rooms"],
            "bendras_plotas_m2": metrics["bendras_plotas_m2"],
            "dazymo_total_m2": metrics["dazymo_total_m2"],
            "kampai_m": metrics["kampai_m"],
            "plyteles_sienos_m2": metrics["plyteles_sienos_m2"],
            "saltinis": metrics["patalpu_saltinis"],
            "lt_warnings": metrics["lt_warnings"],
            "elapsed_s": elapsed,
            "error": metrics["error"],
        }
        summary.append(row)

        if row["error"]:
            print(f"  KLAIDA: {row['error']}")
        else:
            print(
                f"  SUMMARY: rooms={row['rooms']} "
                f"plotas={row['bendras_plotas_m2']}m² "
                f"dažymas={row['dazymo_total_m2']}m² "
                f"kampai={row['kampai_m']}m "
                f"plytelės={row['plyteles_sienos_m2']}m² "
                f"t={elapsed}s src={row['saltinis']}"
            )

    # ── Write V8_BASELINE.md ──────────────────────────────────────────────
    md_lines = [
        "# V8 Baseline — THE BAR for new pipeline",
        "",
        "> This file was auto-generated by `backend/scripts/run_v8_baseline.py`.",
        "> It records what the CURRENT V8 pipeline produces for P1..P5.",
        "> Any new simplified pipeline MUST match or beat these numbers in Phase 3.",
        "> See individual `V8_PN.json` for full per-project detail.",
        "",
        f"Captured: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## V8 Captured Metrics",
        "",
        "| P# | Rooms | Bendras m² | Dažymo m² | Kampai m | Plytelės sienos m² | Šaltinis | t(s) | Klaida? |",
        "|----|-------|------------|-----------|----------|--------------------|----------|------|---------|",
    ]
    for r in summary:
        err_str = "KLAIDA" if r["error"] else ""
        md_lines.append(
            f"| {r['project']} "
            f"| {r['rooms'] if not r['error'] else 'ERR'} "
            f"| {r['bendras_plotas_m2'] if not r['error'] else 'ERR'} "
            f"| {r['dazymo_total_m2'] if not r['error'] else 'ERR'} "
            f"| {r['kampai_m'] if not r['error'] else 'ERR'} "
            f"| {r['plyteles_sienos_m2'] if not r['error'] else 'ERR'} "
            f"| {r['saltinis'] if not r['error'] else 'ERR'} "
            f"| {r['elapsed_s']} "
            f"| {err_str} |"
        )

    md_lines += [
        "",
        "## Manual review needed — Ground truth (rangovo's proposals)",
        "",
        "For each project, open `training-data/projektas_N/projektas_N_pasiulymas.pdf`",
        "(rangovo's actual proposal) and fill in the ground truth columns below.",
        "Then compute Δ% = (V8 - rangovo) / rangovo × 100 per metric.",
        "The worst-case Δ here becomes the threshold the new pipeline must match.",
        "",
        "| P# | rangovo rooms | rangovo bendras m² | rangovo dažymo m² | rangovo plytelės sienos m² | Δ% dažymas | Δ% plytelės |",
        "|----|-----------|-----------------|----------------|------------------------|------------|-------------|",
        "| P1 | _TODO_    | _TODO_          | _TODO_         | _TODO_                 | _TODO_     | _TODO_      |",
        "| P2 | _TODO_    | _TODO_          | _TODO_         | _TODO_                 | _TODO_     | _TODO_      |",
        "| P3 | _TODO_    | _TODO_          | _TODO_         | _TODO_                 | _TODO_     | _TODO_      |",
        "| P4 | _TODO_    | _TODO_          | _TODO_         | _TODO_                 | _TODO_     | _TODO_      |",
        "| P5 | _TODO_    | _TODO_          | _TODO_         | _TODO_                 | _TODO_     | _TODO_      |",
        "",
        "## Key fields in JSON for Phase 3 comparison",
        "",
        "- `v8_totals.dazymo_plotas_m2` — total paintable area",
        "- `v8_totals.kampai_m` — corner bead linear meters",
        "- `v8_totals.plyteles_sienos_m2` — wall tile area",
        "- `v8_totals.plyteles_grindys_m2` — floor tile area",
        "- `v8_totals.bendras_plotas_m2` — total floor area",
        "- `v8_totals.gkp_lubu_standart_m2` — drywall ceiling area",
        "- `projekto_info.patalpu_skaicius` — rooms detected",
        "- `projekto_info.patalpu_saltinis` — `eksplikacija` (better) or `vision` (fallback)",
        "- `skaiciavimai.dazomas_plotas.viso_m2` — V8-overridden paintable area",
        "- `lt_sanity.warnings` — data quality proxy (more = less reliable output)",
        "",
        "## Error log",
        "",
    ]
    has_errors = False
    for r in summary:
        if r["error"]:
            has_errors = True
            md_lines.append(f"- **{r['project']}**: {r['error']}")
    if not has_errors:
        md_lines.append("No errors — all 5 projects completed successfully.")

    baseline_md = OUT / "V8_BASELINE.md"
    baseline_md.write_text("\n".join(md_lines) + "\n")
    print(f"\nBaseline MD: {baseline_md}")

    # Final console table
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"{'P#':<4} {'Rooms':<6} {'Plotas':>8} {'Dažymas':>9} {'Kampai':>8} {'Plytelės':>10} {'t(s)':>6}")
    for r in summary:
        if r["error"]:
            print(f"{r['project']:<4} ERROR: {r['error'][:55]}")
        else:
            print(
                f"{r['project']:<4} "
                f"{str(r['rooms']):<6} "
                f"{str(r['bendras_plotas_m2']):>8} "
                f"{str(r['dazymo_total_m2']):>9} "
                f"{str(r['kampai_m']):>8} "
                f"{str(r['plyteles_sienos_m2']):>10} "
                f"{str(r['elapsed_s']):>6}"
            )


# ---------------------------------------------------------------------------
# Entry point — supports both orchestrator mode (no args) and worker mode
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--worker" in sys.argv:
        idx = sys.argv.index("--worker")
        n = int(sys.argv[idx + 1])
        worker_main(n)
    else:
        main()

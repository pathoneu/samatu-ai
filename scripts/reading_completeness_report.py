"""Reading completeness (Pathon v3 W5-D) on the corpus, printed by codename — a report for eyes, not a test.

The corpus PDFs and frozen extracts are confidential and untracked (docs/superpowers/fixtures/, ground_truth/);
nothing here may become a fixture. Texts are cut to 40 characters and can be hidden with --no-labels.

    venv/bin/python scripts/reading_completeness_report.py floor-legend            # D1
    venv/bin/python scripts/reading_completeness_report.py legend-zones            # D2 + title-zone matches
    venv/bin/python scripts/reading_completeness_report.py columns                 # (c) multi-column legend rows
    venv/bin/python scripts/reading_completeness_report.py sheet-types             # D12
    venv/bin/python scripts/reading_completeness_report.py areas                   # D13
    venv/bin/python scripts/reading_completeness_report.py dimlen objektas_h       # D8
    venv/bin/python scripts/reading_completeness_report.py tags                    # D10 schedule tags on the plan
"""
from __future__ import annotations

import argparse
import collections
import copy
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import yaml  # noqa: E402

CORE = ("objektas_a", "objektas_b", "objektas_c", "objektas_d", "objektas_g", "objektas_h")
NO_LABELS = False


def _codename(entry: dict) -> str:
    slug = str(entry.get("slug") or "")
    if slug.startswith("objektas_"):
        return slug
    return str(entry.get("name") or slug).strip().lower().replace(" ", "_")


def _txt(s) -> str:
    return "" if NO_LABELS else str(s or "")[:40]


def corpus(wanted: list[str]):
    """(codename, pdf bytes, frozen extract or None) per project on disk."""
    reg = yaml.safe_load((REPO / "ground_truth" / "registry.yaml").read_text())
    entries = {e["slug"]: e for e in reg.get("projects") or []}
    by_code = {_codename(e): e for e in entries.values()}
    for want in wanted or list(CORE):
        entry = entries.get(want) or by_code.get(want)
        if not entry:
            print(f"{want}: not in the registry")
            continue
        code = _codename(entry)
        pdf_path = REPO / str(entry.get("project_pdf") or "")
        if not pdf_path.is_file():
            print(f"{code}: PDF not on disk (copy the untracked fixtures into this checkout)")
            continue
        extract = None
        ai = REPO / "ground_truth" / str(entry["slug"]) / "ai_extract.json"
        if ai.is_file():
            extract = json.loads(ai.read_text())
        yield code, pdf_path.read_bytes(), extract


def _pages(pdf: bytes) -> int:
    import pypdfium2 as pdfium
    from extractor.pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf)
        n = len(doc)
        doc.close()
    return n


# ── D1 ───────────────────────────────────────────────────────────────────────

def floor_legend(projects: list[str]) -> None:
    from extractor.geometry_lane import apply_geometry
    from extractor.room_facts import build_room_facts
    for code, pdf, extract in corpus(projects):
        if not extract:
            print(f"{code}: no frozen extract")
            continue
        parsed = copy.deepcopy(extract)
        t0 = time.time()
        apply_geometry(parsed, pdf)
        lines = (parsed.get("_meta") or {}).get("grindu_legenda")
        sheets = ((parsed.get("_meta") or {}).get("geometrija") or {}).get("grindu_dangos", {}).get("lapai")
        print(f"== {code}: floor sheets {sheets}, key lines {None if lines is None else len(lines)} ({time.time() - t0:.1f}s)")
        for ln in lines or []:
            print(f"    p{ln['page']} {ln['klase']:<9} {ln['spalva']}  {_txt(ln['tekstas'])}")
        with_key = read = 0
        for r in parsed.get("patalpos") or []:
            if not r.get("nr") or r.get("_sujungta_i"):
                continue
            facts = build_room_facts(parsed, str(r["nr"])).get("facts") or []
            f = next((x for x in facts if x["key"] == "grindys"), None)
            if f and f["source"]["kind"] == "grindu_planas":
                read += 1
                if f.get("legenda"):
                    with_key += 1
                    print(f"    room {r['nr']}: {_txt(f['legenda']['sentence'])}")
        print(f"   floor facts read off the plan: {read}, with a key line beside them: {with_key}")


# ── D2 + title zones ─────────────────────────────────────────────────────────

def legend_zones(projects: list[str]) -> None:
    from extractor import legend_rows as lr
    from extractor import vector_symbols as vs
    for code, pdf, _ in corpus(projects):
        n = _pages(pdf)
        rows = []
        for p in range(1, n + 1):
            for leg in lr.suggest_legend_rows(pdf, p)["legends"]:
                rows.extend(r for r in leg["rows"] if r.get("countable") and r.get("glyph_kind") == "spalvotas")
        res = vs.count_glyph_instances_many(pdf, rows, time_budget_s=120.0) if rows else []
        listed = sum(len(a.get("uz_zonu") or []) for a in res)
        print(f"== {code}: {len(rows)} countable rows, {sum(a['count'] for a in res)} instances, "
              f"{listed} matches inside legenda / lentele / antspaudas listed without a mark")
        for r, a in zip(rows, res):
            if a.get("uz_zonu"):
                kinds = collections.Counter(x["zona"] for x in a["uz_zonu"])
                print(f"    p{r['page']} {a['count']:>4} kept, outside the plan: {dict(kinds)}  {_txt(r['text'])}")


# ── (c) legend rows per codename ─────────────────────────────────────────────

def columns(projects: list[str]) -> None:
    """Legend rows per sheet, with the rows whose glyph holds a letter (W5-D (c)) listed."""
    from extractor import legend_rows as lr
    for code, pdf, _ in corpus(projects):
        n = _pages(pdf)
        total = 0
        per = []
        for p in range(1, n + 1):
            k = 0
            for leg in lr.suggest_legend_rows(pdf, p)["legends"]:
                k += len(leg["rows"])
                for r in leg["rows"]:
                    if r["glyph_kind"] == "tekstas":
                        print(f"    p{p} tekstas „{r['glyph_text']}“  {_txt(r['text'])}")
            if k:
                per.append(f"p{p}:{k}")
            total += k
        print(f"== {code}: {total} legend rows ({', '.join(per)})")


def main() -> int:
    global NO_LABELS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what")
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--no-labels", action="store_true")
    args = ap.parse_args()
    NO_LABELS = args.no_labels
    fn = {"floor-legend": floor_legend, "legend-zones": legend_zones, "columns": columns}.get(args.what)
    if fn is None:
        print(f"unknown report: {args.what}")
        return 2
    fn(args.projects)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

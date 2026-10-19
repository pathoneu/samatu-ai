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


# ── D12 ──────────────────────────────────────────────────────────────────────

def sheet_types(projects: list[str]) -> None:
    """Every sheet's zones; the sheets the zones alone call „legenda", beside what the paid reading called them."""
    from extractor import sheet_zones as sz
    for code, pdf, extract in corpus(projects):
        n = _pages(pdf)
        paid = {int(p.get("nr") or 0): p.get("tipas") for p in (extract or {}).get("puslapiai") or [] if isinstance(p, dict)}
        hits = []
        t0 = time.time()
        for p in range(1, n + 1):
            zones = sz.read_zones(pdf, p).get("zones") or []
            if sz.sheet_type_from_zones(zones) == "legenda":
                hits.append(f"p{p} (paid reading: {paid.get(p) or '—'}; zones {sorted(z['kind'] for z in zones)})")
        print(f"== {code}: {n} sheets, legend-only {len(hits)} ({time.time() - t0:.0f}s)")
        for h in hits:
            print(f"    {h}")


# ── D8 ───────────────────────────────────────────────────────────────────────

def dimlen(projects: list[str]) -> None:
    """Does a dimension string's evidence line (`span`, what `line_pct` is drawn from) include the stroke's caps?
    Per codename: the median of span − drawn length (`ilgis_pt`), and the line measured at the page's own scale
    against the written value — from the span and from the drawn length."""
    import statistics
    from extractor.plan_dimensions import read_dimension_strings
    for code, pdf, _ in corpus(projects):
        dims = [d for d in read_dimension_strings(pdf, pages=None)
                if d.get("span_source") == "line" and d.get("span") and d.get("ilgis_pt") and d.get("orientation") in ("h", "v")]
        if not dims:
            print(f"== {code}: no line-backed strings")
            continue
        caps = [abs(d["span"][1] - d["span"][0]) - float(d["ilgis_pt"]) for d in dims]
        by_span = [abs(d["span"][1] - d["span"][0]) * float(d["scale_m_per_pt"]) / d["value_m"] - 1 for d in dims]
        by_drawn = [float(d["ilgis_pt"]) * float(d["scale_m_per_pt"]) / d["value_m"] - 1 for d in dims]
        short = [r for d, r in zip(dims, by_span) if d["value_m"] <= 1.0]
        pct = lambda v: f"{100 * v:+.1f} %"  # noqa: E731
        print(f"== {code}: {len(dims)} strings on {len({d['page'] for d in dims})} sheets — span − drawn length: median "
              f"{statistics.median(caps):.2f} pt (min {min(caps):.2f}, max {max(caps):.2f}); measured vs written: span "
              f"{pct(statistics.median(by_span))} (strings ≤ 1 m: {pct(statistics.median(short)) if short else '—'}), "
              f"drawn length {pct(statistics.median(by_drawn))}")


# ── D6 ───────────────────────────────────────────────────────────────────────

def figures(projects: list[str]) -> None:
    """The free re-read with SAMATU_REREAD_FIGURES off and on, on the STORED demo projects (backend/data/samatu.db,
    ids demo-<codename>): which rooms' heights the plan's own statements change, which anchors appear, and what
    the stored project already carries — the paid reading's step 2.44, brought to a stored project."""
    import os
    import sqlite3
    from api.free_reread import FIGURES_FLAG, read_drawing
    from storage import get_storage, pdf_key
    con = sqlite3.connect(REPO / "backend" / "data" / "samatu.db")
    for code in projects or ["objektas_g", "objektas_h"]:
        row = con.execute("select data from projects where id = ?", (f"demo-{code}",)).fetchone()
        if not row:
            print(f"{code}: no stored demo project")
            continue
        project = json.loads(row[0])
        project["id"] = f"demo-{code}"
        pdf = get_storage().get(pdf_key(f"demo-{code}"))
        runs = {}
        for flag in ("0", "1"):
            os.environ[FIGURES_FLAG] = flag
            runs[flag] = read_drawing(project, pdf)
        os.environ.pop(FIGURES_FLAG, None)
        off = {str(r.get("nr")): r for r in runs["0"]["patalpos"]}
        on = {str(r.get("nr")): r for r in runs["1"]["patalpos"]}
        changed = [(nr, off[nr].get("lubu_aukstis_m"), on[nr].get("lubu_aukstis_m")) for nr in on
                   if nr in off and off[nr].get("lubu_aukstis_m") != on[nr].get("lubu_aukstis_m")]
        hs = (runs["1"].get("_meta") or {}).get("plan_height_statement")
        print(f"== {code}: heights changed {len(changed)} {changed}; plan height statement {hs}")
        for key in ("_autoriaus_kiekiai", "_walls_anchor", "_floor_anchors"):
            got = runs["1"].get(key)
            stored = project.get(key)
            norm = lambda v: json.loads(json.dumps(v), parse_int=float)  # noqa: E731 — 320 and 320.0 are the same figure
            same = norm(got) == norm(stored)
            n = len(got) if isinstance(got, list) else (sorted(got) if isinstance(got, dict) else got)
            print(f"    {key}: flag on → {n if not isinstance(got, dict) or key != '_walls_anchor' else got.get('total_area_m2')}"
                  f"; stored project {'has the same' if same else ('has another' if stored else 'has none')}")
        assert all(k not in runs["0"] for k in ("_autoriaus_kiekiai", "_walls_anchor", "_floor_anchors"))


# ── D7 ───────────────────────────────────────────────────────────────────────

def zone_scales(projects: list[str]) -> None:
    """Sheets with two or more plan zones: per zone, how many dimension strings the page's ONE scale backs with a
    line, how many it leaves unbacked, and — for the unbacked — the scale their nearest hairline would give.
    A zone whose strings stay unbacked at one consistent other scale is a second viewport (D7's case)."""
    import statistics
    from extractor import sheet_zones as sz
    from extractor.plan_dimensions import read_dimension_strings
    for code, pdf, _ in corpus(projects):
        dims = read_dimension_strings(pdf, pages=None)
        by_page: dict[int, list[dict]] = collections.defaultdict(list)
        for d in dims:
            by_page[int(d["page"])].append(d)
        found = 0
        for page, ds in sorted(by_page.items()):
            zones = [z for z in sz.read_zones(pdf, page).get("zones") or [] if z.get("kind") == "planas"]
            if len(zones) < 2:
                continue
            found += 1
            W = float(ds[0].get("page_width") or 1)
            H = float(ds[0].get("page_height") or 1)
            parts = []
            for i, z in enumerate(zones):
                inside = [d for d in ds if sz.zone_at([z], ((d["bbox"][0] + d["bbox"][2]) / 2) / W, ((d["bbox"][1] + d["bbox"][3]) / 2) / H)]
                backed = [d for d in inside if d.get("span_source") == "line"]
                sc = [d["value_m"] / float(d["ilgis_pt"]) for d in backed if d.get("ilgis_pt")]
                parts.append(f"zone {i + 1}: {len(inside)} strings, {len(backed)} backed"
                             + (f" at 1:{round(statistics.median(sc) / (25.4 / 72 / 1000))}" if sc else ""))
            print(f"   {code} p{page}: " + "; ".join(parts))
        print(f"== {code}: {found} sheets with two or more plan zones")


def main() -> int:
    global NO_LABELS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what")
    ap.add_argument("projects", nargs="*")
    ap.add_argument("--no-labels", action="store_true")
    args = ap.parse_args()
    NO_LABELS = args.no_labels
    fn = {"floor-legend": floor_legend, "legend-zones": legend_zones, "columns": columns, "sheet-types": sheet_types, "dimlen": dimlen, "figures": figures, "zone-scales": zone_scales}.get(args.what)
    if fn is None:
        print(f"unknown report: {args.what}")
        return 2
    fn(args.projects)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

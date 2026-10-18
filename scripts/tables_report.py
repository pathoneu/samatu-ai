#!/usr/bin/env python3
"""Lentelių ataskaita — what the „lentelės" stage reads on each corpus drawing (Pathon v3 W3-A, 2026-10-18).

    venv/bin/python scripts/tables_report.py                       # every registry project with a PDF
    venv/bin/python scripts/tables_report.py objektas_d objektas_h # some
    venv/bin/python scripts/tables_report.py --questions           # + the free re-read on the cached extract
                                                                   #   and the schedule questions it raises

Zero API: the fixture PDFs and the cached extracts (ground_truth/<slug>/ai_extract.json), the same inputs
eval_harness --recompute uses. Prints per project, by its codename only: the sheets the text layer names a
table on, the ruled tables found per sheet, every schedule read (rows, rows with a box, sheets), the door
schedule scanner's reading (ruled cells or word positions), the seconds — and with --questions the
reconciliation questions a check sheet would ask. Never asserts, exit 0: the fixtures are untracked, so this
is a measuring stick, not a test. Text read off a drawing is masked against the confidential terms.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import yaml  # noqa: E402

from extractor import table_reader  # noqa: E402
from extractor.door_schedule import scan_door_schedule  # noqa: E402
from extractor.schedules import KINDS, candidate_pages, read_schedules  # noqa: E402
from extractor.sheet_zones import REREAD_TABLE_MAX_OBJECTS  # noqa: E402
from extractor.user_text import confidential_pattern  # noqa: E402

_MASK = confidential_pattern()


def _safe(text) -> str:
    s = " ".join(str(text or "").split())
    return _MASK.sub("•••", s) if _MASK else s


def _projects(want: list[str]) -> list[tuple[str, Path]]:
    reg = yaml.safe_load((ROOT / "ground_truth" / "registry.yaml").read_text(encoding="utf-8")) or {}
    out = []
    for e in reg.get("projects") or []:
        slug, pdf = e.get("slug"), e.get("project_pdf")
        if not slug or not pdf or (want and slug not in want) or e.get("blind"):
            continue
        path = ROOT / pdf
        if path.exists():
            out.append((slug, path))
    return out


def _questions(slug: str, pdf: bytes) -> list[dict] | None:
    extract = ROOT / "ground_truth" / slug / "ai_extract.json"
    if not extract.exists():
        return None
    from api.free_reread import read_drawing
    from extractor.project_questions import RECONCILE_KINDS, build_questions
    blob = json.loads(extract.read_text(encoding="utf-8"))
    got = read_drawing(copy.deepcopy(blob), pdf)
    merged = {**blob, "patalpos": got.get("patalpos") or blob.get("patalpos") or [], "_meta": got.get("_meta") or {}}
    for key in ("_duru_ziniarastis", "_vector_symbols", "_langu_ziniarastis", "_apdailos_lentele"):
        if isinstance(got.get(key), dict):
            merged[key] = got[key]
    return [q for q in build_questions(merged, lenteles=True)["questions"] if q["kind"] in RECONCILE_KINDS]


def report(slug: str, path: Path, with_questions: bool) -> dict:
    pdf = path.read_bytes()
    t0 = time.time()
    pages = candidate_pages(pdf)
    t_text = time.time() - t0
    t1 = time.time()
    res = read_schedules(pdf, pages, max_objects=REREAD_TABLE_MAX_OBJECTS)
    t_tables = time.time() - t1
    t2 = time.time()
    doors = scan_door_schedule(pdf)
    t_doors = time.time() - t2
    n_tables = sum(len(v) for v in res["lenteles"].values())
    print(f"\n{slug}: {len(pages)} sheet(s) name a table {pages[:12]}{' …' if len(pages) > 12 else ''}; "
          f"status {res['status']}; {n_tables} ruled table(s); text {t_text:.1f}s, tables {t_tables:.1f}s, "
          f"door scan {t_doors:.1f}s")
    if res.get("detail"):
        print(f"  detail: {_safe(res['detail'])}")
    for page, why in sorted(res["praleisti"].items(), key=lambda kv: int(kv[0])):
        print(f"  p{page} skipped: {_safe(why)}")
    for page, tables in sorted(res["lenteles"].items(), key=lambda kv: int(kv[0])):
        for t in tables:
            print(f"  p{page} {t['table_id']} {t['cols']} col × {len(t['rows'])} row  schedule={t.get('schedule')}  "
                  f"title={_safe(t.get('title'))[:50]!r}  header={[_safe(h)[:18] for h in t['header']]}")
    schedules = {}
    for kind in KINDS:
        s = res["ziniarasciai"].get(kind)
        if not s:
            continue
        boxed = sum(1 for r in s["rows"] if r.get("bbox_pct"))
        schedules[kind] = {"rows": len(s["rows"]), "boxed": boxed, "pages": s["pages"]}
        print(f"  SCHEDULE {kind}: {len(s['rows'])} row(s), {boxed} with a box, sheets {s['pages']}"
              f"{' (continued)' if s['tesinys'] else ''}; columns {sorted(s['columns'])}")
        for r in s["rows"][:6]:
            vals = {k: r.get(k) for k in ("kodas", "plotis_mm", "aukstis_mm", "tipas", "kiekis", "nr", "grindu_danga",
                                          "formatas_mm", "plotas_m2") if r.get(k) is not None}
            print(f"     p{r['page']} {[round(v, 3) for v in r['bbox_pct']] if r.get('bbox_pct') else None} {vals}")
        for tot in s.get("totals") or []:
            print(f"     total {tot['value']} m² ({_safe(tot.get('label'))})")
    lent = doors.get("lentele") or {}
    rows = lent.get("eilutes") or []
    print(f"  door scanner: status {doors['status']}, source {lent.get('saltinis')}, {len(rows)} row(s), "
          f"{sum(1 for r in rows if r.get('bbox_pct'))} with a box")
    out = {"slug": slug, "pages": pages, "tables": n_tables, "schedules": schedules, "doors": doors["status"],
           "door_source": lent.get("saltinis"), "seconds": round(t_text + t_tables + t_doors, 1)}
    if with_questions:
        t3 = time.time()
        qs = _questions(slug, pdf)
        if qs is None:
            print("  questions: no cached extract")
        else:
            print(f"  questions ({time.time() - t3:.1f}s): {len(qs)}")
            for q in qs:
                print(f"     {q['kind']}: {_safe(q['title'])}")
            out["questions"] = [q["kind"] for q in qs]
    return out


def main(argv: list[str]) -> int:
    with_questions = "--questions" in argv
    want = [a for a in argv if not a.startswith("--")]
    rows = []
    for slug, path in _projects(want):
        table_reader.clear()
        try:
            rows.append(report(slug, path, with_questions))
        except Exception as exc:  # noqa: BLE001 — a measuring stick reports, it does not stop
            print(f"\n{slug}: failed — {type(exc).__name__}: {exc}")
    print("\n── corpus ──")
    for r in rows:
        sched = ", ".join(f"{k} {v['rows']}/{v['boxed']} boxed" for k, v in r["schedules"].items()) or "none"
        q = f"; questions {r['questions']}" if "questions" in r else ""
        print(f"  {r['slug']:<28} tables {r['tables']:>3}  schedules: {sched}  doors {r['doors']}"
              f"{'/' + r['door_source'] if r['door_source'] else ''}  {r['seconds']}s{q}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

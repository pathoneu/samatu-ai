"""Legend rows and symbol counts (backend/extractor/legend_rows.py, vector_symbols.count_glyph_instances_many,
cv_match.batch_find_symbol) on every corpus project, printed by codename.

Non-asserting: a report for eyes, not a test — the corpus PDFs are confidential and untracked
(docs/superpowers/fixtures/, see ground_truth/registry.yaml), so nothing here may become a fixture. Row texts
are cut to 40 characters and can be hidden with --no-labels. Counts the person verified by eye are given on
the command line (`--eye objektas_h=9`), never written into the repository.

Per project:
  1. every sheet's `legenda` zones (sheet_zones) → the rows found in each, by kind;
  2. the coloured rows counted from the paths on every sheet carrying their legend: count per sheet;
  3. the diffusers: the old entry (count_legend_symbols) beside the generalised one — rows whose text says
     „difuzorius", from the zones or, where no zone holds them, from a box drawn round the label the way a
     person would — and the eye count when given;
  4. with --raster: the shape search for each diffuser row over its legend sheets, scored against the
     vector instances (the truth there): best true score, best false score, the floor kept, true / false kept.

    venv/bin/python scripts/legend_count_report.py                      # the core corpus
    venv/bin/python scripts/legend_count_report.py objektas_h --raster --eye objektas_h=9
"""
from __future__ import annotations

import argparse
import collections
import io
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import yaml  # noqa: E402

from extractor import legend_rows as lr  # noqa: E402
from extractor import sheet_zones as sz  # noqa: E402
from extractor import vector_symbols as vs  # noqa: E402

CORE = ("objektas_a", "objektas_b", "objektas_c", "objektas_d", "objektas_g", "objektas_h")


def _codename(entry: dict) -> str:
    slug = str(entry.get("slug") or "")
    if slug.startswith("objektas_"):
        return slug
    return str(entry.get("name") or slug).strip().lower().replace(" ", "_")


def _label_boxes(pdf: bytes) -> dict[int, list[list[float]]]:
    """Display-fraction boxes a person would draw round each diffuser legend label (90 pt left of the label
    for the symbol, 250 pt right for the text), per page — for sheets whose legend no zone holds."""
    import hashlib

    import pdfplumber
    out: dict[int, list[list[float]]] = collections.defaultdict(list)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        texts = vs._folded_texts(pdf, hashlib.blake2b(pdf, digest_size=16).digest(), list(range(1, len(doc.pages) + 1)))
        for i, page in enumerate(doc.pages, start=1):
            if "difuzori" not in texts.get(i, ""):
                continue
            try:
                words = page.extract_words()
            except Exception:  # noqa: BLE001
                continue
            W, H = float(page.width), float(page.height)
            for w in words:
                if vs.DIFFUSER_LABEL_RE.search(w["text"]):
                    cy = (w["top"] + w["bottom"]) / 2
                    out[i].append([max(0.0, (w["x0"] - 150) / W), max(0.0, (cy - 9) / H),
                                   min(1.0, (w["x1"] + 200) / W), min(1.0, (cy + 9) / H)])
            page.close()
    return out


def _centre_in(box, inst_boxes, pad=0.003) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return any(b[0] - pad <= cx <= b[2] + pad and b[1] - pad <= cy <= b[3] + pad for b in inst_boxes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects", nargs="*", help="codenames or registry slugs (default: the core corpus)")
    ap.add_argument("--no-labels", action="store_true")
    ap.add_argument("--raster", action="store_true", help="also measure the shape search on the diffuser rows")
    ap.add_argument("--eye", default="", help="comma-separated codename=count the person verified by eye")
    args = ap.parse_args()
    eye = {k.strip(): int(v) for k, v in (p.split("=") for p in args.eye.split(",") if "=" in p)}

    reg = yaml.safe_load((REPO / "ground_truth" / "registry.yaml").read_text())
    entries = {e["slug"]: e for e in reg.get("projects") or []}
    by_code = {_codename(e): e for e in entries.values()}
    for want in args.projects or list(CORE):
        entry = entries.get(want) or by_code.get(want)
        if not entry:
            print(f"{want}: not in the registry")
            continue
        code = _codename(entry)
        pdf_path = REPO / str(entry.get("project_pdf") or "")
        if not pdf_path.is_file():
            print(f"{code}: PDF not on disk (copy the untracked fixtures into this checkout)")
            continue
        pdf = pdf_path.read_bytes()
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf)
        n = len(doc)
        doc.close()
        t0 = time.time()
        rows: list[dict] = []
        kinds: collections.Counter = collections.Counter()
        for p in range(1, n + 1):
            sug = lr.suggest_legend_rows(pdf, p)
            for leg in sug["legends"]:
                k = collections.Counter(r["glyph_kind"] for r in leg["rows"])
                kinds.update(k)
                label = "" if args.no_labels or not leg.get("label") else f" „{leg['label'][:30]}“"
                print(f"{code} p{p} legenda{label}: {len(leg['rows'])} rows "
                      f"({', '.join(f'{kk} {vv}' for kk, vv in sorted(k.items())) or '—'})"
                      + (f" — {leg['detail']}" if leg.get("detail") else ""))
                rows.extend(leg["rows"])
        t_rows = time.time() - t0
        print(f"== {code}: {n} sheets, {len(rows)} legend rows ({dict(kinds)}) in {t_rows:.1f}s")

        coloured = [r for r in rows if r["glyph_kind"] == "spalvotas" and r["countable"]]
        t1 = time.time()
        res = vs.count_glyph_instances_many(pdf, coloured, time_budget_s=120.0) if coloured else []
        t_count = time.time() - t1
        for r, a in zip(coloured, res):
            name = "" if args.no_labels else r["text"][:40]
            pp = ", ".join(f"p{x['page']}:{x['count']}{'(kart.)' if x['kartojasi'] else ''}"
                           f"{'' if x['legenda_lape'] else '(be leg.)'}" for x in a["per_page"])
            print(f"    p{r['page']} {a['status']:<10} {a['count']:>4}  [{pp or '—'}]"
                  f"{' PARTIAL' if a['partial'] else ''}  {name}")
        print(f"   coloured rows counted: {len(coloured)} in {t_count:.1f}s")

        # 3. diffusers: old entry vs generalised vs eye
        t2 = time.time()
        old = vs.count_legend_symbols(pdf)
        t_old = time.time() - t2
        dif = [(r, a) for r, a in zip(coloured, res) if vs.DIFFUSER_LABEL_RE.search(r["text"])]
        src = "zones"
        if not dif:
            boxed = []
            for p, boxes in _label_boxes(pdf).items():
                for b in boxes:
                    boxed += [r for r in lr.split_legend_rows(pdf, p, b)["rows"]
                              if r["glyph_kind"] == "spalvotas" and vs.DIFFUSER_LABEL_RE.search(r["text"])]
            seen, uniq = set(), []
            for r in boxed:
                if r["row_id"] not in seen:
                    seen.add(r["row_id"])
                    uniq.append(r)
            dif = list(zip(uniq, vs.count_glyph_instances_many(pdf, uniq, time_budget_s=120.0))) if uniq else []
            src = "drawn boxes"
        new_total = sum(a["count"] for _r, a in dif)
        print(f"   diffusers: old entry {old['count']} ({t_old:.1f}s) | generalised {new_total} from {len(dif)} rows "
              f"({src}) | eye {eye.get(code, '—')}")

        # 4. the shape search measured against the vector instances
        if args.raster:
            from extractor.cv_match import batch_find_symbol
            from extractor.sheet_zones import zone_to_mediabox_pt
            from extractor.cv_match import _mediabox_geometry
            geo = _mediabox_geometry(pdf)
            for r, a in dif:
                pages = sorted({x["page"] for x in a["per_page"] if not x["kartojasi"]}) or [r["page"]]
                w, h, rot = geo[r["page"] - 1]
                b = zone_to_mediabox_pt({"bbox_pct": r["glyph_bbox_pct"]}, (w, h), rot)
                box = [b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1]
                t3 = time.time()
                s = batch_find_symbol(pdf, r["page"], box, pages, time_budget_s=120.0)
                truth = collections.defaultdict(list)
                for i in a["instances"]:
                    truth[i["page"]].append(i["box_pct"])
                best_t = best_f = None
                raw_t = raw_f = kept_t = kept_f = 0
                for e in s["pages"]:
                    for c in [c for c in e["candidates"] if not c["is_source"]]:
                        ok = _centre_in(c["box_pct"], truth[e["page"]])
                        kept_t += ok
                        kept_f += not ok
                # the scores before the floor: re-run with margin 1 (keeps everything ≥ min_score)
                s_all = batch_find_symbol(pdf, r["page"], box, pages, margin=1.0, max_per_page=300, time_budget_s=120.0)
                t_scores: list[float] = []
                f_scores: list[float] = []
                for e in s_all["pages"]:
                    for c in [c for c in e["candidates"] if not c["is_source"]]:
                        ok = _centre_in(c["box_pct"], truth[e["page"]])
                        if ok:
                            raw_t += 1
                            best_t = max(best_t or 0, c["score"])
                            t_scores.append(c["score"])
                        else:
                            raw_f += 1
                            best_f = max(best_f or 0, c["score"])
                            f_scores.append(c["score"])
                name = "" if args.no_labels else r["text"][:30]
                print(f"   raster p{r['page']} {name}: vector {a['count']} | ≥min_score true {raw_t} false {raw_f} | "
                      f"best true {best_t} best false {best_f} | floor {s['score_floor']} kept true {kept_t} false {kept_f}"
                      f" | {time.time() - t3:.1f}s{' PARTIAL' if s['partial'] else ''}")
                print(f"      true scores {sorted(t_scores, reverse=True)} | best false {sorted(f_scores, reverse=True)[:6]}")
            # black rows have no truth here: the score ranks on their own legend sheet show the separation
            for r in [r for r in rows if r["glyph_kind"] == "juodas" and r["countable"]][:3]:
                w, h, rot = geo[r["page"] - 1]
                b = zone_to_mediabox_pt({"bbox_pct": r["glyph_bbox_pct"]}, (w, h), rot)
                box = [b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1]
                t4 = time.time()
                s = batch_find_symbol(pdf, r["page"], box, [r["page"]], time_budget_s=120.0)
                s_all = batch_find_symbol(pdf, r["page"], box, [r["page"]], margin=1.0, max_per_page=300, time_budget_s=120.0)
                kept = sum(1 for e in s["pages"] for c in e["candidates"] if not c["is_source"])
                scores = sorted((c["score"] for e in s_all["pages"] for c in e["candidates"] if not c["is_source"]), reverse=True)
                ranks = {k: scores[k - 1] for k in (1, 2, 3, 5, 10, 20, 50) if len(scores) >= k}
                name = "" if args.no_labels else r["text"][:30]
                print(f"   raster black p{r['page']} {name}: {s['status']} ≥min_score {len(scores)} | ranks {ranks} | "
                      f"floor {s['score_floor']} kept {kept} | {time.time() - t4:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

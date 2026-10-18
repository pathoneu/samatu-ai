"""Which sheets do the readers place differently once the display frame comes from the page (2026-10-18)?

Non-asserting: a report for eyes, not a test — the corpus PDFs are confidential and untracked
(docs/superpowers/fixtures/, ground_truth/registry.yaml), so nothing here may become a fixture. Projects are
printed by CODENAME only.

What is compared, per project and sheet:
  walls      pdf_vectors.page_geometry (the frame) and pdf_vectors.wall_fills (each fill's bounds)
  text       plan_area_annotations._iter_pages (one frame per text direction) and every word, in the display
             frame (`to_display`)
  dimensions plan_dimensions.read_dimension_strings — the strings AND the hairlines under them (a string whose
             line is read in another frame loses it: `backed` counts the strings with `span_source == "line"`)
  outlines   the geometry lane (geometry_lane.apply_geometry, on the frozen extract after the eval's
             `_undo_lane_state`) — room outlines per sheet

A position is "changed" when its box, rounded to 0,5 pt, is not in the other run. The comparison needs a
snapshot of the code BEFORE the change:

    git checkout <base> && venv/bin/python scripts/reader_frame_report.py --snapshot <scratch>/before.json
    git checkout <fix>  && venv/bin/python scripts/reader_frame_report.py --against <scratch>/before.json

Without a snapshot it reports this checkout alone: every sheet whose reader frame is not the page's own
(sheet_zones.display_frame) — none, once the readers take it from PDFium.

    venv/bin/python scripts/reader_frame_report.py objektas_e --no-outlines
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
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402

from extractor import pdf_vectors  # noqa: E402
from extractor import sheet_zones as sz  # noqa: E402
from extractor.pdf_page_cache import page_count  # noqa: E402
from extractor.plan_area_annotations import _iter_pages, _words  # noqa: E402
from extractor.plan_dimensions import read_dimension_strings  # noqa: E402


def _codename(entry: dict) -> str:
    slug = str(entry.get("slug") or "")
    if slug.startswith("objektas_"):
        return slug
    words = str(entry.get("name") or slug).split()
    return "_".join(w.lower() for w in words[:2])


def _r(v: float) -> float:
    return round(float(v) * 2) / 2


def _box(b) -> list[float]:
    return [_r(v) for v in b]


def _frame(w, h) -> list[float]:
    return [round(float(w), 1), round(float(h), 1)]


def _outlines(entry: dict, pdf: bytes) -> dict | None:
    """{page: [room nr, …]} the geometry lane outlines on the frozen extract, or None without one."""
    extract = REPO / "ground_truth" / str(entry["slug"]) / "ai_extract.json"
    if not extract.is_file():
        return None
    import eval_harness  # noqa: PLC0415 — only when outlines are asked for
    from extractor.geometry_lane import apply_geometry

    parsed = copy.deepcopy(json.loads(extract.read_text(encoding="utf-8")))
    eval_harness._undo_lane_state(parsed)
    apply_geometry(parsed, pdf)
    out: dict[str, list] = collections.defaultdict(list)
    for r in parsed.get("patalpos") or []:
        k = r.get("_konturas") if isinstance(r, dict) else None
        if isinstance(k, dict) and k.get("page"):
            out[str(k["page"])].append([str(r.get("nr")), round(float(k.get("perimetras_m") or 0), 2),
                                        round(float(k.get("plotas_m2") or 0), 2)])
    return {p: sorted(v) for p, v in out.items()}


def _read_project(pdf: bytes, pages: list[int], outlines: bool, entry: dict) -> dict:
    sheets: dict[str, dict] = {}
    for p in pages:
        frame = sz.display_frame(pdf, p)
        W, H, rot = (frame[0], frame[1], frame[2]) if frame else (0.0, 0.0, 0)
        Wv, Hv, _ = pdf_vectors.page_geometry(pdf, p)
        walls = sorted(_box(poly.bounds) for poly in pdf_vectors.wall_fills(pdf, p))
        text_frames, words = [], []
        for _pn, Wd, Hd, chars, to_display in _iter_pages(pdf, [p]):
            text_frames.append(_frame(Wd, Hd))
            for w in _words(chars):
                words.append([str(w["text"])] + _box(to_display([w["x0"], w["top"], w["x1"], w["bottom"]])))
        sheets[str(p)] = {"rotation": rot, "page": _frame(W, H), "walls_frame": _frame(Wv, Hv),
                          "walls": walls, "text_frames": text_frames, "words": sorted(words), "dims": []}
    for d in read_dimension_strings(pdf, pages):
        s = sheets.get(str(d["page"]))
        if s is not None:
            s["dims"].append([str(d["text"])] + _box(d["bbox"]) + [d.get("span_source") or ""])
    for s in sheets.values():
        s["dims"].sort()
    return {"sheets": sheets, "outlines": _outlines(entry, pdf) if outlines else None}


def _changed(before: list, after: list) -> int:
    """Items of `before` with no identical item in `after` (a multiset difference)."""
    left = collections.Counter(json.dumps(x) for x in before)
    left.subtract(collections.Counter(json.dumps(x) for x in after))
    return sum(n for n in left.values() if n > 0)


def _frames_off(s: dict) -> list[str]:
    off = []
    if s["walls"] and s["walls_frame"] != s["page"]:
        off.append(f"walls {s['walls_frame']}")
    if any(f != s["page"] for f in s["text_frames"]):
        off.append(f"text {s['text_frames']}")
    return off


def _report_alone(code: str, data: dict) -> None:
    rotated = collections.Counter(s["rotation"] for s in data["sheets"].values())
    off = [(p, _frames_off(s)) for p, s in data["sheets"].items()]
    off = [(p, o) for p, o in off if o]
    print(f"{code}: {len(data['sheets'])} sheets, /Rotate {dict(rotated)}; "
          f"reader frame not the page's own on {len(off)} sheet(s)")
    for p, o in off:
        print(f"    p{p}: page {data['sheets'][p]['page']} — " + "; ".join(o))


def _report_against(code: str, before: dict, after: dict) -> bool:
    """Prints the differences; True when anything changed."""
    changed_any = False
    lines = []
    for p, a in after["sheets"].items():
        b = before["sheets"].get(p)
        if b is None:
            continue
        bits = []
        if b["walls_frame"] != a["walls_frame"] and (b["walls"] or a["walls"]):
            bits.append(f"walls frame {b['walls_frame']} → {a['walls_frame']}")
        nw = _changed(b["walls"], a["walls"])
        if nw or len(b["walls"]) != len(a["walls"]):
            bits.append(f"wall fills moved {nw}/{len(b['walls'])} (now {len(a['walls'])})")
        if b["text_frames"] != a["text_frames"]:
            bits.append(f"text frames {b['text_frames']} → {a['text_frames']}")
        nt = _changed(b["words"], a["words"])
        if nt or len(b["words"]) != len(a["words"]):
            bits.append(f"words moved {nt}/{len(b['words'])} (now {len(a['words'])})")
        nd = _changed(b["dims"], a["dims"])
        backed_b = sum(1 for d in b["dims"] if d[-1] == "line")
        backed_a = sum(1 for d in a["dims"] if d[-1] == "line")
        if nd or len(b["dims"]) != len(a["dims"]):
            bits.append(f"dimension strings changed {nd}/{len(b['dims'])} (now {len(a['dims'])}), "
                        f"backed by a line {backed_b} → {backed_a}")
        if bits:
            changed_any = True
            lines.append(f"    p{p} (/Rotate {a['rotation']}, page {a['page']}): " + "; ".join(bits))
    ob, oa = before.get("outlines"), after.get("outlines")
    outline_line = None
    if ob is not None and oa is not None:
        pages = sorted(set(ob) | set(oa), key=int)
        diffs = [f"p{p} {len(ob.get(p, []))} → {len(oa.get(p, []))}" for p in pages if ob.get(p, []) != oa.get(p, [])]
        total = f"{sum(len(v) for v in ob.values())} → {sum(len(v) for v in oa.values())}"
        if diffs:
            changed_any = True
        outline_line = f"    outlines {total}" + (f" — changed on {', '.join(diffs)}" if diffs else " — identical per sheet")
    print(f"{code}: {'CHANGED' if changed_any else 'unchanged'} "
          f"({len(after['sheets'])} sheets)")
    for ln in lines:
        print(ln)
    if outline_line:
        print(outline_line)
    return changed_any


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("projects", nargs="*", help="codenames or registry slugs (default: every project on disk)")
    ap.add_argument("--snapshot", help="write this checkout's reading to a JSON file (the BEFORE side)")
    ap.add_argument("--against", help="compare this checkout with a snapshot written by --snapshot")
    ap.add_argument("--no-outlines", action="store_true", help="skip the geometry lane (fast)")
    args = ap.parse_args()

    reg = yaml.safe_load((REPO / "ground_truth" / "registry.yaml").read_text())
    entries = [e for e in reg.get("projects") or [] if not e.get("ablation_of")]
    by_code = {_codename(e): e for e in entries}
    by_slug = {str(e["slug"]): e for e in entries}
    wanted = args.projects or list(by_code)
    before = json.loads(Path(args.against).read_text()) if args.against else None
    snapshot: dict[str, dict] = {}
    moved: list[str] = []
    for want in wanted:
        entry = by_code.get(want) or by_slug.get(want)
        if not entry:
            print(f"{want}: not in the registry")
            continue
        code = _codename(entry)
        pdf_path = REPO / str(entry.get("project_pdf") or "")
        if not pdf_path.is_file():
            print(f"{code}: PDF not on disk (copy the untracked fixtures into this checkout)")
            continue
        pdf = pdf_path.read_bytes()
        t0 = time.time()
        data = _read_project(pdf, list(range(1, page_count(pdf) + 1)), not args.no_outlines, entry)
        snapshot[code] = data
        if before is not None and code in before:
            if _report_against(code, before[code], data):
                moved.append(code)
        else:
            _report_alone(code, data)
        print(f"    ({time.time() - t0:.0f} s)")
    if args.snapshot:
        Path(args.snapshot).write_text(json.dumps(snapshot), encoding="utf-8")
        print(f"snapshot: {len(snapshot)} project(s) → {args.snapshot}")
    if before is not None:
        print(f"changed: {', '.join(moved) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

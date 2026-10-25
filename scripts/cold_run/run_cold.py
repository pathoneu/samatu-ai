#!/usr/bin/env python3
"""Cold run of the deterministic geometry lane on uploaded PDFs — no Vision, €0.

Phase 0 (b) of docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md.

    venv/bin/python scripts/cold_run/run_cold.py \
        --pdfs DIR_WITH_<id>.pdf --blobs DIR_WITH_<id>.json --out OUT_DIR \
        --project objektas_x=<project-id> [--project …]

For every `--project codename=id` whose PDF exists, the lane runs in-process
exactly in the order the paid reading runs its deterministic steps
(vision_call Step 2.44 → 2.44d), but with NO model anywhere:

  text layer scan (scan_text_layer) → room table from the text layer
  (pdfplumber_eksplikacija) → rooms = that table, else the standalone „m²"
  labels on the plan → plan-dimension pairs → raster wall outlines →
  geometry lane (vector outlines, summed perimeters, drawn openings, floor
  coverings) → door schedule, ruled tables, vector symbols.

A second variant seeds the lane with the room LIST production stored (nr,
name, area only — every polygon/perimeter dropped) so the lane's own
outlining can be judged even where the cold room source is empty.
Plan-sheet classification: the cold variant uses none (the lane falls back
to every dimensioned sheet); the seeded variant uses production's stored
`puslapiai` (already paid for, no new call).

Writes OUT_DIR/<codename>.json (lane results, contains the drawing's words —
keep OUT_DIR outside the repository) and prints a compact summary.

Any attempt to construct an Anthropic client raises: the run is guaranteed
free.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.setdefault("SAMATU_AUTH_DISABLED", "1")


def _forbid_anthropic() -> None:
    try:
        import anthropic
    except Exception:  # noqa: BLE001
        return

    def _boom(*_a, **_k):
        raise RuntimeError("cold run: an Anthropic client was requested — this run must not call a model")

    anthropic.Anthropic.__init__ = _boom          # type: ignore[assignment]
    anthropic.AsyncAnthropic.__init__ = _boom     # type: ignore[assignment]


_forbid_anthropic()

ROOM_SEED_KEYS = ("nr", "pavadinimas", "plotas_m2", "puslapio_nr", "lubu_aukstis_m")


def _r2(v):
    try:
        return None if v is None else round(float(v), 2)
    except (TypeError, ValueError):
        return None


def pdf_profile(pdf_bytes: bytes) -> dict:
    """Pages, text characters, image objects and path objects per page (PDFium)."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    from extractor.pdfium_guard import PDFIUM_LOCK  # the lock the lane uses
    out = []
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for i in range(len(doc)):
                page = doc[i]
                tp = page.get_textpage()
                chars = tp.count_chars()
                n_img = n_path = n_text = 0
                for obj in page.get_objects(max_depth=4):
                    t = obj.type
                    if t == raw.FPDF_PAGEOBJ_IMAGE:
                        n_img += 1
                    elif t == raw.FPDF_PAGEOBJ_PATH:
                        n_path += 1
                    elif t == raw.FPDF_PAGEOBJ_TEXT:
                        n_text += 1
                w, h = page.get_size()
                kind = ("vector+text" if n_path > 200 and chars > 200 else
                        "vector, no text" if n_path > 200 else
                        "raster, no text" if n_img and chars < 50 else
                        "text" if chars > 200 else "other")
                out.append({"page": i + 1, "w_pt": round(w, 1), "h_pt": round(h, 1), "chars": chars,
                            "images": n_img, "paths": n_path, "text_objects": n_text, "kind": kind})
                tp.close()
                page.close()
        finally:
            doc.close()
    return {"pages": len(out), "per_page": out}


def preflight_kinds(pdf_bytes: bytes) -> dict:
    try:
        from extractor.preflight import preflight_pdf
        pf = preflight_pdf(pdf_bytes)
        return {k: pf.get(k) for k in ("verdict", "kinds", "page_count", "pages_scanned", "kind_counts") if k in pf}
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}


def rooms_from_labels(annotations: list[dict]) -> list[dict]:
    """No table: one room per standalone „N.NN m²" label on the richest page set (the plan_area lane's own
    choice of „the table"). nr = L1…Ln; the label's box seeds the room's position."""
    from extractor.plan_area_annotations import _candidate_labels
    accepted, _skipped = _candidate_labels(annotations)
    rooms = []
    for i, a in enumerate(accepted, start=1):
        rooms.append({"nr": f"L{i}", "pavadinimas": "", "plotas_m2": float(a["value_m2"]), "puslapio_nr": int(a["page"]),
                      "plotas_saltinis": "plano_uzrasas",
                      "_plotas_uzrasas": {"bbox": a["bbox"], "page": int(a["page"]), "page_width": a["page_width"],
                                          "page_height": a["page_height"], "value_m2": a["value_m2"]}})
    return rooms


def run_lane(pdf_bytes: bytes, rooms: list[dict], puslapiai: list[dict] | None, scan: dict) -> dict:
    """Steps 2.44 → 2.44d of the paid reading on `rooms`, no model."""
    from extractor.geometry_lane import apply_geometry
    from extractor.plan_area_annotations import apply_height_statements, plan_pages_from_classification
    from extractor.plan_dimensions import apply_dimension_strings
    from extractor.wall_outline import apply_wall_outlines

    parsed = {"patalpos": copy.deepcopy(rooms), "puslapiai": puslapiai or []}
    timings: dict[str, float] = {}
    meta: dict = {}
    t = time.time()
    hs = apply_height_statements(parsed["patalpos"], scan.get("heights") or [])
    meta["heights"] = {k: v for k, v in hs.items() if k != "rooms"} | {"rooms": hs.get("rooms")}
    plan_pages = set(plan_pages_from_classification(parsed["puslapiai"]))
    anns = [a for a in scan["annotations"] if not plan_pages or a["page"] in plan_pages]
    try:
        meta["plan_dimension_lane"] = apply_dimension_strings(parsed["patalpos"], list(scan.get("dimensions") or []), anns)
    except Exception as exc:  # noqa: BLE001
        meta["plan_dimension_lane"] = {"error": repr(exc)}
    timings["dimension_pairs_s"] = round(time.time() - t, 2)
    t = time.time()
    try:
        meta["wall_outline_lane"] = apply_wall_outlines(parsed["patalpos"], pdf_bytes, list(scan.get("dimensions") or []), anns)
    except Exception as exc:  # noqa: BLE001
        meta["wall_outline_lane"] = {"error": repr(exc)}
    timings["raster_wall_outlines_s"] = round(time.time() - t, 2)
    t = time.time()
    geo = apply_geometry(parsed, pdf_bytes)
    timings["geometry_lane_s"] = round(time.time() - t, 2)
    return {"parsed": parsed, "geo": geo, "meta": meta, "timings": timings}


def room_rows(parsed: dict) -> list[dict]:
    out = []
    for r in parsed.get("patalpos") or []:
        k = r.get("_konturas") if isinstance(r.get("_konturas"), dict) else {}
        angos = (r.get("_angos_sienose") or {}).get("angos") or [] if isinstance(r.get("_angos_sienose"), dict) else []
        suma = r.get("_perimetras_suma") if isinstance(r.get("_perimetras_suma"), dict) else {}
        out.append({
            "nr": r.get("nr"), "name": r.get("pavadinimas"), "table_m2": _r2(r.get("plotas_m2")),
            "vieta": (r.get("_vieta") or {}).get("saltinis"), "vieta_page": (r.get("_vieta") or {}).get("page"),
            "polygon_source": r.get("polygon_source"),
            "outline_m2": _r2(k.get("plotas_m2")), "outline_perim_m": _r2(k.get("perimetras_m")),
            "outline_page": k.get("page"), "area_mismatch": k.get("plotas_nesutampa"),
            "outline_reason": r.get("_konturo_priezastis"),
            "outline_proposal_m2": _r2((r.get("_konturo_siulymas") or {}).get("plotas_m2")) if isinstance(r.get("_konturo_siulymas"), dict) else None,
            "open_space": (r.get("_atvira_erdve") or {}).get("nariai") if isinstance(r.get("_atvira_erdve"), dict) else None,
            "perim_m": _r2(r.get("perimetras_m")), "perim_source": r.get("perimetras_saltinis"),
            "perim_strings": suma.get("eilutes"), "perim_reason": r.get("_perimetras_priezastis"),
            "perim_estimate_m": _r2(r.get("_perimetras_ivertis_m")),
            "drawn_doors": sum(1 for a in angos if a.get("nupiesta") == "durys"),
            "drawn_windows": sum(1 for a in angos if a.get("nupiesta") == "langas"),
            "openings_total": len(angos), "openings_to_outside": sum(1 for a in angos if a.get("i") == "laukas"),
            "floor_covering": r.get("grindu_danga"), "height_m": r.get("lubu_aukstis_m"),
            "height_source": r.get("lubu_aukstis_saltinis"),
        })
    return out


def geo_summary(geo: dict) -> dict:
    keys = ("status", "vietos", "grupes", "lapai", "konturai", "konturu_priezastys", "atviros_erdves", "perimetrai_sudeti",
            "perimetrai_tusti", "nupiesta", "masteliai", "masteliai_atmesti", "masteliai_kiti", "kiti_aukstai",
            "konturu_siulymai", "perimetrai_atmesti", "poros_patvirtintos", "poros_atmestos", "seconds", "error")
    out = {k: geo.get(k) for k in keys if k in geo}
    g = geo.get("grindu_dangos") or {}
    out["grindu_dangos"] = {"lapai": g.get("lapai"), "perskaityta": len(g.get("perskaityta") or {}),
                            "dvi_dangos": g.get("dvi_dangos")}
    return out


def scales_from_dims(dims: list[dict]) -> dict:
    per: dict[str, dict] = {}
    for d in dims:
        p = str(d["page"])
        rec = per.setdefault(p, {"strings": 0, "line_backed": 0, "scale_m_per_pt": None, "mastelis": None,
                                 "atmestas": None, "kitas": None})
        rec["strings"] += 1
        if d.get("span_source") == "line":
            rec["line_backed"] += 1
        if d.get("scale_m_per_pt") and rec["scale_m_per_pt"] is None:
            rec["scale_m_per_pt"] = d["scale_m_per_pt"]
            rec["mastelis"] = d.get("mastelis")
        if d.get("mastelis_atmestas"):
            rec["atmestas"] = d["mastelis_atmestas"]
        if d.get("mastelis_kitas"):
            rec["kitas"] = d["mastelis_kitas"]
    return per


# What a fresh paid reading carries from the model besides the room list (Phase 3c moves these readers onto the
# text layer; the row builder blanks every quantity that rests on them without a legal source — row_provenance).
MODEL_ROOM_KEYS = ("paskirtis", "lubu_tipas", "elementai", "plyteles_sienos_aukstis_m")
PROJECT_KEYS = ("_apimtis", "_overrides", "detected_symbols_summary", "_door_types", "_sanitary_prietaisai",
                "puslapiai", "_plyteliu_specs")


def samata(lane_parsed: dict, blob: dict | None, scan: dict, pdf_bytes: bytes) -> dict:
    """The sąmata the paid reading builds today on these rooms (v4 3b): production's model readings carried
    in by the room's old key (`_modelio_nr`), the project-level text scans, the height step, the per-room
    engine and the row builder. Every row with its `_kilme`; no model call."""
    from extractor import row_provenance as rp
    from extractor.vision_call import _build_pozicijos_from_rooms, _recompute_per_room_via_python

    parsed = copy.deepcopy(lane_parsed)
    by_old = {str(r.get("nr")): r for r in (blob or {}).get("patalpos") or [] if isinstance(r, dict)}
    for r in parsed.get("patalpos") or []:
        old = by_old.get(str(r.get("_modelio_nr") or r.get("nr")))
        if old:
            for k in MODEL_ROOM_KEYS:
                if k in old and k not in r:
                    r[k] = copy.deepcopy(old[k])
    for k in PROJECT_KEYS:
        if blob and k in blob:
            parsed[k] = copy.deepcopy(blob[k])
    meta = (blob or {}).get("_meta") or {}
    parsed["_meta"] = {k: meta.get(k) for k in ("fixtures_status", "fixtures_counts", "fixtures_raised") if k in meta}
    parsed["_autoriaus_kiekiai"] = scan.get("figures") or []
    try:
        from extractor.symbol_legend import scan_symbol_legend
        parsed["_symbol_legend"] = scan_symbol_legend(pdf_bytes)
    except Exception:  # noqa: BLE001
        pass
    try:
        from extractor.door_schedule import scan_door_schedule
        parsed["_duru_ziniarastis"] = scan_door_schedule(pdf_bytes)
    except Exception:  # noqa: BLE001
        pass
    try:
        from extractor.vector_symbols import scan_vector_symbols
        parsed["_vector_symbols"] = scan_vector_symbols(pdf_bytes)
    except Exception:  # noqa: BLE001
        pass
    from extractor import scope as _scope

    rp.fill_heights_from_read(parsed["patalpos"], parsed)
    # his „ką skaičiuoti" exactly as extract_interior applies it (Step 2.9 → 2.95)
    rules = {**(parsed.get("_overrides") or {})}
    if parsed.get("_apimtis") and not rules.get("apimtis"):
        rules["apimtis"] = parsed["_apimtis"]
    parsed = _recompute_per_room_via_python(parsed, rules)
    parsed["_overrides"] = rules
    apimtis = _scope.normalize_apimtis(rules.get("apimtis"))
    _scope.mark_rooms(parsed.get("patalpos") or [], apimtis)
    if apimtis:
        parsed["_apimtis"] = apimtis
        _scope.apply_ceiling_choice(parsed.get("patalpos") or [], apimtis)
    parsed = _build_pozicijos_from_rooms(parsed)
    if apimtis:
        parsed["pozicijos"] = _scope.filter_rows_by_families(parsed.get("pozicijos"), apimtis)
    rows = [{"skyrius": p.get("skyrius"), "aprasymas": p.get("aprasymas"), "vnt": p.get("vnt"),
             "kiekis": p.get("kiekis"), "kilme": p.get(rp.KILME_KEY), "priezastis": p.get(rp.REASON_KEY)}
            for p in parsed.get("pozicijos") or []]
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["kilme"])] = counts.get(str(r["kilme"]), 0) + 1
    return {"rows": rows, "kilme": counts, "illegal": [r["aprasymas"] for r in rows
                                                      if r["kilme"] in rp.ILLEGAL and r["kiekis"] is not None]}


def project_run(codename: str, pid: str, pdf_path: Path, blob: dict | None) -> dict:
    pdf_bytes = pdf_path.read_bytes()
    res: dict = {"codename": codename, "bytes": len(pdf_bytes), "timings": {}}
    T0 = time.time()
    t = time.time()
    res["profile"] = pdf_profile(pdf_bytes)
    res["preflight"] = preflight_kinds(pdf_bytes)
    res["timings"]["profile_s"] = round(time.time() - t, 2)

    from extractor.geometry_lane import geometry_dimension_strings
    from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
    from extractor.plan_area_annotations import scan_text_layer

    t = time.time()
    scan = scan_text_layer(pdf_bytes)
    res["timings"]["text_scan_s"] = round(time.time() - t, 2)
    res["text_scan"] = {"annotations": len(scan["annotations"]),
                        "standalone_m2_labels": sum(1 for a in scan["annotations"] if a.get("standalone")),
                        "figures": [{k: f.get(k) for k in ("page", "label", "value", "unit", "family")} for f in scan["figures"]],
                        "heights": len(scan.get("heights") or []), "dimension_strings_classified_pages": len(scan["dimensions"])}
    t = time.time()
    dims = geometry_dimension_strings(pdf_bytes)
    res["timings"]["dimension_strings_s"] = round(time.time() - t, 2)
    res["scales"] = scales_from_dims(dims)
    res["dimension_strings_total"] = len(dims)

    from extractor.room_identity import identity_from_table, join_rows

    t = time.time()
    ek = extract_eksplikacija_pdfplumber(pdf_bytes)
    res["timings"]["room_table_s"] = round(time.time() - t, 2)
    # The room list exactly as the paid reading assembles it (vision_call Step 2.4 → extractor/room_identity.py):
    # the text-layer table's rows ARE the rooms — numbers as drawn (`<unit>-<nr>` with `_vienetas` /
    # `_nr_brezinyje` for stacked unit tables), names, areas, row evidence. No model rooms here.
    ident = identity_from_table([], ek)
    table_rooms = []
    if ident is not None:
        join_rows(ident, ek)
        table_rooms = ident["rooms"]
        for r in table_rooms:
            r.setdefault("puslapio_nr", r.get("eksplikacija_source_page"))
    res["room_table"] = {"page": ek.get("eksplikacija_source_page"), "rooms": table_rooms,
                         "sum_m2": _r2(sum(float(r["plotas_m2"] or 0) for r in table_rooms)),
                         "meta": {k: ek.get("_meta", {}).get(k) for k in ("eksplikacija_pages_found", "tables_examined", "header_detected")}}

    # ── variant A: cold (text-layer rooms, no classification) ──
    if table_rooms:
        cold_rooms, src = table_rooms, "room_table_text_layer"
    else:
        cold_rooms, src = rooms_from_labels(scan["annotations"]), "plan_m2_labels"
    res["cold"] = {"room_source": src, "rooms_in": len(cold_rooms)}
    if cold_rooms:
        lane = run_lane(pdf_bytes, cold_rooms, None, scan)
        res["cold"].update({"lane": geo_summary(lane["geo"]), "rooms": room_rows(lane["parsed"]),
                            "dimension_pairs": {k: lane["meta"]["plan_dimension_lane"].get(k) for k in ("status", "confirmed", "corrected", "proposed", "unmatched")},
                            "raster_outlines": {k: lane["meta"]["wall_outline_lane"].get(k) for k in ("status", "traced", "corrected", "unmatched", "error")},
                            "timings": lane["timings"]})
    else:
        res["cold"]["blank_reason"] = "no room table and no standalone m² label in the text layer"

    # ── variant B: production's room list as seed (nr/name/area only) + production's page classification ──
    if blob:
        seed = [{k: r.get(k) for k in ROOM_SEED_KEYS if r.get(k) is not None} for r in blob.get("patalpos") or [] if isinstance(r, dict)]
        res["seeded"] = {"room_source": "production_room_list", "rooms_in": len(seed)}
        if seed:
            lane = run_lane(pdf_bytes, seed, blob.get("puslapiai") or [], scan)
            res["seeded"].update({"lane": geo_summary(lane["geo"]), "rooms": room_rows(lane["parsed"]),
                                  "dimension_pairs": {k: lane["meta"]["plan_dimension_lane"].get(k) for k in ("status", "confirmed", "corrected", "proposed", "unmatched")},
                                  "raster_outlines": {k: lane["meta"]["wall_outline_lane"].get(k) for k in ("status", "traced", "corrected", "unmatched", "error")},
                                  "timings": lane["timings"]})

    # ── variant C: the app's path (Phase 3a) — production's stored model rooms (nr/name/area only) through the
    # paid reading's room assembly (room_identity.identity_from_table + join_rows): what a fresh reading of this
    # project builds now, the model's keys K1… replaced by the drawing's. Production's page classification. ──
    if blob:
        seed = [{k: r.get(k) for k in ROOM_SEED_KEYS if r.get(k) is not None} for r in blob.get("patalpos") or [] if isinstance(r, dict)]
        app = identity_from_table(seed, ek) if seed else None
        res["app"] = {"room_source": "room_identity" if app is not None else "model_list (no text-layer table)",
                      "rooms_in": len(app["rooms"]) if app is not None else len(seed)}
        if app is not None:
            join_rows(app, ek)
            res["app"].update({"renamed": app["renamed"], "dropped": [d.get("nr") for d in app["dropped"]],
                               "matched": app["matched"]})
        app_rooms = app["rooms"] if app is not None else seed
        if app_rooms:
            lane = run_lane(pdf_bytes, app_rooms, blob.get("puslapiai") or [], scan)
            res["app"].update({"lane": geo_summary(lane["geo"]), "rooms": room_rows(lane["parsed"]),
                               "timings": lane["timings"]})
            res["app"]["samata"] = samata(lane["parsed"], blob, scan, pdf_bytes)      # v4 3b

    # ── project-level deterministic scans ──
    t = time.time()
    try:
        from extractor.door_schedule import scan_door_schedule
        ds = scan_door_schedule(pdf_bytes)
        res["door_schedule"] = {k: ds.get(k) for k in ("status", "text_layer_ok", "beapvadines", "su_apvadais", "stumdomos", "kitos", "sakinys")}
    except Exception as exc:  # noqa: BLE001
        res["door_schedule"] = {"error": repr(exc)}
    try:
        from extractor.schedules import read_schedules
        sc = read_schedules(pdf_bytes)
        res["tables"] = {"status": sc.get("status"), "detail": sc.get("detail"), "lapai": sc.get("lapai"),
                         "tables": sum(len(v) for v in (sc.get("lenteles") or {}).values()),
                         "schedules": {k: (len(v.get("rows") or []) if v else None) for k, v in (sc.get("ziniarasciai") or {}).items()}}
    except Exception as exc:  # noqa: BLE001
        res["tables"] = {"error": repr(exc)}
    try:
        from extractor.vector_symbols import scan_vector_symbols
        vs = scan_vector_symbols(pdf_bytes)
        d = vs.get("difuzoriai") or {}
        res["vector_symbols"] = {"diffusers_defined": d.get("defined"), "count": d.get("count"), "sakinys": d.get("sakinys")}
    except Exception as exc:  # noqa: BLE001
        res["vector_symbols"] = {"error": repr(exc)}
    try:
        from extractor.wall_types import read_wall_types
        wt = read_wall_types(pdf_bytes)
        res["wall_types"] = {"rows": len(wt.get("eilutes") or []), "unread": len(wt.get("neperskaityta") or [])}
    except Exception as exc:  # noqa: BLE001
        res["wall_types"] = {"error": repr(exc)}
    res["timings"]["project_scans_s"] = round(time.time() - t, 2)
    res["timings"]["total_s"] = round(time.time() - T0, 2)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdfs", required=True, type=Path)
    ap.add_argument("--blobs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--project", action="append", required=True, help="codename=project-id")
    args = ap.parse_args()
    if ROOT in args.out.resolve().parents or args.out.resolve() == ROOT:
        print("refusing: --out must be outside the repository (results contain the drawing's words)")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for spec in args.project:
        codename, _, pid = spec.partition("=")
        pdf = args.pdfs / f"{pid}.pdf"
        blob_path = args.blobs / f"{pid}.json"
        blob = None
        if blob_path.exists():
            raw = json.loads(blob_path.read_text())
            blob = raw.get("data") if isinstance(raw.get("data"), dict) else raw
        if not pdf.exists():
            print(f"{codename}: no PDF — skipped (blob audit only)")
            continue
        print(f"{codename}: running …", flush=True)
        res = project_run(codename, pid, pdf, blob)
        (args.out / f"{codename}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        c = res.get("cold") or {}
        lane = c.get("lane") or {}
        print(f"  pages {res['profile']['pages']} | kinds {[p['kind'] for p in res['profile']['per_page']]} | "
              f"table rooms {len(res['room_table']['rooms'])} | cold rooms {c.get('rooms_in')} ({c.get('room_source')}) | "
              f"outlines {len(lane.get('konturai') or [])} | summed perims {len(lane.get('perimetrai_sudeti') or [])} | "
              f"{res['timings']['total_s']} s")
        for variant in ("cold", "app", "seeded"):
            rr = (res.get(variant) or {}).get("rooms") or []
            if rr:
                print(f"  {variant:6s}: rooms {len(rr)} | placed by badge/label "
                      f"{sum(1 for r in rr if r.get('vieta') in ('zenkliukas', 'plotas_uzrasas'))} | "
                      f"outlined {sum(1 for r in rr if r.get('outline_m2'))} | keys {[r.get('nr') for r in rr]}")
        sam = (res.get("app") or {}).get("samata")
        if sam:
            print(f"  sąmata (app): rows {len(sam['rows'])} | by class {sam['kilme']} | model/default with a number: "
                  f"{sam['illegal'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
V9 Pipeline — orchestratorius.

Sujungia visus V9 modulius į pilną patalpų ekstrahavimo procesą:

    pdf_bytes
       │
       ▼
    [1] page_classifier  — atrenka aukštų planus (skip pjūvis, fasadai)
       │
       ▼
    [2] vector_polygons  — Shapely polygonize → kambarių polygons (DETERMINISTINIAI plotai)
       │
       ▼
    [3] som_renderer     — render PDF + raudoni numeruoti markeriai per polygons
       │
       ▼
    [4] vision_classifier— Vision'as klasifikuoja KAS yra kiekvienas regionas
                            (NEMATAVO — tik pavadinimas + paskirtis)
       │
       ▼
    [5] merge            — polygon plotai + classification labels → V8 input
       │
       ▼
    [6] universal_engine — V8 industries formules (NRM2/DIN/CSI/ANSI)
       │
       ▼
    [7] lt_sanity        — LT validacija (paskirtis ranges, mansardinis, atviros erdvės)
       │
       ▼
    final result

Privalumai:
- Plotai 100% deterministiniai (ne hallucinated)
- Vision tokens ~60% mažiau (tik klasifikacija, ne matavimas)
- Multi-pass voting → mažiau outlier'ų pavadinime/paskirtyje
- LT specifika: mansardinis svoris, atviros erdvės, paskirties ranges
"""
from __future__ import annotations
import io
import time
from typing import Any

from .vector_polygons import build_room_polygons
from .som_renderer import render_pdf_with_som
from .vision_classifier import classify_rooms_with_som


# LT kambarių vocabulary — pavadinimo atpažinimui iš inline texts.
# Kompozicija: žodžio kamienas + paskirtis (ROOM_TYPE_RULES key).
LT_ROOM_VOCAB = [
    # (atitinka regex pattern, paskirtis)
    (r"svetain", "gyvenamoji"),
    (r"miegam", "miegamoji"),
    (r"vonia|vonios", "vonia"),
    (r"\bwc\b|tualet", "wc"),
    (r"virtuv", "virtuve"),
    (r"valgom", "valgomasis"),
    (r"koridor", "koridorius"),
    (r"\bhol(?:as)?\b|prieškambar", "holas"),
    (r"drabuzin|drabužin|garderob", "drabuzine"),
    (r"sandel", "sandeliukas"),
    (r"tambūr|tambur", "tambūras"),
    (r"garaž|garaz", "garazas"),
    (r"katiln|katilin", "katiline"),
    (r"skalbykl", "skalbykla"),
    (r"kabinet|biur(?:as)?", "gyvenamoji"),
    (r"vaiku|vaik\b", "miegamoji"),
    (r"teras|balkon|lodzi|lodži", "gyvenamoji"),
    (r"patalp|kambar|kamb\.?", "gyvenamoji"),
    # Eksplikacijos lentelės sutrumpinimai
    (r"^k[\-\s]?\d", "gyvenamoji"),    # K-1, K1
    (r"^m[\-\s]?\d", "miegamoji"),
    (r"^sv[\-\s\.]", "gyvenamoji"),    # Sv., Sv-1
    (r"^v[\-\s\.]?\d", "vonia"),       # V1, V.1
]


def _detect_lt_room_name(texts: list[str]) -> tuple[str | None, str | None]:
    """Iš teksto sąrašo grąžina (pavadinimas, paskirtis) jei rastas LT kambario žodis.
    Returns (None, None) jei nieko nerasta.
    """
    import re
    if not texts:
        return None, None
    for t in texts:
        tt = (t or "").strip()
        if len(tt) < 2:
            continue
        tl = tt.lower()
        for pattern, paskirtis in LT_ROOM_VOCAB:
            if re.search(pattern, tl):
                return tt, paskirtis
    return None, None


def _list_pdf_pages(pdf_bytes: bytes) -> int:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


def _classify_pages(pdf_bytes: bytes, max_pages: int = 20) -> list[dict]:
    """Atrenka tik aukštų planus (skip pjūviai/fasadai).
    Naudojam V8 page_classifier jei galima, kitaip — visi puslapiai.
    """
    try:
        from interior_v8.page_classifier import classify_pdf
        # classify_pdf grąžina LIST tiesiai, ne dict
        all_pages = classify_pdf(pdf_bytes) or []
        target_types = {"floor_plan", "aukstu_planas", "ceiling_plan", "lubu_planas",
                        "wall_development", "sienu_isklotines"}
        pages = []
        for p in all_pages[:max_pages]:
            if not isinstance(p, dict):
                continue
            ptype = (p.get("type") or "").lower()
            label = (p.get("label") or "").lower()
            if (any(t in ptype for t in target_types) or "plan" in ptype
                    or "plan" in label):
                pages.append({"page_nr": p.get("page", 0), **p})
        if pages:
            return pages
        # Jei nieko nepasirinkta klasifikatoriaus — naudojam visus
    except Exception as e:
        print(f"[V9] page_classifier neprieinamas: {e}")

    # Fallback: visi puslapiai
    n = _list_pdf_pages(pdf_bytes)
    return [{"page_nr": i + 1, "type": "unknown"} for i in range(min(n, max_pages))]


def _merge_polygon_with_classification(
    polygon: dict,
    classification: dict | None,
    page_nr: int,
    nr_offset: int,
    page_width_pdf: float | None = None,
    page_height_pdf: float | None = None,
) -> dict:
    """Sujungia geometry (iš vector_polygons) + labels (iš Vision) į V8-compatible dict.
    """
    # Default'ai jei Vision nieko nedavė
    pavadinimas = "Patalpa"
    paskirtis = "gyvenamoji"
    H = 2.82
    is_open = False

    if classification:
        pavadinimas = classification.get("pavadinimas") or pavadinimas
        paskirtis = classification.get("paskirtis") or paskirtis
        H = float(classification.get("lubu_aukstis_m") or 2.82)
        is_open = bool(classification.get("is_open_space"))

    # Jei Vision negavo geros klasifikacijos, bandom iš inside_texts
    if pavadinimas == "Patalpa":
        # PIRMA priority: ieškom LT kambario žodžio (svetainė, vonia, virtuvė...)
        all_texts = (polygon.get("inside_texts") or []) + (polygon.get("nearby_texts") or [])
        lt_name, lt_paskirtis = _detect_lt_room_name(all_texts)
        if lt_name:
            pavadinimas = lt_name
            if not classification or not classification.get("paskirtis"):
                paskirtis = lt_paskirtis
        else:
            # Fallback heuristika: praleisti telefono numerius, matmenis, koordinates
            import re
            for t in (polygon.get("inside_texts") or [])[:8]:
                tt = (t or "").strip()
                if len(tt) < 3:
                    continue
                # Praleisti telefono numerius (+370...)
                if tt.startswith("+") or re.match(r"^\d{3,}$", tt):
                    continue
                # Praleisti matmenis (1500, 2,40m, 3.6, 1:50, +2820)
                if re.match(r"^[\d.,+\-:m\s]+$", tt):
                    continue
                # Praleisti aukščio anotacijas (H=2820, +2820)
                if re.match(r"^[H+\-]?\d+$", tt):
                    continue
                # Praleisti vienos raidės "kodus"
                if len(tt) <= 2 and tt.isalpha():
                    continue
                # Tinkamas kandidatas
                pavadinimas = tt
                break

    return {
        "nr": nr_offset + polygon["polygon_id"] + 1,
        "page_nr": page_nr,
        "polygon_id": polygon["polygon_id"],
        "pavadinimas": pavadinimas,
        "paskirtis": paskirtis,
        "plotas_m2": polygon["area_m2"],
        "perimetras_m": polygon["perimeter_m"],
        "lubu_aukstis_m": H,
        "is_open_space": is_open,
        "bbox_pct": polygon.get("bbox_pct"),
        "centroid_pct": polygon.get("centroid_pct"),
        "polygon_pdf": polygon.get("polygon_pdf"),
        # PDF page dimensions — REIKALINGI frontend overlay (polygon_pdf → pikseliais)
        "page_width_pdf": page_width_pdf,
        "page_height_pdf": page_height_pdf,
        "nearby_texts": polygon.get("nearby_texts", []),
        "inside_texts": polygon.get("inside_texts", []),
        "_vote_consensus": (classification or {}).get("_vote_consensus"),
        "_source": "v9_vector",
    }


def extract_v9(
    pdf_bytes: bytes,
    drawing_scale: int = 50,
    n_passes: int = 3,
    max_pages: int = 20,
    rules_override: dict | None = None,
    skip_vision: bool = False,
    detect_symbols: bool = True,
    symbol_max_pages: int = 3,
) -> dict:
    """V9 pilna pipeline: PDF → patalpų sąrašas su V8 industries kiekiais.

    Etapai:
      1. classify_pages() — page_classifier identifikuoja puslapio tipus
         (floor_plan, electrical, plumbing, ceiling, ...).
      2. Per kiekvieną planą: build_room_polygons() iš PDF vector geometry.
      3. SoM render + Vision classify (paskirtis + pavadinimas per polygon).
      4. detect_all_symbols_for_pdf() — AI Vision per kiekvieną page_type
         ieško simbolių (rozetes, klozetus, sviestuvus, difuzorius, ...).
      5. extract_v8(rooms, detected_symbols) — additional_positions naudoja
         TIKRUS detektuotus skaičius vietoj hardcoded vidurkių.

    Args:
        pdf_bytes: PDF turinys
        drawing_scale: 1:N (LT default 50)
        n_passes: Vision multi-pass kambarių klasifikacijai (1=greitai, 3=tiksliau)
        max_pages: ribojam puslapių analize (perf)
        rules_override: vartotojo prefs
        skip_vision: jei True — vector polygons + fallback classification (be Vision)
        detect_symbols: jei True — paleisti AI simbolių detekciją per puslapio tipus
        symbol_max_pages: max puslapių per simbolio tipą (perf)

    Returns:
        {
          "rooms": [...],
          "totals": {...},
          "additional_positions": [...],   # su detected/fallback flag'u
          "detected_symbols": {...},        # AI rasti simboliai per tipą
          "lt_sanity": {...},
          "v9_meta": {pages_processed, polygons_total, symbols_detected,
                      vision_passes, ms_total},
          "engine": "v9_pipeline",
        }
    """
    t0 = time.time()

    if not pdf_bytes:
        return {"error": "empty pdf", "engine": "v9_pipeline"}

    # 1. Atrinkti puslapius (tik planai)
    pages = _classify_pages(pdf_bytes, max_pages=max_pages)
    if not pages:
        return {"error": "no plan pages found", "engine": "v9_pipeline"}

    all_v8_rooms: list[dict] = []
    page_stats: list[dict] = []
    scale_warnings: list[dict] = []
    nr_offset = 0

    # 2. Per puslapį: polygons + SoM + Vision classify
    for page_info in pages:
        page_nr = page_info.get("page_nr") or 1
        page_t0 = time.time()

        try:
            poly_result = build_room_polygons(
                pdf_bytes=pdf_bytes,
                page_nr=page_nr,
                drawing_scale=drawing_scale,
            )
        except Exception as e:
            print(f"[V9 page {page_nr}] vector_polygons failed: {e}")
            page_stats.append({
                "page_nr": page_nr, "error": str(e),
                "polygons": 0, "ms": int((time.time() - page_t0) * 1000),
            })
            continue

        # Propaguoti scale warning iš vector_polygons
        sw = poly_result.get("scale_warning")
        if sw:
            scale_warnings.append({"page_nr": page_nr, "warning": sw})

        polygons = poly_result.get("rooms", [])
        if not polygons:
            page_stats.append({
                "page_nr": page_nr,
                "error": poly_result.get("error", "no polygons"),
                "polygons": 0,
                "ms": int((time.time() - page_t0) * 1000),
            })
            continue

        # 3. SoM render + Vision classify
        classifications_by_id: dict[int, dict] = {}
        if not skip_vision:
            try:
                som = render_pdf_with_som(
                    pdf_bytes=pdf_bytes,
                    page_nr=page_nr,
                    polygons=polygons,
                    dpi=200,
                )
                if som.get("image_b64"):
                    cls_result = classify_rooms_with_som(
                        image_b64=som["image_b64"],
                        polygons_count=len(polygons),
                        n_passes=n_passes,
                    )
                    for r in cls_result.get("rooms", []):
                        pid = r.get("polygon_id")
                        if pid is not None:
                            classifications_by_id[int(pid)] = r
            except Exception as e:
                print(f"[V9 page {page_nr}] SoM/Vision failed: {e}")

        # 4. Merge polygon + classification → V8 input
        page_w_pdf = poly_result.get("page_width_pdf")
        page_h_pdf = poly_result.get("page_height_pdf")
        for poly in polygons:
            pid = poly["polygon_id"]
            cls = classifications_by_id.get(pid)
            v8_room = _merge_polygon_with_classification(
                polygon=poly, classification=cls,
                page_nr=page_nr, nr_offset=nr_offset,
                page_width_pdf=page_w_pdf,
                page_height_pdf=page_h_pdf,
            )
            all_v8_rooms.append(v8_room)

        nr_offset += len(polygons)
        page_stats.append({
            "page_nr": page_nr,
            "polygons": len(polygons),
            "polygons_total_pre_filter": poly_result.get("stats", {}).get("polygons_total", 0),
            "classified": len(classifications_by_id),
            "ms": int((time.time() - page_t0) * 1000),
        })

    if not all_v8_rooms:
        return {
            "error": "no rooms detected after vector + classification",
            "engine": "v9_pipeline",
            "v9_meta": {
                "pages_processed": len(pages),
                "page_stats": page_stats,
                "ms_total": int((time.time() - t0) * 1000),
            },
        }

    # 4.5. AI SIMBOLIŲ DETEKCIJA — per kiekvieną page_type ieškom tinkamų simbolių
    # (rozetes, klozetus, sviestuvus, difuzorius, ...).
    # Tai yra ESMINIS pakeitimas vs senasis hardcoded-multiplier approach.
    detected_symbols_result = None
    if detect_symbols and not skip_vision:
        try:
            from .symbol_detector import detect_all_symbols_for_pdf
            # Pakeičiam page_classifications į formatą, kurį tikisi detect_all
            page_clas_for_sym = []
            for p in pages:
                page_clas_for_sym.append({
                    "page": p.get("page_nr") or p.get("page"),
                    "type": p.get("type", "unknown"),
                })
            detected_symbols_result = detect_all_symbols_for_pdf(
                pdf_bytes=pdf_bytes,
                page_classifications=page_clas_for_sym,
                max_pages_per_type=symbol_max_pages,
            )
            print(f"[V9] Symbol detection: "
                  f"{len(detected_symbols_result.get('by_type', {}))} types, "
                  f"{detected_symbols_result.get('stats', {}).get('api_calls', 0)} API calls, "
                  f"{detected_symbols_result.get('stats', {}).get('ms_total', 0)}ms")
        except Exception as e:
            print(f"[V9] symbol detection failed: {e}")
            detected_symbols_result = None

    # 5. V8 universal engine — industries kiekiai (su detected_symbols!)
    try:
        from interior_v8.universal_engine import extract_v8
        v8_result = extract_v8(
            rooms=all_v8_rooms,
            ceiling_height_m=2.82,
            rules_override=rules_override,
            detected_symbols=detected_symbols_result,
        )
    except Exception as e:
        return {
            "error": f"v8 engine failed: {e}",
            "engine": "v9_pipeline",
            "rooms_pre_v8": all_v8_rooms,
            "v9_meta": {
                "pages_processed": len(pages),
                "page_stats": page_stats,
                "ms_total": int((time.time() - t0) * 1000),
            },
        }

    # 6. LT sanity validation
    lt_sanity = None
    try:
        from interior_v8.lt_sanity import validate_v8_output
        lt_sanity = validate_v8_output(v8_result)
    except Exception as e:
        print(f"[V9] lt_sanity skip: {e}")

    # 7. Augmentuoti V8 rooms su V9 metadata (bbox, polygon, page_nr)
    # V8 grąžina rooms pagal eilę, bet gali pakeisti pavadinimą open_space atveju.
    # Pridedam V9 vector metadata.
    v8_rooms = v8_result.get("rooms", [])
    v9_meta_by_nr = {r["nr"]: r for r in all_v8_rooms}
    for vr in v8_rooms:
        nr = vr.get("nr")
        meta = v9_meta_by_nr.get(nr)
        if meta:
            vr["page_nr"] = meta.get("page_nr")
            vr["polygon_id"] = meta.get("polygon_id")
            vr["bbox_pct"] = meta.get("bbox_pct")
            vr["centroid_pct"] = meta.get("centroid_pct")
            vr["polygon_pdf"] = meta.get("polygon_pdf")
            # PDF page dims — frontend AiRoomOverlay reikia mappinti polygon_pdf → pikseliais
            vr["page_width_pdf"] = meta.get("page_width_pdf")
            vr["page_height_pdf"] = meta.get("page_height_pdf")
            vr["_vote_consensus"] = meta.get("_vote_consensus")

    return {
        **v8_result,
        "lt_sanity": lt_sanity,
        "detected_symbols": detected_symbols_result,
        "v9_meta": {
            "pages_processed": len(pages),
            "page_stats": page_stats,
            "polygons_total": sum(s.get("polygons", 0) for s in page_stats),
            "vision_passes": n_passes if not skip_vision else 0,
            "drawing_scale": drawing_scale,
            "scale_warnings": scale_warnings,
            "symbols_detected": (
                {st: info.get("total", 0)
                 for st, info in (detected_symbols_result or {}).get("by_type", {}).items()}
                if detected_symbols_result else {}
            ),
            "symbol_api_calls": (
                (detected_symbols_result or {}).get("stats", {}).get("api_calls", 0)
            ),
            "ms_total": int((time.time() - t0) * 1000),
        },
        "engine": "v9_pipeline",
    }

"""extractor.vision_call — single Vision call pipeline.

PDF bytes → base64 images → Claude Vision (streaming) → parsed JSON.
Canonical prompt from extractor.prompt (never modified here).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re as _re
import time
from pathlib import Path
from typing import Any

import anthropic
from pdf2image import convert_from_bytes

from .prompt import (
    SYSTEM_TEXT, build_user_content,
    ZOOM_SYSTEM_TEXT, build_zoom_user_content,
    MODEL, MAX_OUTPUT_TOKENS, DPI, MAX_PAGES, IMG_MAX_DIM,
    ZOOM_DPI, ZOOM_MAX_DIM, ZOOM_PADDING_PCT,
)

# Load ANTHROPIC_API_KEY from backend/.env if not already in environment
# parents[1] = backend/ (extractor/vision_call.py → extractor/ → backend/)
_env_file = Path(__file__).resolve().parents[1] / ".env"
if _env_file.exists() and not os.environ.get("ANTHROPIC_API_KEY"):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        pass


def pdf_to_b64_images(pdf_bytes: bytes,
                       max_pages: int = MAX_PAGES,
                       dpi: int = DPI) -> list[dict]:
    """Convert PDF → list of {page_index, image_b64} dicts (JPEG, capped at IMG_MAX_DIM)."""
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    out: list[dict] = []
    for i, img in enumerate(images[:max_pages], start=1):
        w, h = img.size
        scale = min(1.0, IMG_MAX_DIM / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append({
            "page_index": i,
            "image_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
        })
    return out


def _crop_room_image(
    pdf_bytes: bytes,
    page_number: int,
    bbox_pct: dict,
    target_dpi: int = ZOOM_DPI,
    max_dim: int = ZOOM_MAX_DIM,
    padding: float = ZOOM_PADDING_PCT,
) -> str | None:
    """Crop a region of a PDF page at high DPI for zoom-in re-read.

    Args:
        pdf_bytes: full PDF
        page_number: 1-indexed (matches Vision's puslapio_nr)
        bbox_pct: {x, y, w, h} in 0.0-1.0 fractions
        target_dpi: render DPI (300 = readable mm annotations)
        max_dim: cap long edge after crop (Opus 4.7 max 2576)
        padding: fractional padding around bbox (0.05 = 5%)
    Returns: JPEG b64 string of the cropped region, or None if crop fails.
    """
    try:
        # Render only the target page at high DPI
        pages = convert_from_bytes(
            pdf_bytes,
            dpi=target_dpi,
            fmt="jpeg",
            first_page=page_number,
            last_page=page_number,
        )
        if not pages:
            return None
        img = pages[0]
        W, H = img.size

        # Apply padding around bbox
        x = max(0.0, bbox_pct.get("x", 0) - padding)
        y = max(0.0, bbox_pct.get("y", 0) - padding)
        w = min(1.0 - x, bbox_pct.get("w", 1.0) + 2 * padding)
        h = min(1.0 - y, bbox_pct.get("h", 1.0) + 2 * padding)

        x0 = int(W * x)
        y0 = int(H * y)
        x1 = int(W * (x + w))
        y1 = int(H * (y + h))

        # Sanity: ensure minimum crop size
        if x1 - x0 < 50 or y1 - y0 < 50:
            return None

        crop = img.crop((x0, y0, x1, y1))
        cw, ch = crop.size
        scale = min(1.0, max_dim / max(cw, ch))
        if scale < 1.0:
            crop = crop.resize((int(cw * scale), int(ch * scale)))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:
        print(f"[extractor] crop_room_image failed (page={page_number}): {exc}")
        return None


def _vision_zoom_room(
    client: anthropic.Anthropic,
    cropped_b64: str,
    room: dict,
) -> dict | None:
    """Pass-2 zoom Vision call for one room. Returns ZoomResult dict or None."""
    system = [
        {"type": "text", "text": ZOOM_SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,  # zoom output is small per room
            system=system,
            messages=[{"role": "user", "content": build_zoom_user_content(cropped_b64, room)}],
            output_config={"effort": "high"},
        ) as stream:
            resp = stream.get_final_message()

        if resp.stop_reason in ("refusal", "max_tokens"):
            return None
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return json.loads(_repair_json(text))
            except json.JSONDecodeError:
                return None
    except Exception as exc:
        print(f"[extractor] zoom call failed for room {room.get('nr')}: {exc}")
        return None


def _apply_zoom_refinements(room: dict, zoom: dict) -> bool:
    """Merge zoom result into room dict (in-place). Returns True if changes applied."""
    if not zoom or zoom.get("confidence_zoom") == "low":
        return False
    changed = False

    # Perimetras: prefer high-confidence zoom value
    if zoom.get("perimetras_saltinis") == "from_zoom" and zoom.get("perimetras_m") is not None:
        old = room.get("perimetras_m")
        new = float(zoom["perimetras_m"])
        if abs(new - (old or 0)) > 0.1:  # only update if meaningful diff
            room["perimetras_m"] = new
            room.setdefault("_zoom_changes", []).append(f"perimetras: {old} → {new}")
            changed = True

    if zoom.get("plotas_saltinis") == "from_zoom" and zoom.get("plotas_m2") is not None:
        old = room.get("plotas_m2")
        new = float(zoom["plotas_m2"])
        if abs(new - (old or 0)) > 0.1:
            room["plotas_m2"] = new
            room["plotas_saltinis"] = "wall_dim_calc"  # zoom-derived
            room.setdefault("_zoom_changes", []).append(f"plotas: {old} → {new}")
            changed = True

    if zoom.get("lubu_aukstis_m") is not None:
        old = room.get("lubu_aukstis_m")
        new = float(zoom["lubu_aukstis_m"])
        if abs(new - (old or 0)) > 0.05:
            room["lubu_aukstis_m"] = new
            room.setdefault("_zoom_changes", []).append(f"lubu_aukstis: {old} → {new}")
            changed = True

    if zoom.get("plyteles_sienos_aukstis_m") is not None:
        room["plyteles_sienos_aukstis_m"] = float(zoom["plyteles_sienos_aukstis_m"])
        changed = True

    if zoom.get("nisu_metrai") is not None:
        old = room.get("nisu_metrai", 0)
        new = float(zoom["nisu_metrai"])
        if abs(new - old) > 0.1:
            room["nisu_metrai"] = new
            room.setdefault("_zoom_changes", []).append(f"nisu_metrai: {old} → {new}")
            changed = True

    # Store full zoom data for transparency
    room["_zoom"] = zoom
    return changed


def _repair_json(text: str) -> str:
    """Best-effort JSON repair: strip code fences, quote keys, drop trailing commas."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    # Quote unquoted keys
    text = _re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    # Drop trailing commas
    text = _re.sub(r',(\s*[}\]])', r'\1', text)
    return text


_VNT_NORMALIZE = {
    "m2": "m²",
    "m²": "m²",
    "m": "m",
    "b/m": "m",     # b/m = bėginis metras (linear), normalize to m for UI
    "vnt": "vnt",
    "kg": "kg",
    "l": "l",
    "kompl": "kompl",
}

_SKYRIUS_ENUM = {
    "GKP montavimas": "gkp",
    "Glaistymas dazymas": "paint",
    "Plyteles": "tile",
    "Hidroizoliacija": "waterproof",
    "Pridetiniai elementai": "extras",
    "Out of scope": "out_of_scope",
}


def _emit_v8_compat_fields(parsed: dict) -> dict:
    """Backwards-compat: emit V8-shape `darbu_sarasas`, `v8_totals`, `v8_rooms`.

    Frontend (ExportModal.jsx, ProjectMainView.jsx, WorkspacePanel.jsx) reads
    these fields. Without them, the kiekių žiniaraštis tab and Excel/PDF
    export show no works/materials. New `pozicijos[]` schema is preserved
    alongside.
    """
    pozicijos = parsed.get("pozicijos") or []
    darbu_sarasas = []
    for i, p in enumerate(pozicijos, start=1):
        skyrius = p.get("skyrius", "Pridetiniai elementai")
        vnt_raw = p.get("vnt", "vnt")
        vnt = _VNT_NORMALIZE.get(vnt_raw, vnt_raw)
        aprasymas = p.get("aprasymas", "")
        # Append `pastaba` to aprasymas if present (e.g. tile size detail)
        pastaba = p.get("pastaba")
        if pastaba:
            aprasymas = f"{aprasymas} ({pastaba})"
        darbu_sarasas.append({
            "eil_nr": i,
            "skyrius": skyrius,
            "skyrius_label": skyrius,
            "skyrius_enum": _SKYRIUS_ENUM.get(skyrius, "extras"),
            "aprasymas": aprasymas,
            "pavadinimas": aprasymas,
            "mato_vnt": vnt,
            "vnt": vnt,
            "kiekis": p.get("kiekis", 0),
            "saltinis": p.get("saltinis", ""),
        })
    parsed["darbu_sarasas"] = darbu_sarasas

    # v8_totals — mirrored santrauka with V8 key names
    s = parsed.get("santrauka") or {}
    parsed["v8_totals"] = {
        "bendras_plotas_m2": parsed.get("bendras_plotas_m2", 0),
        "dazymo_plotas_m2": s.get("dazymo_plotas_total_m2", 0),
        "kampai_m": s.get("kampai_m_total", 0),
        "angokrasciu_gkp_m": s.get("angokrasciu_gkp_m_total", 0),
        "pasleptu_duru_staktu_m": s.get("pasleptu_duru_staktu_m_total", 0),
        "nisu_metrai": s.get("nisu_metrai_total", 0),
        "gkp_lubu_standart_m2": s.get("gkp_lubu_m2_total", 0),
        "gkp_lubu_virs_3m_m2": s.get("gkp_lubu_virs_3m_m2_total", 0),
        "pvc_grindys_m2": s.get("pvc_grindys_m2_total", 0),
        "plyteles_grindys_m2": s.get("plyteles_grindys_m2_total", 0),
        "plyteles_sienos_m2": s.get("plyteles_sienos_m2_total", 0),
        "isliginamasis_m2": s.get("isliginamasis_m2_total", 0),
        "grindjuosciu_m": s.get("grindjuosciu_m_total", 0),
        "hidroizoliacijos_vnt": s.get("hidroizoliacijos_vnt", 0),
    }

    # v8_rooms — mirror patalpos with V8-friendly aliases (frontend has fallback)
    parsed["v8_rooms"] = parsed.get("patalpos", [])

    return parsed


def _recompute_santrauka(parsed: dict) -> dict:
    """Recompute santrauka from per-room values via calc_totals (single source of truth).

    The Vision model's santrauka field may have arithmetic errors.
    We replace it with our deterministic summation.
    """
    from .universal_rules import calc_totals

    rooms = parsed.get("patalpos", [])
    if not rooms:
        return parsed

    # Map Vision room fields to calc_totals expected fields
    mapped_rooms: list[dict] = []
    for r in rooms:
        mapped_rooms.append({
            "plotas_m2": r.get("plotas_m2", 0),
            "dazymo_plotas_m2": r.get("dazymo_plotas_m2", 0),
            "kampu_metrai": r.get("kampu_metrai", 0),
            "angokrasciu_gkp_m": r.get("angokrasciu_gkp_m", 0),
            "pasleptu_duru_staktu_m": r.get("pasleptu_duru_staktu_m", 0),
            "nisu_metrai": r.get("nisu_metrai", 0),
            "pvc_grindys_m2": r.get("pvc_grindys_m2", 0),
            "plyteles_grindys_m2": r.get("plyteles_grindys_m2", 0),
            "plyteles_sienos_m2": r.get("plyteles_sienos_m2", 0),
            "isliginamasis_m2": r.get("isliginamasis_m2", 0),
            "grindjuosciu_m": r.get("grindjuosciu_m", 0),
            "hidroizoliacija_m2": r.get("hidroizoliacija_m2", 0),
            "lubu_tipas": r.get("lubu_tipas", "gkp"),
            "lubu_aukstis_m": r.get("lubu_aukstis_m", 2.82),
            "paskirtis": r.get("paskirtis", "gyvenamoji"),
        })

    totals = calc_totals(mapped_rooms)

    # Build santrauka in Vision schema format
    parsed["santrauka"] = {
        "dazymo_plotas_total_m2": totals.get("dazymo_plotas_total_m2", 0),
        "kampai_m_total": totals.get("kampai_m_total", 0),
        "angokrasciu_gkp_m_total": totals.get("angokrasciu_gkp_m_total", 0),
        "pasleptu_duru_staktu_m_total": totals.get("pasleptu_duru_staktu_m_total", 0),
        "nisu_metrai_total": totals.get("nisu_metrai_total", 0),
        "gkp_lubu_m2_total": totals.get("gkp_lubu_m2_total", 0),
        "gkp_lubu_virs_3m_m2_total": totals.get("gkp_lubu_virs_3m_m2_total", 0),
        "pvc_grindys_m2_total": totals.get("pvc_grindys_m2_total", 0),
        "plyteles_grindys_m2_total": totals.get("plyteles_grindys_m2_total", 0),
        "plyteles_sienos_m2_total": totals.get("plyteles_sienos_m2_total", 0),
        "isliginamasis_m2_total": totals.get("isliginamasis_m2_total", 0),
        "grindjuosciu_m_total": totals.get("grindjuosciu_m_total", 0),
        "hidroizoliacijos_vnt": totals.get("hidroizoliacijos_vnt", 0),
    }
    return parsed


def extract_interior(pdf_bytes: bytes, rules_override: dict | None = None) -> dict:
    """Single Vision call entry point. PDF bytes → structured takeoff JSON.

    Args:
        pdf_bytes: Raw PDF bytes (single file)
        rules_override: Optional Setup Wizard preferences dict; attached to result
                        as _overrides for downstream UI use.
    Returns: parsed JSON dict with `patalpos`, `santrauka`, `pozicijos`, etc.
             On error returns {"_error": "...", "status": "error"}.
             On success returns {..., "status": "ok", "_meta": {...}}.
    """
    t0 = time.time()
    client = anthropic.Anthropic()

    system = [
        {"type": "text", "text": SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]

    # Step 1: PDF → base64 images
    try:
        pages = pdf_to_b64_images(pdf_bytes)
    except Exception as exc:
        return {
            "status": "error",
            "_error": f"pdf_to_images_failed: {exc}",
        }

    if not pages:
        return {
            "status": "error",
            "_error": "PDF has no renderable pages",
        }

    # Step 2: Vision call with retry (max 3 attempts)
    last_err: Exception | None = None
    parsed: dict | None = None

    for attempt in range(3):
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": build_user_content(pages)}],
                output_config={"effort": "high"},
            ) as stream:
                resp = stream.get_final_message()

            if resp.stop_reason == "refusal":
                return {
                    "status": "error",
                    "_error": "model_refused",
                    "_stop_reason": "refusal",
                }
            if resp.stop_reason == "max_tokens":
                return {
                    "status": "error",
                    "_error": "output_truncated",
                    "_stop_reason": "max_tokens",
                }

            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            )

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(_repair_json(text))
                    parsed["_repaired"] = True
                except json.JSONDecodeError as je:
                    return {
                        "status": "error",
                        "_error": "json_decode_failure",
                        "_raw_text": text[:4000],
                        "_je": str(je),
                    }

            usage = resp.usage
            parsed["_meta"] = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
                "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                "stop_reason": resp.stop_reason,
                "attempt": attempt + 1,
                "pages_sent": len(pages),
                "model": MODEL,
            }
            break  # success

        except Exception as exc:
            last_err = exc
            print(f"[extractor] attempt {attempt + 1} failed: {exc}")
            if attempt == 2:
                return {
                    "status": "error",
                    "_error": f"vision_call_failed: {exc}",
                }
            time.sleep(1.5 ** attempt)

    if parsed is None:
        return {
            "status": "error",
            "_error": str(last_err or "Unknown error"),
        }

    # Step 2.5: PASS-2 ZOOM — per-room high-res re-read for accurate dimensions.
    # User decision (2026-04-27): always-on best-path approach. Per kambarį
    # crop the page region at 300 DPI / 2576px max, send to Vision with room
    # context, ask for refined mm dimensions. Phase 6.5.2 showed determinism
    # is poor (CV 22-150%) on projects without eksplikacija; zoom should fix this.
    rooms = parsed.get("patalpos") or []
    zoom_count_attempted = 0
    zoom_count_applied = 0
    zoom_total_input_tok = 0
    zoom_total_output_tok = 0
    t_zoom_start = time.time()
    for room in rooms:
        bbox = room.get("bbox_pct")
        page_nr = room.get("puslapio_nr")
        if not bbox or not page_nr:
            continue
        cropped = _crop_room_image(pdf_bytes, page_nr, bbox)
        if not cropped:
            continue
        zoom_count_attempted += 1
        zoom_result = _vision_zoom_room(client, cropped, room)
        if not zoom_result:
            continue
        if _apply_zoom_refinements(room, zoom_result):
            zoom_count_applied += 1
    zoom_elapsed = round(time.time() - t_zoom_start, 1)
    parsed.setdefault("_meta", {})["zoom_attempted"] = zoom_count_attempted
    parsed["_meta"]["zoom_applied"] = zoom_count_applied
    parsed["_meta"]["zoom_elapsed_s"] = zoom_elapsed
    print(f"[extractor] zoom pass: {zoom_count_attempted} attempted, "
          f"{zoom_count_applied} applied, {zoom_elapsed}s")

    # Step 3: Recompute santrauka from per-room values (single source of truth)
    # NOTE: this runs AFTER zoom pass so totals reflect refined per-room dims.
    try:
        parsed = _recompute_santrauka(parsed)
    except Exception as exc:
        # Non-fatal: keep Vision's santrauka, add warning
        print(f"[extractor] santrauka recompute failed: {exc}")
        existing_warnings = parsed.get("warnings") or []
        existing_warnings.append({
            "level": "WARN",
            "message": f"Santrauka recompute klaida: {exc} — naudojama Vision santrauka",
        })
        parsed["warnings"] = existing_warnings

    # Step 4: Apply LT sanity checks (adds _lt_warnings, does NOT mutate values)
    try:
        from .lt_rules import apply_lt_sanity
        parsed = apply_lt_sanity(parsed)
    except Exception as exc:
        print(f"[extractor] lt_sanity failed: {exc}")

    # Step 4.5: Determinism warning — if no eksplikacija text was found, Vision
    # had to infer rooms from drawing dimensions alone, which has high run-to-run
    # variance per Phase 6.5.2 measurement (P2 sample: rooms CV 22.9%, plytelės CV
    # 153.8%; vs P3 with eksplikacija: rooms CV 2.8%, dažymas CV 4.2%).
    # Surface this so UI can display a "rezultatai gali svyruoti" hint.
    eksplikacija_page = parsed.get("eksplikacija_source_page")
    if not eksplikacija_page:
        existing = parsed.get("warnings") or []
        existing.append({
            "level": "INFO",
            "message": (
                "Šis projektas neturi rastos eksplikacijos lentelės. Rezultatai "
                "išvesti iš brėžinio matmenų ir gali svyruoti tarp paleidimų "
                "(±10–20% kambarių skaičiui, daugiau plytelių zonoms). "
                "Rekomenduojama peržiūrėti rankiniu būdu arba paleisti 2–3 kartus."
            ),
        })
        parsed["warnings"] = existing

    # Step 5: Frontend backwards-compat — emit V8-shape fields alongside new schema.
    # Frontend (ExportModal, ProjectMainView, WorkspacePanel) reads `darbu_sarasas`,
    # `v8_totals`, `v8_rooms`. Without these, the works/materials list and Excel/PDF
    # export are empty even though `pozicijos[]` is populated.
    try:
        parsed = _emit_v8_compat_fields(parsed)
    except Exception as exc:
        print(f"[extractor] v8_compat emit failed: {exc}")

    # Step 6: Attach rules_override for downstream UI use
    if rules_override is not None:
        parsed["_overrides"] = rules_override

    # Step 7: Finalize
    elapsed = round(time.time() - t0, 1)
    if "_meta" in parsed:
        parsed["_meta"]["elapsed_s"] = elapsed
    else:
        parsed["_meta"] = {"elapsed_s": elapsed}

    parsed["_elapsed_s"] = elapsed
    parsed["status"] = "ok"

    return parsed

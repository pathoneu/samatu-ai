"""extractor.vision_call — single Vision call pipeline.

PDF bytes → base64 images → Claude Vision (streaming) → parsed JSON.
Canonical prompt from extractor.prompt (never modified here).
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import re as _re
import time
from pathlib import Path
from typing import Any

import anthropic
from pdf2image import convert_from_bytes

from .prompt import (
    SYSTEM_TEXT, build_user_content, build_user_content_pdf_native,
    ZOOM_SYSTEM_TEXT, build_zoom_user_content,
    MAX_OUTPUT_TOKENS, DPI, MAX_PAGES, IMG_MAX_DIM,
    ZOOM_DPI, ZOOM_MAX_DIM, ZOOM_PADDING_PCT,
)
from models_config import model_for

_ENV_TRUTHY = {"1", "true", "yes", "on"}
_ENV_FALSY = {"0", "false", "no", "off"}


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in _ENV_TRUTHY


# B-3 lock-in (2026-07-04, docs/superpowers/research/2026-07-04-final-config-
# decision.md): native-PDF Pass-1 input is the PRODUCTION DEFAULT — best
# accuracy of every config tested (16.2% headline MAE) at raster cost.
# Rollback is this one line: set False to restore the raster default
# everywhere (env overrides still win in both directions).
NATIVE_PDF_DEFAULT_ON = True


def _pdf_native_mode() -> tuple[bool, str]:
    """Effective Pass-1 input mode + why. SAMATU_PDF_NATIVE=0/false is the
    escape hatch (forces raster images); =1/true forces native; unset/other
    → NATIVE_PDF_DEFAULT_ON. Returns (native_on, reason)."""
    raw = (os.getenv("SAMATU_PDF_NATIVE") or "").strip().lower()
    if raw in _ENV_FALSY:
        return False, f"env_override (SAMATU_PDF_NATIVE={raw})"
    if raw in _ENV_TRUTHY:
        return True, f"env_override (SAMATU_PDF_NATIVE={raw})"
    return (bool(NATIVE_PDF_DEFAULT_ON),
            f"default (NATIVE_PDF_DEFAULT_ON={NATIVE_PDF_DEFAULT_ON})")


def _pdf_native_enabled() -> bool:
    """Send Pass-1 pages as ONE native PDF `document` block (image +
    extracted text layer per page) instead of pdf2image-rendered image
    blocks. ON by default since the 2026-07-04 lock-in; see
    _pdf_native_mode for the override semantics."""
    return _pdf_native_mode()[0]


def _zoom_agentic_enabled() -> bool:
    """EXPERIMENT gate (SAMATU_ZOOM_AGENTIC=1): route the Pass-2 zoom re-read
    through the model-driven crop loop (extractor.agentic_crop) instead of
    the fixed-bbox crop. Default OFF — zero behavior change."""
    return _env_flag("SAMATU_ZOOM_AGENTIC")


def _mixed_voting_models() -> list[str] | None:
    """EXPERIMENT gate (SAMATU_VOTING_MODELS="m1,m2,m3"): one model PER voting
    round (list length = number of rounds). Unset/empty → None (default OFF)."""
    raw = (os.getenv("SAMATU_VOTING_MODELS") or "").strip()
    if not raw:
        return None
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or None


def _group_rounds_by_model(models: list[str]) -> list[str]:
    """Stable-group round models so same-model rounds run consecutively —
    prompt cache is per-model, so grouping maximizes cache hits (each model
    pays one cache write, its later rounds read). First-appearance order of
    distinct models is preserved."""
    order: list[str] = []
    for m in models:
        if m not in order:
            order.append(m)
    return [m for o in order for m in models if m == o]


def _append_extra_call(parsed: dict, reader_meta: dict | None) -> None:
    """Roll one sub-Vision call's tokens into ``parsed["_meta"]["extra_calls"]``
    so the SINGLE per-extraction usage_event prices the WHOLE pipeline, not
    just Pass-1 (2026-07-04 sub-call metering fix).

    ``reader_meta`` is a sub-reader's own ``_meta`` block (apdailos, doors, one
    door_type round, eksplikacija Vision fallback, a zoom call, an agentic-zoom
    room, sanitary fixtures …). Priced later by pricing.calc_meta_cost_usd,
    each entry at ITS OWN model's rate.

    Purely additive token/cost CAPTURE — never touches extraction output. No-op
    (nothing appended) when the call was free or didn't happen:
      * ``reader_meta`` falsy, or
      * no ``model`` (e.g. the pdfplumber eksplikacija path: source-only, $0), or
      * all token counts zero/None (reader errored before the API call).
    None token values (readers use ``getattr(usage, ..., None)``) coerce to 0.
    """
    if not reader_meta:
        return
    model = reader_meta.get("model")
    if not model:
        return  # free/deterministic path (no Anthropic call) — nothing to price
    in_t = int(reader_meta.get("input_tokens") or 0)
    out_t = int(reader_meta.get("output_tokens") or 0)
    cr_t = int(reader_meta.get("cache_read_tokens") or 0)
    cw_t = int(reader_meta.get("cache_write_tokens") or 0)
    if in_t == 0 and out_t == 0 and cr_t == 0 and cw_t == 0:
        return  # nothing billable
    parsed.setdefault("_meta", {}).setdefault("extra_calls", []).append({
        "model": model,
        "input_tokens": in_t,
        "output_tokens": out_t,
        "cache_read_tokens": cr_t,
        "cache_write_tokens": cw_t,
    })


def _reader_call_metas(result: dict | None) -> list[dict]:
    """Normalize a sub-reader result into a list of per-call ``_meta`` blocks.

    Voted readers (read_door_types_voted / read_fixtures_voted) made N Anthropic
    calls and expose every OK round under ``_round_metas`` — return all of them.
    Single-pass readers expose their one call under ``_meta``. An errored reader
    (no tokens billed) yields ``[]``. The caller appends each via
    _append_extra_call so every billed round is metered exactly once.
    """
    if not result:
        return []
    rounds = result.get("_round_metas")
    if rounds:
        return list(rounds)
    m = result.get("_meta")
    return [m] if m else []


# Anthropic hard request limit is 32 MB; leave headroom for system prompt +
# instruction text + JSON envelope. Above this the native-PDF experiment
# falls back to the image path for that extraction (recorded in _meta).
_PDF_NATIVE_MAX_B64_BYTES = 25 * 1024 * 1024

# B-2 lock-in condition (2026-07-04): text-richness gate. Native mode's edge
# over raster is the extracted text layer; Anthropic's internal PDF rendering
# is ~45% of our raster pixel budget, so a text-FREE native document is
# plausibly WORSE than our own raster images — and ungated evidence for that
# case doesn't exist (the one "text-free native ≈ raster" datapoint fell back
# via the size cap and never tested true native). Below this median we send
# raster images and record fallback_reason="text_free_pdf".
_PDF_NATIVE_MIN_MEDIAN_CHARS = 10


def _median_chars_per_page(pdf_bytes: bytes, page_indices: list[int]) -> float | None:
    """Median extractable-text length (chars) across the SELECTED 1-based
    pages, via pdfplumber (same text source page_filter.py uses; zero API
    cost). None → text layer unmeasurable (broken/unopenable PDF) — the
    caller proceeds and lets the pypdf subset build decide the fallback."""
    try:
        import statistics
        import pdfplumber
        counts: list[int] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n_src = len(pdf.pages)
            for idx in page_indices:
                if 1 <= int(idx) <= n_src:
                    try:
                        text = pdf.pages[int(idx) - 1].extract_text() or ""
                    except Exception:
                        text = ""
                    counts.append(len(text.strip()))
        if not counts:
            return None
        return round(float(statistics.median(counts)), 1)
    except Exception as exc:
        print(f"[experiment:native_pdf] text-richness scan failed "
              f"(gate skipped): {exc}")
        return None


def build_pdf_subset_b64(pdf_bytes: bytes, page_indices: list[int]) -> dict:
    """Split the source PDF to the given 1-based pages via pypdf and base64
    the subset. Returns {"b64", "n_pages", "page_indices", "b64_bytes"} on
    success or {"error": "..."} on failure (caller falls back to images)."""
    try:
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        n_src = len(reader.pages)
        used: list[int] = []
        for idx in page_indices:
            if 1 <= int(idx) <= n_src:
                writer.add_page(reader.pages[int(idx) - 1])
                used.append(int(idx))
        if not used:
            return {"error": "no_valid_pages"}
        buf = io.BytesIO()
        writer.write(buf)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return {"b64": b64, "n_pages": len(used), "page_indices": used,
                "b64_bytes": len(b64)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _prepare_native_pdf(pdf_bytes: bytes, pages: list[dict]) -> dict:
    """Build the native-PDF payload for Pass-1 (SAMATU_PDF_NATIVE=1).

    Returns either {"b64", "n_pages", "page_indices", "b64_bytes",
    "page_map_note", "text_median_chars_page"} (send as document block) or
    {"fallback_reason": ..., "text_median_chars_page": ...} (send image
    blocks; fallback recorded in _meta.experiment).

    text_median_chars_page is recorded on EVERY native-considered run
    (document or fallback) — it is the production segmentation metric for
    native-vs-raster accuracy analysis."""
    indices = [int(p["page_index"]) for p in pages]
    # B-2: text-richness gate BEFORE building the document payload.
    median_chars = _median_chars_per_page(pdf_bytes, indices)
    if median_chars is not None and median_chars < _PDF_NATIVE_MIN_MEDIAN_CHARS:
        print(f"[experiment:native_pdf] text-free PDF (median "
              f"{median_chars} chars/page < {_PDF_NATIVE_MIN_MEDIAN_CHARS}) "
              f"→ raster image mode")
        return {"fallback_reason": "text_free_pdf",
                "text_median_chars_page": median_chars}
    subset = build_pdf_subset_b64(pdf_bytes, indices)
    if subset.get("error"):
        print(f"[experiment:native_pdf] subset build failed → image fallback: "
              f"{subset['error']}")
        return {"fallback_reason": subset["error"],
                "text_median_chars_page": median_chars}
    if subset["b64_bytes"] > _PDF_NATIVE_MAX_B64_BYTES:
        print(f"[experiment:native_pdf] WARNING: subset b64 is "
              f"{subset['b64_bytes'] / 1e6:.1f} MB > "
              f"{_PDF_NATIVE_MAX_B64_BYTES / 1e6:.0f} MB — falling back to "
              f"image mode for this call")
        return {"fallback_reason": "subset_exceeds_size_limit",
                "b64_bytes": subset["b64_bytes"],
                "text_median_chars_page": median_chars}
    # When the subset renumbers pages (vendor pages dropped mid-document),
    # tell the model the document→original mapping so puslapio_nr stays in
    # ORIGINAL numbering (zoom crops render from the original PDF).
    note = None
    if subset["page_indices"] != list(range(1, subset["n_pages"] + 1)):
        pairs = ", ".join(
            f"{doc_nr}={orig_nr}"
            for doc_nr, orig_nr in enumerate(subset["page_indices"], start=1)
        )
        note = (
            "Puslapių numeracija: šio dokumento puslapiai atitinka originalaus "
            f"brėžinių PDF puslapius taip (dokumento=originalus): {pairs}. "
            "Visuose `puslapio_nr` laukuose naudok ORIGINALŲ puslapio numerį."
        )
    return {**subset, "page_map_note": note,
            "text_median_chars_page": median_chars}

# Heavy vision turns on Fable 5 can run many minutes — per-call timeout
# override on the pass-1 stream (do NOT change the global client).
VISION_TIMEOUT_S = 600.0

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
) -> tuple[dict | None, dict]:
    """Pass-2 zoom Vision call for one room.

    Returns ``(zoom_result_or_None, zoom_meta)``. The zoom_result dict is the
    ZoomResult schema, UNCHANGED (no token keys injected — it is stored verbatim
    in ``room["_zoom"]`` for the UI, so mutating it would change extraction
    output). ``zoom_meta`` carries this call's token usage + model so the caller
    can roll it into ``_meta.extra_calls`` — before 2026-07-04 ``resp.usage``
    was discarded and every zoom call went unmetered.
    """
    model = model_for("vision_pass2")
    zoom_meta: dict = {"model": model, "input_tokens": 0, "output_tokens": 0,
                       "cache_read_tokens": 0, "cache_write_tokens": 0}
    system = [
        {"type": "text", "text": ZOOM_SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]
    try:
        with client.messages.stream(
            model=model,
            max_tokens=4096,  # zoom output is small per room
            system=system,
            messages=[{"role": "user", "content": build_zoom_user_content(cropped_b64, room)}],
            # Zoom is a dimension RE-READ (perception), not reasoning — medium is
            # the Opus 4.8 sweet spot here and cuts the ~96s-for-1-applied cost.
            # (Watch: if any perimeter/ceiling moves vs effort=high, revert.)
            output_config={"effort": "medium"},
        ) as stream:
            resp = stream.get_final_message()

        usage = getattr(resp, "usage", None)
        if usage is not None:
            zoom_meta["input_tokens"] = int(getattr(usage, "input_tokens", 0) or 0)
            zoom_meta["output_tokens"] = int(getattr(usage, "output_tokens", 0) or 0)
            zoom_meta["cache_read_tokens"] = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
            zoom_meta["cache_write_tokens"] = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        if resp.stop_reason in ("refusal", "max_tokens"):
            return None, zoom_meta
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        try:
            return json.loads(text), zoom_meta
        except json.JSONDecodeError:
            try:
                return json.loads(_repair_json(text)), zoom_meta
            except json.JSONDecodeError:
                return None, zoom_meta
    except Exception as exc:
        print(f"[extractor] zoom call failed for room {room.get('nr')}: {exc}")
        return None, zoom_meta


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
    "m3": "m3",     # m³ for šiukšlių išvežimas, betonas etc.
    "d.d": "d.d",   # d.d = darbo diena (pastolių nuoma)
}

_SKYRIUS_ENUM = {
    # Modern LT-correct keys (with diacritics)
    "GKP montavimas": "gkp",
    "Sienų lubų glaistymas dažymas": "paint",
    "Plytelių klijavimas": "tile",
    "Hidroizoliacija": "waterproof",
    "Grindys": "floor",
    "Santechnikos darbai": "plumbing",
    "Elektros instaliacijos darbai": "electrical",
    "Pridėtiniai elementai": "extras",
    "Out of scope": "out_of_scope",
    # Legacy ASCII-stripped keys (mojibake from earlier exports) — preserved
    # so projects saved with old skyrius names still classify correctly.
    "Glaistymas dazymas": "paint",
    "Plyteles": "tile",
    "Pridetiniai elementai": "extras",
    "Santechnikos darbai/ kondicionavimo darbai": "plumbing",
}

# Legacy → modern skyrius name migration. Used both in _emit_v8_compat_fields
# (server) and frontend localStorage on project load.
# Sprint §FIX-2 (2026-04-29): expanded with GKP/glaistymas variants found in old
# extractions — user reported 3 separate "GKP montavimas" groups in UI from these.
SKYRIUS_LEGACY_MIGRATION = {
    "Glaistymas dazymas": "Sienų lubų glaistymas dažymas",
    "Glaistymas dažymas": "Sienų lubų glaistymas dažymas",
    "Sienų glaistymas dažymas": "Sienų lubų glaistymas dažymas",
    "Plyteles": "Plytelių klijavimas",
    "Plytelių darbai": "Plytelių klijavimas",
    "Pridetiniai elementai": "Pridėtiniai elementai",
    "Santechnikos darbai/ kondicionavimo darbai": "Santechnikos darbai",
    "Elektros instaliacijos darbai/ apsvietimas": "Elektros instaliacijos darbai",
    "Grindu darbai": "Grindys",
    "Grindų darbai": "Grindys",
    "Grindų danga": "Grindys",
    # GKP variants — all collapse to the canonical "GKP montavimas"
    "GKP": "GKP montavimas",
    "GKP konstrukcija": "GKP montavimas",
    "GKP karkas": "GKP montavimas",
    "Gipso kartono montavimas": "GKP montavimas",
    "Gipsokartono montavimas": "GKP montavimas",
    "GKP lubu montavimas": "GKP montavimas",
    "GKP lubų montavimas": "GKP montavimas",
}


def normalize_skyrius(skyrius: str | None) -> str:
    """Normalize a skyrius string to its canonical form. Used by frontend
    via /api/projects pipeline + by _build_pozicijos_from_rooms ensure no
    duplicate groups appear in UI for the same logical category."""
    if not skyrius:
        return "Kiti darbai"
    s = str(skyrius).strip()
    return SKYRIUS_LEGACY_MIGRATION.get(s, s)


def _apply_wall_elevation_tile_override(parsed: dict) -> int:
    """Sprint §35 (2026-04-29): when _wall_elevations data exists with
    mm-precision tile zones, override paskirtis-based plyteles_sienos_m2
    estimate per room.

    Formula (CLAUDE.md §1.7 polygon-based variant):
        tile_area = Σ (to_floor_mm − from_floor_mm) × wall_total_width_mm / 1e6

    Sprint §AUDIT (2026-04-29): match by `nr` first (unique), then fall back
    to `room_name` only when no nr collision exists. Previously matched purely
    by lowercase name → "Vonia 1" + "Vonia 2" both with `pavadinimas="Vonia"`
    got the same wall data applied to both → inflated counts.

    Returns count of rooms updated. Non-mutating where data missing.
    Adds lt_sanity warning when ambiguous name match attempted.
    """
    elevations = parsed.get("_wall_elevations") or []
    if not elevations:
        return 0
    rooms = parsed.get("patalpos") or []
    if not rooms:
        return 0

    # Group elevations by nr (preferred) AND by normalized room name (fallback).
    by_nr: dict[str, list[dict]] = {}
    by_name: dict[str, list[dict]] = {}
    for e in elevations:
        nr_key = str(e.get("nr") or e.get("room_nr") or "").strip()
        name_key = (e.get("room_name") or "").strip().lower()
        if nr_key:
            by_nr.setdefault(nr_key, []).append(e)
        if name_key:
            by_name.setdefault(name_key, []).append(e)

    # Detect duplicate room names — when two patalpos share the same name,
    # name-based matching is ambiguous and we'd apply the same walls twice.
    from collections import Counter
    name_counts = Counter(
        (r.get("pavadinimas") or "").strip().lower() for r in rooms
    )
    ambiguous_names = {n for n, c in name_counts.items() if c > 1}

    updated = 0
    warnings = parsed.setdefault("_lt_warnings", [])
    for r in rooms:
        nr_key = str(r.get("nr") or "").strip()
        name = (r.get("pavadinimas") or "").strip().lower()

        walls = by_nr.get(nr_key) if nr_key else None
        if not walls:
            # Fallback to name match — but only if name is unambiguous
            if name in ambiguous_names:
                warnings.append({
                    "level": "WARN",
                    "field": "plyteles_sienos_m2",
                    "patalpa_nr": r.get("nr"),
                    "message": (
                        f"Patalpa „{r.get('pavadinimas','?')}" + f"" + f"" +
                        f" (Nr. {r.get('nr','?')}) — wall_elevation duomenys praleisti, " +
                        f"nes pavadinimas dubliuojasi tarp kelių patalpų. Pridėk unikalų " +
                        f"`nr` lauką wall_elevation entry'jėje."
                    ),
                })
                continue
            walls = by_name.get(name)

        if not walls:
            continue

        total_tile_m2 = 0.0
        for w in walls:
            wall_w_mm = w.get("wall_total_width_mm") or 0
            if not wall_w_mm:
                continue
            for tz in (w.get("tile_zones") or []):
                from_mm = tz.get("from_floor_mm") or 0
                to_mm = tz.get("to_floor_mm") or 0
                height_mm = max(0, to_mm - from_mm)
                if height_mm > 0:
                    total_tile_m2 += (height_mm * wall_w_mm) / 1_000_000.0

        # Override existing estimate. Round to 0.01 m² for sąmata sanity.
        prior = r.get("plyteles_sienos_m2")
        r["plyteles_sienos_m2"] = round(total_tile_m2, 2)
        r["_plyteles_sienos_m2_source"] = "wall_elevation_mm"
        # 2026-06-01: also expose as `_tile_area_from_elevation_m2` so
        # universal_rules.py can compute walls_paintable = walls_gross
        # - openings - tile_area without going through walls_paint_factor.
        # This is the bridge that lets paint-above-tile work per-room.
        r["_tile_area_from_elevation_m2"] = round(total_tile_m2, 2)
        if prior is not None and prior != r["plyteles_sienos_m2"]:
            r["_plyteles_sienos_m2_prior"] = round(prior, 2)
        updated += 1

    if updated > 0:
        print(f"[extractor] wall_elevation override applied to {updated}/{len(rooms)} rooms")
    return updated


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
        skyrius_raw = p.get("skyrius", "Pridėtiniai elementai")
        # P7: Migrate legacy ASCII-stripped keys to modern LT-with-diacritics
        skyrius = SKYRIUS_LEGACY_MIGRATION.get(skyrius_raw, skyrius_raw)
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
            # Sprint D Track 1 — medžiagos embedded į work line (LT convention)
            "medziagos_aprasymas": p.get("medziagos_aprasymas"),
            "medziagos_kiekis": p.get("medziagos_kiekis"),
            "medziagos_vnt": p.get("medziagos_vnt"),
            # 2026-06-14: carry per-line confidence (zalia/geltona/raudona) + its
            # Lithuanian reason into the V8-compat shape so the UI can surface
            # which quantities to double-check, regardless of whether it renders
            # `pozicijos` or `darbu_sarasas`.
            "confidence": p.get("confidence"),
            "_confidence_reason": p.get("_confidence_reason"),
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


def _elementai_to_counts(elementai: list) -> dict:
    """Translate Vision-emitted elementai[] into the n_doors/n_windows/area
    fields that calc_room_quantities expects.

    elementai = [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000}, ...]
    Returns {"n_doors", "n_windows", "door_area_m2", "window_area_m2",
             "n_niches", "niche_lengths_m"}
    """
    n_doors, n_windows, n_niches = 0, 0, 0
    n_exterior_doors, n_exterior_windows = 0, 0
    door_areas, window_areas, niche_lengths = [], [], []
    for el in (elementai or []):
        tipas = (el.get("tipas") or "").lower()
        kiekis = int(el.get("kiekis") or 1)
        plotis_mm = el.get("plotis_mm") or 0
        aukstis_mm = el.get("aukstis_mm") or 0
        ilgis_m = el.get("ilgis_m") or 0
        is_exterior = bool(el.get("_exterior"))
        area_m2 = (plotis_mm * aukstis_mm / 1_000_000) if (plotis_mm and aukstis_mm) else 0

        if tipas in ("duris", "pasleptos_duris"):
            n_doors += kiekis
            if is_exterior:
                n_exterior_doors += kiekis
            if area_m2 > 0:
                door_areas.extend([area_m2] * kiekis)
        elif tipas in ("langas", "stoglangis"):
            n_windows += kiekis
            if is_exterior:
                n_exterior_windows += kiekis
            if area_m2 > 0:
                window_areas.extend([area_m2] * kiekis)
        elif tipas == "nisa_led":  # `.lower()` was applied above
            n_niches += kiekis
            if ilgis_m:
                niche_lengths.extend([ilgis_m] * kiekis)

    return {
        "n_doors": n_doors,
        "n_windows": n_windows,
        "n_exterior_doors": n_exterior_doors,
        "n_exterior_windows": n_exterior_windows,
        # Use mean per-element area when present so calc_room_quantities can scale
        # by n. If absent, calc_room_quantities falls back to UNIVERSAL_RULES defaults.
        "door_area_m2": (sum(door_areas) / len(door_areas)) if door_areas else None,
        "window_area_m2": (sum(window_areas) / len(window_areas)) if window_areas else None,
        "n_niches": n_niches,
        "niche_lengths_m": niche_lengths,
    }


# Q-glaisto consumption coefficients (CLAUDE.md §1.11). kg per m² per mm thickness.
_Q_GLAISTAS_KG_PER_M2_MM = {"Q1": 0.8, "Q2": 1.0, "Q3": 1.2, "Q4": 1.5}
# Default putty thickness per Q level (mm). Conservative center of CLAUDE.md range.
# Q4 corrected 2026-04-28: full-surface skim per Merkblatt Nr.2 needs 3-5mm
# (every 0.1mm imperfection visible under gloss paint). Prior 2.5mm under-quoted
# premium projects. Source: Bundesverband der Gipsindustrie + DIN 18181/18363.
_Q_GLAISTAS_THICKNESS_MM = {"Q1": 0.75, "Q2": 1.25, "Q3": 1.75, "Q4": 4.0}
# Q4 sanding labor norm (h/m²). 80-120 grit, 100% surface coverage.
_Q4_SANDING_HOURS_PER_M2 = 0.30
# Paint coverage per liter per coat (m²/l). CLAUDE.md §1.10.
_PAINT_COVERAGE_M2_PER_L = 9.0  # smooth Q2-Q3 surface, 1 coat baseline (Class 2)
# 2-coat multiplier (first coat absorbs more — 1.8× not 2.0×). CLAUDE.md §1.10.
_PAINT_TWO_COAT_FACTOR = 1.8

# Paint class profiles (Sprint §2A.5, 2026-04-28).
# Source: Tikkurila Optiva, Caparol CapaSol TI sheets + EN 13300 paint classes.
# Class 1 — top-quality opaque (Tikkurila Joker, Sikkens Aplhorn): high-hide,
#           1 coat sufficient on prepared/painted substrate.
# Class 2 — standard interior (Sikkens Alpha Matt, Dulux Easycare, Sniezka):
#           the LT residential default. 2 coats with 1.8× first-coat factor.
# Class 3 — economy / fresh-plaster substrate / rough textured walls:
#           more absorbent, requires 3 coats; lower coverage per liter.
_PAINT_CLASS_PROFILES = {
    1: {"coverage_m2_per_l": 10.0, "coats": 1, "absorption_factor": 1.0},
    2: {"coverage_m2_per_l": 9.0,  "coats": 2, "absorption_factor": 1.8},
    3: {"coverage_m2_per_l": 7.5,  "coats": 3, "absorption_factor": 2.5},
}
_PAINT_CLASS_DEFAULT = 2


def _calc_glaistas_kg(dazymo_plotas_m2: float, q_level: str = "Q2") -> float:
    """LT vidaus apdailos glaisto kiekis pagal Q kokybės lygį.

    Formula (CLAUDE.md §1.11): kg = plotas × storis_mm × Q_koef
    Q1 (po sunkių tapetų) = 0.5-1mm × 0.8 kg/m²/mm
    Q2 (po matinio dažymo) = 1-1.5mm × 1.0
    Q3 (po pusiau blizgaus) = 1.5-2mm × 1.2
    Q4 (po blizgaus/lakuoto) = 2-3mm × 1.5
    """
    coef = _Q_GLAISTAS_KG_PER_M2_MM.get(q_level, 1.0)
    thickness = _Q_GLAISTAS_THICKNESS_MM.get(q_level, 1.25)
    return round(dazymo_plotas_m2 * thickness * coef, 2)


def _calc_dazai_liters(dazymo_plotas_m2: float, coats: int = 2,
                        paint_class: int | None = None) -> float:
    """Dažų kiekis litrais (CLAUDE.md §1.10, Sprint §2A.5).

    Formula: l = plotas × absorption_factor / coverage_m²/l

    paint_class (1/2/3) ima pirmenybę prieš coats parametrą — pasiutimo už
    coats reikšmės profile'as nustato visus tris parametrus (coats,
    coverage, absorption_factor). Coats parametras paliktas backward-compat
    (kviečiantieji be paint_class).

    Class 1: 10 m²/L × 1 coat (top opaque, prepared substrate).
    Class 2: 9 m²/L × 2 coats × 1.8 absorption (LT default).
    Class 3: 7.5 m²/L × 3 coats × 2.5 absorption (rough/fresh plaster).
    """
    if paint_class is not None:
        prof = _PAINT_CLASS_PROFILES.get(int(paint_class)) \
            or _PAINT_CLASS_PROFILES[_PAINT_CLASS_DEFAULT]
        return round(dazymo_plotas_m2 * prof["absorption_factor"]
                     / prof["coverage_m2_per_l"], 2)
    # Legacy path: coats only.
    factor = _PAINT_TWO_COAT_FACTOR if coats >= 2 else 1.0
    return round(dazymo_plotas_m2 * factor / _PAINT_COVERAGE_M2_PER_L, 2)


def _resolve_paint_class_from_prefs(rules_or_overrides: dict | None) -> int:
    """Read paint_class (1/2/3) from user prefs (Setup Wizard / Prielaidos).
    Falls back to LT default = 2. Accepts both raw user prefs and the
    translated rules dict (`_paint_class` meta key)."""
    if not rules_or_overrides or not isinstance(rules_or_overrides, dict):
        return _PAINT_CLASS_DEFAULT
    val = rules_or_overrides.get("_paint_class") or rules_or_overrides.get("paint_class")
    try:
        cls = int(val) if val is not None else _PAINT_CLASS_DEFAULT
    except (ValueError, TypeError):
        cls = _PAINT_CLASS_DEFAULT
    return cls if cls in (1, 2, 3) else _PAINT_CLASS_DEFAULT


def _resolve_paint_class(user_default: int, inferred: int | None,
                         inferred_text: str | None) -> tuple[int, str]:
    """Sprint 0 Fix 5: prefer paint class inferred from spec text,
    falling back to user wizard default. Returns (class, source_label).
    """
    from extractor.feature_flags import get_flags
    flag_on = get_flags()["paint_class_inference"]
    if flag_on and inferred is not None:
        return int(inferred), "inferred_from_spec"
    return int(user_default), "user_default"


# Lubų karnizas dedamas TIK gyvenamose patalpose su dekoratyvinėm lubom
# (svetainė, miegamasis, valgomasis, koridorius, holas, kabinetas, drabuzine,
# rubine). NEDEDAMAS: vonia/WC (pakabinamos lubos), garažas/tambūras/sandėliukas
# (utilitarinės — be dekoro), katiline/skalbykla (be apdailos).
_KARNIZAS_PASKIRTYS = {
    "gyvenamoji", "miegamoji", "valgomasis", "koridorius",
    "holas", "kabinetas", "drabuzine", "rubine",
}


def _calc_lubu_karnizas_m(perim: float, paskirtis: str = "") -> float:
    """Lubų karnizas (cornice). CLAUDE.md §1.4: perimetras + 5% atliekų,
    durys NEATIMAMOS (priešingai nei grindjuostės).

    BET tik gyvenamosioms patalpoms su dekoratyvinėm lubom — ne vonioms,
    garažams, ne katilinei. Praktinis LT samatininko convention'as.
    """
    if (paskirtis or "").lower() not in _KARNIZAS_PASKIRTYS:
        return 0.0
    return round(perim * 1.05, 2)


def _calc_nisu_metrai_m(elementai: list) -> float:
    """LED nišų (užuolaidų niches) bendras ilgis. CLAUDE.md §1.5.

    ilgis_m = TOTAL niche length in this room across all segments.
    kiekis is NOT used as a multiplier for nisa_LED (semantics were
    ambiguous and Vision occasionally returned kiekis=3, ilgis_m=15
    meaning "3 segments totaling 15 m" — which got multiplied to 45 m).

    Fallback path (no ilgis_m, only plotis_mm) keeps kiekis as a multiplier
    because plotis_mm is per-window and naturally pairs with a count.
    """
    total = 0.0
    for el in (elementai or []):
        if (el.get("tipas") or "").lower() == "nisa_led":
            ilgis = float(el.get("ilgis_m") or 0)
            if ilgis > 0:
                total += ilgis  # ilgis_m is total per room — do NOT multiply by kiekis
            else:
                kiekis = int(el.get("kiekis") or 1)
                plotis_mm = float(el.get("plotis_mm") or 0)
                if plotis_mm > 0:
                    total += (plotis_mm / 1000 + 0.40) * kiekis
    return round(total, 2)


def _calc_hidroizoliacija_m2(room: dict, perim: float) -> float:
    """LT STR 2.04.01:2018 — vonios/WC/san. mazgo hidroizoliacija.

    grindys: pilnas plotas
    sienos: perimetras × 0.30 m (drėgmės zona) + dušo zona × lubų aukštis (jei dušas)

    Šitas paprastas variantas sumuoja grindis + perim × 0.30. Dušo zona
    pridedama jei pastabose minimas „dušas"/„shower" arba paskirtis vonia.
    """
    paskirtis = (room.get("paskirtis") or "").lower()
    if paskirtis not in ("vonia", "wc", "san", "skalbykla"):
        return 0.0
    plotas = float(room.get("plotas_m2") or 0)
    H = float(room.get("lubu_aukstis_m") or 2.82)
    drėgmės_zona = perim * 0.30
    # Dušas: priimam 1.0 × 1.2 m zoną iki lubų aukščio (apytiksliai)
    has_shower = paskirtis in ("vonia", "san")
    dušo_zona = (1.0 * 2 + 1.2) * H if has_shower else 0  # perimetras × H
    return round(plotas + drėgmės_zona + dušo_zona, 2)


def _recompute_per_room_via_python(parsed: dict, rules_override: dict | None) -> dict:
    """Replace Vision-computed per-room totals with Python-computed deterministic
    values (2026-04-28 deterministic refactor).

    Vision returns ONLY primitives (plotas, perimetras, lubu_aukstis, elementai,
    paskirtis). This function uses those primitives + universal_rules to compute
    every derived quantity (dazymo_plotas, kampu, plyteles_sienos/grindys,
    grindjuostes, hidroizoliacija, GK lubos).

    Same primitives → same output, every run. No Vision arithmetic drift.
    """
    from .universal_rules import calc_room_quantities, translate_user_prefs_to_room_rules

    rules = translate_user_prefs_to_room_rules(rules_override or {})
    rooms = parsed.get("patalpos") or []
    for room in rooms:
        # 1. Parse elementai → counts/areas the calc function understands
        counts = _elementai_to_counts(room.get("elementai") or [])
        # Inject into a working dict (don't mutate primitives)
        calc_input = {
            **room,
            **counts,
        }
        # 2. Compute deterministic per-room quantities
        try:
            computed = calc_room_quantities(calc_input, rules=rules)
        except Exception as exc:
            print(f"[extractor] calc_room_quantities failed for room {room.get('nr')}: {exc}")
            continue

        # 3. Merge — primitives win (already in room), computed overrides everything else.
        # Keep Vision-emitted primitives untouched; overwrite computed fields.
        PRIMITIVE_KEYS = {
            "nr", "pavadinimas", "paskirtis", "puslapio_nr", "bbox_pct",
            "plotas_m2", "plotas_saltinis", "plotas_m2_raw",
            "perimetras_m", "perimetras_m_raw",
            "lubu_aukstis_m", "lubu_aukstis_saltinis", "lubu_aukstis_m_raw",
            "lubu_tipas", "elementai", "confidence", "pastabos",
            "eksplikacija_row_idx",
            "eksplikacija_row_bbox",
            "eksplikacija_page_width_pdf",
            "eksplikacija_page_height_pdf",
            "_zoom", "_zoom_changes",
            # Per-room calculator overrides (Phase-3 calculator scope fixes,
            # 2026-05-31). These are sourced from contractor truth files or
            # downstream Vision passes (elevation/schedule); preserve them
            # through the merger so calc_room_quantities can read them on
            # subsequent recomputes (gestures, calibration, etc.).
            "walls_paint_factor_override", "tile_floor_override",
            "extra_walls_m2", "extra_walls_virs_3m_m2",
            "high_ceiling_area_m2",
            "plyteles_grindys_m2_override",
            "gkp_extra_area_m2",
            "n_exterior_doors", "n_exterior_windows",
            "count_partition_corners",
            # 2026-06-01 paint-above-tile systemic fix
            "_bathroom_paint_above_tile_m",
            "_tile_area_from_elevation_m2",
            "_plyteles_sienos_m2_source",
        }
        for k, v in computed.items():
            if k not in PRIMITIVE_KEYS:
                room[k] = v

        # 4. Hidroizoliacija (not in calc_room_quantities; CLAUDE.md §1.12)
        perim = float(room.get("perimetras_m") or 0)
        room["hidroizoliacija_m2"] = _calc_hidroizoliacija_m2(room, perim)

        # 4.1 Glaistas (kg) per Q-level (rules_override.glaistas_q_lygis if set)
        q_lygis = (rules_override or {}).get("glaistas_q_lygis", "Q2")
        dazymo = float(room.get("dazymo_plotas_m2") or 0)
        room["glaistas_kg"] = _calc_glaistas_kg(dazymo, q_lygis)

        # 4.2 Dažai (litrai) — paint class drives coats × coverage (Sprint §2A.5).
        paint_class = _resolve_paint_class_from_prefs(rules_override)
        room["dazai_l"] = _calc_dazai_liters(dazymo, paint_class=paint_class)
        room["_paint_class"] = paint_class  # surface to UI / debug

        # 4.3 Gruntas (litrai) — 1 coat at lower coverage (~7 m²/l)
        room["gruntas_l"] = round(dazymo / 7.0, 2) if dazymo > 0 else 0.0

        # 4.4 Lubų karnizas (cornice) — perim + 5%, no door deduct,
        # only for living-quality rooms (not vonia/garažas/utility)
        room["lubu_karnizo_m"] = _calc_lubu_karnizas_m(
            perim, room.get("paskirtis", ""))

        # 4.5 LED nišų metrai
        room["nisu_metrai"] = _calc_nisu_metrai_m(room.get("elementai") or [])

        # 5. Audit field
        room["_computed_by"] = "python_deterministic"
        # 6. Calculation trace (human-readable for RoomCard)
        H = float(room.get("lubu_aukstis_m") or 2.82)
        perim = float(room.get("perimetras_m") or 0)
        n_doors = counts["n_doors"]
        n_windows = counts["n_windows"]
        room["calculation_trace"] = (
            f"perim({perim:.2f}) × H({H:.2f}) = {perim * H:.2f} m² "
            f"− {n_windows} lang./{n_doors} dur. atimimai → "
            f"dažymas {room.get('dazymo_plotas_m2', 0):.2f} m². "
            f"Skaičiavo Python (deterministinis)."
        )
    return parsed


def build_gkp_pozicijos(rooms: list[dict]) -> list[dict]:
    """Build GKP pozicijos rows: separate wall (12.5mm) and ceiling (9.5mm) lines.

    Input contract:
      rooms — list of room dicts each with:
        sienos_gkp_m2  — wall drywall area (12.5mm sheets)
        lubos_gkp_m2   — ceiling drywall area (9.5mm sheets)

    Sprint 0 Fix 1 — audit Fix 1 from spec §7.
    Previously emitted a single hardcoded "GKP lapai (12.5 mm)" line for all
    GKP (ceiling + wall combined). Now emits separate lines using the correct
    thickness constants from UNIVERSAL_RULES.
    """
    from .universal_rules import UNIVERSAL_RULES

    SHEET = UNIVERSAL_RULES["drywall_sheet_area_m2"]          # 3.0 m²
    WASTE = 1.10
    wall_thickness = UNIVERSAL_RULES["drywall_thickness_walls_mm"]      # 12.5
    ceil_thickness = UNIVERSAL_RULES["drywall_thickness_ceilings_mm"]   # 9.5

    walls_total = sum(float(r.get("sienos_gkp_m2") or 0) for r in rooms)
    ceilings_total = sum(float(r.get("lubos_gkp_m2") or 0) for r in rooms)

    # Constants used in pozicijos rows — mirror module-level naming in the caller
    _SK_GKP = "GKP montavimas"
    _SAL = "skaiciuota_is_brezinio"

    pozicijos = []
    if walls_total > 0:
        wall_sheets = math.ceil(walls_total / SHEET * WASTE)
        pozicijos.append({
            "skyrius": _SK_GKP,
            "aprasymas": f"GKP lapai sienoms ({wall_thickness} mm)",
            "vnt": "vnt", "kiekis": wall_sheets, "saltinis": _SAL,
            "medziagos_aprasymas": "GKP lapas 1200×2500 mm = 3 m²",
            "medziagos_kiekis": wall_sheets, "medziagos_vnt": "vnt",
        })
    if ceilings_total > 0:
        ceil_sheets = math.ceil(ceilings_total / SHEET * WASTE)
        pozicijos.append({
            "skyrius": _SK_GKP,
            "aprasymas": f"GKP lapai luboms ({ceil_thickness} mm)",
            "vnt": "vnt", "kiekis": ceil_sheets, "saltinis": _SAL,
            "medziagos_aprasymas": "GKP lapas 1200×2500 mm = 3 m²",
            "medziagos_kiekis": ceil_sheets, "medziagos_vnt": "vnt",
        })
    return pozicijos


def _apply_per_room_heights(rooms: list[dict], per_room: dict[str, float],
                            section_average: float,
                            name_key: str = "name") -> list[dict]:
    """Sprint 0 Fix 4: use Vision's per-room ceiling heights when available
    and the flag is enabled; otherwise apply section average to all rooms.

    Returns a NEW list of room dicts (not in-place mutation).

    name_key: which dict key holds the room name. Defaults to "name" for
    test compatibility; production uses "pavadinimas" (LT convention).
    """
    from extractor.feature_flags import get_flags
    flag_on = get_flags()["per_room_ceiling"]
    out = []
    for r in rooms:
        room = {**r}
        room_name = r.get(name_key)
        if flag_on and room_name and room_name in per_room:
            room["lubu_aukstis_m"] = per_room[room_name]
            room["lubu_aukstis_saltinis"] = "per_room"
        else:
            room["lubu_aukstis_m"] = section_average
            room["lubu_aukstis_saltinis"] = "section_average"
        out.append(room)
    return out


def _apply_polygon_prepass(vision_result: dict) -> dict:
    """Sprint 2 + Sprint 4 Block B: shared-walls polygon prepass for
    grindjuostės double-count fix.

    When `polygon_prepass` flag is on:
    1. If a room has `polygon_pct` from Vision — use it directly.
    2. Otherwise synthesize a 4-corner rectangle from `bbox_pct`. LT
       residential rooms are 99%+ axis-aligned rectangles; for L-shapes
       the bbox over-estimates outline edges, biasing toward MORE shared
       edges than reality (conservative — slightly over-corrects grindjuostės
       rather than under).
    3. Estimate page metric extent as median(perimetras_m / bbox_perim_pct)
       across rooms. Assumes isotropic scale (LT plans are square paper).
    4. Pass to `apply_shared_edges` which subtracts half-shared-edge length
       from each room's `perimetras_m`. Downstream `lt_rules.calc_room_quantities`
       then computes grindjuostės from corrected perimetras (no more 0.98 m/m²
       double-count → falls in LT industry expected 0.5-0.6 m/m² ratio).

    Spec §4.3 wall_adjacency, §10 risk register.
    """
    from .feature_flags import get_flags
    from .wall_adjacency import apply_shared_edges

    if not get_flags()["polygon_prepass"]:
        return vision_result
    rooms = vision_result.get("patalpos", []) or []
    if not rooms:
        return vision_result

    # Estimate page extent (m) from median ratio of perimetras_m / bbox_perim_pct.
    # Each ratio represents how many metres a 1.0 page-fraction edge spans.
    ratios = []
    for r in rooms:
        bbox = r.get("bbox_pct")
        perim = r.get("perimetras_m")
        if bbox and perim and isinstance(bbox, dict):
            bbox_perim_pct = 2 * (float(bbox.get("w") or 0) + float(bbox.get("h") or 0))
            if bbox_perim_pct > 0.01:
                ratios.append(float(perim) / bbox_perim_pct)
    page_w = float(vision_result.get("page_width_m") or 0)
    page_h = float(vision_result.get("page_height_m") or 0)
    if page_w <= 0 or page_h <= 0:
        if not ratios:
            return vision_result
        ratios_sorted = sorted(ratios)
        page_extent_m = ratios_sorted[len(ratios_sorted) // 2]
        page_w = page_h = page_extent_m

    # Synthesize polygon from bbox when room lacks explicit polygon_pct
    rooms_with_poly = []
    for r in rooms:
        if r.get("polygon_pct"):
            rooms_with_poly.append(r)
        elif r.get("bbox_pct") and isinstance(r["bbox_pct"], dict):
            b = r["bbox_pct"]
            x, y, w, h = float(b.get("x") or 0), float(b.get("y") or 0), float(b.get("w") or 0), float(b.get("h") or 0)
            if w > 0 and h > 0:
                synth = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                rooms_with_poly.append({**r, "polygon_pct": synth, "polygon_source": "synthesized_from_bbox"})
            else:
                rooms_with_poly.append(r)
        else:
            rooms_with_poly.append(r)

    # apply_shared_edges bails (returns rooms unchanged) if any room still
    # lacks polygon_pct — that's our safety fallback.
    return {**vision_result, "patalpos": apply_shared_edges(rooms_with_poly, page_w, page_h)}


def _validate_room_bboxes(vision_result: dict) -> dict:
    """Sprint 4 follow-up: warn when room bbox_pct values look like Vision
    pointed at label/elevation/eksplikacija text instances instead of the
    floor plan room outlines.

    Heuristic: on a typical LT residential A0/A1 sheet, the floor plan covers
    a meaningful fraction of the page. If the union of all room bboxes covers
    less than ~5% of the page, Vision likely emitted bboxes for small label
    instances scattered across the sheet (e.g., elevation drawings, mazgai)
    rather than the actual rooms. Emits a warning to vision_result["warnings"].

    Does not mutate bbox_pct values — UI click-to-pan + pass-2 zoom still use
    them, and the warning lets the user know the data is suspect.
    """
    rooms = vision_result.get("patalpos") or []
    boxed = [r for r in rooms if isinstance(r.get("bbox_pct"), dict)
             and float(r["bbox_pct"].get("w") or 0) > 0
             and float(r["bbox_pct"].get("h") or 0) > 0]
    if len(boxed) < 3:
        return vision_result

    union_area = sum(
        float(r["bbox_pct"]["w"]) * float(r["bbox_pct"]["h"]) for r in boxed
    )
    if union_area >= 0.05:
        return vision_result

    warnings_list = list(vision_result.get("warnings") or [])
    warnings_list.append({
        "code": "bbox_pct_floor_plan_unlikely",
        "severity": "warning",
        "message": (
            f"Patalpų bbox suma užima tik {union_area*100:.1f}% puslapio — "
            "gali būti, kad AI nukreipė į pavadinimų etiketes ar elevation "
            "brėžinius vietoje tikrojo floor plan'o."
        ),
        "hint": (
            "Re-extract'ink projektą — sustiprintas prompt'as nukreipia AI "
            "į floor plan'ą (top-down view), ne į išklotines/mazgus."
        ),
        "expected": "≥5% puslapio ploto kambariams",
        "actual": f"{union_area*100:.2f}%",
    })
    return {**vision_result, "warnings": warnings_list}


# 2026-06-06: glaistymas/dažymas pozicijų konsolidacija. The generator emits a
# per-coat split (Q1/Q2/šlifavimas/gruntavimas/dažymas-sluoksniai, walls+ceilings)
# but contractors bill ONE m² rate for "Sienų, lubų glaistymas/dažymas" split only
# by height zone (Rangovas A samata items 16/17). This collapses those member
# lines into the combined line(s). Rotband / kampai / angokraščiai stay separate.
# Combined paintable area is unchanged — display-only.
_PAINT_SPLIT_PREFIXES = (
    "Sienų pirminis glaistymas", "Sienų antrinis glaistymas", "Sienų šlifavimas",
    "Sienų gruntavimas", "Sienų dažymas",
    "Lubų pirminis glaistymas", "Lubų antrinis glaistymas", "Lubų šlifavimas",
    "Lubų gruntavimas", "Lubų dažymas",
    "Lubų glaistymas/dažymas (virš",
)


def _consolidate_paint_enabled() -> bool:
    """Feature-flag gate for paint-line consolidation (default ON)."""
    try:
        from .feature_flags import get_flags
        return bool(get_flags().get("consolidate_paint_lines", True))
    except Exception:
        return True


def _consolidate_paint_pozicijos(parsed: dict) -> None:
    """Collapse the per-coat glaistymas/dažymas split into the contractor's
    combined line(s). Mutates parsed['pozicijos'] in place; preserves order and
    keeps Rotband/kampai/angokraščiai. Materials kept in `_medziagos`, the
    original split labels in `_detalus`. Combined area unchanged."""
    if not _consolidate_paint_enabled():
        return
    pozicijos = parsed.get("pozicijos") or []
    rooms = parsed.get("patalpos") or []
    SK_GD = "Sienų lubų glaistymas dažymas"
    SAL = "skaiciuota_is_brezinio"

    def _is_split(p: dict) -> bool:
        if (p.get("skyrius") or "") != SK_GD:
            return False
        a = p.get("aprasymas") or ""
        return any(a.startswith(pre) for pre in _PAINT_SPLIT_PREFIXES)

    members = [p for p in pozicijos if _is_split(p)]
    if not members:
        return

    walls_paint = round(sum(float(r.get("walls_paintable_m2") or 0) for r in rooms), 2)
    lubos_paint = round(sum(float(r.get("ceiling_paintable_m2") or 0) for r in rooms), 2)
    dazymo_total = round(walls_paint + lubos_paint, 2)
    if dazymo_total <= 0:
        parsed["pozicijos"] = [p for p in pozicijos if not _is_split(p)]
        return

    from .universal_rules import is_high_ceiling as _is_high
    virs_3m = round(sum(
        (float(r.get("walls_paintable_m2") or 0) + float(r.get("ceiling_paintable_m2") or 0))
        for r in rooms if _is_high(r.get("lubu_aukstis_m"))
    ), 2)
    virs_3m = min(max(virs_3m, 0.0), dazymo_total)
    iki_3m = round(dazymo_total - virs_3m, 2)

    medziagos = [
        {"aprasymas": "Glaistas (pradinis + baigiamasis)",
         "kiekis": round(sum(float(r.get("glaistas_kg") or 0) for r in rooms), 2), "vnt": "kg"},
        {"aprasymas": "Gruntas",
         "kiekis": round(sum(float(r.get("gruntas_l") or 0) for r in rooms), 2), "vnt": "l"},
        {"aprasymas": "Dažai (2 sluoksniai)",
         "kiekis": round(sum(float(r.get("dazai_l") or 0) for r in rooms), 2), "vnt": "l"},
    ]
    detalus = [p.get("aprasymas") for p in members]
    is_q4 = any((p.get("_q_lygis") == "Q4") for p in members)

    # Surface label reflects which surfaces actually carry paint (e.g. a bare
    # garažas paints only the ceiling → "Lubų glaistymas/dažymas").
    if walls_paint > 0 and lubos_paint > 0:
        surf = "Sienų, lubų"
    elif walls_paint > 0:
        surf = "Sienų"
    else:
        surf = "Lubų"

    new_lines: list[dict] = []
    base = {"skyrius": SK_GD, "vnt": "m2", "saltinis": SAL,
            "_medziagos": medziagos, "_detalus": detalus}
    if virs_3m <= 0.01:
        # no high-ceiling rooms — single line, no height suffix
        new_lines.append({**base, "kiekis": dazymo_total,
                          "aprasymas": f"{surf} glaistymas/dažymas"})
    elif iki_3m <= 0.01:
        # every painted room is >3m — single virš-3m line
        new_lines.append({**base, "kiekis": virs_3m, "_height_zone": ">3m",
                          "aprasymas": f"{surf} glaistymas/dažymas (virš 3m aukščio)"})
    else:
        new_lines.append({**base, "kiekis": iki_3m,
                          "aprasymas": f"{surf} glaistymas/dažymas (iki 3m aukščio)"})
        new_lines.append({"skyrius": SK_GD, "vnt": "m2", "saltinis": SAL, "kiekis": virs_3m,
                          "aprasymas": f"{surf} glaistymas/dažymas (virš 3m aukščio)",
                          "_height_zone": ">3m", "confidence": "medium"})
    if is_q4:
        new_lines.append({"skyrius": SK_GD, "vnt": "m2", "saltinis": SAL, "kiekis": dazymo_total,
                          "aprasymas": f"{surf} šlifavimas Q4 (80–120 grit, 100% paviršius)",
                          "darbo_norma_h_m2": _Q4_SANDING_HOURS_PER_M2, "_q_lygis": "Q4"})

    # Rebuild preserving order: replace the first member-run with the new lines.
    rebuilt: list[dict] = []
    inserted = False
    for p in pozicijos:
        if _is_split(p):
            if not inserted:
                rebuilt.extend(new_lines)
                inserted = True
        else:
            rebuilt.append(p)
    parsed["pozicijos"] = rebuilt


def _build_pozicijos_from_rooms(parsed: dict) -> dict:
    """Build the kiekių žiniaraštis (pozicijos[]) from per-room Python-computed
    aggregates (2026-04-28 deterministic refactor).

    Vision no longer emits pozicijos[]. Python aggregates per-room totals into
    skyrius-grouped lines: Sienų lubų glaistymas dažymas, GKP montavimas,
    Plytelių klijavimas, Hidroizoliacija, Santechnikos darbai, Elektros
    instaliacijos darbai, Pridėtiniai elementai. Each line has skyrius/aprasymas/vnt/kiekis
    matching the original schema so downstream `_emit_v8_compat_fields` still works.
    """
    rooms = parsed.get("patalpos") or []
    if not rooms:
        parsed["pozicijos"] = []
        return parsed

    def _sum(field: str) -> float:
        return round(sum(float(r.get(field) or 0) for r in rooms), 2)

    def _sum_filtered(field: str, paskirtys: set) -> float:
        return round(sum(float(r.get(field) or 0) for r in rooms
                         if (r.get("paskirtis") or "").lower() in paskirtys), 2)

    pozicijos: list[dict] = []
    SAL = "skaiciuota_is_brezinio"

    # Walls vs lubos split aggregates (per-room values from calc_room_quantities)
    walls_paint = round(sum(float(r.get("walls_paintable_m2") or 0) for r in rooms), 2)
    lubos_paint = round(sum(float(r.get("ceiling_paintable_m2") or 0) for r in rooms), 2)
    dazymo_total = walls_paint + lubos_paint

    # Glaistas/gruntas/dažai per medium — split proportionally to walls vs lubos
    walls_share = (walls_paint / dazymo_total) if dazymo_total > 0 else 0.5
    lubos_share = 1 - walls_share if dazymo_total > 0 else 0.5
    glaistas_total = _sum("glaistas_kg")
    dazai_total = _sum("dazai_l")
    gruntas_total = _sum("gruntas_l")

    # Wet rooms (vonia/wc/san) — voniose dažymas tik virš plytelių zonos
    WET = {"vonia", "wc", "san"}

    SK_GD = "Sienų lubų glaistymas dažymas"
    SK_GKP = "GKP montavimas"
    SK_PL = "Plytelių klijavimas"
    SK_HI = "Hidroizoliacija"
    SK_GR = "Grindys"
    SK_SAN = "Santechnikos darbai"
    SK_EL = "Elektros instaliacijos darbai"
    SK_PR = "Pridėtiniai elementai"

    # ════════════════════════════════════════════════════════════════════════
    # SIENŲ LUBŲ GLAISTYMAS DAŽYMAS (~21 lines)
    # Per-coat, walls/lubos split, kampai/grindjuostės/karnizas atskirai
    # ════════════════════════════════════════════════════════════════════════

    # Q-level for sanding labor uplift (Sprint §2A.4 Phase 2). Q4 needs full-
    # surface 80-120 grit sanding (0.30 h/m²) per Merkblatt Nr.2; lower Q's
    # use light scuff sanding only.
    q_lygis = (parsed.get("_overrides") or {}).get("glaistas_q_lygis", "Q2")
    is_q4 = str(q_lygis).upper() == "Q4"
    sanding_suffix = " Q4 (80–120 grit, 100% paviršius)" if is_q4 else ""

    if walls_paint > 0:
        # Sienų lyginimas Rotband — pradinis storas sluoksnis (5-10mm) ant
        # pliko bloko/betono prieš glaistymą. NEAPPLIKUOJASI ant GKP pertvarų
        # (jos jau lygios).
        #
        # 2026-06-09 re-calibration (Berzas fixture, contractor-verified):
        # kontraktoriaus samata = 138,69 m² Rotband ant 460,71 m² visų sienų
        # ploto = 30,1%. Ankstesnis 50% default'as buvo kalibruotas prieš KLAIDINGĄ
        # walls_paint=277,33 (nuo to laiko ištaisyta į ~448 m² — GT walls_paint
        # 460,71, −2,8%). Rotband užvalg. TIK ant pliko bloko/betono (ne ant GKP
        # pertvarų), o tai ~30% vidaus sienų ploto LT naujos statybos name.
        # User gali override per `rotband_share` (0.0-1.0).
        rotband_share = (parsed.get("_overrides") or {}).get("rotband_share", 0.30)
        try:
            rotband_share = max(0.0, min(1.0, float(rotband_share)))
        except (ValueError, TypeError):
            rotband_share = 0.30
        rotband_m2 = round(walls_paint * rotband_share, 2)
        pozicijos.append({
            "skyrius": SK_GD, "aprasymas": "Sienų lyginimas Knauf Rotband",
            "vnt": "m2", "kiekis": rotband_m2, "saltinis": SAL,
            "medziagos_aprasymas": "Rotband (~10 kg/m² esant 5mm storiui)",
            "medziagos_kiekis": round(rotband_m2 * 10.0, 2),
            "medziagos_vnt": "kg",
            "_assumption": f"{int(rotband_share*100)}% sienų ploto (mūro/betono sienos, ne GKP pertvaros). Užvalg. tik prieš glaistant ant pliko bloko/betono.",
        })
        pozicijos.extend([
            {"skyrius": SK_GD, "aprasymas": "Sienų pirminis glaistymas Q1",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Pradinis glaistas",
             "medziagos_kiekis": round(glaistas_total * walls_share * 0.5, 2),
             "medziagos_vnt": "kg"},
            {"skyrius": SK_GD, "aprasymas": "Sienų antrinis glaistymas Q2",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Baigiamasis glaistas",
             "medziagos_kiekis": round(glaistas_total * walls_share * 0.5, 2),
             "medziagos_vnt": "kg"},
            {"skyrius": SK_GD, "aprasymas": f"Sienų šlifavimas{sanding_suffix}",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL,
             **({"darbo_norma_h_m2": _Q4_SANDING_HOURS_PER_M2, "_q_lygis": "Q4"} if is_q4 else {})},
            {"skyrius": SK_GD, "aprasymas": "Sienų gruntavimas (1 sluoksnis)",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Gruntas",
             "medziagos_kiekis": round(gruntas_total * walls_share, 2),
             "medziagos_vnt": "l"},
            {"skyrius": SK_GD, "aprasymas": "Sienų dažymas (1 sluoksnis)",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL},
            {"skyrius": SK_GD, "aprasymas": "Sienų dažymas (2 sluoksnis)",
             "vnt": "m2", "kiekis": walls_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Dažai (2 sluoksniai)",
             "medziagos_kiekis": round(dazai_total * walls_share, 2),
             "medziagos_vnt": "l"},
        ])

    # Molio tinkas / decor-coated walls — separate finish, EXCLUDED from the
    # glaistymas/dažymas lines above (2026-06-11 Bacevičiaus experiment: 160 m²
    # of clay plaster was silently billed as paint, +62.8% combined error).
    molio_total = _sum("molio_tinko_m2")
    if molio_total > 0:
        pozicijos.append({
            "skyrius": SK_GD, "aprasymas": "Sienų dekoravimas molio tinku",
            "vnt": "m2", "kiekis": molio_total, "saltinis": SAL,
            "_assumption": "Plotas iš apdailos plano (molio/kalkinio tinko ar kitos dangos zona). Paruošimas įskaičiuotas į dekoravimo darbą — atskiros glaistymo eilutės šiam plotui nėra.",
        })

    if lubos_paint > 0:
        pozicijos.extend([
            {"skyrius": SK_GD, "aprasymas": "Lubų pirminis glaistymas Q1",
             "vnt": "m2", "kiekis": lubos_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Pradinis glaistas",
             "medziagos_kiekis": round(glaistas_total * lubos_share * 0.5, 2),
             "medziagos_vnt": "kg"},
            {"skyrius": SK_GD, "aprasymas": "Lubų antrinis glaistymas Q2",
             "vnt": "m2", "kiekis": lubos_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Baigiamasis glaistas",
             "medziagos_kiekis": round(glaistas_total * lubos_share * 0.5, 2),
             "medziagos_vnt": "kg"},
            {"skyrius": SK_GD, "aprasymas": f"Lubų šlifavimas{sanding_suffix}",
             "vnt": "m2", "kiekis": lubos_paint, "saltinis": SAL,
             **({"darbo_norma_h_m2": _Q4_SANDING_HOURS_PER_M2, "_q_lygis": "Q4"} if is_q4 else {})},
            {"skyrius": SK_GD, "aprasymas": "Lubų gruntavimas (1 sluoksnis)",
             "vnt": "m2", "kiekis": lubos_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Gruntas",
             "medziagos_kiekis": round(gruntas_total * lubos_share, 2),
             "medziagos_vnt": "l"},
            {"skyrius": SK_GD, "aprasymas": "Lubų dažymas (2 sluoksniai)",
             "vnt": "m2", "kiekis": lubos_paint, "saltinis": SAL,
             "medziagos_aprasymas": "Dažai (2 sluoksniai)",
             "medziagos_kiekis": round(dazai_total * lubos_share, 2),
             "medziagos_vnt": "l"},
        ])

        # Sprint §FIX-5 (2026-04-29): per rangovas P1 — atskirame eilutę „Lubų
        # glaistymas/dažymas (virš 3m aukščio)" su tuo pačiu plotu, ne kaip
        # dvigubas count, o kaip subset HIGHLIGHT — premium aukšto darbas.
        # rangovas savo Pasiūlyme P1: 68.28 m² būtent šitas split. Kainos formuoja
        # per pastolių surcharge'us ir didesnį darbo laiką dėl aukšcio.
        from .universal_rules import is_high_ceiling as _is_high
        lubos_virs_3m = round(sum(
            float(r.get("ceiling_paintable_m2") or 0) for r in rooms
            if _is_high(r.get("lubu_aukstis_m"))
        ), 2)
        if lubos_virs_3m > 0:
            pozicijos.append({
                "skyrius": SK_GD,
                "aprasymas": "Lubų glaistymas/dažymas (virš 3 m aukščio) — papildomas darbas dėl aukščio",
                "vnt": "m2", "kiekis": lubos_virs_3m, "saltinis": SAL,
                "_height_zone": ">3m",
                "confidence": "medium",
            })

    # Kampai split: vidiniai (perim + 4×H) vs išoriniai (angos × kampai)
    # Approx: ~70% vidiniai, ~30% išoriniai (LT typical)
    kampai_total = _sum("kampu_metrai")
    if kampai_total > 0:
        # 2026-06-06 (RC8): ONE corner line (= contractor item 19 "Dažymo kampų
        # montavimas"). Previously the same metrai were ALSO emitted as
        # vidiniai+išoriniai → the corner length billed ~2×. Outer-corner
        # kampuotės (~30%) carried as the material sub-field.
        pozicijos.append({
            "skyrius": SK_GD, "aprasymas": "Dažymo kampų montavimas",
            "vnt": "m", "kiekis": kampai_total, "saltinis": SAL,
            "medziagos_aprasymas": "PVC kampuotės (išoriniai kampai)",
            "medziagos_kiekis": round(kampai_total * 0.3, 2), "medziagos_vnt": "m",
        })

    # Angokraščių apdailos (reveal length around openings) + paslėptų durų stakta.
    # 2026-06-06 (RC3): use the calibrated per-room `angokrasciu_gkp_m` field from
    # calc_room_quantities (doors=W+2H, interior windows=W+2H, EXTERIOR windows=0
    # via is_exterior) instead of recomputing Σ(2H+W) inline. The inline version had
    # NO is_exterior check and over-quoted +54.8% on BOTH the SK_GD glaistymas and
    # SK_GKP apdirbimas lines (138.42 vs field 78.05 on Beržų; contractor 89.39).
    angokrasciai_m = _sum("angokrasciu_gkp_m")
    pasleptu_duru_staktu_m = 0.0
    n_pasleptu_tagged = 0
    reveal_sum = 0.0  # sum of (2H+W) over the glyph-tagged frameless doors
    for r in rooms:
        for el in (r.get("elementai") or []):
            if (el.get("tipas") or "").lower() == "pasleptos_duris":
                W = (el.get("plotis_mm") or 0) / 1000
                H = (el.get("aukstis_mm") or 0) / 1000
                if W > 0 and H > 0:
                    k = int(el.get("kiekis") or 1)
                    pasleptu_duru_staktu_m += (2 * H + W) * k
                    n_pasleptu_tagged += k
                    reveal_sum += (2 * H + W) * k
    pasleptu_duru_staktu_m = round(pasleptu_duru_staktu_m, 2)

    # 2026-06-14: frameless-door RECONCILIATION (council 5/5 + research). The
    # glyph pass under-tags frameless doors (Beržų 2 of ~8) because frame type
    # is NOT in the door symbol — it's in the drawing TEXT. door_type_reader reads
    # the tags/annotations ("skirta beapvadinėms durims"); _door_types carries the
    # reconciled count + a confidence flag. When the text count exceeds the tagged
    # count, scale the reveal meters up to it (avg reveal per tagged door, default
    # 5.1 m for a 900×2400 frameless), and flag the line so the user verifies.
    _dt = parsed.get("_door_types") or {}
    _door_conf = None
    _door_reason = None
    if _dt.get("count") and int(_dt["count"]) > n_pasleptu_tagged:
        avg_reveal = (reveal_sum / n_pasleptu_tagged) if n_pasleptu_tagged > 0 else 5.1
        pasleptu_duru_staktu_m = round(int(_dt["count"]) * avg_reveal, 2)
        _door_conf = _dt.get("confidence")
        _door_reason = _dt.get("reason")
    if angokrasciai_m > 0:
        # Glaistymo skyriaus eilutė (apdailos darbas)
        pozicijos.append({
            "skyrius": SK_GD, "aprasymas": "Angokraščių glaistymas-dažymas",
            "vnt": "m", "kiekis": angokrasciai_m, "saltinis": SAL,
        })
        # P2 fix: GKP skyriaus eilutė (struktūrinis darbas — angokraščio formavimas).
        # rangovas P1+P2+P5 4/5 freq. Tas pats kiekis, kita skyrius.
        pozicijos.append({
            "skyrius": SK_GKP, "aprasymas": "Angokraščių apdirbimas GKP (struktūra)",
            "vnt": "m", "kiekis": angokrasciai_m, "saltinis": SAL,
            "medziagos_aprasymas": "GKP juostelės + savisriegiai",
            "medziagos_kiekis": angokrasciai_m, "medziagos_vnt": "m",
        })
    if pasleptu_duru_staktu_m > 0.5:
        # P5 fix: paslėptų durų staktų pozicija (4/5 freq, ~400 EUR/proj)
        _door_line = {
            "skyrius": SK_GD, "aprasymas": "Durų angų paruošimas beapvadinėms durims",
            "vnt": "m", "kiekis": pasleptu_duru_staktu_m, "saltinis": SAL,
        }
        if _door_conf:  # text-reconciled — carry the flag + reason
            _door_line["confidence"] = _door_conf
            if _door_reason:
                _door_line["_confidence_reason"] = _door_reason
        pozicijos.append(_door_line)

    # Grindjuostės — cap-by-ratio fix (P1 audit measured +88% over rangovas).
    # Per-room (perim − Σdurys) × 1.10 double-counts interior walls (each
    # interior wall belongs to 2 rooms). rangovas ratios across P1+P5: 0.50-0.62
    # m of grindjuostė per m² of floor. Cap at 0.65 m/m² to remove the
    # phantom segments. Audit field marks when cap fires for transparency.
    GRINDJUOSCIU_RATIO_CAP = 0.65  # m grindjuostės per m² floor (rangovas-empirical)
    grindjuostes_raw = _sum("grindjuosciu_m")
    bendras_plotas_for_cap = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    grindjuostes_capped = min(grindjuostes_raw, bendras_plotas_for_cap * GRINDJUOSCIU_RATIO_CAP)
    if grindjuostes_raw > grindjuostes_capped + 0.01:
        # Cap fired — record on each room for audit trail
        for r in rooms:
            r["_grindjuosciu_capped"] = True
        parsed.setdefault("_meta", {})["grindjuosciu_pre_cap_m"] = round(grindjuostes_raw, 2)
        parsed["_meta"]["grindjuosciu_post_cap_m"] = round(grindjuostes_capped, 2)
        parsed["_meta"]["grindjuosciu_cap_ratio_m_per_m2"] = GRINDJUOSCIU_RATIO_CAP
        # Surface to UI so user knows the empirical band-aid (not pure math)
        # capped this number. Prepass should make the cap unnecessary; if it
        # fires, polygon_pct/bbox_pct were missing or wall_adjacency bailed.
        warnings_list = parsed.setdefault("warnings", [])
        warnings_list.append({
            "code": "grindjuosciu_cap_fired",
            "severity": "low",
            "message": (
                f"Grindjuostės apriboti per empirinį 0.65 m/m² limitą: "
                f"{grindjuostes_raw:.1f}m → {grindjuostes_capped:.1f}m. "
                "Reiškia, kad polygon_pct/bbox_pct duomenų trūko ir "
                "wall_adjacency negalėjo apskaičiuoti bendrų sienų."
            ),
            "hint": "Re-extract'ink projektą — naujas Vision prompt'as turėtų grąžinti polygon_pct visoms patalpoms.",
            "expected": "≤0.65 m/m² (po wall_adjacency korekcijos ~0.55)",
            "actual": f"{grindjuostes_raw / max(bendras_plotas_for_cap, 0.01):.3f} m/m² (pre-cap)",
        })
    grindjuostes_total = round(grindjuostes_capped, 2)
    if grindjuostes_total > 0:
        pozicijos.extend([
            {"skyrius": SK_GD, "aprasymas": "Grindjuosčių sumontavimas",
             "vnt": "m", "kiekis": grindjuostes_total, "saltinis": SAL,
             "medziagos_aprasymas": "Grindjuostės (m + 10% atliekų)",
             "medziagos_kiekis": round(grindjuostes_total * 1.10, 2),
             "medziagos_vnt": "m"},
            {"skyrius": SK_GD, "aprasymas": "Grindjuosčių dažymas",
             "vnt": "m", "kiekis": grindjuostes_total, "saltinis": SAL},
        ])

    karnizas_total = _sum("lubu_karnizo_m")
    if karnizas_total > 0:
        pozicijos.extend([
            {"skyrius": SK_GD, "aprasymas": "Lubų karnizo sumontavimas",
             "vnt": "m", "kiekis": karnizas_total, "saltinis": SAL,
             "medziagos_aprasymas": "Karnizas (m + 5% atliekų)",
             "medziagos_kiekis": round(karnizas_total * 1.05, 2),
             "medziagos_vnt": "m"},
            {"skyrius": SK_GD, "aprasymas": "Lubų karnizo dažymas",
             "vnt": "m", "kiekis": karnizas_total, "saltinis": SAL},
        ])

    nisu_total = _sum("nisu_metrai")
    if nisu_total > 0:
        # rangovas audit 2026-04-29: separate STRUCTURAL framing line (GKP karkasą
        # formuoja prieš glaistymą; tai 3/5 jo projektų atskira eilutė).
        pozicijos.extend([
            {"skyrius": SK_GKP, "aprasymas": "Nišų formavimas GKP konstrukcijoje",
             "vnt": "m", "kiekis": nisu_total, "saltinis": SAL,
             "medziagos_aprasymas": "GKP profiliai + savisriegiai",
             "medziagos_kiekis": round(nisu_total * 2.5, 2),  # ~2.5 m profilio per ilgiui
             "medziagos_vnt": "m"},
            {"skyrius": SK_GD, "aprasymas": "LED nišų glaistymas",
             "vnt": "m", "kiekis": nisu_total, "saltinis": SAL},
            {"skyrius": SK_GD, "aprasymas": "LED nišų dažymas",
             "vnt": "m", "kiekis": nisu_total, "saltinis": SAL},
        ])

    # ════════════════════════════════════════════════════════════════════════
    # GKP MONTAVIMAS (~5-9 lines)
    # ════════════════════════════════════════════════════════════════════════

    gkp_standart = _sum("gkp_lubu_standart_m2")
    gkp_high = _sum("gkp_lubu_virs_3m_m2")
    gkp_total = gkp_standart + gkp_high
    if gkp_total > 0:
        if gkp_standart > 0:
            pozicijos.append({
                "skyrius": SK_GKP, "aprasymas": "GKP lubų montavimas (standartinis aukštis)",
                "vnt": "m2", "kiekis": gkp_standart, "saltinis": SAL,
            })
        if gkp_high > 0:
            pozicijos.append({
                "skyrius": SK_GKP, "aprasymas": "GKP lubų montavimas (virš 3 m aukščio)",
                "vnt": "m2", "kiekis": gkp_high, "saltinis": SAL,
            })
        # Sprint 0 Fix 1: separate 9.5mm ceiling sheets from 12.5mm wall sheets.
        # Current data model only tracks ceiling GKP; sienos_gkp_m2=0 until wall
        # GKP fields are added to the extraction schema.
        pozicijos.extend(build_gkp_pozicijos([
            {"sienos_gkp_m2": 0, "lubos_gkp_m2": gkp_total}
        ]))
        # 2026-05-06 formula audit: split CD (laikantieji, ~1.6-1.8 m/m²)
        # vs UW (pakraščio, ~0.4 m/m²) so the bill of materials shows
        # different profile types separately. Total ~2.0 m/m² (was 3.0,
        # within audit's 1.8-2.5 range for ceiling GKP). Source:
        # docs/formulas/2026-05-06-formula-audit.md §8 (Knauf W111).
        cd_total = round(gkp_total * 1.6, 2)
        uw_total = round(gkp_total * 0.4, 2)
        pozicijos.extend([
            {"skyrius": SK_GKP, "aprasymas": "GKP karkaso CD profiliai (laikantieji)",
             "vnt": "m", "kiekis": cd_total, "saltinis": SAL,
             "medziagos_aprasymas": "CD 60×27 mm (~1.6 m/m² lubų, ~625 mm c/c)",
             "medziagos_kiekis": cd_total, "medziagos_vnt": "m"},
            {"skyrius": SK_GKP, "aprasymas": "GKP karkaso UW profiliai (pakraščio)",
             "vnt": "m", "kiekis": uw_total, "saltinis": SAL,
             "medziagos_aprasymas": "UW 28×27 mm pakraščio kontūras",
             "medziagos_kiekis": uw_total, "medziagos_vnt": "m"},
            {"skyrius": SK_GKP, "aprasymas": "GKP siūlių glaistymas + armavimo juostelė",
             "vnt": "m", "kiekis": round(gkp_total * 1.5, 2), "saltinis": SAL,
             "medziagos_aprasymas": "Armavimo juostelė + glaistas siūlėms",
             "medziagos_kiekis": round(gkp_total * 1.5, 2), "medziagos_vnt": "m"},
            {"skyrius": SK_GKP, "aprasymas": "Savisriegiai GKP montavimui",
             "vnt": "vnt", "kiekis": int(gkp_total * 30), "saltinis": SAL,
             "medziagos_aprasymas": "~30 vnt/m² lubų",
             "medziagos_kiekis": int(gkp_total * 30), "medziagos_vnt": "vnt"},
        ])

    # Reviziniai dureliai voniose (1 vnt per drėgnam patalpą)
    rev_dureliai = sum(1 for r in rooms
                       if (r.get("paskirtis") or "").lower() in WET)
    if rev_dureliai > 0:
        pozicijos.append({
            "skyrius": SK_GKP, "aprasymas": "Reviziniai dureliai (vamzdžių prieiga)",
            "vnt": "vnt", "kiekis": rev_dureliai, "saltinis": SAL,
            "medziagos_aprasymas": "Reviziniai dureliai 200×200 mm",
            "medziagos_kiekis": rev_dureliai, "medziagos_vnt": "vnt",
        })

    # ════════════════════════════════════════════════════════════════════════
    # PLYTELĖS (per location: vonia sienos / vonia grindys / virtuvė backsplash)
    # ════════════════════════════════════════════════════════════════════════

    # Per-location aggregates
    pl_sienos_vonia = _sum_filtered("plyteles_sienos_m2", WET)
    pl_sienos_virtuve = _sum_filtered("plyteles_sienos_m2", {"virtuve"})
    pl_sienos_kita = round(_sum("plyteles_sienos_m2") - pl_sienos_vonia - pl_sienos_virtuve, 2)
    pl_grindys_vonia = _sum_filtered("plyteles_grindys_m2", WET)
    pl_grindys_virtuve = _sum_filtered("plyteles_grindys_m2", {"virtuve"})
    pl_grindys_kita = round(_sum("plyteles_grindys_m2") - pl_grindys_vonia - pl_grindys_virtuve, 2)

    def _add_tile_lines(skyrius_loc: str, kiekis: float, vieta: str):
        """Add 4 lines per tile location: klijavimas + klijai, fugavimas + fugos."""
        if kiekis <= 0:
            return
        pozicijos.append({
            "skyrius": SK_PL,
            "aprasymas": f"{vieta} plytelių klijavimas",
            "vnt": "m2", "kiekis": kiekis, "saltinis": SAL,
            "medziagos_aprasymas": "Plytelių klijai (~5 kg/m²)",
            "medziagos_kiekis": round(kiekis * 5.0, 2),
            "medziagos_vnt": "kg",
        })
        pozicijos.append({
            "skyrius": SK_PL,
            "aprasymas": f"{vieta} plytelės",
            "vnt": "m2", "kiekis": round(kiekis * 1.08, 2), "saltinis": SAL,
            "medziagos_aprasymas": "Plytelės (m² + 8% atliekų)",
            "medziagos_kiekis": round(kiekis * 1.08, 2),
            "medziagos_vnt": "m2",
        })
        pozicijos.append({
            "skyrius": SK_PL,
            "aprasymas": f"{vieta} plytelių fugavimas",
            "vnt": "m2", "kiekis": kiekis, "saltinis": SAL,
            "medziagos_aprasymas": "Fugavimo masė (~0.3 kg/m²)",
            "medziagos_kiekis": round(kiekis * 0.3, 2),
            "medziagos_vnt": "kg",
        })

    _add_tile_lines(SK_PL, pl_sienos_vonia, "Vonios sienų")
    _add_tile_lines(SK_PL, pl_sienos_virtuve, "Virtuvės atatvaro")
    _add_tile_lines(SK_PL, pl_sienos_kita, "Kitų sienų")
    _add_tile_lines(SK_PL, pl_grindys_vonia, "Vonios grindų")
    _add_tile_lines(SK_PL, pl_grindys_virtuve, "Virtuvės grindų")
    _add_tile_lines(SK_PL, pl_grindys_kita, "Kitų grindų")

    # Sprint §41 (2026-04-29): tile format split — per rangovas audit v2 #2 gap.
    # Didžiaformatės plytelės (>600×600) reikalauja papildomo darbo: extra
    # klijų sluoksnio, dvigubo padengimo (back-buttering), specialių įrankių.
    # rangovas premium projektai šitai itemize'ina su 2-3× kainos surcharge.
    # BUG FIX (Sprint 0): pl_total must be defined BEFORE the didzformat_count
    # check below. Previously it was assigned at line ~1213 (after its first use
    # at line ~1185), causing a NameError that silently bypassed the entire
    # _build_pozicijos_from_rooms function and fell back to Vision's stale
    # pozicijos (containing the old "GKP lapai (12.5 mm)" single-line format).
    pl_total = round(_sum("plyteles_sienos_m2") + _sum("plyteles_grindys_m2"), 2)
    plyteliu_specs = parsed.get("_plyteliu_specs") or []
    didzformat_count = sum(
        1 for s in plyteliu_specs
        if (s.get("format_label") or "").lower() in {"didžiaformatė", "didžiaformate", "didziaformat"}
    )
    if didzformat_count > 0 and pl_total > 0:
        # Heuristic: when ≥1 didžiaformatė detected, assume ~30% of total
        # tile area is large-format. User can override via Prielaidos.
        # Surcharge: extra labor for backbuttering + masinis lygis levelers.
        didzformat_share = (parsed.get("_overrides") or {}).get("didzformat_share", 0.30)
        didzformat_m2 = round(pl_total * didzformat_share, 2)
        if didzformat_m2 > 0:
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Didžiaformačių plytelių klijavimas (>600×600 mm) — papildoma rūpestis",
                "vnt": "m2", "kiekis": didzformat_m2, "saltinis": SAL,
                "medziagos_aprasymas": "Klijų sluoksnis storas (back-buttering) — ~5 kg/m²",
                "medziagos_kiekis": round(didzformat_m2 * 5.0, 1),
                "medziagos_vnt": "kg",
                "confidence": "medium",
            })
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Didžiaformačių plytelių lygio kontrolė (lazerio + pavedimas)",
                "vnt": "m2", "kiekis": didzformat_m2, "saltinis": SAL,
                "confidence": "medium",
            })

    # Tile-specific operations: 45° pjovimas, silikonas, gręžimas, dušo nuolydis
    # P3 refinement: silikon multiplier × 0.5 → × 1.2 (rangovas P1=129m vs our
    # 0.5×perim suggests we undercount; he counts grindys + lubų pjūvis +
    # dušo kabinos perim). Skylių gręžimas refactored to use symbol counts
    # when available, fallback to opening-count heuristic.
    # NOTE: pl_total is already assigned above (moved up to fix NameError bug).
    if pl_total > 0:
        wet_perim = round(sum(float(r.get("perimetras_m") or 0) for r in rooms
                              if (r.get("paskirtis") or "").lower() in WET), 2)
        # 2026-06-11: silikonavimas seals ALL tiled zones, not only paskirtis-wet
        # rooms — skalbyklos, and any room the apdailos reader marks substantially
        # tiled, are sealed too. Counting only vonia/wc/san under-counted on both
        # anchors (berzas −39%, bacv −68%); adding tiled non-wet rooms recovers the
        # defensible part (berzas −10%, bacv −55%) with the unchanged ×1.4
        # coefficient. (45°-pjovimas keeps WET-only perim — it didn't under-count.)
        def _is_tiled(r: dict) -> bool:
            if (r.get("paskirtis") or "").lower() in WET:
                return True
            bd = r.get("sienu_apdailos_breakdown") or {}
            return float(bd.get("plyteles_share") or 0) >= 0.6
        tiled_perim = round(sum(float(r.get("perimetras_m") or 0) for r in rooms
                                if _is_tiled(r)), 2)
        if wet_perim > 0:
            # Plytelių 45° pjovimas — outer corners × tile_height (vonia
            # default 2 outer corners). Floor: wet_perim × 0.4.
            avg_tile_h = sum(float(r.get("plyteles_sienos_aukstis_m") or 0) for r in rooms
                             if (r.get("paskirtis") or "").lower() in WET)
            n_wet = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() in WET)
            tile_h = (avg_tile_h / n_wet) if n_wet > 0 else 2.0
            pjovimas_45 = max(round(wet_perim * 0.4, 2), round(2 * n_wet * tile_h, 2))
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Plytelių 45° pjovimas (vidiniai kampai)",
                "vnt": "m", "kiekis": pjovimas_45, "saltinis": SAL,
            })
            # rangovas audit 2026-04-29: epoxy variant for premium projects (P1
            # 1/5 freq, but represents premium archetype). Only emit when
            # rules_override or archetypas == "premium". For now: emit as
            # optional add-on when paint_class == 1 (top-tier projects).
            paint_class_for_45 = (parsed.get("_overrides") or {}).get("paint_class", 2)
            if int(paint_class_for_45) == 1:
                pozicijos.append({
                    "skyrius": SK_PL,
                    "aprasymas": "Plytelių 45° pjovimas EPOKSIDU (premium kampai)",
                    "vnt": "m", "kiekis": pjovimas_45, "saltinis": SAL,
                    "medziagos_aprasymas": "Epoksidinis klijuoklis (Mapei Kerapoxy ar pan.)",
                    "medziagos_kiekis": round(pjovimas_45 * 0.05, 2),  # ~0.05 kg/m
                    "medziagos_vnt": "kg",
                })
            # Silikonavimas split (rangovas audit 2026-04-29): separate corner
            # silicone (between tile zones / floor-wall junctions / outside
            # corners) from sanitaryware sealing. rangovas itemizes both.
            #
            # Empirical splits across his 5 projects:
            #   Sanitaryware silikonas ≈ wet_perim × 0.8 (around bath/sink/WC)
            #   Plytelių kampų silikonas ≈ wet_perim × 0.6 (inside corners)
            silikon_san_m = round(tiled_perim * 0.8, 2)
            silikon_kampai_m = round(tiled_perim * 0.6, 2)
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Silikonavimas tarp plytelių zonos ir sanitarinės įrangos",
                "vnt": "m", "kiekis": silikon_san_m, "saltinis": SAL,
                "medziagos_aprasymas": "Sanitarinis silikonas (~10 m/tūbelę)",
                "medziagos_kiekis": max(1, round(silikon_san_m / 10, 0)),
                "medziagos_vnt": "vnt",
            })
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Plytelių vidinių kampų silikonavimas",
                "vnt": "m", "kiekis": silikon_kampai_m, "saltinis": SAL,
                "medziagos_aprasymas": "Spalvotas silikonas pagal fugavimo spalvą",
                "medziagos_kiekis": max(1, round(silikon_kampai_m / 10, 0)),
                "medziagos_vnt": "vnt",
            })
        # Skylių gręžimas — symbol-driven (klozetas×4 + praustuvė×6 + vonia×8
        # + WC rėmas×3) per wet room. Symbols come from detected_symbols_summary
        # or fall back to opening-count heuristic when symbols not detected.
        sym = (parsed.get("detected_symbols_summary") or {})
        n_kloz = int(sym.get("klozetai") or 0)
        n_praust = int(sym.get("praustuves") or 0)
        n_vonia = int(sym.get("vonios") or 0)
        n_wcrem = int(sym.get("wc_remai") or 0)
        skyliu_symbols = n_kloz * 4 + n_praust * 6 + n_vonia * 8 + n_wcrem * 3
        if skyliu_symbols > 0:
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Skylių gręžimas plytelėse (vamzdžiams, kaiščiams)",
                "vnt": "vnt", "kiekis": skyliu_symbols, "saltinis": "simboliai_brezinyje",
                "confidence": "medium",
            })
        else:
            # Fallback: opening-count heuristic when no symbols detected
            n_holes = sum(int(el.get("kiekis") or 1)
                          for r in rooms if (r.get("paskirtis") or "").lower() in WET
                          for el in (r.get("elementai") or [])
                          if (el.get("tipas") or "").lower() in ("duris", "pasleptos_duris", "langas"))
            if n_holes > 0:
                pozicijos.append({
                    "skyrius": SK_PL,
                    "aprasymas": "Skylių gręžimas plytelėse (vamzdžiams, kaiščiams)",
                    "vnt": "vnt", "kiekis": n_holes * 4, "saltinis": SAL,
                    "confidence": "low",
                })
        # Dušo nuolydis — 1 vnt per vonia su dušu
        n_showers = sum(1 for r in rooms
                        if (r.get("paskirtis") or "").lower() in {"vonia", "san"})
        if n_showers > 0:
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Nuolydžio formavimas dušo zonoje",
                "vnt": "vnt", "kiekis": n_showers, "saltinis": SAL,
            })
        # Lentynėliai iš plytelių dušo kabinoje — default 2 per vonia.
        # 2026-05-27 fix (Berzas fixture): truth=5 vnt for 2 bathrooms (=2,5
        # per vonia). Anksčiau default 1 per vonia → 2 vnt (under by -60%).
        # User gali override per `lentyneliu_per_vonia`.
        n_full_vonia = sum(1 for r in rooms
                           if (r.get("paskirtis") or "").lower() in {"vonia", "san"})
        if n_full_vonia > 0:
            per_vonia = (parsed.get("_overrides") or {}).get("lentyneliu_per_vonia", 2)
            try:
                per_vonia = max(0, int(per_vonia))
            except (ValueError, TypeError):
                per_vonia = 2
            pozicijos.append({
                "skyrius": SK_PL,
                "aprasymas": "Lentynėlių iš plytelių įrengimas dušo kabinoje",
                "vnt": "vnt", "kiekis": n_full_vonia * per_vonia,
                "saltinis": "paskirtis_default",
                "confidence": "low",
                "_assumption": f"{per_vonia} lentynėlės per vonią × {n_full_vonia} voniose.",
            })

    # P3 NEW: Dėžučių iš GKP formavimas WC mechanizmams paslėpti — count of
    # wet rooms with klozetas (rangovas P1=2, P2=2, P5=1; 3+/5 freq). 1 per
    # vonia/wc/san where klozetas exists.
    n_wet_klozetas = sum(1 for r in rooms
                          if (r.get("paskirtis") or "").lower() in {"vonia", "wc", "san", "san_mazgas"})
    if n_wet_klozetas > 0:
        pozicijos.append({
            "skyrius": SK_GKP,
            "aprasymas": "Dėžučių iš GKP formavimas WC mechanizmams paslėpti",
            "vnt": "vnt", "kiekis": n_wet_klozetas, "saltinis": "paskirtis_default",
            "medziagos_aprasymas": "GKP plokštė + profiliai",
            "medziagos_kiekis": n_wet_klozetas, "medziagos_vnt": "vnt",
        })

    # ════════════════════════════════════════════════════════════════════════
    # HIDROIZOLIACIJA (~5 lines)
    # ════════════════════════════════════════════════════════════════════════

    # P6: Hidroizoliacijos įrengimas — VIENA pozicija (LT pro contractor
    # convention, rangovas pattern). Bundle paruošimas + 2 sluoksniai + juostelė
    # kampuose į vieną darbą. m² + juostelės m saugojami kaip _detail_*
    # frontend'ui, kad galėtų išskleisti detales jei reikia.
    hidro_m2 = _sum("hidroizoliacija_m2")
    n_wet_zones = sum(1 for r in rooms
                      if (r.get("paskirtis") or "").lower() in WET)
    if hidro_m2 > 0 and n_wet_zones > 0:
        wet_perim = round(sum(float(r.get("perimetras_m") or 0) for r in rooms
                              if (r.get("paskirtis") or "").lower() in WET), 2)
        # Bendros medžiagos: 2 sluoksniai × 1.5 kg/m² + sandarinimo juostelė m
        membrana_kg = round(hidro_m2 * 3.0, 2)  # 2 sluoksniai
        pozicijos.append({
            "skyrius": SK_HI,
            "aprasymas": "Hidroizoliacijos įrengimas (paruošimas + 2 sluoksniai + sandarinimo juostelė)",
            "vnt": "vnt", "kiekis": n_wet_zones, "saltinis": SAL,
            "medziagos_aprasymas": "Hidroizoliacijos medžiaga + sandarinimo juostelė (×2 sluoksniai)",
            "medziagos_kiekis": membrana_kg, "medziagos_vnt": "kg",
            # Detail fields — frontend can show on expand
            "_detail_m2": hidro_m2,
            "_detail_juostele_m": wet_perim,
        })

    # ════════════════════════════════════════════════════════════════════════
    # GRINDYS (~5-6 lines)
    # ════════════════════════════════════════════════════════════════════════

    isliginamasis = _sum("isliginamasis_m2")
    if isliginamasis > 0:
        pozicijos.append({
            "skyrius": SK_GR, "aprasymas": "Grindų išlyginamasis sluoksnis",
            "vnt": "m2", "kiekis": isliginamasis, "saltinis": SAL,
            "medziagos_aprasymas": "Savaime išsilyginantis mišinys (~2 kg/m²/mm)",
            "medziagos_kiekis": round(isliginamasis * 6.0, 2),  # ~3mm × 2 kg
            "medziagos_vnt": "kg",
        })

    pvc_grindys = _sum("pvc_grindys_m2")
    if pvc_grindys > 0:
        pozicijos.extend([
            {"skyrius": SK_GR, "aprasymas": "Grindų dangos pamušalas",
             "vnt": "m2", "kiekis": pvc_grindys, "saltinis": SAL,
             "medziagos_aprasymas": "Pamušalo membrana",
             "medziagos_kiekis": pvc_grindys, "medziagos_vnt": "m2"},
            {"skyrius": SK_GR, "aprasymas": "Parketo / laminato klojimas",
             "vnt": "m2", "kiekis": pvc_grindys, "saltinis": SAL,
             "medziagos_aprasymas": "Grindų danga (m² + 10% atliekų)",
             "medziagos_kiekis": round(pvc_grindys * 1.10, 2),
             "medziagos_vnt": "m2"},
        ])

    # Slenksniai — perėjimai tarp patalpų (per kambarį 1 vnt)
    n_slenksniai = max(0, len(rooms) - 1)
    if pvc_grindys > 0 and n_slenksniai > 0:
        pozicijos.append({
            "skyrius": SK_GR, "aprasymas": "Slenksniai (perėjimai tarp patalpų)",
            "vnt": "vnt", "kiekis": n_slenksniai, "saltinis": SAL,
            "medziagos_aprasymas": "Slenksnis (alu / mediena)",
            "medziagos_kiekis": n_slenksniai, "medziagos_vnt": "vnt",
        })

    # ════════════════════════════════════════════════════════════════════════
    # SANTECHNIKOS DARBAI (~7-12 lines)
    # Per-paskirtis defaults: rangovas P1/P2/P5 stiliumi.
    # Tikslumas — count'ai pagal kambario tipą; vartotojas gali keisti.
    # ════════════════════════════════════════════════════════════════════════

    n_vonia = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() == "vonia")
    n_wc = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() == "wc")
    n_san = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() in ("san", "san_mazgas"))
    n_virtuve = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() == "virtuve")
    n_skalbykla = sum(1 for r in rooms if (r.get("paskirtis") or "").lower() == "skalbykla")

    # Pilnos drėgnos patalpos (vonia + wc + san) — turi klozetą + WC rėmą
    n_wet_with_klozetas = n_vonia + n_wc + n_san
    # Vonios — turi dušą + gyvatuką + dušo maišytuvą + lataką
    n_full_bathroom = n_vonia + n_san
    # 2026-06-06 (RC1): basins are NOT 1-per-wet-room — decouple from toilet count;
    # use the detected praustuvė symbol count when higher (Beržų: 3 vs 2).
    n_praustuves = max(n_wet_with_klozetas,
                       int((parsed.get("detected_symbols_summary") or {}).get("praustuves") or 0))

    if n_wet_with_klozetas > 0 or n_virtuve > 0 or n_skalbykla > 0:
        # WC rėmas + Klozetas
        if n_wet_with_klozetas > 0:
            pozicijos.extend([
                {"skyrius": SK_SAN, "aprasymas": "WC rėmo montavimas",
                 "vnt": "vnt", "kiekis": n_wet_with_klozetas, "saltinis": "paskirtis_default",
                 "medziagos_aprasymas": "WC potinkinis rėmas",
                 "medziagos_kiekis": n_wet_with_klozetas, "medziagos_vnt": "vnt"},
                {"skyrius": SK_SAN, "aprasymas": "Klozeto montavimas",
                 "vnt": "vnt", "kiekis": n_wet_with_klozetas, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Praustuvės maišytuvo montavimas",
                 "vnt": "vnt", "kiekis": n_praustuves, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Praustuvės montavimas",
                 "vnt": "vnt", "kiekis": n_praustuves, "saltinis": "paskirtis_default"},
            ])
        # Pilna vonia — dušas + gyvatukas + linijinis latakas
        if n_full_bathroom > 0:
            pozicijos.extend([
                {"skyrius": SK_SAN, "aprasymas": "Dušo maišytuvo sistemos montavimas",
                 "vnt": "vnt", "kiekis": n_full_bathroom, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Gyvatuko montavimas, teno pajungimas",
                 "vnt": "vnt", "kiekis": n_full_bathroom, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Linijinio latako montavimas (dušo zonoje)",
                 "vnt": "vnt", "kiekis": n_full_bathroom, "saltinis": "paskirtis_default"},
            ])
        # Virtuvė — plautuvė + maišytuvas
        if n_virtuve > 0:
            pozicijos.extend([
                {"skyrius": SK_SAN, "aprasymas": "Plautuvės montavimas",
                 "vnt": "vnt", "kiekis": n_virtuve, "saltinis": "paskirtis_default"},
                {"skyrius": SK_SAN, "aprasymas": "Virtuvės maišytuvo montavimas",
                 "vnt": "vnt", "kiekis": n_virtuve, "saltinis": "paskirtis_default"},
            ])
        # Skalbimo mašinos sifonas — skalbyklos arba vonia
        n_skalbimo_sifonas = max(n_skalbykla, 1 if n_full_bathroom > 0 and n_skalbykla == 0 else 0)
        if n_skalbimo_sifonas > 0:
            pozicijos.append({
                "skyrius": SK_SAN, "aprasymas": "Skalbimo mašinos sifono įrengimas",
                "vnt": "vnt", "kiekis": n_skalbimo_sifonas, "saltinis": "paskirtis_default",
            })
            # 2026-05-27 fix (Berzas fixture): truth has Skalbimo mašinos
            # montavimas (=fizinis pajungimas + paruošimas), atskira nuo
            # sifono. App anksčiau visiškai praleisdavo.
            pozicijos.append({
                "skyrius": SK_SAN, "aprasymas": "Skalbimo mašinos montavimas",
                "vnt": "vnt", "kiekis": n_skalbimo_sifonas, "saltinis": "paskirtis_default",
            })
        # Santechnikos taškų koregavimas — visada baseline 1 vnt projektui
        pozicijos.append({
            "skyrius": SK_SAN, "aprasymas": "Santechnikos taškų koregavimas",
            "vnt": "kompl", "kiekis": 1, "saltinis": "baseline"})

    # ════════════════════════════════════════════════════════════════════════
    # ELEKTROS INSTALIACIJOS DARBAI (placeholders — count po Vision symbol counter)
    # rangovas P2/P5 stiliumi. Kiekiai pagal sutartinius ženklus brėžinyje.
    # Šiuo metu placeholder: confidence "low", vartotojas įveda kiekį.
    # Po simbolių extractor'iaus integracijos — automatiškai užpildys.
    # ════════════════════════════════════════════════════════════════════════

    # Symbol counts iš puslapio analizės (pradiniame draft'e — null/0)
    # Vertinam paskirtį turintį detected_symbols arba v9_meta.symbols_detected
    symbols = (parsed.get("v9_meta", {}) or {}).get("symbols_detected") \
              or parsed.get("detected_symbols_summary") \
              or {}
    rozetes_n = int(symbols.get("rozetes") or 0)
    jungikliai_n = int(symbols.get("jungikliai") or 0)
    sviestuvai_n = int(symbols.get("sviestuvai") or 0)
    pakabinami_n = int(symbols.get("pakabinami_sviestuvai") or 0)
    led_juostu_m = float(symbols.get("led_juostos") or 0)
    difuzoriai_n = int(symbols.get("difuzoriai") or 0)

    # Šitos pozicijos pridedam VISADA (kaip Tomos „checklist") — kiekiai 0/null
    # kai nėra duomenų; vartotojas gali įvesti rankiniu būdu.
    el_lines: list[dict] = []
    if rozetes_n + jungikliai_n > 0:
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Rozetės / jungiklio pajungimas",
            "vnt": "vnt", "kiekis": rozetes_n + jungikliai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
    if sviestuvai_n > 0:
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Lubinių priglaistomų šviestuvų montavimas",
            "vnt": "vnt", "kiekis": sviestuvai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Skylių šviestuvams gręžimas",
            "vnt": "vnt", "kiekis": sviestuvai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
    if pakabinami_n > 0:
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Pakabinamų šviestuvų montavimas",
            "vnt": "vnt", "kiekis": pakabinami_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
    if led_juostu_m > 0:
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "LED juostos pajungimas",
            "vnt": "m", "kiekis": round(led_juostu_m, 2),
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
    if difuzoriai_n > 0:
        # rangovas always lists 2 lines per difuzorius: montavimas + apdirbimas
        # (priglaistomas + glaistymo darbas — separate trade tasks)
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Difūzorių montavimas (vėdinimo taškai)",
            "vnt": "vnt", "kiekis": difuzoriai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Difūzorių apdirbimas (priglaistomas)",
            "vnt": "vnt", "kiekis": difuzoriai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })

    # Sprint §40 (2026-04-29): HVAC ortakiai — rangovas audit v2 top gap.
    # 40% premium projektų turi ortakius (D100/125/160 mm). Vision prompt'as
    # papildytas detect'inti ortakių žymėjimus brėžiniuose; jei rasta — emit
    # per-diameter line items. Heuristic fallback: jei `difuzoriai_n > 0` BET
    # ortakių symbols nedetected, emit estimated D125 (most common).
    SK_VENT = "Ventiliacijos darbai"
    ortakiai_d100 = float(symbols.get("ortakiai_d100_m") or 0)
    ortakiai_d125 = float(symbols.get("ortakiai_d125_m") or 0)
    ortakiai_d160 = float(symbols.get("ortakiai_d160_m") or 0)
    ortakiai_total = ortakiai_d100 + ortakiai_d125 + ortakiai_d160

    if ortakiai_total == 0 and difuzoriai_n > 0:
        # Heuristic fallback: average duct run per diffuser ≈ 4-6 m.
        # Use D125 as default (most common single-family residential).
        ortakiai_d125 = round(difuzoriai_n * 5.0, 1)
        ortakiai_total = ortakiai_d125

    if ortakiai_d100 > 0:
        pozicijos.append({
            "skyrius": SK_VENT, "aprasymas": "Ortakių D100 mm montavimas",
            "vnt": "m", "kiekis": ortakiai_d100,
            "saltinis": "simboliai_brezinyje" if symbols.get("ortakiai_d100_m") else "skaiciuota_is_brezinio",
            "medziagos_aprasymas": "Cinkuoti spiralinio tipo ortakiai D100",
            "medziagos_kiekis": round(ortakiai_d100 * 1.05, 1),  # 5% atliekos
            "medziagos_vnt": "m",
        })
    if ortakiai_d125 > 0:
        pozicijos.append({
            "skyrius": SK_VENT, "aprasymas": "Ortakių D125 mm montavimas",
            "vnt": "m", "kiekis": ortakiai_d125,
            "saltinis": "simboliai_brezinyje" if symbols.get("ortakiai_d125_m") else "skaiciuota_is_brezinio",
            "medziagos_aprasymas": "Cinkuoti spiralinio tipo ortakiai D125",
            "medziagos_kiekis": round(ortakiai_d125 * 1.05, 1),
            "medziagos_vnt": "m",
        })
    if ortakiai_d160 > 0:
        pozicijos.append({
            "skyrius": SK_VENT, "aprasymas": "Ortakių D160 mm montavimas",
            "vnt": "m", "kiekis": ortakiai_d160,
            "saltinis": "simboliai_brezinyje" if symbols.get("ortakiai_d160_m") else "skaiciuota_is_brezinio",
            "medziagos_aprasymas": "Cinkuoti spiralinio tipo ortakiai D160",
            "medziagos_kiekis": round(ortakiai_d160 * 1.05, 1),
            "medziagos_vnt": "m",
        })
    if ortakiai_total > 0:
        # rangovas paaiškina: ortakių izoliacija + tvirtinimas — atskiros eilutės
        pozicijos.append({
            "skyrius": SK_VENT, "aprasymas": "Ortakių izoliacija (akmens vata + AlMg folija)",
            "vnt": "m", "kiekis": round(ortakiai_total * 0.7, 1),  # ~70% (in slabs only)
            "saltinis": "skaiciuota_is_brezinio", "confidence": "medium",
        })
        pozicijos.append({
            "skyrius": SK_VENT, "aprasymas": "Ortakių tvirtinimas (kabykės, rankės)",
            "vnt": "vnt", "kiekis": round(ortakiai_total / 1.5),  # ~1 fix per 1.5 m
            "saltinis": "skaiciuota_is_brezinio", "confidence": "medium",
        })
    if sviestuvai_n > 0:
        # Same pair pattern for šviestuvai — rangovas lists montavimas separately
        # from apdirbimas (gipsiniai). We already emit montavimas + skylės
        # above; add apdirbimas as third line.
        el_lines.append({
            "skyrius": SK_EL, "aprasymas": "Šviestuvų apdirbimas (gipsiniai priglaistomi)",
            "vnt": "vnt", "kiekis": sviestuvai_n,
            "saltinis": "simboliai_brezinyje", "confidence": "medium",
        })
    pozicijos.extend(el_lines)

    # ════════════════════════════════════════════════════════════════════════
    # PRIDĖTINIAI ELEMENTAI (~4-5 lines)
    # ════════════════════════════════════════════════════════════════════════

    # Pastolių nuoma — kai patalpoje virš 3 m aukščio (rangovas P1/P4)
    from .universal_rules import is_high_ceiling as _is_high
    high_ceiling_dazymo = round(sum(
        float(r.get("dazymo_plotas_m2") or 0) for r in rooms
        if _is_high(r.get("lubu_aukstis_m"))
    ), 2)
    if high_ceiling_dazymo > 0:
        # ~1 d.d. per ~50 m² didelio aukščio dažomo ploto
        pastoliu_dd = max(1, round(high_ceiling_dazymo / 50))
        pozicijos.append({
            "skyrius": SK_PR, "aprasymas": "Pastolių nuoma (aukštesnių nei 3m)",
            "vnt": "d.d", "kiekis": pastoliu_dd, "saltinis": "lubu_aukstis>3m",
            "medziagos_aprasymas": "Pastoliai (mobilūs)",
            "medziagos_kiekis": pastoliu_dd, "medziagos_vnt": "d.d",
        })

    bendras_plotas = parsed.get("bendras_plotas_m2") or sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if bendras_plotas > 0:
        # Šiukšlių išvežimas — rangovas convention: m³ (volume of waste).
        # Empirical ratio ~0.075 m³/m² for full vidaus apdaila.
        # 2026-05-27 calibration (Berzas fixture): 12 m³ / 165,61 m² = 0,0725.
        # Anksčiau 0,06 davė 9,9 m³ (under by -17%).
        siuksliu_m3 = max(1.0, round(bendras_plotas * 0.075, 1))
        pozicijos.extend([
            {"skyrius": SK_PR, "aprasymas": "Šiukšlių išvežimas (statybinės atliekos)",
             "vnt": "m3", "kiekis": siuksliu_m3, "saltinis": "skaiciuota_is_brezinio",
             "medziagos_aprasymas": "Konteineris + transportas",
             "medziagos_kiekis": siuksliu_m3, "medziagos_vnt": "m3"},
            {"skyrius": SK_PR, "aprasymas": "Statybvietės sutvarkymas po darbų",
             "vnt": "kompl", "kiekis": 1, "saltinis": SAL},
            {"skyrius": SK_PR, "aprasymas": "Apsauginės dangos / juostos darbų metu",
             "vnt": "m2", "kiekis": round(bendras_plotas, 2), "saltinis": SAL,
             "medziagos_aprasymas": "PE plėvelė + dažymo juostos",
             "medziagos_kiekis": round(bendras_plotas, 2), "medziagos_vnt": "m2"},
        ])

    # 2026-06-06: collapse the per-coat glaistymas/dažymas split into the
    # contractor's combined line(s) (flag ENABLE_CONSOLIDATE_PAINT_LINES, default on).
    parsed["pozicijos"] = pozicijos
    _consolidate_paint_pozicijos(parsed)
    pozicijos = parsed["pozicijos"]

    # Sprint §FIX-7 (2026-04-29): stable-sort by skyrius so all GKP/Plytelių/etc.
    # lines stay grouped even when generator interleaves emit order.
    # User reported „2 GKP montavimas sections" in Excel because „Angokraščių
    # apdirbimas GKP" (SK_GKP) emits BEFORE the main painting block, then the
    # rest of GKP montavimas emits AFTER. Stable sort fixes both Excel sheets
    # and frontend grouping.
    SKYRIUS_ORDER = {
        "Sienų lubų glaistymas dažymas": 1,
        "GKP montavimas":                2,
        "Plytelių klijavimas":           3,
        "Hidroizoliacija":               4,
        "Grindys":                       5,
        "Santechnikos darbai":           6,
        "Ventiliacijos darbai":          7,
        "Elektros instaliacijos darbai": 8,
        "Pridėtiniai elementai":         9,
    }
    pozicijos.sort(key=lambda p: SKYRIUS_ORDER.get(p.get("skyrius", "Pridėtiniai elementai"), 999))

    parsed["pozicijos"] = pozicijos

    # 2026-06-11: per-pozicija confidence (class calibration + apdailos
    # self-reported confidence + voting flags). Measured false-green rate was
    # 50-60% before this pass — see docs/superpowers/research/
    # 2026-06-11-experiments-results.md.
    from .confidence import apply_confidence
    apply_confidence(parsed)
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
        # The two GKP-ceiling fields are produced by calc_room_quantities and
        # already account for partial high-ceiling zones (high_ceiling_area_m2
        # override). When they're present we use them directly and skip the
        # plotas-based fallback in calc_totals (that fallback assumes the
        # entire room is at a single height). The neutral sentinel — None
        # rather than 0 — preserves backwards-compat with paths that
        # legitimately want the fallback (eg. Vision-direct rooms without a
        # recompute pass).
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
            "silikonavimas_m": r.get("silikonavimas_m", 0),
            "hidroizoliacija_m2": r.get("hidroizoliacija_m2", 0),
            "lubu_tipas": r.get("lubu_tipas", "gkp"),
            "lubu_aukstis_m": r.get("lubu_aukstis_m", 2.82),
            "paskirtis": r.get("paskirtis", "gyvenamoji"),
            "gkp_lubu_standart_m2": r.get("gkp_lubu_standart_m2"),
            "gkp_lubu_virs_3m_m2": r.get("gkp_lubu_virs_3m_m2"),
        })

    totals = calc_totals(mapped_rooms)

    # Items 16+17 in LT samata billing structure combine sienų+lubų paint for
    # non-garažas rooms only — garažas paint is billed as separate items with
    # different unit prices. Emit a santrauka field that mirrors that slice so
    # the contractor-truth comparison in the eval harness is apples-to-apples.
    house_paint_total = sum(
        float(r.get("dazymo_plotas_m2") or 0)
        for r in rooms
        if (r.get("paskirtis") or "").lower() != "garazas"
    )

    # Build santrauka in Vision schema format
    parsed["santrauka"] = {
        "dazymo_plotas_total_m2": totals.get("dazymo_plotas_total_m2", 0),
        "dazymo_excl_garazas_total_m2": round(house_paint_total, 2),
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
        "silikonavimas_m_total": totals.get("silikonavimas_m_total", 0),
        "hidroizoliacijos_vnt": totals.get("hidroizoliacijos_vnt", 0),
    }
    return parsed


def _run_pass1_once(client, system, pages, *,
                    native_pdf: dict | None = None,
                    model: str | None = None) -> dict:
    """One Pass-1 extraction (≤3 retries). Returns the parsed dict (with
    `_meta`) on success, or an error dict `{"status":"error", ...}` on failure
    — same error shapes the old inline loop returned.

    native_pdf: payload from _prepare_native_pdf. With "b64" → the page
    subset goes as ONE document block (image + text layer per page); with
    "fallback_reason" → image blocks as usual, fallback recorded in
    _meta.experiment. None → default image blocks.

    B-1 lock-in condition (2026-07-04): if the API rejects the document
    payload (anthropic.BadRequestError) — or the same document payload fails
    twice for any reason — this round rebuilds its content as raster images
    and retries. The shared native_pdf dict is flipped in place, so the
    REMAINING voting rounds also go raster (no per-round re-tripping).
    Recorded as fallback_reason="api_rejected_document".

    model (EXPERIMENT SAMATU_VOTING_MODELS): per-round model override for
    mixed-model voting. None → model_for("vision_pass1") as always.
    """
    last_err: Exception | None = None
    model = model or model_for("vision_pass1")  # resolved per-run (MODEL_OVERRIDE etc.)

    experiment_meta: dict | None = None
    using_document = False
    if native_pdf and native_pdf.get("b64"):
        user_content = build_user_content_pdf_native(
            native_pdf["b64"], native_pdf["n_pages"],
            native_pdf.get("page_map_note"),
        )
        using_document = True
        experiment_meta = {"native_pdf": {
            "input": "document",
            "pdf_pages": native_pdf["n_pages"],
            "pdf_b64_bytes": native_pdf["b64_bytes"],
            "page_map_note_sent": bool(native_pdf.get("page_map_note")),
        }}
    elif native_pdf and native_pdf.get("fallback_reason"):
        user_content = build_user_content(pages)
        experiment_meta = {"native_pdf": {
            "input": "image_fallback",
            "fallback_reason": native_pdf["fallback_reason"],
        }}
    else:
        user_content = build_user_content(pages)
    # B-2: the text-richness median is the production segmentation metric —
    # record it on every native-considered run, document mode or fallback.
    if experiment_meta and native_pdf and "text_median_chars_page" in native_pdf:
        experiment_meta["native_pdf"]["text_median_chars_page"] = \
            native_pdf["text_median_chars_page"]

    def _flip_to_image_fallback(reason: str) -> None:
        """B-1: rebuild this round as raster images AND flip the shared
        native_pdf payload so subsequent voting rounds skip the document
        path entirely (payload is shared across rounds by design)."""
        nonlocal user_content, experiment_meta, using_document
        native_pdf.pop("b64", None)
        native_pdf["fallback_reason"] = reason
        user_content = build_user_content(pages)
        experiment_meta = {"native_pdf": {
            "input": "image_fallback",
            "fallback_reason": reason,
        }}
        if "text_median_chars_page" in native_pdf:
            experiment_meta["native_pdf"]["text_median_chars_page"] = \
                native_pdf["text_median_chars_page"]
        using_document = False

    max_attempts = 3
    attempt = 0
    doc_failures = 0
    while attempt < max_attempts:
        try:
            with client.with_options(timeout=VISION_TIMEOUT_S).messages.stream(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user_content}],
                output_config={"effort": "high"},
            ) as stream:
                resp = stream.get_final_message()

            if resp.stop_reason == "refusal":
                return {"status": "error", "_error": "model_refused", "_stop_reason": "refusal"}
            if resp.stop_reason == "max_tokens":
                return {"status": "error", "_error": "output_truncated", "_stop_reason": "max_tokens"}

            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(_repair_json(text))
                    parsed["_repaired"] = True
                except json.JSONDecodeError as je:
                    return {"status": "error", "_error": "json_decode_failure",
                            "_raw_text": text[:4000], "_je": str(je)}

            usage = resp.usage
            parsed["_meta"] = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
                "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                "stop_reason": resp.stop_reason,
                "attempt": attempt + 1,
                "pages_sent": len(pages),
                "model": model,
            }
            if experiment_meta:
                parsed["_meta"]["experiment"] = experiment_meta
            return parsed
        except Exception as exc:
            last_err = exc
            print(f"[extractor] attempt {attempt + 1} failed: {exc}")
            if using_document:
                doc_failures += 1
                if isinstance(exc, anthropic.BadRequestError) or doc_failures >= 2:
                    print("[experiment:native_pdf] API rejected the document "
                          f"payload ({type(exc).__name__}) → retrying this and "
                          "all remaining rounds as raster images")
                    _flip_to_image_fallback("api_rejected_document")
                    attempt = 0  # fresh retry budget for the image path
                    continue
            attempt += 1
            if attempt >= max_attempts:
                return {"status": "error", "_error": f"vision_call_failed: {exc}"}
            time.sleep(1.5 ** (attempt - 1))
    return {"status": "error", "_error": str(last_err or "Unknown error")}


def _resolve_floor_b64(pages, runs):
    """Pick the floor-plan page image for the adjacency pass.

    The rooms live on a specific page (Vision reports it as scale_source_page,
    or the rooms' modal puslapio_nr). pages[0] is often a title/site sheet, so
    blindly using it makes the adjacency pass read a page with no rooms → 0
    matches → n_partition_walls never set. Resolve the real floor page.
    """
    idx = None
    for r in runs:
        if r.get("scale_source_page"):
            idx = int(r["scale_source_page"])
            break
    if idx is None:  # modal puslapio_nr across rooms
        from collections import Counter
        c = Counter(int(rm["puslapio_nr"]) for r in runs
                    for rm in (r.get("patalpos") or []) if rm.get("puslapio_nr"))
        if c:
            idx = c.most_common(1)[0][0]
    if idx is not None:
        for p in pages:
            if int(p.get("page_index") or -1) == idx:
                return p["image_b64"], idx
    return (pages[0]["image_b64"], pages[0].get("page_index")) if pages else (None, None)


def _run_pass1_voted(client, system, pages, n, _emit, *,
                     native_pdf: dict | None = None) -> dict:
    """Run Pass-1 ``n`` times (+ one shared adjacency pass) and median-vote into
    a single consensus parsed dict.

    The adjacency pass wires ``n_partition_walls`` (and the _exterior window
    flags) into production — these were only ever computed by the offline
    benchmark script before. Median voting means a single adjacency-bail or
    perimeter-jitter run can't tank the consensus. Degrades gracefully: 0 good
    runs → error; 1 good run → that run (adjacency still applied).

    native_pdf: EXPERIMENT payload forwarded to every round (see
    _run_pass1_once). Byte-identical across rounds → cache-friendly.

    EXPERIMENT (SAMATU_VOTING_MODELS="m1,m2,m3"): mixed-model voting — the
    env lists the model PER round (its length overrides ``n``); rounds are
    grouped so same-model rounds run consecutively (prompt cache is
    per-model). Aggregation (vote_extraction) is untouched; per-round
    models + tokens + cost land in _meta.voting_models.
    """
    from .vision.extraction_voter import vote_extraction

    mixed_models = _mixed_voting_models()
    if mixed_models:
        round_models: list[str | None] = list(_group_rounds_by_model(mixed_models))
        n = len(round_models)
        print(f"[voting] mixed-model experiment: rounds → {round_models}")
    else:
        round_models = [None] * n

    def _round_cost_usd(meta: dict) -> float | None:
        """Price one round at ITS model's rates (best-effort — unknown model
        rates must not fail the extraction)."""
        try:
            from pricing import calc_claude_cost_usd
            return round(calc_claude_cost_usd(
                input_tokens=int(meta.get("input_tokens") or 0),
                output_tokens=int(meta.get("output_tokens") or 0),
                cache_read_tokens=int(meta.get("cache_read_tokens") or 0),
                cache_write_tokens=int(meta.get("cache_write_tokens") or 0),
                model=meta.get("model") or "",
            ), 4)
        except Exception:
            return None

    # Run all Pass-1 rounds FIRST so we know which page the rooms are on.
    runs: list[dict] = []
    per_round_meta: list[dict] = []
    for i in range(n):
        _emit({"event": "voting_round_started", "round": i + 1, "of": n,
               "model": round_models[i]})
        p = _run_pass1_once(client, system, pages, native_pdf=native_pdf,
                            model=round_models[i])
        if p.get("status") == "error":
            print(f"[voting] round {i + 1} failed: {p.get('_error')}")
            _emit({"event": "voting_round_failed", "round": i + 1, "error": p.get("_error")})
            if mixed_models:
                per_round_meta.append({"round": i + 1, "model": round_models[i],
                                       "error": p.get("_error")})
            continue
        runs.append(p)
        if mixed_models:
            _rm = p.get("_meta") or {}
            per_round_meta.append({
                "round": i + 1,
                "model": _rm.get("model") or round_models[i],
                "input_tokens": int(_rm.get("input_tokens") or 0),
                "output_tokens": int(_rm.get("output_tokens") or 0),
                "cache_read_tokens": int(_rm.get("cache_read_tokens") or 0),
                "cache_write_tokens": int(_rm.get("cache_write_tokens") or 0),
                "cost_usd": _round_cost_usd(_rm),
            })
        _emit({"event": "voting_round_completed", "round": i + 1,
               "rooms": len(p.get("patalpos") or [])})

    if not runs:
        return {"status": "error", "_error": "all_voting_runs_failed"}

    # Adjacency: one shared pass on the RESOLVED floor-plan page (cached by image
    # hash), applied to every run's rooms. Best-effort — failure leaves
    # n_partition_walls unset, exactly the pre-voting production behaviour.
    floor_b64, floor_idx = _resolve_floor_b64(pages, runs)
    adj = None
    if floor_b64:
        try:
            from .vision.adjacency_extractor import extract_adjacency, apply_adjacency_to_rooms
            adj = extract_adjacency(image_b64=floor_b64, client=client)
            n_set = 0
            for p in runs:
                summary = apply_adjacency_to_rooms(p.get("patalpos") or [], adj)
                n_set += (summary or {}).get("n_rooms_matched", 0)
            print(f"[voting] adjacency on page {floor_idx}: matched rooms across runs={n_set}")
            _emit({"event": "adjacency_applied", "page": floor_idx, "rooms_matched": n_set})
        except Exception as exc:
            print(f"[voting] adjacency failed (n_partition_walls→0): {exc}")

    def _attach_mixed_vote_meta(meta: dict) -> None:
        """Record mixed-model provenance: per-round model/tokens/cost split
        (each round priced at ITS OWN model's rates — pricing per-model caches
        and rates differ) + the run order. Consumed by
        pricing.calc_meta_cost_usd so cost aggregation stays correct."""
        if not mixed_models:
            return
        meta["voting_models"] = per_round_meta
        costs = [r["cost_usd"] for r in per_round_meta if r.get("cost_usd") is not None]
        meta["voting_cost_usd"] = round(sum(costs), 4) if costs else None
        meta.setdefault("experiment", {})["mixed_vote"] = {
            "models_requested": mixed_models,
            "models_run_order": [m for m in round_models],
        }

    if len(runs) == 1:
        runs[0]["_voting"] = {"n_runs": 1, "degraded": True,
                              "note": "only 1 of N runs succeeded — unvoted"}
        _attach_mixed_vote_meta(runs[0].setdefault("_meta", {}))
        return runs[0]

    voted = vote_extraction(runs, min_votes=2)
    # Cost metering (2026-06-19): a voted extraction made N Pass-1 Vision calls,
    # so SUM the token usage across all runs — keeping only runs[0] would make the
    # per-user spend ledger undercount by ~N×. Other _meta keys come from runs[0].
    _tok_sum = {}
    for _k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
        _tok_sum[_k] = sum(int((r.get("_meta") or {}).get(_k) or 0) for r in runs)
    voted["_meta"] = {**runs[0].get("_meta", {}), **_tok_sum, "voting_runs": len(runs)}
    _attach_mixed_vote_meta(voted["_meta"])
    return voted


def extract_interior(
    pdf_bytes: bytes,
    rules_override: dict | None = None,
    progress_cb=None,
) -> dict:
    """Single Vision call entry point. PDF bytes → structured takeoff JSON.

    Args:
        pdf_bytes: Raw PDF bytes (single file)
        rules_override: Optional Setup Wizard preferences dict; attached to result
                        as _overrides for downstream UI use.
        progress_cb: Optional callable(event_dict) fired at lifecycle checkpoints
                     for SM01 streaming UI. Failures swallowed — never break the
                     extraction itself if a downstream consumer raises.
    Returns: parsed JSON dict with `patalpos`, `santrauka`, `pozicijos`, etc.
             On error returns {"_error": "...", "status": "error"}.
             On success returns {..., "status": "ok", "_meta": {...}}.
    """
    t0 = time.time()
    client = anthropic.Anthropic()

    def _emit(ev: dict) -> None:
        if not progress_cb:
            return
        try:
            progress_cb(ev)
        except Exception as exc:
            print(f"[extractor] progress_cb raised: {exc}")

    system = [
        {"type": "text", "text": SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]

    # Step 1: PDF → base64 images
    _emit({"event": "rendering_pdf"})
    try:
        pages = pdf_to_b64_images(pdf_bytes)
    except Exception as exc:
        _emit({"event": "error", "message": f"pdf_to_images_failed: {exc}"})
        return {
            "status": "error",
            "_error": f"pdf_to_images_failed: {exc}",
        }

    if not pages:
        _emit({"event": "error", "message": "PDF has no renderable pages"})
        return {
            "status": "error",
            "_error": "PDF has no renderable pages",
        }

    # Step 1.1 (Sprint E1, 2026-04-28): cost-safe filter — drop vendor quote
    # pages from Pass-1 input. Detected via pdfplumber text heuristics (zero
    # API cost, zero accuracy risk — these pages have no room/dimension data,
    # only supplier price catalogs that the designer stapled into the bundle).
    # page_index field on each page preserves the ORIGINAL 1-based number so
    # `room.puslapio_nr` references stay correct downstream.
    try:
        from .page_filter import detect_vendor_quote_pages
        vendor_pages = detect_vendor_quote_pages(pdf_bytes)
        if vendor_pages:
            original_count = len(pages)
            pages = [p for p in pages if p["page_index"] not in vendor_pages]
            print(f"[extractor] vendor filter: skipped {original_count - len(pages)} "
                  f"pages (indices: {sorted(vendor_pages)}); {len(pages)} → Vision")
    except Exception as exc:
        # Non-fatal: if filter fails, fall through with all pages
        print(f"[extractor] vendor page filter failed: {exc}")
        vendor_pages = set()

    _emit({"event": "started", "page_count": len(pages),
           "vendor_pages_skipped": sorted(vendor_pages) if vendor_pages else []})

    # Step 1.5: Pre-pass — read eksplikacija + schedule tables for ground-truth anchoring.
    _emit({"event": "eksplikacija_started"})
    try:
        from .eksplikacija_reader import read_eksplikacija
        eks = read_eksplikacija(pdf_bytes, client)
    except Exception as exc:
        print(f"[extractor] eksplikacija pre-pass failed: {exc}")
        eks = {"patalpos": [], "schedule_tables": {"durys": [], "langai": []}}
    _emit({
        "event": "eksplikacija_completed",
        "rooms_in_table": len(eks.get("patalpos", [])),
        "doors_in_table": len(eks.get("schedule_tables", {}).get("durys", [])),
        "windows_in_table": len(eks.get("schedule_tables", {}).get("langai", [])),
    })

    # Step 2: Vision call — single pass, or N-pass median voting (flag-gated).
    # Voting stabilises the high-variance Pass-1 (perimeters, ceiling heights,
    # symbol counts) and wires the adjacency pass into production so the kampai
    # pusiniai term is populated on real uploads, not just the benchmark.
    from .feature_flags import get_flags as _get_flags, voting_n as _voting_n
    _vflags = _get_flags()
    _voting_on = bool(_vflags.get("extraction_voting"))
    _emit({"event": "pass1_started", "page_count": len(pages), "voting": _voting_on})

    # Native-PDF Pass-1 (default ON since the 2026-07-04 B-3 lock-in): build
    # the document payload ONCE (byte-identical across voting rounds →
    # cache-friendly) and forward it to Pass-1. SAMATU_PDF_NATIVE=0 escape
    # hatch → _native_pdf stays None, raster images exactly as before.
    _native_on, _native_why = _pdf_native_mode()
    print(f"[extractor] pass1 input mode: "
          f"{'native_pdf' if _native_on else 'raster_images'} — {_native_why}")
    _native_pdf = None
    if _native_on:
        _native_pdf = _prepare_native_pdf(pdf_bytes, pages)
        _emit({"event": "native_pdf_prepared",
               "input": "document" if _native_pdf.get("b64") else "image_fallback",
               "fallback_reason": _native_pdf.get("fallback_reason"),
               "pdf_pages": _native_pdf.get("n_pages"),
               "pdf_b64_bytes": _native_pdf.get("b64_bytes"),
               "text_median_chars_page": _native_pdf.get("text_median_chars_page")})

    if _voting_on:
        parsed = _run_pass1_voted(client, system, pages, _voting_n(), _emit,
                                  native_pdf=_native_pdf)
    else:
        parsed = _run_pass1_once(client, system, pages, native_pdf=_native_pdf)

    if not parsed or parsed.get("status") == "error":
        # Error shapes (model_refused, output_truncated, json_decode_failure,
        # vision_call_failed, all_voting_runs_failed) are returned verbatim so
        # callers see the same payloads as before.
        err = (parsed or {}).get("_error", "Unknown error")
        _emit({"event": "error", "message": str(err)})
        return parsed or {"status": "error", "_error": "Unknown error"}

    # Roll the eksplikacija PRE-pass Vision-fallback tokens into extra_calls now
    # that `parsed` (and its Pass-1 _meta) exists. No-op on the pdfplumber path
    # (source-only _meta, no model → free, not billed). The pre-pass ran before
    # Pass-1 above, so it couldn't attach to `parsed` at its own call site.
    _append_extra_call(parsed, (eks or {}).get("_meta"))

    _pass1_rooms = parsed.get("patalpos") or []
    _emit({
        "event": "pass1_completed",
        "rooms_count": len(_pass1_rooms),
        "patalpos": [
            {
                "nr": r.get("nr"),
                "pavadinimas": r.get("pavadinimas"),
                "paskirtis": r.get("paskirtis"),
                "plotas_m2": r.get("plotas_m2"),
                "puslapio_nr": r.get("puslapio_nr"),
                "confidence": r.get("confidence"),
            }
            for r in _pass1_rooms
        ],
    })

    # Step 2.35: Sprint 0 Fix 5 — resolve paint class from spec inference (flag-gated).
    # Vision may return inferred_paint_class + inferred_paint_class_evidence when the
    # spec explicitly states a finish quality (e.g., 'Q2 matinis', 'Q4 blizgus').
    # _resolve_paint_class gates on ENABLE_PAINT_CLASS_INFERENCE; falls back to user default.
    try:
        inferred_cls = parsed.get("inferred_paint_class")
        inferred_text = parsed.get("inferred_paint_class_evidence")
        user_default = int((rules_override or {}).get("paint_class", 2))
        final_class, source = _resolve_paint_class(user_default, inferred_cls, inferred_text)
        parsed["paint_class"] = final_class
        parsed["paint_class_source"] = source
        # Wire-through: inject resolved paint_class into rules_override so Step 2.9's
        # _resolve_paint_class_from_prefs() picks it up. Without this, the inferred value
        # was visible in metadata (parsed["paint_class"]) but never reached dazai_l math.
        if rules_override is None:
            rules_override = {}
        rules_override["paint_class"] = final_class
    except Exception as exc:
        print(f"[extractor] paint_class inference resolve failed (non-fatal): {exc}")

    # Step 2.4: Merge eksplikacija ground truth into rooms by name match (case-insensitive).
    # Eksplikacija plotas/perimetras override Vision dimension-chain values when available.
    rooms = parsed.get("patalpos") or []
    try:
        eks_by_name = {
            (r.get("pavadinimas") or "").strip().lower(): r
            for r in eks.get("patalpos", [])
        }
        merged_count = 0
        for room in rooms:
            name = (room.get("pavadinimas") or "").strip().lower()
            eks_row = eks_by_name.get(name)
            if eks_row:
                if eks_row.get("plotas_m2"):
                    room["plotas_m2"] = eks_row["plotas_m2"]
                    room["plotas_saltinis"] = "eksplikacija"
                if eks_row.get("perimetras_m"):
                    room["perimetras_m"] = eks_row["perimetras_m"]
                room["eksplikacija_row_idx"] = eks_row.get("row_idx")
                # Per-row bbox + page dims (pdfplumber only; Vision pre-pass
                # doesn't compute these). Frontend uses them to overlay a
                # highlight on the eksplikacija page when this room is focused.
                if eks_row.get("eksplikacija_row_bbox"):
                    room["eksplikacija_row_bbox"] = eks_row["eksplikacija_row_bbox"]
                if eks_row.get("eksplikacija_page_width_pdf"):
                    room["eksplikacija_page_width_pdf"] = eks_row["eksplikacija_page_width_pdf"]
                if eks_row.get("eksplikacija_page_height_pdf"):
                    room["eksplikacija_page_height_pdf"] = eks_row["eksplikacija_page_height_pdf"]
                merged_count += 1
        parsed.setdefault("_meta", {})["eksplikacija_merged_rooms"] = merged_count
        parsed["_meta"]["eksplikacija_total_rows"] = len(eks.get("patalpos", []))
        parsed["_eksplikacija"] = eks  # full pre-pass result for frontend reference
        _emit({
            "event": "eksplikacija_merged",
            "merged_rooms": merged_count,
            "total_rows": len(eks.get("patalpos", [])),
        })
    except Exception as exc:
        print(f"[extractor] eksplikacija merge failed: {exc}")

    # Step 2.45: Schedule-table anchoring for window/door dimensions (Sprint 2).
    # Each room.elementai item with tipas in (langas, stoglangis, duris, pasleptos_duris)
    # is matched against schedule_tables.langai/durys by dimension proximity (±50mm).
    # On match: override plotis_mm/aukstis_mm with EXACT schedule values, mark
    # `_schedule_anchored: True` and `_schedule_id: "L1"` etc. for UI surfacing.
    # Also emits a count-sanity warning if room totals diverge from schedule by >15%.
    try:
        sched = (eks.get("schedule_tables") or {})
        sched_langai = sched.get("langai") or []
        sched_durys = sched.get("durys") or []
        DIM_TOL_MM = 50

        def _match(elem_w, elem_h, candidates):
            if not elem_w or not elem_h:
                return None
            best, best_dist = None, DIM_TOL_MM + 1
            for s in candidates:
                sw, sh = s.get("plotis_mm"), s.get("aukstis_mm")
                if not sw or not sh:
                    continue
                d = abs(sw - elem_w) + abs(sh - elem_h)
                if d < best_dist:
                    best, best_dist = s, d
            return best if best_dist <= DIM_TOL_MM * 2 else None

        anchored_count = 0
        room_langai_total = 0
        room_durys_total = 0
        for room in rooms:
            for elem in (room.get("elementai") or []):
                tipas = elem.get("tipas")
                ew = elem.get("plotis_mm")
                eh = elem.get("aukstis_mm")
                count = elem.get("kiekis") or 1
                if tipas in ("langas", "stoglangis"):
                    room_langai_total += count
                    matched = _match(ew, eh, sched_langai)
                    if matched:
                        elem["plotis_mm"] = matched["plotis_mm"]
                        elem["aukstis_mm"] = matched["aukstis_mm"]
                        elem["_schedule_anchored"] = True
                        elem["_schedule_id"] = matched.get("id")
                        anchored_count += 1
                elif tipas in ("duris", "pasleptos_duris"):
                    room_durys_total += count
                    matched = _match(ew, eh, sched_durys)
                    if matched:
                        elem["plotis_mm"] = matched["plotis_mm"]
                        elem["aukstis_mm"] = matched["aukstis_mm"]
                        elem["_schedule_anchored"] = True
                        elem["_schedule_id"] = matched.get("id")
                        anchored_count += 1

        sched_langai_total = sum((s.get("kiekis") or 1) for s in sched_langai)
        sched_durys_total = sum((s.get("kiekis") or 1) for s in sched_durys)
        parsed.setdefault("_meta", {})["schedule_anchored_elements"] = anchored_count
        parsed["_meta"]["schedule_count_check"] = {
            "langai_room_total": room_langai_total,
            "langai_schedule_total": sched_langai_total,
            "durys_room_total": room_durys_total,
            "durys_schedule_total": sched_durys_total,
        }

        # Emit count-mismatch warnings (>15% divergence and schedule has data).
        warnings = parsed.get("warnings") or []
        for label, room_n, sched_n in [
            ("langų", room_langai_total, sched_langai_total),
            ("durų",  room_durys_total,  sched_durys_total),
        ]:
            if sched_n > 0 and abs(room_n - sched_n) / sched_n > 0.15:
                warnings.append({
                    "level": "WARN",
                    "message": (
                        f"Patalpose suskaičiuota {room_n} {label}, bet "
                        f"specifikacijos lentelėje {sched_n}. Skirtumas "
                        f"{abs(room_n - sched_n)} vnt. — patikrinkite ar visi "
                        f"{label} priskirti patalpoms."
                    ),
                })
        parsed["warnings"] = warnings

        _emit({
            "event": "schedule_anchored",
            "anchored_elements": anchored_count,
            "langai_match": f"{room_langai_total}/{sched_langai_total}",
            "durys_match": f"{room_durys_total}/{sched_durys_total}",
        })
    except Exception as exc:
        print(f"[extractor] schedule anchor merge failed: {exc}")

    # Sprint 2: shared-walls polygon pre-pass (feature-flag-gated by
    # ENABLE_POLYGON_PREPASS). Applies BEFORE per-room ceiling heights so
    # corrected perimetras_m feeds into downstream calculations.
    try:
        parsed = _apply_polygon_prepass(parsed)
        _emit({
            "event": "polygon_prepass_applied",
            "rooms_with_adjacency": sum(
                1 for r in (parsed.get("patalpos") or [])
                if r.get("perimetras_saltinis") == "polygon_adjacency"
            ),
        })
    except Exception as exc:
        print(f"[extractor] polygon prepass failed: {exc}")

    try:
        parsed = _validate_room_bboxes(parsed)
    except Exception as exc:
        print(f"[extractor] bbox validation failed: {exc}")

    # Step 2.4.5: deterministic ceiling-height fallback.
    # Vision sometimes misses tall ceilings (>3 m) annotated as `+3.000` on
    # section / ceiling-plan pages, defaulting to ~2.80 m and skewing every
    # wall-paint quantity downstream.
    #
    # 2026-05-11 W1 audit: the prior "section_pages + (1,)" coverage was
    # wrong for real LT projects — pjūviai routinely sit on back pages
    # (verified empirically against the interior corpus), not p1. And
    # page_classifier may not see those back pages at all (cost-gated
    # to first N pages). Scanner is cheap text extraction; scan ALL
    # pages, let best_ceiling_candidate filter to [2.0, 4.5] m range.
    #
    # Override threshold tightened 0.30 → 0.15 (asymmetric "going up"):
    # if Vision said 2.80 and marker says 3.00, diff 0.20 — used to be
    # ignored, now overrides correctly. Soviet 2.50m default protected
    # by `cand_m > 2.95` guard.
    try:
        from extractor.height_markers import (
            best_ceiling_candidate,
            scan_page_height_markers,
        )
        # Scan every page. Filter to plausible ceiling values happens in
        # height_markers.MIN_CEILING_M / MAX_CEILING_M. Cost: ~50ms/page
        # in pdfplumber for text extraction (no Vision call).
        try:
            import pdfplumber as _pp
            import io as _io
            with _pp.open(_io.BytesIO(pdf_bytes)) as _doc:
                num_pages = len(_doc.pages)
        except Exception:
            num_pages = 0
        scan_pages = tuple(range(1, num_pages + 1)) if num_pages else (1,)
        markers = scan_page_height_markers(pdf_bytes, page_nrs=scan_pages)
        if not markers:
            _emit({
                "event": "no_height_markers",
                "reason": "text_layer_empty_or_flattened_or_no_markers",
                "scan_pages_count": len(scan_pages),
            })
        candidate = best_ceiling_candidate(markers)
        if candidate is not None:
            cand_m = candidate["value_m"]
            section_h = parsed.get("lubu_aukstis_m")
            # Asymmetric guard: only override "going up" to a clearly
            # taller value (>2.95m). Prevents trampling legitimate
            # Soviet-era 2.50m readings with a stray +2.40 beam marker.
            should_override = (
                section_h is None
                or (cand_m > 2.95 and float(section_h) < cand_m - 0.15)
            )
            if should_override:
                parsed["lubu_aukstis_m"] = cand_m
                warnings_list = list(parsed.get("warnings") or [])
                marker_raw = candidate["raw"]
                warnings_list.append({
                    "code": "ceiling_height_from_section_marker",
                    "severity": "info",
                    "message": (
                        f"Lubų aukštis paimtas iš pjūvio žymeklio "
                        f"{marker_raw} → {cand_m:.2f} m "
                        f"(psl. {candidate['page']}). Patikrink Prielaidose."
                    ),
                })
                parsed["warnings"] = warnings_list
                _emit({
                    "event": "ceiling_height_from_marker",
                    "value_m": cand_m,
                    "raw": candidate["raw"],
                    "page": candidate["page"],
                    "previous": section_h,
                })
    except Exception as exc:
        print(f"[extractor] height marker scan failed: {exc}")

    # Step 2.45: Apply per-room ceiling heights when Vision provided them
    # (Sprint 0 Fix 4, gated by ENABLE_PER_ROOM_CEILING).
    #
    # 2026-05-11 W2: Vision sometimes only reads room *numbers* from the
    # lubų plan annotations (e.g. "102=+3400") and can't map them to
    # eksplikacija names. Accept lubu_auksciai_by_nr as a second source
    # and merge into lubu_auksciai via patalpa.nr lookup.
    #
    # 2026-05-11 W2 (afternoon): even with imperative prompt iteration,
    # Vision still narrates height info in warnings[] text on 2/5 corpus
    # PDFs (projektas_3 "švarus lubų aukštis 300cm", projektas_4(2)
    # "3200mm visose voniose"). Add a regex salvage pass that mines
    # warning text for height patterns and merges them into
    # lubu_auksciai when the model didn't structure them itself.
    try:
        per_room_heights = dict(parsed.get("lubu_auksciai") or {})
        per_room_by_nr = parsed.get("lubu_auksciai_by_nr") or {}
        rooms_raw = parsed.get("patalpos") or []
        # Map numeric keys → room names via patalpa.nr; merge so any name
        # the model emitted directly via lubu_auksciai wins (model already
        # did the mapping reliably).
        if per_room_by_nr:
            for room in rooms_raw:
                room_nr = str(room.get("nr") or "").strip()
                if not room_nr:
                    continue
                h_for_nr = per_room_by_nr.get(room_nr) or per_room_by_nr.get(int(room_nr) if room_nr.isdigit() else None)
                if h_for_nr is None:
                    continue
                name = room.get("pavadinimas")
                if name and name not in per_room_heights:
                    per_room_heights[name] = float(h_for_nr)
            parsed["lubu_auksciai"] = per_room_heights

        # Salvage from narrative warnings[]: when prompt iteration didn't
        # fully prevent Vision from describing heights in free text, we
        # mine the text for known patterns and apply them deterministically.
        if not per_room_heights and rooms_raw:
            from extractor.height_markers import salvage_heights_from_warnings
            salvaged = salvage_heights_from_warnings(
                parsed.get("warnings") or [], rooms_raw
            )
            if salvaged:
                per_room_heights.update(salvaged)
                parsed["lubu_auksciai"] = per_room_heights
                _emit({
                    "event": "lubu_auksciai_salvaged_from_warnings",
                    "salvaged_count": len(salvaged),
                    "rooms": list(salvaged.keys()),
                })
        section_avg = float(parsed.get("lubu_aukstis_m") or 2.82)
        rooms_raw = _apply_per_room_heights(
            rooms_raw, per_room_heights, section_avg, name_key="pavadinimas"
        )
        parsed["patalpos"] = rooms_raw
        _emit({
            "event": "per_room_ceiling_applied",
            "rooms_with_per_room": sum(
                1 for r in rooms_raw if r.get("lubu_aukstis_saltinis") == "per_room"
            ),
            "source_count_by_nr": len(per_room_by_nr),
            "source_count_by_name": len(parsed.get("lubu_auksciai") or {}),
        })
    except Exception as exc:
        print(f"[extractor] per-room ceiling height apply failed: {exc}")

    # Re-bind `rooms` to the persisted list so the Pass-2 zoom loop below mutates
    # the SAME room dicts that live in parsed["patalpos"]. _apply_per_room_heights
    # reassigns parsed["patalpos"] to a new list; without this rebind the zoom
    # loop wrote per-room ceiling heights onto a stale earlier binding and the
    # recovery was silently lost (every room fell back to the section average).
    rooms = parsed.get("patalpos") or rooms

    # 2026-06-11: deterministic height-plausibility gate. Vision sometimes puts
    # the tall ceiling on small wet rooms (Bacevičiaus: 3.5 m on a 6.8 m² vonia)
    # while the large svetainė gets the default — inverting the iki/virš-3m split.
    try:
        from .universal_rules import apply_height_plausibility_gate
        _hc = apply_height_plausibility_gate(rooms)
        if _hc:
            parsed.setdefault("_meta", {})["height_gate_corrections"] = _hc
            _emit({"event": "height_gate_applied", "corrections": _hc})
    except Exception as exc:
        print(f"[extractor] height plausibility gate failed: {exc}")

    # Step 2.5: PASS-2 ZOOM — per-room high-res re-read for accurate dimensions.
    # User decision (2026-04-27): always-on best-path approach. Per kambarį
    # crop the page region at 300 DPI / 2576px max, send to Vision with room
    # context, ask for refined mm dimensions. Phase 6.5.2 showed determinism
    # is poor (CV 22-150%) on projects without eksplikacija; zoom should fix this.
    zoom_count_attempted = 0
    zoom_count_applied = 0
    zoom_total_input_tok = 0
    zoom_total_output_tok = 0
    zoom_count_skipped = 0
    t_zoom_start = time.time()

    # Sprint E2: SMART ZOOM SKIP — when room has eksplikacija-anchored plotas
    # AND a name-matched eksplikacija row, plotas is byte-exact (pdfplumber).
    # Zoom adds value primarily for opening dimensions and edge cases. We can
    # safely skip zoom when:
    #   1. plotas_saltinis == "eksplikacija" (deterministic primitive)
    #   2. eksplikacija_row_idx is set (confirmed name match)
    # This typically saves 50-75% of zoom calls on CAD-export projects with
    # clean eksplikacija — without losing accuracy on the primary primitive.
    def _can_skip_zoom(r: dict) -> bool:
        if (r.get("plotas_saltinis") or "") != "eksplikacija":
            return False
        if r.get("eksplikacija_row_idx") is None:
            return False
        # Confidence guard: only skip if Vision considered this room "high"
        if (r.get("confidence") or "") == "low":
            return False
        # Ceiling height is NOT an eksplikacija primitive — the table carries only
        # plotas/perimetras. If this room's height wasn't individually resolved
        # (saltinis != "per_room"), the zoom pass is the ONLY recovery path; don't
        # skip it, else the room keeps the section-average height and the
        # iki/virš-3m paint split + pastoliai collapse. (Fix: 2026-06-09, the
        # zoom-once regression where 10/11 berzas rooms got a uniform 2.82 m.)
        if (r.get("lubu_aukstis_saltinis") or "section_average") != "per_room":
            return False
        return True

    # EXPERIMENT (SAMATU_ZOOM_AGENTIC=1): route zoom through the model-driven
    # crop loop instead of the fixed-bbox re-read. Same inputs (room dict) and
    # same ZoomResult output schema → _apply_zoom_refinements untouched.
    _zoom_agentic_on = _zoom_agentic_enabled()
    _agentic_render_cache: dict = {}   # (page, dpi) → PIL image, shared across rooms
    _agentic_rooms_meta: list[dict] = []

    _zoomable = [r for r in rooms
                 if r.get("bbox_pct") and r.get("puslapio_nr")
                 and not _can_skip_zoom(r)]
    _emit({"event": "zoom_started", "total": len(_zoomable),
           "skipped_via_eksplikacija": sum(1 for r in rooms if _can_skip_zoom(r)),
           "agentic": _zoom_agentic_on})
    for idx, room in enumerate(rooms, start=1):
        bbox = room.get("bbox_pct")
        page_nr = room.get("puslapio_nr")
        if not bbox or not page_nr:
            continue
        # Smart zoom skip — eksplikacija primitives are deterministic enough
        if _can_skip_zoom(room):
            zoom_count_skipped += 1
            continue
        if _zoom_agentic_on:
            from .agentic_crop import agentic_zoom_room
            zoom_count_attempted += 1
            _emit({
                "event": "zoom_room_started",
                "idx": zoom_count_attempted,
                "total": len(_zoomable),
                "room_nr": room.get("nr"),
                "pavadinimas": room.get("pavadinimas"),
            })
            zoom_result, _zmeta = agentic_zoom_room(
                client, pdf_bytes, room, render_cache=_agentic_render_cache)
            _agentic_rooms_meta.append({"room_nr": room.get("nr"), **_zmeta})
        else:
            cropped = _crop_room_image(pdf_bytes, page_nr, bbox)
            if not cropped:
                continue
            zoom_count_attempted += 1
            _emit({
                "event": "zoom_room_started",
                "idx": zoom_count_attempted,
                "total": len(_zoomable),
                "room_nr": room.get("nr"),
                "pavadinimas": room.get("pavadinimas"),
            })
            zoom_result, _zmeta = _vision_zoom_room(client, cropped, room)
            # Roll this zoom call's tokens into extra_calls (was discarded before
            # 2026-07-04) — even a null/parse-fail result still billed tokens.
            _append_extra_call(parsed, _zmeta)
        if not zoom_result:
            _emit({
                "event": "zoom_room_completed",
                "idx": zoom_count_attempted,
                "total": len(_zoomable),
                "room_nr": room.get("nr"),
                "applied": False,
            })
            continue
        applied = _apply_zoom_refinements(room, zoom_result)
        if applied:
            zoom_count_applied += 1
        _emit({
            "event": "zoom_room_completed",
            "idx": zoom_count_attempted,
            "total": len(_zoomable),
            "room_nr": room.get("nr"),
            "applied": applied,
            "plotas_m2": room.get("plotas_m2"),
        })
    zoom_elapsed = round(time.time() - t_zoom_start, 1)
    _emit({
        "event": "zoom_completed",
        "attempted": zoom_count_attempted,
        "applied": zoom_count_applied,
        "skipped_via_eksplikacija": zoom_count_skipped,
        "elapsed_s": zoom_elapsed,
    })
    parsed.setdefault("_meta", {})["zoom_attempted"] = zoom_count_attempted
    parsed["_meta"]["zoom_skipped_via_eksplikacija"] = zoom_count_skipped
    parsed["_meta"]["zoom_applied"] = zoom_count_applied
    parsed["_meta"]["zoom_elapsed_s"] = zoom_elapsed
    if _zoom_agentic_on:
        # Cost metering (2026-07-04): roll every agentic-zoom room's per-turn
        # tokens into extra_calls so the single per-extraction usage_event prices
        # them (each room's meta already carries its own model + summed tokens).
        for _m in _agentic_rooms_meta:
            _append_extra_call(parsed, _m)
        # Provenance for the agentic-zoom experiment: per-room loop stats
        # (crops, turns, tokens, refusals/aborts) + aggregates.
        parsed["_meta"].setdefault("experiment", {})["agentic_zoom"] = {
            "rooms": _agentic_rooms_meta,
            "crops_served_total": sum(m.get("crops_served", 0)
                                      for m in _agentic_rooms_meta),
            "api_turns_total": sum(m.get("api_turns", 0)
                                   for m in _agentic_rooms_meta),
            "input_tokens_total": sum(m.get("input_tokens", 0)
                                      for m in _agentic_rooms_meta),
            "output_tokens_total": sum(m.get("output_tokens", 0)
                                       for m in _agentic_rooms_meta),
            "aborted_rooms": [m["room_nr"] for m in _agentic_rooms_meta
                              if m.get("outcome") not in ("ok",)],
        }
    print(f"[extractor] zoom pass: {zoom_count_attempted} attempted, "
          f"{zoom_count_applied} applied, {zoom_elapsed}s"
          + (" [agentic]" if _zoom_agentic_on else ""))

    # Step 2.85: APDAILOS READER (2026-05-27).
    # Read IŠKLOTINIŲ IR APDAILŲ PLANAS page (typically the last finish-schedule
    # page) and override the heuristic walls_paint per-room. This replaces
    # hardcoded defaults like `tamburas: walls_paint=0` with what the project
    # actually specifies — per the user directive "imam B iškart" (read from
    # project, forget paskirtis-based heuristics). Berzas fixture simulation
    # showed walls accuracy: -11,6% → -4,3% after this step.
    try:
        from .apdailos_reader import read_apdailos_finishes, merge_apdailos_into_rooms
        _emit({"event": "apdailos_started"})
        apdailos_result = read_apdailos_finishes(pdf_bytes, parsed.get("patalpos") or [])
        _append_extra_call(parsed, apdailos_result.get("_meta"))  # roll tokens into cost
        if apdailos_result.get("status") == "ok":
            n_updated = merge_apdailos_into_rooms(parsed.get("patalpos") or [], apdailos_result)
            parsed.setdefault("_meta", {})["apdailos_page"] = apdailos_result.get("page")
            parsed["_meta"]["apdailos_rooms_updated"] = n_updated
            parsed["_meta"]["apdailos_elapsed_s"] = apdailos_result.get("_elapsed_s")
            _emit({
                "event": "apdailos_completed",
                "page": apdailos_result.get("page"),
                "rooms_updated": n_updated,
            })
        else:
            _emit({
                "event": "apdailos_skipped",
                "reason": apdailos_result.get("_error"),
            })
    except ImportError as exc:
        # A missing reader module is a REGRESSION, not a benign runtime miss —
        # it silently drops per-room wall-finish recovery (walls_paint collapses
        # to the legacy paskirtis heuristic). Make it LOUD. (2026-06-09: both
        # reader modules were lost from git and failed silently for weeks.)
        print(f"[extractor] ⚠️ APDAILOS READER MODULE MISSING — paint recovery DISABLED: {exc}")
        _emit({"event": "apdailos_error", "message": f"module_missing: {exc}", "severity": "regression"})
    except Exception as exc:
        print(f"[extractor] apdailos read failed (non-fatal): {exc}")
        _emit({"event": "apdailos_error", "message": str(exc)})

    # Step 2.86: DOORS READER (2026-05-27).
    # Focused Vision pass on floor_plan to count ALL doors including exterior
    # (front, garage, terrace) and corridor doors that pass-1 systematically
    # misses. Berzas fixture: pass-1 found 9 doors, truth = 14. With doors_reader
    # paint area gap closes from -1.2% to ±0.5% (to the dot).
    try:
        from .doors_reader import read_doors_from_plan, merge_doors_into_rooms
        _emit({"event": "doors_started"})
        doors_result = read_doors_from_plan(
            pdf_bytes,
            parsed.get("patalpos") or [],
            page_classifications=parsed.get("puslapiai") or [],
        )
        _append_extra_call(parsed, doors_result.get("_meta"))  # roll tokens into cost
        if doors_result.get("status") == "ok":
            n_updated = merge_doors_into_rooms(parsed.get("patalpos") or [], doors_result)
            parsed.setdefault("_meta", {})["doors_page"] = doors_result.get("page")
            parsed["_meta"]["doors_total_count"] = doors_result.get("total_count")
            parsed["_meta"]["doors_interior_count"] = doors_result.get("interior_count")
            parsed["_meta"]["doors_exterior_count"] = doors_result.get("exterior_count")
            parsed["_meta"]["doors_rooms_updated"] = n_updated
            parsed["_meta"]["doors_elapsed_s"] = doors_result.get("_elapsed_s")
            _emit({
                "event": "doors_completed",
                "page": doors_result.get("page"),
                "total": doors_result.get("total_count"),
                "interior": doors_result.get("interior_count"),
                "exterior": doors_result.get("exterior_count"),
            })
        else:
            _emit({
                "event": "doors_skipped",
                "reason": doors_result.get("_error"),
            })
    except ImportError as exc:
        print(f"[extractor] ⚠️ DOORS READER MODULE MISSING — door recount DISABLED: {exc}")
        _emit({"event": "doors_error", "message": f"module_missing: {exc}", "severity": "regression"})
    except Exception as exc:
        print(f"[extractor] doors read failed (non-fatal): {exc}")
        _emit({"event": "doors_error", "message": str(exc)})

    # Step 2.865: DOOR-TYPE READER (2026-06-14, council 5/5 + research).
    # Frameless ("beapvadinės") door TYPE is structurally NOT in the door glyph —
    # it's in the drawing TEXT (tags LD-1, annotations "skirta beapvadinėms
    # durims"). The glyph pass under-tags frameless doors (Beržų 2 of ~8 →
    # "Durų angų paruošimas" 10.2 m vs contractor 39.2 m). Read the text, reconcile
    # against the tagged count, RAISE + flag — never silently overwrite.
    try:
        from .door_type_reader import (
            read_door_types, read_door_types_voted, reconcile_frameless)
        _emit({"event": "door_types_started"})
        rooms_now = parsed.get("patalpos") or []
        # Opus 4.8 has no temperature knob — this single-pass recall-critical
        # reader is the #1 variance source. Vote it (median/mode) when voting is on.
        dt = (read_door_types_voted(pdf_bytes, rooms_now,
                                    page_classifications=parsed.get("puslapiai") or [])
              if _voting_on else
              read_door_types(pdf_bytes, rooms_now,
                              page_classifications=parsed.get("puslapiai") or []))
        # Roll door-type reader tokens into cost. Voted: one extra_call per round
        # (_round_metas); single-pass: the one _meta. Each round may run a
        # different model (mixed voting) → priced per-model downstream.
        for _rm in _reader_call_metas(dt):
            _append_extra_call(parsed, _rm)
        if dt.get("status") == "ok":
            n_tagged = sum(int(el.get("kiekis") or 1) for r in rooms_now
                           for el in (r.get("elementai") or [])
                           if (el.get("tipas") or "").lower() == "pasleptos_duris")
            _NONINT = {"garazas", "tamburas", "tambūras"}
            n_interior = sum(int(el.get("kiekis") or 1) for r in rooms_now
                             for el in (r.get("elementai") or [])
                             if (el.get("tipas") or "").lower() in ("duris", "pasleptos_duris")
                             and (r.get("paskirtis") or "").lower() not in _NONINT)
            rec = reconcile_frameless(
                plan_frameless=n_tagged, reader_frameless=dt.get("beapvadines_count", 0),
                bendras_tipas=dt.get("bendras_tipas"), n_interior_doors=n_interior,
                archetipas=parsed.get("archetipas") or (parsed.get("santrauka") or {}).get("archetipas"))
            # If the voted reads disagreed (spread>0), surface it as geltona —
            # the honest output is "reads varied, verify", not a silent pick.
            _vote = dt.get("_vote") or {}
            if _vote.get("spread", 0) > 0:
                if rec.get("confidence") == "zalia":
                    rec["confidence"] = "geltona"
                rec["reason"] = (rec.get("reason") or "") + \
                    f" (skaitymai svyravo tarp paleidimų: {_vote.get('beapvadines_values')})"
            parsed["_door_types"] = {**rec, "reader_beapvadines": dt.get("beapvadines_count"),
                                     "plan_tagged": n_tagged, "pages": dt.get("pages"),
                                     "_vote": _vote}
            parsed.setdefault("_meta", {})["door_types_elapsed_s"] = dt.get("_elapsed_s")
            _emit({"event": "door_types_completed", "frameless": rec.get("count"),
                   "confidence": rec.get("confidence"), "reader": dt.get("beapvadines_count"),
                   "tagged": n_tagged})
        else:
            _emit({"event": "door_types_skipped", "reason": dt.get("_error")})
    except Exception as exc:  # noqa: BLE001
        print(f"[extractor] door-type read failed (non-fatal): {exc}")
        _emit({"event": "door_types_error", "message": str(exc)})

    # Step 2.866: SANITARY FIXTURE READER (2026-06-14, research #3 point-list).
    # The full-sheet pass under-counts dense sanitary symbols (Beržų praustuvės
    # 3, truth 5). A focused point-list-then-count read raises recall (3→4 live);
    # reconcile RAISES detected_symbols_summary to the higher count (the skylių
    # formula consumes it), never silently lowers. Modest, honest — fixtures have
    # no clean schedule to read (research-confirmed).
    try:
        from .sanitary_fixture_reader import (
            read_fixtures, read_fixtures_voted, reconcile_fixture_counts)
        _emit({"event": "fixtures_started"})
        fx = (read_fixtures_voted(pdf_bytes, parsed.get("patalpos") or [])
              if _voting_on else
              read_fixtures(pdf_bytes, parsed.get("patalpos") or []))
        # Roll fixture-reader tokens into cost (voted: per-round; single: one).
        for _rm in _reader_call_metas(fx):
            _append_extra_call(parsed, _rm)
        if fx.get("status") == "ok":
            rec = reconcile_fixture_counts(parsed.get("detected_symbols_summary") or {},
                                           fx.get("counts") or {})
            parsed["detected_symbols_summary"] = rec["merged"]
            parsed.setdefault("_meta", {})["fixtures_raised"] = rec["raised"]
            parsed["_meta"]["fixtures_elapsed_s"] = fx.get("_elapsed_s")
            _emit({"event": "fixtures_completed", "raised": rec["raised"],
                   "counts": fx.get("counts")})
        else:
            _emit({"event": "fixtures_skipped", "reason": fx.get("_error")})
    except Exception as exc:  # noqa: BLE001
        print(f"[extractor] fixture read failed (non-fatal): {exc}")
        _emit({"event": "fixtures_error", "message": str(exc)})

    # Step 2.87: NICHE LOCATOR (wired into prod 2026-06-05, multi-page
    # backfill added 2026-06-05 evening).
    # Targeted Vision pass on the ceiling_plan page + conditional
    # backfill from secondary pages (lubu mazgai sections, apsvietimo
    # planas) when the primary's LED-room coverage is sparse.
    #
    # Verified Beržų: -5.44% → -0.99% (primary alone). Secondary pages
    # would over-extract (light-wiring rectangles mis-read as LED), so
    # the COVERAGE_GATE skips them when primary already covers many
    # rooms. Bacveviciaus: -54.75% → -51.60% (primary 4 rooms < gate,
    # backfill kicks in, helps marginally — locator-limited beyond that).
    try:
        from .vision.niche_locator import (
            extract_niches, fold_niches_into_rooms, NicheList,
        )

        def _is_niche_candidate(p: dict) -> bool:
            tipas = (p.get("tipas") or "").lower()
            if tipas == "ceiling_plan":
                return True
            title = (p.get("pavadinimas") or "").lower()
            return ("lub" in title) or ("apšviet" in title) or ("apsviet" in title)

        def _render_one_page(page_nr: int) -> str | None:
            imgs = convert_from_bytes(
                pdf_bytes, dpi=200, fmt="jpeg",
                first_page=page_nr, last_page=page_nr,
            )
            if not imgs:
                return None
            buf = io.BytesIO()
            imgs[0].save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("ascii")

        page_classifications = parsed.get("puslapiai") or []
        candidates = [p for p in page_classifications if _is_niche_candidate(p)]
        # Primary = first ceiling_plan, else first candidate
        candidates.sort(key=lambda p: (
            0 if (p.get("tipas") or "").lower() == "ceiling_plan" else 1,
            int(p.get("nr", 999)),
        ))
        page_nrs = [int(p.get("nr")) for p in candidates]
        if not page_nrs:
            _emit({"event": "niche_locator_skipped",
                   "reason": "no candidate page (no ceiling_plan / lub / apšviet)"})
        else:
            _emit({"event": "niche_locator_started", "pages": page_nrs})
            combined = NicheList()
            covered: set[str] = set()
            COVERAGE_GATE = 5  # rooms with non-zero LED before backfill skips
            # Primary pass
            primary_pg = page_nrs[0]
            image_b64 = _render_one_page(primary_pg)
            if image_b64:
                nl_p = extract_niches(image_b64=image_b64)
                for n in nl_p.niches:
                    if n.type in ("ceiling_led", "wall_led") and (n.length_mm or 0) > 0:
                        covered.add(str(n.room_nr))
                    combined.niches.append(n)
                # Backfill secondaries only when primary coverage is sparse
                if len(covered) < COVERAGE_GATE:
                    for page_nr in page_nrs[1:]:
                        img = _render_one_page(page_nr)
                        if not img:
                            continue
                        nl_s = extract_niches(image_b64=img)
                        for n in nl_s.niches:
                            is_led = n.type in ("ceiling_led", "wall_led")
                            if (not is_led) or (str(n.room_nr) not in covered):
                                combined.niches.append(n)
                fold_niches_into_rooms(parsed.get("patalpos") or [], combined)
                parsed.setdefault("_meta", {})["niche_locator_pages"] = page_nrs
                parsed["_meta"]["niche_locator_primary_covered"] = len(covered)
                parsed["_meta"]["niche_locator_count"] = len(combined.niches)
                _emit({
                    "event": "niche_locator_completed",
                    "primary_page": primary_pg,
                    "primary_rooms_covered": len(covered),
                    "total_niches_kept": len(combined.niches),
                    "backfill_ran": len(covered) < COVERAGE_GATE,
                })
            else:
                _emit({"event": "niche_locator_skipped",
                       "reason": f"failed to render primary page {primary_pg}"})
    except Exception as exc:
        print(f"[extractor] niche_locator failed (non-fatal): {exc}")
        _emit({"event": "niche_locator_error", "message": str(exc)})

    # Step 2.88: STATISTICAL NICHE INFERENCE (2026-06-05).
    # For rooms where the niche_locator returned nothing but the room
    # paskirtis empirically has LED (corridor 0.55, wet rooms 0.27,
    # etc.), inject a fallback estimate based on perim × ratio.
    # See backend/extractor/niche_inference.py for the per-paskirtis
    # table and the validated impact on bacveviciaus (-52% → -18%).
    try:
        from .niche_inference import infer_missing_niches
        n_inferred = infer_missing_niches(parsed.get("patalpos") or [])
        if n_inferred:
            parsed.setdefault("_meta", {})["niche_inference_rooms"] = n_inferred
            _emit({"event": "niche_inference_completed",
                   "rooms_inferred": n_inferred})
    except Exception as exc:
        print(f"[extractor] niche inference failed (non-fatal): {exc}")
        _emit({"event": "niche_inference_error", "message": str(exc)})

    _emit({"event": "post_processing"})

    # Step 2.9: PYTHON DETERMINISTIC MATH (2026-04-28 deterministic refactor).
    # Replace Vision-emitted per-room totals with Python-computed values from
    # primitives. Same primitives → same output, every run.
    try:
        parsed = _recompute_per_room_via_python(parsed, rules_override)
        _emit({
            "event": "python_math_completed",
            "rooms_computed": len(parsed.get("patalpos") or []),
        })
    except Exception as exc:
        print(f"[extractor] per-room Python recompute failed: {exc}")
        existing_warnings = parsed.get("warnings") or []
        existing_warnings.append({
            "level": "WARN",
            "message": f"Python skaičiavimo klaida: {exc}",
        })
        parsed["warnings"] = existing_warnings

    # Step 2.95: BUILD POZICIJOS from Python-computed per-room aggregates.
    # Vision no longer emits pozicijos[] (deterministic refactor). Python
    # synthesizes the kiekių žiniaraštis from per-room totals.
    # Pre-set _overrides so _build_pozicijos_from_rooms can read NRM2/VOB/LT
    # deduction standard (Sprint §2A.1). Re-set definitively at Step 6 below.
    if rules_override is not None:
        parsed["_overrides"] = rules_override
    try:
        parsed = _build_pozicijos_from_rooms(parsed)
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(f"[extractor] pozicijos build failed: {exc}\n{tb}", flush=True)
        # CRITICAL: do NOT fall back to Vision's pre-Sprint-0 pozicijos.
        # Those contain stale labels (e.g. "GKP lapai (12.5 mm)") that
        # Sprint 0 Fix 1 deliberately replaced with the wall/ceiling split.
        # Better to ship empty pozicijos + visible warning than silently regress.
        parsed["pozicijos"] = []
        existing_warnings = parsed.get("warnings") or []
        existing_warnings.append({
            "level": "ERROR",
            "source": "pozicijos_build_failure",
            "message": f"Pozicijos rekonstrukcija nepavyko: {exc}. Reikia rankomis sukurti.",
        })
        parsed["warnings"] = existing_warnings

    # Step 3: Recompute santrauka from per-room values (single source of truth)
    # NOTE: this runs AFTER Python per-room compute so totals reflect deterministic dims.
    try:
        parsed = _recompute_santrauka(parsed)
    except Exception as exc:
        # Non-fatal: keep current santrauka, add warning
        print(f"[extractor] santrauka recompute failed: {exc}")
        existing_warnings = parsed.get("warnings") or []
        existing_warnings.append({
            "level": "WARN",
            "message": f"Santrauka recompute klaida: {exc}",
        })
        parsed["warnings"] = existing_warnings

    # Step 4: Apply LT sanity checks (adds _lt_warnings, does NOT mutate values)
    try:
        from .lt_rules import apply_lt_sanity
        parsed = apply_lt_sanity(parsed)
    except Exception as exc:
        print(f"[extractor] lt_sanity failed: {exc}")

    # Step 4.05: Cross-page consistency validator — pure-python rule engine
    # cross-checks plotai/elementai/schedules/eksplikacija. Adds entries to
    # parsed["warnings"] so they propagate into the lt_sanity UI banner below.
    try:
        from .cross_page_validator import validate_consistency
        cross_warnings = validate_consistency(parsed)
        if cross_warnings:
            existing = parsed.get("warnings") or []
            for w in cross_warnings:
                existing.append({
                    "level": w["level"].upper(),
                    "field": w.get("field", ""),
                    "message": w.get("message_lt", ""),
                    "suggestion": w.get("suggestion", ""),
                    "discrepancy_pct": w.get("discrepancy_pct"),
                    "source": "cross_page_validator",
                })
            parsed["warnings"] = existing
            print(f"[extractor] cross_page_validator emitted {len(cross_warnings)} warnings")
    except Exception as exc:
        print(f"[extractor] cross_page_validator failed: {exc}")

    # Step 4.06: Scale verification (Sprint 0 Fix 3) — warn when declared scale
    # doesn't match actual rendered pixel dimensions.
    # Adaptation note: Vision populates scale_source_page (int) but NOT a
    # scale_source_text string. We scan puslapiai[].pavadinimas for "M 1:X"
    # annotations as a best-effort text source. If nothing is found the check
    # is silently skipped (no rooms have diagonal_px populated yet either, so
    # validate_scale() is a no-op until the Vision prompt is extended in a
    # future task to return pixel bounding-box dimensions).
    try:
        from .scale_validator import parse_scale_string, validate_scale
        # Collect candidate scale text from page title blocks
        scale_factor: float | None = None
        for page in (parsed.get("puslapiai") or []):
            sf = parse_scale_string(page.get("pavadinimas") or "")
            if sf is not None:
                scale_factor = sf
                break  # use first page that declares a scale
        if scale_factor:
            scale_warnings = validate_scale(
                scale_factor=scale_factor,
                rendered_dpi=DPI,  # match render DPI used in pdf_to_b64_images
                rooms=parsed.get("patalpos") or [],
            )
            if scale_warnings:
                existing_warnings = parsed.get("warnings") or []
                for msg in scale_warnings:
                    existing_warnings.append({
                        "level": "WARN",
                        "message": msg,
                        "source": "scale_validator",
                    })
                parsed["warnings"] = existing_warnings
                print(f"[extractor] scale_validator emitted {len(scale_warnings)} warnings "
                      f"(scale 1:{int(scale_factor)})")
    except Exception as exc:
        print(f"[extractor] scale_validator failed (non-fatal): {exc}")

    # Step 4.065: Sprint 4 Block C — Section 6 sanity checks.
    # Pure LT-industry math validators (CLAUDE.md §6). Each check is a
    # post-extraction suspicion, NOT a value mutation. Output is structured
    # Warning dicts merged with existing scale/cross-page warnings (string +
    # dict shapes coexist; frontend handles both).
    try:
        from .sanity_checks import run_all_checks
        sanity_warnings = run_all_checks(parsed)
        if sanity_warnings:
            existing = parsed.get("warnings") or []
            parsed["warnings"] = existing + sanity_warnings
            print(f"[extractor] sanity_checks emitted {len(sanity_warnings)} warnings")
    except Exception as exc:
        print(f"[extractor] sanity_checks failed (non-fatal): {exc}")

    # Step 4.067 (2026-06-01): permanent consistency checker.
    # Pure-Python audit (room count vs eksplikacija, wall/floor ratio,
    # height plausibility + uniformity, perim-geometry). Emits a report
    # under parsed["_consistency_checks"] + warnings on failed checks.
    try:
        from .consistency_checker import run_all_checks as _ck_run
        ck_report = _ck_run(parsed)
        parsed["_consistency_checks"] = ck_report
        if ck_report["n_warn"] > 0 or ck_report["n_fail"] > 0:
            existing = parsed.get("warnings") or []
            for c in ck_report["checks"]:
                if c["status"] in ("WARN", "FAIL"):
                    existing.append({
                        "level": c["status"], "source": "consistency_checker",
                        "message": f"{c['name']}: {c['message']}",
                    })
            parsed["warnings"] = existing
            print(f"[extractor] consistency_checker: "
                  f"{ck_report['n_warn']} warn + {ck_report['n_fail']} fail")
    except Exception as exc:
        print(f"[extractor] consistency_checker failed (non-fatal): {exc}")

    # Step 4.066 (2026-06-01): permanent geometric perimeter validation.
    # Pure-Python check that each room's perimetras_m is consistent with
    # its plotas_m2 via the isoperimetric bound. Emits structured warnings
    # for any room with impossible perimeter; downstream code MAY trigger
    # re-extraction. Today: just surface the report on parsed for audit;
    # no automated re-extraction (would require the rich dimension_extractor
    # to be wired into production — separate work item).
    try:
        from .vision.perimeter_validator import validate_extract
        perim_report = validate_extract(parsed)
        parsed["_perimeter_validation"] = perim_report
        if perim_report["n_needs_reextraction"] > 0:
            existing = parsed.get("warnings") or []
            for fr in perim_report["flagged_rooms"]:
                existing.append({
                    "level": "WARN",
                    "message": (f"Room {fr['room_nr']} ({fr['room_name']}): "
                                f"perimeter {fr['perim_m']:.1f}m outside geometric "
                                f"bounds [{fr['lower_bound_m']:.1f}, {fr['upper_bound_m']:.1f}]"
                                f" for area {fr['area_m2']:.1f}m²"),
                    "source": "perimeter_validator",
                })
            parsed["warnings"] = existing
            print(f"[extractor] perimeter_validator flagged "
                  f"{perim_report['n_needs_reextraction']}/{perim_report['n_total']} rooms")
        else:
            print(f"[extractor] perimeter_validator: all "
                  f"{perim_report['n_total']} rooms within bounds")
    except Exception as exc:
        print(f"[extractor] perimeter_validator failed (non-fatal): {exc}")

    # Step 4.07: P4 — Plytelių specifikacijos pdfplumber reader. Deterministic,
    # $0 cost. Reads tile size mentions (e.g., 1200×1200×6) on
    # finish_schedule / wall_elevation pages and attaches as parsed['_plyteliu_specs'].
    # Per `parsed.puslapiai[].tipas` classification — limit scan to relevant
    # pages so we don't false-match door dims on plan pages.
    try:
        from .plyteliu_specifikacija import (
            extract_plyteliu_specifikacija, RELEVANT_PAGE_TYPES,
        )
        relevant = [
            p["nr"] for p in (parsed.get("puslapiai") or [])
            if p.get("tipas") in RELEVANT_PAGE_TYPES
        ]
        plyt = extract_plyteliu_specifikacija(pdf_bytes, relevant_pages=relevant or None)
        parsed["_plyteliu_specs"] = plyt.get("tile_specs", [])
        if plyt.get("tile_specs"):
            print(f"[extractor] plyteliu_specifikacija found {len(plyt['tile_specs'])} "
                  f"size-specific tile mentions on {len(relevant)} relevant pages, "
                  f"{plyt['_meta'].get('elapsed_s', 0)}s, $0 cost")
    except Exception as exc:
        print(f"[extractor] plyteliu_specifikacija failed (non-fatal): {exc}")

    # Step 4.08: Wall elevation specialized Vision extractor. Opt-in via
    # WALL_ELEVATION_EXTRACT=1 env var because each page costs ~$0.10-0.20.
    # Output attached as parsed['_wall_elevations']; pozicijos generator and
    # frontend can use exact tile_zones/paint_zones/niches mm boundaries
    # instead of paskirtis-based approximations.
    if os.environ.get("WALL_ELEVATION_EXTRACT") == "1":
        try:
            from .wall_elevation import extract_wall_elevations
            we_pages = [
                p["nr"] for p in (parsed.get("puslapiai") or [])
                if p.get("tipas") == "wall_elevation"
            ]
            if we_pages:
                _emit({"event": "wall_elevation_started", "pages": len(we_pages)})
                we_result = extract_wall_elevations(pdf_bytes, client, we_pages)
                parsed["_wall_elevations"] = we_result.get("wall_elevations", [])
                parsed.setdefault("_meta", {})["wall_elevation_meta"] = we_result.get("_meta", {})
                _emit({
                    "event": "wall_elevation_completed",
                    "elevations": len(we_result.get("wall_elevations", [])),
                    "pages_processed": we_result.get("_meta", {}).get("pages_processed", 0),
                })
                print(f"[extractor] wall_elevation: {len(we_result.get('wall_elevations', []))} "
                      f"elevations from {we_result.get('_meta', {}).get('pages_processed', 0)} pages, "
                      f"{we_result.get('_meta', {}).get('elapsed_s', 0)}s")

                # Sprint §35 (2026-04-29): override paskirtis-based plyteles_sienos_m2
                # with mm-precision sum from wall_elevations data. Per CLAUDE.md §1.7,
                # tile zone area = (to_floor_mm − from_floor_mm) × wall_total_width_mm.
                _apply_wall_elevation_tile_override(parsed)
        except Exception as exc:
            print(f"[extractor] wall_elevation failed (non-fatal): {exc}")

    # Step 4.1: Emit `lt_sanity: {warnings, summary}` mirror for frontend
    # SanityWarningsBanner.jsx expects this V8 shape; new extractor uses flat
    # `_lt_warnings`. Normalize level WARN → WARNING to match UI's level enum.
    # Also merges `warnings[]` (Vision-emitted + auto eksplikacija-missing INFO)
    # so the user sees BOTH STR sanity AND pipeline-level notes in one banner.
    try:
        flat_warnings = parsed.get("_lt_warnings") or []
        pipeline_warnings = parsed.get("warnings") or []
        ui_warnings = []
        for w in flat_warnings + pipeline_warnings:
            level = w.get("level", "INFO")
            if level == "WARN":
                level = "WARNING"
            ui_warnings.append({
                "level": level,
                "room": w.get("patalpa_nr") or w.get("room") or "",
                "field": w.get("field", ""),
                "value": w.get("value"),
                "expected": w.get("expected"),
                "message": w.get("message", ""),
            })
        rooms_total = parsed.get("patalpos") or []
        n_err = sum(1 for w in ui_warnings if w["level"] == "ERROR")
        n_warn = sum(1 for w in ui_warnings if w["level"] == "WARNING")
        n_info = sum(1 for w in ui_warnings if w["level"] == "INFO")
        parsed["lt_sanity"] = {
            "warnings": ui_warnings,
            "summary": {
                "rooms_count": len(rooms_total),
                "total_area_m2": round(parsed.get("bendras_plotas_m2", 0), 1),
                "warnings_count": n_err + n_warn,
                "errors": n_err,
                "warnings": n_warn,
                "info": n_info,
            },
        }
    except Exception as exc:
        print(f"[extractor] lt_sanity mirror emit failed: {exc}")

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

    # Phase C-2 (2026-05-02): if a patalpa has plotas_m2 but no plotas_source,
    # tag it as 'vision' (came from Anthropic Vision response, not eksplikacija).
    # Eksplikacija reader sets 'eksplikacija' explicitly; manual polygons set
    # 'manual_polygon' on the frontend. Anything left over is Vision.
    #
    # 2026-05-06: Mirror plotas_saltinis (LT field name written by deterministic
    # pipeline) to plotas_source (EN field name read by frontend ConfidenceBadge).
    # Without this, eksplikacija-sourced rooms show 🔴 neaišku because the
    # frontend never sees the source flag — bug visible in user's screenshot.
    _SALTINIS_TO_SOURCE = {
        "eksplikacija": "eksplikacija",
        "wall_dim_calc": "vision",  # zoom-derived dimension calc
        "vision": "vision",
        "polygon_adjacency": "vision",  # synthesized from prepass
    }
    try:
        patalpos = parsed.get("patalpos") or []
        for p in patalpos:
            if p.get("plotas_m2") is None:
                continue
            if p.get("plotas_source"):
                continue
            saltinis = (p.get("plotas_saltinis") or "").strip()
            p["plotas_source"] = _SALTINIS_TO_SOURCE.get(saltinis, "vision")
    except Exception as exc:
        print(f"[extractor] plotas_source fallback failed: {exc}")

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

    # Step 6.5: Optional verify pass (gated by ENABLE_VERIFY_PASS).
    # Runs Opus on the Pass-1 result, asks "what would you disagree with?".
    # Result is ADVISORY — never auto-applied; surfaced to UI as suggestions.
    # When the flag is OFF (default), this returns empty corrections fast.
    try:
        from .verify_pass import run_verify_pass
        verify = run_verify_pass(
            rooms=parsed.get("patalpos") or [],
            pozicijos=parsed.get("pozicijos") or [],
        )
        parsed["_verify_pass"] = {
            "corrections": verify.corrections,
            "error": verify.error,
        }
    except Exception as exc:
        # Never break extraction over an advisory pass.
        parsed["_verify_pass"] = {"corrections": [], "error": str(exc)}

    # Step 7: Finalize
    elapsed = round(time.time() - t0, 1)
    if "_meta" in parsed:
        parsed["_meta"]["elapsed_s"] = elapsed
    else:
        parsed["_meta"] = {"elapsed_s": elapsed}

    parsed["_elapsed_s"] = elapsed
    parsed["status"] = "ok"

    return parsed


def vision_polygon_at_click(project_id: str, page_idx: int,
                            click_xy_pct: list[float]) -> dict:
    """Sprint 2 G1 hook. Returns a stub polygon centered at click + low
    confidence; Sprint 4 wires the real Pass-2 zoom Vision call.

    The stub MUST return a valid 4-vertex CW polygon so frontend integration
    can proceed. Mocked in tests via patch().
    """
    cx, cy = click_xy_pct
    # 20% page-width square as a placeholder room outline
    half = 0.10
    return {
        "polygon_pct": [
            [max(0.0, cx - half), max(0.0, cy - half)],
            [max(0.0, cx - half), min(1.0, cy + half)],
            [min(1.0, cx + half), min(1.0, cy + half)],
            [min(1.0, cx + half), max(0.0, cy - half)],
        ],
        "room_name_guess": None,
        "confidence": "low",
    }

"""EXPERIMENTAL agentic crop loop for the Pass-2 zoom re-read.

Gate: env ``SAMATU_ZOOM_AGENTIC=1`` (checked in vision_call, default OFF).

Today the zoom pass crops the FIXED room bbox once and asks for refined
dimensions. This module inverts control: the model gets a client-side
``request_crop`` tool and drives its own zooming — it can chase a dimension
chain off the bbox edge, re-render a blurry mm string at 600 DPI, or peek at
a neighbouring wall. Evidence: CropVLM (arXiv 2511.19820) shows the largest
gains exactly when resolution is the bottleneck; A1 sheets at the 2576 px
cap ARE resolution-limited for small dimension strings
(docs/superpowers/research/2026-07-04-accuracy-deep-dive.md, experiment #6).

Contract with the caller (vision_call zoom loop):
  * input  — same room dict the fixed-crop path uses (bbox_pct, puslapio_nr,
             plotas/perimetras/lubu_aukstis primitives),
  * output — the SAME ZoomResult JSON schema ZOOM_SYSTEM_TEXT defines, so
             ``_apply_zoom_refinements`` and everything downstream is
             untouched.

Loop rules (hard requirements):
  * parallel tool_use blocks → ALL answered in ONE user message,
  * ``pause_turn`` → append assistant content, re-call,
  * ``refusal`` → abort the room gracefully (caller records it in _meta),
  * max 8 crops per room (hard stop) → then the model must answer,
  * belt-and-suspenders turn cap so a misbehaving loop can never spin.
"""
from __future__ import annotations

import base64
import io
from typing import Any

from models_config import model_for

# Hard limits.
MAX_CROPS_PER_ROOM = 8
MAX_API_TURNS = 12            # absolute loop ceiling (tool turns + final answer)
MAX_CROP_DPI = 600
DEFAULT_CROP_DPI = 300
CROP_MAX_DIM = 2576           # model max long edge
MIN_CROP_PX = 20              # reject degenerate slivers
AGENTIC_TIMEOUT_S = 600.0     # same per-call ceiling as the rest of the vision path

REQUEST_CROP_TOOL: dict[str, Any] = {
    "name": "request_crop",
    "description": (
        "Išsikirpk brėžinio fragmentą didesne raiška. Nurodyk PDF puslapį "
        "(1-based, ORIGINALI numeracija) ir iškarpos kraštines kaip puslapio "
        "dalis 0.0–1.0 (x0<x1, y0<y1; (0,0) = viršutinis kairys kampas). "
        "dpi pasirenkamas (numatytasis 300, maksimumas 600) — kelk dpi, kai "
        "mm užrašai per smulkūs perskaityti. Grąžinamas iškarpos vaizdas. "
        "Iš viso turi ne daugiau 8 iškarpų šiai patalpai — naudok jas taupiai."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer",
                     "description": "PDF puslapio numeris (1-based, originali numeracija)"},
            "x0": {"type": "number", "description": "kairė riba, 0.0–1.0 puslapio pločio"},
            "y0": {"type": "number", "description": "viršutinė riba, 0.0–1.0 puslapio aukščio"},
            "x1": {"type": "number", "description": "dešinė riba, 0.0–1.0 (privalo būti > x0)"},
            "y1": {"type": "number", "description": "apatinė riba, 0.0–1.0 (privalo būti > y0)"},
            "dpi": {"type": "integer",
                    "description": "renderinimo DPI (numatytasis 300, maksimumas 600)"},
        },
        "required": ["page", "x0", "y0", "x1", "y1"],
    },
}

AGENTIC_SYSTEM_SUFFIX = """<agentinis_zoom>
Tau duotas `request_crop` įrankis — gali pats išsikirpti bet kurią brėžinio
vietą didesne raiška (iki 600 DPI). Naudok jį, kai:
- matmenų grandinė tęsiasi už pradinės iškarpos ribų,
- mm užrašas per smulkus ar susiliejęs — išsikirpk jį stambiau ir/ar didesniu DPI,
- reikia pamatyti gretimą sieną / aukščio žymą / lentelės eilutę.

Limitas: ne daugiau 8 iškarpų šiai patalpai. Kai turi pakankamai duomenų
(arba pasiekei limitą), grąžink GALUTINĮ atsakymą — VIENĄ ZoomResult JSON
pagal <output_schema>. Jokių markdown fences, jokios prozos aplink JSON.
</agentinis_zoom>"""

_FINAL_ANSWER_NUDGE = (
    "Iškarpų limitas pasiektas. Daugiau `request_crop` kvietimų nebus atsakyta — "
    "grąžink GALUTINĮ ZoomResult JSON dabar, pagal <output_schema>."
)


# ── rendering ──────────────────────────────────────────────────────────────────
def _render_page(pdf_bytes: bytes, page: int, dpi: int, cache: dict):
    """Full-page render at (page, dpi), memoized in ``cache``. Returns a PIL
    Image or None."""
    key = (int(page), int(dpi))
    if key not in cache:
        from pdf2image import convert_from_bytes
        try:
            pages = convert_from_bytes(
                pdf_bytes, dpi=dpi, fmt="jpeg",
                first_page=page, last_page=page,
            )
            cache[key] = pages[0] if pages else None
        except Exception as exc:
            print(f"[agentic_crop] page render failed (page={page}, dpi={dpi}): {exc}")
            cache[key] = None
    return cache[key]


def _validate_crop_args(args: dict) -> str | None:
    """Return an error string for invalid request_crop input, else None."""
    try:
        page = int(args.get("page"))
    except (TypeError, ValueError):
        return "invalid page: must be a 1-based integer"
    if page < 1:
        return "invalid page: must be >= 1"
    try:
        x0, y0 = float(args.get("x0")), float(args.get("y0"))
        x1, y1 = float(args.get("x1")), float(args.get("y1"))
    except (TypeError, ValueError):
        return "invalid coordinates: x0/y0/x1/y1 must be numbers in 0.0-1.0"
    for v in (x0, y0, x1, y1):
        if not (0.0 <= v <= 1.0):
            return "invalid coordinates: values must be within 0.0-1.0"
    if x1 <= x0 or y1 <= y0:
        return "invalid coordinates: require x1 > x0 and y1 > y0"
    return None


def _render_crop(pdf_bytes: bytes, args: dict,
                 cache: dict) -> tuple[str | None, str | None]:
    """Render one requested crop. Returns (jpeg_b64, None) or (None, error)."""
    err = _validate_crop_args(args)
    if err:
        return None, err
    page = int(args["page"])
    dpi = int(args.get("dpi") or DEFAULT_CROP_DPI)
    dpi = max(72, min(MAX_CROP_DPI, dpi))
    img = _render_page(pdf_bytes, page, dpi, cache)
    if img is None:
        return None, f"page {page} could not be rendered from the PDF"
    W, H = img.size
    px0, py0 = int(W * float(args["x0"])), int(H * float(args["y0"]))
    px1, py1 = int(W * float(args["x1"])), int(H * float(args["y1"]))
    if px1 - px0 < MIN_CROP_PX or py1 - py0 < MIN_CROP_PX:
        return None, "crop region too small — widen the box"
    crop = img.crop((px0, py0, px1, py1))
    cw, ch = crop.size
    scale = min(1.0, CROP_MAX_DIM / max(cw, ch))
    if scale < 1.0:
        crop = crop.resize((int(cw * scale), int(ch * scale)))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii"), None


# ── the loop ───────────────────────────────────────────────────────────────────
def _build_initial_user_content(seed_b64: str | None, room: dict) -> list[dict]:
    """Seed the loop with the same fixed-bbox crop + room context the
    non-agentic path sends, plus the bbox so the model can aim its crops."""
    import json as _json
    room_context = {
        "nr": room.get("nr"),
        "pavadinimas": room.get("pavadinimas"),
        "paskirtis": room.get("paskirtis"),
        "plotas_m2_pradinis": room.get("plotas_m2"),
        "perimetras_m_pradinis": room.get("perimetras_m"),
        "lubu_aukstis_m_pradinis": room.get("lubu_aukstis_m"),
        "puslapio_nr": room.get("puslapio_nr"),
        "bbox_pct": room.get("bbox_pct"),
    }
    content: list[dict] = []
    if seed_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": seed_b64},
        })
    content.append({
        "type": "text",
        "text": (
            "Patalpa kontekstas (iš overview pass'o):\n"
            f"```json\n{_json.dumps(room_context, ensure_ascii=False, indent=2)}\n```\n\n"
            + ("Aukščiau — pradinė šios patalpos iškarpa (bbox_pct sritis + 5% "
               "paraštė). " if seed_b64 else "Pradinės iškarpos nėra. ")
            + "Naudok `request_crop`, jei reikia pamatyti smulkiau ar plačiau, "
              "tada grąžink VIENĄ ZoomResult JSON pagal output_schema."
        ),
    })
    return content


def agentic_zoom_room(
    client,
    pdf_bytes: bytes,
    room: dict,
    *,
    model: str | None = None,
    render_cache: dict | None = None,
    max_crops: int = MAX_CROPS_PER_ROOM,
) -> tuple[dict | None, dict]:
    """Model-driven zoom re-read for one room.

    Returns (zoom_result_or_None, meta). zoom_result matches the ZoomResult
    schema of the fixed-crop path (drop-in for _apply_zoom_refinements);
    meta carries crops_served / api_turns / tokens / outcome for _meta.
    """
    # Local imports avoid a circular import (vision_call imports this module
    # lazily inside the zoom loop, we borrow its helpers here).
    from .vision_call import _crop_room_image, _repair_json
    from .prompt import ZOOM_SYSTEM_TEXT
    import json as _json

    model = model or model_for("vision_pass2")
    render_cache = render_cache if render_cache is not None else {}
    meta: dict[str, Any] = {
        "mode": "agentic",
        "model": model,
        "crops_served": 0,
        "api_turns": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "outcome": None,
    }

    seed_b64 = None
    bbox = room.get("bbox_pct")
    page_nr = room.get("puslapio_nr")
    if bbox and page_nr:
        seed_b64 = _crop_room_image(pdf_bytes, int(page_nr), bbox)
    if not seed_b64:
        # Same behaviour as the fixed path when the crop fails: skip the room.
        meta["outcome"] = "seed_crop_failed"
        return None, meta

    system = [
        {"type": "text", "text": ZOOM_SYSTEM_TEXT},
        {"type": "text", "text": AGENTIC_SYSTEM_SUFFIX,
         "cache_control": {"type": "ephemeral"}},
    ]
    messages: list[dict] = [
        {"role": "user", "content": _build_initial_user_content(seed_b64, room)}
    ]

    limit_notified = False
    try:
        while meta["api_turns"] < MAX_API_TURNS:
            resp = client.with_options(timeout=AGENTIC_TIMEOUT_S).messages.create(
                model=model,
                max_tokens=4096,
                system=system,
                tools=[REQUEST_CROP_TOOL],
                messages=messages,
                # Same effort rationale as the fixed-crop zoom: this is a
                # perception RE-READ, not open-ended reasoning.
                output_config={"effort": "medium"},
            )
            meta["api_turns"] += 1
            usage = getattr(resp, "usage", None)
            if usage is not None:
                meta["input_tokens"] += int(getattr(usage, "input_tokens", 0) or 0)
                meta["output_tokens"] += int(getattr(usage, "output_tokens", 0) or 0)
                meta["cache_read_tokens"] += int(
                    getattr(usage, "cache_read_input_tokens", 0) or 0)
                meta["cache_write_tokens"] += int(
                    getattr(usage, "cache_creation_input_tokens", 0) or 0)

            stop = resp.stop_reason
            if stop == "refusal":
                # Abort this room gracefully — caller records it in _meta.
                meta["outcome"] = "refusal"
                return None, meta
            if stop == "max_tokens":
                meta["outcome"] = "max_tokens"
                return None, meta
            if stop == "pause_turn":
                # Server paused a long turn — resume by echoing the content.
                messages.append({"role": "assistant", "content": resp.content})
                continue

            if stop == "tool_use":
                tool_uses = [b for b in resp.content
                             if getattr(b, "type", None) == "tool_use"]
                messages.append({"role": "assistant", "content": resp.content})
                # Parallel tool_use blocks: answer ALL in ONE user message.
                results: list[dict] = []
                for tu in tool_uses:
                    if meta["crops_served"] >= max_crops:
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": _FINAL_ANSWER_NUDGE,
                            "is_error": True,
                        })
                        continue
                    tool_input = tu.input if isinstance(tu.input, dict) else {}
                    crop_b64, err = _render_crop(pdf_bytes, tool_input, render_cache)
                    if err:
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": f"Error: {err}",
                            "is_error": True,
                        })
                        continue
                    meta["crops_served"] += 1
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": [{
                            "type": "image",
                            "source": {"type": "base64",
                                       "media_type": "image/jpeg",
                                       "data": crop_b64},
                        }],
                    })
                user_content: list[dict] = results
                if meta["crops_served"] >= max_crops and not limit_notified:
                    user_content = results + [
                        {"type": "text", "text": _FINAL_ANSWER_NUDGE}]
                    limit_notified = True
                messages.append({"role": "user", "content": user_content})
                continue

            # end_turn (or anything else): the final structured answer.
            text = "".join(b.text for b in resp.content
                           if getattr(b, "type", None) == "text")
            try:
                parsed = _json.loads(text)
            except _json.JSONDecodeError:
                try:
                    parsed = _json.loads(_repair_json(text))
                except _json.JSONDecodeError:
                    meta["outcome"] = "json_decode_failure"
                    return None, meta
            meta["outcome"] = "ok"
            return parsed, meta

        meta["outcome"] = "turn_limit"
        return None, meta
    except Exception as exc:
        print(f"[agentic_crop] loop failed for room {room.get('nr')}: {exc}")
        meta["outcome"] = f"error: {type(exc).__name__}: {exc}"
        return None, meta

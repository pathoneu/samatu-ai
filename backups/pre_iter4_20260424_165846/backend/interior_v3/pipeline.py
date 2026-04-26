"""
V3 pipeline entry point.

- Converts PDFs to page images (reuses V2.1 logic).
- Selects the most relevant pages (text heuristics — avoids Haiku classifier
  entirely so there is no fragile filter between data and Opus).
- Builds one big Opus 4.7 call with 4 (or 5) training projects as few-shot
  context plus the selected page images.
- Parses the returned JSON, writes debug logs, and returns a V1/V2.1-shaped
  response so the existing frontend can render it without changes.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .prompt_builder import (
    SYSTEM_PROMPT,
    build_user_message,
    load_training_dataset,
)

VISION_MODEL = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 12288
MAX_PAGES_TO_SHOW = 45
IMAGE_MAX_DIM = 1400
IMAGE_QUALITY = 78
DPI = 200

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "v3_runs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


# ───────── PDF → page images ───────────────────────────────────────────────

def _pdf_to_pages(filename: str, pdf_bytes: bytes) -> list[dict]:
    """Return one dict per page: {filename, page_idx, image_b64, text}."""
    import pdfplumber
    from pdf2image import convert_from_bytes

    text_by_page: dict[int, str] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text_by_page[i] = page.extract_text() or ""
    except Exception:
        pass

    pages: list[dict] = []
    try:
        images = convert_from_bytes(pdf_bytes, dpi=DPI, fmt="jpeg")
        for idx, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            pages.append({
                "filename": filename,
                "page_idx": idx,
                "image_b64": base64.b64encode(buf.getvalue()).decode("utf-8"),
                "text": text_by_page.get(idx, ""),
            })
    except Exception:
        return []

    return pages


def _resize_b64(b64: str, max_dim: int = IMAGE_MAX_DIM, quality: int = IMAGE_QUALITY) -> str:
    from PIL import Image
    data = base64.b64decode(b64)
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ───────── Page selection (heuristic, no Haiku) ─────────────────────────────

# Drawing types that MUST be present for full-project extraction. Each tuple
# gives (tag, [patterns]). When scoring we reward every page that looks like
# one of these; when selecting we also guarantee AT LEAST one page per tag
# makes it in if any page matched that tag.
_DRAWING_TAGS: list[tuple[str, list[re.Pattern]]] = [
    ("eksplikacija", [
        re.compile(r"patalp\w*\s*eksplikacij|eksplikacija\s+patalp|"
                   r"pavadinimas.*plotas.*m2|nr\.\s*pavadinimas", re.I),
    ]),
    ("pertvaros", [
        re.compile(r"pertvar[ųu].*plan|pertvaros\s+plan", re.I),
    ]),
    ("sienu_isklotines", [
        re.compile(r"sien[ųu]\s*iškl|sienų\s*iškl|iškotin|wall\s*elevation", re.I),
        re.compile(r"MAZGAS\s*[A-D]|detal\w+\s*\d|išklot", re.I),
    ]),
    ("lubu_planas", [
        re.compile(r"lub[ųu]\s*plan|reflected\s*ceiling|\+2[0-9]{3}\s", re.I),
        re.compile(r"LED\s*nišos|lub[ųu]\s*aukst", re.I),
    ]),
    ("plyteles", [
        re.compile(r"plyteli[ųu]\s*iškl|plyteli[ųu]\s*plan|tile\s*layout|"
                   r"keramik|1200x1200|1200x600|plyteli[ųu]\s*išd", re.I),
    ]),
    ("grindys", [
        re.compile(r"grind[ųu]\s*plan|floor\s*plan|grindų\s*danga|parketl|"
                   r"grindų\s*danga|išlyginamasis", re.I),
    ]),
    ("specifikacija", [
        re.compile(r"specifikacij|durys.*lentel|langų\s*lentel|medžiag\w+\s*sąraš", re.I),
    ]),
    ("fasadai", [
        re.compile(r"fasad|pjūvis\s+[A-Z]|šiaurės|pietų|rytų|vakarų", re.I),
    ]),
    ("santechnika", [
        re.compile(r"santechnik|vandentiek", re.I),
    ]),
    ("elektra", [
        re.compile(r"elektros\s+plan|rozeč|apšviet|el\.\s*plan", re.I),
    ]),
]

# Any drawing-like token gives a baseline "this is a drawing page" score,
# even if we can't classify it further. That way we don't drop pages 28+
# just because they happen to have sparse text extraction.
_BASELINE_DRAWING_PATTERNS = [
    re.compile(r"\d{3,5}\s*[x×]\s*\d{3,5}"),  # "1200x1200" or "2800 x 1200"
    re.compile(r"\bmm\b|\bcm\b", re.I),
    re.compile(r"M\s*1\s*:\s*\d{2,}"),  # "M 1:50" scale markers
    re.compile(r"\+2\d{3}|\+3\d{3}"),  # "+2800" ceiling height annotations
    re.compile(r"Patalpa\s+\d{2}", re.I),
]


def _score_page(page: dict) -> tuple[int, list[str]]:
    """Return (score, matched_tags). Higher = more relevant."""
    text = page.get("text", "") or ""
    filename = (page.get("filename") or "").lower()
    page_idx = page.get("page_idx", 0)

    tags: list[str] = []
    score = 0

    # Each drawing-tag match is worth a lot
    for tag, patterns in _DRAWING_TAGS:
        if any(p.search(text) for p in patterns):
            score += 100
            tags.append(tag)
        if any(p.search(filename) for p in patterns):
            score += 40

    # Baseline drawing markers — dimensions, scale, patalpa labels
    baseline_hits = sum(1 for p in _BASELINE_DRAWING_PATTERNS if p.search(text))
    score += min(baseline_hits, 5) * 15

    # Title page of each PDF is always worth a peek (eksplikacija often lives there)
    if page_idx == 0:
        score += 30
    elif page_idx <= 2:
        score += 10

    # If the page has NO text at all, it's probably a 3D render — mark it cheap
    if not text.strip():
        score -= 20

    return score, tags


def _select_pages(all_pages: list[dict], max_pages: int = MAX_PAGES_TO_SHOW) -> list[dict]:
    """
    1. Score every page.
    2. Force-include first page per file.
    3. Force-include at least one page for every drawing tag that appeared
       anywhere in the project (so tiles_layout always gets represented etc.).
    4. Fill remaining slots with highest-scored pages.
    """
    if len(all_pages) <= max_pages:
        return list(all_pages)

    scored: list[tuple[int, list[str], dict]] = [
        (s, tags, p) for p, (s, tags) in ((p, _score_page(p)) for p in all_pages)
    ]

    selected: list[dict] = []
    seen: set[tuple[str, int]] = set()

    def key_of(p: dict) -> tuple[str, int]:
        return (p.get("filename", ""), p.get("page_idx", 0))

    def add(p: dict) -> bool:
        k = key_of(p)
        if k in seen:
            return False
        seen.add(k)
        selected.append(p)
        return True

    # (a) First page per file
    seen_files: set[str] = set()
    for p in all_pages:
        fn = p.get("filename") or ""
        if fn and fn not in seen_files:
            seen_files.add(fn)
            add(p)
            if len(selected) >= max_pages:
                return selected

    # (b) Best page per drawing tag, in tag priority order
    tag_best: dict[str, tuple[int, dict]] = {}
    for s, tags, p in scored:
        for t in tags:
            prev = tag_best.get(t)
            if prev is None or s > prev[0]:
                tag_best[t] = (s, p)

    tag_priority = [t for t, _ in _DRAWING_TAGS]
    for t in tag_priority:
        if t in tag_best:
            _, p = tag_best[t]
            add(p)
            if len(selected) >= max_pages:
                return selected

    # (c) Fill remaining slots with top-scored pages
    scored.sort(key=lambda tpl: (-tpl[0],
                                 tpl[2].get("filename") or "",
                                 tpl[2].get("page_idx", 0)))
    for s, _, p in scored:
        if len(selected) >= max_pages:
            break
        add(p)

    return selected[:max_pages]


# ───────── Opus call ────────────────────────────────────────────────────────

def _clean_json_text(raw: str) -> str:
    """Strip markdown fences and leading/trailing junk from Opus output."""
    s = raw.strip()
    # Remove ```json ... ``` fences
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    # Trim to first { ... last }
    first = s.find("{")
    last = s.rfind("}")
    if first >= 0 and last > first:
        s = s[first:last + 1]
    return s.strip()


def _call_opus_with_pages(
    user_text: str,
    pages: list[dict],
    max_retries: int = 2,
) -> dict[str, Any]:
    """One synchronous Opus Vision call — blocking; wrapped in run_in_executor."""
    client = _get_client()

    content: list[dict] = [{"type": "text", "text": user_text}]
    for i, page in enumerate(pages):
        b64 = page.get("image_b64", "")
        if not b64:
            continue
        try:
            b64 = _resize_b64(b64)
        except Exception:
            pass
        label = f"[PDF {page.get('filename','?')} · puslapis {page.get('page_idx',0)+1}]"
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
        content.append({"type": "text", "text": label})

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.messages.create(
                model=VISION_MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            text_out = "".join(
                (b.text for b in resp.content if getattr(b, "type", None) == "text")
            )
            cleaned = _clean_json_text(text_out)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as je:
                return {
                    "_parse_error": str(je),
                    "_raw_text": text_out,
                }
            parsed["_raw_model_text"] = text_out[:2000]
            parsed["_usage"] = {
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
            }
            return parsed
        except Exception as exc:
            last_err = exc
            if attempt == max_retries:
                raise
            time.sleep(1.5 ** attempt)

    raise last_err or RuntimeError("Opus call failed without exception")


# ───────── Response shaping for V1 frontend compat ──────────────────────────

def _build_skaiciavimai(fakt: dict[str, Any],
                        validated: dict[str, Any],
                        patalpos: list[dict],
                        confidence: str) -> dict[str, Any]:
    """
    Shape V3 `faktiniai_kiekiai_suvestinis` into the `skaiciavimai` structure
    that InteriorProject.jsx reads for the 6 main apdailos cards + medžiagų
    cards. We keep arithmetic minimal — the Opus numbers are authoritative.
    """
    def _f(key: str, default: float = 0.0) -> float:
        v = fakt.get(key)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    dazymo_standart = _f("dazymo_plotas_standart_m2")
    dazymo_virs_3m = _f("dazymo_plotas_virs_3m_m2")
    dazymo_total = dazymo_standart + dazymo_virs_3m

    lubu_standart = _f("gkp_lubu_standart_m2")
    lubu_virs_3m = _f("gkp_lubu_virs_3m_m2")
    lubu_total = _f("gkp_lubu_total_m2") or (lubu_standart + lubu_virs_3m)

    # UI kortelėje "Dažomas plotas" pagrindinė reikšmė — standart aukštis
    # (taip kaip rangovo sąmatose). Virš 3m eina atskira eilute su pastaba.
    sienos_standart = max(0.0, dazymo_standart - lubu_standart)

    kampai_m = _f("kampai_m")
    ang_gkp = _f("angokrasciai_gkp_m")
    ang_daz = _f("angokrasciai_dazymo_m")
    plyteles_total = _f("plyteles_total_m2")
    parketas = _f("parketlentes_m2")
    pvc = _f("pvc_grindys_m2")
    isligin = _f("isliginamasis_m2")
    grindjuostes = _f("grindjuostes_total_m")

    bendras_plotas = sum((p.get("plotas_m2") or 0) for p in patalpos)
    avg_h = 2.8  # default; V3 does not vary ceiling per room

    # Sienos / lubos split rodomas UI kortelėje "Dažomas plotas"
    pastaba_virs = None
    if dazymo_virs_3m > 0:
        pastaba_virs = f"+ virš 3m: {round(dazymo_virs_3m, 1)} m² (atskira pozicija sąmatoje)"
    dazomas_plotas = {
        "sienos_m2": round(sienos_standart, 1),
        "lubos_m2":  round(lubu_standart if lubu_standart else bendras_plotas, 2),
        "viso_m2":   round(dazymo_standart, 1),
        "pastaba":   pastaba_virs,
        "confidence": confidence,
    }

    glaistymo_kampai = {
        "kampai_vnt":          0,  # Opus returns meters, not count
        "isoriniu_kampu_vnt":  0,
        "vidutinis_aukstis_m": avg_h,
        "viso_m":              round(kampai_m, 1),
        "skaiciavimo_budas":   "opus_v3",
    }

    angokrasciai = {
        "langu_vnt":  0,
        "duru_vnt":   0,
        "viso_m":     round(ang_gkp + ang_daz, 1),
        "viso_m_x2":  round((ang_gkp + ang_daz) * 2, 1),
        "area_m2":    round((ang_gkp + ang_daz) * 0.10, 2),
        "details":    [],
    }

    # UI nuskaito dazai materials; V3 negrąžina litrų — skaičiuojame iš viso ploto
    sienos_total = max(0.0, dazymo_total - lubu_total)  # sienos visos (standart + virš 3m)
    dazai_sienoms = round(sienos_total * 2 / 9, 1)
    dazai_luboms = round(lubu_total * 2 / 10, 1)
    gruntas = round(dazymo_total * 0.15, 1)

    gk_lapai = int(round(sienos_total / 3.0 * 1.1)) if sienos_total > 0 else 0
    glaistas_kg = int(round(dazymo_total * 1.25 * 1.0))  # Q2 defaults
    glaistas_maisai = (glaistas_kg + 24) // 25 if glaistas_kg > 0 else 0

    return {
        "dazomas_plotas": dazomas_plotas,
        "glaistymo_kampai": glaistymo_kampai,
        "angokrasciai": angokrasciai,
        "lubu_perimetras": {"viso_m": 0},
        "grindjuostes": {"viso_m": round(grindjuostes, 1)},
        "uzuolaidu_nisos": {"viso_m": 0, "details": []},
        "dazai": {
            "sienos_l":  dazai_sienoms,
            "lubos_l":   dazai_luboms,
            "gruntas_l": gruntas,
            "viso_l":    round(dazai_sienoms + dazai_luboms + gruntas, 1),
        },
        "gk_lapai": {"vnt": gk_lapai},
        "glaistas": {
            "lygis":       "Q2",
            "kg":          glaistas_kg,
            "maisai_25kg": glaistas_maisai,
        },
        "validation_notes": [],
        "plyteles_m2": round(plyteles_total, 1),
        # V3-specific extras the UI can surface if it wants:
        "_v3_breakdown": {
            "dazymo_standart_m2": round(dazymo_standart, 1),
            "dazymo_virs_3m_m2":  round(dazymo_virs_3m, 1),
            "lubu_standart_m2":   round(lubu_standart, 1),
            "lubu_virs_3m_m2":    round(lubu_virs_3m, 1),
            "angokrasciai_gkp_m":    round(ang_gkp, 1),
            "angokrasciai_dazymo_m": round(ang_daz, 1),
            "parketlentes_m2":    round(parketas, 1),
            "pvc_grindys_m2":     round(pvc, 1),
            "isliginamasis_m2":   round(isligin, 1),
            "plyteles_1200x1200_m2": round(_f("plyteles_1200x1200_m2"), 1),
            "plyteles_1200x600_m2":  round(_f("plyteles_1200x600_m2"), 1),
            "plyteles_standart_m2":  round(_f("plyteles_standart_m2"), 1),
        },
    }


def _shape_for_frontend(v3: dict[str, Any]) -> dict[str, Any]:
    """
    Make V3 output consumable by the existing InteriorProject.jsx UI.
    Provides `skaiciavimai` in the V1 shape so the UI picks numbers directly
    from Opus rather than re-running frontend calc engine.
    """
    patalpos = v3.get("patalpos") or []
    validated = v3.get("validated_quantities") or {}
    fakt = v3.get("faktiniai_kiekiai_suvestinis") or {}
    reasoning = v3.get("reasoning") or {}
    warnings = v3.get("warnings") or []
    confidence = v3.get("confidence") or "medium"

    out = dict(v3)
    out["status"] = "ok"
    out.setdefault("projektas", v3.get("projektas") or "Interjero projektas")
    out.setdefault("tipas", v3.get("tipas") or "interjeras")
    out["patalpos"] = patalpos
    out["validated_quantities"] = validated
    out["faktiniai_kiekiai_suvestinis"] = fakt
    out["reasoning"] = reasoning
    out["warnings"] = warnings
    out["scope_type"] = v3.get("scope_type") or "full_project"
    out["confidence"] = confidence

    # Stored skaiciavimai — UI reads these directly
    out["skaiciavimai"] = _build_skaiciavimai(fakt, validated, patalpos, confidence)

    # raw_calc_data kept for back-compat but UI now prefers skaiciavimai above
    out["raw_calc_data"] = {
        "patalpos": patalpos,
        "bendras_plotas_m2": v3.get("bendras_plotas_m2") or 0,
        "lubu_aukstis_m": v3.get("lubu_aukstis_m") or 2.8,
        "sudetingumo_klase": v3.get("sudetingumo_klase") or None,
        "scope_type": out["scope_type"],
        "validated_quantities": validated,
        "meta": {"doors": [], "windows": [], "niches": []},
        "sekcijos": {},
    }
    return out


# ───────── Logging ──────────────────────────────────────────────────────────

def _log_run(stage: str, data: Any) -> None:
    try:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        path = _LOG_DIR / f"{ts}_{stage}.json"
        safe = _strip_images(data)
        path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    except Exception:
        pass


def _strip_images(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_images(v) for k, v in obj.items() if k != "image_b64"}
    if isinstance(obj, list):
        return [_strip_images(x) for x in obj]
    return obj


# ───────── Public entry point ───────────────────────────────────────────────

async def process_interior_project_v3(
    pdf_files: list[tuple[str, bytes]],
    holdout_pid: str | None = None,
    project_hint: str = "",
) -> dict[str, Any]:
    """
    Run V3 end-to-end.

    Args:
        pdf_files: [(filename, pdf_bytes), ...]
        holdout_pid: if set (e.g. "P1"), exclude that project from the few-shot
                     block. Used only by the leave-one-out accuracy sweep.
        project_hint: optional human-written hint (e.g. "Projektas P3, premium")
    """
    if not pdf_files:
        return {"status": "error", "error": "Nepateikti PDF failai"}

    t0 = time.time()

    # 1. Convert all PDFs to page images
    all_pages: list[dict] = []
    for filename, pdf_bytes in pdf_files:
        all_pages.extend(_pdf_to_pages(filename, pdf_bytes))
    if not all_pages:
        return {"status": "error", "error": "Nepavyko konvertuoti PDF į puslapius"}

    # 2. Rank and pick the top pages
    selected = _select_pages(all_pages)
    _log_run("page_selection", {
        "total_pages": len(all_pages),
        "selected_pages": [{"filename": p["filename"], "page_idx": p["page_idx"]}
                            for p in selected],
    })

    # 3. Build prompt
    dataset = load_training_dataset()
    user_text = build_user_message(dataset, exclude_pid=holdout_pid,
                                   project_hint=project_hint)

    # 4. Call Opus on a worker thread (blocking SDK)
    loop = asyncio.get_running_loop()
    try:
        parsed = await loop.run_in_executor(
            None, _call_opus_with_pages, user_text, selected
        )
    except Exception as e:
        return {
            "status": "error",
            "error": f"V3 Opus call failed: {e}",
            "traceback": traceback.format_exc(),
        }

    if "_parse_error" in parsed:
        _log_run("parse_error", parsed)
        return {
            "status": "error",
            "error": f"Opus grąžino ne-JSON atsakymą: {parsed['_parse_error']}",
            "raw_text": parsed.get("_raw_text", "")[:4000],
        }

    shaped = _shape_for_frontend(parsed)
    shaped["_elapsed_s"] = round(time.time() - t0, 1)
    shaped["_holdout_pid"] = holdout_pid
    _log_run("response", shaped)
    return shaped

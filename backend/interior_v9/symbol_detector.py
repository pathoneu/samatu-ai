"""
Symbol detection — Togal-style "Image Search" arba count-by-template.

Du režimai:
1. detect_symbols(pdf, type) — Vision'as suranda visus tipą (durys/langai/rozetės)
   per visus puslapius. Grąžina: count + bbox koordinatės.

2. count_symbols_by_template(pdf, template_b64) — vartotojas paspauskite ant
   simbolio brėžinyje, sistema suranda visus panašius. Naudoja CLIP embedding
   similarity (jei galimas) arba Vision pattern matching.

Šaltinis: skill A.2 (SoM) + Togal Image Search docs.
"""
from __future__ import annotations
import io
import json
import os
import re
from typing import Any

import anthropic


VISION_MODEL = "claude-opus-4-8"


def _parse_vision_json(text: str) -> dict:
    """Robust parser for Vision responses that may include trailing text,
    code fences, or unquoted keys. Always returns a dict; never raises.

    2026-05-06: hardened after 'Extra data: line 6 column 1' bug — Vision
    occasionally appends explanatory prose AFTER the JSON. raw_decode()
    extracts the first complete object and ignores the rest.
    """
    cleaned = re.sub(r'^```(?:json)?\s*\n', '', text or '')
    cleaned = re.sub(r'\n```\s*$', '', cleaned).strip()
    if not cleaned:
        return {}
    decoder = json.JSONDecoder()
    # Try strict parse first.
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back: scan for first `{` and use raw_decode (tolerates trailing).
    brace_idx = cleaned.find('{')
    if brace_idx >= 0:
        try:
            obj, _ = decoder.raw_decode(cleaned[brace_idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    # Last resort: try to fix unquoted keys + trailing commas (legacy path).
    fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned)
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        # Try raw_decode on the fixed text too.
        b = fixed.find('{')
        if b >= 0:
            try:
                obj, _ = decoder.raw_decode(fixed[b:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    return {"_parse_failed": True, "_raw_excerpt": cleaned[:200]}


SYMBOL_TYPES = {
    # ── ELEKTROS PLANAS — sutartiniai ženklai pagal LST EN 60617 ──
    "rozetes": {
        "lt": "kištukinės rozetės",
        "page_types": ["electrical", "rozetes", "elektros"],
        "patterns": [
            "apskritimas su 1-2 trumpomis radialinėmis linijomis (kištuko anga)",
            "raidė R arba puslankis su 'R' tekstu",
            "skaitmuo (1-4) prie apskritimo — gali būti rozečių grupė",
            "kvadratas grindų aukštyje (grindų rozetė) su 'P' arba 'P/'",
        ],
    },
    "jungikliai": {
        "lt": "jungikliai",
        "page_types": ["electrical", "elektros"],
        "patterns": [
            "trumpas brūkšnys nukreiptas link sienos (vienpolis jungiklis)",
            "raidė J apskritime",
            "kvadratinis simbolis su trumpa linija prie sienos",
            "skaitmuo prie simbolio (jungiklio grupių sk., 2-3 grupės)",
        ],
    },
    "sviestuvai": {
        "lt": "šviestuvai (lubinis apšvietimas)",
        "page_types": ["ceiling", "lubu", "electrical", "elektros"],
        "patterns": [
            "apskritimas su X kryžmum (taškinis šviestuvas)",
            "kvadratas su X arba diagonaliais brūkšniais (LED panelis)",
            "apskritimas su 'L' arba 'Š' raide",
            "linijinis šviestuvas (LED juostos blokas)",
        ],
    },
    "pakabinami_sviestuvai": {
        "lt": "pakabinami šviestuvai",
        "page_types": ["ceiling", "lubu"],
        "patterns": [
            "apskritimas viduryje patalpos su žymėjimu virš stalo (valgomasis)",
            "didesnis apskritimas su krypštim",
            "lubų plane: simbolis su 'P' (pakabinamas) arba dryžiais",
        ],
    },
    "led_juostos": {
        "lt": "LED juostos / nišos",
        "page_types": ["ceiling", "lubu"],
        "patterns": [
            "ilga linijinė formacija sienos perimetre arba lubų niše",
            "punktyriniu konturu pažymėta linija (slėpta apšvietimo niša)",
            "tekstas LED arba LED juosta",
        ],
        "linear": True,  # matuojam ilgį, ne skaičių
    },
    "difuzoriai": {
        "lt": "ventiliacijos difūzoriai",
        "page_types": ["ceiling", "lubu", "ventilation"],
        "patterns": [
            "apskritimas su 4 stačiom linijom centrinėj zonoj (apvalūs grotelės)",
            "kvadratas su X kryžmum (kvadratinės grotelės)",
            "kvadratas su rodyklėm (oro srauto kryptis)",
            "apvalus simbolis su 'V' arba 'V+' žymėjimu",
        ],
    },
    # ── SANTECHNIKOS PLANAS — sutartiniai ženklai pagal LST EN 806 ──
    "klozetai": {
        "lt": "klozetai (WC)",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "stačiakampis su apskritimu apačioje (klozeto vaizdas iš viršaus)",
            "ovalus simbolis prie sienos su trumpa linija",
            "tekstas WC arba simbolis prie sienos",
        ],
    },
    "praustuvai": {
        "lt": "praustuvai (kriauklės)",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "ovalus arba pusapvalis simbolis prie sienos (vonioje, virtuvėje)",
            "tekstas PR prie simbolio",
        ],
    },
    "vonios": {
        "lt": "vonios (su dušu arba įvonios)",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "didelis stačiakampis su simboliu (V) viduje (1.7×0.7m)",
            "kvadratas su trapu (du. kabina, 0.9×0.9m)",
        ],
    },
    "trapai": {
        "lt": "trapai (drenažo angos)",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "kvadratinis arba apvalus simbolis grindyse su kryžmum (taškinis trapas)",
            "ilga linijinė anga (linijinis latakas, dušo zonoje)",
            "apskritimas su 'T' raide",
        ],
    },
    "maisytuvai": {
        "lt": "maišytuvai",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "trumpas išsikišimas iš sienos virš praustuvo arba vonios",
            "simbolis su rodyklėm (vandens srauto)",
            "tekstas M prie linijos sankirtos",
        ],
    },
    "gyvatukai": {
        "lt": "gyvatukai (rankšluosčių džiovintuvai)",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "stačiakampis ant sienos su vertikaliom skersinėm linijom (gyvatuko forma)",
            "tekstas G arba GR sienoje vonios zonoje",
        ],
    },
    "skalbimo_masinos": {
        "lt": "skalbimo mašinos prijungimas",
        "page_types": ["plumbing", "santechnika"],
        "patterns": [
            "kvadratas grindyse su tekstu SK arba SM",
            "specifinis simbolis prie sienos su nuotekų ir vandens prijungimu",
        ],
    },
    "radiatoriai": {
        "lt": "radiatoriai (šildymas)",
        "page_types": ["heating", "santechnika"],
        "patterns": [
            "stačiakampis su vidinėm vertikaliom linijom (radiatoriaus sekcijos)",
            "ryški linija prie sienos su skaičium (sekcijų sk.)",
        ],
    },
    # ── AUKŠTŲ PLANAS — pagrindiniai elementai ──
    "durys": {
        "lt": "durys (vidaus)",
        "page_types": ["floor_plan", "aukstu"],
        "patterns": [
            "lankai 90° rotacijos kampu (atidarymo trajektorija)",
            "kvadratinis bbox staktoms (0.8-0.9m plotis)",
            "punktyrinė linija arba šviesi linija atspindinti atidarymą",
        ],
    },
    "langai": {
        "lt": "langai",
        "page_types": ["floor_plan", "aukstu", "elevation", "fasadas"],
        "patterns": [
            "paralelinės dvigubos linijos sienoje (stiklai)",
            "rectangle su X kryžmum (uždarytas langas)",
            "rentinys plane: trumpa linija statmenai sienai",
        ],
    },
}


def list_symbol_types_for_page_type(page_type: str) -> list[str]:
    """Grąžina simbolių tipus, kurie tikėtini tame puslapio tipe.

    Pvz: "elektros" puslapyje ieškom rozeces+jungiklius+sviestuvus,
    bet ne klozetus ar trapus.
    """
    if not page_type:
        return []
    pt = page_type.lower()
    matches = []
    for sym_type, info in SYMBOL_TYPES.items():
        for accepted in info.get("page_types", []):
            if accepted in pt or pt in accepted:
                matches.append(sym_type)
                break
    return matches


def detect_symbols(
    pdf_bytes: bytes,
    symbol_type: str,
    page_nr: int = 1,
) -> dict:
    """Surandam visus simbolius vieno tipo per puslapį.

    Args:
        pdf_bytes: PDF
        symbol_type: viena iš SYMBOL_TYPES key'ų
        page_nr: 1-indexed

    Returns:
        {"count": int, "symbols": [{x_pct, y_pct, confidence}, ...]}
    """
    if symbol_type not in SYMBOL_TYPES:
        return {"error": f"unknown symbol_type: {symbol_type}"}

    info = SYMBOL_TYPES[symbol_type]

    # Render PDF page
    try:
        import pdfplumber
        from PIL import Image
        import base64
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_nr < 1 or page_nr > len(pdf.pages):
                return {"error": "page out of range"}
            page = pdf.pages[page_nr - 1]
            pim = page.to_image(resolution=200)
            img = pim.original.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        return {"error": f"render: {e}"}

    # Vision call
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "no API key"}
    client = anthropic.Anthropic(api_key=api_key, timeout=60.0)

    pattern_text = "\n".join(f"- {p}" for p in info["patterns"])
    prompt = f"""Šitame brėžinyje surandi VISUS {info['lt']}.

Pattern'ai (kaip atrodo {info['lt']} brėžiniuose):
{pattern_text}

Per kiekvieną aptiktą simbolį grąžink:
- "x_pct": x koordinatė kaip procentas nuo puslapio pločio (0.0-1.0)
- "y_pct": y koordinatė kaip procentas nuo puslapio aukščio (0.0-1.0)
- "confidence": "high" (aiškiai matomas), "medium" (galimas), "low" (panašu)

NESUKŪRK simbolių, kurių nematai. Geriau grąžink mažiau, bet tiksliau.

Output JSON:
{{
  "count": int,
  "symbols": [{{"x_pct": 0.15, "y_pct": 0.25, "confidence": "high"}}, ...]
}}
"""

    try:
        resp = client.messages.create(
            model=VISION_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": img_b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        parsed = _parse_vision_json(text)
        return parsed
    except Exception as e:
        return {"error": str(e)}


def detect_symbols_bundled(
    pdf_bytes: bytes,
    page_nr: int,
    symbol_types: list[str],
) -> dict:
    """BUNDLED detection — vienas Vision call per puslapį visiems tipams.

    Vietoj N atskirų API call'ų, padarom VIENĄ call kuris klausia AI rasti
    VISŲ duotų simbolių tipų tame puslapyje vienu metu. Sumažina latency
    ~10x (1 call vs 10).

    Args:
        pdf_bytes: PDF
        page_nr: 1-indexed
        symbol_types: simbolių tipų sąrašas, kurie tikėtini šiame puslapyje
                      (iš list_symbol_types_for_page_type)

    Returns:
        {sym_type: {"count": int, "symbols": [...]}, ...} — per kiekvieną tipą
    """
    if not symbol_types:
        return {}

    # Validuoti tipus
    valid_types = [t for t in symbol_types if t in SYMBOL_TYPES]
    if not valid_types:
        return {}

    # Render PDF page
    try:
        import pdfplumber
        from PIL import Image
        import base64
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_nr < 1 or page_nr > len(pdf.pages):
                return {}
            page = pdf.pages[page_nr - 1]
            pim = page.to_image(resolution=200)
            img = pim.original.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        return {"_error": f"render: {e}"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"_error": "no API key"}
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

    # Bundled prompt — visi tipai vienu Vision call'u
    type_descriptions = []
    for st in valid_types:
        info = SYMBOL_TYPES[st]
        patterns = "\n      - ".join(info["patterns"])
        type_descriptions.append(f"  {st} ({info['lt']}):\n      - {patterns}")
    types_block = "\n".join(type_descriptions)

    is_linear_types = [st for st in valid_types
                        if SYMBOL_TYPES[st].get("linear")]

    prompt = f"""Šitame brėžinyje surask šių simbolių tipus:

{types_block}

Per kiekvieną aptiktą simbolį grąžink:
- "type": simbolio tipas (vienas iš: {', '.join(valid_types)})
- "x_pct": x koordinatė procentais nuo puslapio pločio (0.0-1.0)
- "y_pct": y koordinatė procentais nuo puslapio aukščio (0.0-1.0)
- "confidence": "high" | "medium" | "low"

NESUKURK simbolių, kurių nematai. Geriau grąžink mažiau, bet tiksliau.
{('Linijiniai tipai (LED juostos): "x_pct"/"y_pct" yra centras, '
  '"length_m" — apytikslis ilgis metrais.') if is_linear_types else ''}

Output JSON (TIK JSON, be markdown):
{{
  "symbols": [
    {{"type": "rozetes", "x_pct": 0.15, "y_pct": 0.25, "confidence": "high"}},
    ...
  ]
}}
"""

    try:
        resp = client.messages.create(
            model=VISION_MODEL,
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": img_b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        parsed = _parse_vision_json(text)

        # Group by type
        by_type: dict[str, dict] = {}
        for sym in parsed.get("symbols", []):
            t = sym.get("type")
            if t not in valid_types:
                continue
            if t not in by_type:
                by_type[t] = {"count": 0, "symbols": []}
            by_type[t]["count"] += 1
            by_type[t]["symbols"].append({
                "x_pct": sym.get("x_pct", 0),
                "y_pct": sym.get("y_pct", 0),
                "confidence": sym.get("confidence", "medium"),
                "length_m": sym.get("length_m"),  # tik linijiniams
            })
        return by_type
    except Exception as e:
        return {"_error": str(e)}


def detect_all_symbols_for_pdf(
    pdf_bytes: bytes,
    page_classifications: list[dict] | None = None,
    only_types: list[str] | None = None,
    max_pages_per_type: int = 3,
) -> dict:
    """ORCHESTRATORINĖ funkcija — surandam VISUS svarbius simbolius pilnam PDF.

    Logika:
      1. page_classifier identifikuoja kiekvieno puslapio tipą (electrical,
         plumbing, ceiling, floor_plan, etc.).
      2. Per kiekvieną page_type — list_symbol_types_for_page_type() grąžina
         simbolių tipus, kurie tikėtini šiame puslapyje.
      3. Per kiekvieną (page, sym_type) porą — detect_symbols() grąžina count.
      4. Agreguojam VISUS skaičius per simbolio tipą (jei tas pats simbolis
         randasi keliuose puslapiuose, imam MAX'ą — vengiam dublikavimo).

    Args:
        pdf_bytes: PDF
        page_classifications: iš classify_pdf() — list of {page, type, ...}
        only_types: jei nurodyta, ieškom tik šių tipų (perf optimization)
        max_pages_per_type: max puslapių per tipą (perf — vengti N*M call'ų)

    Returns:
        {
          "by_type": {
            "rozetes":   {"total": 32, "pages": [{page: 4, count: 32}]},
            "klozetai":  {"total": 2,  "pages": [{page: 6, count: 2}]},
            ...
          },
          "stats": {api_calls, ms_total, page_types_found},
        }
    """
    import time
    t0 = time.time()

    # Default: visus puslapius traktuoti kaip nežinomus
    if not page_classifications:
        # Greitas fallback: pamatuojam puslapių skaičių
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page_classifications = [
                    {"page": i+1, "type": "unknown"}
                    for i in range(len(pdf.pages))
                ]
        except Exception as e:
            return {"error": f"pdf open: {e}"}

    # OPTIMIZACIJA (Phase 4 fix): per kiekvieną PUSLAPĮ — vienas Vision call
    # visiems tinkamiems simbolių tipams. Buvo: O(N_types × N_pages) call'ai.
    # Dabar: O(N_pages) call'ai. Maksimalus speedup ~10×.
    # Plus parallel execution per puslapius (su ThreadPoolExecutor).
    page_to_types: dict[int, list[str]] = {}
    for pc in page_classifications:
        page_nr = pc.get("page") or pc.get("page_nr")
        ptype = pc.get("type", "")
        if not page_nr:
            continue
        sym_types = list_symbol_types_for_page_type(ptype)
        if not sym_types:
            sym_types = list(SYMBOL_TYPES.keys())
        if only_types:
            sym_types = [st for st in sym_types if st in only_types]
        if sym_types:
            page_to_types.setdefault(page_nr, []).extend(
                [st for st in sym_types if st not in page_to_types.get(page_nr, [])]
            )

    # Limituojam — max_pages_per_type per kiekvieną tipą per visą rezultatą
    # (bet kadangi mes per puslapį visus tipus skaičiuojam, čia max puslapių iš viso)
    pages_to_process = list(page_to_types.keys())[:max(max_pages_per_type * 3, 6)]

    # PARALLEL: visi puslapiai per ThreadPool (Vision sync API → kiekviena thread)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    page_results: dict[int, dict] = {}
    api_calls = 0

    def _detect_page(page_nr):
        types = page_to_types.get(page_nr, [])
        return page_nr, detect_symbols_bundled(pdf_bytes, page_nr, types)

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(_detect_page, pn) for pn in pages_to_process]
        for fut in as_completed(futures):
            try:
                page_nr, by_t = fut.result()
                api_calls += 1
                if isinstance(by_t, dict) and "_error" not in by_t:
                    page_results[page_nr] = by_t
            except Exception as e:
                print(f"[detect_all_bundled] page failed: {e}")

    # Aggregate per tipas — MAX'ą per puslapius (NE sum, kad nebūtų dubliuoti)
    by_type: dict[str, dict] = {}
    for page_nr, page_by_type in page_results.items():
        for sym_type, info in page_by_type.items():
            if sym_type not in SYMBOL_TYPES:
                continue
            cnt = info.get("count", 0)
            if sym_type not in by_type:
                by_type[sym_type] = {"total": 0, "pages": []}
            # MAX strategija (vengti dubliuoti tarp puslapių)
            if cnt > by_type[sym_type]["total"]:
                by_type[sym_type]["total"] = cnt
            by_type[sym_type]["pages"].append({
                "page": page_nr,
                "count": cnt,
                "symbols": info.get("symbols", [])[:30],
            })

    return {
        "by_type": by_type,
        "stats": {
            "api_calls": api_calls,
            "pages_processed": len(pages_to_process),
            "ms_total": int((time.time() - t0) * 1000),
            "method": "bundled+parallel",
        },
    }


def count_symbols_by_template(
    pdf_bytes: bytes,
    template_x_pct: float,
    template_y_pct: float,
    template_size_pct: float = 0.05,
    page_nr: int = 1,
) -> dict:
    """Vartotojas paspauskite ant simbolio brėžinyje (template_x/y_pct).
    Sistema suranda visus panašius simbolius.

    PoC: Naudojam Vision per template image patch'ą.
    Production: CLIP embeddings + FAISS index (greičiau).
    """
    try:
        import pdfplumber
        from PIL import Image
        import base64
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_nr < 1 or page_nr > len(pdf.pages):
                return {"error": "page out of range"}
            page = pdf.pages[page_nr - 1]
            pim = page.to_image(resolution=200)
            img = pim.original.convert("RGB")
            w, h = img.size
            # Template patch — kvadratas aplink template_x/y
            tx = int(template_x_pct * w)
            ty = int(template_y_pct * h)
            ts = int(template_size_pct * min(w, h))
            template_box = (max(0, tx - ts), max(0, ty - ts),
                            min(w, tx + ts), min(h, ty + ts))
            template_img = img.crop(template_box)

            # Encode template + full image
            buf_t = io.BytesIO()
            template_img.save(buf_t, format="JPEG", quality=90)
            template_b64 = base64.b64encode(buf_t.getvalue()).decode("ascii")

            buf_f = io.BytesIO()
            img.save(buf_f, format="JPEG", quality=85)
            full_b64 = base64.b64encode(buf_f.getvalue()).decode("ascii")
    except Exception as e:
        return {"error": f"render: {e}"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "no API key"}
    client = anthropic.Anthropic(api_key=api_key, timeout=90.0)

    prompt = """Pirmas paveikslas yra ŠABLONO simbolis (mažas iškirptas patch'as).
Antras paveikslas yra PILNAS brėžinys.

Tavo užduotis: surandi VISUS simbolius pilname brėžinyje, kurie ATITINKA šablono
simbolį (tokio pat tipo, panašios formos).

Per kiekvieną grąžink:
- "x_pct", "y_pct" — koordinatės pilname brėžinyje (0.0-1.0)
- "confidence" — "high"/"medium"/"low"

Output JSON:
{
  "count": int,
  "matches": [{"x_pct": 0.12, "y_pct": 0.34, "confidence": "high"}, ...]
}
"""

    try:
        resp = client.messages.create(
            model=VISION_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": template_b64,
                    }},
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg",
                        "data": full_b64,
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        parsed = _parse_vision_json(text)
        return parsed
    except Exception as e:
        return {"error": str(e)}

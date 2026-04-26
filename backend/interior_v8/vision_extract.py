"""
V7 AI-first pipeline.

Architektūra:
1. PDF → visi puslapiai kaip nuotraukos (300 DPI)
2. Vision call'as su DETALIU prompt'u — AI matuoja PER KAMBARĮ
3. Vision grąžina:
   - Patalpos su matmenimis
   - Per kambarį: dazymo_plotas, kampai_m, angokraščiai
   - Sutartiniai ženklai (durys, langai, nišos, stoglangiai)
   - Spalviniai indikatoriai (LED nišos, plytelinės zonos)
4. Sanity check: palyginti su V6 vector duomenimis (bendras plotas).
   Jei gap > 30% — perspeti vartotoją.
"""

from __future__ import annotations
import asyncio
import base64
import io
import json
import re
import time
from typing import Any

from .vision_helpers import (
    _pdf_to_pages,
    _resize_b64,
    _clean_json_text,
    _get_client,
)
from .vision_multi_pass import merge_multi_pass_results, run_multi_pass_vision
from .vision_self_validation import build_validation_prompt, merge_validation_result


VISION_MODEL = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 8192
IMAGE_MAX_DIM = 2000  # didesnis nei V5 — kad matmenys (mm) būtų aiškūs


SYSTEM_PROMPT = """Tu esi profesionalus LT statybos sąmatininkas (quantity surveyor) su 15+ metų patirtimi vidaus apdailoje. Tavo darbas — pagal RICS NRM2 standartą + LT statybos praktikas atlikti TIKSLIUS matavimus iš brėžinio.

Atsakyk TIK JSON formatu. Jokio papildomo teksto."""


USER_PROMPT = """Pateiktas LT vidaus apdailos brėžinys (gali būti vienas ar keli puslapiai). Tavo užduotis — IŠMATUOTI ir SUSKAIČIUOTI sąmatos pozicijas TIESIOGIAI iš brėžinio.

# DALIS 1 — Identifikuok PATALPAS

Per kiekvieną patalpą:
- `nr`: numeracija (01, 02, ... — kaip brėžinyje)
- `pavadinimas`: tikslus pavadinimas (Svetainė, Vonia 1, Drabužinė, Garažas, etc.)
- `paskirtis`: gyvenamoji|miegamoji|virtuve|vonia|wc|koridorius|holas|rubine|katiline|skalbykla|valgomasis|tambūras|garazas
- `plotas_m2`: TIKSLUS plotas. Šaltiniai (pirmenybės tvarka):
  1. Eksplikacija lentelė ("01 HOLAS 11.55") — pirmenybė
  2. Inline brėžinyje ("Miegamasis 14.5m²")
  3. Skaičiuojamas iš sienų matmenų (mm parašyta brėžinyje)
- `perimetras_m`: tikras perimetras m. Sumavimas iš sienų ilgių brėžinyje (mm)
- `lubu_aukstis_m`: paprastai 2.7-2.85. Jei pjūvyje H-3400 ar +3400 — tai virš 3m
- `lubu_tipas`: gkp | betonas | pakabinamos
  - GKP: matosi dvigubas karkasas, GKP žymėjimas
  - Betonas: tambūras, garažas, tech. patalpos
  - Pakabinamos: matomas „pakabinamos lubos" žymėjimas

# DALIS 2 — TIESIOGIAI SUSKAIČIUOK per kambarį (RICS NRM2):

## `dazymo_plotas_m2` — TIKSLUS dažomas plotas
**Formulė per patalpą**:
- Sienos = perimetras × lubų aukštis − angos − plytelinės_zonos
  - Atimti durys (W × H) jei plotas ≥ 1m² (NRM2 Section 29 rule)
  - Atimti langai (W × H) jei plotas ≥ 1m²
  - Vonia/WC: atimti perimetras × 2.0m (plytelinė juosta)
  - Drabužinė: jei spintos visose sienose — atimti perim × H × 0.5
  - Garažas, tambūras: 0 (nedažoma)
- Lubos: + plotas_m2 jei lubu_tipas=gkp
**Pridėti per visas patalpas → bendras dazymo plotas**

## `kampai_m` — TIKSLŪS dažymo kampai
**Formulė per patalpą** (RICS NRM2 + LT):
- + Lubų periferija (= perimetras)
- + 4 vidiniai vert kampai × H (paprastas stačiakampis)
  - Jei L-formos: 6 × H
  - Jei T-formos: 8 × H
- + Nišų briaunos: 2 × ilgis per niša (LED nišos lubose)
- + Išoriniai kampai (kolonos, atsikišimai): kampu_skaicius × H
- Vonia/garažas: 0 (plytelės/silikonas, ne dažo)
- Stoglangiai: + 2 × (W + H) per stoglangis (4 reveal'ai)

## `angokrasciu_gkp_m` — angokraščių GKP apdaila
**Per patalpą** ((W + 2H)/1000):
- Standart durys (su apvadu): 0 (turi savo apdailą)
- Paslėptos (beapvadinės) durys: pridedam (W + 2H)/1000
- Langai: pridedam TIK jei gkp_angokrastis arba premium projektas (W ≥ 2.0m)
- Stoglangiai: visada (4 reveal'ai)

## `pasleptu_duru_staktu_m` — beapvadinių staktų ilgis
- Σ((W + 2H)/1000) per kiekvieną PASLĖPTĄ duris

## `nisu_metrai` — LED nišų ilgis
- Σ ilgis per kiekvieną nišą (matomas pažymėjimu „karnizas/niša")

## `pvc_grindys_m2`, `plyteles_grindys_m2`
- Vonia/WC/skalbykla/katilinė: plytelės grindys
- Garažas/tambūras: nedažoma
- Kitos: PVC arba parketas (default PVC)

# DALIS 3 — Sutartiniai ženklai

Brėžinyje matomi simboliai:
- **Durys**: lankai (90° rotacija) — kvadratinis bbox + lankas
- **Langai**: paralelinės dvigubos linijos sienoje
- **Nišos LED**: pažymėjimas „karnizas/niša Xcm gylio" + raudona linija lubose
- **Stoglangiai**: ovalas/lankas stoge (matomas pjūvyje arba lubų plane)
- **Plytelinės sienos vonioje**: matosi pažymėjimas + plytelių pattern

Per kiekvieną:
- Durys: tipas (standart=su apvadu / pasleptos=beapvadinės), W (mm), H (mm)
- Langai: W, H, gkp_angokrastis (true jei premium platus angokraštis)

# DALIS 3.5 — bbox_pct (patalpos koordinates) — OPTIONAL

Jei žinai patalpos koordinates brėžinyje, gali pridėti bbox_pct lauką.
Tai NEPRIVALOMA - jei nežinai tiksliai, palik null.

Formatas: 4 skaičiai 0.0-1.0 nuo puslapio kairio viršaus:
- "x": kairysis kraštas
- "y": viršutinis kraštas
- "w": plotis (dalis nuo puslapio pločio)
- "h": aukštis (dalis nuo puslapio aukščio)

NEEIKVOK laiko bbox - svarbiau plotai ir paskirtys.

# DALIS 4 — Globalūs duomenys

- `archetipas`: standart | premium | renovacija | dideli_namu_premium
- `bendras_plotas_m2`: Σ patalpų plotų (be garažo/tambūro)
- `pastabos`: trumpas tekstas

# OUTPUT (TIK JSON):

{
  "archetipas": "...",
  "bendras_plotas_m2": 0.0,
  "patalpos": [
    {
      "nr": "01",
      "pavadinimas": "...",
      "paskirtis": "...",
      "puslapio_nr": 1,
      "bbox_pct": {"x": 0.15, "y": 0.20, "w": 0.30, "h": 0.25},
      "plotas_m2": 0.0,
      "perimetras_m": 0.0,
      "lubu_aukstis_m": 2.82,
      "lubu_tipas": "gkp",
      "dazymo_plotas_m2": 0.0,
      "kampu_metrai": 0.0,
      "angokrasciu_gkp_m": 0.0,
      "pasleptu_duru_staktu_m": 0.0,
      "pvc_grindys_m2": 0.0,
      "plyteles_grindys_m2": 0.0,
      "plyteles_sienos_m2": 0.0,
      "isliginamasis_m2": 0.0,
      "grindjuosciu_m": 0.0,
      "_komentaras": "bbox_pct - patalpos koordinates kaip procentas nuo puslapio (0.0-1.0)"
    }
  ],
  "durys": [{"plotis_mm": 0, "aukstis_mm": 0, "tipas": "standart"}],
  "langai": [{"plotis_mm": 0, "aukstis_mm": 0, "gkp_angokrastis": false, "stoglangis": false}],
  "nisos": [{"ilgis_m": 0.0}],
  "santrauka": {
    "dazymo_plotas_total_m2": 0.0,
    "kampai_m_total": 0.0,
    "angokrasciu_gkp_m_total": 0.0,
    "pasleptu_duru_staktu_m_total": 0.0,
    "nisu_metrai_total": 0.0,
    "gkp_lubu_m2_total": 0.0,
    "gkp_lubu_virs_3m_m2_total": 0.0,
    "pvc_grindys_m2_total": 0.0,
    "plyteles_grindys_m2_total": 0.0,
    "plyteles_sienos_m2_total": 0.0,
    "isliginamasis_m2_total": 0.0,
    "grindjuosciu_m_total": 0.0,
    "hidroizoliacijos_vnt": 0
  },
  "pastabos": "..."
}

SVARBU:
- Per kiekvieną patalpą — TIKSLŪS skaičiai (ne aproksimacija)
- Σ santrauka turi atitikti per-patalpą sumavimą
- Jei matmenys neaiškūs — naudok mažiausią/saugiausią vertę
- Vonios sienų plytelės iki 2.0m default (jei brėžinyje nematyti kito aukščio)
"""


def _call_opus_v7(pages: list[dict]) -> dict[str, Any]:
    """Vienas Vision call'as su detaliu prompt'u."""
    client = _get_client()

    content: list[dict] = [{"type": "text", "text": USER_PROMPT}]
    for page in pages:
        b64 = page.get("image_b64", "")
        if not b64:
            continue
        try:
            b64 = _resize_b64(b64, max_dim=IMAGE_MAX_DIM, quality=85)
        except Exception:
            pass
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=VISION_MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            text_out = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            )
            cleaned = _clean_json_text(text_out)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as je:
                # Bandymas pataisyti — Vision kartais grąžina JS-style objects
                # su `key:` (be kabučių). Pridedam kabutes apie raktus.
                try:
                    import re as _re
                    fixed = _re.sub(
                        r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                        r'\1"\2":',
                        cleaned,
                    )
                    # Pataisom trailing commas
                    fixed = _re.sub(r',(\s*[}\]])', r'\1', fixed)
                    parsed = json.loads(fixed)
                    parsed["_repaired"] = True
                except json.JSONDecodeError:
                    return {"_parse_error": str(je), "_raw_text": text_out[:4000]}
            parsed["_usage"] = {
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
            }
            return parsed
        except Exception as exc:
            last_err = exc
            if attempt == 2:
                raise
            time.sleep(1.5 ** attempt)
    raise last_err or RuntimeError("Opus call failed")


def _select_best_pages(
    pdf_bytes: bytes,
    max_pages: int = 20,
    page_filter: list[int] | None = None,
) -> list[dict]:
    """Atrinkti svarbius brėžinio puslapius.

    Jei `page_filter` pateiktas (1-indexed psl. numeriai) — paima TIK juos.
    Tai naudojama kai page_classifier (V8) jau identifikavo floor_plan +
    specification + wall_elevation + ceiling_plan puslapius — Vision'ui
    duodam fokusuotą rinkinį, ne pirmus 8 atsitiktinius.

    Jei `page_filter` nėra — fallback: pirmi `max_pages` puslapiai.
    """
    all_pages = _pdf_to_pages("input.pdf", pdf_bytes)
    if not page_filter:
        return all_pages[:max_pages]

    # page_filter 1-indexed; _pdf_to_pages list is 0-indexed
    filter_set = {int(p) for p in page_filter if isinstance(p, int)}
    selected = []
    for i, page in enumerate(all_pages, start=1):
        if i in filter_set:
            selected.append(page)
        if len(selected) >= max_pages:
            break

    # Fallback: jei filter nieko neradusio — naudoti pirmus max_pages
    if not selected:
        return all_pages[:max_pages]
    return selected


def extract_v7(pdf_bytes: bytes,
                rangovo_profilis: dict | None = None,
                enable_self_validation: bool = True,
                page_filter: list[int] | None = None,
                max_pages: int = 20) -> dict[str, Any]:
    """V7 entry point: AI Vision atlieka pilną darbą.

    Args:
        pdf_bytes: PDF bytes
        rangovo_profilis: vartotojo Setup Wizard prefs
        enable_self_validation: ar paleisti 2-step validation (Sprint 2 D2)
        page_filter: 1-indexed psl. numeriai (iš page_classifier — floor_plan
                     + specification + wall_elevation + ceiling). Jei None —
                     ima pirmus max_pages.
        max_pages: max kiek psl. siųsti Vision'ui (default 20).
    """
    pages = _select_best_pages(pdf_bytes, max_pages=max_pages, page_filter=page_filter)
    if not pages:
        return {"status": "error", "error": "Nepavyko atrinkti puslapių"}

    t0 = time.time()
    parsed = _call_opus_v7(pages)
    elapsed = time.time() - t0

    if "_parse_error" in parsed:
        return {
            "status": "error",
            "error": f"Vision JSON parse error: {parsed['_parse_error']}",
            "raw_text": parsed.get("_raw_text", "")[:2000],
        }

    parsed.setdefault("patalpos", [])
    parsed.setdefault("durys", [])
    parsed.setdefault("langai", [])
    parsed.setdefault("nisos", [])
    parsed.setdefault("santrauka", {})

    # Sanity: ar santrauka sutampa su per-patalpą sumavimu?
    per_room_dazymo = sum(p.get("dazymo_plotas_m2", 0) or 0
                          for p in parsed["patalpos"])
    santrauka_dazymo = parsed["santrauka"].get("dazymo_plotas_total_m2", 0)
    sanity_warnings = []
    if abs(per_room_dazymo - santrauka_dazymo) > 5:
        sanity_warnings.append({
            "level": "INFO",
            "message": (f"Santrauka ({santrauka_dazymo:.1f}m²) skiriasi nuo "
                        f"per-kambarį sumavimo ({per_room_dazymo:.1f}m²). "
                        f"Naudosim per-kambarį sumavimą."),
        })

    # Sprint 2 D2: Self-validation 2-step (Vision peržiūri savo rezultatus)
    if enable_self_validation and parsed.get("patalpos"):
        try:
            from interior_v8.vision_self_validation import (
                build_validation_prompt, merge_validation_result,
            )
            t1 = time.time()
            validation_prompt = build_validation_prompt(parsed["patalpos"])
            # Sukursime mažą call'ą BE images — tik tekstinis review
            client = _get_client()
            v_resp = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": validation_prompt}],
                }],
            )
            v_text = "".join(
                b.text for b in v_resp.content if getattr(b, "type", None) == "text"
            )
            v_cleaned = _clean_json_text(v_text)
            try:
                v_parsed = json.loads(v_cleaned)
                # Auto-repair jei sugadintas
            except json.JSONDecodeError:
                import re as _re
                v_fixed = _re.sub(
                    r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
                    r'\1"\2":', v_cleaned,
                )
                v_fixed = _re.sub(r',(\s*[}\]])', r'\1', v_fixed)
                try:
                    v_parsed = json.loads(v_fixed)
                except Exception:
                    v_parsed = None

            if v_parsed and "patalpos" in v_parsed:
                parsed = merge_validation_result(parsed, v_parsed)
                pataisymai = v_parsed.get("_pataisymai", [])
                if pataisymai:
                    sanity_warnings.append({
                        "level": "INFO",
                        "message": (f"AI peržiūrėjo savo rezultatus ir pataisė "
                                    f"{len(pataisymai)} dalykus. Žr. _validation_pataisymai."),
                    })
                print(f"[V7] Self-validation: {len(pataisymai)} pataisymai "
                      f"(per {time.time() - t1:.1f}s)")
        except Exception as e:
            print(f"[V7] Self-validation failed: {e}")
            # Nepertraukiam pipeline'ą — original result lieka

    parsed["status"] = "ok"
    parsed["_elapsed_s"] = round(elapsed, 1)
    parsed["_sanity_warnings"] = sanity_warnings
    return parsed

"""
V8 Page Classifier — atpažįsta brėžinio puslapio tipą iš teksto.

Tipai (LT brėžiniai):
- floor_plan: aukšto / pertvarų / baldų planas
- ceiling_plan: lubų / apšvietimo planas
- wall_elevation: sienų išklotinės
- facade: fasadai / iš išorės
- section: pjūvis
- electrical: rozečių / elektros / apšvietimo planas
- plumbing: santechnikos / vandentiekio planas
- specification: specifikacija / žiniaraštis
- title: titulinis lapas
- unknown: nepavyksta klasifikuoti

Strategija:
1. Ekstrahuojam tekstą iš puslapio (pdfplumber)
2. Ieškom keyword'ų antraštės plokštelėje (paprastai apačioje)
3. Klasifikuojame pagal pirmą rastą atitikmenį
4. Confidence: high (rasta tipinis pavadinimas), medium (rasta tikriausiai),
   low (nieko nerasta — fallback unknown)
"""
from __future__ import annotations
import re
from typing import Any


# Keyword'ai per kiekvieną tipą (prioriteto tvarka — pirmasis match wins)
PAGE_TYPE_KEYWORDS = [
    # Specifikacija (turi būti pirma — gali turėti "planas" žodį pavadinime)
    ("specification", [
        "specifikacija", "žiniaraštis", "ziniarastis", "kiekių žiniaraštis",
        "darbų žiniaraštis", "duru specifikacija", "langu specifikacija",
        "apdailos specifikacija",
    ]),
    # Lubų / apšvietimo
    ("ceiling_plan", [
        "lubų planas", "lubu planas", "reflected ceiling", "lubų aukščių",
        "lubu aukstis", "lubų plotai", "apšvietimo planas", "apsvietimo planas",
        "lubų brėžinys", "lubu brezinys",
    ]),
    # Sienų išklotinės
    ("wall_elevation", [
        "sienų išklotinė", "sienu isklotine", "sienų išklotinės", "sienu isklotines",
        "išklotinė", "isklotine", "wall elevation", "interior elevation",
    ]),
    # Fasadas
    ("facade", [
        "fasadas", "fasadai", "fasadų", "fasadu", "elevation", "fronton",
        "rytinis fasadas", "vakarinis fasadas", "šiaurinis fasadas",
        "siaurinis fasadas", "pietinis fasadas",
    ]),
    # Pjūvis
    ("section", [
        "pjūvis", "pjuvis", "pjūviai", "pjuviai", "section", "išilginis pjūvis",
        "skersinis pjūvis", "isilginis pjuvis", "skersinis pjuvis",
    ]),
    # Elektros / rozečių
    ("electrical", [
        "rozečių planas", "roeciu planas", "roziciu planas", "elektros planas",
        "apšvietimo schema", "apsvietimo schema", "rozeciu", "roziciu",
        "elektrotechnika", "silpnos srovės",
    ]),
    # Santechnika
    ("plumbing", [
        "santechnikos", "vandentiekio", "kanalizacijos planas",
        "ventiliacijos", "rekuperacijos planas",
    ]),
    # Grindų / aukšto / pertvarų / baldų — paskutinis (catch-all)
    ("floor_plan", [
        "aukšto planas", "auksto planas", "pertvarų planas", "pertvaru planas",
        "baldų planas", "baldu planas", "grindų planas", "grindu planas",
        "pirmojo aukšto", "pirmo aukšto", "antro aukšto", "antrojo aukšto",
        "rūsio planas", "rusio planas", "mansardos planas",
        "floor plan", "1 a.", "2 a.", "1a", "2a",
    ]),
    # Tituliniai
    ("title", [
        "titulinis lapas", "titulinis", "title page", "antraštė",
        "antrastine plokstele", "antraštinė plokštelė",
    ]),
]


# Patalpų pavadinimų indikatoriai (specializacija ceiling vs floor)
CEILING_INDICATORS = [
    "+2820", "+2650", "+2400", "+2750",  # Lubų aukščio žymėjimai
    "h=2", "h=3", "h-2", "h-3",
    "led juosta", "uzuolaidu nisa", "užuolaidų niša",
    "gkp lubos", "pakabinamos lubos",
]

FLOOR_INDICATORS = [
    "plotas", "m²", "m2", "ploto",
]


def normalize(s: str) -> str:
    """Norm tekstą — lower, suvienodina diakritiką."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.lower()).strip()


def classify_page(page_text: str) -> dict:
    """Klasifikuoja vieną puslapį iš jo teksto.

    Returns:
      {
        "type": "floor_plan" | ... | "unknown",
        "confidence": "high" | "medium" | "low",
        "matched_keywords": [...],
        "label": "Žmonėms skaitomas pavadinimas",
      }
    """
    n_text = normalize(page_text)
    if not n_text or len(n_text) < 10:
        return {
            "type": "unknown",
            "confidence": "low",
            "matched_keywords": [],
            "label": "Nežinomas",
        }

    matched_keywords = []
    matched_type = None

    # Pirma — patys konkretūs (specifikacija, lubų, sienų išklotinė)
    for ptype, keywords in PAGE_TYPE_KEYWORDS:
        for kw in keywords:
            if kw.lower() in n_text:
                matched_keywords.append(kw)
                if not matched_type:
                    matched_type = ptype

    # Jei nieko nerasta — bandom indikatorius
    if not matched_type:
        ceiling_hints = sum(1 for ind in CEILING_INDICATORS if ind in n_text)
        floor_hints = sum(1 for ind in FLOOR_INDICATORS if ind in n_text)

        if ceiling_hints >= 2:
            matched_type = "ceiling_plan"
            matched_keywords.append(f"<{ceiling_hints} ceiling indicators>")
        elif floor_hints >= 2:
            matched_type = "floor_plan"
            matched_keywords.append(f"<{floor_hints} floor indicators>")
        else:
            return {
                "type": "unknown",
                "confidence": "low",
                "matched_keywords": [],
                "label": "Nežinomas",
            }

    # Confidence: high jei direct match, medium jei iš indikatorių
    confidence = "high" if matched_keywords and not matched_keywords[0].startswith("<") else "medium"

    LABELS = {
        "floor_plan": "Grindų / aukšto planas",
        "ceiling_plan": "Lubų / apšvietimo planas",
        "wall_elevation": "Sienų išklotinė",
        "facade": "Fasadas",
        "section": "Pjūvis",
        "electrical": "Elektros planas",
        "plumbing": "Santechnikos planas",
        "specification": "Specifikacija",
        "title": "Titulinis lapas",
        "unknown": "Nežinomas",
    }

    return {
        "type": matched_type,
        "confidence": confidence,
        "matched_keywords": matched_keywords[:3],
        "label": LABELS.get(matched_type, matched_type),
    }


def classify_pdf(pdf_bytes: bytes) -> list[dict]:
    """Klasifikuoja kiekvieną PDF puslapį.

    Returns: list of {page, type, confidence, label, matched_keywords}
    """
    try:
        import pdfplumber
        import io
    except ImportError:
        return []

    results = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                cls = classify_page(text)
                cls["page"] = i
                cls["text_length"] = len(text)
                results.append(cls)
    except Exception as e:
        print(f"[page_classifier] Klaida: {e}")
        return []

    return results


def summarize(classifications: list[dict]) -> dict:
    """Sumarizuoja kuriuos puslapius reikia atskirai analizuoti.

    Returns:
      {
        "total_pages": int,
        "by_type": {type: [page_nrs]},
        "ceiling_pages": [...],     # specialaus dėmesio reikia
        "wall_elevations": [...],
        "floor_plans": [...],
        "specs": [...],
      }
    """
    by_type = {}
    for c in classifications:
        t = c.get("type", "unknown")
        by_type.setdefault(t, []).append(c["page"])

    return {
        "total_pages": len(classifications),
        "by_type": by_type,
        "ceiling_pages": by_type.get("ceiling_plan", []),
        "wall_elevations": by_type.get("wall_elevation", []),
        "floor_plans": by_type.get("floor_plan", []),
        "facades": by_type.get("facade", []),
        "sections": by_type.get("section", []),
        "electrical": by_type.get("electrical", []),
        "plumbing": by_type.get("plumbing", []),
        "specs": by_type.get("specification", []),
        "unknown_pages": by_type.get("unknown", []),
    }

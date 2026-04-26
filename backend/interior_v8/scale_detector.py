"""
V8 Scale Detector — automatiškai aptinka brėžinio mastelį iš PDF.

3 nepriklausomi metodai (paleidžiame visus, sutariamą rezultatą laikome
patikimu — voting):

1. **Tekstinis žymeklis** — ieškome "M 1:50", "Skala 1:50", "Mastelis 1:50"
2. **Dimensijų užrašai** — "3450" tipo skaičius ant linijos. Jei žinome
   linijos ilgį pikseliais, gauname mm/pixel mastelį.
3. **Sanity check** — žinom, kad gyvenamoji patalpa LT vidutiniškai 12–30m².
   Jei aptiktas plotas iš dažnai naudotų masteliu (1:50, 1:100, 1:200) duoda
   logiškas reikšmes — patvirtinam.

Output:
{
  "scale_ratio": 50,           # 1:50 = 50
  "mm_per_unit": 50.0,         # arba 100, 200, 25
  "confidence": "high|medium|low",
  "source": "text|dimensions|sanity|fallback",
  "warnings": [...],
}
"""
from __future__ import annotations
import re
from typing import Any

# Tipiniai LT/EU brėžinių masteliai
COMMON_SCALES = [25, 50, 75, 100, 150, 200, 250, 500]


# ─────────────────────────────────────────────────────────────────────
# 1. Tekstinis mastelio žymeklis
# ─────────────────────────────────────────────────────────────────────

# Patternai per LT/EU/RU/EN brėžinius
SCALE_PATTERNS = [
    # M 1:50, M1:50, M 1: 50
    re.compile(r"\bM\s*[: ]\s*1\s*[: ]\s*(\d{1,4})\b", re.IGNORECASE),
    # Mastelis 1:50, Skala 1:50, Scale 1:50
    re.compile(r"(?:mastelis|skala|scale|massstab|maßstab)\s*[: ]?\s*1\s*[: ]\s*(\d{1,4})\b", re.IGNORECASE),
    # 1:50 atskirai (riskingiau — gali būti datų ar kitų santykių)
    re.compile(r"(?<![/\d])1\s*:\s*(\d{1,4})(?!\d)"),
]


def detect_scale_from_text(text: str) -> dict | None:
    """Ieškom mastelio per tekstinius žymeklius PDF tekste.

    Grąžinam pirmą tikėtiną radinį (validuojam su COMMON_SCALES kai įmanoma).
    """
    if not text:
        return None

    candidates = []
    for pattern in SCALE_PATTERNS:
        for m in pattern.finditer(text):
            try:
                ratio = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if 10 <= ratio <= 1000:
                candidates.append((ratio, m.start()))

    if not candidates:
        return None

    # Pirmenybė COMMON_SCALES
    common = [c for c in candidates if c[0] in COMMON_SCALES]
    if common:
        ratio = common[0][0]
        confidence = "high"
    else:
        ratio = candidates[0][0]
        confidence = "medium"

    return {
        "scale_ratio": ratio,
        "mm_per_unit": float(ratio),
        "confidence": confidence,
        "source": "text",
        "match_count": len(candidates),
    }


# ─────────────────────────────────────────────────────────────────────
# 2. Dimensijų užrašai (vector PDF)
# ─────────────────────────────────────────────────────────────────────

# Dimensijos pattern: skaičiai 100–10000mm range
DIMENSION_PATTERN = re.compile(r"\b(\d{2,5})\b")
# Decimaliniai (3.45m formatu)
DIMENSION_DECIMAL = re.compile(r"\b(\d{1,2})[.,](\d{1,3})\s*m?\b")


def detect_scale_from_dimensions(pdf_path: str | bytes) -> dict | None:
    """Iš PDF vector layer'io ekstrahuoja dimensijos užrašus prie linijų,
    palygina su pikselių/PDF unitų ilgiu, gauname mastelį.

    PDF coordinate space: 1 unit = 1/72 inch ≈ 0.353mm.
    Tikrasis mastelis 1:50 reiškia, kad 1mm popieriuje = 50mm realybėje.
    Todėl nuo PDF unitų gauti realius mm = (pdf_unit / 72 * 25.4) * scale.
    """
    try:
        import pdfplumber
    except ImportError:
        return None

    try:
        if isinstance(pdf_path, bytes):
            import io
            pdf = pdfplumber.open(io.BytesIO(pdf_path))
        else:
            pdf = pdfplumber.open(pdf_path)
    except Exception:
        return None

    candidates: list[float] = []  # collected mm-per-pdfunit ratios

    try:
        for page in pdf.pages[:10]:  # tik pirmieji 10 puslapių
            words = page.extract_words() or []
            lines = page.lines or []

            if not words or not lines:
                continue

            for word in words:
                text = (word.get("text") or "").strip()
                if not text:
                    continue

                # Bandom decimal'us pirma (3.45m)
                m = DIMENSION_DECIMAL.match(text)
                if m:
                    try:
                        whole = int(m.group(1))
                        frac = m.group(2)
                        real_mm = (whole + int(frac) / 10**len(frac)) * 1000
                    except (ValueError, IndexError):
                        continue
                else:
                    m2 = DIMENSION_PATTERN.match(text)
                    if not m2:
                        continue
                    try:
                        val = int(m2.group(1))
                    except (ValueError, IndexError):
                        continue
                    # Filtras: tipiniai LT brėžinių dimensijos 500-15000mm
                    if val < 500 or val > 15000:
                        continue
                    real_mm = float(val)

                # Žodžio centras
                wx = (word["x0"] + word["x1"]) / 2
                wy = (word["top"] + word["bottom"]) / 2

                # Surask artimiausią liniją
                closest_line = None
                closest_dist = float("inf")
                for ln in lines:
                    if not all(k in ln for k in ("x0", "x1", "top", "bottom")):
                        continue
                    cx = (ln["x0"] + ln["x1"]) / 2
                    cy = (ln["top"] + ln["bottom"]) / 2
                    d = ((cx - wx) ** 2 + (cy - wy) ** 2) ** 0.5
                    if d < closest_dist:
                        closest_dist = d
                        closest_line = ln

                if not closest_line or closest_dist > 50:
                    continue

                # Linijos ilgis PDF unitais
                lx = closest_line["x1"] - closest_line["x0"]
                ly = closest_line["bottom"] - closest_line["top"]
                pdf_len = (lx * lx + ly * ly) ** 0.5

                if pdf_len < 5:
                    continue

                # mm per PDF unitą
                mm_per_unit = real_mm / pdf_len

                # Validacija: Tipinis 1:50 mastelis — 1mm popier × 50 = 50mm.
                # PDF unitas ≈ 0.353mm. Tai 0.353 × 50 = 17.6 mm/unit.
                # Tipiniai range: 8 (1:25) iki 70 (1:200).
                if 5 <= mm_per_unit <= 200:
                    candidates.append(mm_per_unit)
    finally:
        pdf.close()

    if len(candidates) < 3:
        return None

    # Median (atsparesnis nei mean)
    candidates.sort()
    median = candidates[len(candidates) // 2]

    # Kuris bendrinis mastelis arčiausiai?
    pdf_unit_mm = 25.4 / 72  # ≈ 0.353
    expected_per_scale = {s: pdf_unit_mm * s for s in COMMON_SCALES}
    closest_scale = min(
        expected_per_scale.items(),
        key=lambda kv: abs(kv[1] - median),
    )
    diff_pct = abs(closest_scale[1] - median) / closest_scale[1]

    if diff_pct < 0.15:  # 15% accuracy
        confidence = "high"
    elif diff_pct < 0.30:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "scale_ratio": closest_scale[0],
        "mm_per_unit": median,
        "expected_for_ratio": closest_scale[1],
        "confidence": confidence,
        "source": "dimensions",
        "match_count": len(candidates),
    }


# ─────────────────────────────────────────────────────────────────────
# 3. Sanity check (žinome tipinius LT būsto plotus)
# ─────────────────────────────────────────────────────────────────────

# LT būsto/komercinių patalpų realistiniai range'ai (m²)
ROOM_AREA_RANGES = {
    "gyvenamoji":  (8, 60),
    "miegamoji":   (8, 30),
    "valgomasis":  (10, 30),
    "virtuve":     (5, 25),
    "vonia":       (3, 15),
    "wc":          (1, 6),
    "san":         (3, 12),
    "koridorius":  (2, 30),
    "holas":       (5, 50),
    "drabuzine":   (1.5, 15),
    "rubine":      (2, 20),
    "katiline":    (3, 15),
    "skalbykla":   (2, 10),
    "tambūras":    (1.5, 10),
    "garazas":     (12, 50),
    "sandeliukas": (1, 10),
    "sandėliukas": (1, 10),
}


def validate_scale_via_sanity(rooms: list[dict]) -> dict:
    """Patikrinam ar aptikti plotai logiški pagal LT būsto realumą.

    Grąžina:
      {
        "logical": True/False,
        "warnings": [...],
        "anomaly_count": int,
        "suggested_correction": float or None,  # mastelio daugiklis
      }
    """
    warnings = []
    anomalies = 0
    multipliers = []  # jei aptiktas plotas yra 4× per mažas, mastelis blogai

    for r in rooms:
        paskirtis = r.get("paskirtis", "gyvenamoji")
        plotas = r.get("plotas_m2") or 0
        if plotas <= 0:
            continue

        rng = ROOM_AREA_RANGES.get(paskirtis, (5, 80))
        lo, hi = rng

        if plotas < lo:
            ratio = lo / plotas if plotas > 0 else 1
            warnings.append({
                "level": "WARNING",
                "patalpa": r.get("pavadinimas"),
                "plotas_m2": plotas,
                "tikejosi": rng,
                "message": f"{r.get('pavadinimas', '?')}: {plotas} m² per mažas {paskirtis} patalpai (norma {lo}–{hi} m²)",
            })
            anomalies += 1
            # Galimas mastelio multiplier
            if 1.5 <= ratio <= 16:
                multipliers.append(ratio ** 0.5)  # mastelis kvadratuojasi į plotą

        elif plotas > hi:
            ratio = plotas / hi
            warnings.append({
                "level": "WARNING",
                "patalpa": r.get("pavadinimas"),
                "plotas_m2": plotas,
                "tikejosi": rng,
                "message": f"{r.get('pavadinimas', '?')}: {plotas} m² per didelis {paskirtis} patalpai (norma {lo}–{hi} m²)",
            })
            anomalies += 1
            if 1.5 <= ratio <= 16:
                multipliers.append(1 / (ratio ** 0.5))

    n = len(rooms)
    anomaly_pct = anomalies / n if n > 0 else 0

    # Jei daugiau kaip 50% patalpų abnormalūs — mastelis blogai
    suggested_mult = None
    if multipliers and anomaly_pct > 0.5:
        # median multiplier
        multipliers.sort()
        suggested_mult = multipliers[len(multipliers) // 2]

    return {
        "logical": anomaly_pct <= 0.3,
        "warnings": warnings,
        "anomaly_count": anomalies,
        "anomaly_pct": round(anomaly_pct * 100, 1),
        "suggested_scale_multiplier": suggested_mult,
    }


# ─────────────────────────────────────────────────────────────────────
# Voting: sutariam tarp 3 metodų
# ─────────────────────────────────────────────────────────────────────

def auto_detect_scale(pdf_bytes: bytes,
                       pdf_text: str = "",
                       rooms: list[dict] | None = None) -> dict:
    """Pagrindinis entry point — paleidžia visus 3 metodus, sujungia rezultatą.

    Args:
        pdf_bytes: PDF failo bytes
        pdf_text: ekstrahuotas tekstas iš PDF (greičiau jei jau turima)
        rooms: jau ekstrahuotos patalpos su plotais (sanity check'ui)

    Returns:
        {
          "scale_ratio": int (1:50 = 50),
          "confidence": "high|medium|low",
          "source": str,
          "votes": [{...}, ...],
          "warnings": [...],
        }
    """
    votes = []
    warnings = []

    # 1. Tekstinis
    if pdf_text:
        text_result = detect_scale_from_text(pdf_text)
        if text_result:
            votes.append(text_result)

    # 2. Dimensijos (jei nėra teksto, arba jei text low confidence)
    dim_result = detect_scale_from_dimensions(pdf_bytes)
    if dim_result:
        votes.append(dim_result)

    # 3. Sanity check
    sanity_result = None
    if rooms:
        sanity_result = validate_scale_via_sanity(rooms)
        warnings.extend(sanity_result.get("warnings", []))

    # Pasirinkimas:
    # - Jei text + dim sutampa → high confidence
    # - Jei tik vienas → vidutinis
    # - Jei sanity rodo problemas → perspėjimas
    if not votes:
        return {
            "scale_ratio": 50,  # default LT mastelis
            "mm_per_unit": 50.0,
            "confidence": "low",
            "source": "fallback",
            "votes": [],
            "warnings": ["Mastelis nerastas — naudojam default 1:50"],
            "sanity": sanity_result,
        }

    # Voting
    high_votes = [v for v in votes if v["confidence"] == "high"]
    if high_votes:
        chosen = high_votes[0]
        # Patikrinam, ar visi sutaria
        ratios = {v["scale_ratio"] for v in high_votes}
        if len(ratios) == 1:
            chosen["confidence"] = "high"
            chosen["source"] = "+".join(v["source"] for v in high_votes)
        else:
            chosen["confidence"] = "medium"
            warnings.append(f"Mastelio metodai nesutaria: {ratios}")
    else:
        # Pirmas medium
        chosen = votes[0]

    # Sanity sumažina confidence
    if sanity_result and not sanity_result["logical"]:
        chosen["confidence"] = "low"
        warnings.append(
            f"Plotai atrodo nelogiški ({sanity_result['anomaly_pct']}% anomalijų)"
        )
        if sanity_result.get("suggested_scale_multiplier"):
            mult = sanity_result["suggested_scale_multiplier"]
            warnings.append(
                f"Galimas mastelio daugiklis: ×{mult:.2f}"
            )

    return {
        "scale_ratio": chosen["scale_ratio"],
        "mm_per_unit": chosen.get("mm_per_unit", float(chosen["scale_ratio"])),
        "confidence": chosen["confidence"],
        "source": chosen["source"],
        "votes": votes,
        "warnings": warnings,
        "sanity": sanity_result,
    }

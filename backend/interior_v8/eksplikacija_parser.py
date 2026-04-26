"""
Eksplikacijos lentelės parser — V6 Tier 1 logika atstatyta.

Iš PDF teksto suranda PATALPŲ EKSPLIKACIJOS lentelę ir parse'ina
patalpas su tiksliais plotais. Tai 95%+ TIKSLUS šaltinis kambariui +
plotui, lyginant su Vision (kuris gali klysti).

Format'ai (LT projektuose pasitaiko):
  P1 stilius: "01 TAMBŪRAS 7,36 M²" (kablelis, M² suffix, 2-digit)
  P3 stilius: "1 HOLAS 11.55" (taškas, be suffixo, 1-digit)
  Multi-word: "02 SVETAINĖ/VALGOMASIS/VIRTUVĖ 62,42 M²"
  Su tašku: "04 SAN. MAZGAS 4.1"
"""
from __future__ import annotations
import io
import re
from typing import Any


# Žinomi LT patalpų kambario žodžių prefiksai (kad atskirti nuo kitų skaičių)
KNOWN_ROOM_KEYWORDS = {
    "tambūras", "tamburas", "svetainė", "svetaine", "valgomasis", "virtuvė",
    "virtuve", "miegamasis", "miegamoji", "miegamoji", "vonia", "wc",
    "tualetas", "san", "san.", "mazgas", "koridorius", "holas", "kambarys",
    "drabužinė", "drabuzine", "garderob", "sandėliukas", "sandeliuk",
    "garažas", "garazas", "katilinė", "katiline", "skalbykla", "lodžija",
    "balkonas", "terasa", "kabinetas", "biuras", "patalpa", "rūsys", "rusys",
}

# Paskirties mapping pagal pavadinimą
def _infer_paskirtis(pavadinimas: str) -> str:
    p = pavadinimas.lower()
    if any(x in p for x in ("vonia", "vonios")):
        return "vonia"
    if "wc" in p or "tualet" in p:
        return "wc"
    if "san." in p or "san " in p or "mazgas" in p:
        return "san"
    if any(x in p for x in ("virtuv",)):
        return "virtuve"
    if any(x in p for x in ("valgom",)):
        return "valgomasis"
    if "miegam" in p or "kambar" in p:
        return "miegamoji"
    if any(x in p for x in ("svetain",)):
        return "gyvenamoji"
    if "korid" in p or "hol" in p or "prieskambar" in p:
        return "koridorius"
    if "drabuz" in p or "drabuž" in p or "garderob" in p:
        return "drabuzine"
    if "sandel" in p or "sandėl" in p:
        return "sandeliukas"
    if "tambūr" in p or "tambur" in p:
        return "tambūras"
    if "garaž" in p or "garaz" in p:
        return "garazas"
    if "katiln" in p or "katilin" in p:
        return "katiline"
    if "skalbyk" in p:
        return "skalbykla"
    return "gyvenamoji"


# Regex pattern: NR (1-3 skaitmenų) + NAME (didelės/mažos LT raidės, /, ., space) + AREA (skaičius su . arba ,)
# Modifikatoriai:
# - NR: 1-3 skaitmenys, gali būti su 0 (01, 02)
# - NAME: bent 1 raidė + iki 30 chars (žodis/žodžiai)
# - AREA: 1-4 sveikieji + . ar , + 1-3 dešimtainiai
_ROOM_ROW_RE = re.compile(
    r"\b(\d{1,3})\s+"                                        # NR
    r"([A-ZĄČĘĖĮŠŲŪŽa-ząčęėįšųūž][A-ZĄČĘĖĮŠŲŪŽa-ząčęėįšųūž\.\s/\-]{2,40}?)"  # NAME (non-greedy)
    r"\s+(\d{1,4}[\.,]\d{1,3})"                              # AREA
    r"(?:\s*[Mm][²2])?",                                     # optional M² suffix
    re.UNICODE,
)


def _normalize_area(s: str) -> float | None:
    """„7,36" → 7.36, „11.55" → 11.55."""
    try:
        return float(s.replace(",", "."))
    except (ValueError, TypeError):
        return None


def _is_likely_room_name(name: str) -> bool:
    """Filtras: ar tai panašu į patalpos pavadinimą?"""
    n = name.strip().lower()
    if len(n) < 3:
        return False
    # Bent vienas LT kambario žodis turi būti
    if any(kw in n for kw in KNOWN_ROOM_KEYWORDS):
        return True
    # Arba tai didžiosios raidės pavadinimas (HOLAS, KORIDORIUS, ...)
    if name.isupper() and len(n) >= 4:
        return True
    return False


def parse_eksplikacija_text(text: str) -> list[dict]:
    """Iš PDF teksto suranda eksplikacijos lentelę, grąžina patalpų sąrašą.

    Args:
        text: Pilnas PDF puslapio (-ių) tekstas

    Returns:
        [{nr, pavadinimas, plotas_m2, paskirtis}] — surasti kambariai
    """
    if not text:
        return []
    upper = text.upper()
    if "EKSPLIK" not in upper:
        return []

    # Imam tekstą nuo "EKSPLIKACIJA" iki teksto pabaigos arba kito header'io
    idx = upper.find("EKSPLIK")
    chunk = text[idx:idx + 4000]

    # Paliekame tik dalį iki pirmo „BENDR" / "PASTAB" / "BRĖŽINI" — tai
    # signaluoja kad eksplikacija pasibaigė
    end_markers = ["BENDR", "PASTAB", "BRĖŽINI", "BREZINI", "ZONOS", "LEGEND"]
    end_idx = len(chunk)
    for marker in end_markers:
        m_idx = chunk.upper().find(marker, 30)  # +30 kad neprariktų pačios EKSPLIKACIJA
        if 0 < m_idx < end_idx:
            end_idx = m_idx
    chunk = chunk[:end_idx]

    rooms: list[dict] = []
    seen_nrs: set[int] = set()

    for m in _ROOM_ROW_RE.finditer(chunk):
        try:
            nr = int(m.group(1))
            name = m.group(2).strip().rstrip(".")
            area_str = m.group(3)
            area = _normalize_area(area_str)
        except (ValueError, IndexError):
            continue

        if area is None or area <= 0 or area > 500:
            continue
        if not _is_likely_room_name(name):
            continue
        if nr in seen_nrs:
            continue  # vengti dublikavimo
        # Patalpos paprastai 1-50 nr
        if nr < 1 or nr > 99:
            continue
        seen_nrs.add(nr)
        rooms.append({
            "nr": nr,
            "pavadinimas": name.title() if name.isupper() else name,
            "plotas_m2": area,
            "paskirtis": _infer_paskirtis(name),
            "_source": "eksplikacija_text",
        })

    # Sortuojame pagal nr
    rooms.sort(key=lambda r: r["nr"])
    return rooms


def extract_eksplikacija_from_pdf(pdf_bytes: bytes,
                                    max_pages: int = 5) -> list[dict]:
    """Iš PDF bytes suranda eksplikacijos lentelę per visus puslapius.

    Args:
        pdf_bytes: PDF
        max_pages: ribojam analizę (perf)

    Returns:
        [{nr, pavadinimas, plotas_m2, paskirtis, page_nr}]
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    rooms: list[dict] = []
    seen_keys: set[tuple] = set()

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages[:max_pages], start=1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    continue
                if "EKSPLIK" not in text.upper():
                    continue

                page_rooms = parse_eksplikacija_text(text)
                for r in page_rooms:
                    key = (r["nr"], r["pavadinimas"].lower())
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    r["page_nr"] = page_idx
                    rooms.append(r)
    except Exception as e:
        print(f"[eksplikacija] pdf parse error: {e}")
        return []

    rooms.sort(key=lambda r: r["nr"])
    return rooms

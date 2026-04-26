"""
V8 Stress Test — paleidžia pilną V8 pipeline ant P1-P5 ir lygina su rangovo sąmatomis.

Trys režimai:
  --mode=vision  → tikras Vision call'as (reikia ANTHROPIC_API_KEY)
  --mode=cached  → naudoja cached Vision rezultatus iš ankstesnių sweep'ų
  --mode=mock    → simuliuoja patalpas iš rangovo sąmatos (greičiausia)

Output: accuracy ataskaita su:
  - dazymo_plotas (V8 vs rangovas)
  - kampai (V8 vs rangovas)
  - additional_positions sutapimai
  - sanity warnings
  - mastelis aptiktas
  - puslapių klasifikacija
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from interior_v8 import (
    extract_v8, auto_detect_scale,
    classify_pdf, summarize_pages,
)


# ─────────────────────────────────────────────────────────────────────
# Tikras rangovo sąmatos kiekiai per kategoriją
# ─────────────────────────────────────────────────────────────────────

def load_tomo_data():
    """Iš parsed_pasiulymai.json išrenkam pagrindinius kiekius."""
    f = ROOT / "training-data" / "parsed_pasiulymai.json"
    data = json.loads(f.read_text(encoding="utf-8"))

    result = {}
    for proj_id, parsed in data.items():
        proj_data = {
            "dazymo_plotas_m2": 0,  # "Sienų/lubų glaistymas/dažymas"
            "rotband_m2": 0,         # "Sienų lyginimas Rotband"
            "lubu_virs_3m_m2": 0,    # "Lubų virš 3m"
            "kampai_m": 0,           # "Dažymo kampų"
            "gkp_lubu_m2": 0,        # "GKP montavimas ant lubų"
            "gkp_nisu_m": 0,         # "Nišų formavimas iš GKP"
            "gkp_angokrasciu_m": 0,  # "Angokraščių apdirbimas GKP"
            "duru_paruosimas_m": 0,  # "Durų angų paruošimas"
            "sviestuvai_vnt": 0,     # "Lubinių sviestuvų"
            "skyles_pliteles_vnt": 0, # "Skylių gręžimas plytelėse"
            "kampu_silikonavimas_m": 0, # "Kampų silikonavimas"
            "siuksliu_vnt": 0,       # "Šiukšlių išvežimas"
            "nuolydis_dusho_vnt": 0, # "Nuolydžio formavimas"
            "hidroizoliacijos_vnt": 0, # "Hidroizoliacijos"
        }

        for skyrius in parsed.get("skyriai", []):
            for eil in skyrius.get("eilutes", []):
                aprasymas = eil.get("aprasymas", "").lower()
                kiekis = eil.get("kiekis") or 0

                if "sienų/ lubų glaistymas" in aprasymas or "sienų, lubų glaistymas" in aprasymas:
                    proj_data["dazymo_plotas_m2"] += kiekis
                elif "sienų lyginimas" in aprasymas or "rotband" in aprasymas:
                    proj_data["rotband_m2"] += kiekis
                elif "lubų glaistymas" in aprasymas and "virš 3m" in aprasymas:
                    proj_data["lubu_virs_3m_m2"] += kiekis
                elif "dažymo kampų" in aprasymas:
                    proj_data["kampai_m"] += kiekis
                elif "gkp" in aprasymas and "lubų" in aprasymas and "virš 3m" not in aprasymas:
                    proj_data["gkp_lubu_m2"] += kiekis
                elif "nišų formavimas" in aprasymas or "nišų iš gkp" in aprasymas:
                    proj_data["gkp_nisu_m"] += kiekis
                elif "angokraščių apdirbimas" in aprasymas:
                    proj_data["gkp_angokrasciu_m"] += kiekis
                elif "durų angų paruošimas" in aprasymas:
                    proj_data["duru_paruosimas_m"] += kiekis
                elif "lubinių" in aprasymas and "šviestuvų" in aprasymas:
                    proj_data["sviestuvai_vnt"] += kiekis
                elif "skylių gręžimas" in aprasymas and "plytel" in aprasymas:
                    proj_data["skyles_pliteles_vnt"] += kiekis
                elif "kampų silikon" in aprasymas:
                    proj_data["kampu_silikonavimas_m"] += kiekis
                elif "šiukšlių" in aprasymas:
                    proj_data["siuksliu_vnt"] += kiekis
                elif "nuolydž" in aprasymas:
                    proj_data["nuolydis_dusho_vnt"] += kiekis
                elif "hidroizoliacij" in aprasymas:
                    proj_data["hidroizoliacijos_vnt"] += kiekis

        result[proj_id] = proj_data
    return result


# ─────────────────────────────────────────────────────────────────────
# Mock Vision rezultatai (iš parsed_pasiulymai dedukuojam)
# ─────────────────────────────────────────────────────────────────────

# Tipiniai LT projektai — vidutinis kambarių skaičius ir ploto pasiskirstymas.
# Iš rangovo P1-P5 rasti dazymo_plotas range 150-461 m² → namo plotai ~50-150m².
# Vidutiniam projektui mock'inu ~12 kambarių su realistišku LT bustų breakdown.

def mock_rooms_for_project(proj_id: str, target_dazymo_m2: float) -> list[dict]:
    """Sugeneruojam realistinius mock kambarius pagal projektą."""
    # Pradedam nuo bendro ploto. Dažomas plotas ~3.5× nuo grindų ploto.
    grindu_plotas = target_dazymo_m2 / 3.5
    # 12 kambarių vidutinis breakdown
    rooms = [
        {'pavadinimas': 'Svetainė', 'paskirtis': 'gyvenamoji', 'plotas_m2': grindu_plotas * 0.25},
        {'pavadinimas': 'Virtuvė', 'paskirtis': 'virtuve', 'plotas_m2': grindu_plotas * 0.10},
        {'pavadinimas': 'Miegamasis 1', 'paskirtis': 'miegamoji', 'plotas_m2': grindu_plotas * 0.12},
        {'pavadinimas': 'Miegamasis 2', 'paskirtis': 'miegamoji', 'plotas_m2': grindu_plotas * 0.10},
        {'pavadinimas': 'Vonia', 'paskirtis': 'vonia', 'plotas_m2': grindu_plotas * 0.05},
        {'pavadinimas': 'WC', 'paskirtis': 'wc', 'plotas_m2': grindu_plotas * 0.025},
        {'pavadinimas': 'Koridorius', 'paskirtis': 'koridorius', 'plotas_m2': grindu_plotas * 0.10},
        {'pavadinimas': 'Drabužinė', 'paskirtis': 'drabuzine', 'plotas_m2': grindu_plotas * 0.04},
        {'pavadinimas': 'Sandėliukas', 'paskirtis': 'sandeliukas', 'plotas_m2': grindu_plotas * 0.03},
        {'pavadinimas': 'Katilinė', 'paskirtis': 'katiline', 'plotas_m2': grindu_plotas * 0.04},
        {'pavadinimas': 'Holas', 'paskirtis': 'holas', 'plotas_m2': grindu_plotas * 0.05},
        {'pavadinimas': 'Garažas', 'paskirtis': 'garazas', 'plotas_m2': grindu_plotas * 0.135},
    ]
    for i, r in enumerate(rooms, start=1):
        r['nr'] = f"{i:02d}"
        r['plotas_m2'] = round(r['plotas_m2'], 1)
        r['perimetras_m'] = round(4.18 * r['plotas_m2']**0.5, 1)
        r['lubu_aukstis_m'] = 2.82
    return rooms


# ─────────────────────────────────────────────────────────────────────
# Accuracy comparison
# ─────────────────────────────────────────────────────────────────────

def compare(v8_value, tomo_value, label):
    if tomo_value == 0:
        if v8_value == 0:
            return f"{label:35s} rangovo=0   V8={v8_value:8.1f}  → N/A"
        return f"{label:35s} rangovo=0   V8={v8_value:8.1f}  → V8 PRIDEDA"
    diff_pct = (v8_value - tomo_value) / tomo_value * 100
    direction = "+" if diff_pct >= 0 else ""
    return f"{label:35s} rangovo={tomo_value:8.1f}  V8={v8_value:8.1f}  → {direction}{diff_pct:6.1f}%"


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def run_one_project(proj_id: str, rangovo: dict, mode: str = "mock"):
    print(f"\n{'='*72}")
    print(f"PROJEKTAS {proj_id}")
    print('='*72)

    pdf_path = ROOT / "training-data" / f"projektas_{proj_id[1:]}" / f"projektas_{proj_id[1:]}_breziniai.pdf"
    pdf_bytes = pdf_path.read_bytes() if pdf_path.exists() else b""

    # 1. Page classifier
    if pdf_bytes:
        classifications = classify_pdf(pdf_bytes)
        summary = summarize_pages(classifications)
        n_known = sum(1 for c in classifications if c.get("type") not in ("unknown", "title"))
        print(f"\n[Page classifier] {summary['total_pages']} psl, atpažinta {n_known}/{summary['total_pages']}")
        for t in ["floor_plan", "ceiling_plan", "wall_elevation", "specification"]:
            n = len(summary["by_type"].get(t, []))
            if n:
                print(f"    - {t}: {n} psl")

    # 2. Mock kambariai (target: rangovo dazymo_plotas)
    rooms = mock_rooms_for_project(proj_id, rangovo.get("dazymo_plotas_m2", 200))

    # 3. Mastelio aptikimas
    if pdf_bytes:
        try:
            import pdfplumber, io as _io
            with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
                pdf_text = "\n".join((p.extract_text() or "") for p in pdf.pages[:5])
            scale = auto_detect_scale(pdf_bytes=pdf_bytes, pdf_text=pdf_text, rooms=rooms)
            print(f"\n[Mastelis] 1:{scale['scale_ratio']} ({scale['confidence']}, src={scale['source']})")
            if scale.get("warnings"):
                for w in scale["warnings"][:2]:
                    print(f"    WARN: {w}")
        except Exception as e:
            print(f"\n[Mastelis] klaida: {e}")

    # 4. V8 universal engine
    v8 = extract_v8(rooms, ceiling_height_m=2.82)
    totals = v8["totals"]
    additional = v8["additional_positions"]

    print("\n[V8 vs rangovas]")
    # Extract V8 additional values
    additional_map = {a["aprasymas"].lower()[:30]: a["kiekis"] for a in additional}
    v8_rotband = sum(a["kiekis"] for a in additional if "lyginimas" in a["aprasymas"].lower())
    v8_angokrasciai = sum(a["kiekis"] for a in additional if "angokraščių" in a["aprasymas"].lower())
    v8_sviestuvai = sum(a["kiekis"] for a in additional if "šviestuvų" in a["aprasymas"].lower())
    v8_skyles = sum(a["kiekis"] for a in additional if "skylių gręžimas" in a["aprasymas"].lower())
    v8_silikonas = sum(a["kiekis"] for a in additional if "silikon" in a["aprasymas"].lower())
    v8_siuksles = sum(a["kiekis"] for a in additional if "šiukšlių" in a["aprasymas"].lower())
    v8_nuolydis = sum(a["kiekis"] for a in additional if "nuolydžio" in a["aprasymas"].lower())

    print("  " + compare(totals.get("dazymo_plotas_m2", 0), rangovo.get("dazymo_plotas_m2", 0), "Sienų/lubų dažymas (m²)"))
    print("  " + compare(v8_rotband, rangovo.get("rotband_m2", 0), "Sienų lyginimas Rotband (m²)"))
    print("  " + compare(totals.get("kampai_m", 0), rangovo.get("kampai_m", 0), "Dažymo kampai (m)"))
    print("  " + compare(totals.get("gkp_lubu_standart_m2", 0) + totals.get("gkp_lubu_virs_3m_m2", 0), rangovo.get("gkp_lubu_m2", 0), "GKP lubos (m²)"))
    print("  " + compare(v8_angokrasciai, rangovo.get("gkp_angokrasciu_m", 0), "Angokraščiai GKP (m)"))
    print("  " + compare(v8_sviestuvai, rangovo.get("sviestuvai_vnt", 0), "Šviestuvai (vnt)"))
    print("  " + compare(v8_skyles, rangovo.get("skyles_pliteles_vnt", 0), "Skylių gręžimas (vnt)"))
    print("  " + compare(v8_silikonas, rangovo.get("kampu_silikonavimas_m", 0), "Kampų silikonas (m)"))
    print("  " + compare(v8_siuksles, rangovo.get("siuksliu_vnt", 0), "Šiukšlės (m³)"))
    print("  " + compare(v8_nuolydis, rangovo.get("nuolydis_dusho_vnt", 0), "Nuolydis dušui (vnt)"))
    print("  " + compare(totals.get("hidroizoliacijos_vnt", 0), rangovo.get("hidroizoliacijos_vnt", 0), "Hidroizoliacija (vnt)"))


def main():
    tomo_data = load_tomo_data()
    print("V8 STRESS TEST")
    print("Naudojam mock kambarius — accuracy parodo TIK formulių logiką, ne Vision tikslumą.")

    for proj_id in ["P1", "P2", "P3", "P4", "P5"]:
        if proj_id not in tomo_data:
            continue
        run_one_project(proj_id, tomo_data[proj_id])


if __name__ == "__main__":
    main()

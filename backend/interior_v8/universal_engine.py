"""
V8 Universal Engine — interior takeoff pagal industries standart.

Architektūra:
1. AI Vision per kambarį identifikuoja TIPINĮ paskirties tipą
2. Universal taisyklės nustato KIEK tos patalpos dažoma, plyteliuojama
3. Matematika atlieka skaičiavimus
4. Sanity check'ai pranešia anomalijas

NĖRA Rangovas overfitting. Industries STANDART.
"""

from __future__ import annotations
import math
from typing import Any


# ═════════════════════════════════════════════════════════════════════════
# UNIVERSAL TAISYKLĖS (industries standartai)
# ═════════════════════════════════════════════════════════════════════════

UNIVERSAL_RULES = {
    # NRM2 Section 29: angos > 1m² atimamos iš dažomo ploto
    "openings_threshold_m2": 1.0,

    # Standart angų dydžiai (m²)
    "default_door_area_m2": 1.85,    # 0.91 × 2.03 = 21 sq ft (US standart)
    "default_window_area_m2": 1.40,  # 0.91 × 1.52 = 15 sq ft (US standart)

    # Vonios plytelinės juostos aukštis (default — vartotojas gali keisti)
    "bathroom_tile_height_m": 2.0,

    # Lubų aukštis defaults
    "default_ceiling_height_m": 2.82,        # LT modernus
    "soviet_era_ceiling_height_m": 2.50,     # Sovietmečio
    "high_ceiling_threshold_m": 3.0,         # Virš 3m → atskira pozicija

    # Glaistas Q lygiai (kg/m²/mm)
    "skim_consumption": {
        "Q1": 0.8,  # Under wallpaper
        "Q2": 1.0,  # Under matte paint (STANDARD)
        "Q3": 1.2,  # Under semi-gloss
        "Q4": 1.5,  # Under gloss
    },
    "skim_default_thickness_mm": 1.5,

    # Coverage rates (m²/L per coat)
    "paint_coverage": {
        "smooth_repaint": 11,        # Previously painted
        "plastered_q2_q3": 8,        # NEW STANDART
        "fresh_plaster": 4,
        "ceiling_smooth": 11,
        "primer": 7,                 # 0.15 L/m²
    },
    "default_coats": 2,
    "first_coat_factor": 1.8,        # NE 2.0 — first coat absorbs more

    # Drywall (gypsum board)
    "drywall_sheet_area_m2": 3.0,    # 1200×2500mm = 3.0m²
    "drywall_screws_per_sheet": 30,
    "drywall_joint_compound_kg_per_m2": 0.4,
    "drywall_thickness_walls_mm": 12.5,
    "drywall_thickness_ceilings_mm": 9.5,

    # Waste factors (% per material)
    "waste_factors": {
        "paint": 0.07,                # 5-10% standard
        "drywall": 0.12,              # 10-15%
        "tiles_straight": 0.08,
        "tiles_diagonal": 0.13,
        "tiles_herringbone": 0.18,
        "laminate_straight": 0.10,
        "laminate_diagonal": 0.13,
        "parquet_herringbone": 0.20,
    },

    # Wallpaper
    "wallpaper_roll_usable_area_m2": 4.5,  # 0.53×10.05m gross, ~4-5 useful
}


# ═════════════════════════════════════════════════════════════════════════
# PER PATALPOS TIPĄ — universal taisyklės
# ═════════════════════════════════════════════════════════════════════════

ROOM_TYPE_RULES = {
    # paskirtis: (sienos_dažomos, lubų_tipas, grindys, plytelės_sienos_iki, plytelės_grindys)
    "gyvenamoji":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "miegamoji":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "valgomasis":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "virtuve":     {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0.6, "tile_floor": True},   # backsplash 0.6m
    "vonia":       {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "wc":          {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "san":         {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "koridorius":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "holas":       {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "rubine":      {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "drabuzine":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "katiline":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "skalbykla":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "tambūras":    {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "tile", "tile_walls_to_m": 0,  "tile_floor": True},
    "garazas":     {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "concrete", "tile_walls_to_m": 0, "tile_floor": False},
    "sandėliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "sandeliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
}


def translate_user_prefs_to_room_rules(prefs: dict | None) -> dict | None:
    """
    Konvertuoja vartotojo Setup Wizard pasirinkimus (flat dict)
    į per-paskirtis ROOM_TYPE_RULES struktūrą.

    Frontend siunčia:
        {
          bathroom_tile_height_m: 2.4,
          drabuzine_painted: true,
          garazas_painted: false,
          ...
        }

    Grąžinama: ROOM_TYPE_RULES copy su pakeistais laukais.
    """
    if not prefs:
        return None

    # Pradedame nuo standart taisyklių, tada modifikuojame
    rules = {k: dict(v) for k, v in ROOM_TYPE_RULES.items()}

    # Vonios plytelių aukštis (vonia/wc/san)
    bath_h = prefs.get("bathroom_tile_height_m")
    if bath_h is not None:
        for room_type in ("vonia", "wc", "san"):
            rules[room_type]["tile_walls_to_m"] = float(bath_h)

    # Vonios sienos virš plytelių dažomos?
    bath_paint = prefs.get("bathroom_walls_painted_above_tiles")
    if bath_paint is False:
        for room_type in ("vonia", "wc", "san"):
            rules[room_type]["walls_paint"] = 0.0

    # Virtuvės backsplash
    kitchen_h = prefs.get("kitchen_backsplash_height_m")
    if kitchen_h is not None and "virtuve" in rules:
        rules["virtuve"]["tile_walls_to_m"] = float(kitchen_h)

    # Patalpos: dažoma TAIP/NE
    paint_map = {
        "drabuzine_painted": ("drabuzine",),
        "rubine_painted": ("rubine",),
        "sandeliukas_painted": ("sandeliukas", "sandėliukas"),
        "katiline_painted": ("katiline",),
        "garazas_painted": ("garazas",),
        "tamburas_painted": ("tambūras", "tamburas"),
    }
    for pref_key, room_keys in paint_map.items():
        if pref_key not in prefs:
            continue
        val = bool(prefs[pref_key])
        for rk in room_keys:
            if rk in rules:
                rules[rk]["walls_paint"] = 1.0 if val else 0.0

    return rules


def normalize_paskirtis(p: str) -> str:
    """Normalizuoja patalpos paskirtį į standartinę."""
    if not p:
        return "gyvenamoji"
    p = p.lower().strip()
    # Aliasai
    if "garaž" in p or "garaz" in p:
        return "garazas"
    if "tambūr" in p or "tambur" in p:
        return "tambūras"
    if "vonia" in p:
        return "vonia"
    if "wc" in p or "tualet" in p:
        return "wc"
    if "san" in p and "mazg" in p:
        return "san"
    if "drabuž" in p or "rūbin" in p or "rubin" in p:
        return "drabuzine"
    if "katil" in p:
        return "katiline"
    if "skalb" in p:
        return "skalbykla"
    if "virtuv" in p:
        return "virtuve"
    if "valgom" in p:
        return "valgomasis"
    if "miegam" in p:
        return "miegamoji"
    if "kambar" in p or "svetain" in p:
        return "gyvenamoji"
    if "holas" in p or "hol" in p:
        return "holas"
    if "koridor" in p:
        return "koridorius"
    if "sandėl" in p or "sandel" in p:
        return "sandeliukas"
    return p


# ═════════════════════════════════════════════════════════════════════════
# SKAIČIAVIMAI per patalpą
# ═════════════════════════════════════════════════════════════════════════

def calc_room_quantities(room: dict,
                          ceiling_height_m: float = 2.82,
                          rules: dict | None = None) -> dict:
    """
    Per patalpą skaičiuoja TIKSLIUS kiekius pagal universal industries
    taisykles.

    Args:
        room: {nr, pavadinimas, paskirtis, plotas_m2, perimetras_m, [doors, windows]}
        ceiling_height_m: lubų aukštis (default 2.82)
        rules: vartotojo override'us (custom ROOM_TYPE_RULES)

    Returns:
        Dictionary su per kambarį kiekiais.
    """
    pavadinimas = room.get("pavadinimas") or ""

    # Sprint 2 D3: atviros erdvės auto-detection (LT specifika)
    # Jei pavadinimas yra "Svetainė-valgomasis-virtuvė" ir paskirtis nenumatyta,
    # priskirti "gyvenamoji" + skaičiuoti virtuvės backsplash atskirai.
    from .lt_area_calculator import is_open_space, get_open_space_paskirtis
    is_open = is_open_space(pavadinimas)
    if is_open and not room.get("paskirtis"):
        room["paskirtis"] = get_open_space_paskirtis(pavadinimas)

    paskirtis = normalize_paskirtis(room.get("paskirtis"))
    rt_rules = (rules or {}).get(paskirtis) or ROOM_TYPE_RULES.get(paskirtis) or ROOM_TYPE_RULES["gyvenamoji"]

    plotas = float(room.get("plotas_m2") or 0)
    perim = float(room.get("perimetras_m") or 0)
    H = float(room.get("lubu_aukstis_m") or ceiling_height_m)

    # Mansardinis svoris (jei zones pateikti)
    mansard_zones = room.get("mansard_zones")  # list of {plotas_m2, lubu_aukstis_m}
    mansard_correction = 0
    if mansard_zones:
        from .lt_area_calculator import calc_room_area_with_mansard
        ma = calc_room_area_with_mansard(mansard_zones)
        plotas = ma["total_area_weighted"]  # plotas su STR svoriu
        mansard_correction = ma["mansard_correction"]

    # Jei perimetras nepateiktas — aproks pagal stačiakampį 1.3:1
    if perim <= 0 and plotas > 0:
        perim = 4.18 * math.sqrt(plotas)

    # Sienos bruto plotas
    walls_gross = perim * H

    # Atimti angas (NRM2: > 1m² atimame)
    n_doors = int(room.get("n_doors") or 1)  # default 1 durys per kambarį
    n_windows = int(room.get("n_windows") or 1)  # default 1 langas per kambarį
    door_area = float(room.get("door_area_m2") or UNIVERSAL_RULES["default_door_area_m2"])
    window_area = float(room.get("window_area_m2") or UNIVERSAL_RULES["default_window_area_m2"])

    doors_total = n_doors * door_area if door_area >= UNIVERSAL_RULES["openings_threshold_m2"] else 0
    windows_total = n_windows * window_area if window_area >= UNIVERSAL_RULES["openings_threshold_m2"] else 0

    # Plytelinės sienos (vonia / virtuvė backsplash)
    tile_height = float(rt_rules.get("tile_walls_to_m") or 0)
    tile_walls_area = perim * tile_height if tile_height > 0 else 0

    # Sprint 2 D3: jei atvira erdvė su virtuve — pridėti backsplash atskirai
    if is_open:
        from .lt_area_calculator import calc_open_space_features
        os_features = calc_open_space_features(pavadinimas, plotas, perim)
        if os_features.get("has_kitchen_zone"):
            # Backsplash plytelės virš virtuvės zonos (priimam, kad
            # virtuvės dalis ~30% perimetro × 0.6m)
            tile_walls_area += os_features.get("kitchen_backsplash_m2", 0)

    # Sienos NETO (dažomos)
    # Naudojam .get su default — NE 'or' — kad 0.0 (garažas/tambūras) liktų 0
    walls_paint_factor = rt_rules.get("walls_paint")
    walls_paint_factor = float(walls_paint_factor) if walls_paint_factor is not None else 1.0
    walls_net = max(0, walls_gross - doors_total - windows_total - tile_walls_area)
    walls_paintable = walls_net * walls_paint_factor

    # Lubos
    ceiling_type = rt_rules.get("ceiling_type") or "gkp"
    ceiling_paintable = plotas if ceiling_type == "gkp" else 0

    # GKP lubos atskirtos pagal aukštį
    is_high_ceiling = H > UNIVERSAL_RULES["high_ceiling_threshold_m"]
    gkp_lubu_standart = ceiling_paintable if not is_high_ceiling else 0
    gkp_lubu_virs_3m = ceiling_paintable if is_high_ceiling else 0

    # Dažymo plotas (sienos + lubos)
    dazymo_plotas = walls_paintable + ceiling_paintable

    # Plytelės grindyse
    tile_floor = bool(rt_rules.get("tile_floor"))
    plyteles_grindys = plotas if tile_floor else 0

    # Sprint 2 D3: jei atvira erdvė su virtuve — virtuvės grindyse plytelės
    if is_open:
        from .lt_area_calculator import calc_open_space_features
        os_features = calc_open_space_features(pavadinimas, plotas, perim)
        if os_features.get("kitchen_floor_tiles_m2"):
            plyteles_grindys += os_features["kitchen_floor_tiles_m2"]

    # Plytelės sienose
    plyteles_sienos = tile_walls_area

    # Kampai (RICS NRM2 + LT praktika, Sprint 2 D6):
    # 1. Periferija (lubinis + grindinis kampas)
    # 2. 4 vidiniai vert kampai × H per dažomą kambarį
    # 3. Angokraščių krašto kampai per kiekvienai durims/langui
    #    Per duris: (W + 2H) — 3 kraštai, kuriuose susitinka angokraštis su siena
    #    Per langą: (W + 2H) — irgi 3 kraštai
    # Stress-test parodė: be #3 — mūsų kampai 200m vs Rangovo 400-580m.
    if walls_paint_factor > 0:
        # Bazė: perimetras + 4 vidiniai vert kampai
        kampai = perim + 4 * H
        # Plius: angokraščių krašto kampai per kiekvienai angai
        # Standart durys 0.9 × 2.05: 0.9 + 2×2.05 = 5.0 m / angas
        door_height = 2.05
        door_width = 0.9
        kampai += n_doors * (door_width + 2 * door_height)
        # Standart langas 1.2 × 1.5: 1.2 + 2×1.5 = 4.2 m / langas
        window_height = 1.5
        window_width = 1.2
        kampai += n_windows * (window_width + 2 * window_height)
    else:
        kampai = 0

    # Grindjuostės (perimetras − durų pločiai, vonia/wc neturi)
    door_widths_total = n_doors * 0.85  # default 0.85m per durys
    grindjuostes = max(0, perim - door_widths_total) if not tile_floor else 0

    # PVC/parkettas/laminat grindys
    floor_type = rt_rules.get("floor")
    pvc_grindys = plotas if floor_type == "parquet" else 0  # default

    # Išlyginamasis grindims
    isliginamasis = plotas if floor_type != "concrete" else 0

    return {
        "nr": room.get("nr"),
        "pavadinimas": room.get("pavadinimas"),
        "paskirtis": paskirtis,
        "puslapio_nr": room.get("puslapio_nr"),
        "bbox_pct": room.get("bbox_pct"),  # Auto-detect koordinatės brėžinyje
        "is_open_space": is_open,           # Sprint 2 D3
        "mansard_correction_m2": round(mansard_correction, 2) if mansard_correction else 0,
        "plotas_m2": round(plotas, 2),
        "perimetras_m": round(perim, 2),
        "lubu_aukstis_m": round(H, 2),
        "ceiling_type": ceiling_type,
        "walls_gross_m2": round(walls_gross, 2),
        "walls_paintable_m2": round(walls_paintable, 2),
        "ceiling_paintable_m2": round(ceiling_paintable, 2),
        "dazymo_plotas_m2": round(dazymo_plotas, 2),
        "gkp_lubu_standart_m2": round(gkp_lubu_standart, 2),
        "gkp_lubu_virs_3m_m2": round(gkp_lubu_virs_3m, 2),
        "kampai_m": round(kampai, 2),
        "plyteles_sienos_m2": round(plyteles_sienos, 2),
        "plyteles_grindys_m2": round(plyteles_grindys, 2),
        "pvc_grindys_m2": round(pvc_grindys, 2),
        "isliginamasis_m2": round(isliginamasis, 2),
        "grindjuostes_m": round(grindjuostes, 2),
        "doors_deducted_m2": round(doors_total, 2),
        "windows_deducted_m2": round(windows_total, 2),
    }


def _classify_trace_type(aprasymas: str, vnt: str) -> str:
    """Pagal mato_vnt + aprašymą — counted/area/linear/formula.

    Tipas lemia, kaip frontend'as vizualizuos poziciją brėžinyje:
      counted → raudoni dot'ai per simbolį
      area    → polygons spalvotai užpildyti
      linear  → linijos perimetru
      formula → tooltip su skaičiavimo paaiškinimu (be vizualinio overlay'o)
    """
    v = (vnt or "").lower().strip().rstrip(".")
    a = (aprasymas or "").lower()

    # Formula tipas — pagal aprašymą (turi prioritetą)
    formula_keywords = [
        "šiukšl", "siukšl", "atliekų", "atlieku",
        "pastol", "išvež", "isvez",
        "lyginimas", "rotband",  # plotinis bet skaičiuojamas %
    ]
    if any(kw in a for kw in formula_keywords):
        return "formula"

    if v in ("vnt", "kompl", "vienetai"):
        return "counted"
    if v in ("m2", "m²", "kvadr", "m^2"):
        return "area"
    if v in ("m", "tiesinis", "lin"):
        return "linear"
    if v in ("d.d", "dd", "m3", "m³", "kg", "l", "kompletas", "kpl"):
        return "formula"
    return "formula"


def _build_trace_links(
    position: dict,
    rooms_calculated: list[dict],
    detected_symbols: dict | None,
    trace_type: str,
) -> list[dict]:
    """Surenkam visas brėžinio koordinates šiai pozicijai.

    Format priklauso nuo trace_type:
      counted → [{page_nr, x_pct, y_pct, confidence}] per kiekvieną simbolį
      area    → [{page_nr, polygon_pdf, page_width_pdf, page_height_pdf,
                  room_nr, room_name}] per kambarį
      linear  → [{page_nr, polygon_pdf, page_width_pdf, page_height_pdf,
                  type:'perimeter', room_nr, room_name}]
      formula → [] (tuščias — vizualinio linko nėra)
    """
    if trace_type == "formula":
        return []

    aprasymas_lower = (position.get("aprasymas") or "").lower()
    detected = (detected_symbols or {}).get("by_type", {})

    # Helper: kuriose patalpose ši pozicija aktuali (skip garažas/tambūras
    # dažymui, pvz.). Default — visos patalpos.
    def _applicable_rooms() -> list[dict]:
        # Drėgnos patalpos pozicijoms (silikonavimas, plytelės, hidroizoliacija,
        # klozetas, maišytuvas, ...)
        wet_keywords = ["silikon", "plytel", "hidroizoli", "klozet", "wc",
                        "maišytu", "maisytu", "gyvatuk", "nuolyd", "trap"]
        if any(kw in aprasymas_lower for kw in wet_keywords):
            return [r for r in rooms_calculated
                     if r.get("paskirtis") in ("vonia", "wc", "san")]
        # Garažas/tambūras — nedažomi
        skip_keywords = ["dažym", "dazym", "glaisty", "tapet"]
        if any(kw in aprasymas_lower for kw in skip_keywords):
            return [r for r in rooms_calculated
                     if r.get("paskirtis") not in
                        ("garazas", "tambūras", "tamburas")]
        return list(rooms_calculated)

    # ─ COUNTED tipas — ieškom simbolio koordinatės iš detected_symbols ──────
    if trace_type == "counted":
        # Mapping aprasymas → simbolio tipas (kuris yra detected_symbols)
        SYMBOL_MAP = {
            "klozet": "klozetai",
            "wc rėm": "klozetai",
            "wc rem": "klozetai",
            "maišytu": "maisytuvai",
            "maisytu": "maisytuvai",
            "gyvatuk": "gyvatukai",
            "rankšluoščių": "gyvatukai",
            "ranksluoscu": "gyvatukai",
            "skalbim": "skalbimo_masinos",
            "trap": "trapai",
            "linijinio latako": "trapai",
            "rozet": "rozetes",
            "jungikl": "jungikliai",
            "rozetės/jungikl": ("rozetes", "jungikliai"),
            "rozetes/jungikl": ("rozetes", "jungikliai"),
            "lubinių pri": "sviestuvai",
            "lubiniu pri": "sviestuvai",
            "pakabinam": "pakabinami_sviestuvai",
            "led juost": "led_juostos",
            "difūzori": "difuzoriai",
            "difuzori": "difuzoriai",
            "ventiliac": "difuzoriai",
            "duris": "durys",
            "lang": "langai",
        }
        # Suranda atitinkantį simbolio tipą
        sym_types_to_use = []
        for kw, sym_t in SYMBOL_MAP.items():
            if kw in aprasymas_lower:
                if isinstance(sym_t, tuple):
                    sym_types_to_use.extend(sym_t)
                else:
                    sym_types_to_use.append(sym_t)
                break
        if not sym_types_to_use:
            return []  # Be specifinio simbolio tipo — counted bet be koordinatės

        links = []
        for st in sym_types_to_use:
            info = detected.get(st)
            if not info:
                continue
            for page_data in info.get("pages", []):
                page_nr = page_data.get("page")
                for sym in page_data.get("symbols", []):
                    links.append({
                        "page_nr": page_nr,
                        "x_pct": float(sym.get("x_pct", 0)),
                        "y_pct": float(sym.get("y_pct", 0)),
                        "confidence": sym.get("confidence", "medium"),
                    })
        return links

    # ─ AREA tipas — polygons iš v8_rooms ─────────────────────────────────────
    # V9 atveju turim polygon_pdf (tikslus). V8 atveju tik bbox_pct (procentinis
    # bounding box iš Vision). Frontend fallback'ina į bbox jei polygon nėra.
    if trace_type == "area":
        applicable = _applicable_rooms()
        links = []
        for r in applicable:
            poly = r.get("polygon_pdf")
            bbox = r.get("bbox_pct")
            if not poly and not bbox:
                continue  # nei polygono, nei bbox — nieko nerodysim
            links.append({
                "page_nr": r.get("page_nr") or r.get("puslapio_nr") or 1,
                "polygon_pdf": poly,                            # gali būti None (V8 path)
                "page_width_pdf": r.get("page_width_pdf"),     # gali būti None
                "page_height_pdf": r.get("page_height_pdf"),   # gali būti None
                "bbox_pct": bbox,                               # YRA tiek V8, tiek V9 atveju
                "centroid_pct": r.get("centroid_pct"),
                "room_nr": r.get("nr"),
                "room_name": r.get("pavadinimas"),
            })
        return links

    # ─ LINEAR tipas — polygon perimeter (arba bbox borders fallback) ─────────
    if trace_type == "linear":
        applicable = _applicable_rooms()
        links = []
        for r in applicable:
            poly = r.get("polygon_pdf")
            bbox = r.get("bbox_pct")
            if not poly and not bbox:
                continue
            links.append({
                "page_nr": r.get("page_nr") or r.get("puslapio_nr") or 1,
                "polygon_pdf": poly,
                "page_width_pdf": r.get("page_width_pdf"),
                "page_height_pdf": r.get("page_height_pdf"),
                "bbox_pct": bbox,
                "type": "perimeter",
                "room_nr": r.get("nr"),
                "room_name": r.get("pavadinimas"),
            })
        return links

    return []


def _explain_formula(position: dict, totals: dict) -> str:
    """Žmonėms suprantamas paaiškinimas iš ko skaičiuojama formulę pozicija."""
    a = (position.get("aprasymas") or "").lower()
    kiekis = position.get("kiekis", 0)
    bendras = totals.get("bendras_plotas_m2", 0)
    if "šiukšl" in a or "siukšl" in a or "atliek" in a:
        return (f"Šiukšlių/atliekų išvežimas: bendras plotas {bendras:.1f}m² × "
                f"vidurkis 0.05 m³/m² = {kiekis}m³")
    if "pastol" in a:
        return (f"Pastolių dienos: aukštos patalpos plotas × 0.2 d.d./m² (NRM2 5.5)")
    if "rotband" in a or "lyginimas" in a:
        return (f"Sienų lyginimas: 25% nuo dažomo sienų ploto (DIN 18363 § 3.4)")
    if "išvež" in a or "isvez" in a:
        return f"Išvežimo paslauga: skaičiuojama nuo bendros darbų apimties"
    return f"Skaičiavimas pagal universal industries formulę ({position.get('source','')})"


def calc_additional_positions(rooms_calculated: list[dict],
                                totals: dict,
                                user_prefs: dict | None = None,
                                detected_symbols: dict | None = None) -> list[dict]:
    """
    Pridedami CORE pozicijos, kurias industries standartai (NRM2, DIN, CSI)
    rekomenduoja kaip atskiras eilutes.

    Args:
      rooms_calculated: per kambarį skaičiavimai (su plotas, perim, paskirtis)
      totals: globalūs sumos (dazymo_plotas, kampai_m, ...)
      user_prefs: Setup Wizard pasirinkimai
      detected_symbols: AI Vision DETEKTUOTI simboliai iš brėžinio.
        Format: {"by_type": {"rozetes": {"total": 32, ...},
                              "klozetai": {"total": 2, ...}, ...}}
        Jei pateikta — naudojam TIKRUS skaičius, ne hardcoded vidurkius.
        Jei NĖRA — fallback į vidurkius su LOW confidence.

    Per kiekvieną poziciją:
      "source" — citata (NRM2/DIN/CSI/etc.)
      "confidence":
        "high"   — vector matavimas (durys/langai iš PDF lines)
        "medium" — AI Vision aptikta + agreguota
        "low"    — formulės vidurkis (FALLBACK kai AI nieko nerado)
      "detected" — true jei AI rado, false jei fallback

    Grąžina list of dicts:
        {nr, aprasymas, vnt, kiekis, kategorija, source, confidence, detected}
    """
    prefs = user_prefs or {}
    interior_subtype = prefs.get("interior_subtype", "naujas")
    detected = (detected_symbols or {}).get("by_type", {})

    def _detected_count(sym_type: str) -> int | None:
        """Grąžina TIKRĄ count jei AI Vision rado, kitaip None (= fallback)."""
        info = detected.get(sym_type)
        if not info:
            return None
        total = info.get("total")
        return int(total) if total is not None and total > 0 else None

    # Sienos NETO ploto (be lubų) — nuvedam dazymo iš lubų
    sienos_dazomos = (
        totals.get("dazymo_plotas_m2", 0)
        - totals.get("gkp_lubu_standart_m2", 0)
        - totals.get("gkp_lubu_virs_3m_m2", 0)
    )
    sienos_dazomos = max(0, sienos_dazomos)

    # Drėgnos patalpos — vonia/wc/san
    dregnos = [r for r in rooms_calculated
               if r.get("paskirtis") in ("vonia", "wc", "san")]

    # Bendras durų skaičius (default 1 per kambarį)
    n_doors_total = sum(int(r.get("n_doors") or 1) for r in rooms_calculated)

    # Šviestuvai per kambarį pagal paskirtį (industries: 1 per gyvenamoji,
    # 2 per virtuvė/vonia, 0 garažas)
    sviestuvai_total = 0
    for r in rooms_calculated:
        p = r.get("paskirtis")
        if p in ("garazas", "tambūras", "tamburas"):
            n = 0
        elif p in ("virtuve", "vonia", "wc", "san"):
            n = 2
        elif p in ("sandeliukas", "sandėliukas", "drabuzine"):
            n = 1
        else:
            n = 1
        sviestuvai_total += n

    additional = []

    # ─ 1. Sienų lyginimas (Q1 Vorspachtelung) ─────────────────────────────
    # Šaltinis: DIN 18363 § 3.4 — naujam mūro paviršiui paruošti prieš glaistymą.
    # Vidurkis: 25% nuo dažomo sienų ploto (NRM2 atvejų vidurkis).
    rotband_pct = float(prefs.get("rotband_pct", 0.25))
    if rotband_pct > 0 and sienos_dazomos > 0:
        kiekis = round(sienos_dazomos * rotband_pct, 1)
        additional.append({
            "aprasymas": "Sienų lyginimas (paruošiamasis sluoksnis, mūro pertvaroms)",
            "vnt": "m2", "kiekis": kiekis,
            "kategorija": "Sienų paruošimas",
            "source": "DIN 18363 § 3.4 (Q1 Vorspachtelung)",
            "confidence": "medium",
        })

    # ─ 2. GKP angokraščių apdirbimas ──────────────────────────────────────
    # Šaltinis: NRM2 29.10 — door reveals in solid walls.
    # Formulė: durų sk. × 5.1 m (std anga 0.9×2.05m, perim = 2×2.05+0.9 = 5.0).
    if n_doors_total > 0:
        kiekis = round(n_doors_total * 5.0, 1)
        additional.append({
            "aprasymas": "Angokraščių apdirbimas GKP (sustorintų sienų durims)",
            "vnt": "m", "kiekis": kiekis,
            "kategorija": "GKP",
            "source": "NRM2 29.10 (door reveals)",
            "confidence": "medium",
        })

    # ─ 3. Lubinių šviestuvų apdirbimas ─────────────────────────────────────
    # Šaltinis: CSI MasterFormat 26 50 00 — lighting fixtures finishing.
    if sviestuvai_total > 0:
        additional.append({
            "aprasymas": "Lubinių priglaistomų šviestuvų apdirbimas",
            "vnt": "vnt", "kiekis": sviestuvai_total,
            "kategorija": "Apšvietimas",
            "source": "CSI MasterFormat 26 50 00",
            "confidence": "low",
        })

    # ─ 4. Skylių gręžimas plytelėse ────────────────────────────────────────
    # Šaltinis: ANSI A108 — wet area penetrations for plumbing.
    # Vidurkis: 10 vnt per drėgną patalpą (santechnika + ventiliacija).
    if dregnos:
        kiekis = len(dregnos) * 10
        additional.append({
            "aprasymas": "Skylių gręžimas plytelėse (santechnikos taškams)",
            "vnt": "vnt", "kiekis": kiekis,
            "kategorija": "Plytelių darbai",
            "source": "ANSI A108 (wet area penetrations)",
            "confidence": "low",
        })

    # ─ 5. Kampų silikonavimas ──────────────────────────────────────────────
    # Šaltinis: NRM2 29.13 — sealant to wall/floor junctions in wet rooms.
    # Formulė: drėgnoms patalpoms — perimetras (sienų-grindų sankirta) +
    # kiekvienas vidaus kampas (~4 vert kampai × H per kambarį).
    if dregnos:
        sil_total = 0.0
        for r in dregnos:
            perim = r.get("perimetras_m", 0)
            H = r.get("lubu_aukstis_m", 2.82)
            # Sienų-grindų junctura + 4 vidaus vert kampai (apatinė pora)
            sil_total += perim + 4 * H
        kiekis = round(sil_total, 1)
        additional.append({
            "aprasymas": "Kampų silikonavimas (drėgnose patalpose)",
            "vnt": "m", "kiekis": kiekis,
            "kategorija": "Plytelių darbai",
            "source": "NRM2 29.13 (sealant in wet rooms)",
            "confidence": "medium",
        })

    # ─ 6. Nuolydžio formavimas dušo kabinoje ───────────────────────────────
    # Šaltinis: ANSI A118.10 — shower floor slope to drain.
    # Vidurkis: 1 vnt per kiekvieną drėgną patalpą su dušu.
    n_dusu = len([r for r in dregnos
                   if r.get("paskirtis") in ("vonia", "san")])
    if n_dusu > 0:
        additional.append({
            "aprasymas": "Nuolydžio formavimas dušo kabinoje",
            "vnt": "vnt", "kiekis": n_dusu,
            "kategorija": "Plytelių darbai",
            "source": "ANSI A118.10 (shower floor slope)",
            "confidence": "medium",
        })

    # ─ 7. Šiukšlių išvežimas ───────────────────────────────────────────────
    # Šaltinis: LT STR 2.07.01:2003 (statybvietės plotmė) +
    # Sherwin-Williams construction waste calculator vidurkis.
    # Vidurkis: 0.05 m³ atliekų / m² apdailos darbų.
    bendras_plotas = totals.get("bendras_plotas_m2", 0)
    if bendras_plotas > 0:
        kiekis = round(bendras_plotas * 0.05, 1)
        additional.append({
            "aprasymas": "Šiukšlių išvežimas (statybvietės atliekos)",
            "vnt": "m3", "kiekis": kiekis,
            "kategorija": "Bendrai",
            "source": "STR 2.07.01:2003 + S-W waste calculator",
            "confidence": "low",
        })

    # ─ 8. GKP nišų formavimas (LED apšvietimui) ────────────────────────────
    # Šaltinis: tipologijos klausimas — premium projektams.
    # User pref: "led_niche_per_room_avg_m" (default 0).
    led_per_room = float(prefs.get("led_niche_per_room_avg_m", 0))
    if led_per_room > 0:
        kiekis = round(led_per_room * len(rooms_calculated), 1)
        additional.append({
            "aprasymas": "Nišų formavimas iš GKP (paslėptam apšvietimui)",
            "vnt": "m", "kiekis": kiekis,
            "kategorija": "GKP",
            "source": "User preference (premium feature)",
            "confidence": "low",
        })

    # ─ 9. Durų angų paruošimas beapvasdinėms durims (premium) ──────────────
    if prefs.get("beapvasdines_doors") and n_doors_total > 0:
        kiekis = round(n_doors_total * 5.0, 1)
        additional.append({
            "aprasymas": "Durų angų paruošimas beapvasdinėms durims",
            "vnt": "m", "kiekis": kiekis,
            "kategorija": "Sienų paruošimas",
            "source": "User preference (frameless doors)",
            "confidence": "medium",
        })

    # ═══════════════════════════════════════════════════════════════════════
    # AI-DETEKTUOTI SIMBOLIAI iš brėžinio (Diena 3 v2 — TIKRA detekcija).
    # Tipinis flow: V9 pipeline po vector_polygons + page_classifier paleido
    # detect_all_symbols_for_pdf() kuris per kiekvieną page_type ieškojo
    # tinkamų simbolių. Rezultatas — detected_symbols['by_type'][...].
    #
    # JEIGU detected_symbols PATEIKTA — naudojam TIKRUS skaičius (high conf).
    # JEIGU NEPATEIKTA — fallback į žemus vidurkius (LOW conf, su flag'u).
    # ═══════════════════════════════════════════════════════════════════════

    drabuzine_count = sum(1 for r in rooms_calculated
                           if r.get("paskirtis") in ("drabuzine",))
    n_wc_kambarius = len([r for r in dregnos
                           if r.get("paskirtis") in ("wc", "vonia", "san")])

    # ─ 10. Difūzoriai (ventiliacijos taškai) iš lubų plano ─────────────────
    # AI ieško: apskritimas + 4 stačios linijos / kvadratas su X
    n_difuzoriai = _detected_count("difuzoriai")
    if n_difuzoriai is not None:
        additional.append({
            "aprasymas": "Difūzorių apdirbimas (ventiliacijos taškai)",
            "vnt": "vnt", "kiekis": n_difuzoriai,
            "kategorija": "Ventiliacija",
            "source": "AI Vision (lubų planas) + ASHRAE 62.2",
            "confidence": "medium", "detected": True,
        })
    else:
        # Fallback: 1 per kambarį (kuris turi ventiliaciją)
        guess = sum(1 for r in rooms_calculated
                     if r.get("paskirtis") not in ("garazas", "tambūras", "sandeliukas"))
        if guess > 0:
            additional.append({
                "aprasymas": "Difūzorių apdirbimas (ventiliacijos taškai)",
                "vnt": "vnt", "kiekis": guess,
                "kategorija": "Ventiliacija",
                "source": "FALLBACK: 1 per gyvenamąją (AI nerado lubų plano)",
                "confidence": "low", "detected": False,
            })

    # ─ 11. Klozetai (iš santechnikos plano) ─────────────────────────────────
    n_klozetu = _detected_count("klozetai")
    if n_klozetu is not None:
        # WC rėmas, klozeto montavimas, GKP dėžutė — visi pagal klozetus
        for ap, kat, src in [
            ("Klozeto montavimas", "Santechnika", "AI Vision"),
            ("WC rėmo montavimas (paslėptas)", "Santechnika", "AI Vision (klozeto rama)"),
            ("GKP dėžučių formavimas (paslėptiems vamzdžiams)", "GKP", "AI Vision (sąsaja su klozetu)"),
        ]:
            additional.append({
                "aprasymas": ap, "vnt": "vnt", "kiekis": n_klozetu,
                "kategorija": kat, "source": src,
                "confidence": "medium", "detected": True,
            })
    elif n_wc_kambarius > 0:
        for ap, kat in [
            ("Klozeto montavimas", "Santechnika"),
            ("WC rėmo montavimas (paslėptas)", "Santechnika"),
            ("GKP dėžučių formavimas (paslėptiems vamzdžiams)", "GKP"),
        ]:
            additional.append({
                "aprasymas": ap, "vnt": "vnt", "kiekis": n_wc_kambarius,
                "kategorija": kat,
                "source": "FALLBACK: 1 per drėgną patalpą (AI nerado santech.plano)",
                "confidence": "low", "detected": False,
            })

    # ─ 12. Maišytuvai (iš santechnikos plano) ───────────────────────────────
    n_maisytuvu = _detected_count("maisytuvai")
    if n_maisytuvu is not None:
        additional.append({
            "aprasymas": "Maišytuvų montavimas",
            "vnt": "vnt", "kiekis": n_maisytuvu,
            "kategorija": "Santechnika",
            "source": "AI Vision (santechnikos planas)",
            "confidence": "medium", "detected": True,
        })

    # ─ 13. Gyvatukai (rankšluosčių džiovintuvai) ────────────────────────────
    n_gyvatuku = _detected_count("gyvatukai")
    if n_gyvatuku is not None:
        additional.append({
            "aprasymas": "Gyvatuko (rankšluosčių džiovintuvo) montavimas",
            "vnt": "vnt", "kiekis": n_gyvatuku,
            "kategorija": "Santechnika",
            "source": "AI Vision (santechnikos planas)",
            "confidence": "medium", "detected": True,
        })

    # ─ 14. Trapai (linijiniai latakai vonioje) ──────────────────────────────
    n_trapu = _detected_count("trapai")
    if n_trapu is not None and n_trapu > 0:
        additional.append({
            "aprasymas": "Linijinio latako montavimas (vonios drenažas)",
            "vnt": "vnt", "kiekis": n_trapu,
            "kategorija": "Santechnika",
            "source": "AI Vision (santech. planas — trapai grindyse)",
            "confidence": "medium", "detected": True,
        })

    # ─ 15. Skalbimo mašinos prijungimas ─────────────────────────────────────
    n_skalb = _detected_count("skalbimo_masinos")
    if n_skalb is not None and n_skalb > 0:
        additional.append({
            "aprasymas": "Skalbimo mašinos sifono įrengimas",
            "vnt": "vnt", "kiekis": n_skalb,
            "kategorija": "Santechnika",
            "source": "AI Vision (santech. planas)",
            "confidence": "medium", "detected": True,
        })

    # ─ 16. Šviestuvai lubų / pakabinami (iš lubų plano) ─────────────────────
    n_sviestuvu = _detected_count("sviestuvai")
    if n_sviestuvu is not None:
        additional.append({
            "aprasymas": "Lubinių priglaistomų šviestuvų apdirbimas",
            "vnt": "vnt", "kiekis": n_sviestuvu,
            "kategorija": "Apšvietimas",
            "source": "AI Vision (lubų planas)",
            "confidence": "medium", "detected": True,
        })

    n_pakab = _detected_count("pakabinami_sviestuvai")
    if n_pakab is not None and n_pakab > 0:
        additional.append({
            "aprasymas": "Pakabinamų šviestuvų montavimas",
            "vnt": "vnt", "kiekis": n_pakab,
            "kategorija": "Apšvietimas",
            "source": "AI Vision (lubų planas)",
            "confidence": "medium", "detected": True,
        })

    # ─ 17. Rozetės + jungikliai (iš elektros plano) ─────────────────────────
    n_rozetes = _detected_count("rozetes")
    n_jungikliai = _detected_count("jungikliai")
    if n_rozetes is not None or n_jungikliai is not None:
        total_komutavimo = (n_rozetes or 0) + (n_jungikliai or 0)
        additional.append({
            "aprasymas": "Rozetės/jungiklio komutavimas",
            "vnt": "vnt", "kiekis": total_komutavimo,
            "kategorija": "Elektra",
            "source": (
                f"AI Vision (elektros planas: {n_rozetes or '?'} rozetes + "
                f"{n_jungikliai or '?'} jungikliai)"
            ),
            "confidence": "medium", "detected": True,
        })

    # ─ 18. LED juostos / nišos (iš lubų plano) ──────────────────────────────
    led_info = detected.get("led_juostos")
    led_m = (led_info or {}).get("total")
    if led_m and led_m > 0:
        # AI grąžina ilgį (linear=True simbolio config)
        additional.append({
            "aprasymas": "Nišų formavimas iš GKP (paslėptam apšvietimui)",
            "vnt": "m", "kiekis": round(led_m, 1),
            "kategorija": "GKP",
            "source": "AI Vision (lubų planas — LED nišos)",
            "confidence": "medium", "detected": True,
        })
        additional.append({
            "aprasymas": "LED juostos komutavimas",
            "vnt": "m", "kiekis": round(led_m, 1),
            "kategorija": "Apšvietimas",
            "source": "AI Vision (lubų planas — LED juostos)",
            "confidence": "medium", "detected": True,
        })
    else:
        # User pref fallback
        if led_per_room > 0:
            led_komutavimo_m = round(led_per_room * len(rooms_calculated), 1)
            additional.append({
                "aprasymas": "LED juostos komutavimas",
                "vnt": "m", "kiekis": led_komutavimo_m,
                "kategorija": "Apšvietimas",
                "source": "User preference (AI nerado lubų plano)",
                "confidence": "low", "detected": False,
            })

    # ═══════════════════════════════════════════════════════════════════════
    # GEOMETRINĖS POZICIJOS (formulės iš plotų/perimetrų — NE simbolių)
    # Šios pozicijos yra deterministinės — geometrija, ne objektų counting.
    # ═══════════════════════════════════════════════════════════════════════

    # ─ 19. Plytelių supjovimas 45° kampu (geom — vonios išorinių kampų × H) ─
    # Šaltinis: ANSI A108 — mitered tile edges for exposed corners.
    # Mes negalim deterministinai pasakyti kiek išorinių kampų vonioje BE Vision.
    # Bet jei AI grąžino vonios išorinių kampų count, naudojam jį.
    n_vonios_kampu = _detected_count("vonios_isoriniai_kampai")  # custom type
    if n_vonios_kampu is not None or dregnos:
        if n_vonios_kampu:
            kampai = n_vonios_kampu
            conf = "medium"; det = True; src = "AI Vision (vonios išoriniai kampai)"
        else:
            kampai = len(dregnos) * 1  # 1 išorinis per vonią (vidurkis)
            conf = "low"; det = False; src = "FALLBACK: 1 išorinis kampas per vonią"
        H_avg = sum(r.get("lubu_aukstis_m", 2.82) for r in dregnos) / max(len(dregnos), 1)
        kiekis = round(kampai * H_avg, 1)
        if kiekis > 0:
            additional.append({
                "aprasymas": "Plytelių supjovimas 45° kampu",
                "vnt": "m", "kiekis": kiekis,
                "kategorija": "Plytelių darbai",
                "source": src + " · ANSI A108",
                "confidence": conf, "detected": det,
            })

    # ─ 20. Revizinių durelių apdirbimas ─────────────────────────────────────
    # Šie simboliai retai pažymėti — Vision sunkiai aptiks.
    # Naudojam fallback: 1 per drėgną patalpą.
    if dregnos:
        n_reviz = len(dregnos)
        additional.append({
            "aprasymas": "Revizinių durelių apdirbimas (santechnikos)",
            "vnt": "vnt", "kiekis": n_reviz,
            "kategorija": "Santechnika",
            "source": "FALLBACK: 1 per drėgną patalpą (santech. dureles retai pažymėtos)",
            "confidence": "low", "detected": False,
        })

    # ─ 21. Pastoliai (geom — aukštos patalpos × 0.2 d.d./m²) ────────────────
    aukstos_patalpos = [r for r in rooms_calculated
                         if r.get("lubu_aukstis_m", 0) > 3.0]
    if aukstos_patalpos:
        plotas_aukstu = sum(r.get("plotas_m2", 0) for r in aukstos_patalpos)
        d_d = round(plotas_aukstu * 0.2, 1)
        if d_d > 0:
            additional.append({
                "aprasymas": "Pastolių nuoma (aukštesnių nei 3m patalpoms)",
                "vnt": "d.d", "kiekis": d_d,
                "kategorija": "Pastoliai",
                "source": "Geom: aukštos patalpos × 0.2 d.d./m² (NRM2 5.5)",
                "confidence": "high", "detected": True,
            })

    # ─ 22. Lubų glaistymas/dažymas (virš 3m, atskirai) ──────────────────────
    aukstu_lubu_m2 = totals.get("gkp_lubu_virs_3m_m2", 0)
    if aukstu_lubu_m2 > 0:
        additional.append({
            "aprasymas": "Lubų glaistymas/dažymas (virš 3m)",
            "vnt": "m2", "kiekis": round(aukstu_lubu_m2, 1),
            "kategorija": "Sienų paruošimas",
            "source": "Geom: aukštų patalpų lubos (DIN 18363 + premium)",
            "confidence": "high", "detected": True,
        })

    # ─ 23. GKP pertvaros (user pref) ────────────────────────────────────────
    n_pertvaru = int(prefs.get("gkp_pertvaros_count", 0))
    if n_pertvaru > 0:
        additional.append({
            "aprasymas": "GKP pertvaros įrengimas",
            "vnt": "vnt", "kiekis": n_pertvaru,
            "kategorija": "GKP",
            "source": "User preference (Setup Wizard)",
            "confidence": "high", "detected": True,
        })

    # ═══════════════════════════════════════════════════════════════════════
    # SUB-TIPO SPECIFINĖS POZICIJOS (Sprint 1 Q3)
    # ═══════════════════════════════════════════════════════════════════════

    bendras_plotas = totals.get("bendras_plotas_m2", 0)

    if interior_subtype == "renovacija":
        # Renovacijai: pridedam ardymo darbus + senų sienų paruošimą.
        # Šaltinis: Lietuvos statybos taisyklės STR 1.06.04 (renovacijos darbai).

        # Sienų ardymas (gipso, plytelių, tapeto demontavimas)
        if sienos_dazomos > 0:
            kiekis = round(sienos_dazomos * 0.3, 1)  # ~30% sienų ardymas
            additional.append({
                "aprasymas": "Senų apdailos sluoksnių pašalinimas (tapetai/glaistas/plytelės)",
                "vnt": "m2", "kiekis": kiekis,
                "kategorija": "Renovacija — paruošimas",
                "source": "STR 1.06.04 (renovacija)",
                "confidence": "low",
            })

        # Sienų lyginimas (renovacijos sienos dažniau lygintinos)
        if sienos_dazomos > 0:
            kiekis = round(sienos_dazomos * 0.6, 1)  # 60% sienų lyginimas (vs 25% naujam)
            additional.append({
                "aprasymas": "Senų sienų gilus lyginimas (renovacija)",
                "vnt": "m2", "kiekis": kiekis,
                "kategorija": "Renovacija — paruošimas",
                "source": "DIN 18363 + LT renovacijos praktika",
                "confidence": "medium",
            })

        # Statybinių atliekų išvežimas (renovacijai 3× daugiau)
        if bendras_plotas > 0:
            kiekis = round(bendras_plotas * 0.15, 1)  # 0.15 m³/m² (vs 0.05 naujam)
            additional.append({
                "aprasymas": "Statybinių atliekų išvežimas (renovacija)",
                "vnt": "m3", "kiekis": kiekis,
                "kategorija": "Renovacija — atliekos",
                "source": "STR 2.07.01:2003 (renovacija coefficient)",
                "confidence": "medium",
            })

    elif interior_subtype == "komercinis":
        # Komerciniam: papildomi šviestuvai, accessibility vonios
        # Šaltinis: STR 2.03.01:2019 (komercinių patalpų reikalavimai)

        # Daugiau šviestuvų (komerciniam reikalingas didesnis apšvietimas)
        kiekis = sviestuvai_total + len(rooms_calculated) * 2
        additional.append({
            "aprasymas": "Papildomi šviestuvai (komercinis apšvietimo standartas)",
            "vnt": "vnt", "kiekis": kiekis,
            "kategorija": "Apšvietimas — komercinis",
            "source": "STR 2.03.01:2019 + EN 12464-1",
            "confidence": "medium",
        })

        # Accessibility vonios (didesnės, papildomi turėklai)
        if dregnos:
            kiekis = len(dregnos)
            additional.append({
                "aprasymas": "Accessibility turėklai vonioje (neįgaliesiems)",
                "vnt": "kompl", "kiekis": kiekis,
                "kategorija": "Komercinis — accessibility",
                "source": "STR 2.03.01:2019",
                "confidence": "medium",
            })

        # Nukabinamos lubos (komerciniam standartas)
        if bendras_plotas > 0:
            kiekis = round(bendras_plotas * 0.6, 1)  # 60% ploto turi nukabinamas lubas
            additional.append({
                "aprasymas": "Nukabinamų lubų sistema (komercinis standartas)",
                "vnt": "m2", "kiekis": kiekis,
                "kategorija": "Lubos — komercinis",
                "source": "STR 2.03.01:2019",
                "confidence": "low",
            })

    # interior_subtype == "naujas" — joks papildomas modifier'is, default formules

    # ═══════════════════════════════════════════════════════════════════════
    # POST-PROCESS: kiekvienai pozicijai pridedam trace_type + trace_links.
    # SAFETY: jei kažkas nutinka, NESULAUŽOM additional — tik praleidžiam trace.
    # ═══════════════════════════════════════════════════════════════════════
    for pos in additional:
        try:
            trace_type = _classify_trace_type(
                pos.get("aprasymas", ""), pos.get("vnt", "")
            )
            pos["trace_type"] = trace_type
            pos["trace_links"] = _build_trace_links(
                pos, rooms_calculated, detected_symbols, trace_type,
            )
            if trace_type == "formula":
                pos["formula_explanation"] = _explain_formula(pos, totals)
        except Exception as e:
            # Trace failure neturi sulaužyti calculation
            print(f"[universal_engine] trace skip ({pos.get('aprasymas','?')[:30]}): {e}")
            pos["trace_type"] = "formula"
            pos["trace_links"] = []

    return additional


def calc_totals(rooms_calculated: list[dict]) -> dict:
    """Suminiai kiekiai per visą projektą."""
    totals = {
        "bendras_plotas_m2": 0.0,
        "dazymo_plotas_m2": 0.0,
        "gkp_lubu_standart_m2": 0.0,
        "gkp_lubu_virs_3m_m2": 0.0,
        "kampai_m": 0.0,
        "plyteles_sienos_m2": 0.0,
        "plyteles_grindys_m2": 0.0,
        "pvc_grindys_m2": 0.0,
        "isliginamasis_m2": 0.0,
        "grindjuostes_m": 0.0,
        "hidroizoliacijos_vnt": 0,
    }
    for r in rooms_calculated:
        totals["bendras_plotas_m2"] += r.get("plotas_m2", 0)
        totals["dazymo_plotas_m2"] += r.get("dazymo_plotas_m2", 0)
        totals["gkp_lubu_standart_m2"] += r.get("gkp_lubu_standart_m2", 0)
        totals["gkp_lubu_virs_3m_m2"] += r.get("gkp_lubu_virs_3m_m2", 0)
        totals["kampai_m"] += r.get("kampai_m", 0)
        totals["plyteles_sienos_m2"] += r.get("plyteles_sienos_m2", 0)
        totals["plyteles_grindys_m2"] += r.get("plyteles_grindys_m2", 0)
        totals["pvc_grindys_m2"] += r.get("pvc_grindys_m2", 0)
        totals["isliginamasis_m2"] += r.get("isliginamasis_m2", 0)
        totals["grindjuostes_m"] += r.get("grindjuostes_m", 0)
        if r.get("paskirtis") in ("vonia", "wc", "san", "katiline", "skalbykla"):
            totals["hidroizoliacijos_vnt"] += 1

    # Apvalinam
    return {k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()}


def extract_v8(rooms: list[dict],
                ceiling_height_m: float = 2.82,
                rules_override: dict | None = None,
                detected_symbols: dict | None = None) -> dict:
    """
    V8 entry point: gauna patalpų sąrašą (iš Vision), grąžina tikslius
    kiekius pagal universal industries taisykles.

    Args:
        rooms: [{nr, pavadinimas, paskirtis, plotas_m2, perimetras_m}, ...]
        ceiling_height_m: globalus default
        rules_override: vartotojo profilis (vėliau setup wizard)
        detected_symbols: AI Vision DETEKTUOTI simboliai per puslapio tipus
          (iš V9 detect_all_symbols_for_pdf). Format:
            {"by_type": {"rozetes": {"total": 32, "pages": [...]},
                         "klozetai": {"total": 2, ...}, ...}}
          Jei pateikta — additional_positions naudoja TIKRUS skaičius.
          Jei NĖRA — fallback į vidurkius su LOW confidence.

    Returns:
        {
          "rooms": [...],     # per-kambarį skaičiai
          "totals": {...},    # bendras
          "additional_positions": [...],  # CORE pozicijos su detected/fallback flag'u
          "rules_used": ROOM_TYPE_RULES,
        }
    """
    # Vartotojo prefs (flat) → per-paskirtis room rules
    # Jei rules_override jau yra per-paskirtis struktūra (testai), naudojame kaip yra.
    # Kitu atveju (frontend) konvertuojame.
    if rules_override and any(k in rules_override for k in (
        "bathroom_tile_height_m", "garazas_painted", "drabuzine_painted",
    )):
        room_rules = translate_user_prefs_to_room_rules(rules_override)
    else:
        room_rules = rules_override

    calculated = []
    for r in rooms:
        calculated.append(
            calc_room_quantities(r, ceiling_height_m, room_rules)
        )

    totals = calc_totals(calculated)

    # CORE pozicijos pagal industries standartus (NRM2/DIN/CSI/ANSI)
    # Naudojam detected_symbols jei pateikta (tikri skaičiai), kitu atveju
    # fallback į vidurkius su low confidence flag'u.
    additional_positions = calc_additional_positions(
        calculated, totals,
        user_prefs=rules_override,
        detected_symbols=detected_symbols,
    )

    return {
        "rooms": calculated,
        "totals": totals,
        "additional_positions": additional_positions,
        "rules_used": room_rules or ROOM_TYPE_RULES,
        "ceiling_height_m": ceiling_height_m,
        "engine": "v8_universal",
        "user_prefs_applied": bool(rules_override),
        "detected_symbols_used": bool(detected_symbols),
        "detected_symbols_summary": (
            {st: info.get("total", 0)
             for st, info in (detected_symbols or {}).get("by_type", {}).items()}
            if detected_symbols else {}
        ),
    }

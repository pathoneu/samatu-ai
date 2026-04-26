"""
V2.1 Phase 4 — Materials & Line Items.
Deterministic Python, no AI calls.
Uses material_conversion_coefficients from training_dataset_v2.json.
"""
import math
from typing import Any

from .scope_method import get_material_coefs

# rangovas standard pricing (EUR) per unit — placeholder until DB integration
_TOMAS_PRICES: dict[str, float] = {
    # Paint
    "standart_sienos_lubos": 7.50,
    "standart_sienos_lubos_virs_3m": 9.50,
    "premium_benjamin_moore_lubos": 14.00,
    "premium_benjamin_moore_sienos_lubos": 14.00,
    "premium_supreme_ultimate_sienos_lubos": 18.00,
    "molio_tinko_dekoras": 25.00,
    "stiklo_audinio_klijavimas": 8.00,
    "rotband_sausas_gipsinis_tinkas": 12.00,
    "rotband_sausas_gipsinis_tinkas_virs_3m": 15.00,
    "papildomas_sienu_glaistymas": 4.00,
    "duru_angos_beapvadines_paruosimas": 12.00,
    "durys_staktu_apdirbimas_gkp_glaistymas": 45.00,
    "durys_varcios_dazymas": 35.00,
    "angokrasciai_glaistymas_dazymas": 8.00,
    "moldingu_dazymas": 6.00,
    "nisu_glaistymas_dazymas": 8.00,
    "kampai_montavimas": 3.50,
    "sviestuvu_difuzoriu_apdirbimas_apvalus": 25.00,
    "sviestuvu_difuzoriu_apdirbimas_plysiniai": 30.00,
    "sviestuvu_apdirbimas": 15.00,
    "reviziniu_dureliu_apdirbimas": 35.00,
    "strabu_uztaisymas": 5.00,
    "stoglangiu_apdirbimas": 120.00,
    "duru_angos_siaurinimas_zeminimas": 50.00,
    "gkp_pjovimas_lubose_seselinei_siulei": 8.00,
    # GKP
    "lubos_standart_aukstis": 18.00,
    "lubos_virs_3m": 24.00,
    "lubos_laiptineje": 28.00,
    "pertvara_dviguba": 22.00,
    "pertvara_keturi_sluoksniai_apsiltinta": 35.00,
    "laidu_apsiuvimas_garaze": 12.00,
    "nisu_formavimas_led_apsvietimui": 15.00,
    "dezutes_wc_mechanizmams_paslepti": 85.00,
    "angokrasciai_apdirbimas_gkp": 18.00,
    "nisa_duše": 120.00,
    # Tiles
    "standartinio_formato_sienos_grindys": 22.00,
    "standartinio_formato_nisos_angokrasciai": 35.00,
    "1200x1200x6_sienos_grindys": 28.00,
    "1200x600x9_sienos_grindys": 25.00,
    "didziaformates_sienos_grindys": 35.00,
    "hidroizoliacija": 8.00,
    "nuolydzio_formavimas_duše": 150.00,
    "trapo_montavimas": 45.00,
    "lataku_montavimas": 55.00,
    "glaistymas_epoksidinis": 12.00,
    # Floors
    "parketlentes_klijavimas_45_eglute": 32.00,
    "parketlentes_klasikinis": 25.00,
    "pvc_grindys": 18.00,
    "grindjuostes_i_siena_ileistos": 12.00,
    "grindjuostes_paprastos_medines": 8.00,
    # Plumbing
    "wc_remas_paprastas": 85.00,
    "wc_remas_suleidziamas_i_siena": 180.00,
    "klozeto_bide_montavimas": 45.00,
    "bide_dusiukas_potinkine_dalis": 120.00,
    "bide_dusiukas_virstinkine_dalis": 45.00,
    "praustuvo_maisytuvas_potinkinis_montavimas": 150.00,
    "praustuvo_maisytuvas_virstinkine_dalis": 45.00,
    "dušo_maisytuvas_potinkinis": 180.00,
    "dušo_maisytuvas_virstinkine_dalis": 45.00,
    "vonios_maisytuvas_potinkinis": 160.00,
    "skalbimo_masinos_sifonas": 35.00,
    "gyvatukas_teno_pajungimas": 55.00,
    # Electrical
    "rozetes_jungiklio_komutavimas": 12.00,
    "skyliu_grezimas_betone_dezuciu": 8.00,
    "pakabinamu_sviestuvu_montavimas": 25.00,
    "led_juostos_komutavimas": 15.00,
    # Ventilation
    "rekuperatoriaus_montavimas": 350.00,
    "kondicionieriaus_irengimas": 280.00,
    # Site overhead
    "siukšliu_isvezimas": 180.00,
    "pastoliu_nuoma_virs_3m": 250.00,
    "dregmes_surinkejo_nuoma": 120.00,
}


def lookup_tomas_price(kategorija: str) -> float:
    return _TOMAS_PRICES.get(kategorija, 0.0)


def calculate_materials(phase2_merged: dict, project_class: str) -> dict:
    """
    Deterministic materials calculation from Phase 2 quantities.
    Uses training_dataset_v2.json material_conversion_coefficients.
    """
    coef = get_material_coefs()

    # Aggregate paint areas
    paint_standart = sum(
        i["kiekis"] for i in phase2_merged.get("paint_items", [])
        if i["kategorija"] == "standart_sienos_lubos"
    )
    paint_virs_3m = sum(
        i["kiekis"] for i in phase2_merged.get("paint_items", [])
        if i["kategorija"] == "standart_sienos_lubos_virs_3m"
    )
    paint_bm_lubos = sum(
        i["kiekis"] for i in phase2_merged.get("paint_items", [])
        if i["kategorija"] == "premium_benjamin_moore_lubos"
    )
    paint_bm_sienos = sum(
        i["kiekis"] for i in phase2_merged.get("paint_items", [])
        if i["kategorija"] in ("premium_benjamin_moore_sienos_lubos",)
    )
    stiklo_audinys = sum(
        i["kiekis"] for i in phase2_merged.get("paint_items", [])
        if i["kategorija"] == "stiklo_audinio_klijavimas"
    )

    gkp_standart = sum(
        i["kiekis"] for i in phase2_merged.get("gkp_items", [])
        if i["kategorija"] in ("lubos_standart_aukstis",)
    )
    gkp_virs_3m = sum(
        i["kiekis"] for i in phase2_merged.get("gkp_items", [])
        if i["kategorija"] == "lubos_virs_3m"
    )
    total_gkp = gkp_standart + gkp_virs_3m

    tiles_total = sum(
        i["kiekis"] for i in phase2_merged.get("tiles_items", [])
        if "sienos_grindys" in i["kategorija"]
    )

    # Paint calculations
    sienu_coef = coef.get("dazai_sienoms", {})
    padengimas = sienu_coef.get("padengimas_m2_per_l_per_sluoksni", 9.0)
    sluoksniai = sienu_coef.get("sluoksniu_skaicius", 2)

    dazai_standart_l = (paint_standart * sluoksniai / padengimas) if padengimas else 0
    dazai_virs3m_l = (paint_virs_3m * sluoksniai / padengimas) if padengimas else 0
    dazai_bm_l = ((paint_bm_lubos + paint_bm_sienos) * sluoksniai / padengimas) if padengimas else 0

    total_paintable = paint_standart + paint_virs_3m + paint_bm_lubos + paint_bm_sienos

    # Primer
    gruntas_coef = coef.get("gruntas", {})
    litru_per_m2 = gruntas_coef.get("litru_per_m2", 0.15)
    gruntas_l = total_paintable * litru_per_m2

    # Skimming (glaistas Q2 standard)
    glaistas_coef = coef.get("glaistas_Q2", {})
    glaistas_q2_rate = glaistas_coef.get("rezultatas_kg_per_m2", 1.25)
    maiso_svoris = glaistas_coef.get("maiso_svoris_kg", 25)
    glaistas_kg = total_paintable * glaistas_q2_rate
    glaistas_maisai = math.ceil(glaistas_kg / maiso_svoris) if maiso_svoris else 0

    # GKP sheets
    gk_coef = coef.get("gk_lapas", {})
    waste_factor = gk_coef.get("waste_factor", 1.10)
    lapo_plotas = gk_coef.get("vieno_lapo_plotas_m2", 3.0)
    gk_lapai = math.ceil(total_gkp * waste_factor / lapo_plotas) if lapo_plotas else 0

    # Tile adhesive
    klijai_coef = coef.get("plyteliu_klijai", {})
    klijai_kg = tiles_total * klijai_coef.get("kg_per_m2", 4.0)

    # Waterproofing
    hidro_area = sum(
        i["kiekis"] for i in phase2_merged.get("tiles_items", [])
        if i["kategorija"] == "hidroizoliacija"
    )
    hidro_coef = coef.get("hidroizoliacija", {})
    hidro_kg = hidro_area * hidro_coef.get("kg_per_m2_per_sluoksnis", 1.5) * hidro_coef.get("sluoksniu_skaicius", 2)

    # Glass fabric
    stiklo_coef = coef.get("stiklo_audinys", {})
    stiklo_bruto = stiklo_audinys * 1.10  # 10% waste

    return {
        "dazai_standart_l": round(dazai_standart_l, 1),
        "dazai_virs_3m_l": round(dazai_virs3m_l, 1),
        "dazai_benjamin_moore_l": round(dazai_bm_l, 1),
        "gruntas_l": round(gruntas_l, 1),
        "glaistas_q2_kg": round(glaistas_kg, 1),
        "glaistas_maisai_25kg": glaistas_maisai,
        "gk_lapai_vnt": gk_lapai,
        "plyteliu_klijai_kg": round(klijai_kg, 1),
        "hidroizoliacija_kg": round(hidro_kg, 1),
        "stiklo_audinys_bruto_m2": round(stiklo_bruto, 1),
        "total_paintable_m2": round(total_paintable, 1),
        "total_gkp_m2": round(total_gkp, 1),
        "total_tiles_m2": round(tiles_total, 1),
    }


def build_line_items(phase2_merged: dict) -> list[dict]:
    """
    Generate sąmatos line items from Phase 2 extracted items.
    Adds unit_price and total_eur per item.
    """
    items = []
    section_map = {
        "paint_items": "Sienų lubų glaistymas dažymas",
        "gkp_items": "Gipso kartono montavimas",
        "tiles_items": "Plytelių darbai",
        "floor_items": "Grindų danga",
        "plumbing_items": "Santechnikos darbai",
        "electrical_items": "Elektros darbai",
        "ventilation_items": "Rekuperacija / HVAC",
        "special_works_items": "Specialūs darbai",
        "site_overhead_items": "Statybvietės išlaidos",
    }

    for section_key, section_name in section_map.items():
        for item in phase2_merged.get(section_key, []):
            kategorija = item.get("kategorija", "")
            kiekis = float(item.get("kiekis", 0))
            unit = item.get("unit", "vnt")
            price = lookup_tomas_price(kategorija)
            items.append({
                "skyrius": section_name,
                "kategorija": kategorija,
                "kiekis": round(kiekis, 3),
                "unit": unit,
                "unit_price_eur": price,
                "total_eur": round(kiekis * price, 2),
                "notes": item.get("notes"),
            })

    return items


def calculate_phase4(phase2_merged: dict, project_class: str) -> dict:
    """Main Phase 4 entry point."""
    materials = calculate_materials(phase2_merged, project_class)
    line_items = build_line_items(phase2_merged)
    total_darbo_kaina = sum(i["total_eur"] for i in line_items)
    return {
        "materials": materials,
        "line_items": line_items,
        "total_darbo_kaina_eur": round(total_darbo_kaina, 2),
        "total_su_pvm_eur": round(total_darbo_kaina * 1.21, 2),
    }

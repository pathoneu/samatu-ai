"""
Materials calculator — deterministic, no AI.
Converts validated quantities into material purchase lists.
"""
import math


def calculate_materials(quantities: dict, training_data: dict) -> dict:
    """
    Convert area/length quantities into specific material quantities.
    Uses coefficients from training_dataset.json material_conversion_coefficients.
    """
    coef = training_data.get("material_conversion_coefficients", {})

    dazomas_m2 = quantities.get("dazomas_plotas_m2") or 0
    lubos_m2 = quantities.get("lubu_plotas_m2") or 0
    gkp_m2 = quantities.get("gkp_lubu_m2") or 0
    plyteles_m2 = quantities.get("plyteliu_plotas_m2") or 0

    # Paint — walls (2 coats)
    sienu_dazai = coef.get("dazai_sienoms", {})
    padengimas_sienos = sienu_dazai.get("padengimas_m2_per_l_per_sluoksni", 9.0)
    dazai_sienoms_l = (dazomas_m2 * 2 / padengimas_sienos) if padengimas_sienos else 0

    # Paint — ceilings (2 coats)
    lubu_dazai = coef.get("dazai_luboms", {})
    padengimas_lubos = lubu_dazai.get("padengimas_m2_per_l_per_sluoksni", 10.0)
    dazai_luboms_l = (lubos_m2 * 2 / padengimas_lubos) if padengimas_lubos else 0

    # Primer (gruntas)
    gruntas_coef = coef.get("gruntas", {})
    litru_per_m2 = gruntas_coef.get("litru_per_m2", 0.15)
    gruntas_l = (dazomas_m2 + lubos_m2) * litru_per_m2

    # Skimming (glaistas Q2)
    glaistas_coef = coef.get("glaistas_Q2", {})
    glaistas_kg_per_m2 = glaistas_coef.get("rezultatas_kg_per_m2", 1.5)
    maiso_svoris = glaistas_coef.get("maiso_svoris_kg", 25)
    glaistas_kg = dazomas_m2 * glaistas_kg_per_m2
    glaistas_maisai = math.ceil(glaistas_kg / maiso_svoris) if maiso_svoris else 0

    # Drywall sheets (GKP)
    gk_coef = coef.get("gk_lapas", {})
    waste_factor = gk_coef.get("waste_factor", 1.10)
    lapo_plotas = gk_coef.get("vieno_lapo_plotas_m2", 3.0)
    gk_lapai = math.ceil(gkp_m2 * waste_factor / lapo_plotas) if lapo_plotas else 0

    # Tile adhesive
    klijai_coef = coef.get("plyteliu_klijai", {})
    kg_per_m2 = klijai_coef.get("kg_per_m2", 5.5)
    plyteliu_klijai_kg = plyteles_m2 * kg_per_m2

    return {
        "dazai_sienoms_l": round(dazai_sienoms_l, 1),
        "dazai_luboms_l": round(dazai_luboms_l, 1),
        "gruntas_l": round(gruntas_l, 1),
        "glaistas_q2_kg": round(glaistas_kg, 1),
        "glaistas_maisai_25kg": glaistas_maisai,
        "gk_lapai_vnt": gk_lapai,
        "plyteliu_klijai_kg": round(plyteliu_klijai_kg, 1),
    }

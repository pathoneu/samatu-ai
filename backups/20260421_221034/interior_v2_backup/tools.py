"""
V2.1 Tool schemas for all 10 Phase 2 extractors + Phase 1 analyzer + Phase 3 validator.
"""

PROJECT_ANALYZER_TOOL = {
    "name": "analyze_project_context",
    "description": "Analyze Lithuanian construction drawings to extract room list, classify complexity, identify special features",
    "input_schema": {
        "type": "object",
        "required": ["patalpos", "bendras_plotas_m2", "sudetingumo_klase", "features", "confidence"],
        "properties": {
            "patalpos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["nr", "pavadinimas", "plotas_m2"],
                    "properties": {
                        "nr": {"type": "string"},
                        "pavadinimas": {"type": "string"},
                        "plotas_m2": {"type": "number"},
                    },
                },
            },
            "bendras_plotas_m2": {"type": "number"},
            "garazo_plotas_m2": {"type": ["number", "null"]},
            "lubu_aukstis_m": {"type": "number", "description": "Default 2.8 if not specified"},
            "aukstesniu_lubu_patalpos": {"type": "array", "items": {"type": "string"}},
            "sudetingumo_klase": {
                "type": "string",
                "enum": ["small_apartment", "medium_house", "complex_house", "premium"],
            },
            "features": {
                "type": "object",
                "properties": {
                    "arkos_ar_apvalios_formos": {"type": "boolean"},
                    "lubu_nisos_led": {"type": "boolean"},
                    "aukstesniu_nei_3m": {"type": "boolean"},
                    "sanitariniu_patalpu_skaicius": {"type": "integer"},
                    "stoglangiai": {"type": "boolean"},
                    "garazas_virs_2m_auksciu": {"type": "boolean"},
                    "premium_pozymiai": {"type": "array", "items": {"type": "string"}},
                },
            },
            "scope_type": {
                "type": "string",
                "enum": ["full_project", "partial_paint_only", "partial_paint_and_tiles", "partial_other"],
                "description": "If drawings suggest only partial scope, flag here",
            },
            "confidence": {
                "type": "number",
                "description": "0-1. <0.5 means room table not found",
            },
        },
    },
}

PARTITION_PLAN_TOOL = {
    "name": "extract_partition_plan_data",
    "description": "Extract corners, doors, windows, GKP niches from partition plan",
    "input_schema": {
        "type": "object",
        "required": ["visu_kampu_vnt", "isoriniu_kampu_vnt"],
        "properties": {
            "visu_kampu_vnt": {
                "type": "integer",
                "description": "ALL vertical corners (inner + outer). P1=580m, P2=202m, P5=124m reference.",
            },
            "isoriniu_kampu_vnt": {"type": "integer"},
            "vidiniu_kampu_vnt": {"type": "integer"},
            "arkos_ar_puslankiai": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipas": {"type": "string", "enum": ["arka", "puslankis", "apvalus_kampas"]},
                        "spindulys_mm": {"type": "number"},
                        "aukstis_mm": {"type": "number"},
                    },
                },
            },
            "doors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "room_nr": {"type": "string"},
                        "plotis_mm": {"type": "number"},
                        "aukstis_mm": {"type": "number"},
                        "beapvadine": {"type": "boolean"},
                    },
                },
            },
            "langai": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "room_nr": {"type": "string"},
                        "plotis_mm": {"type": "number"},
                        "aukstis_mm": {"type": "number"},
                    },
                },
            },
            "gkp_nisos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ilgis_mm": {"type": "number"},
                        "room_nr": {"type": "string"},
                    },
                },
            },
        },
    },
}

WALL_ELEVATIONS_TOOL = {
    "name": "extract_wall_elevations",
    "description": "Extract wall sections (išklotinės) with dimensions, paint/tile zones per room",
    "input_schema": {
        "type": "object",
        "required": ["wall_sections"],
        "properties": {
            "wall_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "room_nr", "plotis_mm", "aukstis_mm"],
                    "properties": {
                        "id": {"type": "string"},
                        "room_nr": {"type": "string"},
                        "plotis_mm": {"type": "number"},
                        "aukstis_mm": {"type": "number"},
                        "tipas": {
                            "type": "string",
                            "enum": ["dazoma", "plytelemis", "medinis", "dekoratyvinis", "misras"],
                        },
                        "zones": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tipas": {"type": "string"},
                                    "plotas_m2": {"type": "number"},
                                },
                            },
                        },
                        "openings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tipas": {"type": "string", "enum": ["durys", "langas", "niša"]},
                                    "plotis_mm": {"type": "number"},
                                    "aukstis_mm": {"type": "number"},
                                },
                            },
                        },
                    },
                },
            }
        },
    },
}

CEILING_PLAN_TOOL = {
    "name": "extract_ceiling_plan",
    "description": "Extract ceiling GKP items, niches, lights, diffusers, access doors using sparse items array",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "lubos_standart_aukstis",
                                "lubos_virs_3m",
                                "lubos_laiptineje",
                                "laidu_apsiuvimas_garaze",
                                "nisu_formavimas_led_apsvietimui",
                                "difuzoriu_montavimas_apvalus",
                                "difuzoriu_montavimas_plysiniai",
                                "sviestuvu_montavimas",
                                "sviestuvu_led_profiliu_montavimas",
                                "reviziniu_dureliu_montavimas_600x600",
                                "reviziniu_dureliu_montavimas_1500x500",
                                "reviziniu_dureliu_montavimas_300x300",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]},
                        "room_nr": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                    },
                },
            },
            "gkp_plotas_standartinis_m2": {"type": "number"},
            "gkp_plotas_virs_3m_m2": {"type": "number"},
        },
    },
}

FLOOR_PLAN_TOOL = {
    "name": "extract_floor_plan",
    "description": "Extract floor coverings — parquet, tiles, PVC, rubber by area and type",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "parketlentes_klijavimas_45_eglute",
                                "parketlentes_klasikinis",
                                "pvc_grindys",
                                "isliginamasis_sluoksnis",
                                "grindjuostes_i_siena_ileistos",
                                "grindjuostes_paprastos_medines",
                                "grindjuostes_aliuminio",
                                "palangiu_montavimas",
                                "guminis_dangos_montavimas_garaze",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m"]},
                    },
                },
            }
        },
    },
}

PLUMBING_TOOL = {
    "name": "extract_plumbing_points",
    "description": "Extract plumbing fixtures: potinkinis (concealed) vs virstinkine (surface)",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "wc_remas_paprastas",
                                "wc_remas_suleidziamas_i_siena",
                                "klozeto_bide_montavimas",
                                "bide_dusiukas_potinkine_dalis",
                                "bide_dusiukas_virstinkine_dalis",
                                "praustuvo_maisytuvas_potinkinis_montavimas",
                                "praustuvo_maisytuvas_virstinkine_dalis",
                                "dušo_maisytuvas_potinkinis",
                                "dušo_maisytuvas_virstinkine_dalis",
                                "dušo_sistema_potinkine",
                                "vonios_maisytuvas_potinkinis",
                                "vonios_maisytuvas_virstinkine_dalis",
                                "skalbimo_masinos_sifonas",
                                "skalbimo_masinos_montavimas",
                                "dziovyklės_montavimas",
                                "gyvatukas_teno_pajungimas",
                                "plautuves_montavimas",
                                "vandens_tasas_laistymui",
                                "lauko_laistymo_ciaupas",
                                "santechnikos_tasku_koregavimas",
                                "vandens_mazgo_demontavimas_sumontavimas",
                                "kondicionieriaus_sifono_irengimas",
                                "trasu_kondicionieriams_irengimas",
                                "lataku_montavimas_vonia",
                            ],
                        },
                        "kiekis": {"type": "integer"},
                        "unit": {"type": "string", "enum": ["vnt"]},
                        "room_nr": {"type": ["string", "null"]},
                    },
                },
            }
        },
    },
}

ELECTRICAL_TOOL = {
    "name": "extract_electrical_points",
    "description": "Extract electrical points — outlets, switches, cable runs, automated breakers",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "rozetes_jungiklio_komutavimas",
                                "skyliu_grezimas_betone_dezuciu",
                                "skyliu_grezimas_gkp_dezuciu",
                                "skyliu_grezimas_sviestuvams",
                                "esamu_kabeliu_koregavimas_nauju_kabeliavimas",
                                "automatiniu_jungikliu_montavimas_e_skyde",
                                "pakabinamu_sviestuvu_montavimas",
                                "led_juostos_komutavimas",
                                "signalizacijos_davikliu_pajungimas_languose",
                                "smulkūs_el_darbai",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m"]},
                    },
                },
            }
        },
    },
}

PAINT_AND_GKP_TOOL = {
    "name": "extract_paint_and_gkp",
    "description": "Extract paint/plaster areas AND GKP drywall construction from wall elevations and partition plans",
    "input_schema": {
        "type": "object",
        "required": ["paint_items", "gkp_items"],
        "properties": {
            "paint_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "standart_sienos_lubos",
                                "standart_sienos_lubos_virs_3m",
                                "premium_benjamin_moore_lubos",
                                "premium_benjamin_moore_sienos_lubos",
                                "premium_supreme_ultimate_sienos_lubos",
                                "molio_tinko_dekoras",
                                "stiklo_audinio_klijavimas",
                                "rotband_sausas_gipsinis_tinkas",
                                "rotband_sausas_gipsinis_tinkas_virs_3m",
                                "papildomas_sienu_glaistymas",
                                "duru_angos_beapvadines_paruosimas",
                                "durys_staktu_apdirbimas_gkp_glaistymas",
                                "durys_varcios_dazymas",
                                "angokrasciai_glaistymas_dazymas",
                                "moldingu_dazymas",
                                "nisu_glaistymas_dazymas",
                                "kampai_montavimas",
                                "sviestuvu_difuzoriu_apdirbimas_apvalus",
                                "sviestuvu_difuzoriu_apdirbimas_plysiniai",
                                "sviestuvu_apdirbimas",
                                "reviziniu_dureliu_apdirbimas",
                                "strabu_uztaisymas",
                                "stoglangiu_apdirbimas",
                                "duru_angos_siaurinimas_zeminimas",
                                "gkp_pjovimas_lubose_seselinei_siulei",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]},
                        "room_nr": {"type": ["string", "null"]},
                    },
                },
            },
            "gkp_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "lubos_standart_aukstis",
                                "lubos_virs_3m",
                                "lubos_laiptineje",
                                "lubos_katilineje_betono_valymas",
                                "pertvara_dviguba",
                                "pertvara_keturi_sluoksniai_apsiltinta",
                                "laidu_apsiuvimas_garaze",
                                "nisu_formavimas_led_apsvietimui",
                                "dezutes_wc_mechanizmams_paslepti",
                                "dezutes_wc_mechanizmams_paslepti_dviguba",
                                "dezutes_ant_lubu_zeminimas",
                                "pertvareles_lentynoms_dušo_kabinoje",
                                "pasleptu_duru_staktu_apdirbimas",
                                "difuzoriu_montavimas_apvalus",
                                "difuzoriu_montavimas_plysiniai",
                                "sviestuvu_montavimas",
                                "sviestuvu_led_profiliu_montavimas",
                                "reviziniu_dureliu_montavimas_600x600",
                                "reviziniu_dureliu_montavimas_1500x500",
                                "reviziniu_dureliu_montavimas_300x300",
                                "angokrasciai_apdirbimas_gkp",
                                "nisa_duše",
                                "gkp_klijavimas_ant_sienos_katilineje",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]},
                    },
                },
            },
        },
    },
}

TILES_TOOL = {
    "name": "extract_tiles",
    "description": "Extract tile work by size category and location",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "standartinio_formato_sienos_grindys",
                                "standartinio_formato_nisos_angokrasciai",
                                "1200x1200x6_sienos_grindys",
                                "1200x1200x6_nisos_angokrasciai",
                                "1200x600x9_sienos_grindys",
                                "1200x600x9_nisos_angokrasciai",
                                "didziaformates_sienos_grindys",
                                "didziaformates_nisos_angokrasciai",
                                "iki_120x60_sienos_grindys",
                                "glaistymas_epoksidinis",
                                "hidroizoliacija",
                                "nuolydzio_formavimas_duše",
                                "lataku_montavimas",
                                "trapo_montavimas",
                                "skyliu_grezimas",
                                "kampu_silikonavimas",
                                "supjovimas_45_laipsniu",
                                "plintusu_supjovimas",
                                "nisu_lentyneles_montavimas",
                                "laiptu_irengimas_garaze",
                                "pripjovimas_prie_trapo_garaze",
                                "aliuminio_apdailinio_kampo_montavimas_garaze",
                                "garazo_plyteles_komplektas",
                                "isliginamojo_pylimas",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "m2/m", "vnt"]},
                        "room_nr": {"type": ["string", "null"]},
                    },
                },
            }
        },
    },
}

VENTILATION_TOOL = {
    "name": "extract_ventilation",
    "description": "Extract ventilation/HVAC high-level items. Detailed duct breakdowns require separate HVAC drawings.",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "rekuperatoriaus_montavimas",
                                "rekuperacijos_ortakiu_irengimas",
                                "kondicionieriaus_irengimas",
                                "ortakis_spiro_d160",
                                "ortakis_spiro_d125",
                                "ortakis_spiro_d100",
                                "alkune_45_d160",
                                "alkune_45_d125",
                                "alkune_45_d100",
                                "alkune_90_d160",
                                "alkune_90_d125",
                                "alkune_90_d100",
                                "mova_d160",
                                "mova_d125",
                                "mova_d100",
                                "pereiga_160_125",
                                "pereiga_125_100",
                                "trisakis_125_125",
                                "trisakis_100_100",
                                "trisakis_160_160",
                                "trisakis_125_100",
                                "plysinis_priglaistomas_difuzorius_egrovent_1m",
                                "apvalus_potinkinis_difuzorius_egrovent_d125",
                                "apvalus_potinkinis_difuzorius_egrovent_d100",
                                "montavimo_darbai_rekuperacijos",
                                "pagalbinės_montavimo_medziagos",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m", "komp"]},
                    },
                },
            },
            "has_detailed_hvac_plan": {
                "type": "boolean",
                "description": "True if separate HVAC engineering plan was part of input",
            },
        },
    },
}

SPECIAL_WORKS_TOOL = {
    "name": "extract_special_works_and_overhead",
    "description": "Extract custom decorative works, door modifications, site overhead",
    "input_schema": {
        "type": "object",
        "properties": {
            "special_works_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "duru_angos_platinimas",
                                "sienos_paruosimas_dekorui",
                                "sienos_dekoravimas_custom",
                                "duru_rankenos_keitimas",
                                "jungikliai_rozetes_komplektas_medziagos",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m2", "komp"]},
                        "description": {"type": "string"},
                    },
                },
            },
            "site_overhead_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "siukšliu_isvezimas",
                                "pastoliu_nuoma_virs_3m",
                                "dregmes_surinkejo_nuoma",
                            ],
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m3", "dd"]},
                    },
                },
            },
        },
    },
}

VALIDATOR_TOOL = {
    "name": "validate_and_finalize_v2",
    "description": "Validate Phase 2 quantities against training data ratios and return final validated output",
    "input_schema": {
        "type": "object",
        "required": ["validated_items", "warnings", "confidence_level"],
        "properties": {
            "validated_items": {
                "type": "object",
                "description": "Dict of kategorija → validated kiekis. Same structure as Phase 2 merged output.",
                "additionalProperties": {"type": "number"},
            },
            "warnings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                        "description": {"type": "string"},
                        "actual_value": {"type": ["number", "null"]},
                        "expected_range": {"type": ["string", "null"]},
                    },
                },
            },
            "confidence_level": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "scope_confirmed": {
                "type": "string",
                "enum": ["full_project", "partial_paint_only", "partial_paint_and_tiles", "partial_other"],
            },
            "similar_projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "projekto_id": {"type": "string"},
                        "similarity_reason": {"type": "string"},
                    },
                },
            },
        },
    },
}

# Maps page_type → tool for Phase 2
TOOL_FOR_PAGE_TYPE: dict = {
    "partition_plan": PARTITION_PLAN_TOOL,
    "wall_elevations": PAINT_AND_GKP_TOOL,
    "ceiling_plan": CEILING_PLAN_TOOL,
    "floor_plan": FLOOR_PLAN_TOOL,
    "plumbing_plan": PLUMBING_TOOL,
    "electrical_plan": ELECTRICAL_TOOL,
    "tiles_layout": TILES_TOOL,
    "ventilation_plan": VENTILATION_TOOL,
}

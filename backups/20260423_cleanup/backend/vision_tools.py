"""
V2 Vision pipeline — Anthropic Tool Use schemas.
All tool definitions for Phase 1, Phase 2, Phase 3.
"""

PROJECT_ANALYZER_TOOL = {
    "name": "analyze_project_context",
    "description": "Analyze Lithuanian construction project drawings to extract room list, classify complexity, and identify special features",
    "input_schema": {
        "type": "object",
        "required": ["patalpos", "bendras_plotas_m2", "sudetingumo_klase", "features"],
        "properties": {
            "patalpos": {
                "type": "array",
                "description": "Patalpų eksplikacija - EVERY room from the room table",
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
            "bendras_plotas_m2": {
                "type": "number",
                "description": "Total floor area excluding garage",
            },
            "garazo_plotas_m2": {
                "type": ["number", "null"],
                "description": "Garage area if present, null otherwise",
            },
            "lubu_aukstis_m": {
                "type": "number",
                "description": "Standard ceiling height. Default 2.8m if not specified.",
            },
            "aukstesniu_lubu_patalpos": {
                "type": "array",
                "description": "Room numbers with ceiling height > 3m",
                "items": {"type": "string"},
            },
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
                    "premium_pozymiai": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "confidence": {
                "type": "number",
                "description": "Confidence 0-1. If room table not found, confidence < 0.5",
            },
        },
    },
}

PARTITION_PLAN_TOOL = {
    "name": "extract_partition_plan_data",
    "description": "Extract corners, doors, windows, and GKP niches from partition plan",
    "input_schema": {
        "type": "object",
        "required": ["visu_kampu_vnt", "isoriniu_kampu_vnt", "doors", "langai"],
        "properties": {
            "visu_kampu_vnt": {
                "type": "integer",
                "description": "ALL vertical wall corners - both convex (outer) AND concave (inner)",
            },
            "isoriniu_kampu_vnt": {
                "type": "integer",
                "description": "Only OUTER (convex) corners",
            },
            "vidiniu_kampu_vnt": {
                "type": "integer",
                "description": "Only INNER (concave) corners",
            },
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
    "description": "Extract wall sections (išklotinės) with dimensions, zones, and openings per room",
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
                        "id": {"type": "string", "description": "Section ID like 'a1', 'b2'"},
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
                                    "plotis_mm": {"type": "number"},
                                    "aukstis_mm": {"type": "number"},
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
    "description": "Extract ceiling information - GKP areas, niches, lights, diffusers",
    "input_schema": {
        "type": "object",
        "properties": {
            "gkp_plotas_standartinis_m2": {
                "type": "number",
                "description": "Total GKP ceiling area at standard height",
            },
            "gkp_plotas_virs_3m_m2": {
                "type": "number",
                "description": "GKP ceiling area for rooms with ceilings >3m",
            },
            "nisos_led_m": {
                "type": "number",
                "description": "Total length of LED niches in meters",
            },
            "difuzoriu_skaicius": {
                "type": "object",
                "properties": {
                    "apvalus": {"type": "integer"},
                    "plysiniai": {"type": "integer"},
                },
            },
            "sviestuvu_skaicius": {
                "type": "integer",
                "description": "Total embedded/recessed lights",
            },
            "reviziniu_dureliu": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "matmenys": {"type": "string"},
                        "kiekis": {"type": "integer"},
                    },
                },
            },
        },
    },
}

FLOOR_PLAN_TOOL = {
    "name": "extract_floor_plan",
    "description": "Extract floor coverings - parquet, tiles, PVC by area",
    "input_schema": {
        "type": "object",
        "properties": {
            "parketlentes_m2": {"type": "number"},
            "parketlentes_rastas": {"type": "string", "description": "chevron, eglute, klasikinis, etc."},
            "plyteles_grindyse_m2": {"type": "number"},
            "pvc_grindys_m2": {"type": "number"},
            "kilimas_m2": {"type": "number"},
            "terasa_m2": {"type": "number"},
            "grindjuosciu_tipai": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipas": {"type": "string", "enum": ["ileistos", "paprastos", "aliuminio"]},
                        "ilgis_m": {"type": "number"},
                    },
                },
            },
        },
    },
}

PLUMBING_TOOL = {
    "name": "extract_plumbing_points",
    "description": "Extract plumbing fixture points by type and location",
    "input_schema": {
        "type": "object",
        "properties": {
            "wc_remai_vnt": {"type": "integer"},
            "wc_remai_ileidziami_sienon_vnt": {"type": "integer"},
            "praustuvu_maisytuvai_potinkiniai_vnt": {"type": "integer"},
            "dusu_maisytuvai_potinkiniai_vnt": {"type": "integer"},
            "vonios_maisytuvai_vnt": {"type": "integer"},
            "bide_dusiukai_vnt": {"type": "integer"},
            "skalbimo_masinos_sifonai_vnt": {"type": "integer"},
            "gyvatukai_vnt": {"type": "integer"},
            "lauko_ciaupai_vnt": {"type": "integer"},
            "trapai_lanakai_vnt": {"type": "integer"},
            "kondicionieriu_trasos_vnt": {"type": "integer"},
        },
    },
}

ELECTRICAL_TOOL = {
    "name": "extract_electrical_points",
    "description": "Extract electrical points - outlets, switches, LED strips",
    "input_schema": {
        "type": "object",
        "properties": {
            "rozetes_vnt": {"type": "integer"},
            "jungikliai_vnt": {"type": "integer"},
            "rozetes_jungikliai_total_vnt": {
                "type": "integer",
                "description": "Total - used in estimates as single line",
            },
            "led_juostos_m": {"type": "number"},
            "sviestuvu_iskaiciai_vnt": {"type": "integer"},
            "lauko_rozetes_vnt": {"type": "integer"},
            "trifazes_rozetes_vnt": {"type": "integer"},
            "signalizacijos_davikliu_vnt": {"type": "integer"},
        },
    },
}

VALIDATOR_TOOL = {
    "name": "validate_and_finalize",
    "description": "Validate extracted quantities against expected ratios for the project class",
    "input_schema": {
        "type": "object",
        "required": ["validated_quantities", "warnings", "confidence_level"],
        "properties": {
            "validated_quantities": {
                "type": "object",
                "properties": {
                    "dazomas_plotas_m2": {"type": "number"},
                    "lubu_plotas_m2": {"type": "number"},
                    "sienos_neto_m2": {"type": "number"},
                    "kampai_m": {"type": "number"},
                    "angokrasciai_m": {"type": "number"},
                    "plyteliu_plotas_m2": {"type": "number"},
                    "gkp_lubu_m2": {"type": "number"},
                    "grindjuosciu_ilgis_m": {"type": "number"},
                },
            },
            "warnings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string"},
                        "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                        "description": {"type": "string"},
                        "actual_value": {"type": "number"},
                        "expected_range": {"type": "string"},
                    },
                },
            },
            "confidence_level": {
                "type": "string",
                "enum": ["high", "medium", "low"],
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

TOOL_FOR_PAGE_TYPE: dict = {
    "pertvarų": PARTITION_PLAN_TOOL,
    "išklotinė": WALL_ELEVATIONS_TOOL,
    "lubų": CEILING_PLAN_TOOL,
    "grindų": FLOOR_PLAN_TOOL,
    "santechnikos": PLUMBING_TOOL,
    "rozecių": ELECTRICAL_TOOL,
    "apšvietimo": ELECTRICAL_TOOL,
}

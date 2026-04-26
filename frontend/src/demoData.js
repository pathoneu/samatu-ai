// Demo project seeded on first load for new users.
// Based on Beržų g. 24 interior design project (17-page PDF, 11 rooms).

export const DEMO_PROJECTS = [
  {
    id: "demo-berzai-001",
    created_date: "2025-01-28T10:00:00.000Z",
    name: "Beržų g. 24 — interjero projektas",
    company_name: "UAB Sąmatų AI Demo",
    tipas: "interjeras",
    status: "ready",
    rows: [],
    total_rows: 11,
    total_value: 0,

    patalpos: [
      { nr: "101", pavadinimas: "Tambūras",           plotas_m2: 11.01, lubu_aukstis_mm: 2800, lubu_tipas: "GKP" },
      { nr: "102", pavadinimas: "Svetainė / virtuvė", plotas_m2: 53.18, lubu_aukstis_mm: 3400, lubu_tipas: "GKP",
        grindu_danga: "parketlentės",
        sienu_apdaila: [
          { tipas: "dažymas",  plotas_m2: 82.4 },
          { tipas: "plytelės", plotas_m2: 18.6 },
        ]
      },
      { nr: "103", pavadinimas: "Koridorius",         plotas_m2: 13.98, lubu_aukstis_mm: 2800, lubu_tipas: "GKP" },
      { nr: "104", pavadinimas: "Darbo kambarys",     plotas_m2: 16.74, lubu_aukstis_mm: 2800,
        grindu_danga: "parketlentės",
        sienu_apdaila: [{ tipas: "dažymas", plotas_m2: 34.2 }]
      },
      { nr: "105", pavadinimas: "Garažas",            plotas_m2: 20.94, lubu_aukstis_mm: 3000 },
      { nr: "106", pavadinimas: "Skalbykla",          plotas_m2: 5.55,  lubu_aukstis_mm: 2800,
        grindu_danga: "plytelės",
        sienu_apdaila: [{ tipas: "plytelės", plotas_m2: 14.4 }]
      },
      { nr: "107", pavadinimas: "Vyrų san. mazgas",   plotas_m2: 5.81,  lubu_aukstis_mm: 2800,
        grindu_danga: "plytelės",
        sienu_apdaila: [{ tipas: "plytelės", plotas_m2: 15.2 }]
      },
      { nr: "108", pavadinimas: "Berniuko kambarys",  plotas_m2: 17.22, lubu_aukstis_mm: 2800,
        grindu_danga: "parketlentės",
        sienu_apdaila: [
          { tipas: "dažymas",  plotas_m2: 36.4 },
          { tipas: "tapetai",  plotas_m2: 9.8 },
        ]
      },
      { nr: "109", pavadinimas: "Berniuko kambarys",  plotas_m2: 17.04, lubu_aukstis_mm: 2800,
        grindu_danga: "parketlentės",
        sienu_apdaila: [
          { tipas: "dažymas",  plotas_m2: 35.8 },
          { tipas: "tapetai",  plotas_m2: 9.6 },
        ]
      },
      { nr: "110", pavadinimas: "Miegamasis",         plotas_m2: 24.53, lubu_aukstis_mm: 2800,
        grindu_danga: "parketlentės",
        sienu_apdaila: [
          { tipas: "dažymas",  plotas_m2: 44.6 },
          { tipas: "medžio lukštas", plotas_m2: 11.2 },
        ]
      },
      { nr: "111", pavadinimas: "Tėvų vonia",         plotas_m2: 9.98,  lubu_aukstis_mm: 2800,
        grindu_danga: "plytelės",
        sienu_apdaila: [
          { tipas: "plytelės", plotas_m2: 24.8 },
          { tipas: "veidrodis", plotas_m2: 3.2 },
        ]
      },
    ],

    skaiciavimai: {
      dazomas_plotas: {
        sienos_m2: 343.1,
        lubos_m2:  165.6,
        viso_m2:   508.7,
        pastaba: "Bruto atėmus plytelių/plokščių/angų zonas (iš išklotinių matmenų)",
      },
      plyteles_m2:  72.4,
      plokstes_m2:  11.2,
      glaistymo_kampai: {
        isoriniu_kampu_vnt:  4,
        vidutinis_aukstis_m: 2.93,
        viso_m:              11.7,
      },
      angokrasciai: {
        langu_vnt: 0,
        duru_vnt:  3,
        viso_m:    15.5,
        viso_m_x2: 31.0,
        details: [
          { tipas: "durys", plotis_m: 0.9, aukstis_m: 2.8, perimetras_m: 6.5 },
          { tipas: "durys", plotis_m: 0.8, aukstis_m: 2.2, perimetras_m: 5.2 },
          { tipas: "durys", plotis_m: 0.8, aukstis_m: 2.2, perimetras_m: 5.2 },
        ],
      },
      lubu_perimetras: {
        viso_m:            161.8,
        skaiciavimo_budas: "iš išklotinių matmenų",
      },
      uzuolaidu_nisos: {
        viso_m:  3.5,
        details: [
          { vieta: "102 pietų siena", ilgis_mm: 3500 },
        ],
      },
    },

    papildomi_kiekiai: {
      plyteles_m2:     72.4,
      parketlentes_m2: 128.7,
      grindjuostes_m:  92.5,
      led_juostos_m:   45.0,
      gkp_lubos_m2:    88.3,
      led_nisos_m:     23.0,
    },

    sienu_apdaila: {
      "dažymas":       233.4,
      "plytelės":       72.4,
      "medžio lukštas": 11.2,
      "tapetai":        19.4,
      "veidrodis":       3.2,
    },

    lubu_data: {
      gkp_m2:            88.3,
      led_nisu_m:        23.0,
      uzuolaidu_nisu_m:   3.5,
      gkp_dezuciu_m:     12.0,
    },

    grindys: {
      medžiagos: [
        { medžiaga: "parketlentės",                     patalpos: ["102","104","108","109","110"], plotas_m2: 128.7 },
        { medžiaga: "plytelės Living Ceramics Vonn Light 120×120 cm", patalpos: ["106","107","111"], plotas_m2: 21.3 },
      ],
      grindjuostes_m:  92.5,
      parketlentes_m2: 128.7,
    },

    elektra: {
      rozetes_vnt:               45,
      jungikliai_vnt:            18,
      interneto_rozetes_vnt:      8,
      antenos_vnt:                2,
      usb_c_vnt:                  1,
      termostatai_vnt:           10,
      prietaisu_pajungimai_vnt:   6,
      vartai_vnt:                 1,
    },

    santechnika: {
      wc_remai_vnt:           2,
      duso_sistemos_vnt:      2,
      praustuves_vnt:         3,
      vonios_maistuvai_vnt:   1,
      skalbimo_masinos_vnt:   1,
      trapai_vnt:             2,
      kondicionieriai_vnt:    5,
      maistuvai_vnt:          4,
    },

    apsvietimas: {
      ileidziami_sviestuvai_vnt:   35,
      pakabinami_sviestuvai_vnt:    4,
      sieniniai_sviestuvai_vnt:     8,
      pavirsiniai_sviestuvai_vnt:   2,
      led_juostos_m:               45,
      judesio_davikliai_vnt:        3,
      gaisro_davikliai_vnt:         6,
      garso_koloneles_vnt:          4,
      elektrines_uzuolaidos_vnt:    6,
    },

    meta: {
      vision_pages: 14,
      poppler_available: true,
    },

    bendri_kiekiai: {
      total_rooms: 11,
      total_area_m2: 165.6,
    },

    confidence: "high",
    pastabos: [
      "Demo projektas — Beržų g. 24 interjero projektas",
      "Išanalizuoti 17 puslapių: pertvarų, lubų, grindų, rozečių, santechnikos, apšvietimo ir išklotinių planai",
    ],
  },
];

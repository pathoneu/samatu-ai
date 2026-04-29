/**
 * ltLibrary — SM03 LT classification library with seeded defaults.
 *
 * Surfaces in the UI:
 *  1. PRESETS — bundled override sets (Standartinis / Premium / Soviet renovacija)
 *  2. ROOM_DEFAULTS — per-paskirtis what's automatically included (read-only viewer)
 *  3. WASTE_FACTORS — material-specific atliekos % from CLAUDE.md §3
 *  4. STANDARD_DIMENSIONS — LT typical opening sizes from CLAUDE.md §2
 *  5. VAT — 21% pre-set
 *
 * Source of truth for the room rules engine lives in
 * backend/extractor/universal_rules.py (ROOM_TYPE_RULES). This module is the
 * USER-FACING mirror so a samatininkas can see what the system assumes
 * before they upload a project.
 */

export const VAT_RATE = 0.21;

// Bundled override sets the user can apply with one click. Keys map directly
// onto the rules_override fields the backend `/recompute-interior` accepts.
export const PRESETS = [
  {
    id: 'standartinis',
    name: 'Standartinis remontas',
    description: 'Tipinis privatus apartamentas / namas. Q2 glaistas, 2.0 m vonios plytelės, 0.6 m virtuvės backsplash.',
    overrides: {
      bathroom_tile_height_m: 2.0,
      bathroom_walls_painted_above_tiles: true,
      kitchen_backsplash_height_m: 0.6,
      drabuzine_painted: true,
      rubine_painted: true,
      sandeliukas_painted: true,
      katiline_painted: true,
      garazas_painted: false,
      tamburas_painted: false,
      glaistas_q_lygis: 'Q2',
      glaistas_storis_mm: 1.5,
      tile_method: 'tiesiai',
      tile_waste_pct: 8,
      paint_waste_pct: 5,
      high_ceiling_threshold_m: 3.0,
      // Sprint §26 (2026-04-29): naujieji accuracy parametrai
      paint_class: 2,
      paint_deduction_standard: 'LT',
    },
  },
  {
    id: 'premium',
    name: 'Premium klasė',
    description: 'Aukšta apdaila — Q3 glaistas, plytelės iki lubų vonioje, eglutės klojimas, didesnis atliekų rezervas.',
    overrides: {
      bathroom_tile_height_m: 2.4,
      bathroom_walls_painted_above_tiles: false,
      kitchen_backsplash_height_m: 0.6,
      drabuzine_painted: true,
      rubine_painted: true,
      sandeliukas_painted: true,
      katiline_painted: true,
      garazas_painted: false,
      tamburas_painted: false,
      glaistas_q_lygis: 'Q3',
      glaistas_storis_mm: 2.0,
      tile_method: 'eglute',
      tile_waste_pct: 12,
      paint_waste_pct: 8,
      high_ceiling_threshold_m: 3.2,
      // Premium: Klasė 1 (Tikkurila Joker), NRM2 strict opening rule
      paint_class: 1,
      paint_deduction_standard: 'NRM2',
    },
  },
  {
    id: 'renovacija',
    name: 'Soviet renovacija',
    description: 'Daugiabučio modernizavimas — esamų sienų išlyginimas (Q1), žemos lubos 2.5m, mažesni vonios plytelių aukščiai.',
    overrides: {
      bathroom_tile_height_m: 1.8,
      bathroom_walls_painted_above_tiles: true,
      kitchen_backsplash_height_m: 0.5,
      drabuzine_painted: false,
      rubine_painted: false,
      sandeliukas_painted: false,
      katiline_painted: true,
      garazas_painted: false,
      tamburas_painted: false,
      glaistas_q_lygis: 'Q1',
      glaistas_storis_mm: 1.0,
      tile_method: 'tiesiai',
      tile_waste_pct: 8,
      paint_waste_pct: 8,
      high_ceiling_threshold_m: 2.7,
      // Renovacija: Klasė 3 (rough/fresh plaster), LT default
      paint_class: 3,
      paint_deduction_standard: 'LT',
    },
  },
  {
    id: 'komercinis',
    name: 'Komercinė patalpa',
    description: 'Biurai/parduotuvės — pakabinamos lubos, sausa luba, didesni angokraščiai, atviri planai.',
    overrides: {
      bathroom_tile_height_m: 2.0,
      bathroom_walls_painted_above_tiles: true,
      kitchen_backsplash_height_m: 0.6,
      drabuzine_painted: true,
      rubine_painted: true,
      sandeliukas_painted: true,
      katiline_painted: true,
      garazas_painted: false,
      tamburas_painted: false,
      glaistas_q_lygis: 'Q2',
      glaistas_storis_mm: 1.5,
      tile_method: 'tiesiai',
      tile_waste_pct: 8,
      paint_waste_pct: 5,
      high_ceiling_threshold_m: 3.0,
      // Komercinis: Klasė 2 standard, NRM2 strict (compliance projects)
      paint_class: 2,
      paint_deduction_standard: 'NRM2',
    },
  },
];

// Per-paskirtis defaults the AI applies when nothing is overridden. Read-only
// reference so users can verify what's auto-included before customizing.
// Mirror of backend/extractor/universal_rules.py ROOM_TYPE_RULES.
export const ROOM_DEFAULTS = [
  { paskirtis: 'gyvenamoji',  label: 'Gyvenamoji / svetainė',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'miegamoji',   label: 'Miegamoji',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'valgomasis',  label: 'Valgomasis',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'virtuve',     label: 'Virtuvė',
    walls: 'dažomos', ceiling: 'GKP', floor: 'plytelės', tiles_walls: 'backsplash 0.6 m', tiles_floor: 'taip' },
  { paskirtis: 'vonia',       label: 'Vonia',
    walls: 'dažomos virš plytelių', ceiling: 'pakabinamos', floor: 'plytelės',
    tiles_walls: 'iki 2.0 m', tiles_floor: 'taip', extras: 'hidroizoliacija PRIVALOMA' },
  { paskirtis: 'wc',          label: 'WC',
    walls: 'dažomos virš plytelių', ceiling: 'pakabinamos', floor: 'plytelės',
    tiles_walls: 'iki 2.0 m', tiles_floor: 'taip', extras: 'hidroizoliacija PRIVALOMA' },
  { paskirtis: 'san',         label: 'San. mazgas',
    walls: 'dažomos virš plytelių', ceiling: 'pakabinamos', floor: 'plytelės',
    tiles_walls: 'iki 2.0 m', tiles_floor: 'taip', extras: 'hidroizoliacija PRIVALOMA' },
  { paskirtis: 'koridorius',  label: 'Koridorius',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'holas',       label: 'Holas',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'rubine',      label: 'Rūbinė',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'drabuzine',   label: 'Drabužinė',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'katiline',    label: 'Katilinė',
    walls: 'dažomos', ceiling: 'GKP', floor: 'plytelės', tiles_walls: '—', tiles_floor: 'taip' },
  { paskirtis: 'skalbykla',   label: 'Skalbykla',
    walls: 'dažomos', ceiling: 'GKP', floor: 'plytelės', tiles_walls: '—', tiles_floor: 'taip',
    extras: 'hidroizoliacija rekomenduojama' },
  { paskirtis: 'sandeliukas', label: 'Sandėliukas',
    walls: 'dažomos', ceiling: 'GKP', floor: 'parketas', tiles_walls: '—', tiles_floor: '—' },
  { paskirtis: 'tamburas',    label: 'Tambūras',
    walls: 'NE dažomos', ceiling: 'betonas', floor: 'plytelės', tiles_walls: '—', tiles_floor: 'taip' },
  { paskirtis: 'garazas',     label: 'Garažas',
    walls: 'NE dažomos', ceiling: 'betonas', floor: 'betonas', tiles_walls: '—', tiles_floor: '—' },
];

// Material atliekos % (CLAUDE.md §3). The backend extraction already applies
// these per category — surfaced here for transparency.
export const WASTE_FACTORS = [
  { material: 'Plytelės — tiesiai',   waste_pct: '8 %' },
  { material: 'Plytelės — eglutė',    waste_pct: '12 %' },
  { material: 'Plytelės — šešiakampis', waste_pct: '16 %' },
  { material: 'Dažai',                waste_pct: '5 %' },
  { material: 'GKP lapai',            waste_pct: '10 %' },
  { material: 'Glaistas',             waste_pct: '5 %' },
  { material: 'Grindjuostės',         waste_pct: '10 %' },
  { material: 'Lubų karnizas',        waste_pct: '5 %' },
  { material: 'Parketas / lamination', waste_pct: '10 %' },
  { material: 'Tapetai',              waste_pct: '15 %' },
  { material: 'Hidroizoliacija',      waste_pct: '5 %' },
  { material: 'Armavimo tinklelis',   waste_pct: '10 %' },
];

// Standard LT opening sizes (CLAUDE.md §2).
export const STANDARD_DIMENSIONS = [
  { kind: 'Langas — mažas',       wxh: '900 × 1500 mm',  area_m2: 1.35 },
  { kind: 'Langas — standartinis', wxh: '1200 × 1500 mm', area_m2: 1.80 },
  { kind: 'Langas — didelis',     wxh: '1500 × 1500 mm', area_m2: 2.25 },
  { kind: 'Langas — panoraminis', wxh: '2100 × 1500 mm', area_m2: 3.15 },
  { kind: 'Durys — kambarys',     wxh: '800 × 2000 mm',  area_m2: 1.60 },
  { kind: 'Durys — vonia',        wxh: '700 × 2000 mm',  area_m2: 1.40 },
  { kind: 'Durys — WC',           wxh: '600 × 2000 mm',  area_m2: 1.20 },
];

export function findPresetById(id) {
  return PRESETS.find(p => p.id === id) || null;
}

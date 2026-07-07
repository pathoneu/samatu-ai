// Characterization + formula tests for interiorCalc.js — the live client-side
// recalculation engine for interior finishing quantities (dažomas plotas,
// angokraščiai, glaistymo kampai, grindjuostės, glaistas, gk lapai).
//
// These numbers are what customers see live in the Prielaidos panel and
// (indirectly) bill from. Every test pins a formula from CLAUDE.md §1 against
// a hand-computed expected value — do NOT "fix" a failure here by adjusting
// the assertion; a failure means either a regression or a documented formula
// mismatch that needs founder review (see interiorCalc discrepancies noted
// in the accompanying test-sweep report).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { calculateInteriorQuantities, DEFAULT_ASSUMPTIONS } from './interiorCalc.js';

// ── 1. DAŽOMAS PLOTAS — room WITHOUT wall sections (perimeter fallback) ────
// CLAUDE.md §1.1: S_walls_gross = perimeter × ceiling_height (no iškotinės
// present → perimeter synthesized as 4.1×√area, per project_perimeter_floor
// memory fix). No openings to deduct here.
test('dazomas_plotas: no-section room uses 4.1×sqrt(area) perimeter synthesis', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2800 }],
    sekcijos: {},
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, DEFAULT_ASSUMPTIONS);

  const expectedPerimM = 4.1 * Math.sqrt(20); // 18.3348...
  const expectedWalls = expectedPerimM * 2.8; // 51.337... m2 (no door on this room)

  assert.equal(result.dazomas_plotas.lubos_m2, 20);
  assert.ok(Math.abs(result.dazomas_plotas.sienos_m2 - expectedWalls) < 0.05);
  assert.equal(result.dazomas_plotas.viso_m2, Math.round((expectedWalls + 20) * 10) / 10);
});

test('dazomas_plotas: no-section room subtracts door area between it and another room', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2800 }],
    sekcijos: {},
    meta: { doors: [{ width_mm: 900, height_mm: 2100, between: ['101', '102'] }] },
  };
  const result = calculateInteriorQuantities(rawData, DEFAULT_ASSUMPTIONS);

  const perimM = 4.1 * Math.sqrt(20);
  const doorAreaM2 = 0.9 * 2.1; // 1.89
  const expectedWalls = perimM * 2.8 - doorAreaM2;

  assert.ok(Math.abs(result.dazomas_plotas.sienos_m2 - expectedWalls) < 0.05);
});

// ── 2. DAŽOMAS PLOTAS — room WITH wall sections (išklotinės) ──────────────
// CLAUDE.md §1.1: S_walls_net = gross − tiles − panels − openings (openings
// here modeled directly as section "openings", tiles/panels as "zones").
test('dazomas_plotas: sectioned room = gross(w×h) − tiles − window opening', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: {
        room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [],
        openings: [{ type: 'langas', width_mm: 1200, height_mm: 1500 }],
      },
      A2: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
      A3: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A4: {
        room_nr: '201', width_mm: 3000, height_mm: 2500,
        zones: [{ type: 'plytelės', area_m2: 2.0 }], openings: [],
      },
    },
    meta: { doors: [{ width_mm: 900, height_mm: 2100, between: ['201'] }] },
  };
  const result = calculateInteriorQuantities(rawData, {});

  // gross = 2*(4+3)*2.5 = 35; minus tiles 2.0; minus window 1.2*1.5=1.8 => 31.2
  assert.equal(result.dazomas_plotas.sienos_m2, 31.2);
  assert.equal(result.dazomas_plotas.lubos_m2, 12);
  assert.equal(result.plyteles_m2, 2);
});

test('dazomas_plotas: explicit "dažymas" zone sum wins over gross-minus-other when present', () => {
  const rawData = {
    patalpos: [{ nr: '301', plotas_m2: 10, lubu_aukstis_mm: 2700 }],
    sekcijos: {
      A1: {
        room_nr: '301', width_mm: 5000, height_mm: 2700,
        zones: [{ type: 'dažymas', area_m2: 8.5 }], openings: [],
      },
    },
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  assert.equal(result.dazomas_plotas.sienos_m2, 8.5);
});

// ── 3. ANGOKRAŠČIAI (window/door reveals) ───────────────────────────────────
// CLAUDE.md §1.2: reveal_length = 2×height + width; reveal_area = length × wall_thickness
test('angokrasciai: window + door reveal length and area match CLAUDE.md formula', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: {
        room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [],
        openings: [{ type: 'langas', width_mm: 1200, height_mm: 1500 }],
      },
    },
    meta: { doors: [{ width_mm: 900, height_mm: 2100, between: ['201'] }] },
  };
  const result = calculateInteriorQuantities(rawData, { sienos_storis_m: 0.10 });

  const windowReveal = 2 * 1.5 + 1.2; // 4.2
  const doorReveal = 2 * 2.1 + 0.9;   // 5.1
  const totalReveal = windowReveal + doorReveal; // 9.3

  assert.equal(result.angokrasciai.langu_vnt, 1);
  assert.equal(result.angokrasciai.duru_vnt, 1);
  assert.equal(result.angokrasciai.viso_m, Math.round(totalReveal * 10) / 10);
  assert.equal(result.angokrasciai.area_m2, Math.round(totalReveal * 0.10 * 100) / 100);
});

test('angokrasciai: custom_windows override replaces section-derived windows', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: {
        room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [],
        openings: [{ type: 'langas', width_mm: 1200, height_mm: 1500 }],
      },
    },
    meta: { doors: [] },
  };
  const customWindows = [{ width_mm: 1500, height_mm: 1500 }]; // "large" LT standard
  const result = calculateInteriorQuantities(rawData, { custom_windows: customWindows });

  assert.equal(result.angokrasciai.langu_vnt, 1);
  const expectedReveal = 2 * 1.5 + 1.5; // 4.5, not the section's 4.2
  assert.equal(result.angokrasciai.viso_m, expectedReveal);
});

// ── 4. GRINDJUOSTĖS (baseboards) ────────────────────────────────────────────
// CLAUDE.md §1.4: baseboard = room_perimeter − Σ(door_widths) + 10% waste.
// FIXED 2026-07-05: the +10% waste is now applied here, exactly once. Trace
// confirmed the WASTE_FACTORS UI table (ltLibrary.js Grindjuostės 10%) is
// display-only and the ExportModal reads grindjuostes.viso_m verbatim, so the
// waste was previously applied ZERO times end-to-end. lubu_perimetras stays
// net (§1.4: ceiling cornice gets +5%, tracked separately, not baseboard).
test('grindjuostes: sectioned room = (perimeter − door width) × 1.10 waste (§1.4)', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A2: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
      A3: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A4: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
    },
    meta: { doors: [{ width_mm: 900, height_mm: 2100, between: ['201'] }] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  // perimeter = 4000+3000+4000+3000 = 14000mm = 14m; minus door 0.9m => 13.1m net
  // grindjuostės = 13.1 × 1.10 (§1.4 waste) = 14.41 → round1 = 14.4m
  assert.equal(result.grindjuostes.viso_m, 14.4);
  assert.equal(result.lubu_perimetras.viso_m, 14);
});

test('grindjuostes: no-section room uses perimeter synthesis minus door width, floored at 0', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 5, lubu_aukstis_mm: 2500 }],
    sekcijos: {},
    // Door wider than the tiny synthesized perimeter forces the Math.max(0, …) floor.
    meta: { doors: [{ width_mm: 50000, height_mm: 2100, between: ['101'] }] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  assert.equal(result.grindjuostes.viso_m, 0);
});

// ── 5. GLAISTYMO KAMPAI (plastering corners) ───────────────────────────────
// CLAUDE.md §1.3 base formula: corner_length = outer_corners × ceiling_height.
// Production code layers three data-quality tiers on top (vision_total >
// outer_x3.5 heuristic > ratio_estimate fallback) — pin all three tiers.
test('glaistymo_kampai: prefers Vision-reported total corner count when present', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2600 }],
    sekcijos: {},
    meta: { visu_kampu_vnt: 16, doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  assert.equal(result.glaistymo_kampai.kampai_vnt, 16);
  assert.equal(result.glaistymo_kampai.skaiciavimo_budas, 'vision_total');
  assert.equal(result.glaistymo_kampai.viso_m, Math.round(16 * 2.6 * 10) / 10);
});

test('glaistymo_kampai: falls back to outer-corners × 3.5 heuristic', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2600 }],
    sekcijos: {},
    meta: { isoriniu_kampu_vnt: 4, doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  assert.equal(result.glaistymo_kampai.kampai_vnt, Math.round(4 * 3.5));
  assert.equal(result.glaistymo_kampai.skaiciavimo_budas, 'outer_x3.5');
});

test('glaistymo_kampai: last-resort ratio estimate from total paintable area', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2800 }],
    sekcijos: {},
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  const dazymasTotal = result.dazomas_plotas.sienos_m2 + result.dazomas_plotas.lubos_m2;
  const expectedKampai = Math.round((dazymasTotal * 0.70) / 2.8);
  assert.equal(result.glaistymo_kampai.kampai_vnt, expectedKampai);
  assert.equal(result.glaistymo_kampai.skaiciavimo_budas, 'ratio_estimate');
});

// ── 6. DAŽAI (paint liters) — FINDING: hardcoded to 0 in this module ───────
// CLAUDE.md §1.10: paint_liters = area × coats / coverage_rate. The frontend
// deliberately stubs sienos_l/lubos_l to 0 (2026-05-10 hotfix comment: the
// backend POST /api/recompute-quantities is the canonical source; the old
// null placeholders produced NaN downstream). This is intentional, not a
// bug — pin it so a future refactor doesn't silently reintroduce NaN.
test('dazai: sienos_l/lubos_l are stubbed to 0 (backend is canonical); gruntas_l is computed locally', () => {
  const rawData = {
    patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2800 }],
    sekcijos: {},
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  assert.equal(result.dazai.sienos_l, 0);
  assert.equal(result.dazai.lubos_l, 0);
  // gruntas_l = total paintable area × 0.15 l/m2 (CLAUDE.md §1.10 primer coverage ~7 m2/l => 0.143 l/m2, code uses 0.15)
  const totalArea = result.dazomas_plotas.viso_m2;
  assert.equal(result.dazai.gruntas_l, Math.round(totalArea * 0.15 * 10) / 10);
  assert.ok(Number.isFinite(result.dazai.viso_l), 'viso_l must never be NaN');
});

// ── 7. GK LAPAI (drywall sheets) ────────────────────────────────────────────
// CLAUDE.md §1.8: sheets = CEILING(wall_area / 3.0) × 1.10 — code applies the
// 1.10 factor INSIDE the ceiling (Math.ceil(area/3.0*1.10)), not ceil-then-
// multiply; pin the actual code behavior.
test('gk_lapai: sheets = ceil(paint_wall_area / 3.0 × 1.10)', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A2: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
      A3: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A4: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
    },
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  const wallArea = result.dazomas_plotas.sienos_m2; // 35
  assert.equal(result.gk_lapai.vnt, Math.ceil((wallArea / 3.0) * 1.1));
});

// ── 8. GLAISTYMAS (skim coat) — Q-level rates/thickness from CLAUDE.md §1.11 ─
// node:test has no test.each — loop and register each case individually.
// Q4 thickness corrected 2.5 → 4 mm (2026-07-05) per CLAUDE.md §1.11
// (Q4 = 3–5 mm full-surface skim; mid-range 4 mm). Prior 2.5 mm was a
// characterization pin of an under-estimating value — updated to spec.
for (const [level, rate, thickness] of [
  ['Q1', 0.8, 1.2], ['Q2', 1.0, 1.25], ['Q3', 1.2, 1.75], ['Q4', 1.5, 4],
]) {
  test(`glaistas: ${level} uses documented rate ${rate} kg/m²/mm and code thickness ${thickness}mm`, () => {
    const rawData = {
      patalpos: [{ nr: '101', plotas_m2: 20, lubu_aukstis_mm: 2800 }],
      sekcijos: {},
      meta: { doors: [] },
    };
    const result = calculateInteriorQuantities(rawData, { glaistimo_lygis: level });
    const totalArea = result.dazomas_plotas.viso_m2;
    // NB: interiorCalc's dazymasVisoM2 pre-rounding value is used inside the
    // calc; result.dazomas_plotas.viso_m2 is already rounded to 1 decimal, so
    // allow a small tolerance vs. re-deriving from the rounded output.
    const expectedKg = Math.round(totalArea * thickness * rate);
    assert.ok(Math.abs(result.glaistas.kg - expectedKg) <= 1);
    assert.equal(result.glaistas.maisai_25kg, Math.ceil(result.glaistas.kg / 25));
    assert.equal(result.glaistas.lygis, level);
  });
}

// CLAUDE.md §1.11 documents Q1=0.5-1mm, Q2=1-1.5mm, Q3=1.5-2mm, Q4=3-5mm as
// TYPICAL thickness ranges. Q4 corrected 2.5 → 4 mm (2026-07-05) to sit mid-range
// in the documented 3–5 mm full-surface-skim band (was under-ordering putty).
// Q1–Q3 left as-is (within/near their bands and unchanged by this pass).
test('glaistas: Q_THICK table values match CLAUDE.md §1.11 (Q4 = 4 mm mid-range)', () => {
  const levels = { Q1: 1.2, Q2: 1.25, Q3: 1.75, Q4: 4 };
  for (const [level, mm] of Object.entries(levels)) {
    const rawData = { patalpos: [{ nr: '1', plotas_m2: 10, lubu_aukstis_mm: 2500 }], sekcijos: {}, meta: { doors: [] } };
    const result = calculateInteriorQuantities(rawData, { glaistimo_lygis: level });
    const totalArea = result.dazomas_plotas.viso_m2;
    const rate = { Q1: 0.8, Q2: 1.0, Q3: 1.2, Q4: 1.5 }[level];
    assert.equal(result.glaistas.kg, Math.round(totalArea * mm * rate));
  }
});

// ── 9. Validation notes — sienos/lubos ratio sanity check (CLAUDE.md §6.1) ──
test('validation_notes: flags wall/ceiling ratio below the 2.5-4x norm', () => {
  // Tiny perimeter relative to floor area (long corridor-ish room) can trip low.
  const rawData = {
    patalpos: [{ nr: '1', plotas_m2: 20, lubu_aukstis_mm: 2000 }],
    sekcijos: {
      A1: { room_nr: '1', width_mm: 2000, height_mm: 2000, zones: [], openings: [] },
    },
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  // gross wall = 2*2 = 4 m2, ceiling = 20 m2 => ratio 0.2, well under 2.0
  assert.ok(result.validation_notes.some(n => /per mažas/.test(n)));
});

test('validation_notes: empty when ratio is within the 2.5-4x norm', () => {
  const rawData = {
    patalpos: [{ nr: '201', plotas_m2: 12, lubu_aukstis_mm: 2500 }],
    sekcijos: {
      A1: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A2: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
      A3: { room_nr: '201', width_mm: 4000, height_mm: 2500, zones: [], openings: [] },
      A4: { room_nr: '201', width_mm: 3000, height_mm: 2500, zones: [], openings: [] },
    },
    meta: { doors: [] },
  };
  const result = calculateInteriorQuantities(rawData, {});
  // wall 35 / ceiling 12 = 2.9x — inside norm
  assert.equal(result.validation_notes.length, 0);
});

// Pins the LT classification library's user-facing tables against CLAUDE.md
// §2 (standard dimensions) and §3 (waste factors). This module is the
// USER-FACING mirror of backend/extractor/universal_rules.py (ROOM_TYPE_RULES)
// — it doesn't compute anything itself, but a silent edit to these constants
// would desync what the UI shows from what the backend actually applies, or
// drift away from the documented CLAUDE.md ranges. Pin the exact values.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  WASTE_FACTORS, STANDARD_DIMENSIONS, PRESETS, VAT_RATE, findPresetById,
} from './ltLibrary.js';

function wastePct(material) {
  const row = WASTE_FACTORS.find(w => w.material === material);
  assert.ok(row, `expected a WASTE_FACTORS row for "${material}"`);
  return Number(row.waste_pct.replace('%', '').trim());
}

test('VAT_RATE is 21% (CLAUDE.md: always 21% PVM)', () => {
  assert.equal(VAT_RATE, 0.21);
});

// CLAUDE.md §3 table: tiles straight 5-10%, herringbone 10-15%, hexagonal 15-17%
test('WASTE_FACTORS: tile waste tiers fall inside the CLAUDE.md §3 ranges', () => {
  assert.ok(wastePct('Plytelės — tiesiai') >= 5 && wastePct('Plytelės — tiesiai') <= 10);
  assert.ok(wastePct('Plytelės — eglutė') >= 10 && wastePct('Plytelės — eglutė') <= 15);
  assert.ok(wastePct('Plytelės — šešiakampis') >= 15 && wastePct('Plytelės — šešiakampis') <= 17);
});

// CLAUDE.md §3: Paint 5-8%, Drywall 10-15%, Wallpaper 10-15%
test('WASTE_FACTORS: paint/drywall/wallpaper fall inside CLAUDE.md §3 ranges', () => {
  assert.ok(wastePct('Dažai') >= 5 && wastePct('Dažai') <= 8);
  assert.ok(wastePct('GKP lapai') >= 10 && wastePct('GKP lapai') <= 15);
  assert.ok(wastePct('Tapetai') >= 10 && wastePct('Tapetai') <= 15);
});

test('WASTE_FACTORS: every row has a material name and a parseable percentage', () => {
  assert.ok(WASTE_FACTORS.length > 0);
  for (const row of WASTE_FACTORS) {
    assert.equal(typeof row.material, 'string');
    assert.ok(row.material.length > 0);
    const pct = Number(row.waste_pct.replace('%', '').trim());
    assert.ok(Number.isFinite(pct) && pct > 0 && pct <= 20, `${row.material}: ${row.waste_pct}`);
  }
});

// CLAUDE.md §2 "Windows (Langai)" table — exact area = width × height.
test('STANDARD_DIMENSIONS: window areas match CLAUDE.md §2 width×height table', () => {
  const expected = {
    'Langas — mažas': [0.9, 1.5, 1.35],
    'Langas — standartinis': [1.2, 1.5, 1.80],
    'Langas — didelis': [1.5, 1.5, 2.25],
    'Langas — panoraminis': [2.1, 1.5, 3.15],
  };
  for (const [kind, [w, h, area]] of Object.entries(expected)) {
    const row = STANDARD_DIMENSIONS.find(d => d.kind === kind);
    assert.ok(row, `missing STANDARD_DIMENSIONS row for ${kind}`);
    assert.ok(Math.abs(row.area_m2 - area) < 1e-9, `${kind}: expected ${area}, got ${row.area_m2}`);
    assert.ok(Math.abs(w * h - area) < 1e-9); // sanity: area really is w×h
  }
});

// CLAUDE.md §2 "Interior Doors" table gives leaf sizes per room; this module
// surfaces the same leaf width×height (not the larger rough-opening size).
test('STANDARD_DIMENSIONS: door leaf areas match width×height for each room type', () => {
  const expected = {
    'Durys — kambarys': [0.8, 2.0, 1.60],
    'Durys — vonia': [0.7, 2.0, 1.40],
    'Durys — WC': [0.6, 2.0, 1.20],
  };
  for (const [kind, [w, h, area]] of Object.entries(expected)) {
    const row = STANDARD_DIMENSIONS.find(d => d.kind === kind);
    assert.ok(row, `missing STANDARD_DIMENSIONS row for ${kind}`);
    assert.ok(Math.abs(row.area_m2 - area) < 1e-9);
    assert.ok(Math.abs(w * h - area) < 1e-9);
  }
});

// PRESETS: bundled override sets used by RulesOverridePanel. Pin the Q-level
// / waste-pct combinations so a preset edit doesn't silently drift.
test('PRESETS: findPresetById resolves each bundled preset with its glaistas Q-level', () => {
  assert.equal(findPresetById('standartinis').overrides.glaistas_q_lygis, 'Q2');
  assert.equal(findPresetById('premium').overrides.glaistas_q_lygis, 'Q3');
  assert.equal(findPresetById('renovacija').overrides.glaistas_q_lygis, 'Q1');
  assert.equal(findPresetById('komercinis').overrides.glaistas_q_lygis, 'Q2');
  assert.equal(findPresetById('does-not-exist'), null);
});

test('PRESETS: every preset waste_pct field is inside the CLAUDE.md §3 tile/paint ranges', () => {
  for (const preset of PRESETS) {
    const { tile_waste_pct, paint_waste_pct } = preset.overrides;
    assert.ok(tile_waste_pct >= 5 && tile_waste_pct <= 17, `${preset.id} tile_waste_pct=${tile_waste_pct}`);
    assert.ok(paint_waste_pct >= 5 && paint_waste_pct <= 8, `${preset.id} paint_waste_pct=${paint_waste_pct}`);
  }
});

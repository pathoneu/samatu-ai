// Pathon v3 W5-D D12 — a sheet whose only zone is a legend gets the type „Legenda" (€0, no paid prompt change).
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSheetRail, sheetTypeFromZones, withZoneSheetTypes } from './sheetRail.js';
import { PAGE_TYPE_LABELS } from './pageTypes.js';

const z = (kind) => ({ kind, bbox_pct: [0, 0, 0.2, 0.2] });

test('only a legend (with a title block or notes beside it) makes a legend sheet', () => {
  assert.equal(sheetTypeFromZones([z('legenda'), z('antspaudas'), z('pastabos')]), 'legend');
  assert.equal(sheetTypeFromZones([z('legenda'), z('planas')]), null);
  assert.equal(sheetTypeFromZones([z('legenda'), z('lentele')]), null);
  assert.equal(sheetTypeFromZones([z('antspaudas')]), null);
  assert.equal(sheetTypeFromZones(undefined), null);
});

test('the zones type a sheet the reading left open — never one it typed', () => {
  const pages = [{ nr: 1, tipas: 'floor_plan', pavadinimas: 'Planas' }, { nr: 2, tipas: 'unknown', pavadinimas: 'Ženklai' }];
  const zonos = { 1: [z('legenda')], 2: [z('legenda'), z('antspaudas')], 3: [z('legenda')], 4: [z('planas')] };
  const out = withZoneSheetTypes(pages, zonos);
  assert.equal(out[0].tipas, 'floor_plan');
  assert.deepEqual(out[1], { nr: 2, tipas: 'legend', pavadinimas: 'Ženklai', saltinis: 'zonos' });
  assert.deepEqual(out.find((p) => p.nr === 3), { nr: 3, tipas: 'legend', pavadinimas: '', saltinis: 'zonos' });
  assert.equal(out.some((p) => p.nr === 4), false);
  // nothing to change: the same array (no re-render)
  assert.equal(withZoneSheetTypes(pages, { 1: [z('legenda')] }), pages);
  assert.equal(withZoneSheetTypes(pages, undefined), pages);
});

test('the rail names it „Legenda" in the architecture group, and his own type still wins', () => {
  assert.equal(PAGE_TYPE_LABELS.legend, 'Legenda');
  const puslapiai = withZoneSheetTypes([], { 2: [z('legenda')] });
  const rail = buildSheetRail({ puslapiai, pageCount: 2 });
  assert.equal(rail.sheets[1].tipas, 'legend');
  assert.equal(rail.sheets[1].discipline, 'architektura');
  const his = buildSheetRail({ puslapiai, pageCount: 2, overrides: { 2: { type: 'electrical' } } });
  assert.equal(his.sheets[1].tipas, 'electrical');
});

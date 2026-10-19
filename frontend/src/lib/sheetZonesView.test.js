import test from 'node:test';
import assert from 'node:assert/strict';
import { hoverZoneAt, zoneLabel, zonesToDraw, ZONE_NAMES } from './sheetZonesView.js';

// demo-objektas_h sheet 3 as the zones route answers it (rounded)
const SHEET3 = [
  { kind: 'legenda', bbox_pct: [0.06, 0.5, 0.22, 0.68], label: 'SUTARTINIAI ŽYMĖJIMAI' },
  { kind: 'legenda', bbox_pct: [0.26, 0.76, 0.42, 0.82] },
  { kind: 'antspaudas', bbox_pct: [0.42, 0.87, 0.97, 0.98] },
  { kind: 'planas', bbox_pct: [0.08, 0.16, 0.83, 0.67], label: 'APŠVIETIMO PLANAS' },
  { kind: 'pastabos', bbox_pct: [0.06, 0.9, 0.37, 0.94] },
];

test('every kind has a Lithuanian name; a zone with a title says both, shortened', () => {
  assert.equal(zoneLabel(SHEET3[2]), 'Antspaudas');
  assert.equal(zoneLabel(SHEET3[0]), 'Legenda · SUTARTINIAI ŽYMĖJIMAI');
  assert.equal(zoneLabel({ kind: 'lentele', label: 'lentelė' }), 'Lentelė');
  assert.match(zoneLabel({ kind: 'lentele', label: 'X'.repeat(80) }), /^Lentelė · X{39}…$/);
  assert.equal(zoneLabel({ kind: 'nezinoma' }), ZONE_NAMES.kita);
});

test('the hover names the innermost zone and never the plan', () => {
  // inside the legend that sits inside the plan's box
  assert.equal(hoverZoneAt(SHEET3, 0.1, 0.6).kind, 'legenda');
  // on the plan only → nothing (the plan is most of the sheet)
  assert.equal(hoverZoneAt(SHEET3, 0.5, 0.4), null);
  assert.equal(hoverZoneAt(SHEET3, 0.6, 0.92).kind, 'antspaudas');
  assert.equal(hoverZoneAt(SHEET3, 0.99, 0.01), null);
  assert.equal(hoverZoneAt(null, 0.1, 0.1), null);
});

test('„Rodyti sritis" draws every zone; otherwise only the hovered one', () => {
  assert.equal(zonesToDraw(SHEET3, { shown: true }).length, 5);
  assert.deepEqual(zonesToDraw(SHEET3, { hovered: SHEET3[2] }), [SHEET3[2]]);
  assert.deepEqual(zonesToDraw(SHEET3, {}), []);
  // a hovered zone from another sheet is not drawn here
  assert.deepEqual(zonesToDraw(SHEET3, { hovered: { kind: 'legenda', bbox_pct: [0, 0, 1, 1] } }), []);
  assert.deepEqual(zonesToDraw([{ kind: 'legenda' }, { kind: 'x', bbox_pct: [0, 0, 1, 1] }], { shown: true }), []);
});

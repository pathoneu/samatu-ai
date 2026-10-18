import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  OV_KINDS, ov, paint, STROKE_PX, SELECTED_STROKE_PX, FILL_ALPHA, FILL_ALPHA_HOVER, DASH, DASH_ESTIMATED,
  LABEL_FONT_PX, LINE_KINDS, lineStyle, outlineKindOf, OUTLINE_SENTENCE, LEGENDS, labelWidth,
} from './overlayTokens.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(HERE, '../index.css'), 'utf8');

function token(name) {
  const m = css.match(new RegExp(`--${name}:\\s*([\\d.]+)\\s+([\\d.]+)%\\s+([\\d.]+)%`));
  if (!m) return null;
  return m.slice(1).map(Number);
}
function hslToRgb([h, s, l]) {
  const S = s / 100; const L = l / 100;
  const k = (n) => (n + h / 30) % 12;
  const a = S * Math.min(L, 1 - L);
  const f = (n) => L - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0), f(8), f(4)].map((v) => Math.round(v * 255));
}
function contrastOnWhite(rgb) {
  const lin = (v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; };
  const L = 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
  return 1.05 / (L + 0.05);
}

test('every overlay kind is a token in index.css', () => {
  for (const kind of OV_KINDS) assert.ok(token(`ov-${kind}`), `--ov-${kind} missing from :root`);
});

test('every stroke colour reads on the white sheet (≥ 3:1, WCAG 1.4.11)', () => {
  for (const kind of OV_KINDS.filter((k) => !['label-bg', 'zone-fill'].includes(k))) {
    const ratio = contrastOnWhite(hslToRgb(token(`ov-${kind}`)));
    assert.ok(ratio >= 3, `--ov-${kind} is ${ratio.toFixed(2)}:1 on white`);
  }
});

test('label ink on the label pill passes the text floor (≥ 4.5:1)', () => {
  assert.deepEqual(hslToRgb(token('ov-label-bg')), [255, 255, 255]);
  assert.ok(contrastOnWhite(hslToRgb(token('ov-label-fg'))) >= 4.5);
});

test('muted text clears 5.5:1 on white (contrast floor, audit A#1)', () => {
  assert.ok(contrastOnWhite(hslToRgb(token('muted-foreground'))) >= 5.5);
});

test('the revision colours stay as the server paints them (test-locked in the backend)', () => {
  assert.deepEqual(token('revision-new'), [165, 24, 32]);
  assert.deepEqual(token('revision-removed'), [12, 38, 48]);
});

test('ov() builds the CSS colour, with an optional alpha; unknown kinds throw', () => {
  assert.equal(ov('read'), 'hsl(var(--ov-read))');
  assert.equal(ov('zone-fill', FILL_ALPHA), 'hsl(var(--ov-zone-fill) / 0.16)');
  assert.throws(() => ov('blue'));
});

test('paint() returns only the paints given', () => {
  assert.deepEqual(paint({ stroke: ov('error') }), { stroke: 'hsl(var(--ov-error))' });
  assert.deepEqual(paint({}), {});
});

test('line constants: constant 2 px strokes, heavier selection, fills 0.12–0.20 (design §6)', () => {
  assert.equal(STROKE_PX, 2);
  assert.ok(SELECTED_STROKE_PX > STROKE_PX);
  assert.ok(FILL_ALPHA >= 0.12 && FILL_ALPHA <= 0.2);
  assert.ok(FILL_ALPHA_HOVER > FILL_ALPHA && FILL_ALPHA_HOVER <= 0.3);
  assert.equal(LABEL_FONT_PX, 12);
});

test('dashed means estimated or proposed — nothing else; red means error — nothing else', () => {
  assert.equal(DASH, DASH_ESTIMATED);
  for (const [kind, k] of Object.entries(LINE_KINDS)) {
    const dashed = k.dash != null;
    assert.equal(dashed, kind === 'estimated' || kind === 'proposed', `${kind} dash`);
    if (dashed) assert.equal(k.dash, DASH);
    assert.equal(k.stroke === 'error', kind === 'error', `${kind} red`);
    assert.ok(k.sentence.length > 10, `${kind} has a sentence`);
  }
  assert.equal(lineStyle('estimated').dash, DASH);
  assert.equal(lineStyle('read').dash, null);
  assert.equal(lineStyle('nonsense').dash, DASH);       // unknown → never passes for read
});

test('outlineKindOf: his outline is confirmed, a wall-traced one read, anything else an estimate', () => {
  assert.equal(outlineKindOf({ polygon_source: 'corrected' }), 'confirmed');
  assert.equal(outlineKindOf({ polygon_source: 'manual' }), 'confirmed');
  assert.equal(outlineKindOf({ polygon_source: 'vektoriniai_konturai' }), 'read');
  assert.equal(outlineKindOf({ polygon_source: 'sienu_konturas' }), 'read');
  assert.equal(outlineKindOf({ polygon_source: 'auto_floodfill' }), 'estimated');
  assert.equal(outlineKindOf({ polygon_source: 'synthesized_from_bbox' }), 'estimated');
  assert.equal(outlineKindOf({}), 'estimated');
  for (const k of ['confirmed', 'read', 'estimated', 'marker']) assert.ok(OUTLINE_SENTENCE[k]);
});

test('legends: every row names a token kind, dashes only for estimates, and says it in words', () => {
  for (const [layer, rows] of Object.entries(LEGENDS)) {
    for (const row of rows) {
      assert.ok(OV_KINDS.includes(row.stroke), `${layer}/${row.key} stroke`);
      if (row.fill) assert.ok(OV_KINDS.includes(row.fill), `${layer}/${row.key} fill`);
      if (row.dash) {
        assert.equal(row.dash, DASH);
        assert.ok(['estimated', 'proposed'].includes(row.stroke), `${layer}/${row.key}: dashed but ${row.stroke}`);
      }
      assert.ok(row.label && !/zon(a|os|ą|ų|ai|oje)\b|\bAI\b|vektorin/i.test(row.label), `${layer}/${row.key}: „${row.label}"`);
    }
  }
});

test('labelWidth grows with the text and never returns less than the padding', () => {
  assert.ok(labelWidth('61,81 m²') > labelWidth('4 m'));
  assert.ok(labelWidth('') >= 14);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { makeEmbedAdapter } from './embedPdfAdapter.js';

// Landscape mediabox (A1-ish proportions) rendered at zoom 1.5. On reported
// /Rotate 90/270 the DISPLAYED page is the mediabox quarter-turned, so the
// rendered box swaps axes.
const W = 1000;
const H = 800;
const Z = 1.5;

function adapterFor(reportedRotation) {
  const swapped = reportedRotation === 90 || reportedRotation === 270
    || reportedRotation === 1 || reportedRotation === 3;
  return makeEmbedAdapter({
    renderedWidth: (swapped ? H : W) * Z,
    renderedHeight: (swapped ? W : H) * Z,
    pageWidthPt: W,
    pageHeightPt: H,
    reportedRotation,
  });
}

const SAMPLE_POINTS = [
  { x: 0, y: 0 },
  { x: W, y: H },
  { x: 123.4, y: 56.78 },
  { x: 300, y: 272 },
  { x: W / 2, y: H / 2 },
];

test('toPdf(toViewport(p)) round-trips for rotations 0/90/180/270', () => {
  for (const rot of [0, 90, 180, 270]) {
    const a = adapterFor(rot);
    for (const p of SAMPLE_POINTS) {
      const back = a.toPdf(a.toViewport(p));
      assert.ok(Math.abs(back.x - p.x) < 1e-9, `rot ${rot}: x ${p.x} -> ${back.x}`);
      assert.ok(Math.abs(back.y - p.y) < 1e-9, `rot ${rot}: y ${p.y} -> ${back.y}`);
    }
  }
});

test('toViewport(toPdf(sp)) round-trips screen points for all rotations', () => {
  for (const rot of [0, 90, 180, 270]) {
    const a = adapterFor(rot);
    for (const sp of [{ x: 0, y: 0 }, { x: a.width, y: a.height }, { x: 41.5, y: 977.25 }]) {
      const back = a.toViewport(a.toPdf(sp));
      assert.ok(Math.abs(back.x - sp.x) < 1e-9, `rot ${rot}: sx ${sp.x} -> ${back.x}`);
      assert.ok(Math.abs(back.y - sp.y) < 1e-9, `rot ${rot}: sy ${sp.y} -> ${back.y}`);
    }
  }
});

// The verified Beržų anchor: room 102 sits at mediabox pct (0.30, 0.34) on a
// reported-/Rotate-270 sheet and must land at DISPLAY pct (0.66, 0.30) —
// PDFium shows the complement, i.e. a 90° CW turn of the mediabox.
test('room-102 anchor: mediabox (0.30,0.34) on reported-270 page lands at display (0.66,0.30)', () => {
  const a = adapterFor(270);
  const sp = a.toViewport({ x: 0.30 * W, y: 0.34 * H });
  assert.ok(Math.abs(sp.x / a.width - 0.66) < 1e-9, `display fx ${sp.x / a.width}`);
  assert.ok(Math.abs(sp.y / a.height - 0.30) < 1e-9, `display fy ${sp.y / a.height}`);
});

test('scale is px per PDF point and uses the swapped axis on 90/270', () => {
  // rot 0/180: renderedWidth spans pageWidthPt.
  assert.ok(Math.abs(adapterFor(0).scale - Z) < 1e-12);
  assert.ok(Math.abs(adapterFor(180).scale - Z) < 1e-12);
  // rot 90/270: renderedWidth spans pageHEIGHTPt. Unswapped math would give
  // Z*H/W = 1.2, not 1.5 — assert the swap actually happened.
  assert.ok(Math.abs(adapterFor(90).scale - Z) < 1e-12);
  assert.ok(Math.abs(adapterFor(270).scale - Z) < 1e-12);
  assert.notEqual(Math.abs((Z * H) / W - Z) < 1e-12, true);
});

test('width/height mirror the rendered box', () => {
  const a0 = adapterFor(0);
  assert.equal(a0.width, W * Z);
  assert.equal(a0.height, H * Z);
  const a90 = adapterFor(90);
  assert.equal(a90.width, H * Z);
  assert.equal(a90.height, W * Z);
});

test('accepts PDFium quarter-turn integers (3 === 270)', () => {
  const aInt = adapterFor(3);
  const aDeg = adapterFor(270);
  for (const p of SAMPLE_POINTS) {
    const si = aInt.toViewport(p);
    const sd = aDeg.toViewport(p);
    assert.ok(Math.abs(si.x - sd.x) < 1e-12 && Math.abs(si.y - sd.y) < 1e-12);
  }
  assert.equal(aInt.scale, aDeg.scale);
});

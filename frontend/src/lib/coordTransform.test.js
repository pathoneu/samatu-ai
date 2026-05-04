// frontend/src/lib/coordTransform.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  canvasPxToPdfPct, pdfPctToCanvasPx, pdfPctPolyToCanvasPxPoly,
} from './coordTransform.js';

test('canvasPxToPdfPct: identity at scale=1, no translate', () => {
  const tx = { scale: 1, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  assert.deepEqual(canvasPxToPdfPct({ px: 100, py: 50 }, tx), { x: 0.5, y: 0.5 });
});

test('canvasPxToPdfPct: handles scale=2', () => {
  const tx = { scale: 2, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  assert.deepEqual(canvasPxToPdfPct({ px: 200, py: 100 }, tx), { x: 0.5, y: 0.5 });
});

test('canvasPxToPdfPct: handles translate', () => {
  const tx = { scale: 1, translate: { x: 50, y: 20 }, canvasWidth: 200, canvasHeight: 100 };
  assert.deepEqual(canvasPxToPdfPct({ px: 150, py: 70 }, tx), { x: 0.5, y: 0.5 });
});

test('pdfPctToCanvasPx: round-trip with canvasPxToPdfPct', () => {
  const tx = { scale: 1.5, translate: { x: 30, y: 10 }, canvasWidth: 800, canvasHeight: 600 };
  const original = { px: 320, py: 200 };
  const pct = canvasPxToPdfPct(original, tx);
  const back = pdfPctToCanvasPx(pct, tx);
  assert.ok(Math.abs(back.px - original.px) < 1e-6);
  assert.ok(Math.abs(back.py - original.py) < 1e-6);
});

test('pdfPctPolyToCanvasPxPoly: maps every vertex', () => {
  const tx = { scale: 1, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  const poly = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]];
  const out = pdfPctPolyToCanvasPxPoly(poly, tx);
  assert.deepEqual(out, [[0, 0], [200, 0], [200, 100], [0, 100]]);
});

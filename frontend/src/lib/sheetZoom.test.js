import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ZOOM_MAX, ZOOM_MIN, clampZoom, fullSheetUrl, paddedRect, rectCentre, rectKey, visibleRect, withRect, zoomForRect,
} from './sheetZoom.js';

const url = '/api/projects/p1/evidence?page=4&rect=0.1345,0.1329,0.6059,0.8990&dpi=110';

test('withRect swaps the rectangle and asks for the sharp dpi', () => {
  assert.equal(withRect(url, [0.2, 0.3, 0.4, 0.5]),
    '/api/projects/p1/evidence?page=4&rect=0.2000,0.3000,0.4000,0.5000&dpi=160');
  assert.equal(fullSheetUrl(url),
    '/api/projects/p1/evidence?page=4&rect=0.0000,0.0000,1.0000,1.0000&dpi=160');
});

test('withRect adds rect and dpi when the URL has neither', () => {
  assert.equal(withRect('/api/projects/p1/evidence?page=2', [0, 0, 1, 1], 120),
    '/api/projects/p1/evidence?page=2&rect=0.0000,0.0000,1.0000,1.0000&dpi=120');
  assert.equal(withRect(null, [0, 0, 1, 1]), null);
});

// Contract fixtures — the same four rectangles are asserted server-side in
// backend/tests/test_evidence_padding_contract.py.
const near = (got, want) => got.forEach((v, i) => assert.ok(Math.abs(v - want[i]) < 1e-9, `${got} vs ${want}`));

test('paddedRect matches the endpoint: plain padding', () => {
  near(paddedRect([0.30, 0.30, 0.60, 0.60]), [0.288, 0.288, 0.612, 0.612]);
});

test('paddedRect matches the endpoint: legibility floors around a small label', () => {
  near(paddedRect([0.50, 0.50, 0.52, 0.51]), [0.46, 0.4825, 0.56, 0.5275]);
});

test('paddedRect matches the endpoint: slides a crop back onto the sheet', () => {
  near(paddedRect([0.00, 0.00, 0.05, 0.02]), [0.0, 0.0, 0.1, 0.045]);
  near(paddedRect([0.97, 0.99, 1.00, 1.00]), [0.9, 0.955, 1.0, 1.0]);
});

test('paddedRect leaves the whole sheet whole', () => {
  near(paddedRect([0, 0, 1, 1]), [0, 0, 1, 1]);
});

test('visibleRect returns the on-screen part of a zoomed image', () => {
  const box = { left: 100, top: 100, right: 700, bottom: 500, width: 600, height: 400 };
  const img = { left: -200, top: -300, right: 1000, bottom: 1300, width: 1200, height: 1600 };
  near(visibleRect(box, img), [0.25, 0.25, 0.75, 0.5]);
});

test('visibleRect is null when the whole image is on screen (fitted view)', () => {
  const box = { left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600 };
  const img = { left: 100, top: 10, right: 700, bottom: 590, width: 600, height: 580 };
  assert.equal(visibleRect(box, img), null);
  assert.equal(visibleRect(box, null), null);
});

test('zoomForRect frames the outlined spot and clamps to the zoom range', () => {
  const box = { width: 1200, height: 700 };
  const fitted = { width: 500, height: 700 };
  // the plan frame of the anchor: nearly the whole sheet → barely above fitted
  const z = zoomForRect([0.1345, 0.1329, 0.6059, 0.8990], box, fitted);
  assert.ok(z > 0.7 && z < 1.3, String(z));
  // a small area label → clamps at the maximum
  assert.equal(zoomForRect([0.50, 0.50, 0.52, 0.51], box, fitted), ZOOM_MAX);
  assert.equal(zoomForRect(null, box, fitted), ZOOM_MIN);
});

test('clampZoom, rectKey and rectCentre', () => {
  assert.equal(clampZoom(0.2), ZOOM_MIN);
  assert.equal(clampZoom(99), ZOOM_MAX);
  assert.equal(clampZoom('x'), ZOOM_MIN);
  assert.equal(rectKey([0.1, 0.22, 0.333, 1]), '0.1000,0.2200,0.3330,1.0000');
  const c = rectCentre([0.2, 0.4, 0.6, 0.8]);
  assert.ok(Math.abs(c.x - 0.4) < 1e-9 && Math.abs(c.y - 0.6) < 1e-9);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getBboxPctRect,
  getEksplikacijaRect,
  getFocusedRoomRect,
  getTextLabelRect,
  getPolygonPdfPoints,
  getPolygonPdfRect,
  getPolygonPctPoints,
  getPolygonPctRect,
  pickOverlayRect,
} from './planOverlayGeometry.js';

test('getBboxPctRect: converts fractional room bbox to rendered page pixels', () => {
  assert.deepEqual(
    getBboxPctRect({ x: 0.25, y: 0.1, w: 0.5, h: 0.2 }, { width: 1000, height: 700 }),
    { left: 250, top: 70, width: 500, height: 140 }
  );
});

test('getEksplikacijaRect: converts PDF-space table bbox to rendered page pixels', () => {
  assert.deepEqual(
    getEksplikacijaRect([100, 50, 300, 90], {
      pageWidthPdf: 1000,
      pageHeightPdf: 500,
      renderedWidth: 500,
      renderedHeight: 250,
    }),
    { left: 50, top: 25, width: 100, height: 20 }
  );
});

test('getFocusedRoomRect: prefers precise room polygon on room page and table bbox on eksplikacija page', () => {
  const room = {
    puslapio_nr: 5,
    bbox_pct: { x: 0.1, y: 0.2, w: 0.3, h: 0.4 },
    polygon_pdf: [[100, 100], [400, 100], [400, 300], [100, 300]],
    page_width_pdf: 1000,
    page_height_pdf: 500,
    eksplikacija_row_bbox: [100, 50, 300, 90],
  };
  assert.deepEqual(
    getFocusedRoomRect({ room, page: 5, eksplikacijaPage: 7, renderedSize: { width: 1000, height: 500 }, pdfSize: { width: 1000, height: 500 } }),
    { type: 'room', left: 100, top: 100, width: 300, height: 200 }
  );
  assert.deepEqual(
    getFocusedRoomRect({ room, page: 7, eksplikacijaPage: 7, renderedSize: { width: 1000, height: 500 }, pdfSize: { width: 1000, height: 500 } }),
    { type: 'eksplikacija', left: 100, top: 50, width: 200, height: 40 }
  );
  assert.equal(
    getFocusedRoomRect({ room, page: 6, eksplikacijaPage: 7, renderedSize: { width: 1000, height: 500 }, pdfSize: { width: 1000, height: 500 } }),
    null
  );
});

test('getFocusedRoomRect: ignores legacy bbox_pct when no precise polygon exists', () => {
  const room = {
    puslapio_nr: 5,
    bbox_pct: { x: 0.18, y: 0.3, w: 0.18, h: 0.2 },
    eksplikacija_row_bbox: [100, 50, 300, 90],
  };
  assert.deepEqual(
    getFocusedRoomRect({
      room,
      page: 5,
      eksplikacijaPage: 5,
      renderedSize: { width: 1000, height: 500 },
      pdfSize: { width: 1000, height: 500 },
    }),
    { type: 'eksplikacija', left: 100, top: 50, width: 200, height: 40 }
  );
});

test('getPolygonPdfRect: maps precise polygon bounds from PDF space', () => {
  assert.deepEqual(
    getPolygonPdfRect([[100, 50], [300, 50], [300, 150], [100, 150]], {
      pageWidthPdf: 1000,
      pageHeightPdf: 500,
      renderedWidth: 500,
      renderedHeight: 250,
    }),
    { left: 50, top: 25, width: 100, height: 50 }
  );
});

test('getPolygonPdfPoints: maps precise polygon points from PDF space', () => {
  assert.deepEqual(
    getPolygonPdfPoints([[100, 50], [300, 150], [100, 150]], {
      pageWidthPdf: 1000,
      pageHeightPdf: 500,
      renderedWidth: 500,
      renderedHeight: 250,
    }),
    [[50, 25], [150, 75], [50, 75]]
  );
});

// ── polygon_pct path (room-graph rooms carry fractional coords, not PDF points) ──
// This is the fix for the wrong-room-halo bug: getFocusedRoomRect only checked
// polygon_pdf (absent on room-graph rooms) and fell through to coarse fallbacks.

test('getPolygonPctPoints: maps fractional points to rendered pixels, no Y-flip', () => {
  const poly = [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }];
  assert.deepEqual(
    getPolygonPctPoints(poly, { renderedWidth: 1000, renderedHeight: 800 }),
    [[100, 160], [500, 160], [500, 480]],
  );
});

test('getPolygonPctPoints: accepts [x,y] pair shape too', () => {
  assert.deepEqual(
    getPolygonPctPoints([[0.1, 0.2], [0.5, 0.2], [0.5, 0.6]], { renderedWidth: 1000, renderedHeight: 800 }),
    [[100, 160], [500, 160], [500, 480]],
  );
});

test('getPolygonPctPoints: returns null for <3 points, bad numbers, or zero render size', () => {
  assert.equal(getPolygonPctPoints([{ x_pct: 0.1, y_pct: 0.2 }], { renderedWidth: 1000, renderedHeight: 800 }), null);
  assert.equal(getPolygonPctPoints([{ x_pct: NaN, y_pct: 0 }, {}, {}], { renderedWidth: 1000, renderedHeight: 800 }), null);
  assert.equal(getPolygonPctPoints([{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }], { renderedWidth: 0, renderedHeight: 800 }), null);
});

test('getPolygonPctRect: returns the bbox of the mapped points', () => {
  const poly = [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }];
  assert.deepEqual(
    getPolygonPctRect(poly, { renderedWidth: 1000, renderedHeight: 800 }),
    { left: 100, top: 160, width: 400, height: 320 },
  );
});

test('getFocusedRoomRect: prefers polygon_pct over absent polygon_pdf and lands a room rect', () => {
  const room = { puslapio_nr: 2, polygon_pct: [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }] };
  assert.deepEqual(
    getFocusedRoomRect({ room, page: 2, renderedSize: { width: 1000, height: 800 }, pdfSize: { width: 600, height: 480 } }),
    { type: 'room', left: 100, top: 160, width: 400, height: 320 },
  );
});

test('getFocusedRoomRect: polygon_pct only fires on the room’s own page', () => {
  const room = { puslapio_nr: 5, polygon_pct: [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }] };
  assert.equal(getFocusedRoomRect({ room, page: 2, renderedSize: { width: 1000, height: 800 } }), null);
});

test('getTextLabelRect: pads a PDF text item so room-number clicks have a visible target', () => {
  assert.deepEqual(
    getTextLabelRect({
      str: '103',
      x: 250,
      y: 180,
      width: 24,
      height: 10,
    }, { padding: 8 }),
    { left: 242, top: 172, width: 40, height: 26 }
  );
});

test('getTextLabelRect: rejects unrelated text and empty dimensions', () => {
  assert.equal(getTextLabelRect({ str: 'A-103', x: 1, y: 2, width: 3, height: 4 }, { roomNr: '103' }), null);
  assert.equal(getTextLabelRect({ str: '103', x: 1, y: 2, width: 0, height: 4 }, { roomNr: '103' }), null);
});

test('pickOverlayRect: precise polygon match wins over everything', () => {
  const focused = { type: 'room', left: 0, top: 0, width: 10, height: 10 };
  const label = { left: 99, top: 99, width: 8, height: 8 };
  assert.deepEqual(pickOverlayRect(focused, label), focused);
});

test('pickOverlayRect: text label on plan wins over eksplikacija row when both present', () => {
  // Regression for screenshot bug: floor plan and eksplikacija share a page,
  // getFocusedRoomRect returns type 'eksplikacija', but the room number is
  // also drawn on the plan and was found by the PDF text-layer search.
  const focused = { type: 'eksplikacija', left: 100, top: 50, width: 200, height: 40 };
  const label = { left: 600, top: 400, width: 30, height: 30 };
  assert.deepEqual(
    pickOverlayRect(focused, label),
    { type: 'label', left: 600, top: 400, width: 30, height: 30 },
  );
});

test('pickOverlayRect: eksplikacija row used as last resort when no label found', () => {
  const focused = { type: 'eksplikacija', left: 100, top: 50, width: 200, height: 40 };
  assert.deepEqual(pickOverlayRect(focused, null), focused);
});

test('pickOverlayRect: text label alone surfaces when nothing else matches', () => {
  const label = { left: 600, top: 400, width: 30, height: 30 };
  assert.deepEqual(
    pickOverlayRect(null, label),
    { type: 'label', left: 600, top: 400, width: 30, height: 30 },
  );
});

test('pickOverlayRect: returns null when both inputs are missing', () => {
  assert.equal(pickOverlayRect(null, null), null);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getBboxPctRect,
  getEksplikacijaRect,
  getFocusedRoomRect,
  getTextLabelRect,
  getPolygonPdfPoints,
  getPolygonPdfRect,
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

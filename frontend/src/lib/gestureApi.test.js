// frontend/src/lib/gestureApi.test.js
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { visionFill, lassoRerun, addSymbol, removeSymbol, overrideQuantity, colorZone } from './gestureApi.js';

let lastReq = null;
beforeEach(() => {
  lastReq = null;
  globalThis.fetch = async (url, opts) => {
    lastReq = { url, body: JSON.parse(opts.body) };
    return { ok: true, status: 200, json: async () => ({ ok: true, polygon_pct: [[0,0],[1,0],[1,1],[0,1]] }) };
  };
});

test('visionFill posts to /api/vision-fill with click coords', async () => {
  await visionFill({ projectId: 'p1', pageIdx: 0, clickXyPct: [0.4, 0.5] });
  assert.equal(lastReq.url, '/api/vision-fill');
  assert.deepEqual(lastReq.body.click_xy_pct, [0.4, 0.5]);
  assert.equal(lastReq.body.project_id, 'p1');
});

test('lassoRerun posts polygon to /api/lasso-rerun', async () => {
  await lassoRerun({
    projectId: 'p1', pageIdx: 0,
    lassoPolygonPct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
  });
  assert.equal(lastReq.url, '/api/lasso-rerun');
  assert.equal(lastReq.body.lasso_polygon_pct.length, 3);
});

test('addSymbol posts an add_symbol edit to recompute', async () => {
  await addSymbol({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', pointXyPct: [0.3, 0.3],
    currentAssumptions: {},
  });
  assert.equal(lastReq.url, '/api/recompute-quantities');
  assert.equal(lastReq.body.edits[0].field, 'add_symbol');
  assert.equal(lastReq.body.edits[0].target_pozicija_id, 'p1');
});

test('removeSymbol posts a remove_symbol edit', async () => {
  await removeSymbol({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'remove_symbol');
});

test('overrideQuantity posts an override_pozicija edit', async () => {
  await overrideQuantity({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', newValue: 99, currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'override_pozicija');
  assert.equal(lastReq.body.edits[0].new_value, 99);
});

test('colorZone posts a color_zone edit', async () => {
  await colorZone({
    rooms: [{ id: 'r1' }], pozicijos: [],
    targetRoomId: 'r1',
    colorRgb: [10, 20, 30],
    polygonsPct: [[[0,0],[1,0],[1,1]]],
    currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'color_zone');
  assert.deepEqual(lastReq.body.edits[0].color_rgb, [10, 20, 30]);
});

test('visionFill propagates AbortSignal', async () => {
  const ac = new AbortController();
  ac.abort();
  globalThis.fetch = async (url, opts) => {
    if (opts.signal?.aborted) {
      const err = new Error('aborted');
      err.name = 'AbortError';
      throw err;
    }
    return { ok: true, json: async () => ({}) };
  };
  await assert.rejects(
    visionFill({ projectId: 'p1', pageIdx: 0, clickXyPct: [0.5, 0.5], signal: ac.signal }),
    /aborted/
  );
});

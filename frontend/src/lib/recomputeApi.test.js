import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recompute } from './recomputeApi.js';

// Mock global fetch
globalThis.fetch = async (url, opts) => {
  if (url.endsWith('/api/recompute-quantities')) {
    const body = JSON.parse(opts.body);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        rooms: body.rooms.map(r => ({ ...r, dazai_l: 12.5 })),
        pozicijos: [],
        assumptions: body.current_assumptions,
      }),
    };
  }
  throw new Error('unexpected url ' + url);
};

test('recompute() POSTs to backend and returns updated rooms', async () => {
  const result = await recompute({
    rooms: [{ name: 'K1', dazomas_plotas_m2: 50 }],
    edits: [{ field: 'paint_class', new_value: 2 }],
    current_assumptions: { paint_class: 1 },
  });
  assert.equal(result.rooms.length, 1);
  assert.equal(result.rooms[0].dazai_l, 12.5);
});

test('recompute() throws on non-OK response', async () => {
  globalThis.fetch = async () => ({
    ok: false, status: 400,
    json: async () => ({ detail: "bad field" }),
  });
  await assert.rejects(
    () => recompute({ rooms: [], edits: [{ field: 'x', new_value: 1 }], current_assumptions: {} }),
    /bad field/
  );
});

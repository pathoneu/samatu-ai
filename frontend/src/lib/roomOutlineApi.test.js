import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchOutlineMerge, fetchOutlineSet } from './roomOutlineApi.js';

function stubFetch() {
  const bodies = [];
  globalThis.fetch = async (_url, init) => { bodies.push(JSON.parse(init.body)); return { ok: true, json: async () => ({ status: 'ok' }) }; };
  return bodies;
}

test('his answers to „Kas atimama?" ride with the holes on outline-set and outline-merge', async () => {
  const bodies = stubFetch();
  const ring = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]];
  const hole = [[0.12, 0.12], [0.13, 0.12], [0.13, 0.13]];
  await fetchOutlineSet('p', '01', { page: 1, polygon_pct: ring, holes: [hole], holes_walls: [false] });
  await fetchOutlineSet('p', '01', { page: 1, polygon_pct: ring, holes: [hole] });
  await fetchOutlineSet('p', '01', { page: 1, polygon_pct: ring, holes: [], holes_walls: [false] });
  await fetchOutlineMerge('p', '02', { page: 1, kept_nr: '01', polygon_pct: ring, holes: [hole], holes_walls: [true] });
  assert.deepEqual(bodies[0].holes_walls, [false]);
  assert.equal('holes_walls' in bodies[1], false);
  assert.equal('holes' in bodies[2] || 'holes_walls' in bodies[2], false);
  assert.deepEqual(bodies[3].holes_walls, [true]);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildRecomputeContext, RECOMPUTE_CONTEXT_KEYS } from './recomputeContext.js';

test('carries the eksplikacija ceiling anchor and every reader output', () => {
  const blob = {
    _ceiling_anchor: { total_area_m2: 165.61, label: 'Iš viso', page: 2 },
    _walls_anchor: { total_area_m2: 220, label: 'sienų apdailos plano legenda', page: 3 },
    _floor_anchors: { grindjuostes: { total: 53.69, unit: 'm' }, laminatas: { total: 76.65, unit: 'm2' } },
    _door_types: { '101': 'beapvadinės' },
    detected_symbols_summary: { rozetes: 66 },
    _plyteliu_specs: [{ vieta: 'vonia' }],
    _symbol_legend: { x: 1 },
    _duru_ziniarastis: { status: 'lentele' },
    _vector_symbols: { difuzoriai: { defined: true, count: 9 } },
    bendras_plotas_m2: 165.61,
    v9_meta: { a: 1 },
    _overrides: { stretch_ceiling_override: { '110': 1 } },
    patalpos: [{ nr: '101' }],           // not context — must not leak in
  };
  const ctx = buildRecomputeContext(blob);
  assert.deepEqual(Object.keys(ctx).sort(), [...RECOMPUTE_CONTEXT_KEYS].sort());
  assert.equal(ctx._ceiling_anchor.total_area_m2, 165.61);
  assert.equal(ctx._walls_anchor.total_area_m2, 220);
  assert.equal(ctx._floor_anchors.grindjuostes.total, 53.69);
  assert.equal(ctx._overrides.stretch_ceiling_override['110'], 1);
  assert.equal(ctx._vector_symbols.difuzoriai.count, 9);
  assert.equal(ctx._duru_ziniarastis.status, 'lentele');
  assert.equal('patalpos' in ctx, false);
});

test('tolerates a missing blob — every key present, all undefined', () => {
  const ctx = buildRecomputeContext(undefined);
  assert.deepEqual(Object.keys(ctx).sort(), [...RECOMPUTE_CONTEXT_KEYS].sort());
  for (const k of RECOMPUTE_CONTEXT_KEYS) assert.equal(ctx[k], undefined);
});

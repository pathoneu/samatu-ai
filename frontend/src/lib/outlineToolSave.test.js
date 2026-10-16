import test from 'node:test';
import assert from 'node:assert/strict';
import { saveOutlineTool } from './outlineToolSave.js';

const ring = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]];
const project = () => ({
  patalpos: [
    { nr: '01', pavadinimas: 'A', plotas_m2: 12, polygon_pct: ring },
    { nr: '02', pavadinimas: 'B', plotas_m2: 9 },
    { nr: '03', pavadinimas: 'C', plotas_m2: 5, _angos_sienose: { page: 1, angos: [] } },
  ],
  v8_rooms: [{ nr: '01' }, { nr: '02' }, { nr: '03' }],
  _apimtis: { patalpos_ne: [], darbai_ne: [] },
});

test('set: the answer lands on the room, holes travel with the request', async () => {
  const calls = [];
  const api = {
    outlineSet: async (nr, body) => {
      calls.push([nr, body]);
      return { status: 'ok', room: { polygon_pct: body.polygon_pct, polygon_holes_pct: body.holes, _konturas: { plotas_m2: 11.5 } } };
    },
  };
  const holes = [[[0.12, 0.12], [0.13, 0.12], [0.13, 0.13]]];
  const patch = await saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: ring, holes }, { api, getFresh: project });
  assert.deepEqual(calls, [['01', { page: 1, polygon_pct: ring, holes }]]);
  assert.deepEqual(patch.patalpos[0].polygon_holes_pct, holes);
  assert.equal(patch.patalpos[0].pavadinimas, 'A');            // nothing but geometry changes
  assert.equal(patch.v8_rooms[0].polygon_holes_pct, holes);
  assert.equal(patch._apimtis, undefined);
});

test('split: both halves land in ONE patch; the answers never speak for the two rooms that changed', async () => {
  const api = {
    outlineSet: async (nr, body) => ({
      status: 'ok',
      room: { polygon_pct: body.polygon_pct, _konturas: { nr } },
      kitu_angos: { '01': { stale: nr }, '02': { stale: nr }, '03': { page: 1, angos: [{ i: nr }] } },
    }),
  };
  const other = [[0.2, 0.1], [0.3, 0.1], [0.3, 0.2]];
  const patch = await saveOutlineTool(
    { kind: 'split', nr: '01', page: 1, polygon: ring, holes: [], other: { nr: '02', polygon: other, holes: [] } },
    { api, getFresh: project },
  );
  const [a, b, c] = patch.patalpos;
  assert.deepEqual(a.polygon_pct, ring);
  assert.deepEqual(b.polygon_pct, other);
  assert.equal(a._angos_sienose, undefined);
  assert.equal(b._angos_sienose, undefined);
  assert.deepEqual(c._angos_sienose, { page: 1, angos: [{ i: '02' }] });
});

test('split: a refused second half refuses the whole operation', async () => {
  let n = 0;
  const api = { outlineSet: async () => (n++ ? { status: 'bad', detail: 'Išpjova turi būti visa kontūro viduje' } : { status: 'ok', room: {} }) };
  await assert.rejects(
    saveOutlineTool({ kind: 'split', nr: '01', page: 1, polygon: ring, other: { nr: '02', polygon: ring } }, { api, getFresh: project }),
    /kontūro viduje/,
  );
});

test('merge: the kept room bills both rows and holds both rooms\' openings; the scope is not touched', async () => {
  const api = {
    outlineMerge: async (gone, body) => {
      assert.equal(gone, '02');
      assert.equal(body.kept_nr, '01');
      return {
        status: 'ok',
        rooms: {
          '01': { polygon_pct: body.polygon_pct, _konturas: { prijungta: ['02'] } },
          '02': { polygon_pct: null, _konturas: { saltinis: 'sujungta', i: '01', plotas_m2: 0 } },
        },
        sujungimas: {
          '01': { plotas_m2: 21, plotas_saltinis: 'eksplikacija_sujungta', _plotas_pries_sujungima: 12,
            _sujungimas: { su: ['02'] }, elementai: [{ tipas: 'langas', kiekis: 1, _is_patalpos: '02' }], _sujungta_i: null },
          '02': { plotas_m2: 9, elementai: [], _sujungta_i: '01', _elementai_pries_sujungima: [{ tipas: 'langas', kiekis: 1 }] },
        },
        kitu_angos: {},
      };
    },
  };
  const patch = await saveOutlineTool({ kind: 'merge', keptNr: '01', goneNr: '02', page: 1, polygon: ring }, { api, getFresh: project });
  assert.equal(patch._apimtis, undefined);
  const [kept, gone] = patch.patalpos;
  assert.equal(kept.plotas_m2, 21);
  assert.equal(kept.plotas_saltinis, 'eksplikacija_sujungta');
  assert.equal(kept.pavadinimas, 'A');
  assert.equal(kept.elementai[0]._is_patalpos, '02');
  assert.equal('polygon_pct' in gone, false);
  assert.equal(gone._sujungta_i, '01');
  assert.deepEqual(gone.elementai, []);
  assert.equal(gone.plotas_m2, 9);                 // its table row stays — the engine bills it inside 01
  assert.equal(patch.v8_rooms[1]._sujungta_i, '01');
});

test('unknown operations and refused answers throw with the server sentence', async () => {
  await assert.rejects(saveOutlineTool({ kind: 'x' }, { api: {}, getFresh: project }), /Nežinomas/);
  const api = { outlineSet: async () => ({ status: 'nope', detail: 'Kontūras per mažas arba išsigimęs' }) };
  await assert.rejects(saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: ring }, { api, getFresh: project }), /per mažas/);
});

test('mergeFinishWarning: says what moves between lines when the finishes differ, nothing when they agree', async () => {
  const { mergeFinishWarning } = await import('./outlineToolSave.js');
  const kitchen = { nr: '04', plotas_m2: 26.31, grindu_danga: 'plyteles', plyteles_sienos_m2: 1.4 };
  const living = { nr: '05', plotas_m2: 35.5, grindu_danga: 'minksta', plyteles_sienos_m2: 0 };
  assert.equal(mergeFinishWarning(kitchen, living, '04', '05'),
    'Patalpų apdaila skiriasi: 05 grindys parketas arba laminatas, 04 plytelės — sujungus visam plotui (61,81 m²) '
    + 'bus taikoma 04 apdaila; 35,50 m² pereis iš parketo arba laminato į plyteles.');
  assert.equal(mergeFinishWarning(living, { ...living, nr: '06' }, '05', '06'), null);
  const bath = { nr: '03', plotas_m2: 6, plyteles_grindys_m2: 6, plyteles_sienos_m2: 18 };
  const hall = { nr: '02', plotas_m2: 4, plyteles_grindys_m2: 4 };
  assert.equal(mergeFinishWarning(hall, bath, '02', '03'),
    'Patalpų apdaila skiriasi: 03 sienose plytelės, 02 — ne — sujungus visam plotui (10,00 m²) bus taikoma 02 apdaila; '
    + '03 sienų plytelių (18,00 m²) sąmatoje nebeliks.');
});

test('set: his answers to „Kas atimama?" travel as holes_walls; none given, none sent', async () => {
  const calls = [];
  const api = { outlineSet: async (nr, body) => { calls.push(body); return { status: 'ok', room: { polygon_pct: body.polygon_pct } }; } };
  const holes = [[[0.12, 0.12], [0.13, 0.12], [0.13, 0.13]]];
  await saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: ring, holes, holesWalls: [false] }, { api, getFresh: project });
  await saveOutlineTool({ kind: 'set', nr: '01', page: 1, polygon: ring, holes }, { api, getFresh: project });
  assert.deepEqual(calls[0].holes_walls, [false]);
  assert.equal('holes_walls' in calls[1], false);
});

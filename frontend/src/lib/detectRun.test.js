import test from 'node:test';
import assert from 'node:assert/strict';
import {
  STAGE_IDS, FEATURES, allFeatures, toggleFeature, canStart, requestBody, viewOf, needsPolling,
  statusMark, headline, scopeCounts, summaryText, buttonLabel,
} from './detectRun.js';

const stages = (statuses) => STAGE_IDS.map((id, i) => ({
  id, label_lt: id[0].toUpperCase() + id.slice(1), about_lt: `apie ${id}`, status: statuses[i] || 'pending', note: null,
}));

test('the stage ids are the server\'s, in the lane\'s order (openings before walls)', () => {
  assert.deepEqual(STAGE_IDS, ['mastelis', 'tekstas', 'planas', 'konturai', 'angos', 'sienos', 'grindys', 'kiekiai']);
});

test('ticking walls ticks the outlines they are added along; unticking outlines unticks what needs them', () => {
  const none = { plotai: true, konturai: false, sienos: false, angos: false, grindys: false };
  assert.deepEqual(toggleFeature(none, 'sienos', true), { ...none, konturai: true, sienos: true, angos: true });
  const all = allFeatures();
  assert.deepEqual(toggleFeature(all, 'konturai', false), { ...all, konturai: false, sienos: false, angos: false });
  assert.deepEqual(toggleFeature(all, 'grindys', false), { ...all, grindys: false });
  // an outline brings its openings, and openings need their outline
  assert.deepEqual(toggleFeature(none, 'konturai', true), { ...none, konturai: true, angos: true });
  assert.deepEqual(toggleFeature(all, 'angos', false), { ...all, konturai: false, sienos: false, angos: false });
});

test('„plotai" cannot be unticked and alone is not a run', () => {
  const only = toggleFeature({ plotai: true }, 'plotai', false);
  assert.equal(only.plotai, true);
  assert.equal(canStart(only), false);
  assert.equal(canStart(toggleFeature(only, 'grindys', true)), true);
});

test('the request body: one sheet or the set, every feature named', () => {
  assert.deepEqual(requestBody([3, 1, 3], allFeatures()), { pages: [1, 3], features: allFeatures() });
  const body = requestBody('all', { grindys: true });
  assert.equal(body.pages, 'all');
  assert.deepEqual(body.features, { plotai: true, konturai: false, sienos: false, angos: false, grindys: true });
});

test('a running snapshot: the current stage, its education text, the progress', () => {
  const v = viewOf({ job: 'j', stages: stages(['done', 'done', 'done', 'running']) });
  assert.equal(v.current.id, 'konturai');
  assert.equal(v.current.about, 'apie konturai');
  assert.equal(v.progress, 3 / 8);
  assert.equal(v.terminal, false);
  assert.equal(headline(v, [1]), 'Konturai… 4/8 (pritaikoma lapui 1)');
  assert.equal(needsPolling({ job: 'j', result_ready: false, failed: false }), true);
});

test('the server leaves „kiekiai" running; the browser\'s landing finishes it', () => {
  const snap = { job: 'j', result_ready: true, stages: stages(['done', 'done', 'done', 'done', 'done', 'done', 'skipped', 'perduota']) };
  assert.equal(needsPolling(snap), false);
  const handed = viewOf(snap);
  assert.equal(handed.current.id, 'kiekiai');
  assert.equal(handed.current.status, 'running');
  assert.equal(handed.terminal, false);
  const landing = viewOf(snap, { status: 'running', note: null });
  assert.equal(landing.current.id, 'kiekiai');
  assert.equal(landing.done, false);
  const landed = viewOf(snap, { status: 'done', note: '8 kontūrai' });
  assert.equal(landed.done, true);
  assert.equal(landed.terminal, true);
  assert.equal(landed.progress, 1);
  assert.equal(landed.stages.at(-1).note, '8 kontūrai');
  assert.equal(headline(landed, 'all'), 'Perskaityta (visi lapai)');
});

test('a failure is named by its stage, never a generic error', () => {
  const v = viewOf({ job: 'j', failed: true, stages: stages(['done', 'done', 'done', 'failed', 'skipped', 'skipped', 'skipped', 'skipped']) });
  assert.equal(v.failed, true);
  assert.equal(v.failedStage.id, 'konturai');
  assert.equal(headline(v, [1]), 'Nepavyko: Konturai (pritaikoma lapui 1)');
  // the browser's own step can fail too — after the server finished
  const snap = { job: 'j', result_ready: true, stages: stages(['done', 'done', 'done', 'done', 'done', 'done', 'done', 'running']) };
  const v2 = viewOf(snap, { status: 'failed', note: 'Kiekių perskaičiuoti nepavyko' });
  assert.equal(v2.failedStage.id, 'kiekiai');
});

test('before the first answer the list is the stage names, all waiting', () => {
  const v = viewOf(null);
  assert.deepEqual(v.stages.map((s) => s.id), STAGE_IDS);
  assert.equal(v.current.id, 'mastelis');
  assert.equal(statusMark('done'), '✓');
  assert.equal(statusMark('running'), '●');
  assert.equal(statusMark('skipped'), '–');
  assert.equal(statusMark('pending'), '○');
});

const project = {
  patalpos: [
    { nr: '01', polygon_source: 'corrected', perimetras_saltinis: 'matmenu_eilutes', grindu_danga_saltinis: 'grindu_planas',
      _angos_sienose: { angos: [{ i: '02', nupiesta: 'durys' }, { i: 'laukas', nupiesta: 'langas' }] } },
    { nr: '02', polygon_source: 'vektoriniai_konturai', perimetras_saltinis: 'konturo_ivertis',
      _angos_sienose: { angos: [{ i: '01', nupiesta: 'durys' }, { i: 'vidus' }] } },
    { nr: '03', polygon_source: 'synthesized_from_bbox', perimetras_saltinis: 'plano_matmenys' },
    { nr: '09', polygon_source: 'vektoriniai_konturai' },
  ],
};

test('the counts are over the run\'s rooms, a shared door once', () => {
  assert.deepEqual(scopeCounts(project, ['01', '02', '03']), {
    patalpos: 3, konturai: 2, jusu: 1, angos: 3, perimetrai: 2, grindys: 1,
  });
});

test('the toast says the numbers in Lithuanian, only for what was read', () => {
  const c = { patalpos: 11, konturai: 8, jusu: 4, angos: 23, perimetrai: 6, grindys: 11 };
  assert.equal(summaryText(c), '8 kontūrai, 23 angos, 6 perimetrai iš matmenų, danga 11 iš 11. Jūsų pataisyti kontūrai (4) palikti.');
  assert.equal(summaryText({ ...c, konturai: 1, angos: 11, perimetrai: 21, jusu: 0 }, { konturai: true, angos: true, sienos: true }),
    '1 kontūras, 11 angų, 21 perimetras iš matmenų.');
  assert.equal(summaryText({ patalpos: 0 }), 'Šiame lape eksplikacijos patalpų nerasta — niekas nepakeista.');
});

test('the button reads „iš naujo" once the sheet\'s plan has been read', () => {
  const p = { _meta: { geometrija: { grupes: [[1, 2, 3], [8]] } } };
  assert.equal(buttonLabel(p, 2), 'Perskaityti iš naujo');
  assert.equal(buttonLabel(p, 5), 'Perskaityti lapą');
  assert.equal(buttonLabel({}, 1), 'Perskaityti lapą');
  assert.equal(FEATURES.length, 5);
});

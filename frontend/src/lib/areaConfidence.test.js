import test from 'node:test';
import assert from 'node:assert/strict';
import {
  computeAreaConfidence, AREA_AGREEMENT_TOLERANCE_PCT, inferPlotasSource, dominantAreaSource, areaSourceSentence,
} from './areaConfidence.js';

test('computeAreaConfidence: room with eksplikacija + agreeing manual polygon → high', () => {
  const room = {
    nr: '01', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 12.6,  // 0.8% off, within tolerance
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources.sort(), ['eksplikacija', 'manual_polygon']);
});

test('computeAreaConfidence: eksplikacija only (no polygon) → high (deterministic source-of-truth)', () => {
  const room = {
    nr: '02', plotas_m2: 12.5, plotas_source: 'eksplikacija',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources, ['eksplikacija']);
});

test('computeAreaConfidence: manual polygon only → high (user-set, authoritative)', () => {
  const room = {
    nr: '03', plotas_m2: 8.4, plotas_source: 'manual_polygon',
    polygon_pdf: [[0, 0], [10, 0], [5, 5]],
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'manual_polygon');
});

test('computeAreaConfidence: vision-only (no eksplikacija, no polygon) → low', () => {
  const room = {
    nr: '04', plotas_m2: 6.0, plotas_source: 'vision',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.primarySource, 'vision');
});

test('computeAreaConfidence: eksplikacija + manual polygon DISAGREE (>5% off) → low', () => {
  const room = {
    nr: '05', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 18.0,  // 44% off
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.disagreement, true);
});

test('computeAreaConfidence: user_verified_at promotes medium → high', () => {
  const room = {
    nr: '06', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    user_verified_at: '2026-05-02T10:00:00Z',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.ok(r.userVerified);
});

test('computeAreaConfidence: room with no plotas_m2 → unknown', () => {
  const room = { nr: '07', plotas_m2: null };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'unknown');
});

test('computeAreaConfidence: legacy room (plotas_m2 but no plotas_source) → backfilled to eksplikacija high', () => {
  // Simulates a project extracted before Phase C-2 Task 2 landed. The backend
  // didn't tag plotas_source on these, but pdfplumber eksplikacija was the
  // dominant historical path — single-source eksplikacija is high-confidence.
  const room = { nr: '08', plotas_m2: 7.36, pavadinimas: 'Tambūras' };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'eksplikacija');
});

test('inferPlotasSource: explicit plotas_source → returned as-is', () => {
  const room = { nr: '09', plotas_m2: 10, plotas_source: 'vision' };
  assert.equal(inferPlotasSource(room), 'vision');
});

test('inferPlotasSource: legacy room → backfilled to eksplikacija', () => {
  const room = { nr: '10', plotas_m2: 12 };
  assert.equal(inferPlotasSource(room), 'eksplikacija');
});

test('inferPlotasSource: manual polygon takes precedence over missing flag', () => {
  const room = { nr: '11', plotas_m2: 8, polygon_pdf: [[0,0],[1,0],[0,1]], polygon_source: 'manual' };
  assert.equal(inferPlotasSource(room), 'manual_polygon');
});

test('inferPlotasSource: room with no plotas_m2 → null', () => {
  assert.equal(inferPlotasSource({ nr: '12', plotas_m2: null }), null);
});

test('AREA_AGREEMENT_TOLERANCE_PCT is 5%', () => {
  // Spec §3.2.1 specifies ±2% in the "high" path, but allow up to ±5% for "agreement"
  // because hand-drawn polygons trace edges with imprecision. The badge stays "high"
  // when sources are within ±2% AND drops to "low" when >5% — between, it stays "medium".
  assert.ok(AREA_AGREEMENT_TOLERANCE_PCT > 0 && AREA_AGREEMENT_TOLERANCE_PCT <= 0.05);
});


test('plano_uzrasas: the designer\'s area label read from the PDF text is a deterministic single source → high, own chip type (2026-09-06)', () => {
  const room = { plotas_m2: 37.86, plotas_saltinis: 'plano_uzrasas', plotas_source: 'vision' };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'plano_uzrasas');
  assert.deepEqual(r.sources.map((s) => s.type), ['plano_uzrasas']);
  assert.equal(inferPlotasSource(room), 'plano_uzrasas');
});

test('dominantAreaSource: the source most rooms share, said once in the list header', () => {
  const eks = { plotas_m2: 4.48, plotas_saltinis: 'eksplikacija' };
  const plan = { plotas_m2: 6.9, plotas_saltinis: 'plano_uzrasas' };
  assert.equal(dominantAreaSource([eks, eks, plan]), 'eksplikacija');
  assert.equal(dominantAreaSource([plan, plan, eks]), 'plano_uzrasas');
  assert.equal(dominantAreaSource([plan, eks]), 'plano_uzrasas', 'a tie goes to the source met first');
  assert.equal(dominantAreaSource([{ plotas_m2: null }, {}]), null);
  assert.equal(dominantAreaSource(null), null);
});

test('areaSourceSentence: every area source is said in words with its sheet, never the raw id (B2-B)', async () => {
  const { readFileSync } = await import('node:fs');
  const lt = JSON.parse(readFileSync(new URL('../i18n/lt.json', import.meta.url), 'utf8'));
  const words = lt.project.eksplikacijaPopover.source;
  const cases = [
    [{ plotas_m2: 12, plotas_saltinis: 'eksplikacija', eksplikacija_source_page: 2 }, 'eksplikacija', 2],
    [{ plotas_m2: 12, plotas_saltinis: 'eksplikacija' }, 'eksplikacijaNoPage', null],
    [{ plotas_m2: 12, plotas_saltinis: 'plano_uzrasas', puslapio_nr: 3 }, 'plano_uzrasas', 3],
    [{ plotas_m2: 12, plotas_source: 'manual_polygon', page_nr: 1 }, 'manual_polygonNoPage', 1],
    [{ plotas_m2: 12, plotas_source: 'vision', page_nr: 4 }, 'vision', 4],
    [{ plotas_m2: 12, plotas_source: 'dimension' }, 'dimensionNoPage', null],
    [{ plotas_m2: 12, plotas_source: 'something_new', page_nr: 1 }, 'otherNoPage', 1],
  ];
  for (const [room, id, page] of cases) {
    const s = areaSourceSentence(room);
    assert.equal(s.id, id);
    assert.equal(s.page, page);
    assert.equal(typeof words[s.id], 'string', `lt.json has no sentence for ${s.id}`);
    assert.doesNotMatch(words[s.id], /pdfplumber|Šaltinis|vision|eksplikacij/i);
  }
  assert.equal(words.eksplikacija.replace('{{page}}', '2'), 'Plotas perskaitytas iš brėžinio patalpų lentelės, 2 lapas.');
});

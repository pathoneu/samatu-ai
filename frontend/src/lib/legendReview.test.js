import test from 'node:test';
import assert from 'node:assert/strict';
import {
  applyCreate, boxFromPctDrag, buildCreate, createLabel, decisionsFor, displayBoxToMediaBox, displayPctToMediaPt,
  initialReview, journalRows, keptInstances, legendCursorHint, legendLedgerText, legendPill, legendRowsToSave,
  LEGEND_PHASES, LEGEND_SOURCE, marksWord, matchSavedLegend, MAX_ACCEPTS_PER_ROW, perPage, perPageText, proposalsFrom,
  rowName, rowsOf, rowsToCreate, syncLegendRows, blankRows, blankSamataRow, BLANK_REASON,
  BOX_EMPTY, boxFailureText, countingText, legendGotoPage, noLegendText, onSheetsText, requestErrorText, reviewOutcome, rowsWord, summaryText,
} from './legendReview.js';

const A3 = { size: { width: 1000, height: 500 }, rotation: 0 };

const rowA = { row_id: 'p3-a', page: 3, text: 'Rozetė', countable: true, glyph_kind: 'spalvotas', glyph_bbox_pct: [0.1, 0.1, 0.11, 0.11] };
const rowB = { row_id: 'p3-b', page: 3, text: 'Jungiklis', countable: true, glyph_kind: 'juodas', glyph_bbox_pct: [0.1, 0.2, 0.11, 0.21] };
const rowS = { row_id: 'p3-s', page: 3, text: 'LED juosta', countable: false, reason_lt: 'pavyzdys' };
const inst = (page, x, y, score = null) => ({ page, box_pct: [x - 0.01, y - 0.01, x + 0.01, y + 0.01], score, saltinis: 'vektoriai' });
const counts = {
  'p3-a': { row_id: 'p3-a', status: 'ok', count: 3, saltinis: 'vektoriai', instances: [inst(3, 0.5, 0.5), inst(3, 0.6, 0.5), inst(4, 0.2, 0.2)] },
  'p3-b': { row_id: 'p3-b', status: 'ok', count: 0, saltinis: 'rastras', instances: [] },
  'p3-s': { row_id: 'p3-s', status: 'neskaiciuojama', count: 0, instances: [] },
};
const pages = [A3, A3, A3, A3];

test('phases are the documented order', () => {
  assert.deepEqual(LEGEND_PHASES, ['suggesting', 'proposed', 'box', 'reading', 'counting', 'review', 'creating']);
});

test('display fractions map to mediabox points, rotation undone', () => {
  assert.deepEqual(displayPctToMediaPt(0.5, 0.25, A3), { x: 500, y: 125 });
  // a /Rotate 90 sheet: display (1 − y, x) ← mediabox (x, y), so display (0.75, 0.1) is mediabox (0.1, 0.25)
  assert.deepEqual(displayPctToMediaPt(0.75, 0.1, { size: { width: 400, height: 800 }, rotation: 90 }), { x: 40, y: 200 });
  assert.equal(displayPctToMediaPt(0.5, 0.5, { size: null }), null);
  assert.deepEqual(displayBoxToMediaBox([0.1, 0.2, 0.3, 0.4], A3), [100, 100, 300, 200]);
});

test('a drag box is clamped and refused when too small', () => {
  assert.deepEqual(boxFromPctDrag({ x: 0.4, y: 0.6 }, { x: 0.2, y: 0.3 }), [0.2, 0.3, 0.4, 0.6]);
  assert.equal(boxFromPctDrag({ x: 0.2, y: 0.2 }, { x: 0.205, y: 0.4 }), null);
  assert.deepEqual(boxFromPctDrag({ x: -0.1, y: 0.1 }, { x: 0.3, y: 1.2 }), [0, 0.1, 0.3, 1]);
});

test('proposals keep legends that have rows; rows are taken once', () => {
  const answer = { page: 3, legends: [{ bbox_pct: [0, 0, 0.2, 0.2], rows: [rowA, rowB] }, { bbox_pct: [0.5, 0.5, 0.6, 0.6], rows: [] }, { bbox_pct: [0.3, 0.3, 0.4, 0.4], rows: [rowA, rowS] }] };
  const props = proposalsFrom(answer);
  assert.equal(props.length, 2);
  assert.deepEqual(props.map((p) => p.id), ['3:0', '3:1']);
  assert.deepEqual(rowsOf(props).map((r) => r.row_id), ['p3-a', 'p3-b', 'p3-s']);
  assert.deepEqual(proposalsFrom({ page: 1, legends: [] }), []);
});

test('the review starts from a proposal: found rows ✔, empty / sample rows 🗑', () => {
  const review = initialReview([rowA, rowB, rowS], counts);
  assert.equal(review['p3-a'].keep, true);
  assert.equal(review['p3-b'].keep, false);
  assert.equal(review['p3-s'].keep, false);
  // a count with no instance to show (candidates only on text letters) is not proposed ✔
  assert.equal(initialReview([rowA], { 'p3-a': { status: 'ok', count: 2, instances: [] } })['p3-a'].keep, false);
  // a sample row is never created even if kept
  assert.deepEqual(rowsToCreate([rowA, rowS], { 'p3-a': { keep: true }, 'p3-s': { keep: true } }, counts).map((r) => r.row_id), ['p3-a']);
  assert.equal(createLabel(2), 'Sukurti kiekius (2)');
});

test('kept instances, per page and the Lithuanian count forms', () => {
  const kept = keptInstances(counts['p3-a'], new Set(['p3-a#1']));
  assert.deepEqual(kept.map((i) => i.id), ['p3-a#0', 'p3-a#2']);
  assert.deepEqual(perPage(kept), [{ page: 3, n: 1 }, { page: 4, n: 1 }]);
  assert.equal(perPageText([{ page: 1, n: 3 }, { page: 3, n: 1 }, { page: 5, n: 0 }]), '3 ženklai lape 1, 1 ženklas lape 3');
  assert.equal(perPageText([]), 'ženklų nerasta');
  assert.deepEqual([1, 2, 5, 10, 11, 12, 21, 22].map(marksWord), ['ženklas', 'ženklai', 'ženklai', 'ženklų', 'ženklų', 'ženklų', 'ženklas', 'ženklai']);
});

test('his name wins over the legend text', () => {
  assert.equal(rowName(rowA, { name: '  Dvivietė rozetė ' }), 'Dvivietė rozetė');
  assert.equal(rowName(rowA, { name: '' }), 'Rozetė');
  assert.equal(rowName({ text: '' }, null), 'Ženklas');
});

test('create: a new type per kept row with marks, with legend_row_id, marks at the instance centres, removed ones left out', () => {
  const review = { 'p3-a': { keep: true, name: null }, 'p3-b': { keep: true, name: 'Jungikliai' }, 'p3-s': { keep: true } };
  const plan = buildCreate({ rows: [rowA, rowB, rowS], counts, review, removed: new Set(['p3-a#1']), countTypes: [], pages });
  // p3-b found no mark: a blank row, not a count type
  assert.equal(plan.types.length, 1);
  assert.deepEqual(plan.types.map((t) => [t.label, t.legend_row_id]), [['Rozetė', 'p3-a']]);
  assert.deepEqual(plan.blanks.map((b) => [b.aprasymas, b.kiekis]), [['Jungikliai (pagal legendą)', null]]);
  assert.equal(plan.marks.length, 2);
  assert.ok(plan.marks.every((m) => m.kind === 'count' && m.source === LEGEND_SOURCE && m.typeId === plan.types[0].id));
  assert.deepEqual(plan.marks[0].points, [{ x: 500, y: 250 }]);
  assert.deepEqual(plan.marks[1].page, 4);
  assert.deepEqual(plan.replaceTypeIds, []);
});

test('create again: the same legend row reuses its type, old legend marks replaced, hand marks kept', () => {
  const old = { id: 'rozete', label: 'Rozetė', color: '#000', legend_row_id: 'p3-a', legend_text: 'Rozetė' };
  const review = { 'p3-a': { keep: true, name: 'Rozetės' } };
  const plan = buildCreate({ rows: [rowA], counts, review, countTypes: [old], pages });
  assert.deepEqual(plan.types, []);
  assert.deepEqual(plan.replaceTypeIds, ['rozete']);
  const measurements = [
    { id: 'm1', kind: 'count', typeId: 'rozete', source: LEGEND_SOURCE },
    { id: 'm2', kind: 'count', typeId: 'rozete', source: 'user' },
    { id: 'm3', kind: 'distance' },
  ];
  const next = applyCreate(measurements, [old], plan);
  assert.deepEqual(next.measurements.slice(0, 2).map((m) => m.id), ['m2', 'm3']);
  assert.equal(next.measurements.length, 2 + 3);
  assert.equal(next.countTypes[0].label, 'Rozetės');
});

test('decisions: removed marks reject, kept marks of kept rows accept (capped), dropped rows not per mark', () => {
  const many = { row_id: 'p3-a', status: 'ok', count: 30, instances: Array.from({ length: 30 }, (_, i) => inst(3, 0.1 + i * 0.02, 0.5, 0.9)) };
  const dec = decisionsFor({
    rows: [rowA, rowB], counts: { 'p3-a': many, 'p3-b': { ...counts['p3-b'], instances: [inst(3, 0.3, 0.3)] } },
    review: { 'p3-a': { keep: true }, 'p3-b': { keep: false } }, removed: new Set(['p3-a#0', 'p3-b#0']), pages, klassOf: (r) => r.row_id,
  });
  const accepts = dec.filter((d) => d.decision === 'accept');
  const rejects = dec.filter((d) => d.decision === 'reject');
  assert.equal(accepts.length, MAX_ACCEPTS_PER_ROW);
  assert.deepEqual(rejects.map((d) => d.klass), ['p3-a', 'p3-b']);
  assert.ok(dec.every((d) => d.source === LEGEND_SOURCE && d.box_pt.length === 4 && d.page_idx === 2));
});

test('journal: one row per legend row, source legenda, what was kept and removed', () => {
  const rows = journalRows({ rows: [rowA, rowS], counts, review: { 'p3-a': { keep: true, name: 'Rozetės' }, 'p3-s': { keep: true } }, removed: new Set(['p3-a#2']) });
  assert.equal(rows.length, 1);   // the material sample is not journalled
  assert.deepEqual(rows[0], {
    field_path: 'legenda.3.p3-a', old_value: { eilute: 'Rozetė', rasta: 3 },
    new_value: { sprendimas: 'accept', pavadinimas: 'Rozetės', kiekis: 2, pasalinta: 1 }, source: 'legenda', note: 'vektoriai',
  });
  const dropped = journalRows({ rows: [rowB], counts, review: { 'p3-b': { keep: false } } });
  assert.equal(dropped[0].new_value.sprendimas, 'reject');
});

test('the saved legend carries only kept countable rows with his names', () => {
  const saved = legendRowsToSave([rowA, rowB, rowS], { 'p3-a': { keep: true, name: 'X' }, 'p3-b': { keep: false }, 'p3-s': { keep: true } });
  assert.deepEqual(saved.map((r) => [r.row_id, r.name]), [['p3-a', 'X']]);
});

test('an earlier legend fits only when most rows match; his names come with it', () => {
  const rows = [rowA, rowB, rowS];
  const saved = { rows: [{ text: 'rozetė ', name: 'Rozetės (dvivietės)' }, { text: 'Jungiklis', name: null }, { text: 'Kita' }] };
  const fit = matchSavedLegend(rows, saved);
  assert.equal(fit.matched, 2);
  assert.equal(fit.review['p3-a'].name, 'Rozetės (dvivietės)');
  assert.equal(fit.review['p3-a'].keep, true);
  assert.equal(matchSavedLegend(rows, { rows: [{ text: 'Rozetė' }] }), null);
  assert.equal(matchSavedLegend(rows, { rows: [] }), null);
});

test('a legend type gets ONE sąmata row, linked by eilute_id; Atšaukti removes it; kiekis then follows via measuredRows', async () => {
  const { syncMeasuredRows } = await import('./measuredRows.js');
  const review = { 'p3-a': { keep: true, name: null } };
  const plan = buildCreate({ rows: [rowA], counts, review, countTypes: [], pages });
  const t = plan.types[0];
  assert.equal(t.eilute_id, `rnk-legenda-${t.id}`);
  assert.equal(t.kaip, 'kiekis');
  const base = [{ id: 'x', aprasymas: 'Dažymas', kiekis: 10 }];
  const one = syncLegendRows(base, plan.marks, [t]);
  assert.equal(one.length, 2);
  assert.equal(one[1].id, t.eilute_id);
  assert.equal(one[1].kiekis, 3);
  assert.equal(one[1].quantity_source, 'measurement_count');
  // nothing more to create → the same array
  assert.equal(syncLegendRows(one, plan.marks, [t]), one);
  // the row follows the marks through lib/measuredRows, with the legend sentence as its ledger line
  const marks = [...plan.marks.slice(0, 2), { kind: 'count', typeId: t.id, page: 3, source: 'user', id: 'h1' }];
  const project = { darbu_sarasas: one, measurements: marks, countTypes: [t] };
  const synced = syncMeasuredRows(project);
  const row = synced.darbu_sarasas.find((r) => r.id === t.eilute_id);
  assert.equal(row.kiekis, 3);
  assert.equal(row.matavimai[0].tekstas, 'suskaičiuota pagal legendą: eilutė „Rozetė“, 3 ženklai lape 3 (iš jų 1 pažymėta rankiniu būdu)');
  // the type gone (Atšaukti) → the row goes
  assert.deepEqual(syncLegendRows(one, [], []).map((r) => r.id), ['x']);
  // count rows not made from a legend are not touched
  const plain = [{ id: 'y', quantity_source: 'measurement_count', measure_type_id: 'z', kiekis: 4 }];
  assert.equal(syncLegendRows(plain, [], []), plain);
});

test('ledger sentence', () => {
  assert.equal(legendLedgerText('Rozetė', [{ page: 2, n: 5 }]), 'suskaičiuota pagal legendą: eilutė „Rozetė“, 5 ženklai lape 2');
});

test('hints and pill per phase, always a way out', () => {
  for (const p of LEGEND_PHASES) {
    assert.ok(legendCursorHint(p), p);
    const pill = legendPill({ phase: p, proposals: 1, toCreate: 1 });
    assert.ok(pill.actions.length >= 1, p);
  }
  assert.equal(legendCursorHint(null), null);
  const proposed = legendPill({ phase: 'proposed', proposals: 2 });
  assert.deepEqual(proposed.actions.map((a) => a.label), ['Taip', 'Nubrėžti kitaip']);
  assert.equal(proposed.detail, 'Tai legendos? (2)');
  const review = legendPill({ phase: 'review', toCreate: 0 });
  assert.equal(review.actions[0].disabled, true);
  assert.equal(legendPill({ phase: 'review', toCreate: 3 }).actions[0].label, 'Sukurti kiekius (3)');
});


test('a kept row with no mark is never counted: it becomes a blank sąmata row with the question', () => {
  const review = { 'p3-a': { keep: true }, 'p3-b': { keep: true, name: 'Jungikliai' } };
  // p3-b found nothing; p3-a loses all three marks by hand → both blank
  assert.deepEqual(rowsToCreate([rowA, rowB], review, counts).map((r) => r.row_id), ['p3-a']);
  assert.deepEqual(blankRows([rowA, rowB], review, counts).map((r) => r.row_id), ['p3-b']);
  const gone = new Set(['p3-a#0', 'p3-a#1', 'p3-a#2']);
  assert.deepEqual(rowsToCreate([rowA, rowB], review, counts, gone), []);
  const plan = buildCreate({ rows: [rowA, rowB], counts, review, removed: gone, countTypes: [], pages });
  assert.deepEqual(plan.types, []);
  assert.deepEqual(plan.marks, []);
  assert.deepEqual(plan.blanks.map((b) => b.legend_row_id), ['p3-a', 'p3-b']);
  const blank = blankSamataRow(rowB, review['p3-b']);
  assert.equal(blank.kiekis, null);
  assert.equal(blank.aprasymas, 'Jungikliai (pagal legendą)');
  assert.equal(blank.ledger_note_lt, BLANK_REASON);
  assert.match(blank._confidence_reason, /^Legendoje yra, brėžinyje ženklų nerasta — suskaičiuokite „Kiekis“ įrankiu$/);
  assert.ok(!/ženkl(ai|as) lape/.test(blank.ledger_note_lt), 'no ledger line claims a count');
  // blank rows are not count rows: the legend sync never touches them
  const rows = [blank];
  assert.equal(syncLegendRows(rows, [], []), rows);
  // the pill lets him create blanks alone, the label still counts only the rows with marks
  const pill = legendPill({ phase: 'review', toCreate: 0, blanks: 2 });
  assert.equal(pill.actions[0].label, 'Sukurti kiekius (0)');
  assert.equal(pill.actions[0].disabled, false);
});

// ── B1-B: every outcome ends in one sentence ─────────────────────────────────────────────────────────

test('Lithuanian forms: eilutė / eilutės / eilučių, lape / lapuose', () => {
  assert.deepEqual([1, 2, 9, 10, 11, 14, 21, 22].map(rowsWord), ['eilutė', 'eilutės', 'eilutės', 'eilučių', 'eilučių', 'eilučių', 'eilutė', 'eilutės']);
  assert.equal(onSheetsText(1), '1 lape');
  assert.equal(onSheetsText(3), '3 lapuose');
  assert.equal(summaryText({ rows: 14, marks: 38, pages: 3 }), 'Rasta 14 eilučių, 38 ženklai 3 lapuose');
});

test('the review outcome: counted, nothing found, only samples, error, out of time', () => {
  const ok = reviewOutcome({ rows: [rowA, rowB, rowS], counts });
  assert.equal(ok.tone, 'ok');
  assert.equal(ok.text, 'Rasta 2 eilutės, 3 ženklai 2 lapuose.');
  assert.equal(ok.retry, false);
  const none = reviewOutcome({ rows: [rowB], counts });
  assert.equal(none.tone, 'empty');
  assert.match(none.text, /^Legendą perskaičiau \(1 eilutė\), bet ženklų plane neradau\. Pažymėkite juos „Kiekis“ įrankiu/);
  const samples = reviewOutcome({ rows: [rowS], counts });
  assert.match(samples.text, /tik medžiagų ar linijų pavyzdžiai/);
  const err = reviewOutcome({ rows: [rowA], counts: {}, countError: 'serveris neatsakė per skirtą laiką' });
  assert.equal(err.tone, 'error');
  assert.equal(err.retry, true);
  assert.match(err.text, /^Ženklų suskaičiuoti nepavyko: serveris neatsakė per skirtą laiką\./);
  const partial = reviewOutcome({ rows: [rowA], counts: { 'p3-a': { ...counts['p3-a'], partial: true } } });
  assert.equal(partial.tone, 'warn');
  assert.equal(partial.retry, true);
  assert.match(partial.text, /Ne visi lapai spėti peržiūrėti/);
  for (const o of [ok, none, samples, err, partial]) assert.ok(o.short && o.short.length <= 60, o.short);
});

test('a failed request is said in Lithuanian, never in the browser\'s words', () => {
  const named = (name, message = '') => Object.assign(new Error(message), { name });
  assert.equal(requestErrorText(named('TimeoutError', 'signal timed out')), 'serveris neatsakė per skirtą laiką');
  assert.equal(requestErrorText(new TypeError('Load failed')), 'nepavyko pasiekti serverio — patikrinkite ryšį');     // Safari
  assert.equal(requestErrorText(new TypeError('Failed to fetch')), 'nepavyko pasiekti serverio — patikrinkite ryšį'); // Chrome
  assert.equal(requestErrorText(Object.assign(new Error('Per daug užklausų.'), { status: 429 })), 'per daug užklausų iš eilės — palaukite minutę');
  assert.equal(requestErrorText(Object.assign(new Error('HTTP 500'), { status: 500 })), 'serverio klaida');
  assert.equal(requestErrorText(Object.assign(new Error('Tokio lapo brėžinyje nėra'), { status: 400 })), 'Tokio lapo brėžinyje nėra');
  assert.equal(requestErrorText(new Error('something odd')), 'nežinoma klaida');
});

test('a box without a legend says so, and why when the reader said why', () => {
  assert.equal(boxFailureText({ status: 'ok', detail: null }), `${BOX_EMPTY}.`);
  assert.match(boxFailureText({ status: 'ok', detail: '15 teksto eil. be ženklo prie jų — ne legendos eilutės' }), /patalpų lentelė/);
  assert.match(boxFailureText({ status: 'ok', detail: 'rėmelyje nėra teksto eilučių — nubrėžkite' }), /nėra jokio teksto/);
  assert.match(boxFailureText({ status: 'be_teksto' }), /nėra teksto .*„Kiekis“ įrankiu/);
  // never the reader's own words (they carry „eil." and the like)
  assert.doesNotMatch(boxFailureText({ status: 'ok', detail: '15 teksto eil. be ženklo prie jų' }), /teksto eil\./);
});

test('no legend on this sheet: where it is, and the pill and panel offer to go there', () => {
  assert.equal(noLegendText(1, []), 'Šiame lape legendos neradau — apveskite ją rėmeliu');
  assert.equal(noLegendText(1, [{ page: 5, rows: 15 }]), 'Šiame lape legendos nėra. Legenda yra 5 lape — eikite ten arba apveskite ją rėmeliu čia');
  assert.match(noLegendText(1, [{ page: 2 }, { page: 3 }]), /Legenda yra 2, 3 lapuose/);
  assert.equal(legendGotoPage({ phase: 'box', page: 1, elsewhere: [{ page: 5 }] }), 5);
  assert.equal(legendGotoPage({ phase: 'box', page: 1, elsewhere: [{ page: 5 }], failure: { page: 1 } }), null);
  const pill = legendPill({ phase: 'box', notice: noLegendText(1, [{ page: 5 }]), gotoPage: 5 });
  assert.deepEqual(pill.actions.map((a) => a.id), ['legendGoto', 'legendExit']);
  assert.equal(pill.actions[0].label, 'Į 5 lapą');
});

test('while it works the pill counts the seconds; a failure offers „Bandyti dar kartą"', () => {
  assert.equal(countingText(12.7), 'Skaičiuoju… 12 s — gali užtrukti iki minutės');
  assert.equal(legendPill({ phase: 'counting', elapsed: 3 }).detail, 'Skaičiuoju… 3 s — gali užtrukti iki minutės');
  assert.match(legendPill({ phase: 'counting' }).keys, /Esc/);
  const failed = legendPill({ phase: 'box', outcome: { retry: true, short: 'Rėmelio perskaityti nepavyko', text: '…' } });
  assert.equal(failed.detail, 'Rėmelio perskaityti nepavyko');
  assert.equal(failed.actions[0].label, 'Bandyti dar kartą');
  const review = legendPill({ phase: 'review', toCreate: 0, outcome: { retry: true, short: 'Ženklų suskaičiuoti nepavyko' } });
  assert.deepEqual(review.actions.map((a) => a.id), ['legendRetry', 'legendCreate', 'legendRedraw', 'legendExit']);
  assert.equal(legendPill({ phase: 'review', toCreate: 2, outcome: { short: 'Rasta 2 eilutės, 3 ženklai 2 lapuose' } }).detail, 'Rasta 2 eilutės, 3 ženklai 2 lapuose');
});

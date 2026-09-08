import test from 'node:test';
import assert from 'node:assert/strict';
import {
  diffDarbuSarasas,
  filterTakeoffRows,
  getFirstReviewRow,
  getQuantitySourceKind,
  getQuantitySourceLabel,
  getRowImpact,
  getRowTargetPage,
  isRowVerified,
  needsTakeoffReview,
  pickSensitiveInput,
  rankReviewRows,
  selectReviewQueue,
  summarizeTakeoffWorkflow,
  trustMeter,
  unverifiedRisk,
} from './takeoffWorkflow.js';

// Production vocabulary is LT (backend extractor/confidence.py): zalia/geltona/raudona.
const rows = [
  { eil_nr: 1, aprasymas: 'Sienu dazymas', kiekis: 10, kaina: 5, confidence: 'zalia', mato_vnt: 'm2' },
  { eil_nr: 2, aprasymas: 'Rozetes', kiekis: 4, kaina: 0, confidence: 'geltona', mato_vnt: 'vnt' },
  { eil_nr: 3, aprasymas: 'Lubos', kiekis: 12, kaina: 3, confidence: 'raudona', manual_override: true },
  { eil_nr: 4, aprasymas: 'Grindjuostes', kiekis: 20, kaina: 0, confidence: 'zalia', quantity_source: 'manual_override' },
];

test('summarizeTakeoffWorkflow: counts review, manual and missing price rows (LT confidence vocabulary)', () => {
  const summary = summarizeTakeoffWorkflow({
    darbu_sarasas: rows,
    patalpos: [{ plotas_m2: 10 }, { plotas_m2: 12.5 }],
    puslapiai: [{}, {}, {}],
  }, { hasPdf: true });

  assert.equal(summary.totalRows, 4);
  assert.equal(summary.reviewRows, 1);
  assert.equal(summary.manualOverrides, 2);
  assert.equal(summary.missingPrices, 2);
  assert.equal(summary.totalRooms, 2);
  assert.equal(summary.totalPages, 3);
  assert.equal(summary.totalArea, 22.5);
  assert.equal(summary.aiSymbolRows, 0);
  assert.equal(summary.assumptionRows, 0);
  assert.equal(summary.hasPdf, true);
  assert.equal(summary.readyForBeta, false);
  assert.equal(summary.readinessScore, 71);
});

test('needsTakeoffReview: engine-flagged LT rows need review, zalia and unstamped rows do not', () => {
  assert.equal(needsTakeoffReview({ confidence: 'geltona' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'raudona' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'zalia' }), false);
  assert.equal(needsTakeoffReview({}), false);
});

test('needsTakeoffReview: legacy EN blobs (old localStorage caches) still flag correctly', () => {
  assert.equal(needsTakeoffReview({ confidence: 'medium' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'low' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'high' }), false);
});

test('needsTakeoffReview: rows already accepted/rejected in the review queue drop out', () => {
  assert.equal(needsTakeoffReview({ confidence: 'raudona', _review_status: 'accepted' }), false);
  assert.equal(needsTakeoffReview({ confidence: 'geltona', _review_status: 'rejected' }), false);
  assert.equal(needsTakeoffReview({ confidence: 'geltona', _review_status: 'kita' }), true);
});

test('takeoff review: explicit review_required forces review even with zalia confidence', () => {
  const row = {
    eil_nr: 5,
    aprasymas: 'WC rėmo montavimas',
    confidence: 'zalia',
    review_required: true,
    quantity_source: 'room_type_assumption',
  };

  assert.deepEqual(filterTakeoffRows([row], { mode: 'review' }).map(r => r.aprasymas), ['WC rėmo montavimas']);
  assert.equal(getQuantitySourceKind(row), 'assumption');
  assert.equal(getQuantitySourceLabel(row), 'Prielaida');
});

test('takeoff summary: AI symbols and assumptions are counted separately', () => {
  const summary = summarizeTakeoffWorkflow({
    darbu_sarasas: [
      { aprasymas: 'Sienos', confidence: 'zalia', kaina: 2, quantity_source: 'deterministic_formula' },
      { aprasymas: 'Šviestuvai', confidence: 'raudona', kaina: 2, quantity_source: 'ai_symbol_candidate', review_required: true },
      { aprasymas: 'WC', confidence: 'geltona', kaina: 2, quantity_source: 'room_type_assumption', review_required: true },
    ],
    patalpos: [],
    puslapiai: [{}],
  }, { hasPdf: true });

  assert.equal(summary.aiSymbolRows, 1);
  assert.equal(summary.assumptionRows, 1);
  assert.equal(summary.reviewRows, 2);
  assert.equal(summary.readyForBeta, false);
  assert.ok(summary.readinessScore < 70);
});

test('getRowImpact: kiekis × kaina when prices are used, kiekis alone before prices exist', () => {
  const row = { kiekis: 12, kaina: 2.5 };
  assert.equal(getRowImpact(row, true), 30);
  assert.equal(getRowImpact(row, false), 12);
  assert.equal(getRowImpact({ kiekis: null, kaina: 4 }, true), 0);
  assert.equal(getRowImpact({}, false), 0);
});

test('rankReviewRows: review rows come back ranked by € impact, not confidence order', () => {
  const impactRows = [
    { eil_nr: 1, aprasymas: 'Mazas raudonas', kiekis: 2, kaina: 1, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'Didelis geltonas', kiekis: 100, kaina: 30, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'Zalias', kiekis: 500, kaina: 50, confidence: 'zalia' },
    { eil_nr: 4, aprasymas: 'Vidutinis geltonas', kiekis: 10, kaina: 8, confidence: 'geltona' },
  ];
  assert.deepEqual(
    rankReviewRows(impactRows).map(r => r.aprasymas),
    ['Didelis geltonas', 'Vidutinis geltonas', 'Mazas raudonas'],
  );
});

test('rankReviewRows: before any prices exist the ranking falls back to kiekis', () => {
  const noPrices = [
    { eil_nr: 1, aprasymas: 'A', kiekis: 3, kaina: 0, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'B', kiekis: 40, kaina: 0, confidence: 'geltona' },
  ];
  assert.deepEqual(rankReviewRows(noPrices).map(r => r.aprasymas), ['B', 'A']);
});

test('rankReviewRows: equal impact breaks ties by severity (raudona first), then eil_nr', () => {
  const tied = [
    { eil_nr: 7, aprasymas: 'Geltonas', kiekis: 5, kaina: 2, confidence: 'geltona' },
    { eil_nr: 9, aprasymas: 'Raudonas', kiekis: 10, kaina: 1, confidence: 'raudona' },
    { eil_nr: 3, aprasymas: 'Geltonas ankstesnis', kiekis: 10, kaina: 1, confidence: 'geltona' },
  ];
  assert.deepEqual(
    rankReviewRows(tied).map(r => r.aprasymas),
    ['Raudonas', 'Geltonas ankstesnis', 'Geltonas'],
  );
});

test('getFirstReviewRow: returns the highest-impact review row and skips manual overrides', () => {
  assert.equal(getFirstReviewRow(rows).aprasymas, 'Rozetes');

  const impactRows = [
    { eil_nr: 1, aprasymas: 'Mazas raudonas', kiekis: 2, kaina: 1, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'Didelis geltonas', kiekis: 100, kaina: 30, confidence: 'geltona' },
  ];
  assert.equal(getFirstReviewRow(impactRows).aprasymas, 'Didelis geltonas');
  assert.equal(getFirstReviewRow([]), null);
});

test('selectReviewQueue: default view = all raudona + top-5 geltona by value, rest collapsed', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'R1', kiekis: 1, kaina: 2, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'R2', kiekis: 1, kaina: 1, confidence: 'raudona' },
    { eil_nr: 3, aprasymas: 'G100', kiekis: 10, kaina: 10, confidence: 'geltona' },
    { eil_nr: 4, aprasymas: 'G90', kiekis: 9, kaina: 10, confidence: 'geltona' },
    { eil_nr: 5, aprasymas: 'G80', kiekis: 8, kaina: 10, confidence: 'geltona' },
    { eil_nr: 6, aprasymas: 'G70', kiekis: 7, kaina: 10, confidence: 'geltona' },
    { eil_nr: 7, aprasymas: 'G60', kiekis: 6, kaina: 10, confidence: 'geltona' },
    { eil_nr: 8, aprasymas: 'G50', kiekis: 5, kaina: 10, confidence: 'geltona' },
    { eil_nr: 9, aprasymas: 'G40', kiekis: 4, kaina: 10, confidence: 'geltona' },
    { eil_nr: 10, aprasymas: 'Zalias', kiekis: 100, kaina: 5, confidence: 'zalia' },
  ];
  const queue = selectReviewQueue(queueRows);

  assert.equal(queue.usePrices, true);
  assert.equal(queue.ranked.length, 9);
  // All raudona present regardless of value + the five biggest geltona.
  // Primary preserves the impact ranking (biggest € first).
  assert.deepEqual(
    queue.primary.map(r => r.aprasymas),
    ['G100', 'G90', 'G80', 'G70', 'G60', 'R1', 'R2'],
  );
  assert.deepEqual(queue.rest.map(r => r.aprasymas), ['G50', 'G40']);

  // Share of the whole estimate the primary rows represent:
  // primary € = 403 of the 993 € total (2+1+100+90+80+70+60+50+40+500).
  const expectedShare = (100 + 90 + 80 + 70 + 60 + 2 + 1) / 993;
  assert.ok(Math.abs(queue.shareOfTotal - expectedShare) < 1e-9);
});

test('selectReviewQueue: before prices exist there is no € share and ranking uses kiekis', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'G maza', kiekis: 2, kaina: 0, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'G didele', kiekis: 30, kaina: 0, confidence: 'geltona' },
  ];
  const queue = selectReviewQueue(queueRows);
  assert.equal(queue.usePrices, false);
  assert.equal(queue.shareOfTotal, null);
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G didele', 'G maza']);
  assert.deepEqual(queue.rest, []);
});

test('selectReviewQueue: excluded rows (eksplikacija-locked) leave the queue but stay in the € total', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'Locked geltona', kiekis: 10, kaina: 10, confidence: 'geltona', saltinis: 'eksplikacija' },
    { eil_nr: 2, aprasymas: 'G', kiekis: 5, kaina: 10, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'Zalias', kiekis: 5, kaina: 10, confidence: 'zalia' },
  ];
  const queue = selectReviewQueue(queueRows, { exclude: r => r.saltinis === 'eksplikacija' });
  assert.deepEqual(queue.ranked.map(r => r.aprasymas), ['G']);
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G']);
  // total = 100 + 50 + 50 = 200; primary = 50.
  assert.ok(Math.abs(queue.shareOfTotal - 50 / 200) < 1e-9);
});

test('selectReviewQueue: maxGeltona is configurable', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'G1', kiekis: 3, kaina: 1, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'G2', kiekis: 2, kaina: 1, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'G3', kiekis: 1, kaina: 1, confidence: 'geltona' },
  ];
  const queue = selectReviewQueue(queueRows, { maxGeltona: 1 });
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G1']);
  assert.deepEqual(queue.rest.map(r => r.aprasymas), ['G2', 'G3']);
});

test('ltEilutesPhrase: Lithuanian numeral agreement for the review copy', async () => {
  const { ltEilutesPhrase } = await import('./takeoffWorkflow.js');
  assert.equal(ltEilutesPhrase(1), 'šią 1 eilutę');
  assert.equal(ltEilutesPhrase(6), 'šias 6 eilutes');
  assert.equal(ltEilutesPhrase(11), 'šias 11 eilučių');
  assert.equal(ltEilutesPhrase(20), 'šias 20 eilučių');
  assert.equal(ltEilutesPhrase(21), 'šią 21 eilutę');
  assert.equal(ltEilutesPhrase(102), 'šias 102 eilutes');
});

test('filterTakeoffRows: filters by review mode, manual mode, missing price mode and query', () => {
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'review' }).map(r => r.aprasymas), ['Rozetes']);
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'manual' }).map(r => r.aprasymas), ['Lubos', 'Grindjuostes']);
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'missing_price' }).map(r => r.aprasymas), ['Rozetes', 'Grindjuostes']);
  assert.deepEqual(filterTakeoffRows(rows, { query: 'sienu' }).map(r => r.aprasymas), ['Sienu dazymas']);
});

test('getRowTargetPage: prefers eksplikacija page for table-backed rows and falls back to row page', () => {
  const project = { _eksplikacija: { eksplikacija_source_page: 7 } };
  assert.equal(getRowTargetPage({ eksplikacija_row_bbox: [1, 2, 3, 4], puslapio_nr: 2 }, project), 7);
  assert.equal(getRowTargetPage({ puslapio_nr: 2 }, project), 2);
  assert.equal(getRowTargetPage({}, project), null);
});

// ── Patikra — the guided audit loop (2026-09-02) ────────────────────────────

const PATIKRA_ROOMS = [
  // Read off the drawing: eksplikacija area, a per-room height.
  { nr: '110', pavadinimas: 'Miegamasis', plotas_m2: 23.97, lubu_aukstis_m: 2.8,
    plotas_saltinis: 'eksplikacija', lubu_aukstis_saltinis: 'per_room' },
  // Assumed: one section average spread over every room.
  { nr: '104', pavadinimas: 'Darbo kambarys', plotas_m2: 13.51, lubu_aukstis_m: 2.85,
    plotas_saltinis: 'eksplikacija', lubu_aukstis_saltinis: 'section_average' },
  // Assumed area — no table behind it.
  { nr: '103', pavadinimas: 'Koridorius', plotas_m2: 9.64, lubu_aukstis_m: 2.8,
    plotas_saltinis: 'polygon', lubu_aukstis_saltinis: 'per_room' },
];

const contribution = (nr, name, value, terms) => ({
  room_nr: nr, room_name: name, page: 2, value, unit: 'm',
  included_because: 'Dažomos sienos', geometry: 'polygon',
  ...(terms ? { terms } : {}),
});

test('trustMeter counts only what a human stood behind', () => {
  const meter = trustMeter([
    { kiekis: 10, kaina: 5 },                                   // 50 €, untouched
    { kiekis: 10, kaina: 5, user_verified_at: '2026-09-02' },   // 50 €, verified
    { kiekis: 10, kaina: 5, confidence: 'zalia' },              // 50 €, green ≠ verified
  ]);
  assert.equal(meter.usePrices, true);
  assert.equal(meter.total, 150);
  assert.equal(meter.verified, 50);
  assert.equal(meter.verifiedCount, 1);
  assert.ok(Math.abs(meter.share - 1 / 3) < 1e-9);
});

test('trustMeter also accepts an accepted review or a manual quantity', () => {
  const meter = trustMeter([
    { kiekis: 4, kaina: 1, _review_status: 'accepted' },
    { kiekis: 4, kaina: 1, manual_override: true },
    { kiekis: 4, kaina: 1, _review_status: 'rejected' },
  ]);
  assert.equal(meter.verifiedCount, 2);
  assert.ok(Math.abs(meter.share - 2 / 3) < 1e-9);
});

test('trustMeter falls back to kiekis before any price exists, and 0 on empty', () => {
  const meter = trustMeter([
    { kiekis: 30 }, { kiekis: 10, user_verified_at: 'x' },
  ]);
  assert.equal(meter.usePrices, false);
  assert.equal(meter.total, 40);
  assert.equal(meter.share, 0.25);

  const empty = trustMeter([]);
  assert.equal(empty.share, 0);
  assert.equal(empty.totalCount, 0);
});

test('unverifiedRisk prices exactly the rows still in the queue', () => {
  const risk = unverifiedRisk([
    { kiekis: 10, kaina: 5, confidence: 'raudona' },            // 50 € pending
    { kiekis: 10, kaina: 5, confidence: 'geltona' },            // 50 € pending
    { kiekis: 10, kaina: 5, confidence: 'zalia' },              // settled
    { kiekis: 10, kaina: 5, confidence: 'raudona', user_verified_at: 'x' },
  ]);
  assert.equal(risk.count, 2);
  assert.equal(risk.amount, 100);
  assert.equal(risk.usePrices, true);
});

test('a paint line with no terms leans on the top room’s ceiling height', () => {
  const row = { kiekis: 100, mato_vnt: 'm²',
    contributions: [contribution('110', 'Miegamasis', 60), contribution('104', 'Darbo', 40)] };
  const pick = pickSensitiveInput(row, PATIKRA_ROOMS);
  assert.equal(pick.kind, 'height');
  assert.equal(pick.roomNr, '110');
  assert.equal(pick.value, 2.8);
  assert.equal(pick.assumed, false);         // per_room = read off the drawing
  assert.equal(pick.source, 'per_room');
  assert.ok(Math.abs(pick.contributionShare - 0.6) < 1e-9);
});

test('an assumed height outranks a read one even on a smaller share', () => {
  const row = { kiekis: 100, mato_vnt: 'm²',
    contributions: [contribution('104', 'Darbo kambarys', 60)] };
  const pick = pickSensitiveInput(row, PATIKRA_ROOMS);
  assert.equal(pick.kind, 'height');
  assert.equal(pick.assumed, true);
  assert.equal(pick.source, 'section_average');
});

test('a perimeter-driven line points at the area, not the height', () => {
  // Grindjuostės: every term is perimeter work, and 103’s area is not from a table.
  const row = { kiekis: 20, mato_vnt: 'm', contributions: [
    contribution('103', 'Koridorius', 20,
      { 'perimetras be durų': 18.2, 'atliekos 10 %': 1.8 }),
  ] };
  const pick = pickSensitiveInput(row, PATIKRA_ROOMS);
  assert.equal(pick.kind, 'area');
  assert.equal(pick.assumed, true);
  assert.equal(pick.value, 9.64);
  assert.equal(pick.unit, 'm²');
});

test('kampai terms keep the height as the sensitive input', () => {
  const row = { kiekis: 81.4, mato_vnt: 'm', contributions: [
    contribution('110', 'Miegamasis', 81.4, {
      'vidiniai kampai': 11.2, 'angų atbrailos': 30.0,
      'pusiniai kampai': 25.2, 'perimetras': 15.0,
    }),
  ] };
  assert.equal(pickSensitiveInput(row, PATIKRA_ROOMS).kind, 'height');
});

test('with no ledger the card falls back to the row’s own reason', () => {
  const row = { kiekis: 5, _confidence_reason: 'Skaičius iš simbolių brėžinyje.' };
  assert.deepEqual(pickSensitiveInput(row, PATIKRA_ROOMS),
    { kind: 'reason', reason: 'Skaičius iš simbolių brėžinyje.' });
  // Nothing to say at all → nothing claimed.
  assert.equal(pickSensitiveInput({ kiekis: 5 }, PATIKRA_ROOMS), null);
  // A contribution whose room is gone from the project degrades the same way.
  assert.deepEqual(
    pickSensitiveInput({ kiekis: 5, _confidence_reason: 'x',
      contributions: [contribution('999', 'Nėra', 5)] }, PATIKRA_ROOMS),
    { kind: 'reason', reason: 'x' });
});

test('pickSensitiveInput survives rooms with no source fields at all', () => {
  const row = { kiekis: 10, contributions: [contribution('201', 'Nauja', 10)] };
  const pick = pickSensitiveInput(row, [{ nr: '201', pavadinimas: 'Nauja' }]);
  assert.equal(pick.kind, 'height');
  assert.equal(pick.value, null);      // no height stored — say nothing, don't invent
  assert.equal(pick.assumed, true);    // and no source means it was not read
  assert.equal(pick.source, null);
});

test('the ripple diff reports the rows that moved and the € delta', () => {
  const prior = [
    { id: 'a', skyrius: 'S', aprasymas: 'Dažymas', kiekis: 100, kaina: 5 },
    { id: 'b', skyrius: 'S', aprasymas: 'Kampai', kiekis: 50, kaina: 2 },
    { id: 'c', skyrius: 'S', aprasymas: 'Dingusi', kiekis: 10, kaina: 1 },
  ];
  const next = [
    { id: 'a', skyrius: 'S', aprasymas: 'Dažymas', kiekis: 120, kaina: 5 },  // +100 €
    { id: 'b', skyrius: 'S', aprasymas: 'Kampai', kiekis: 50, kaina: 2 },    // unchanged
    { id: 'd', skyrius: 'S', aprasymas: 'Nauja', kiekis: 4, kaina: 3 },      // +12 €
  ];
  const diff = diffDarbuSarasas(prior, next);
  assert.equal(diff.count, 3);                       // changed + added + removed
  assert.equal(diff.deltaEur, 102);                  // +100 +12 −10
  assert.deepEqual(diff.changed.map(c => c.kind), ['changed', 'added', 'removed']);
  assert.equal(diff.changed[0].before, 100);
  assert.equal(diff.changed[0].after, 120);
});

test('a duplicated id never attributes an edit to the wrong row', () => {
  // Both sides carry two rows under 'dup'; matching by id would pick whichever
  // came first and report a change nobody made.
  const prior = [
    { id: 'dup', skyrius: 'S', aprasymas: 'Pirma', kiekis: 10, kaina: 1 },
    { id: 'dup', skyrius: 'S', aprasymas: 'Antra', kiekis: 20, kaina: 1 },
  ];
  const next = [
    { id: 'dup', skyrius: 'S', aprasymas: 'Pirma', kiekis: 10, kaina: 1 },
    { id: 'dup', skyrius: 'S', aprasymas: 'Antra', kiekis: 20, kaina: 1 },
  ];
  const diff = diffDarbuSarasas(prior, next);
  // The label pair disambiguates: nothing moved, so nothing is reported.
  assert.equal(diff.count, 0);
  assert.equal(diff.deltaEur, 0);
});

test('an id AND label collision is reported as add+remove, never as a silent swap', () => {
  const prior = [
    { id: 'dup', skyrius: 'S', aprasymas: 'Ta pati', kiekis: 10, kaina: 1 },
    { id: 'dup', skyrius: 'S', aprasymas: 'Ta pati', kiekis: 20, kaina: 1 },
  ];
  const next = [
    { id: 'dup', skyrius: 'S', aprasymas: 'Ta pati', kiekis: 10, kaina: 1 },
    { id: 'dup', skyrius: 'S', aprasymas: 'Ta pati', kiekis: 20, kaina: 1 },
  ];
  const diff = diffDarbuSarasas(prior, next);
  // Unresolvable on both keys → 2 added + 2 removed, and the € delta still nets
  // to zero. Over-reporting is safe; mis-attributing an edit is not.
  assert.deepEqual(diff.changed.map(c => c.kind).sort(),
    ['added', 'added', 'removed', 'removed']);
  assert.equal(diff.deltaEur, 0);
});

test('the diff works on old blobs that carry no ids at all', () => {
  const prior = [{ skyrius: 'S', aprasymas: 'Dažymas', kiekis: 100, kaina: 5 }];
  const next = [{ skyrius: 'S', aprasymas: 'Dažymas', kiekis: 90, kaina: 5 }];
  const diff = diffDarbuSarasas(prior, next);
  assert.equal(diff.count, 1);
  assert.equal(diff.deltaEur, -50);
});

test('isRowVerified is the one definition the meter and the queue share', () => {
  assert.equal(isRowVerified({ user_verified_at: 'x' }), true);
  assert.equal(isRowVerified({ _review_status: 'accepted' }), true);
  assert.equal(isRowVerified({ quantity_source: 'manual_override' }), true);
  assert.equal(isRowVerified({ confidence: 'zalia' }), false);
  assert.equal(isRowVerified(null), false);
});

test('the meter counts rows, not mixed units, before prices exist', () => {
  const meter = trustMeter([
    { kiekis: 1180.8, mato_vnt: 'kg' },
    { kiekis: 23.97, mato_vnt: 'm²', user_verified_at: 'x' },
    { kiekis: 4, mato_vnt: 'vnt.' },
    { kiekis: 12, mato_vnt: 'm' },
  ]);
  assert.equal(meter.usePrices, false);
  assert.equal(meter.countShare, 0.25);
  // The kiekis share exists but is meaningless across kg + m² + vnt.; the UI
  // reads countShare instead. Pinned so nobody swaps them back.
  assert.ok(meter.share < 0.02);
});

// ── checklist rows (kiekis null) never become Patikra cards ─────────────────
import { isChecklistRow, rankReviewRows as _rank, selectReviewQueue as _select, trustMeter as _meter, unverifiedRisk as _risk } from './takeoffWorkflow.js';

test('a checklist row is never ranked as a claim, and is offered separately', () => {
  const rows = [
    { id: 'a', eil_nr: 1, aprasymas: 'GKP dėžučių montavimas — suveskite ilgį', kiekis: null, mato_vnt: 'm', confidence: 'raudona', saltinis: 'checklist' },
    { id: 'b', eil_nr: 2, aprasymas: 'Sienų lyginimas', kiekis: 126.77, kaina: 8.5, mato_vnt: 'm²', confidence: 'geltona' },
    { id: 'c', eil_nr: 3, aprasymas: 'Dažymo kampų montavimas', kiekis: 356.8, kaina: 0, mato_vnt: 'm', confidence: 'raudona' },
  ];
  assert.equal(isChecklistRow(rows[0]), true);
  assert.equal(isChecklistRow(rows[1]), false);
  const ranked = _rank(rows);
  assert.deepEqual(ranked.map(r => r.id), ['b', 'c']);       // € first, checklist gone
  const q = _select(rows);
  assert.deepEqual(q.checklist.map(r => r.id), ['a']);
  assert.equal(q.ranked.includes(rows[0]), false);
  assert.equal(_risk(rows).count, 2);
  assert.equal(_meter(rows).totalCount, 2);                  // not a claim → not in the meter
});

// ── summarizeSamataRows — the one line under the sąmata ──────────────────────

test('summarizeSamataRows: counts drawing rows, checked rows, his own rows, and rows with no quantity', async () => {
  const { summarizeSamataRows } = await import('./takeoffWorkflow.js');
  const rows = [
    { id: 'p1', kiekis: 12.5 },                              // from the drawing, unchecked
    { id: 'p2', kiekis: 3, user_verified_at: '2026-09-04' }, // from the drawing, checked
    { id: 'p3', kiekis: 8, _review_status: 'accepted' },     // from the drawing, checked
    { id: 'p4', kiekis: 0 },                                 // from the drawing, no quantity
    { id: 'rnk-abc', kiekis: 4 },                            // his own row
    { id: 'rnk-def', kiekis: 0 },                            // his own row, no quantity
  ];
  const s = summarizeSamataRows(rows);
  assert.equal(s.total, 6);
  assert.equal(s.fromDrawing, 4);
  assert.equal(s.verified, 2);
  assert.equal(s.mine, 2);
  assert.equal(s.noQty, 2);
});

test('summarizeSamataRows: a manual quantity counts as checked — he typed the number himself', async () => {
  const { summarizeSamataRows } = await import('./takeoffWorkflow.js');
  const s = summarizeSamataRows([{ id: 'p1', kiekis: 140, manual_override: true }]);
  assert.equal(s.verified, 1);
  assert.equal(s.mine, 0);   // the ROW came from the drawing; only its number is his
});

test('summarizeSamataRows: an empty or junk list reads zeros, never NaN', async () => {
  const { summarizeSamataRows } = await import('./takeoffWorkflow.js');
  for (const input of [[], null, undefined, [null, undefined]]) {
    const s = summarizeSamataRows(input);
    assert.deepEqual(s, { total: 0, fromDrawing: 0, verified: 0, mine: 0, noQty: 0 });
  }
});

test('summarizeSamataRows: _id carries the rnk- marker too (rows that came back through a merge)', async () => {
  const { summarizeSamataRows } = await import('./takeoffWorkflow.js');
  const s = summarizeSamataRows([{ _id: 'rnk-xyz', kiekis: 2 }]);
  assert.equal(s.mine, 1);
  assert.equal(s.fromDrawing, 0);
});


// ── a tier split is one move, not a disappearance (2026-09-08) ──────────────

test('diffDarbuSarasas folds an iki/virš 3 m split into one change', () => {
  const prior = [{ id: 'a', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Sienų glaistymas/dažymas', kiekis: 279.08, mato_vnt: 'm²' }];
  const next = [
    { id: 'a-iki', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 248.12, mato_vnt: 'm²' },
    { id: 'a-virs', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Sienų glaistymas/dažymas (virš 3m aukščio)', kiekis: 32.94, mato_vnt: 'm²' },
  ];
  const diff = diffDarbuSarasas(prior, next);
  assert.equal(diff.count, 1);
  const c = diff.changed[0];
  assert.equal(c.kind, 'changed');
  assert.equal(c.row.aprasymas, 'Sienų glaistymas/dažymas');
  assert.equal(c.before, 279.08);
  assert.equal(c.after, 281.06);
  assert.equal(c.tiers.length, 3);
});

test('diffDarbuSarasas folds the merge back and drops a pure re-tiering', () => {
  const prior = [
    { skyrius: 'S', aprasymas: 'Lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 97.63, mato_vnt: 'm²' },
    { skyrius: 'S', aprasymas: 'Lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 6.9, mato_vnt: 'm²' },
  ];
  const next = [{ skyrius: 'S', aprasymas: 'Lubų glaistymas/dažymas', kiekis: 104.53, mato_vnt: 'm²' }];
  const diff = diffDarbuSarasas(prior, next);
  assert.equal(diff.count, 0, 'same quantity under one label instead of two — nothing moved');
});

test('diffDarbuSarasas leaves unrelated added and removed rows alone', () => {
  const prior = [{ skyrius: 'S', aprasymas: 'Pastolių nuoma (aukštesnių nei 3m)', kiekis: 1, mato_vnt: 'd.d' }];
  const next = [{ skyrius: 'S', aprasymas: 'Ortakių D125 mm montavimas', kiekis: 24, mato_vnt: 'm' }];
  const diff = diffDarbuSarasas(prior, next);
  assert.equal(diff.count, 2);
  assert.deepEqual(diff.changed.map((c) => c.kind).sort(), ['added', 'removed']);
});

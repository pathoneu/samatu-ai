import test from 'node:test';
import assert from 'node:assert/strict';
import {
  SEV_HIGH,
  SEV_MED,
  SEV_LOW,
  ACTION_PRIELAIDOS,
  assumptionFocus,
  normalizeLevel,
  normalizeSeverity,
  warningSeverity,
  isActionable,
  warningKey,
  summarizeSanity,
  groupBySeverity,
  warningAction,
  expectedSuffix,
  mergeSanity,
} from './sanitySeverity.js';

// ── tier resolution ─────────────────────────────────────────────────────────

test('normalizeLevel: every level a validator has ever emitted', () => {
  assert.equal(normalizeLevel('WARN'), 'WARNING');
  assert.equal(normalizeLevel('warning'), 'WARNING');
  assert.equal(normalizeLevel('FAIL'), 'ERROR');
  assert.equal(normalizeLevel('info'), 'INFO');
  assert.equal(normalizeLevel(''), null);
  assert.equal(normalizeLevel(undefined), null);
});

test('normalizeSeverity: sanity_checks vocabulary plus older synonyms', () => {
  assert.equal(normalizeSeverity('high'), SEV_HIGH);
  assert.equal(normalizeSeverity('med'), SEV_MED);
  assert.equal(normalizeSeverity('medium'), SEV_MED);
  assert.equal(normalizeSeverity('LOW'), SEV_LOW);
  assert.equal(normalizeSeverity('nonsense'), null);
});

test('a severity-only warning is never demoted to the info tier', () => {
  // THE bug: the backend mirror applied w.get("level", "INFO") to a
  // sanity_checks warning, which carries severity and no level at all.
  const w = { code: 'paintable_floor_ratio', severity: 'high', message: '6,10×' };
  assert.equal(warningSeverity(w), SEV_HIGH);
  assert.equal(isActionable(w), true);
});

test('an authored ERROR outranks its severity', () => {
  assert.equal(warningSeverity({ level: 'ERROR', severity: 'low' }), SEV_HIGH);
});

test('level-only warnings keep the tier they always rendered at', () => {
  assert.equal(warningSeverity({ level: 'WARN' }), SEV_MED);
  assert.equal(warningSeverity({ level: 'INFO' }), SEV_LOW);
  assert.equal(warningSeverity({ level: 'FAIL' }), SEV_HIGH);
  assert.equal(warningSeverity({}), SEV_LOW);
  assert.equal(warningSeverity(null), SEV_LOW);
});

// ── counting ────────────────────────────────────────────────────────────────

test('summarizeSanity: įspėjimai are high+med, pastabos are low', () => {
  const s = summarizeSanity({
    warnings: [
      { severity: 'high' }, { severity: 'med' }, { severity: 'med' },
      { severity: 'low' }, { level: 'INFO' }, { level: 'ERROR' },
    ],
  });
  assert.deepEqual(
    { high: s.high, med: s.med, low: s.low, warnings: s.warnings, notes: s.notes },
    { high: 2, med: 2, low: 2, warnings: 4, notes: 2 },
  );
});

test('summarizeSanity: a high-severity check is counted, not swallowed', () => {
  // Pre-fix it landed in `info`, which the counter excluded entirely, so the
  // header read "0 įspėjimai" on a project with a 6,1× paint ratio.
  const s = summarizeSanity({ warnings: [{ severity: 'high', message: 'x' }] });
  assert.equal(s.warnings, 1);
  assert.equal(s.notes, 0);
});

test('summarizeSanity: tolerates a missing or malformed payload', () => {
  assert.equal(summarizeSanity(null).total, 0);
  assert.equal(summarizeSanity({ warnings: 'nope' }).total, 0);
});

test('groupBySeverity: loudest first, empty tiers omitted', () => {
  const groups = groupBySeverity([
    { severity: 'low', message: 'c' },
    { severity: 'high', message: 'a' },
    { severity: 'low', message: 'd' },
  ]);
  assert.deepEqual(groups.map(([sev, items]) => [sev, items.length]),
    [[SEV_HIGH, 1], [SEV_LOW, 2]]);
});

// ── actionable jumps ────────────────────────────────────────────────────────

test('warningAction: §6 checks whose fix lives in Prielaidos offer the jump', () => {
  assert.equal(warningAction({ code: 'paintable_floor_ratio' }), ACTION_PRIELAIDOS);
  assert.equal(warningAction({ code: 'ceiling_floor_mismatch' }), ACTION_PRIELAIDOS);
  assert.equal(warningAction({ code: 'consistency_height_uniformity' }), ACTION_PRIELAIDOS);
});

test('warningAction: falls back to `field` for blobs saved before the codes', () => {
  assert.equal(warningAction({ field: 'lubu_aukstis_m' }), ACTION_PRIELAIDOS);
});

test('warningAction: no invented affordance when no control exists', () => {
  assert.equal(warningAction({ code: 'baseboard_perimeter_mismatch' }), null);
  assert.equal(warningAction({}), null);
  assert.equal(warningAction(null), null);
});

// ── expected range, said once ───────────────────────────────────────────────

test('expectedSuffix: appended when the message does not state the range', () => {
  assert.equal(
    expectedSuffix({ message: 'Dažomas sienų plotas 4,57× grindų ploto',
      expected: '2,5–4,0×' }),
    '2,5–4,0×',
  );
});

test('expectedSuffix: suppressed when the message already says it', () => {
  // "Grindjuostės 56,0 m, tikėtina ~41,4 m (…) (tikėtina ~41,4 m)" — the row
  // said the same number twice.
  assert.equal(expectedSuffix({
    message: 'Grindjuostės 56,0 m, tikėtina ~41,4 m (perimetras 43,0 m − 2 durys × 0,8 m)',
    expected: '~41,4 m (±10 %)',
  }), null);
  assert.equal(expectedSuffix({
    message: 'Svetainė (nr=101): lubų aukštis 5.60 m neįprastas (norma 2.2–4.5 m).',
    expected: '2.2–4.5 m',
  }), null);
});

test('expectedSuffix: nothing to append', () => {
  assert.equal(expectedSuffix({ message: 'x' }), null);
  assert.equal(expectedSuffix({ message: 'x', expected: '  ' }), null);
  assert.equal(expectedSuffix(null), null);
});

// ── dismissal identity ──────────────────────────────────────────────────────

test('warningKey ignores severity so a re-run does not resurrect a dismissal', () => {
  const a = { source: 'sanity_checks', code: 'x', message: 'm', severity: 'med' };
  const b = { source: 'sanity_checks', code: 'x', message: 'm', severity: 'high' };
  assert.equal(warningKey(a), warningKey(b));
});

test('warningKey separates different findings from the same validator', () => {
  assert.notEqual(
    warningKey({ source: 's', code: 'a', message: 'm' }),
    warningKey({ source: 's', code: 'b', message: 'm' }),
  );
});

// ── revalidate merge ────────────────────────────────────────────────────────

const PREV = {
  warnings: [
    { source: 'sanity_checks', code: 'paintable_floor_ratio',
      severity: 'high', message: 'Dažomas sienų plotas 6,10× grindų ploto' },
    { source: 'perimeter_validator', code: 'perimeter_out_of_bounds',
      level: 'WARN', message: 'Salonas: perimetras neįmanomas' },
    { source: 'cross_page_validator', level: 'WARN', message: 'sena' },
  ],
  summary: { rooms_count: 7, total_area_m2: 95.6 },
};

test('mergeSanity: a stream the rebuild did not produce is preserved', () => {
  const fresh = {
    warnings: [{ source: 'cross_page_validator', level: 'WARN', message: 'nauja' }],
    summary: { rooms_count: 7, total_area_m2: 95.6 },
  };
  const out = mergeSanity(PREV, fresh);
  const codes = out.warnings.map((w) => w.code || w.message);
  assert.ok(codes.includes('paintable_floor_ratio'),
    'the §6 high-severity check must survive a revalidate that did not re-run it');
  assert.ok(codes.includes('perimeter_out_of_bounds'));
});

test('mergeSanity: a stream the rebuild DID produce is authoritative', () => {
  const fresh = {
    warnings: [{ source: 'cross_page_validator', level: 'WARN', message: 'nauja' }],
    summary: {},
  };
  const out = mergeSanity(PREV, fresh);
  const cross = out.warnings.filter((w) => w.source === 'cross_page_validator');
  assert.deepEqual(cross.map((w) => w.message), ['nauja']);
});

test('mergeSanity: a check that now passes disappears', () => {
  // The rebuild ran sanity_checks and it produced nothing for that code —
  // but it DID produce another sanity_checks row, so the stream is fresh.
  const fresh = {
    warnings: [{ source: 'sanity_checks', code: 'paint_consumption_rate',
      severity: 'low', message: 'Dažų sąnaudos 0,310 l/m²' }],
    summary: {},
  };
  const out = mergeSanity(PREV, fresh);
  assert.ok(!out.warnings.some((w) => w.code === 'paintable_floor_ratio'));
});

test('mergeSanity: the summary is recomputed from the merged rows', () => {
  const fresh = {
    warnings: [{ source: 'cross_page_validator', level: 'WARN', message: 'nauja' }],
    summary: { rooms_count: 7, total_area_m2: 95.6, warnings_count: 1, high: 0 },
  };
  const out = mergeSanity(PREV, fresh);
  // 1 high (§6) + 1 med (perimeter) + 1 med (fresh cross-page) = 3 actionable.
  assert.equal(out.summary.warnings_count, 3);
  assert.equal(out.summary.high, 1);
  assert.equal(out.summary.medium, 2);
  // Untouched keys ride along.
  assert.equal(out.summary.rooms_count, 7);
});

test('mergeSanity: identical rows are not duplicated', () => {
  const fresh = { warnings: [...PREV.warnings], summary: {} };
  const out = mergeSanity(PREV, fresh);
  assert.equal(out.warnings.length, PREV.warnings.length);
});

test('mergeSanity: a malformed rebuild leaves what is on screen alone', () => {
  assert.equal(mergeSanity(PREV, null), PREV);
  assert.equal(mergeSanity(PREV, {}), PREV);
});

test('mergeSanity: no prior state just adopts the rebuild', () => {
  const fresh = { warnings: [{ severity: 'high', message: 'a' }], summary: {} };
  const out = mergeSanity(null, fresh);
  assert.equal(out.warnings.length, 1);
  assert.equal(out.summary.high, 1);
});

// ── „Atidaryti Prielaidas" now lands on the named control (2026-09-02) ──────

test('assumptionFocus maps a warning to the control it is about', () => {
  assert.deepEqual(
    assumptionFocus({ code: 'lubu_aukstis_out_of_range', room: '110' }),
    { field: 'lubu_auksciai', roomNr: '110' });
  // Project-level validator: the section, no row.
  assert.deepEqual(
    assumptionFocus({ code: 'consistency_height_uniformity' }),
    { field: 'lubu_auksciai', roomNr: null });
  // Falls back to the warning's `field` when the code is unmapped.
  assert.deepEqual(
    assumptionFocus({ code: 'kazkas_naujo', field: 'lubu_aukstis_m', room: 102 }),
    { field: 'lubu_auksciai', roomNr: '102' });
  assert.deepEqual(
    assumptionFocus({ code: 'ceiling_floor_mismatch', room: '110' }),
    { field: 'stretch_ceiling_override', roomNr: '110' });
  // Nothing to scroll to → the panel just opens, exactly as before.
  assert.equal(assumptionFocus({ code: 'paint_consumption_rate' }), null);
  assert.equal(assumptionFocus(null), null);
  assert.equal(assumptionFocus({ code: 'lubu_aukstis_out_of_range', room: '  ' }).roomNr, null);
});

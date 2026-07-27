import test from 'node:test';
import assert from 'node:assert/strict';
import {
  parseExcludedSections,
  serializeExcludedSections,
  selectedFor,
  toggleSection,
} from './exportSectionSelection.js';

const SECTIONS = ['Dažymas', 'GKP montavimas', 'Plytelių klijavimas'];

test('no stored selection → everything is included', () => {
  const excluded = parseExcludedSections(null);
  assert.deepEqual([...selectedFor(SECTIONS, excluded)].sort(), [...SECTIONS].sort());
});

test('a NEW section defaults IN while old unchecks are preserved', () => {
  const stored = serializeExcludedSections(new Set(['GKP montavimas']));
  const excluded = parseExcludedSections(stored);
  const withNew = [...SECTIONS, 'Matavimai'];
  const selected = selectedFor(withNew, excluded);
  assert.ok(selected.has('Matavimai'), 'new skyrius must be included by default');
  assert.ok(!selected.has('GKP montavimas'), 'explicit uncheck must survive');
  assert.equal(selected.size, 3);
});

test('legacy v1 payload (array of INCLUDED names) does not crash and includes all', () => {
  const legacy = JSON.stringify(['Dažymas']);
  const excluded = parseExcludedSections(legacy);
  assert.equal(excluded.size, 0);
  assert.equal(selectedFor(SECTIONS, excluded).size, 3);
});

test('corrupt payloads are tolerated', () => {
  for (const raw of ['', 'not json', '{}', '{"v":2}', '{"excluded":"x"}', 'null']) {
    assert.equal(parseExcludedSections(raw).size, 0, raw);
  }
  assert.deepEqual([...parseExcludedSections('{"v":2,"excluded":["A",3,null]}')], ['A']);
});

test('toggleSection flips membership and round-trips through storage', () => {
  let excluded = new Set();
  excluded = toggleSection(excluded, 'Dažymas');
  assert.ok(excluded.has('Dažymas'));
  const roundTripped = parseExcludedSections(serializeExcludedSections(excluded));
  assert.deepEqual([...roundTripped], ['Dažymas']);
  assert.ok(!toggleSection(roundTripped, 'Dažymas').has('Dažymas'));
});

test('exclusions for sections that vanished are kept, not resurrected as checked', () => {
  const excluded = parseExcludedSections(serializeExcludedSections(new Set(['Senas skyrius'])));
  assert.equal(selectedFor(SECTIONS, excluded).size, 3);       // not shown now
  assert.ok(!selectedFor([...SECTIONS, 'Senas skyrius'], excluded).has('Senas skyrius'));
});

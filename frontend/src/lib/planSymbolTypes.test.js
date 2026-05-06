import test from 'node:test';
import assert from 'node:assert/strict';
import { getPlanSymbolTypes } from './planSymbolTypes.js';

test('getPlanSymbolTypes: floor and partition plans show openings, not MEP fixtures', () => {
  assert.deepEqual(
    getPlanSymbolTypes('aukstu').map(type => type.id),
    ['durys', 'langai']
  );
  assert.deepEqual(
    getPlanSymbolTypes('pertvaru planas').map(type => type.id),
    ['durys', 'langai']
  );
});

test('getPlanSymbolTypes: electrical plans show electrical symbols', () => {
  assert.deepEqual(
    getPlanSymbolTypes('elektros apsvietimo planas').map(type => type.id),
    ['rozetes', 'jungikliai', 'sviestuvai']
  );
});

test('getPlanSymbolTypes: unknown page types keep the full manual choice set', () => {
  assert.ok(getPlanSymbolTypes('unknown').length > 8);
});

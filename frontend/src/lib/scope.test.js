import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isDefaultScope, isFamilyOn, isRoomIncluded, learnedDefaults, normalizeScope, rememberScope,
  rulesWithScope, scopeForBackend, withFamily, withLubos, withRoomIncluded, withSienosAngos,
} from './scope.js';

test('normalizeScope fills the defaults and drops junk', () => {
  assert.deepEqual(normalizeScope(undefined), { patalpos_ne: [], darbai_ne: [], lubos: 'dazomos', sienos_angos: 'atimti' });
  assert.deepEqual(normalizeScope({ patalpos_ne: [7, ' 07', '07'], darbai_ne: ['plyteles', 'x'], lubos: 'ne_musu', sienos_angos: 'nope' }),
    { patalpos_ne: ['07', '7'], darbai_ne: ['plyteles'], lubos: 'ne_musu', sienos_angos: 'atimti' });
});

test('a default scope sends nothing to the backend', () => {
  assert.equal(isDefaultScope(null), true);
  assert.equal(scopeForBackend({ lubos: 'dazomos' }), null);
  assert.deepEqual(rulesWithScope({ glaistas_q_lygis: 'Q2', apimtis: { lubos: 'ne_musu' } }, null), { glaistas_q_lygis: 'Q2' });
  assert.deepEqual(rulesWithScope({ glaistas_q_lygis: 'Q2' }, { patalpos_ne: ['07'] }),
    { glaistas_q_lygis: 'Q2', apimtis: { patalpos_ne: ['07'], darbai_ne: [], lubos: 'dazomos', sienos_angos: 'atimti' } });
});

test('room and family switches are idempotent and reversible', () => {
  let s = withRoomIncluded(null, '07', false);
  assert.equal(isRoomIncluded(s, '07'), false);
  assert.equal(isRoomIncluded(s, '06'), true);
  s = withRoomIncluded(s, '07', false);
  assert.deepEqual(s.patalpos_ne, ['07']);
  s = withRoomIncluded(s, '07', true);
  assert.equal(isDefaultScope(s), true);
  s = withFamily(s, 'plyteles', false);
  assert.equal(isFamilyOn(s, 'plyteles'), false);
  assert.deepEqual(withFamily(s, 'nesamone', false), s);
  assert.equal(withLubos(s, 'itempiamos').lubos, 'itempiamos');
  assert.equal(withLubos(s, 'x').lubos, 'dazomos');
  assert.equal(withSienosAngos(s, 'neatimti').sienos_angos, 'neatimti');
});

test('a project-level choice becomes a default after three identical projects — and only then', () => {
  let h = [];
  h = rememberScope(h, { lubos: 'ne_musu' });
  h = rememberScope(h, { lubos: 'ne_musu' });
  assert.deepEqual(learnedDefaults(h), {}, 'two projects are not a habit');
  h = rememberScope(h, { lubos: 'ne_musu', darbai_ne: ['elektra'] });
  assert.deepEqual(learnedDefaults(h), { lubos: 'ne_musu' }, 'the family choice differs on the third → not learned');
  h = rememberScope(h, { lubos: 'dazomos' });
  assert.deepEqual(learnedDefaults(h), {}, 'the newest project broke the streak');
  assert.equal(rememberScope(new Array(20).fill({}), {}).length, 10, 'history is capped');
  assert.deepEqual(learnedDefaults(null), {});
});

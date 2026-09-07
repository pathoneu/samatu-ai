import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isDefaultScope, isFamilyOn, isRoomFamilyOn, isRoomIncluded, learnedDefaults, normalizeScope,
  rememberScope, roomFamiliesOff, rulesWithScope, scopeForBackend, withFamily, withLubos,
  withKampai, withRoomFamily, withRoomIncluded, withRotband, withSienosAngos,
} from './scope.js';

test('normalizeScope fills the defaults and drops junk', () => {
  assert.deepEqual(normalizeScope(undefined), { patalpos_ne: [], darbai_ne: [], patalpu_sritys_ne: {}, lubos: 'dazomos', sienos_angos: 'atimti', rotband: 'dalis', rotband_dalis: null, kampai: 'su_vidiniais' });
  assert.deepEqual(normalizeScope({ patalpos_ne: [7, ' 07', '07'], darbai_ne: ['plyteles', 'x'], lubos: 'ne_musu', sienos_angos: 'nope',
    patalpu_sritys_ne: { '03': ['grindys', 'elektra'], '': ['apdaila'] }, rotband: 'dalis', rotband_dalis: '45' }),
    { patalpos_ne: ['07', '7'], darbai_ne: ['plyteles'], patalpu_sritys_ne: { '03': ['grindys'] }, lubos: 'ne_musu', sienos_angos: 'atimti', rotband: 'dalis', rotband_dalis: 45, kampai: 'su_vidiniais' });
});

test('a default scope sends nothing to the backend', () => {
  assert.equal(isDefaultScope(null), true);
  assert.equal(scopeForBackend({ lubos: 'dazomos' }), null);
  assert.deepEqual(rulesWithScope({ glaistas_q_lygis: 'Q2', apimtis: { lubos: 'ne_musu' } }, null), { glaistas_q_lygis: 'Q2' });
  assert.deepEqual(rulesWithScope({ glaistas_q_lygis: 'Q2' }, { patalpos_ne: ['07'] }),
    { glaistas_q_lygis: 'Q2', apimtis: { patalpos_ne: ['07'], darbai_ne: [], patalpu_sritys_ne: {}, lubos: 'dazomos', sienos_angos: 'atimti', rotband: 'dalis', rotband_dalis: null, kampai: 'su_vidiniais' } });
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


test('one room can switch off apdaila / grindys / plyteles; project-wide families show in the room too', () => {
  let s = withRoomFamily(null, '03', 'grindys', false);
  assert.deepEqual(roomFamiliesOff(s, '03'), ['grindys']);
  assert.equal(isRoomFamilyOn(s, '03', 'apdaila'), true);
  assert.equal(isRoomFamilyOn(s, '04', 'grindys'), true);
  s = withFamily(s, 'plyteles', false);
  assert.deepEqual(roomFamiliesOff(s, '04'), ['plyteles'], 'a project-wide family is off in every room');
  s = withRoomFamily(s, '03', 'grindys', true);
  assert.deepEqual(s.patalpu_sritys_ne, {}, 'switching back on removes the room entry');
  assert.deepEqual(withRoomFamily(s, '03', 'elektra', false), s, 'electrics are not a per-room family');
});

test('Rotband is a choice: none, a share, or every painted wall', () => {
  assert.equal(isDefaultScope(withRotband(null, 'dalis')), true);
  const half = withRotband(null, 'dalis', 50);
  assert.equal(half.rotband_dalis, 50);
  assert.equal(isDefaultScope(half), false);
  assert.equal(withRotband(null, 'nera').rotband, 'nera');
  assert.equal(withRotband(null, 'visos').rotband, 'visos');
  assert.equal(withRotband(null, 'dalis', '').rotband_dalis, null);
  assert.equal(withRotband(null, 'dalis', 140).rotband_dalis, 100);
});


test('corner bead on the rooms\' own corners is a choice, default as today', () => {
  assert.equal(isDefaultScope(withKampai(null, 'su_vidiniais')), true);
  assert.equal(withKampai(null, 'tik_isoriniai').kampai, 'tik_isoriniai');
  assert.equal(isDefaultScope(withKampai(null, 'tik_isoriniai')), false);
  assert.equal(withKampai(null, 'x').kampai, 'su_vidiniais');
});

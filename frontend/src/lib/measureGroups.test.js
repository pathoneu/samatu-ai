import test from 'node:test';
import assert from 'node:assert/strict';
import {
  NO_FILTERS, addGroup, assignToGroup, filtersActive, groupedSections, groupsOf, nextGroupName, passesFilters,
  removeGroup, renameGroup,
} from './measureGroups.js';

const ITEMS = [
  { key: 'm:a', kind: 'distance', source: 'user', pages: [1] },
  { key: 'm:b', kind: 'area', source: 'user', pages: [2] },
  { key: 'type:roz', kind: 'count', source: 'auto', pages: [2, 3] },
  { key: 'type:sv', kind: 'count', source: 'mixed', pages: [3] },
];

test('groups are named, renamed, removed — nothing is ever deleted with a group', () => {
  let s = addGroup(null, '', 'g1');
  assert.deepEqual(s.groups, [{ id: 'g1', name: 'Grupė 1' }]);
  s = addGroup(s, '  Virtuvė  ', 'g2');
  assert.equal(s.groups[1].name, 'Virtuvė');
  assert.equal(nextGroupName(s), 'Grupė 3');
  s = renameGroup(s, 'g1', 'Vonia');
  assert.equal(s.groups[0].name, 'Vonia');
  assert.equal(renameGroup(s, 'g1', '   ').groups[0].name, 'Vonia', 'an empty name keeps the old one');
  s = assignToGroup(s, 'm:a', 'g1');
  s = assignToGroup(s, 'm:b', 'g1');
  s = removeGroup(s, 'g1');
  assert.deepEqual(s.groups.map((g) => g.id), ['g2']);
  assert.deepEqual(s.members, {}, 'its measurements go back to „Be grupės"');
});

test('stored groups are read defensively', () => {
  const s = groupsOf({ measureGroups: { groups: [{ id: 1, name: 'A' }, { id: 2, name: '' }, null], members: { 'm:a': 1, 'm:b': 9 } } });
  assert.deepEqual(s.groups, [{ id: '1', name: 'A' }]);
  assert.deepEqual(s.members, { 'm:a': '1' });
  assert.deepEqual(groupsOf({}), { groups: [], members: {} });
  // assigning to a group that does not exist takes the item out
  assert.deepEqual(assignToGroup(s, 'm:a', 'nope').members, {});
});

test('sections: every group (empty ones too), then „Be grupės"', () => {
  let s = addGroup(null, 'Vonia', 'g1');
  s = addGroup(s, 'Tuščia', 'g2');
  s = assignToGroup(s, 'm:b', 'g1');
  const sec = groupedSections(ITEMS, s);
  assert.deepEqual(sec.map((x) => [x.name, x.items.map((i) => i.key)]), [
    ['Vonia', ['m:b']], ['Tuščia', []], ['Be grupės', ['m:a', 'type:roz', 'type:sv']],
  ]);
  // no groups → one unnamed section, the list as it was
  assert.deepEqual(groupedSections(ITEMS, null).map((x) => [x.name, x.items.length]), [[null, 4]]);
});

test('filters: who found it, this sheet, kind — a mixed count type passes both sources', () => {
  const pass = (f, page) => ITEMS.filter((i) => passesFilters(i, f, { page })).map((i) => i.key);
  assert.deepEqual(pass(NO_FILTERS), ITEMS.map((i) => i.key));
  assert.deepEqual(pass({ source: 'auto' }), ['type:roz', 'type:sv']);
  assert.deepEqual(pass({ source: 'user' }), ['m:a', 'm:b', 'type:sv']);
  assert.deepEqual(pass({ thisSheet: true }, 2), ['m:b', 'type:roz']);
  assert.deepEqual(pass({ kind: 'count', thisSheet: true }, 3), ['type:roz', 'type:sv']);
  assert.deepEqual(pass({ kind: 'note' }), []);
  assert.equal(filtersActive(NO_FILTERS), false);
  assert.equal(filtersActive({ thisSheet: true }), true);
});

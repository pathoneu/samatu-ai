// measureGroups — named groups and filters for the Matavimai list (Pathon v3 W5-B, B10; coverage #126, #127).
//
// WHERE GROUPS LIVE. `project.measureGroups = { groups: [{id, name}], members: {<item key>: groupId} }` — beside the
// measurements, never on them: the viewer owns `measurements` and writes its whole list back on every save, so a
// field put on a measurement object here would be gone at its next save (the same reason W4-A's links live in
// `project.measurementRows`). Item keys are the list's own (lib/measuredRows linkKey: „m:<id>", „type:<id>"), so a
// group survives every redraw of the list and a measurement deleted in the viewer simply drops out of its group.
//
// FILTERS (local to the panel, not stored): kas — „Rasta automatiškai" (legend / „Rasti panašius" marks) or „Jūsų";
// lapas — only the sheet on screen; tipas — atstumas / perimetras / plotas / kiekis / pastabos. Pure.

export const KIND_FILTERS = Object.freeze([
  { id: 'distance', label: 'Atstumai' },
  { id: 'perimeter', label: 'Perimetrai' },
  { id: 'area', label: 'Plotai' },
  { id: 'count', label: 'Kiekiai' },
  { id: 'note', label: 'Pastabos' },
]);

export const SOURCE_FILTERS = Object.freeze([
  { id: 'auto', label: 'Rasta automatiškai' },
  { id: 'user', label: 'Jūsų' },
]);

export const NO_FILTERS = Object.freeze({ source: null, thisSheet: false, kind: null });
const NAME_MAX = 60;

function cleanName(name) {
  return String(name ?? '').replace(/\s+/g, ' ').trim().slice(0, NAME_MAX);
}

/** The stored groups, always well-formed ({groups: [], members: {}} when none). */
export function groupsOf(project) {
  const raw = project?.measureGroups;
  const groups = Array.isArray(raw?.groups)
    ? raw.groups.filter((g) => g && g.id != null && cleanName(g.name)).map((g) => ({ id: String(g.id), name: cleanName(g.name) }))
    : [];
  const ids = new Set(groups.map((g) => g.id));
  const members = {};
  for (const [k, v] of Object.entries(raw?.members && typeof raw.members === 'object' ? raw.members : {})) {
    if (ids.has(String(v))) members[k] = String(v);
  }
  return { groups, members };
}

/** „Grupė 1", „Grupė 2"… — the next free default name. */
export function nextGroupName(state) {
  const taken = new Set((state?.groups || []).map((g) => g.name));
  let n = (state?.groups || []).length + 1;
  while (taken.has(`Grupė ${n}`)) n += 1;
  return `Grupė ${n}`;
}

export function addGroup(state, name = null, id = null) {
  const s = groupsOf({ measureGroups: state });
  const gid = id || `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return { groups: [...s.groups, { id: gid, name: cleanName(name) || nextGroupName(s) }], members: { ...s.members } };
}

/** Rename; an empty name keeps the old one (a group is never nameless). */
export function renameGroup(state, id, name) {
  const s = groupsOf({ measureGroups: state });
  const n = cleanName(name);
  if (!n) return s;
  return { ...s, groups: s.groups.map((g) => (g.id === String(id) ? { ...g, name: n } : g)) };
}

/** Remove a group; its measurements go back to „Be grupės" (nothing is deleted). */
export function removeGroup(state, id) {
  const s = groupsOf({ measureGroups: state });
  const members = {};
  for (const [k, v] of Object.entries(s.members)) if (v !== String(id)) members[k] = v;
  return { groups: s.groups.filter((g) => g.id !== String(id)), members };
}

/** Put an item in a group, or take it out (groupId null). */
export function assignToGroup(state, key, groupId) {
  const s = groupsOf({ measureGroups: state });
  const members = { ...s.members };
  if (groupId == null || !s.groups.some((g) => g.id === String(groupId))) delete members[key];
  else members[key] = String(groupId);
  return { ...s, members };
}

/**
 * Does an item pass the filters? item = {key, kind, source: 'auto'|'user'|'mixed', pages: [n…]}. A count type holding
 * both found and placed marks is 'mixed' — it shows under both „Rasta automatiškai" and „Jūsų".
 */
export function passesFilters(item, filters = NO_FILTERS, { page = null } = {}) {
  const f = { ...NO_FILTERS, ...(filters || {}) };
  if (f.kind && item.kind !== f.kind) return false;
  if (f.source && item.source !== f.source && item.source !== 'mixed') return false;
  if (f.thisSheet && page != null && !(item.pages || []).includes(Number(page))) return false;
  return true;
}

export function filtersActive(filters) {
  const f = { ...NO_FILTERS, ...(filters || {}) };
  return Boolean(f.kind || f.source || f.thisSheet);
}

/**
 * The list in sections: each named group (in its order, empty ones too — a new group must be visible to drop into)
 * and then „Be grupės". → [{id, name, items}] with id null for the ungrouped section (omitted when empty and there
 * are groups).
 */
export function groupedSections(items, state) {
  const s = groupsOf({ measureGroups: state });
  const byGroup = new Map(s.groups.map((g) => [g.id, []]));
  const loose = [];
  for (const it of items) {
    const g = s.members[it.key];
    if (g && byGroup.has(g)) byGroup.get(g).push(it); else loose.push(it);
  }
  const out = s.groups.map((g) => ({ id: g.id, name: g.name, items: byGroup.get(g.id) }));
  if (loose.length || !s.groups.length) out.push({ id: null, name: s.groups.length ? 'Be grupės' : null, items: loose });
  return out;
}

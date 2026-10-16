// History mode for the viewer's committed measurements and count marks
// (2026-10-16, Togal analysis §6 / §11): one undo / redo stack over the whole
// list, and the „Istorija" panel that lists it and can step back to any entry.
//
// Pure reducer, snapshot based: every entry keeps the list before and after the
// action. Lists are small (hundreds of marks at most) and the snapshots share
// the measurement objects, so a 50-deep history costs little and makes
// „Grąžinti iki čia" a plain assignment.
//
// state = { present: Measurement[], past: Entry[], future: Entry[] }
// Entry = { id, label, at, before: Measurement[], after: Measurement[] }
//   past   — oldest first; the last entry is the action that produced `present`
//   future — the undone entries, most recently undone LAST (redo pops it)

export const HISTORY_LIMIT = 50;

let _seq = 0;

export function initHistory(present = []) {
  return { present: Array.isArray(present) ? present : [], past: [], future: [] };
}

/**
 * Actions:
 *   { type: 'apply', update: Measurement[] | (present) => Measurement[], label?, describe?, at? }
 *        — records an entry unless the list did not change. `describe(before, after)`
 *          returns the label when `label` is not given (see describeChange).
 *   { type: 'undo' } · { type: 'redo' }
 *   { type: 'revertTo', entryId } — the state right after that entry; later entries
 *        become redoable.
 *   { type: 'reset', present } — new list, history cleared (hydration).
 */
export function historyReducer(state, action) {
  switch (action?.type) {
    case 'apply': {
      const before = state.present;
      const after = typeof action.update === 'function' ? action.update(before) : action.update;
      if (!Array.isArray(after) || sameList(before, after)) return state;
      const label = action.label ?? action.describe?.(before, after) ?? 'Pakeisti matavimai';
      const entry = { id: `h${Date.now().toString(36)}_${_seq++}`, label, at: action.at ?? Date.now(), before, after };
      return { present: after, past: [...state.past, entry].slice(-HISTORY_LIMIT), future: [] };
    }
    case 'undo': {
      if (!state.past.length) return state;
      const entry = state.past[state.past.length - 1];
      return { present: entry.before, past: state.past.slice(0, -1), future: [...state.future, entry] };
    }
    case 'redo': {
      if (!state.future.length) return state;
      const entry = state.future[state.future.length - 1];
      return { present: entry.after, past: [...state.past, entry], future: state.future.slice(0, -1) };
    }
    case 'revertTo': {
      const i = state.past.findIndex((h) => h.id === action.entryId);
      if (i < 0) return state;
      const undone = state.past.slice(i + 1);            // oldest first
      if (!undone.length) return state;
      return {
        present: state.past[i].after,
        past: state.past.slice(0, i + 1),
        // redo order: the entry right after i must be redone first → it goes LAST
        future: [...state.future, ...undone.reverse()],
      };
    }
    case 'reset':
      return initHistory(action.present);
    default:
      return state;
  }
}

export const canUndo = (s) => s.past.length > 0;
export const canRedo = (s) => s.future.length > 0;

function sameList(a, b) {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

// ---- labels ------------------------------------------------------------------

// Lithuanian noun + the participle's gender: atstumas / plotas / perimetras are
// masculine („Pridėtas"), žymė feminine („Pridėta").
const NOUN = {
  distance: { one: 'atstumas', many: 'atstumai', fem: false },
  perimeter: { one: 'perimetras', many: 'perimetrai', fem: false },
  area: { one: 'plotas', many: 'plotai', fem: false },
  count: { one: 'žymė', many: 'žymės', fem: true },
};
const nounOf = (kind) => NOUN[kind] || { one: 'matavimas', many: 'matavimai', fem: false };

function verb(stem, noun, many) {
  // stem: 'Pridėt' | 'Pašalint' | 'Pervadint'
  if (many) return `${stem}${noun.fem ? 'os' : 'i'}`;
  return `${stem}${noun.fem ? 'a' : 'as'}`;
}

// „Pridėtas atstumas 6,65 m · „Virtuvė" · psl. 1" — the value sits on the noun, the rest after dots.
function single(head, m, ctx) {
  let out = head;
  const tail = [];
  if (m.kind === 'count') {
    const t = ctx.countTypeLabel?.(m.typeId);
    if (t) tail.push(t);
  } else {
    const v = ctx.formatValue?.(m);
    if (v) out += ` ${v}`;
  }
  if (m.name) tail.push(`„${m.name}"`);
  if (m.page != null) tail.push(`psl. ${m.page}`);
  return [out, ...tail].join(' · ');
}

/**
 * The history line for a change from `before` to `after`, in the panel's words:
 *   „Pridėtas atstumas 6,65 m · psl. 1", „Pašalinta žymė · Rozetės · psl. 2",
 *   „Pašalintos 5 žymės · Rozetės", „Pervadintas plotas → „Virtuvė"",
 *   „Pakeistas žymės tipas · Rozetės → Jungikliai".
 * ctx: { countTypeLabel(typeId) → string, formatValue(m) → '6,65 m' | null }
 */
export function describeChange(before, after, ctx = {}) {
  const beforeById = new Map(before.map((m) => [m.id, m]));
  const afterById = new Map(after.map((m) => [m.id, m]));
  const added = after.filter((m) => !beforeById.has(m.id));
  const removed = before.filter((m) => !afterById.has(m.id));
  const changed = after.filter((m) => beforeById.has(m.id) && beforeById.get(m.id) !== m);

  if (added.length && !removed.length && !changed.length) return addRemoveLabel('Pridėt', added, ctx);
  if (removed.length && !added.length && !changed.length) return addRemoveLabel('Pašalint', removed, ctx);
  if (changed.length === 1 && !added.length && !removed.length) {
    const prev = beforeById.get(changed[0].id);
    const m = changed[0];
    const noun = nounOf(m.kind);
    if ((prev.name || '') !== (m.name || '')) {
      const head = `${verb('Pervadint', noun, false)} ${noun.one}`;
      return m.name ? `${head} → „${m.name}"` : `${head} · pavadinimas pašalintas`;
    }
    if (prev.typeId !== m.typeId) {
      const from = ctx.countTypeLabel?.(prev.typeId) || prev.typeId || '—';
      const to = ctx.countTypeLabel?.(m.typeId) || m.typeId || '—';
      return `Pakeistas žymės tipas · ${from} → ${to}`;
    }
    return `${verb('Pakeist', noun, false)} ${noun.one}${m.page != null ? ` · psl. ${m.page}` : ''}`;
  }
  if (changed.length > 1 && !added.length && !removed.length) {
    const sameType = changed.every((m) => m.kind === 'count');
    return sameType ? `Pakeistos ${changed.length} žymės` : `Pakeisti ${changed.length} matavimai`;
  }
  return 'Pakeisti matavimai';
}

function addRemoveLabel(stem, list, ctx) {
  if (list.length === 1) {
    const m = list[0];
    const noun = nounOf(m.kind);
    return single(`${verb(stem, noun, false)} ${noun.one}`, m, ctx);
  }
  const kinds = new Set(list.map((m) => m.kind));
  if (kinds.size === 1) {
    const noun = nounOf(list[0].kind);
    const head = `${verb(stem, noun, true)} ${list.length} ${noun.many}`;
    if (list[0].kind === 'count') {
      const types = new Set(list.map((m) => m.typeId));
      const t = types.size === 1 ? ctx.countTypeLabel?.(list[0].typeId) : null;
      return t ? `${head} · ${t}` : head;
    }
    return head;
  }
  return `${verb(stem, NOUN.distance, true)} ${list.length} matavimai`;
}

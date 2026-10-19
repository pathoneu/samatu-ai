// roomSheetNav — moving around the room sheet without the mouse hunt (Pathon v3 W5-C, C7 / coverage #215).
//
//   roomPickerItems  the room picker's list: every room with its state in words — „patikrinta", „liko
//                    patikrinti", „neskaičiuojama" (left out of the estimate), „sujungta su 04" (merged)
//   typedDigit       a digit typed while a fact is focused opens that fact's number field with the digit
//                    already in it — no „Pataisyti" click first
//
// Pure; RoomSheet / RoomSheetStrip / FactRow render and act.

const STATE_ORDER = ['open', 'checked', 'merged', 'excluded'];

/**
 * rooms     the sheet's rooms in drawing order ({nr, pavadinimas, user_verified_at, _sujungta_i})
 * included  (nr) → boolean — the room counts in the estimate (lib/scope.isRoomIncluded)
 * current   the room on screen
 * → [{ nr, name, state, mergedInto, current }]
 */
export function roomPickerItems(rooms, included = () => true, current = null) {
  return (Array.isArray(rooms) ? rooms : [])
    .filter((r) => r && r.nr != null && String(r.nr) !== '')
    .map((r) => {
      const nr = String(r.nr);
      const mergedInto = r._sujungta_i != null && String(r._sujungta_i) !== '' ? String(r._sujungta_i) : null;
      let state = r.user_verified_at ? 'checked' : 'open';
      if (mergedInto) state = 'merged';
      else if (!included(nr)) state = 'excluded';
      return { nr, name: r.pavadinimas || r.name || '', state, mergedInto, current: current != null && String(current) === nr };
    });
}

/** How many rooms are in each state — the picker's header line. */
export function pickerCounts(items) {
  const out = Object.fromEntries(STATE_ORDER.map((s) => [s, 0]));
  for (const it of items || []) if (out[it.state] != null) out[it.state] += 1;
  return out;
}

const TYPING = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/**
 * The digit to put into the focused fact's number field, or null.
 * event { key, ctrlKey, metaKey, altKey, defaultPrevented }
 * ctx   { targetTag, targetEditable, layerOpen, busy, factKind } — factKind: the focused fact's editable kind
 */
export function typedDigit(event = {}, ctx = {}) {
  if (!event || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return null;
  if (!/^[0-9]$/.test(String(event.key || ''))) return null;
  if (TYPING.has(String(ctx.targetTag || '').toUpperCase()) || ctx.targetEditable) return null;
  if (ctx.layerOpen || ctx.busy) return null;
  if (ctx.factKind !== 'number') return null;
  return event.key;
}

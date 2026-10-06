/**
 * escapeToClose — may this Escape close the open drawer?
 *
 * Not when something inside already handled it (`defaultPrevented`: a field
 * that cancels its own edit on Esc calls preventDefault), and not when it comes
 * from a field being typed in: there Esc belongs to the field, and a value some
 * fields commit only on blur (the Nustatymai „Visoms patalpoms" height) must not
 * be cut off by the drawer closing under them. Pure, so the rule is tested
 * without a browser.
 */

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/** An element the user types into: a text field, a list box, editable text. */
export function isTypingTarget(target) {
  if (!target || typeof target !== 'object') return false;
  if (target.isContentEditable) return true;
  return TYPING_TAGS.has(String(target.tagName || '').toUpperCase());
}

/** A keydown that should close the drawer: Escape, unhandled, not from a field being typed in. */
export function closesOnEscape(event) {
  if (!event || event.key !== 'Escape' || event.defaultPrevented) return false;
  return !isTypingTarget(event.target);
}

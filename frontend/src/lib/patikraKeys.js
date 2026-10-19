// patikraKeys — the two keys of the Patikra question queue (Pathon v3 W5-C, task C4 / coverage #217).
//
//   Enter → „Tinka": the proposed answer is taken and the next question comes up (the card's own
//           `question-accept` button is pressed, so every kind of question answers the way its button does)
//   Esc   → back to the list: the focus goes to the current question in the list on the left
//
// Pure: the page hands in what it knows; the decision is made here so the rules can be tested.
// A key never acts while he types (fields keep their own Enter — the height field already answers with it),
// while a menu or dialog is open, while a save is running, or with a modifier held. Enter on a focused button
// is the button's own click, so it is left alone too (no double answer).

const TYPING = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

/**
 * @param {{key:string, ctrlKey?:boolean, metaKey?:boolean, altKey?:boolean, shiftKey?:boolean,
 *          defaultPrevented?:boolean, isComposing?:boolean}} event
 * @param {{targetTag?:string, targetEditable?:boolean, targetIsButton?:boolean, insideQueue?:boolean,
 *          onBody?:boolean, layerOpen?:boolean, busy?:boolean, canAccept?:boolean}} ctx
 * @returns {'accept'|'list'|null}
 */
export function patikraKeyAction(event = {}, ctx = {}) {
  if (!event || event.defaultPrevented || event.isComposing) return null;
  if (event.ctrlKey || event.metaKey || event.altKey) return null;
  if (ctx.layerOpen) return null;
  // only while he is in the queue (or nowhere in particular — the page itself has the focus)
  if (!ctx.insideQueue && !ctx.onBody) return null;
  const typing = TYPING.has(String(ctx.targetTag || '').toUpperCase()) || Boolean(ctx.targetEditable);
  if (event.key === 'Escape') return 'list';
  if (event.key !== 'Enter' || event.shiftKey) return null;
  if (typing || ctx.targetIsButton) return null;
  if (ctx.busy || !ctx.canAccept) return null;
  return 'accept';
}

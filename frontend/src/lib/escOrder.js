// escOrder — what ONE press of Esc undoes in the viewer (Pathon v3 click model, W1-B task B4; design
// 2026-10-18 §5 „Esc order is tool → panel → selection", Kreo §3 „removes the last point; with no points
// left, exits the tool").
//
// Before: Esc closed the search, disarmed the tool AND dropped the room in one press, and did not close
// Masteliai or Istorija (audit F3). Now each press takes one step back, smallest first:
//
//   1. a menu or dialog on top            — it closes itself; nothing else happens
//   2. the last point of a measurement    — the drawing stays, one point shorter
//   3. a calibration's first point
//   4. an outline being edited            — left without saving
//   5. an outline tool's last click (Padalyti / Sujungti / Atimti), then the tool itself
//   6. „Rasti panašius", then an armed „Kontūras paspaudus"
//   7. the marks selected with „Žymėti" / „Laso"
//   8. the armed tool                     — back to rest
//   9. open panels: search, Masteliai, Istorija, the scale check card
//  10. the selected room — last, and never while a panel above is still open
//
// Pure: TakeoffViewer gathers the state and acts on the step's id. A new step (W1-D's pending room
// proposal, for one) is one line in ESC_STEPS, in the place its weight says.

export const ESC_STEPS = [
  { id: 'popover', when: (s) => !!s.popoverOpen },
  { id: 'draftPoint', when: (s) => (s.draftPoints || 0) > 0 },
  { id: 'calibPoint', when: (s) => !!s.calibPoint },
  { id: 'outlineEdit', when: (s) => !!s.outlineEdit },
  { id: 'outlineToolStep', when: (s) => !!s.outlineTool && (s.outlineToolSteps || 0) > 0 },
  { id: 'outlineTool', when: (s) => !!s.outlineTool },
  { id: 'symbolSearch', when: (s) => !!s.symbolSearch },
  { id: 'fill', when: (s) => !!s.fillArmed },
  { id: 'measureSelection', when: (s) => (s.measureSelection || 0) > 0 },
  { id: 'tool', when: (s) => s.tool != null },
  { id: 'panel', when: (s) => !!s.panelOpen },
  { id: 'room', when: (s) => !!s.roomSelected },
];

/** The id of the step one Esc takes for this state, or null when there is nothing to step back from. */
export function escStep(state = {}) {
  const step = ESC_STEPS.find((st) => st.when(state));
  return step ? step.id : null;
}

/**
 * A menu, dialog or the draft's pop-up is open in the document (Radix closes its own on Esc). A layer on its
 * way out (Radix keeps it in the DOM with data-state="closed" while it fades) is not open: an Esc pressed
 * right after a menu choice must reach the panel that choice opened.
 */
export const OPEN_LAYER_SELECTOR = ['[role="menu"]', '[role="dialog"]', '[role="alertdialog"]']
  .map((s) => `${s}:not([data-state="closed"])`).concat('[data-draft-menu]').join(', ');

export function openLayerInDocument(doc = (typeof document !== 'undefined' ? document : null)) {
  return !!doc?.querySelector?.(OPEN_LAYER_SELECTOR);
}

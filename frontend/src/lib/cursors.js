// cursors — ONE table of the viewer's pointer shapes (Pathon v3 W5-A, A6 [#112]).
//
// Every layer that sets a CSS cursor asks here, so the same act always looks the same: a crosshair while a
// point is placed, a grabbing hand while something is dragged, a pointer over a thing a click opens. Before,
// each layer wrote its own string (OutlineEditLayer 'grab' / 'copy', MeasureLayer 'crosshair', the outline
// tools 'pointer' / 'crosshair'…) and two layers could disagree about the same gesture. Pure.

export const CURSORS = Object.freeze({
  rest: 'default',          // nothing armed, or a layer that only shows
  select: 'default',        // „Žymėti": a click picks what is under it
  pan: 'grab',              // „Rankutė" / held Space, before the drag
  panning: 'grabbing',      // …while the drawing moves
  place: 'crosshair',       // a point is placed: measure, calibrate, count, a hole, a cut line
  box: 'crosshair',         // a box is dragged: marquee, „Rasti panašius", a rectangle hole
  vertex: 'grab',           // over a corner that can be moved
  dragging: 'grabbing',     // a corner or an edge being moved
  edge: 'move',             // over an outline edge: drag moves it, a click adds a corner
  insert: 'copy',           // over an edge's middle point: a click adds a corner there
  pick: 'pointer',          // over a thing a click opens or picks (an opening, a neighbour to merge, a link)
  busy: 'progress',         // a request is under way (the room tool reading)
  refused: 'not-allowed',   // a button that cannot act yet
});

// What each mode shows while nothing is under the pointer.
const MODE_CURSORS = {
  select: 'select',
  lasso: 'box',
  pan: 'pan',
  distance: 'place',
  area: 'place',
  perimeter: 'place',
  count: 'place',
  calibrate: 'place',
  scalecheck: 'place',
  room: 'place',
  findSimilar: 'box',
  outlineEdit: 'rest',
  measureEdit: 'rest',
  split: 'place',
  merge: 'rest',
  subtract: 'place',
  fill: 'place',
};

export const CURSOR_MODES = Object.freeze(Object.keys(MODE_CURSORS));

/** The CSS cursor for a role from CURSORS ('vertex', 'dragging'…); an unknown role is the plain arrow. */
export function cursorOf(role) {
  return CURSORS[role] || CURSORS.rest;
}

/** The CSS cursor a mode shows at rest (`null` = nothing armed). */
export function cursorForMode(mode) {
  return cursorOf(MODE_CURSORS[mode] || 'rest');
}

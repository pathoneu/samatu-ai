/**
 * Design tokens — single source of truth for values that need to be
 * accessed from both CSS (Tailwind classes) AND JavaScript (Fabric
 * stroke / fill colors, dynamic style props).
 *
 * Anything that's purely visual styling (paddings, fonts, breakpoints)
 * lives in Tailwind classes inline — we do NOT duplicate it here to
 * avoid a two-source-of-truth problem.
 *
 * Use case: AnnotationCanvas needs JS access to the polygon fill color
 * to pass to fabric.Polygon({fill: ...}). It can't read Tailwind
 * variables at runtime, so colors live here as raw strings, the same
 * values Tailwind's slate / blue palette uses.
 */

export const COLORS = {
  // Polygon + measurement colors (used by Fabric in AnnotationCanvas).
  // Match Tailwind blue-500 / blue-600 / red-500 / green-500 palette so
  // the colors look consistent with Tailwind-styled UI.
  roomPolygon:        '#3b82f6',          // blue-500 — default polygon stroke
  roomPolygonFill:    'rgba(42, 111, 181, 0.08)',
  roomSelected:       '#2a6fb5',
  roomSelectedFill:   'rgba(42, 111, 181, 0.30)',
  roomHoverFill:      'rgba(42, 111, 181, 0.18)',
  measureLine:        '#2a6fb5',
  measureLineSelect:  '#1d4ed8',
  measureHalo:        '#facc15',          // yellow-400 — selected-measurement halo
  snapIndicator:      '#16a34a',          // green-600 — snap-target ring
  draftLine:          '#16a34a',
  calibrationLine:    '#f59e0b',          // amber-500 — in-progress calibration
};

// Animations — keyframes are defined in src/index.css; this is just a
// label so callers can reference 'animate-pulse-soft' etc. without
// re-typing the durations.
export const ANIM = {
  pulse:      'samatu-pulse 1.5s ease-in-out infinite',
  fadeIn:     'samatu-fadein 200ms ease forwards',
  slideRight: 'samatu-slidein-right 200ms ease forwards',
};

/**
 * overlayTokens.js — the ONE drawing language of the viewer (Pathon v3, W1-C; design 2026-10-18 §6,
 * founder decision 2).
 *
 *   solid  = read from the drawing, or confirmed by the user;
 *   dashed = estimated or proposed — nothing else, and always the one pattern DASH;
 *   red    = an error — nothing else;
 *   selection = a heavy neutral outline (SELECTED_STROKE_PX) plus a label;
 *   rooms share one neutral tint — the room type is written in the label, never coded by hue;
 *   meaning never rides on colour alone: every kind carries a sentence (hover title, legend row).
 *
 * Colours are the --ov-* tokens in src/index.css (the single place to restyle from); this module
 * only names them, fixes the line widths, alphas and the dash, and says each kind in Lithuanian.
 * SVG paint goes through `style` (paint()), which resolves var() in every browser.
 */

export const OV_KINDS = [
  'read', 'estimated', 'proposed', 'user', 'opening', 'wall',
  'selected', 'editing', 'error', 'zone-fill', 'label-bg', 'label-fg',
];

/** `hsl(var(--ov-<kind>))`, or with an alpha `hsl(var(--ov-<kind>) / a)`. */
export function ov(kind, alpha = null) {
  if (!OV_KINDS.includes(kind)) throw new Error(`unknown overlay kind: ${kind}`);
  return alpha == null ? `hsl(var(--ov-${kind}))` : `hsl(var(--ov-${kind}) / ${alpha})`;
}

export const STROKE_PX = 2;
export const SELECTED_STROKE_PX = 3;
export const FILL_ALPHA = 0.16;
export const FILL_ALPHA_HOVER = 0.24;
/** The only dash on the sheet: estimated or proposed. */
export const DASH_ESTIMATED = '6 4';
export const DASH = DASH_ESTIMATED;

/** Labels on the drawing: the app's sans (never system-ui), 12 px floor, tabular numbers. */
export const LABEL_FONT_PX = 12;
export const LABEL_FONT_FAMILY = 'var(--font-sans)';
export const LABEL_STYLE = { fontFamily: LABEL_FONT_FAMILY, fontVariantNumeric: 'tabular-nums' };
/** Rough text width at LABEL_FONT_PX in the sans (Plex Sans ≈ 0.53 em per character, tabular digits
 *  included; W0-B measured 0.45 em for lowercase prose — erring wide never clips a label). */
export function labelWidth(text, px = LABEL_FONT_PX) {
  return String(text ?? '').length * px * 0.53 + 14;
}

/** SVG paint as a style object: var() resolves here in every browser (presentation attributes vary). */
export function paint({ stroke = null, fill = null } = {}) {
  const s = {};
  if (stroke) s.stroke = stroke;
  if (fill) s.fill = fill;
  return s;
}

/**
 * The line kinds: colour token, dash, and the sentence that names the kind wherever it is drawn.
 * `solid` and `dashed` are the vocabulary; the colour only repeats what the line style already says.
 */
export const LINE_KINDS = {
  read: { stroke: 'read', dash: null, sentence: 'Perskaityta brėžinyje arba patvirtinta jūsų' },
  confirmed: { stroke: 'read', dash: null, sentence: 'Patvirtinta jūsų' },
  estimated: { stroke: 'estimated', dash: DASH, sentence: 'Apytikslė — programa įvertino, brėžinyje to tiksliai nėra' },
  proposed: { stroke: 'proposed', dash: DASH, sentence: 'Siūloma — dar neišsaugota, laukia jūsų sprendimo' },
  error: { stroke: 'error', dash: null, sentence: 'Klaida — taip išsaugoti negalima' },
};

export function lineStyle(kind) {
  const k = LINE_KINDS[kind] || LINE_KINDS.estimated;
  return { stroke: ov(k.stroke), dash: k.dash, sentence: k.sentence };
}

// Outline sources (polygon_source) a person drew or fixed, and the ones read off a vector PDF's wall
// lines (the same groups lib/quantitiesTree.geometrySource and lib/detectRun use). Anything else that
// still has a polygon — the browser flood fill, a box — is an estimate.
const USER_SOURCES = new Set(['corrected', 'manual']);
const WALL_SOURCES = new Set(['vektoriniai_konturai', 'sienu_konturas']);

/** How a room's outline is drawn: 'confirmed' | 'read' (solid) or 'estimated' (dashed). */
export function outlineKindOf(room) {
  const src = String(room?.polygon_source || '');
  if (USER_SOURCES.has(src)) return 'confirmed';
  if (WALL_SOURCES.has(src)) return 'read';
  return 'estimated';
}

/** The sentence for a room outline of that kind (hover title, chip line, legend). */
export const OUTLINE_SENTENCE = {
  confirmed: 'kontūras patvirtintas jūsų',
  read: 'kontūras perskaitytas pagal brėžinio sienas',
  estimated: 'kontūras apytikslis — patikrinkite',
  marker: 'pažymėtas tik patalpos numeris, kontūro nėra',
};

/**
 * Legend rows per layer — what a layer draws, named once where the layer is (OverlayLegend).
 * swatch: 'line' (stroke + dash), 'fill' (tinted box), 'bar' (thick line), 'ring' (circle).
 */
export const LEGENDS = {
  zones: [
    { key: 'zone-read', swatch: 'line', stroke: 'read', dash: null, fill: 'zone-fill', label: 'Kontūras perskaitytas arba patvirtintas' },
    { key: 'zone-estimated', swatch: 'line', stroke: 'estimated', dash: DASH, fill: 'zone-fill', label: 'Kontūras apytikslis' },
    { key: 'zone-marker', swatch: 'ring', stroke: 'selected', dash: null, label: 'Tik numeris, be kontūro' },
  ],
  walls: [
    { key: 'wall', swatch: 'fill', stroke: 'wall', fill: 'wall', label: 'Sienos, kurias programa perskaitė' },
    { key: 'outline-read', swatch: 'line', stroke: 'read', dash: null, label: 'Kontūras pagal sienas arba patvirtintas' },
    { key: 'outline-estimated', swatch: 'line', stroke: 'estimated', dash: DASH, label: 'Kontūras apytikslis' },
    { key: 'opening', swatch: 'bar', stroke: 'opening', dash: null, label: 'Anga: D — durys, L — langas; spustelėkite angą — keisti' },
  ],
};

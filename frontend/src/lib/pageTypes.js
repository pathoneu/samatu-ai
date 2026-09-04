// pageTypes — central registry for the `puslapiai[]` enum emitted by the
// extractor (see backend/extractor/prompt.py OUTPUT_SCHEMA).
//
// Used by the PdfViewer thumbnail sidebar (Phase 14 / QW02 auto-count-style page
// classification) and by the Brėžinio struktūra card.

import {
  FileText, Layers, Square, Building2, BookOpen, Zap, Droplets,
  HelpCircle, ChevronRight, Map, DoorOpen, Brush, Frame, EyeOff,
} from 'lucide-react';

// LT user-facing labels per enum value.
export const PAGE_TYPE_LABELS = {
  floor_plan:           'Aukšto planas',
  wall_elevation:       'Sienų išklotinė',
  ceiling_plan:         'Lubų planas',
  section:              'Pjūvis',
  eksplikacija:         'Eksplikacija',
  door_window_schedule: 'Durų/langų specifikacija',
  finish_schedule:      'Apdailų specifikacija',
  site_plan:            'Sklypo planas',
  facade:               'Fasadas',
  structural:           'Konstrukcijos',
  electrical:           'Elektros planas',
  plumbing:             'Santechnikos planas',
  specification:        'Specifikacija',
  title_page:           'Tituliniai',
  unknown:              'Nežinomas',
  non_relevant:         'Nereikalingas',
};

// Color used for the dot beside each thumbnail label.
// Tones mirror PageStructureCard's prior palette where available.
export const PAGE_TYPE_COLOR = {
  floor_plan:           '#2563eb', // mėlyna
  wall_elevation:       '#d97706', // gintaras
  ceiling_plan:         '#9333ea', // violetinė
  section:              '#57534e', // taupe
  eksplikacija:         '#0d9488', // teal
  door_window_schedule: '#dc2626', // red
  finish_schedule:      '#db2777', // pink
  site_plan:            '#65a30d', // lime
  facade:               '#16a34a', // žalia
  structural:           '#7c3aed', // purple
  electrical:           '#ca8a04', // amber
  plumbing:             '#0891b2', // ciano
  specification:        '#4f46e5', // indigo
  title_page:           '#78716c', // pilkstvo
  unknown:              '#a8a29e',
  non_relevant:         '#525252',
};

export const PAGE_TYPE_ICON = {
  floor_plan:           FileText,
  wall_elevation:       Square,
  ceiling_plan:         Layers,
  section:              ChevronRight,
  eksplikacija:         BookOpen,
  door_window_schedule: DoorOpen,
  finish_schedule:      Brush,
  site_plan:            Map,
  facade:               Building2,
  structural:           Frame,
  electrical:           Zap,
  plumbing:             Droplets,
  specification:        BookOpen,
  title_page:           FileText,
  unknown:              HelpCircle,
  non_relevant:         EyeOff,
};

// Drawing types that a complete interior project SHOULD include.
// If any of these are missing from puslapiai[], the sidebar shows a warning.
export const EXPECTED_INTERIOR_TYPES = [
  'floor_plan',
  'wall_elevation',
  'ceiling_plan',
];

export function pageTypeLabel(tipas) {
  return PAGE_TYPE_LABELS[tipas] || PAGE_TYPE_LABELS.unknown;
}

export function pageTypeColor(tipas) {
  return PAGE_TYPE_COLOR[tipas] || PAGE_TYPE_COLOR.unknown;
}

// Build a {nr: {label, type, confidence}} dict consumed by the PdfViewer
// thumbnail sidebar. Tolerates either the new puslapiai[] shape or the old
// v8_pages[] shape (for legacy projects sitting in localStorage).
export function buildPageMetaDict(project) {
  if (!project) return {};
  const dict = {};
  const pus = Array.isArray(project.puslapiai) ? project.puslapiai : null;
  if (pus) {
    for (const p of pus) {
      if (!p?.nr) continue;
      dict[p.nr] = {
        label: p.pavadinimas || pageTypeLabel(p.tipas),
        type: p.tipas || 'unknown',
        confidence: p.confidence || 'medium',
        pastabos: p.pastabos || '',
      };
    }
    return dict;
  }
  const v8 = Array.isArray(project.v8_pages) ? project.v8_pages : [];
  for (const p of v8) {
    if (!p?.page) continue;
    dict[p.page] = {
      label: p.label,
      type: p.type || 'unknown',
      confidence: p.confidence || 'medium',
    };
  }
  return dict;
}

// Returns expected types that are not present in puslapiai[].
// Empty array if either everything is covered or puslapiai[] is missing
// (don't pester users on legacy projects without the field).
export function missingInteriorTypes(puslapiai) {
  if (!Array.isArray(puslapiai) || puslapiai.length === 0) return [];
  const present = new Set(puslapiai.map(p => p?.tipas).filter(Boolean));
  return EXPECTED_INTERIOR_TYPES.filter(t => !present.has(t));
}

// ── Where the drawing should OPEN ────────────────────────────────────────────

// The page types a contractor means by „brėžinys". A cover render, a
// specification table and a site plan are none of them.
const PLAN_TYPES = ['floor_plan', 'ceiling_plan', 'wall_elevation', 'section'];

/**
 * The page the viewer should open on — the first PLAN, never the cover.
 *
 * Measured on the 11-room dev project: page 1 is a marketing render of a
 * kitchen, the plan starts on page 2, and the scale on page 1 reads
 * „nekalibruotas" while page 2 auto-seeds „~1:109". Landing on the cover asks
 * a 52-year-old contractor to work out that the app has opened the wrong page
 * before he has done anything at all.
 *
 * Order of preference: a classified plan page → the page the eksplikacija was
 * read from → the first page any room says it lives on → page 1. Every step is
 * a fact already stored on the project; nothing new is computed.
 *
 * @param {object} project
 * @returns {number} 1-based page number, always ≥ 1
 */
export function firstPlanPage(project) {
  const pages = Array.isArray(project?.puslapiai) ? project.puslapiai
    : Array.isArray(project?.v8_pages) ? project.v8_pages : [];
  const numbered = pages
    .map((p) => ({ nr: Number(p?.nr ?? p?.page ?? p?.puslapio_nr), tipas: p?.tipas || p?.type }))
    .filter((p) => Number.isFinite(p.nr) && p.nr >= 1);

  for (const wanted of PLAN_TYPES) {
    const hit = numbered.filter((p) => p.tipas === wanted).sort((a, b) => a.nr - b.nr)[0];
    if (hit) return hit.nr;
  }

  const eks = Number(project?._eksplikacija?.eksplikacija_source_page
    ?? project?.eksplikacija_source_page);
  if (Number.isFinite(eks) && eks >= 1) return eks;

  const rooms = project?.v8_rooms || project?.patalpos || [];
  const roomPages = rooms
    .map((r) => Number(r?.puslapio_nr ?? r?.page_nr))
    .filter((n) => Number.isFinite(n) && n >= 1);
  if (roomPages.length) return Math.min(...roomPages);

  return 1;
}

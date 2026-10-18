// The viewer's keyboard and mouse shortcuts — ONE table (2026-10-16, Togal analysis §11).
//
// Everything that names a shortcut reads it from here: ViewerHotkeys matches key
// events through matchViewerHotkey(), the toolbar titles and status-bar hints are
// built with keyText() / hintText(), and the „?" guide (ShortcutsGuide.jsx) plus
// its printable PDF list SHORTCUT_GROUPS × VIEWER_SHORTCUTS. A key changed here
// changes everywhere at once, so the guide cannot drift from what is bound.
//
// `bound` says who listens for the entry:
//   'hotkeys' — ViewerHotkeys in TakeoffViewer.jsx (tested: every id has a handler)
//   'draft'   — MeasureLayer, while a measurement is being drawn
//   'outline' — TakeoffViewer's outline-edit listener
//   'search'  — the toolbar search box
//   'mouse'   — a pointer gesture, listed for the guide only
//
// A combo: { keys: [KeyboardEvent.key values, first one is shown], mod?: 'primary'
// (⌘ on Mac, Ctrl elsewhere — both are accepted), shift?: true | false (absent =
// either) }. Mouse entries carry `display` instead: a string or { mac, other }.

export const SHORTCUT_GROUPS = [
  { id: 'navigation', title: 'Naršymas' },
  { id: 'measure', title: 'Matavimai' },
  { id: 'outline', title: 'Kontūro redagavimas' },
  { id: 'selection', title: 'Žymėjimas ir istorija' },
  { id: 'layers', title: 'Sluoksniai' },
];

export const VIEWER_SHORTCUTS = [
  // ── Naršymas
  { id: 'zoomIn', group: 'navigation', bound: 'hotkeys', label: 'Artinti', combos: [{ keys: ['+', '='] }] },
  { id: 'zoomOut', group: 'navigation', bound: 'hotkeys', label: 'Tolinti', combos: [{ keys: ['-'] }] },
  { id: 'fitPage', group: 'navigation', bound: 'hotkeys', label: 'Sutalpinti visą puslapį', combos: [{ keys: ['0'] }] },
  { id: 'fitWidth', group: 'navigation', bound: 'hotkeys', label: 'Sutalpinti per visą plotį', combos: [{ keys: ['1'] }] },
  { id: 'nextPage', group: 'navigation', bound: 'hotkeys', label: 'Kitas puslapis', combos: [{ keys: ['PageDown'] }, { keys: [']'] }] },
  { id: 'prevPage', group: 'navigation', bound: 'hotkeys', label: 'Ankstesnis puslapis', combos: [{ keys: ['PageUp'] }, { keys: ['['] }] },
  { id: 'toggleThumbs', group: 'navigation', bound: 'hotkeys', label: 'Rodyti arba slėpti puslapių juostą', combos: [{ keys: ['t', 'T'] }] },
  { id: 'openSearch', group: 'navigation', bound: 'hotkeys', label: 'Ieškoti teksto brėžinyje', combos: [{ keys: ['f', 'F'], mod: 'primary' }, { keys: ['/'] }, { keys: ['f', 'F'] }] },
  { id: 'searchNext', group: 'navigation', bound: 'search', label: 'Paieškoje — kitas rezultatas', combos: [{ keys: ['Enter'] }] },
  { id: 'searchPrev', group: 'navigation', bound: 'search', label: 'Paieškoje — ankstesnis rezultatas', combos: [{ keys: ['Enter'], shift: true }] },
  { id: 'print', group: 'navigation', bound: 'hotkeys', label: 'Spausdinti brėžinį', combos: [{ keys: ['p', 'P'], mod: 'primary' }] },
  { id: 'wheelZoom', group: 'navigation', bound: 'mouse', label: 'Artinti ties žymekliu', display: { mac: '⌘ + ratukas arba suspausti du pirštus', other: 'Ctrl + pelės ratukas' } },
  { id: 'openGuide', group: 'navigation', bound: 'hotkeys', label: 'Šis sparčiųjų klavišų sąrašas', combos: [{ keys: ['?'] }] },

  // ── Matavimai
  { id: 'toolDistance', group: 'measure', bound: 'hotkeys', label: 'Atstumas — matuoti metrais', combos: [{ keys: ['2'] }] },
  { id: 'toolArea', group: 'measure', bound: 'hotkeys', label: 'Plotas — matuoti m²', combos: [{ keys: ['3'] }] },
  { id: 'toolPerimeter', group: 'measure', bound: 'hotkeys', label: 'Perimetras — kontūro ilgis metrais', combos: [{ keys: ['4'] }] },
  { id: 'toolCount', group: 'measure', bound: 'hotkeys', label: 'Kiekis — skaičiuoti vienetus', combos: [{ keys: ['6'] }] },
  { id: 'draftFinish', group: 'measure', bound: 'draft', label: 'Baigti braižomą matavimą', hint: 'baigti', combos: [{ keys: ['Enter'] }] },
  { id: 'draftFinishMouse', group: 'measure', bound: 'mouse', label: 'Baigti braižomą matavimą', display: 'Dukart spustelėti' },
  { id: 'draftUndoPoint', group: 'measure', bound: 'draft', label: 'Atšaukti paskutinį nubrėžtą tašką', hint: 'atgal', combos: [{ keys: ['z', 'Z'] }, { keys: ['Backspace'] }] },
  { id: 'draftCancel', group: 'measure', bound: 'draft', label: 'Atsisakyti braižomo matavimo', hint: 'atšaukti', combos: [{ keys: ['Escape'] }] },
  { id: 'orthoLock', group: 'measure', bound: 'mouse', label: 'Brėžti tik horizontaliai, vertikaliai arba 45° kampu', display: 'Laikyti Shift' },
  { id: 'countRemove', group: 'measure', bound: 'mouse', label: 'Kiekio įrankiu — pašalinti tą žymę', display: 'Spustelėti ant žymės' },

  // ── Kontūro redagavimas
  { id: 'outlineDrag', group: 'outline', bound: 'mouse', label: 'Perkelti viršūnę (prilimpa prie sienų)', display: 'Tempti kampą' },
  { id: 'outlineInsert', group: 'outline', bound: 'mouse', label: 'Pridėti viršūnę', display: 'Spustelėti vidurio tašką' },
  { id: 'outlineRemove', group: 'outline', bound: 'mouse', label: 'Pašalinti viršūnę', display: 'Dukart spustelėti kampą' },
  { id: 'outlineUndo', group: 'outline', bound: 'outline', label: 'Atšaukti paskutinį viršūnės pakeitimą', hint: 'atgal', combos: [{ keys: ['z', 'Z'] }] },
  { id: 'outlineSave', group: 'outline', bound: 'outline', label: 'Išsaugoti kontūrą', hint: 'išsaugoti', combos: [{ keys: ['Enter'] }] },
  { id: 'outlineCancel', group: 'outline', bound: 'outline', label: 'Atšaukti redagavimą (niekas neišsaugoma)', hint: 'atšaukti', combos: [{ keys: ['Escape'] }] },

  // ── Žymėjimas ir istorija
  { id: 'deleteSelected', group: 'selection', bound: 'hotkeys', label: 'Ištrinti pažymėtus matavimus („Žymėti" arba „Laso" įrankiu)', hint: 'ištrinti pažymėtus', combos: [{ keys: ['Delete'] }, { keys: ['Backspace'] }] },
  { id: 'toolLasso', group: 'selection', bound: 'hotkeys', label: 'Laso — apvesti kelis matavimus ir žymes', combos: [{ keys: ['l', 'L'] }] },
  { id: 'lassoAdd', group: 'selection', bound: 'mouse', label: 'Laso — pridėti prie pažymėtų', display: 'Laikyti Shift apvedant' },
  { id: 'contextMenu', group: 'selection', bound: 'mouse', label: 'Matavimo meniu: pervadinti, keisti tipą, ištrinti, rodyti sąraše; su laso — veiksmai su visais pažymėtais', display: 'Dešinysis pelės klavišas ant matavimo' },
  { id: 'undo', group: 'selection', bound: 'hotkeys', label: 'Atšaukti paskutinį veiksmą su matavimais ir žymėmis', combos: [{ keys: ['z', 'Z'], mod: 'primary', shift: false }] },
  { id: 'redo', group: 'selection', bound: 'hotkeys', label: 'Grąžinti atšauktą veiksmą', combos: [{ keys: ['z', 'Z'], mod: 'primary', shift: true }, { keys: ['y', 'Y'], mod: 'primary' }] },
  { id: 'escape', group: 'selection', bound: 'hotkeys', label: 'Uždaryti paiešką, išjungti įrankį, atsisakyti patalpos', combos: [{ keys: ['Escape'] }] },

  // ── Sluoksniai
  { id: 'toggleZoneFills', group: 'layers', bound: 'hotkeys', label: 'Nuspalvinti patalpas arba palikti brėžinį švarų', combos: [{ keys: ['u', 'U'] }] },
  { id: 'toggleWallsLayer', group: 'layers', bound: 'hotkeys', label: 'Sienų sluoksnis: sienos, kontūrai ir angos iš PDF', combos: [{ keys: ['s', 'S'] }] },
];

const BY_ID = new Map(VIEWER_SHORTCUTS.map((s) => [s.id, s]));

export function shortcutById(id) {
  return BY_ID.get(id) || null;
}

export function isMacPlatform(nav = (typeof navigator !== 'undefined' ? navigator : null)) {
  const p = nav?.userAgentData?.platform || nav?.platform || nav?.userAgent || '';
  return /mac|iphone|ipad|ipod/i.test(p);
}

const KEY_NAMES = {
  PageDown: 'PgDn', PageUp: 'PgUp', Escape: 'Esc', '-': '−', ' ': 'Tarpas',
};

function keyName(k) {
  if (KEY_NAMES[k]) return KEY_NAMES[k];
  return k.length === 1 ? k.toUpperCase() : k;
}

/** One combo as the person reads it: „Ctrl + Shift + Z" / „⌘ ⇧ Z". */
export function formatCombo(combo, { mac = isMacPlatform() } = {}) {
  const parts = [];
  if (combo.mod === 'primary') parts.push(mac ? '⌘' : 'Ctrl');
  if (combo.shift === true) parts.push(mac ? '⇧' : 'Shift');
  parts.push(keyName(combo.keys[0]));
  return parts.join(mac ? ' ' : ' + ');
}

/** Every way to trigger the entry, for the guide: ['Ctrl + F', '/', 'F'] or the mouse text. */
export function displayKeys(entry, { mac = isMacPlatform() } = {}) {
  if (!entry) return [];
  if (entry.display) {
    return [typeof entry.display === 'string' ? entry.display : (mac ? entry.display.mac : entry.display.other)];
  }
  return (entry.combos || []).map((c) => formatCombo(c, { mac }));
}

/** The shortest key text for a title: „(2)", „Ctrl + Z". Alternatives joined with „ / ". */
export function keyText(id, { mac = isMacPlatform(), all = false } = {}) {
  const keys = displayKeys(shortcutById(id), { mac });
  return all ? keys.join(' / ') : (keys[0] || '');
}

/** A button title with its key: „Tolinti (−)". Unknown id → the title alone. */
export function withKey(title, id, opts) {
  const k = keyText(id, opts);
  return k ? `${title} (${k})` : title;
}

/** Status-bar hint pieces: „Z — atgal · Enter — išsaugoti · Esc — atšaukti". */
export function hintText(ids, { mac = isMacPlatform() } = {}) {
  return ids
    .map((id) => {
      const e = shortcutById(id);
      if (!e) return null;
      return `${keyText(id, { mac, all: true })} — ${e.hint || e.label.toLowerCase()}`;
    })
    .filter(Boolean)
    .join(' · ');
}

function comboMatches(combo, e) {
  if (!combo.keys.includes(e.key)) return false;
  const primary = !!(e.metaKey || e.ctrlKey);
  if (combo.mod === 'primary') {
    if (!primary || e.altKey) return false;
  } else if (primary) {
    return false;
  }
  if (combo.shift === true && !e.shiftKey) return false;
  if (combo.shift === false && e.shiftKey) return false;
  return true;
}

/**
 * The ViewerHotkeys entry a key event triggers, or null. Only `bound: 'hotkeys'`
 * entries take part; the first match in table order wins (undo is listed before
 * redo, and they differ by Shift).
 */
export function matchViewerHotkey(e) {
  if (!e || typeof e.key !== 'string') return null;
  for (const s of VIEWER_SHORTCUTS) {
    if (s.bound !== 'hotkeys') continue;
    if ((s.combos || []).some((c) => comboMatches(c, e))) return s.id;
  }
  return null;
}

/** The guide's rows: [{ group, title, items: [{ id, label, keys: [..] }] }]. */
export function shortcutGuideRows({ mac = isMacPlatform() } = {}) {
  return SHORTCUT_GROUPS.map((g) => ({
    group: g.id,
    title: g.title,
    items: VIEWER_SHORTCUTS.filter((s) => s.group === g.id).map((s) => ({
      id: s.id, label: s.label, keys: displayKeys(s, { mac }), mouse: !!s.display,
    })),
  }));
}

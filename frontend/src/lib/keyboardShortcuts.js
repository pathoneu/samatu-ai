// frontend/src/lib/keyboardShortcuts.js
/**
 * Sprint 2: keyboard shortcuts for gesture tools.
 *
 * Spec §5.4: V=pan, 1..5=tool, Esc=cancel. Documented in tooltips, never
 * primary UI. Skip when target is an input / textarea / contenteditable.
 */
const NUMERIC_TOOL = { 1: 'g1', 2: 'g2', 3: 'g3', 4: 'g4', 5: 'g5' };

export function keyToTool(key, target) {
  if (target) {
    const tag = target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return null;
    if (target.isContentEditable) return null;
  }
  if (key === 'v' || key === 'V') return 'pan';
  if (key === 'Escape') return 'pan';
  if (NUMERIC_TOOL[key]) return NUMERIC_TOOL[key];
  return null;
}

export function attachShortcuts({ setCurrentTool, win = window }) {
  const handler = (e) => {
    const tool = keyToTool(e.key, e.target);
    if (tool) setCurrentTool(tool);
  };
  win.addEventListener('keydown', handler);
  return () => win.removeEventListener('keydown', handler);
}

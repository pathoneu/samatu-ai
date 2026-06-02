/**
 * useCommandStack — generic undo/redo with optional Ctrl+Z / Ctrl+Y / Esc
 * keyboard bindings.
 *
 * Each command is `{ do: () => void, undo: () => void, label?: string }`.
 * Push a command after the user action has applied so undo() reverts it.
 *
 * Returns `{ push, undo, redo, canUndo, canRedo, clear, depth, redoDepth }`.
 *
 * If `bindKeys` is true (default), Ctrl/Cmd+Z undoes and Ctrl/Cmd+Y
 * (or Shift+Ctrl/Cmd+Z) redoes. Escape does nothing here — callers
 * usually pair it with a separate cancelDraft handler.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export default function useCommandStack({ bindKeys = true } = {}) {
  // Two stacks; React state for the depth counters so consumers can
  // disable buttons based on canUndo / canRedo.
  const undoStack = useRef([]);
  const redoStack = useRef([]);
  const [depth, setDepth] = useState(0);
  const [redoDepth, setRedoDepth] = useState(0);

  const refresh = useCallback(() => {
    setDepth(undoStack.current.length);
    setRedoDepth(redoStack.current.length);
  }, []);

  const push = useCallback((cmd) => {
    if (!cmd || typeof cmd.undo !== 'function') return;
    undoStack.current.push(cmd);
    redoStack.current.length = 0;  // any new action clears redo
    refresh();
  }, [refresh]);

  const undo = useCallback(() => {
    const cmd = undoStack.current.pop();
    if (!cmd) return false;
    try {
      cmd.undo();
      redoStack.current.push(cmd);
    } catch (err) {
      // Swallow but log — a bad command shouldn't crash the viewer.
      // The user can re-do their work; better than a white screen.
      // eslint-disable-next-line no-console
      console.error('[useCommandStack] undo threw', err);
    }
    refresh();
    return true;
  }, [refresh]);

  const redo = useCallback(() => {
    const cmd = redoStack.current.pop();
    if (!cmd) return false;
    try {
      (cmd.do || (() => {}))();
      undoStack.current.push(cmd);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[useCommandStack] redo threw', err);
    }
    refresh();
    return true;
  }, [refresh]);

  const clear = useCallback(() => {
    undoStack.current.length = 0;
    redoStack.current.length = 0;
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!bindKeys) return undefined;
    const onKey = (e) => {
      // Don't hijack typing in inputs/textareas
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) {
        return;
      }
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const k = e.key.toLowerCase();
      // Ctrl+Z undo, Ctrl+Shift+Z OR Ctrl+Y redo
      if (k === 'z' && !e.shiftKey) {
        if (undoStack.current.length > 0) {
          e.preventDefault();
          undo();
        }
      } else if ((k === 'z' && e.shiftKey) || k === 'y') {
        if (redoStack.current.length > 0) {
          e.preventDefault();
          redo();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [bindKeys, undo, redo]);

  return {
    push,
    undo,
    redo,
    clear,
    canUndo: depth > 0,
    canRedo: redoDepth > 0,
    depth,
    redoDepth,
  };
}

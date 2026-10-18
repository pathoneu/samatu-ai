/**
 * useOutlineTool — the state of the viewer's outline tools (2026-10-16, Togal analysis §6):
 * „Padalyti" (split), „Sujungti" (merge), „Atimti" (subtract). One tool at a time, bound to the
 * focused room's outline; nothing is saved until „Išsaugoti". Every step snapshots the previous
 * state, so Z / „Atgal" walks back through the clicks.
 *
 * The state is plain data in DISPLAY-frame page fractions (the frame `polygon_pct` lives in):
 *   {mode, nr, page, ring, holes, tableAreaM2, history,
 *    split:    a, b, parts: [{ring, holes}], keep, otherNr
 *    merge:    targetNr, union: {ring, holes}, refused
 *    subtract: shape ('rect' | 'poly'), draft, dirty}
 * OutlineToolLayer computes the geometry (it knows the sheet's size and scale) and writes results
 * back through `change`; OutlineToolPanel reads them and offers the choices and the save.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { roomPageOf } from '@/lib/roomZones';
import { holeHasWalls, roomHoleWalls } from '@/lib/outlineTools';

export { holeHasWalls, roomHoleWalls };

export const OUTLINE_TOOL_MODES = ['split', 'merge', 'subtract'];

const strip = (t) => {
  if (!t) return t;
  const { history: _h, ...rest } = t;
  return rest;
};

function roomRing(r) {
  return Array.isArray(r?.polygon_pct) && r.polygon_pct.length >= 3
    ? r.polygon_pct.map(([x, y]) => [Number(x), Number(y)])
    : null;
}

export function roomHoles(r) {
  return Array.isArray(r?.polygon_holes_pct)
    ? r.polygon_holes_pct.filter((h) => Array.isArray(h) && h.length >= 3).map((h) => h.map(([x, y]) => [Number(x), Number(y)]))
    : [];
}

/** The operation the save sends (lib/outlineToolSave), or null while the tool has nothing to save yet. */
export function outlineToolOperation(tool) {
  const op = operationOf(tool);
  if (!op) return null;
  const walls = (holes) => (holes || []).map((h) => holeHasWalls(h, tool.holeWalls));
  return op.other
    ? { ...op, holesWalls: walls(op.holes), other: { ...op.other, holesWalls: walls(op.other.holes) } }
    : { ...op, holesWalls: walls(op.holes) };
}

function operationOf(tool) {
  if (!tool) return null;
  if (tool.mode === 'split') {
    if (!tool.parts || tool.keep == null) return null;
    const kept = tool.parts[tool.keep];
    const other = tool.parts[1 - tool.keep];
    const base = { nr: tool.nr, page: tool.page, polygon: kept.ring, holes: kept.holes };
    return tool.otherNr
      ? { kind: 'split', ...base, other: { nr: tool.otherNr, polygon: other.ring, holes: other.holes } }
      : { kind: 'set', ...base };
  }
  if (tool.mode === 'merge') {
    if (!tool.union || !tool.targetNr) return null;
    return { kind: 'merge', keptNr: tool.nr, goneNr: tool.targetNr, page: tool.page, polygon: tool.union.ring, holes: tool.union.holes };
  }
  if (tool.mode === 'subtract') {
    if (!tool.dirty) return null;
    return { kind: 'set', nr: tool.nr, page: tool.page, polygon: tool.ring, holes: tool.holes };
  }
  return null;
}

export default function useOutlineTool({ rooms, focusedRoom, onSave, onBeforeStart }) {
  const [tool, setTool] = useState(null);
  const [saving, setSaving] = useState(false);

  const start = useCallback((mode) => {
    const r = focusedRoom && (rooms || []).find((x) => String(x?.nr) === String(focusedRoom.nr));
    const ring = roomRing(r);
    if (!ring) {
      toast.info('Ši patalpa dar neturi kontūro — pirmiausia „Kontūras paspaudus"');
      return;
    }
    onBeforeStart?.();
    setTool({
      mode,
      nr: String(r.nr),
      page: roomPageOf(r),
      ring,
      holes: roomHoles(r),
      holeWalls: roomHoleWalls(r),
      tableAreaM2: Number(r.plotas_m2) > 0 ? Number(r.plotas_m2) : null,
      history: [],
      ...(mode === 'subtract' ? { shape: 'rect', draft: [], dirty: false } : {}),
    });
  }, [focusedRoom, rooms, onBeforeStart]);

  const cancel = useCallback(() => setTool(null), []);

  /** Apply `update(cur) → next`; `snapshot` keeps the previous state for „Atgal". */
  const change = useCallback((update, { snapshot = true } = {}) => setTool((cur) => {
    if (!cur) return cur;
    const next = typeof update === 'function' ? update(cur) : { ...cur, ...update };
    if (!next || next === cur) return cur;
    return snapshot ? { ...next, history: [...(cur.history || []).slice(-49), strip(cur)] } : { ...next, history: cur.history };
  }), []);

  const undo = useCallback(() => setTool((cur) => {
    if (!cur?.history?.length) return cur;
    const prev = cur.history[cur.history.length - 1];
    return { ...prev, history: cur.history.slice(0, -1) };
  }), []);

  const toolRef = useRef(tool);
  useEffect(() => { toolRef.current = tool; });
  const save = useCallback(async () => {
    const t = toolRef.current;
    const op = outlineToolOperation(t);
    if (!op || !onSave) return;
    setSaving(true);
    try {
      const saved = await onSave(op);
      // „Atšaukti" for 10 s (Pathon v3 W1-D, D3): the host PUTs the rooms' previous keys back (both rooms of a
      // merge or a split, the holes of a subtract).
      const undo = typeof saved?.undo === 'function' ? saved.undo : null;
      const what = {
        split: op.kind === 'split' ? `Patalpa ${op.nr} padalyta — kita dalis priskirta patalpai ${op.other.nr}` : `Patalpa ${op.nr} padalyta — kita dalis neįtraukta`,
        merge: `Patalpa ${op.goneNr} prijungta prie ${op.keptNr} — abiejų plotai ir angos skaičiuojami patalpoje ${op.keptNr}`,
        subtract: `Patalpos ${op.nr} kontūras išsaugotas su ${op.holes.length} išpjov${op.holes.length === 1 ? 'a' : 'omis'}`,
      }[t.mode];
      toast.success(what, {
        description: 'Sienos perskaitytos iš naujo, kiekiai perskaičiuojami.',
        ...(undo ? { duration: 10_000, action: { label: 'Atšaukti', onClick: () => { undo(); } } } : {}),
      });
      setTool(null);
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko išsaugoti kontūro');
    } finally {
      setSaving(false);
    }
  }, [onSave]);

  // The tool is bound to the focused room: focus moving elsewhere abandons it (nothing was saved).
  const focusedNr = focusedRoom?.nr ?? null;
  useEffect(() => { setTool(null); }, [focusedNr]);

  return { tool, saving, start, cancel, change, undo, save, canSave: !!outlineToolOperation(tool) };
}

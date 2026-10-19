/**
 * useMeasureRows — putting a measurement on a sąmata row, from any surface (Pathon v3 W4-A M2): a drop on a
 * Kiekiai or Sąmata row, „Į eilutę…" (MeasureRowPicker), the „iš matavimų" chip (switch how, take off).
 *
 * Every write is field-scoped onto the STORED project (getProject → linkPatch → updateProject, the same
 * contract as the viewer's measurement saves) and offers „Atšaukti" in its toast, which puts the previous link
 * back — the rows follow the link (lib/measuredRows.js), so one undo restores both. Drag state is module-level:
 * a drag starts in one panel and ends in another, and `dragover` cannot read the payload.
 */

import { useCallback, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { getProject, updateProject } from '@/lib/projectStore';
import {
  MEASURE_DRAG_TYPE, KAIP_LABELS, canLinkTo, defaultKaip, linkPatch, linksOf, measureSource, sourceText,
} from '@/lib/measuredRows';
import { ltQuantity } from '@/lib/ledger';

let dragging = null;   // the link key being dragged, while a drag is on

/** Props that make an element a drag source of one measurement (or count type) key. */
export function measureDragProps(key) {
  return {
    draggable: true,
    'data-measure-drag': key,
    onDragStart: (e) => {
      dragging = key;
      e.dataTransfer.setData(MEASURE_DRAG_TYPE, key);
      e.dataTransfer.setData('text/plain', key);
      e.dataTransfer.effectAllowed = 'link';
    },
    onDragEnd: () => { dragging = null; },
  };
}

const rowLabel = (row) => `„${row?.aprasymas || row?.pavadinimas || 'eilutė'}“`;

export function useMeasureRows(project, onProjectChange) {
  const id = project?.id;
  const [overRowId, setOverRowId] = useState(null);

  const stored = useCallback(() => getProject(id) || project, [id, project]);

  /** Write one link (null = off); returns {saved, before} — `before` is the link it replaced. */
  const write = useCallback((key, link) => {
    const base = stored();
    const before = linksOf(base).get(key) || null;
    const saved = updateProject(id, linkPatch(base, key, link));
    if (saved) onProjectChange?.(saved);
    return { saved, before };
  }, [id, stored, onProjectChange]);

  const undoTo = useCallback((key, before) => () => {
    write(key, before);
    toast.success('Atšaukta — matavimas grąžintas, kaip buvo');
  }, [write]);

  /**
   * Put `key` on `row` (`kaip` defaults to defaultKaip). Says what happened in a toast with „Atšaukti" —
   * `{quiet: true}` leaves the toast to the caller and returns `{before}` for its own Undo. False on a refusal.
   */
  const link = useCallback((key, row, kaip = null, { quiet = false } = {}) => {
    const base = stored();
    const source = measureSource(base, key);
    const check = canLinkTo(source, row);
    if (!check.ok) {
      toast.error(check.why);
      return false;
    }
    const how = kaip || defaultKaip(row);
    const prevRow = (base.darbu_sarasas || []).find((r) => r?.id === row.id) || row;
    const { saved, before } = write(key, { eilute_id: row.id, kaip: how });
    if (quiet) return { before };
    const nextRow = (saved?.darbu_sarasas || []).find((r) => r?.id === row.id) || null;
    const line = (nextRow?.matavimai || []).find((l) => l.key === key);
    const unit = prevRow.mato_vnt || prevRow.vnt || '';
    const description = line && !line.taikoma
      ? line.priezastis
      : `${KAIP_LABELS[how]}: ${ltQuantity(prevRow.kiekis, unit)} → ${ltQuantity(nextRow?.kiekis, unit)}`;
    toast.success(`${sourceText(source)} → ${rowLabel(row)}`, {
      description,
      duration: 8000,
      action: { label: 'Atšaukti', onClick: undoTo(key, before) },
    });
    return { before };
  }, [stored, write, undoTo]);

  const unlink = useCallback((key, { quiet = false } = {}) => {
    const { before } = write(key, null);
    if (!before || quiet) return;
    toast.success('Matavimas nuimtas nuo eilutės — eilutės kiekis grįžo į programos skaičių', {
      duration: 8000,
      action: { label: 'Atšaukti', onClick: undoTo(key, before) },
    });
  }, [write, undoTo]);

  const setKaip = useCallback((key, kaip) => {
    const current = linksOf(stored()).get(key);
    if (!current || current.kaip === kaip) return;
    const { before } = write(key, { ...current, kaip });
    toast.success(`${KAIP_LABELS[kaip]}`, {
      duration: 8000,
      action: { label: 'Atšaukti', onClick: undoTo(key, before) },
    });
  }, [stored, write, undoTo]);

  /** Props that make a row a drop target; `overRowId` lights the row under the drag. */
  const dropProps = useCallback((row) => ({
    'data-measure-drop': row?.id || undefined,
    onDragOver: (e) => {
      if (!row?.id || !Array.from(e.dataTransfer?.types || []).includes(MEASURE_DRAG_TYPE)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'link';
      setOverRowId((cur) => (cur === row.id ? cur : row.id));
    },
    onDragLeave: (e) => {
      if (e.currentTarget.contains(e.relatedTarget)) return;
      setOverRowId((cur) => (cur === row?.id ? null : cur));
    },
    onDrop: (e) => {
      const key = e.dataTransfer?.getData(MEASURE_DRAG_TYPE) || dragging;
      setOverRowId(null);
      dragging = null;
      if (!key || !row?.id) return;
      e.preventDefault();
      e.stopPropagation();
      link(key, row);
    },
  }), [link]);

  return useMemo(() => ({ link, unlink, setKaip, dropProps, overRowId }), [link, unlink, setKaip, dropProps, overRowId]);
}

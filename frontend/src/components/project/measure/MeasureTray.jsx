/**
 * MeasureTray — the measurements as chips above a list of rows (Kiekiai, Sąmata), so a length can be dragged
 * onto a row without leaving the list (Pathon v3 W4-A M2). Each chip says what it is and where it sits now;
 * a click opens „Į eilutę…" (the keyboard way). Folded to one line; shown only when there is something
 * measured.
 */

import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Ruler } from 'lucide-react';

import { linkStatus, measureSource, sourceText } from '@/lib/measuredRows';
import { measureDragProps } from './useMeasureRows';

const GEOMETRY = new Set(['distance', 'perimeter', 'area']);

/** Every measurement and count type a row could take, in the viewer's order. */
export function measureKeys(project) {
  const ms = Array.isArray(project?.measurements) ? project.measurements : [];
  const keys = ms.filter((m) => m?.id && GEOMETRY.has(m.kind)).map((m) => `m:${m.id}`);
  const types = [...new Set(ms.filter((m) => m?.kind === 'count' && m.typeId).map((m) => m.typeId))];
  return [...keys, ...types.map((id) => `type:${id}`)];
}

// Open by default while the chips fit in a couple of lines; a long list starts folded.
const OPEN_UP_TO = 8;

export default function MeasureTray({ project, onPickRow }) {
  const items = useMemo(() => measureKeys(project).map((key) => ({
    key, source: measureSource(project, key), status: linkStatus(project, key),
  })).filter((i) => i.source), [project]);
  const [open, setOpen] = useState(() => items.length <= OPEN_UP_TO);
  if (!items.length) return null;
  const linked = items.filter((i) => i.status?.row).length;
  return (
    <div className="shrink-0 border-b border-border/60 bg-card text-ui" data-testid="measure-tray">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full min-h-[32px] flex items-center gap-1.5 px-2.5 text-left text-foreground hover:bg-muted/50"
      >
        {open ? <ChevronDown className="w-4 h-4 text-muted-foreground" /> : <ChevronRight className="w-4 h-4 text-muted-foreground" />}
        <Ruler className="w-4 h-4 text-muted-foreground" aria-hidden />
        <span className="font-medium whitespace-nowrap shrink-0">Matavimai ({items.length})</span>
        <span className="min-w-0 text-muted-foreground truncate">
          · {linked ? `priskirta ${linked} · ` : ''}tempkite ant eilutės arba spustelėkite
        </span>
      </button>
      {open && (
        <ul className="flex flex-wrap gap-1.5 px-2.5 pb-2">
          {items.map(({ key, source, status }) => (
            <li key={key}>
              <button
                type="button"
                {...measureDragProps(key)}
                onClick={() => onPickRow?.(key)}
                className="inline-flex max-w-[18rem] items-center gap-1 rounded border border-border bg-background px-2 min-h-[32px] cursor-grab hover:bg-muted active:cursor-grabbing"
                title={status?.row
                  ? `Eilutėje „${status.row.aprasymas}“ — tempkite ant kitos arba spustelėkite, kad pakeistumėte`
                  : 'Tempkite ant eilutės arba spustelėkite ir pasirinkite eilutę'}
                data-testid="measure-chip"
              >
                <span className="truncate">{sourceText(source).replace(/^matavimas /, '')}</span>
                {status?.row && <span className="text-muted-foreground truncate">→ {status.row.aprasymas}</span>}
                {status && !status.row && <span className="text-muted-foreground">→ eilutės nebėra</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

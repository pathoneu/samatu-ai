/**
 * MeasurementsList — sidebar list of measurements with bidirectional
 * linking to the canvas.
 *
 * Click a row → onSelect(id) so Annotator can pan the canvas to that
 * measurement and trigger a pulse highlight.
 *
 * If `selectedId` is set, the matching row gets a yellow ring and we
 * auto-scroll it into view (useful when the user clicks a measurement
 * on the canvas to highlight its row).
 *
 * Props:
 *   measurements[]        — [{id, p1_pct, p2_pct, length_mm}]
 *   selectedId            — currently-highlighted measurement id (or null)
 *   onSelect(id)          — user clicked a row
 *   onDelete(id)          — user clicked the row's Trinti button
 *   onClearAll()          — user clicked the section's Išvalyti button
 */
import React, { useEffect, useRef } from 'react';
import { Ruler, Trash2 } from 'lucide-react';

export default function MeasurementsList({
  measurements,
  selectedId,
  onSelect,
  onDelete,
  onClearAll,
}) {
  const rowRefs = useRef({});

  // Bidirectional: when an external caller (canvas click) sets
  // selectedId, scroll the corresponding row into view.
  useEffect(() => {
    if (!selectedId) return;
    const row = rowRefs.current[selectedId];
    if (row && typeof row.scrollIntoView === 'function') {
      row.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedId]);

  return (
    <section className="flex-1 overflow-auto">
      <header className="flex items-center justify-between px-4 py-2 text-xs font-medium uppercase text-neutral-500">
        <span>Matavimai ({measurements.length})</span>
        {measurements.length > 0 && onClearAll && (
          <button
            type="button"
            onClick={onClearAll}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs"
          >Išvalyti</button>
        )}
      </header>
      {measurements.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-neutral-500">
          <Ruler size={28} strokeWidth={1.5} aria-hidden="true"
            className="mx-auto mb-2 text-neutral-300" />
          <div className="font-medium text-neutral-600 mb-0.5">Nėra matavimų</div>
          <div>Spustelėkite <span className="font-medium">Matuoti</span> ir brėžkite du taškus ant brėžinio</div>
        </div>
      ) : (
        <ul className="text-sm">
          {measurements.map((m, i) => {
            const isSelected = m.id === selectedId;
            return (
              <li
                key={m.id}
                ref={(el) => { rowRefs.current[m.id] = el; }}
                onClick={() => onSelect && onSelect(m.id)}
                className={`flex cursor-pointer items-center justify-between gap-2 border-b border-neutral-100 px-4 py-1.5 transition-colors ${
                  isSelected
                    ? 'bg-yellow-50 ring-2 ring-inset ring-yellow-400'
                    : 'hover:bg-neutral-50'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className="inline-block h-3 w-3 rounded-full bg-blue-600" />
                  <span className="text-neutral-500">#{i + 1}</span>
                </span>
                <span className="font-mono text-blue-700">
                  {(m.length_mm || 0).toFixed(1)} mm
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete && onDelete(m.id);
                  }}
                  className="rounded border border-neutral-300 px-1.5 py-1 text-neutral-600 hover:border-red-400 hover:text-red-600 transition-colors"
                  title="Ištrinti matavimą"
                  aria-label="Ištrinti matavimą"
                >
                  <Trash2 size={12} strokeWidth={1.75} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/**
 * RoomDetailCard — info panel for the currently-selected room.
 *
 * Shows: name + verification badge, key dimensions, per-wall AI lengths
 * with optional contractor overrides + per-wall edit buttons, and
 * confirm/correct action buttons.
 *
 * Props:
 *   room                  — room object from /room-graph (must include
 *                            nr, name, polygon_pct (nullable),
 *                            perimeter_mm, area_m2, ceiling_height_m,
 *                            walls_paintable_m2, ceiling_paintable_m2,
 *                            dazymo_plotas_m2)
 *   verificationState[]   — map nr → 'confirmed' | 'corrected' | undefined
 *   roomOverrides         — map nr → { walls: { wallId: lengthMm, ... } }
 *   scale                 — current mm-per-px scale (null disables wall edit)
 *   onConfirm(nr)         — user clicked '✓ Patvirtinti'
 *   onMarkCorrected(nr)   — user clicked '✎ Pakoregavau'
 *   onStartWallEdit(nr, wallId) — user clicked '✎ Pertaškyti' on a wall
 */
import React from 'react';

export default function RoomDetailCard({
  room,
  verificationState,
  roomOverrides,
  scale,
  onConfirm,
  onMarkCorrected,
  onStartWallEdit,
}) {
  if (!room) return null;
  const state = verificationState?.[room.nr];
  const overrides = roomOverrides?.[room.nr]?.walls || {};
  const perWallAiMm = room.polygon_pct && room.polygon_pct.length > 0
    ? (room.perimeter_mm / room.polygon_pct.length)
    : null;

  return (
    <section className="border-b border-neutral-200 bg-blue-50/40 px-4 py-3">
      <div className="mb-1 flex items-center justify-between">
        <div className="text-xs font-medium uppercase text-neutral-500">Pasirinkta patalpa</div>
        {state === 'confirmed' && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">✓ Patvirtinta</span>
        )}
        {state === 'corrected' && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">✎ Pakoreguota</span>
        )}
      </div>
      <div className="text-base font-semibold text-neutral-800">
        {room.nr} {room.name}
      </div>
      <div className="mt-1 grid grid-cols-3 gap-2 text-xs">
        <div><span className="text-neutral-500">Plotas: </span>
          <strong>{(room.area_m2 || 0).toFixed(2)} m²</strong></div>
        <div><span className="text-neutral-500">Perimetras: </span>
          <strong>{((room.perimeter_mm || 0) / 1000).toFixed(2)} m</strong></div>
        <div><span className="text-neutral-500">H: </span>
          <strong>{(room.ceiling_height_m || 0).toFixed(2)} m</strong></div>
        <div><span className="text-neutral-500">Sienos dažomos: </span>
          <strong>{(room.walls_paintable_m2 || 0).toFixed(1)} m²</strong></div>
        <div><span className="text-neutral-500">Lubos: </span>
          <strong>{(room.ceiling_paintable_m2 || 0).toFixed(1)} m²</strong></div>
        <div><span className="text-neutral-500">Σ dažymas: </span>
          <strong>{(room.dazymo_plotas_m2 || 0).toFixed(1)} m²</strong></div>
      </div>
      {room.polygon_pct && perWallAiMm !== null && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-neutral-500">Sienos</div>
          <ul className="space-y-1">
            {room.polygon_pct.map((_, idx) => {
              const wallId = `w${idx + 1}`;
              const override = overrides[wallId];
              return (
                <li key={wallId} className="flex items-center gap-2 text-xs">
                  <span className="w-8 font-mono text-neutral-500">{wallId}</span>
                  <span className="flex-1">
                    AI: {(perWallAiMm / 1000).toFixed(2)} m
                    {override !== undefined && (
                      <span className="ml-2 font-mono font-semibold text-amber-700">
                        → {(override / 1000).toFixed(2)} m
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    onClick={() => onStartWallEdit && onStartWallEdit(room.nr, wallId)}
                    disabled={!scale}
                    title={scale ? 'Pertaškyti sieną' : 'Pirmiausia kalibruokite'}
                    className="rounded border border-blue-300 bg-white px-2 py-0.5 text-blue-700 hover:border-blue-500 disabled:opacity-40"
                  >✎ Pertaškyti</button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => onConfirm && onConfirm(room.nr)}
          className="flex-1 rounded border border-emerald-500 bg-emerald-50 px-2 py-1 text-xs text-emerald-700"
        >✓ Patvirtinti</button>
        <button
          type="button"
          onClick={() => onMarkCorrected && onMarkCorrected(room.nr)}
          className="flex-1 rounded border border-amber-500 bg-amber-50 px-2 py-1 text-xs text-amber-700"
        >✎ Pakoregavau</button>
      </div>
    </section>
  );
}

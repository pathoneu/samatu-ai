/**
 * VerifyWalkthrough — guided cycle through every polygon-equipped
 * room, asking the contractor to confirm or correct each.
 *
 * Renders nothing when not active. When active, shows a floating card
 * over the canvas with the current room's summary and three actions:
 * Taip (confirm), Koreguoti (mark for manual correction), Toliau
 * (skip to next).
 *
 * On the last room, after confirm/correct the parent should set
 * walkthroughActive=false and surface the summary (X patvirtinta,
 * Y pakoreguota).
 *
 * Props:
 *   rooms[]              — rooms with polygons in walkthrough order
 *   currentIdx           — which room (0-based)
 *   verificationState    — map nr → 'confirmed'|'corrected'|undefined
 *   onConfirm(nr)        — user clicked ✓ Taip
 *   onCorrect(nr)        — user clicked ✎ Koreguoti
 *   onAdvance()          — skip to next (no verdict)
 *   onStop()             — user clicked Nutraukti
 */
import React from 'react';

export default function VerifyWalkthrough({
  rooms,
  currentIdx,
  verificationState,
  onConfirm,
  onCorrect,
  onAdvance,
  onStop,
}) {
  if (!rooms || rooms.length === 0) return null;
  const current = rooms[currentIdx];
  if (!current) return null;

  const total = rooms.length;
  const confirmed = Object.values(verificationState || {})
    .filter((v) => v === 'confirmed').length;
  const corrected = Object.values(verificationState || {})
    .filter((v) => v === 'corrected').length;
  const remaining = Math.max(0, total - currentIdx - 1);

  return (
    <div className="absolute right-4 top-32 z-40 w-80 rounded-lg border border-sky-300 bg-white p-4 shadow-2xl">
      <div className="mb-1 text-xs uppercase text-sky-600">
        Tikrinimas {currentIdx + 1} / {total}
      </div>
      <div className="text-base font-semibold text-neutral-800">
        {current.nr} {current.name}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-neutral-600">
        <div>Plotas: <strong>{(current.area_m2 || 0).toFixed(2)} m²</strong></div>
        <div>Perim.: <strong>{((current.perimeter_mm || 0) / 1000).toFixed(2)} m</strong></div>
        <div>H: <strong>{(current.ceiling_height_m || 0).toFixed(2)} m</strong></div>
        <div>Dažym.: <strong>{(current.dazymo_plotas_m2 || 0).toFixed(1)} m²</strong></div>
      </div>
      <p className="mt-3 text-sm font-medium text-neutral-700">Ar AI matmenys teisingi?</p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => { onConfirm && onConfirm(current.nr); }}
          className="flex-1 rounded border border-emerald-500 bg-emerald-50 px-2 py-1.5 text-sm text-emerald-700"
        >✓ Taip</button>
        <button
          type="button"
          onClick={() => onCorrect && onCorrect(current.nr)}
          className="flex-1 rounded border border-amber-500 bg-amber-50 px-2 py-1.5 text-sm text-amber-700"
          title="Pakoreguokite sienas dešinėje, tada Toliau"
        >✎ Koreguoti</button>
      </div>
      <div className="mt-2 flex gap-2 text-xs">
        <button
          type="button"
          onClick={() => onAdvance && onAdvance()}
          className="flex-1 rounded border border-neutral-300 px-2 py-1 text-neutral-600"
        >→ Toliau</button>
        <button
          type="button"
          onClick={() => onStop && onStop()}
          className="rounded border border-neutral-300 px-2 py-1 text-neutral-500"
        >Nutraukti</button>
      </div>
      <div className="mt-2 text-xs text-neutral-400">
        ✓ {confirmed}  ·  ✎ {corrected}  ·  liko {remaining}
      </div>
    </div>
  );
}

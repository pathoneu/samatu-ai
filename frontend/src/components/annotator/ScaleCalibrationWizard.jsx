/**
 * ScaleCalibrationWizard — first-time scale setup modal.
 *
 * Shown when a project loads with no saved scale. Pre-fills the
 * AI-computed scale factor (from /room-graph's page_scale_mm_per_pct)
 * as the default. The user can:
 *   1. Accept the AI default → modal closes, scale is set
 *   2. Choose "Aš nubrėšiu" → modal closes, calibrate tool activates,
 *      next two canvas clicks + prompt set the manual scale
 *   3. Choose "Praleisti" → modal closes, no scale set; user can
 *      calibrate later via the toolbar
 *
 * Props:
 *   aiScale          — AI-computed mm-per-px (or null if unavailable)
 *   onAccept(scale)  — user accepted AI default
 *   onDrawLine()     — user wants to draw a calibration line manually
 *   onSkip()         — user dismissed the wizard
 */
import React from 'react';

export default function ScaleCalibrationWizard({
  aiScale,
  onAccept,
  onDrawLine,
  onSkip,
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onSkip}
    >
      <div
        className="w-[460px] max-w-[90vw] rounded-lg bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 text-lg font-semibold text-neutral-800">Nustatykite mastelį</h2>
        <p className="mb-4 text-sm text-neutral-600">
          Kad matavimai būtų tikslūs, sistemai reikia žinoti, kiek
          milimetrų atitinka vienas pikselis brėžinyje.
        </p>

        {aiScale ? (
          <>
            <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
              <div className="text-xs font-medium uppercase text-emerald-700">
                AI siūlomas mastelis
              </div>
              <div className="mt-1 font-mono text-lg font-semibold text-emerald-800">
                {aiScale.toFixed(3)} mm/px
              </div>
              <div className="mt-1 text-xs text-emerald-700">
                Apskaičiuota iš brėžinio matmenų lentelės. Jei pasitikite
                — spustelėkite „Priimti“.
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => onAccept && onAccept(aiScale)}
                className="flex-1 rounded border border-emerald-600 bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700"
              >Priimti AI mastelį</button>
              <button
                type="button"
                onClick={onDrawLine}
                className="flex-1 rounded border border-blue-500 bg-white px-3 py-2 text-sm text-blue-700 hover:bg-blue-50"
              >Aš nubrėšiu</button>
            </div>
          </>
        ) : (
          <>
            <p className="mb-4 text-sm text-neutral-700">
              AI nepavyko automatiškai nustatyti mastelio. Nubrėžkite liniją
              ant žinomos sienos ir įveskite jos ilgį milimetrais.
            </p>
            <button
              type="button"
              onClick={onDrawLine}
              className="w-full rounded border border-blue-600 bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >Nubrėžti kalibravimo liniją</button>
          </>
        )}

        <button
          type="button"
          onClick={onSkip}
          className="mt-3 w-full text-center text-xs text-neutral-500 hover:text-neutral-700"
        >Praleisti (kalibruosiu vėliau)</button>
      </div>
    </div>
  );
}

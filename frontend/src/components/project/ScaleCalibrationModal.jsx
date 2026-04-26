/**
 * ScaleCalibrationModal — vartotojas pažymi 2 taškus brėžinyje, įveda
 * realų atstumą metrais, gauname mastelio ratio.
 *
 * Modes:
 *   'idle'      — vartotojas nepradėjo (toolbar mygtukas)
 *   'pick_p1'   — laukiame pirmo paspaudimo
 *   'pick_p2'   — laukiame antro paspaudimo
 *   'enter_distance' — modal'as su input'u
 *   'apply'     — siūlome "taikyti visiems puslapiams"
 */

import { useState } from 'react';
import { Ruler, Check, X, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ScaleCalibrationModal({
  point1, point2, onCancel, onConfirm,
  totalPages, currentPage,
}) {
  const [distanceM, setDistanceM] = useState('');
  const [applyAll, setApplyAll] = useState(false);

  if (!point1 || !point2) return null;

  // Pikselių atstumas tarp paspaudimo taškų
  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  const pxDist = Math.sqrt(dx * dx + dy * dy);

  const handleSubmit = (e) => {
    e.preventDefault();
    const meters = parseFloat(String(distanceM).replace(',', '.'));
    if (!meters || meters <= 0) return;
    const pxPerMeter = pxDist / meters;
    onConfirm({
      pixels_per_meter: pxPerMeter,
      apply_all_pages: applyAll,
      reference_distance_m: meters,
      reference_distance_px: pxDist,
    });
  };

  // Įvertinimas: jei mastelis 1:50, tipinis A3 brėžinys turi ~5–15m matavimus
  const sanityHint = (() => {
    const m = parseFloat(String(distanceM).replace(',', '.'));
    if (!m || m <= 0) return null;
    if (m < 0.5) return { type: 'warn', text: 'Atrodo mažai. Įprastai matuoja sienas (>1m).' };
    if (m > 50) return { type: 'warn', text: 'Atrodo daug. Patikrink ar tikrai metrai (ne mm).' };
    return { type: 'ok', text: `Įvertintas mastelis ≈ 1:${Math.round(pxDist / m * 50 / pxDist * 1000 / 1000 * 50 || 50)}` };
  })();

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-card rounded-xl shadow-2xl w-full max-w-md border border-border overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ruler className="w-4 h-4 text-foreground" />
            <span className="font-semibold text-sm text-foreground">Mastelio kalibracija</span>
          </div>
          <button onClick={onCancel}
            className="p-1 hover:bg-muted rounded text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div className="text-sm text-foreground">
            Pažymėjai du taškus, atstumas tarp jų — <strong className="font-mono">{pxDist.toFixed(1)} px</strong>.
          </div>

          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">
              Įvesk realų atstumą metrais
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                value={distanceM}
                onChange={e => setDistanceM(e.target.value)}
                placeholder="Pvz. 3,45"
                autoFocus
                className="flex-1 px-3 py-2 border border-border bg-background rounded-lg text-base font-mono focus:outline-none focus:border-foreground/40"
              />
              <span className="text-sm text-muted-foreground font-medium">m</span>
            </div>
            {sanityHint && (
              <p className={`text-xs mt-1.5 ${
                sanityHint.type === 'warn'
                  ? 'text-amber-600 dark:text-amber-400'
                  : 'text-muted-foreground'
              }`}>
                {sanityHint.text}
              </p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Patarimas: matuok ilgą žinomą atstumą (sienos ilgį, kambario ilgį) — tikslesni rezultatai.
            </p>
          </div>

          {totalPages > 1 && (
            <label className="flex items-start gap-2 p-3 bg-muted/50 rounded-lg cursor-pointer hover:bg-muted transition-colors">
              <input
                type="checkbox"
                checked={applyAll}
                onChange={e => setApplyAll(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-foreground"
              />
              <div className="text-sm">
                <div className="font-medium text-foreground flex items-center gap-1.5">
                  <Copy className="w-3 h-3" />
                  Taikyti visiems {totalPages} puslapiams
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  Naudoti tą patį mastelį visam dokumentui. Atjunk, jei pjūvis ar fasadas turi kitokį mastelį.
                </div>
              </div>
            </label>
          )}

          <div className="flex items-center justify-between gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Atšaukti
            </Button>
            <Button type="submit"
              disabled={!distanceM || parseFloat(String(distanceM).replace(',', '.')) <= 0}
              className="bg-foreground text-background hover:opacity-90 gap-1.5"
            >
              <Check className="w-4 h-4" />
              Patvirtinti mastelį
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

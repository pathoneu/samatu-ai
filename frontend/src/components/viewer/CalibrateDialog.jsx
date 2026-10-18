/**
 * CalibrateDialog (port of backup ScaleCalibrationDialog) — the second half of the two-point scale-calibration
 * flow. The overlay reports two PDF points (the calibrate tool); this dialog
 * asks for their real-world length + unit, builds a PageScale, and hands it
 * back via onConfirm. Persistence is a later task — this only computes + emits.
 *
 * Matches the repo's fixed-overlay modal pattern (see ScaleCalibrationModal.jsx)
 * rather than the shadcn Dialog primitive: the calibration line is drawn in the
 * SVG overlay directly under the modal, and a Radix Dialog portal + focus trap
 * layered over that overlay adds nothing here. We reuse the shadcn Button /
 * Input / Select controls for consistent styling.
 */
import { useEffect, useMemo, useState } from 'react';
import { Ruler, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  pdfDistance,
  realDistanceM,
  calibrateUniform,
  calibrateAxis,
  formatNumberLT,
  storedAxisForDisplayAxis,
  axisSpanShare,
  AXIS_SPAN_MIN_SHARE,
} from '@/lib/measureGeometry';
import { displayRotationFor } from '@/lib/viewerEngine/pageRotation';
import { Checkbox } from '@/components/ui/checkbox';
import { suggestStandardScale, standardScalePageScale } from '@/lib/scaleSuggestion';

const UNITS = [
  { value: 'mm', label: 'mm' },
  { value: 'cm', label: 'cm' },
  { value: 'm', label: 'm' },
  { value: 'in', label: 'in' },
  { value: 'ft', label: 'ft' },
];

// Uniform / X-only / Y-only. calibrateUniform for 'uniform', calibrateAxis for the axes.
const AXES = [
  { value: 'uniform', label: 'Vienoda' },
  { value: 'x', label: 'Tik horizontali' },
  { value: 'y', label: 'Tik vertikali' },
];

export default function CalibrateDialog({
  request,        // { pageNr, a, b } | null — a/b are PDF points; null = closed
  numPages,
  currentScale,
  // The page's /Rotate. a/b are UNROTATED mediabox points, but the axis labels
  // describe what the user SEES — on a 90°/270° page the two are swapped.
  pageRotation = 0,
  onConfirm,      // (pageScale, applyToPages) => void   applyToPages: number[]|null
  onClose,        // () => void
}) {
  const [length, setLength] = useState('');
  const [unit, setUnit] = useState('m');
  const [axis, setAxis] = useState('uniform');
  const [applyTo, setApplyTo] = useState('page'); // 'page' | 'all'
  // Togal's „Snap to standard scales" (2026-10-16): when the two clicks measure within 3 % of a drawing
  // scale (1:50, 1:100 …), the dialog offers to take that scale instead of the measured ratio.
  const [roundToStandard, setRoundToStandard] = useState(true);

  // Reset the form each time a fresh calibration request arrives.
  useEffect(() => {
    if (request) {
      setLength('');
      setUnit('m');
      setAxis('uniform');
      setApplyTo('page');
      setRoundToStandard(true);
    }
  }, [request]);

  const pdfLen = useMemo(
    () => (request ? pdfDistance(request.a, request.b) : 0),
    [request],
  );

  const parsedLength = useMemo(() => {
    const n = parseFloat(String(length).replace(',', '.'));
    return Number.isFinite(n) ? n : null;
  }, [length]);

  const canConfirm = parsedLength !== null && parsedLength > 0;

  // What the two clicks MEASURE as a drawing scale, and the standard scale next to it (uniform axis only).
  const suggestion = useMemo(
    () => (axis === 'uniform' && parsedLength ? suggestStandardScale(pdfLen, parsedLength, unit) : null),
    [axis, parsedLength, pdfLen, unit],
  );
  const offerRounding = !!suggestion?.within;

  if (!request) return null;

  const handleConfirm = () => {
    if (!canConfirm) return;
    let scale;
    try {
      if (axis === 'uniform') {
        scale = offerRounding && roundToStandard
          ? standardScalePageScale(suggestion.nearest)
          : calibrateUniform(request.a, request.b, parsedLength, unit);
      } else {
        // 'x' = what the user sees as horizontal → the STORED axis it maps to.
        const storedAxis = storedAxisForDisplayAxis(axis, displayRotationFor(pageRotation));
        // A line almost perpendicular to the chosen axis has a span of a few
        // points — dividing metres by it mis-scales the page wildly (audit P1).
        if (axisSpanShare(request.a, request.b, storedAxis) < AXIS_SPAN_MIN_SHARE) {
          toast.error('Pasirinkta ašis beveik statmena linijai — naudokite bendrą kalibravimą');
          return;
        }
        scale = calibrateAxis(request.a, request.b, parsedLength, unit, currentScale, storedAxis);
      }
    } catch (e) {
      // Geometry rejects degenerate picks by throwing — surface the reason
      // instead of leaving a dead Patvirtinti button (audit P1).
      toast.error(e?.message || 'Nepavyko kalibruoti mastelio');
      return;
    }
    const pages = applyTo === 'all'
      ? Array.from({ length: numPages || 1 }, (_, i) => i + 1)
      : null;
    onConfirm(scale, pages);
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleConfirm();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  // Self-check echo: what the CURRENT scale would say this line measures.
  const selfCheck = currentScale?.calibrated
    ? realDistanceM(request.a, request.b, currentScale)
    : null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-card rounded-xl shadow-2xl w-full max-w-md border border-border overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Ruler className="w-4 h-4 text-foreground" />
            <span className="font-semibold text-sm text-foreground">Mastelio kalibracija</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-muted rounded text-muted-foreground"
            aria-label="Uždaryti"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* "PDF taškų" is a rendering unit that means nothing on site. Lead
              with the instruction instead; keep the raw number as a hover
              detail. (2026-07-28 explainability pass.) */}
          <div
            className="text-sm text-foreground"
            title={`Pažymėtos linijos ilgis brėžinio vienetais: ${formatNumberLT(pdfLen, 1)} PDF taškų`}
          >
            Įrašykite, koks yra <strong>tikras</strong> ką tik pažymėtos atkarpos ilgis — pagal jį bus nustatytas viso brėžinio mastelis.
          </div>

          {/* Real length + unit */}
          <div>
            <label
              htmlFor="calib-length-input"
              className="text-sm font-medium text-foreground block mb-1.5"
            >
              Realus atstumas
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="calib-length-input"
                type="text"
                inputMode="decimal"
                value={length}
                onChange={(e) => setLength(e.target.value)}
                placeholder="Pvz. 3,45"
                autoFocus
                data-testid="calib-length"
                aria-label="Realus pažymėtos atkarpos atstumas"
                title="Tikras atstumas, pvz. iš brėžinio matmenų linijos. Kablelis arba taškas — abu tinka."
                className="flex-1 font-mono"
              />
              <Select value={unit} onValueChange={setUnit}>
                <SelectTrigger
                  className="w-[84px]"
                  data-testid="calib-unit"
                  aria-label="Atstumo matavimo vienetas"
                  title="Kuriais vienetais įrašėte atstumą"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {UNITS.map((u) => (
                    <SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Axis */}
          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">Ašis</label>
            <Select value={axis} onValueChange={setAxis}>
              <SelectTrigger
                data-testid="calib-axis"
                aria-label="Kuriai krypčiai taikyti mastelį"
                title="Beveik visada palikite „Vienoda“. Atskirai horizontalią ar vertikalią rinkitės tik tada, jei skenuotas brėžinys ištemptas į vieną pusę."
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AXES.map((a) => (
                  <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Apply-to */}
          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">Taikyti</label>
            <Select value={applyTo} onValueChange={setApplyTo}>
              <SelectTrigger
                data-testid="calib-apply"
                aria-label="Kuriems lapams taikyti mastelį"
                title="„Visiems lapams“ perrašo ir tuos lapus, kuriems mastelis jau nustatytas — rinkitės, jei visi brėžiniai to paties mastelio."
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="page">Šiam lapui</SelectItem>
                <SelectItem value="all">Visiems lapams{numPages ? ` (${numPages})` : ''}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Self-check echo */}
          {selfCheck !== null && (
            <div className="text-xs text-muted-foreground">
              Patikra: pagal esamą mastelį ši linija = {formatNumberLT(selfCheck, 2)} m
            </div>
          )}

          {/* Measured drawing scale + the nearest standard one (2026-10-16) */}
          {suggestion && (
            <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-foreground space-y-1.5" data-testid="calib-suggestion">
              <div>
                Pagal šią atkarpą mastelis ≈ <span className="font-mono">1:{formatNumberLT(suggestion.measured, 1)}</span>
                {' '}· artimiausias standartinis <span className="font-mono">1:{suggestion.nearest}</span>
                {' '}(skiriasi {formatNumberLT(suggestion.diffPct, 1)} %)
              </div>
              {offerRounding ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={roundToStandard}
                    onCheckedChange={(v) => setRoundToStandard(v === true)}
                    data-testid="calib-round-standard"
                    aria-label={`Suapvalinti iki standartinio mastelio 1:${suggestion.nearest}`}
                  />
                  <span>Suapvalinti iki standartinio mastelio 1:{suggestion.nearest}</span>
                </label>
              ) : (
                <div className="text-muted-foreground">
                  Skirtumas per didelis standartiniam masteliui — lapas greičiausiai atspausdintas kitu dydžiu nei brėžtas; paliekamas išmatuotas.
                </div>
              )}
            </div>
          )}

          {/* Anisotropy tip */}
          {/* The tip said "X/Y" while the control right above it says
              „Vienoda / Tik horizontali / Tik vertikali" — match the words the
              user can actually click. (2026-07-28.) */}
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Skenuoti brėžiniai dažnai būna ištempti į vieną pusę. Tokiu atveju ašyje rinkitės „Tik horizontali" arba „Tik vertikali" ir kalibruokite du kartus.
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              title="Uždaryti nenustačius mastelio — matavimai liks be metrų"
            >
              Atšaukti
            </Button>
            <Button
              type="button"
              onClick={handleConfirm}
              disabled={!canConfirm}
              data-testid="calib-confirm"
              title={canConfirm
                ? 'Nustatyti mastelį — visi matavimai bus perskaičiuoti metrais'
                : 'Pirmiausia įrašykite realų atstumą (skaičių didesnį už 0)'}
              className="gap-1.5"
            >
              <Check className="w-4 h-4" />
              Patvirtinti mastelį
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

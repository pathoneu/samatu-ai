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
} from '@/lib/measureGeometry';

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
  onConfirm,      // (pageScale, applyToPages) => void   applyToPages: number[]|null
  onClose,        // () => void
}) {
  const [length, setLength] = useState('');
  const [unit, setUnit] = useState('m');
  const [axis, setAxis] = useState('uniform');
  const [applyTo, setApplyTo] = useState('page'); // 'page' | 'all'

  // Reset the form each time a fresh calibration request arrives.
  useEffect(() => {
    if (request) {
      setLength('');
      setUnit('m');
      setAxis('uniform');
      setApplyTo('page');
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

  if (!request) return null;

  const handleConfirm = () => {
    if (!canConfirm) return;
    let scale;
    if (axis === 'uniform') {
      scale = calibrateUniform(request.a, request.b, parsedLength, unit);
    } else {
      scale = calibrateAxis(request.a, request.b, parsedLength, unit, currentScale, axis);
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
          <div className="text-sm text-foreground">
            Pažymėta linija — <strong className="font-mono">{formatNumberLT(pdfLen, 1)} PDF taškų</strong>.
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
                className="flex-1 font-mono"
              />
              <Select value={unit} onValueChange={setUnit}>
                <SelectTrigger className="w-[84px]" data-testid="calib-unit">
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
              <SelectTrigger data-testid="calib-axis">
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
              <SelectTrigger data-testid="calib-apply">
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

          {/* Anisotropy tip */}
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300">
            Perskenuoti PDF dažnai ištempti — kalibruokite atskirai X/Y jei reikia.
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>
              Atšaukti
            </Button>
            <Button
              type="button"
              onClick={handleConfirm}
              disabled={!canConfirm}
              data-testid="calib-confirm"
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

/**
 * PolygonRoomModal — atsiranda kai vartotojas baigia brūkšnioti polygon'ą.
 * Vartotojas priskiria pavadinimą + paskirtį → polygon išsaugomas su
 * room metadata.
 */

import { useState } from 'react';
import { Check, X, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';

const PASKIRTIS_OPTIONS = [
  { value: 'gyvenamoji', label: 'Gyvenamoji / Svetainė' },
  { value: 'miegamoji', label: 'Miegamoji' },
  { value: 'virtuve', label: 'Virtuvė' },
  { value: 'valgomasis', label: 'Valgomasis' },
  { value: 'vonia', label: 'Vonia' },
  { value: 'wc', label: 'WC' },
  { value: 'koridorius', label: 'Koridorius' },
  { value: 'holas', label: 'Holas' },
  { value: 'drabuzine', label: 'Drabužinė' },
  { value: 'sandeliukas', label: 'Sandėliukas' },
  { value: 'tambūras', label: 'Tambūras' },
  { value: 'garazas', label: 'Garažas' },
  { value: 'katiline', label: 'Katilinė' },
  { value: 'skalbykla', label: 'Skalbykla' },
];

export default function PolygonRoomModal({
  area_m2, perimeter_m,
  defaultLabel = '', defaultPaskirtis = 'gyvenamoji',
  onCancel, onConfirm,
}) {
  const [label, setLabel] = useState(defaultLabel);
  const [paskirtis, setPaskirtis] = useState(defaultPaskirtis);
  const [aukstis, setAukstis] = useState('2.82');

  const handleSubmit = (e) => {
    e.preventDefault();
    onConfirm({
      label: label.trim() || PASKIRTIS_OPTIONS.find(o => o.value === paskirtis)?.label || 'Patalpa',
      paskirtis,
      lubu_aukstis_m: parseFloat(String(aukstis).replace(',', '.')) || 2.82,
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-card rounded-xl shadow-2xl w-full max-w-md border border-border overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Square className="w-4 h-4 text-foreground" />
            <span className="font-semibold text-sm text-foreground">Nauja patalpa</span>
          </div>
          <button onClick={onCancel}
            className="p-1 hover:bg-muted rounded text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Pre-calculated info */}
        <div className="px-5 py-3 bg-muted/30 border-b border-border">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-0.5">Plotas</div>
              <div className="text-2xl font-semibold tabular-nums text-foreground">
                {area_m2.toFixed(1)} <span className="text-base font-normal text-muted-foreground">m²</span>
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground uppercase tracking-wide mb-0.5">Perimetras</div>
              <div className="text-2xl font-semibold tabular-nums text-foreground">
                {perimeter_m.toFixed(1)} <span className="text-base font-normal text-muted-foreground">m</span>
              </div>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-3">
          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">
              Pavadinimas
            </label>
            <input
              type="text"
              value={label}
              onChange={e => setLabel(e.target.value)}
              placeholder="Pvz., Svetainė, Miegamasis 1, Vonia"
              autoFocus
              className="w-full px-3 py-2 border border-border bg-background rounded-lg text-sm focus:outline-none focus:border-foreground/40"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">
              Paskirtis
            </label>
            <select
              value={paskirtis}
              onChange={e => setPaskirtis(e.target.value)}
              className="w-full px-3 py-2 border border-border bg-background rounded-lg text-sm focus:outline-none focus:border-foreground/40"
            >
              {PASKIRTIS_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-foreground block mb-1.5">
              Lubų aukštis
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                value={aukstis}
                onChange={e => setAukstis(e.target.value)}
                className="flex-1 px-3 py-2 border border-border bg-background rounded-lg text-sm font-mono focus:outline-none focus:border-foreground/40"
              />
              <span className="text-sm text-muted-foreground font-medium">m</span>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Atšaukti
            </Button>
            <Button type="submit"
              className="bg-foreground text-background hover:opacity-90 gap-1.5">
              <Check className="w-4 h-4" />
              Pridėti patalpą
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

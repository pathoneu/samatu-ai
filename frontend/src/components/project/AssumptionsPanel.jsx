import React, { useState } from 'react';
import { AlertCircle, ChevronDown, ChevronUp, Plus, Trash2, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtM(val) {
  if (val == null) return '—';
  return `${Number(val).toFixed(2)} m`;
}

function NumberInput({ value, onChange, min, max, step = 0.01, unit }) {
  return (
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={e => onChange(parseFloat(e.target.value) || value)}
        className="h-7 w-20 text-xs bg-card border-border text-right tabular-nums"
      />
      {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
    </div>
  );
}

function Row({ label, note, children }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/40 last:border-0 gap-4">
      <div className="min-w-0">
        <span className="text-sm text-foreground">{label}</span>
        {note && <p className="text-xs text-muted-foreground mt-0.5">{note}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

// ── Window/Door list editor ───────────────────────────────────────────────────

function OpeningEditor({ items, onChange, label, defaultItem }) {
  const handleChange = (i, field, val) => {
    const next = items.map((item, idx) =>
      idx === i ? { ...item, [field]: parseInt(val) || 0 } : item
    );
    onChange(next);
  };

  const handleAdd = () => onChange([...items, { ...defaultItem }]);
  const handleRemove = i => onChange(items.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-1">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground w-4 text-right">{i + 1}.</span>
          {item.patalpa && (
            <span className="text-muted-foreground truncate max-w-[80px]">{item.patalpa}</span>
          )}
          <Input
            type="number"
            value={item.width_mm}
            onChange={e => handleChange(i, 'width_mm', e.target.value)}
            className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
            placeholder="plotis"
          />
          <span className="text-muted-foreground">×</span>
          <Input
            type="number"
            value={item.height_mm}
            onChange={e => handleChange(i, 'height_mm', e.target.value)}
            className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
            placeholder="aukštis"
          />
          <span className="text-muted-foreground">mm</span>
          {item.suggested && (
            <Badge variant="outline" className="text-[10px] border-amber-400/50 text-amber-600 py-0 px-1">est.</Badge>
          )}
          <button onClick={() => handleRemove(i)} className="ml-auto text-muted-foreground hover:text-destructive">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      ))}
      <button
        onClick={handleAdd}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-1"
      >
        <Plus className="w-3 h-3" /> Pridėti {label.toLowerCase()}
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AssumptionsPanel({ assumptions, onChange, prielaidos, rawData }) {
  const [open, setOpen] = useState(false);
  const [windowsExpanded, setWindowsExpanded] = useState(false);
  const [doorsExpanded, setDoorsExpanded] = useState(false);

  const { sienos_storis_m, glaistimo_lygis, lubu_auksciai, custom_windows, custom_doors } = assumptions;
  const isFallback = prielaidos?.langai_fallback;

  // Derive display windows list: custom or fallback-suggested or empty
  const displayWindows = custom_windows ?? (
    isFallback ? (prielaidos?.langai_suggested || []) : []
  );

  // Derive display doors list: custom or meta doors
  const metaDoors = rawData?.meta?.doors || [];
  const displayDoors = custom_doors ?? metaDoors;

  const setField = (field, val) => onChange({ ...assumptions, [field]: val });

  const setLubuAukstis = (roomNr, val) =>
    onChange({ ...assumptions, lubu_auksciai: { ...lubu_auksciai, [roomNr]: val } });

  const rooms = rawData?.patalpos || [];
  const avgH  = rooms.length > 0
    ? rooms.reduce((s, r) => s + (r.lubu_aukstis_mm || 2800), 0) / rooms.length / 1000
    : 2.80;

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Info className="w-4 h-4 text-muted-foreground" />
          Prielaidos
          {isFallback && (
            <Badge className="text-xs bg-amber-100 text-amber-800 border-amber-200 border font-normal">
              langai — prielaida
            </Badge>
          )}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-3 space-y-1">

          {/* Window fallback warning */}
          {isFallback && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 mb-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Langai nerasti brėžiniuose</p>
                <p className="text-xs mt-0.5">
                  Pateikiami standartiniai pasiūlymai pagal patalpų tipus. Patikrink ir pakoreguok žemiau.
                </p>
              </div>
            </div>
          )}

          {/* Sienos storis */}
          <Row
            label="Sienos storis (pertvaros)"
            note="Naudojama angokraščių ploto skaičiavimui"
          >
            <NumberInput
              value={sienos_storis_m}
              onChange={v => setField('sienos_storis_m', v)}
              min={0.05} max={0.50} step={0.01} unit="m"
            />
          </Row>

          {/* Glaistymo lygis */}
          <Row label="Glaistymo lygis" note="Naudojama glaisto kiekio skaičiavimui">
            <div className="flex gap-1">
              {['Q1','Q2','Q3','Q4'].map(q => (
                <button
                  key={q}
                  onClick={() => setField('glaistimo_lygis', q)}
                  className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${
                    glaistimo_lygis === q
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                  }`}
                >
                  {q}
                </button>
              ))}
            </div>
          </Row>

          {/* Lubų aukštis per kambarį */}
          {rooms.length > 0 && (
            <div className="py-2">
              <p className="text-sm text-foreground mb-2">
                Lubų aukštis <span className="text-xs text-muted-foreground">(numatytasis: {avgH.toFixed(2)} m)</span>
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => (
                  <div key={room.nr} className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground truncate flex-1" title={room.pavadinimas}>
                      {room.pavadinimas || room.nr}
                    </span>
                    <Input
                      type="number"
                      value={lubu_auksciai[room.nr] ?? ((room.lubu_aukstis_mm || 2800) / 1000)}
                      min={2.0} max={6.0} step={0.05}
                      onChange={e => setLubuAukstis(room.nr, parseFloat(e.target.value) || 2.8)}
                      className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
                    />
                    <span className="text-xs text-muted-foreground">m</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Langai */}
          <div className="py-2 border-b border-border/40">
            <button
              className="flex items-center justify-between w-full mb-2"
              onClick={() => setWindowsExpanded(v => !v)}
            >
              <span className="text-sm text-foreground">
                Langai
                <span className="text-xs text-muted-foreground ml-2">
                  ({displayWindows.length} vnt.)
                  {isFallback && !custom_windows && <span className="text-amber-600 ml-1">prielaida</span>}
                </span>
              </span>
              {windowsExpanded
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              }
            </button>
            {windowsExpanded && (
              <OpeningEditor
                items={displayWindows}
                onChange={wins => setField('custom_windows', wins)}
                label="langą"
                defaultItem={{ width_mm: 1200, height_mm: 1500 }}
              />
            )}
          </div>

          {/* Durys */}
          <div className="py-2">
            <button
              className="flex items-center justify-between w-full mb-2"
              onClick={() => setDoorsExpanded(v => !v)}
            >
              <span className="text-sm text-foreground">
                Durys
                <span className="text-xs text-muted-foreground ml-2">({displayDoors.length} vnt.)</span>
              </span>
              {doorsExpanded
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              }
            </button>
            {doorsExpanded && (
              <OpeningEditor
                items={displayDoors}
                onChange={ds => setField('custom_doors', ds)}
                label="duris"
                defaultItem={{ width_mm: 800, height_mm: 2200 }}
              />
            )}
          </div>

          <p className="text-xs text-muted-foreground pt-1">
            Kiekiai persiskaičiuoja automatiškai kiekvieną kartą keičiant prielaidas.
          </p>
        </div>
      )}
    </div>
  );
}

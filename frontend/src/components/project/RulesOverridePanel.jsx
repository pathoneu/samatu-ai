/**
 * RulesOverridePanel — vartotojo per-paskirtis nustatymai (Phase 10).
 *
 * Po extract-interior'o, vartotojas gali keisti:
 *  - Ar dažomos sienos drabužinėse, garažuose, tambūruose, sandėliukuose
 *  - Vonios sienų plytelių aukštis
 *  - Virtuvės backsplash aukštis
 *  - Per-room overrides (force tile_floor TAIP/NE konkretiems kambariams)
 *
 * Pakeitimai siunčiami į backend /recompute-interior (be Vision call'o,
 * pure math). Sub-second roundtrip, visi totals atnaujinami.
 */

import { useState, useMemo, useEffect, useRef } from 'react';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Loader2, RefreshCw, AlertCircle } from 'lucide-react';

const API = '';

// Per-paskirtis flagai. Frontend mapuojami į backend rules_override.
const PASKIRTIS_TOGGLES = [
  { key: 'drabuzine_painted',  label: 'Drabužinės sienos dažomos',  default: true },
  { key: 'rubine_painted',     label: 'Rūbų kambario sienos dažomos', default: true },
  { key: 'sandeliukas_painted', label: 'Sandėliuko sienos dažomos',  default: true },
  { key: 'katiline_painted',   label: 'Katilinės sienos dažomos',   default: true },
  { key: 'garazas_painted',    label: 'Garažo sienos dažomos',      default: false },
  { key: 'tamburas_painted',   label: 'Tambūro sienos dažomos',     default: false },
];

const NUMERIC_FIELDS = [
  { key: 'bathroom_tile_height_m',     label: 'Vonios plytelių aukštis',  unit: 'm', min: 1.5, max: 3.0, step: 0.1, default: 2.0 },
  { key: 'kitchen_backsplash_height_m', label: 'Virtuvės backsplash aukštis', unit: 'm', min: 0.4, max: 1.2, step: 0.1, default: 0.6 },
  { key: 'high_ceiling_threshold_m',   label: 'Aukšta luba (>X m = atskira pozicija)', unit: 'm', min: 2.5, max: 4.0, step: 0.1, default: 3.0 },
];

const FLOOR_OVERRIDABLE_PASKIRTYS = ['koridorius', 'holas', 'gyvenamoji', 'valgomasis', 'miegamoji', 'drabuzine', 'rubine', 'kabinetas'];


export default function RulesOverridePanel({ project, onProjectUpdate }) {
  const [overrides, setOverrides] = useState(() => project._overrides || {});
  const [perRoomOverrides, setPerRoomOverrides] = useState(() => project._per_room_overrides || {});
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState(null);
  const debounceRef = useRef(null);

  const patalpos = project.v8_rooms || project.patalpos || [];
  const candidateRooms = useMemo(
    () => patalpos.filter(r => FLOOR_OVERRIDABLE_PASKIRTYS.includes((r.paskirtis || '').toLowerCase())),
    [patalpos]
  );

  // Debounced trigger of backend recompute
  const triggerRecompute = (newOverrides, newPerRoom) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setRecomputing(true);
      setError(null);
      try {
        const payload = {
          patalpos,
          rules_override: newOverrides,
          per_room_overrides: newPerRoom,
          archetipas: project.archetipas,
          bendras_plotas_m2: project.bendras_plotas_m2,
        };
        const res = await fetch(`${API}/recompute-interior`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        if (result.status !== 'ok') throw new Error(result._error || 'Recompute klaida');
        // Merge result back into project — preserve all original fields not in result
        onProjectUpdate({
          ...project,
          ...result,
          _overrides: newOverrides,
          _per_room_overrides: newPerRoom,
        });
      } catch (e) {
        console.error('Recompute failed:', e);
        setError(e.message || 'Nepavyko perskaičiuoti');
      } finally {
        setRecomputing(false);
      }
    }, 400); // 400ms debounce
  };

  const updateToggle = (key, value) => {
    const next = { ...overrides, [key]: value };
    setOverrides(next);
    triggerRecompute(next, perRoomOverrides);
  };

  const updateNumeric = (key, value) => {
    const next = { ...overrides, [key]: value };
    setOverrides(next);
    triggerRecompute(next, perRoomOverrides);
  };

  const updatePerRoomTileFloor = (roomNr, tileFloor) => {
    const next = { ...perRoomOverrides, [roomNr]: { ...(perRoomOverrides[roomNr] || {}), tile_floor: tileFloor } };
    setPerRoomOverrides(next);
    triggerRecompute(overrides, next);
  };

  const updatePerRoomPaint = (roomNr, paint) => {
    const next = { ...perRoomOverrides, [roomNr]: { ...(perRoomOverrides[roomNr] || {}), walls_paint: paint ? 1.0 : 0.0 } };
    setPerRoomOverrides(next);
    triggerRecompute(overrides, next);
  };

  const reset = () => {
    setOverrides({});
    setPerRoomOverrides({});
    triggerRecompute({}, {});
  };

  return (
    <div className="space-y-6">
      {/* Header status */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Prielaidos ir nustatymai</h2>
          <p className="text-sm text-muted-foreground">
            Pakeisk default'us — sumos perskaičiuojamos per ~1 sek (be Vision call'o).
          </p>
        </div>
        <div className="flex items-center gap-3">
          {recomputing && (
            <span className="text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Perskaičiuoja...
            </span>
          )}
          <Button variant="outline" size="sm" onClick={reset} disabled={recomputing}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Atstatyti default'us
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>{error}</div>
        </div>
      )}

      {/* Per-paskirtis toggles */}
      <div className="border border-border rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold mb-2">Patalpų tipai — sienos dažomos?</h3>
        {PASKIRTIS_TOGGLES.map(t => {
          const value = t.key in overrides ? overrides[t.key] : t.default;
          return (
            <div key={t.key} className="flex items-center justify-between py-1.5">
              <span className="text-sm">{t.label}</span>
              <Switch
                checked={!!value}
                onCheckedChange={v => updateToggle(t.key, v)}
                disabled={recomputing}
              />
            </div>
          );
        })}
      </div>

      {/* Numeric inputs */}
      <div className="border border-border rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold mb-2">Aukščiai ir ribos</h3>
        {NUMERIC_FIELDS.map(f => {
          const value = f.key in overrides ? overrides[f.key] : f.default;
          return (
            <div key={f.key} className="flex items-center justify-between py-1.5">
              <span className="text-sm">{f.label}</span>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  value={value}
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  onChange={e => updateNumeric(f.key, parseFloat(e.target.value) || f.default)}
                  className="h-8 w-24 text-right tabular-nums"
                  disabled={recomputing}
                />
                <span className="text-sm text-muted-foreground w-4">{f.unit}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Per-room overrides */}
      {candidateRooms.length > 0 && (
        <div className="border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-2">Konkretūs kambariai</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Force'ink plytelės/parketas ar dažoma TAIP/NE konkrečiai patalpai (apeina default'ą).
          </p>
          <div className="space-y-2">
            {candidateRooms.map(r => {
              const ov = perRoomOverrides[r.nr] || {};
              return (
                <div key={r.nr} className="flex items-center justify-between gap-3 py-1.5 border-b border-border/40 last:border-0">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{r.nr} {r.pavadinimas}</div>
                    <div className="text-xs text-muted-foreground">
                      {r.paskirtis} · {r.plotas_m2} m² · grindys: {r.plyteles_grindys_m2 > 0 ? 'plytelės' : 'parketas/PVC'}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-1 text-xs">
                      <span className="text-muted-foreground">Plytelės grindys</span>
                      <Switch
                        checked={ov.tile_floor === undefined ? r.plyteles_grindys_m2 > 0 : ov.tile_floor}
                        onCheckedChange={v => updatePerRoomTileFloor(r.nr, v)}
                        disabled={recomputing}
                      />
                    </label>
                    <label className="flex items-center gap-1 text-xs">
                      <span className="text-muted-foreground">Sienos dažomos</span>
                      <Switch
                        checked={ov.walls_paint === undefined ? (r.dazymo_plotas_m2 > 0) : (ov.walls_paint > 0)}
                        onCheckedChange={v => updatePerRoomPaint(r.nr, v)}
                        disabled={recomputing}
                      />
                    </label>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

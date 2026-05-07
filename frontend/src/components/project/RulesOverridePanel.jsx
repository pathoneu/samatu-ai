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
import { Loader2, RefreshCw, AlertCircle, Building2, Calculator, ChevronDown, ChevronUp, Library, Check } from 'lucide-react';
import { logCorrection, updateProject } from '@/lib/projectStore';
import { MIN_FLOORS, MAX_FLOORS, getFloorCount } from '@/lib/floorMultiplier';
import { PRESETS, ROOM_DEFAULTS, WASTE_FACTORS, STANDARD_DIMENSIONS } from '@/lib/ltLibrary';
import { recompute as recomputeQuantities } from '@/lib/recomputeApi';
import { API_BASE as API } from '@/lib/apiBase';

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

        // Sprint 0 Fix 2: fire /api/recompute-quantities in parallel when
        // paint_class is present, to update per-room dazai_l / dazai_luboms_l.
        // Only paint_class is wired on the backend today (_VALID_FIELDS).
        // Other override fields go only to /recompute-interior.
        const paintClassChanged = 'paint_class' in newOverrides;
        const quantitiesPromise = paintClassChanged
          ? recomputeQuantities({
              rooms: patalpos,
              edits: [{ field: 'paint_class', new_value: newOverrides.paint_class }],
              current_assumptions: {
                paint_class: project._overrides?.paint_class ?? overrides.paint_class ?? 2,
              },
            }).catch(e => {
              // Non-fatal — /recompute-interior already covers the full recompute.
              // Log but don't surface to the user as a separate error.
              console.warn('[recomputeQuantities] paint_class recompute failed:', e);
              return null;
            })
          : Promise.resolve(null);

        const res = await fetch(`${API}/recompute-interior`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        if (result.status !== 'ok') throw new Error(result._error || 'Recompute klaida');

        // Await quantities result (already resolved or in-flight)
        const quantitiesResult = await quantitiesPromise;

        // Merge per-room dazai_l / dazai_luboms_l from Fix 2 endpoint into the
        // rooms returned by /recompute-interior, if available.
        // Keyed by room index (both arrays share same patalpos order).
        // pozicijos intentionally NOT overwritten — Fix 2 endpoint returns
        // pozicijos:[] today; full pozicijos rebuild lives in /recompute-interior.
        let mergedRooms = result.patalpos || result.v8_rooms || patalpos;
        if (quantitiesResult?.rooms && Array.isArray(quantitiesResult.rooms)) {
          mergedRooms = mergedRooms.map((room, idx) => {
            const qRoom = quantitiesResult.rooms[idx];
            if (!qRoom) return room;
            const patch = {};
            if (qRoom.dazai_l != null)       patch.dazai_l       = qRoom.dazai_l;
            if (qRoom.dazai_luboms_l != null) patch.dazai_luboms_l = qRoom.dazai_luboms_l;
            return Object.keys(patch).length ? { ...room, ...patch } : room;
          });
        }

        // Merge result back into project — preserve all original fields not in result
        const updated = {
          ...project,
          ...result,
          _overrides: newOverrides,
          _per_room_overrides: newPerRoom,
        };
        // Splice in dazai_l-patched rooms (use whichever key the project uses)
        if (result.patalpos) updated.patalpos = mergedRooms;
        if (result.v8_rooms) updated.v8_rooms = mergedRooms;
        // Merge Fix 2 assumptions (e.g. paint_class echo) into project prielaidos
        if (quantitiesResult?.assumptions) {
          updated.prielaidos = { ...(updated.prielaidos || {}), ...quantitiesResult.assumptions };
        }

        onProjectUpdate(updated);
      } catch (e) {
        console.error('Recompute failed:', e);
        setError(e.message || 'Nepavyko perskaičiuoti');
      } finally {
        setRecomputing(false);
      }
    }, 400); // 400ms debounce
  };

  const updateToggle = (key, value) => {
    const old = key in overrides ? overrides[key] : null;
    const next = { ...overrides, [key]: value };
    setOverrides(next);
    triggerRecompute(next, perRoomOverrides);
    logCorrection(project.id, {
      field_path: `rules_override.${key}`, old_value: old, new_value: value,
      source: 'rules_override',
    });
  };

  const updateNumeric = (key, value) => {
    const old = key in overrides ? overrides[key] : null;
    const next = { ...overrides, [key]: value };
    setOverrides(next);
    triggerRecompute(next, perRoomOverrides);
    logCorrection(project.id, {
      field_path: `rules_override.${key}`, old_value: old, new_value: value,
      source: 'rules_override',
    });
  };

  const updatePerRoomTileFloor = (roomNr, tileFloor) => {
    const old = perRoomOverrides[roomNr]?.tile_floor;
    const next = { ...perRoomOverrides, [roomNr]: { ...(perRoomOverrides[roomNr] || {}), tile_floor: tileFloor } };
    setPerRoomOverrides(next);
    triggerRecompute(overrides, next);
    logCorrection(project.id, {
      field_path: `per_room.${roomNr}.tile_floor`, old_value: old, new_value: tileFloor,
      source: 'per_room_override', room_nr: roomNr,
    });
  };

  const updatePerRoomPaint = (roomNr, paint) => {
    const old = perRoomOverrides[roomNr]?.walls_paint;
    const next = { ...perRoomOverrides, [roomNr]: { ...(perRoomOverrides[roomNr] || {}), walls_paint: paint ? 1.0 : 0.0 } };
    setPerRoomOverrides(next);
    triggerRecompute(overrides, next);
    logCorrection(project.id, {
      field_path: `per_room.${roomNr}.walls_paint`, old_value: old, new_value: paint ? 1.0 : 0.0,
      source: 'per_room_override', room_nr: roomNr,
    });
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

      {/* Sprint §2A.1 + §2A.5: Skaičiavimo standartai */}
      <div className="border border-border rounded-xl p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold mb-1">Skaičiavimo standartai</h3>
          <p className="text-xs text-muted-foreground">
            Pažangūs nustatymai accuracy iteracijai. Defaults — LT pro praktika.
          </p>
        </div>

        {/* Angų atimties standartas */}
        <div>
          <div className="text-sm font-medium mb-1.5">Angų atimties standartas</div>
          <div className="text-xs text-muted-foreground mb-2">
            Kaip atimti durų / langų plotą iš dažomo ploto.
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[
              { val: 'LT',   title: 'LT — Lietuvos pramonės įprotis. Atimama kiekviena anga ≥1 m², angokraščiai pridedami prie kiekvieno lango/durų' },
              { val: 'NRM2', title: 'NRM2 — Britanijos standartas (RICS). Smulkios angos (iki 0.5 m²) neatimamos. 0.5–3 m² — atimama, bet angokraščių nepridedam. Virš 3 m² — atimama + pridedami angokraščiai' },
              { val: 'VOB',  title: 'VOB DIN 18363 — Vokietijos standartas. Kaip NRM2, bet angokraščiai pridedami nuo 2.5 m² (ne 3 m²)' },
            ].map(opt => {
              const cur = overrides.paint_deduction_standard || 'LT';
              const active = cur === opt.val;
              return (
                <button
                  key={opt.val}
                  type="button"
                  title={opt.title}
                  onClick={() => updateNumeric('paint_deduction_standard', opt.val)}
                  className="px-3 py-1.5 rounded text-xs font-medium border transition-colors"
                  style={{
                    borderColor: active ? 'hsl(var(--primary))' : 'hsl(var(--border))',
                    background: active ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--card))',
                    color: active ? 'hsl(var(--primary))' : 'hsl(var(--foreground))',
                  }}
                  disabled={recomputing}
                >
                  {opt.val}
                </button>
              );
            })}
          </div>
        </div>

        {/* Glaistymo kokybės lygis (Q1-Q4) — 2026-04-29 added (Sprint §FIX) */}
        <div>
          <div className="text-sm font-medium mb-1.5">Glaistymo kokybės lygis</div>
          <div className="text-xs text-muted-foreground mb-2">
            Pasirinkimas valdo glaisto kiekį (kg/m²) ir šlifavimo darbų apimtį.
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[
              { val: 'Q1', title: 'Q1 — Pagrindinis glaistymas. Po sunkių tapetų, struktūrinių dangos ar betoninio paviršiaus. Storis 0.5–1 mm. Nereikalauja tobulo paviršiaus' },
              { val: 'Q2', title: 'Q2 — Standartinis paruošimas po matiniais dažais. Storis 1–1.5 mm. Lietuvos gyvenamųjų patalpų default — 95% projektų' },
              { val: 'Q3', title: 'Q3 — Aukštesnis paruošimas po pusiau blizgiais dažais ar šviesa krintančiomis sienomis. Storis 1.5–2 mm. Reikalauja kruopštesnio šlifavimo' },
              { val: 'Q4', title: 'Q4 — Premium paruošimas po blizgiais/lakuotais dažais arba salonams. Pilno paviršiaus glaistymas 3–5 mm + 80–120 grit šlifavimas (0.30 h/m²). Brangiausias darbas' },
            ].map(opt => {
              const cur = overrides.glaistas_q_lygis || 'Q2';
              const active = cur === opt.val;
              return (
                <button
                  key={opt.val}
                  type="button"
                  title={opt.title}
                  onClick={() => updateNumeric('glaistas_q_lygis', opt.val)}
                  className="px-3 py-1.5 rounded text-xs font-medium border transition-colors"
                  style={{
                    borderColor: active ? 'hsl(var(--primary))' : 'hsl(var(--border))',
                    background: active ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--card))',
                    color: active ? 'hsl(var(--primary))' : 'hsl(var(--foreground))',
                  }}
                  disabled={recomputing}
                >
                  {opt.val}
                </button>
              );
            })}
          </div>
        </div>

        {/* Dažų klasė */}
        <div>
          <div className="text-sm font-medium mb-1.5">Dažų klasė</div>
          <div className="text-xs text-muted-foreground mb-2">
            Pasirinkimas valdo coats × coverage rate. Default = 2 (LT residential).
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {[
              { val: 1, label: 'Klasė 1', title: 'Aukščiausios kokybės dengiamieji dažai (pvz. Tikkurila Joker, Sikkens Alphalon). Dengiamumas 10 m²/L, pakanka 1 sluoksnio ant paruošto pagrindo' },
              { val: 2, label: 'Klasė 2', title: 'Standartiniai vidaus dažai (pvz. Sikkens Alpha Matt, Dulux Easycare, Sniezka). Dengiamumas 9 m²/L, reikia 2 sluoksnių. Lietuvos gyvenamųjų patalpų default' },
              { val: 3, label: 'Klasė 3', title: 'Ekonomija arba sudėtingas pagrindas (šviežias tinkas, neglaistytos sienos). Dengiamumas 7.5 m²/L, reikia 3 sluoksnių dėl didesnio sugėrimo' },
            ].map(opt => {
              const cur = overrides.paint_class || 2;
              const active = Number(cur) === opt.val;
              return (
                <button
                  key={opt.val}
                  type="button"
                  title={opt.title}
                  onClick={() => updateNumeric('paint_class', opt.val)}
                  className="px-3 py-1.5 rounded text-xs font-medium border transition-colors"
                  style={{
                    borderColor: active ? 'hsl(var(--primary))' : 'hsl(var(--border))',
                    background: active ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--card))',
                    color: active ? 'hsl(var(--primary))' : 'hsl(var(--foreground))',
                  }}
                  disabled={recomputing}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2026-05-06: per user request, removed:
            - SM03 Šablonai (presets) + LibraryViewer
            - SM02 Daugiabučių aukštų pakartojimas
            - QW03 Skaičiavimo formulės card
          Components stay in this file but are not rendered. Re-enable here
          if needed; nothing else imports them. */}

      {/* Per-room overrides — anchor */}
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

// ── SM03: Šablonai (presets) ─────────────────────────────────────────────────
//
// Vienas paspaudimas — visi tipiniai overrides įsijungia. Vartotojas po to
// gali bet ką per-tweak'inti. Match'inimo loginė: jei VISI preset.overrides
// reikšmės dabar lygios overrides[k], tas preset yra "aktyvus".

function presetMatchesCurrent(preset, current) {
  for (const [k, v] of Object.entries(preset.overrides)) {
    if (current[k] !== v) return false;
  }
  return true;
}

function PresetsSection({ currentOverrides, onApplyPreset }) {
  const activeId = PRESETS.find(p => presetMatchesCurrent(p, currentOverrides))?.id;
  return (
    <div className="border border-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Library className="w-4 h-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Šablonai</h3>
        <span className="text-[10px] text-muted-foreground">
          (vienu paspaudimu uždedi tipinius LT nustatymus)
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {PRESETS.map(p => {
          const active = activeId === p.id;
          return (
            <button
              key={p.id}
              onClick={() => onApplyPreset(p.overrides)}
              className={`text-left rounded-lg border p-3 transition-colors ${
                active
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-foreground/30 hover:bg-muted/40'
              }`}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <div className="text-sm font-semibold text-foreground">{p.name}</div>
                {active && <Check className="w-3.5 h-3.5 text-primary" />}
              </div>
              <p className="text-[11px] text-muted-foreground leading-snug">{p.description}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── SM03: Bibliotekos peržiūra (read-only) ──────────────────────────────────

function LibraryViewer() {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Library className="w-4 h-4 text-muted-foreground" />
          LT bibliotekos peržiūra
          <span className="text-[10px] font-normal text-muted-foreground">
            (kas automatiškai įtraukta į skaičiavimus)
          </span>
        </span>
        {open
          ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
          : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      {open && (
        <div className="px-4 py-3 space-y-4 text-xs">
          {/* Per-paskirtis defaults */}
          <div>
            <div className="font-semibold text-foreground mb-1.5">Patalpų tipų numatytieji</div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[11px]">
                <thead>
                  <tr className="text-muted-foreground border-b border-border">
                    <th className="py-1 pr-2 font-medium">Patalpa</th>
                    <th className="py-1 pr-2 font-medium">Sienos</th>
                    <th className="py-1 pr-2 font-medium">Lubos</th>
                    <th className="py-1 pr-2 font-medium">Grindys</th>
                    <th className="py-1 pr-2 font-medium">Plytelės sienose</th>
                    <th className="py-1 font-medium">Pastabos</th>
                  </tr>
                </thead>
                <tbody>
                  {ROOM_DEFAULTS.map(r => (
                    <tr key={r.paskirtis} className="border-b border-border/40 last:border-0">
                      <td className="py-1 pr-2 font-medium">{r.label}</td>
                      <td className="py-1 pr-2 text-muted-foreground">{r.walls}</td>
                      <td className="py-1 pr-2 text-muted-foreground">{r.ceiling}</td>
                      <td className="py-1 pr-2 text-muted-foreground">{r.floor}</td>
                      <td className="py-1 pr-2 text-muted-foreground">{r.tiles_walls}</td>
                      <td className="py-1 text-muted-foreground italic">{r.extras || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Atliekos */}
          <div>
            <div className="font-semibold text-foreground mb-1.5">Atliekų rezervas pagal medžiagą</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-0.5 text-[11px]">
              {WASTE_FACTORS.map(w => (
                <div key={w.material} className="flex justify-between border-b border-border/30 py-0.5">
                  <span className="text-muted-foreground">{w.material}</span>
                  <span className="tabular-nums font-medium">{w.waste_pct}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Standartiniai dydžiai */}
          <div>
            <div className="font-semibold text-foreground mb-1.5">Standartiniai LT angos dydžiai</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
              {STANDARD_DIMENSIONS.map(d => (
                <div key={d.kind} className="flex justify-between border-b border-border/30 py-0.5">
                  <span className="text-muted-foreground">{d.kind}</span>
                  <span className="tabular-nums">
                    {d.wxh} <span className="text-muted-foreground/70">({d.area_m2} m²)</span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="text-[10px] text-muted-foreground/80 pt-1 border-t border-border/40">
            PVM: <strong>21%</strong> · vonia/WC/san. mazgas — hidroizoliacija įtraukiama automatiškai ·
            durys ploto neatima jei &lt; 0.5 m² (RICS NRM2 §29).
          </div>
        </div>
      )}
    </div>
  );
}

// ── SM02: Daugiabučių aukštų pakartojimas ────────────────────────────────────
//
// Vartotojas įkelia 1 tipinio aukšto brėžinį → nurodo "× N aukštų".
// Multipliers laikomi project.prielaidos.aukstu_skaicius. Display + export
// sluoksniuose (PositionsPanel, WorkspacePanel, ExportDropdown) kiekiai
// pagaugina iš lib/floorMultiplier.js. Originalūs duomenys nemutuojami.

function FloorMultiplierSection({ project, onProjectUpdate }) {
  const value = getFloorCount(project);
  const onChange = (n) => {
    const clamped = Math.max(MIN_FLOORS, Math.min(MAX_FLOORS, parseInt(n, 10) || 1));
    const nextPrielaidos = { ...(project.prielaidos || {}), aukstu_skaicius: clamped };
    const nextProject = { ...project, prielaidos: nextPrielaidos };
    updateProject(project.id, nextProject);
    onProjectUpdate?.(nextProject);
    logCorrection(project.id, {
      field_path: 'prielaidos.aukstu_skaicius',
      old_value: value,
      new_value: clamped,
      source: 'floor_multiplier',
    });
  };
  const hint = value > 1
    ? `Visi kiekiai bus padauginti iš ${value} (eksportui ir santraukoms).`
    : 'Tipinis vienbutis. Pakeisk į 2+, jei tas pats brėžinys kartojasi keliuose aukštuose.';
  return (
    <div className="border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Building2 className="w-4 h-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Daugiabučio aukštai</h3>
        {value > 1 && (
          <span className="ml-2 px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">
            × {value} aukštai
          </span>
        )}
      </div>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Tipinio aukšto pakartojimų skaičius</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onChange(value - 1)}
            disabled={value <= MIN_FLOORS}
            className="w-7 h-7 rounded border border-border text-sm hover:bg-muted/40 disabled:opacity-30"
            aria-label="Mažinti"
          >−</button>
          <Input
            type="number"
            value={value}
            min={MIN_FLOORS}
            max={MAX_FLOORS}
            onChange={(e) => onChange(e.target.value)}
            className="h-7 w-14 text-center tabular-nums"
          />
          <button
            onClick={() => onChange(value + 1)}
            disabled={value >= MAX_FLOORS}
            className="w-7 h-7 rounded border border-border text-sm hover:bg-muted/40 disabled:opacity-30"
            aria-label="Didinti"
          >+</button>
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">{hint}</p>
    </div>
  );
}

// ── QW03: Universalios LT skaičiavimo formulės ───────────────────────────────

const Q_LEVEL_KG_PER_M2_MM = { Q1: 0.8, Q2: 1.0, Q3: 1.2, Q4: 1.5 };

function FormulaRow({ name, formula, current, source }) {
  return (
    <li className="space-y-0.5 pb-2 last:pb-0 border-b last:border-0 border-border/40">
      <div className="text-xs font-semibold text-foreground">{name}</div>
      <code className="block text-[11px] text-muted-foreground font-mono whitespace-pre-wrap leading-relaxed">
        {formula}
      </code>
      {current && (
        <div className="text-[11px] text-foreground/80">
          <span className="text-muted-foreground">Su jūsų prielaidomis: </span>
          <span className="font-mono">{current}</span>
        </div>
      )}
      {source && <div className="text-[10px] text-muted-foreground/70">{source}</div>}
    </li>
  );
}

function FormulasCard({ sienosStorisM, glaistimoLygis }) {
  const [open, setOpen] = useState(false);
  const qCoef = Q_LEVEL_KG_PER_M2_MM[glaistimoLygis] ?? 1.0;
  const reveal = (sienosStorisM ?? 0.10).toFixed(2);
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Calculator className="w-4 h-4 text-muted-foreground" />
          Skaičiavimo formulės
          <span className="text-[10px] font-normal text-muted-foreground">
            (kaip kiekvienas skaičius gaunamas)
          </span>
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      {open && (
        <ul className="px-4 py-3 space-y-2">
          <FormulaRow
            name="Sienų dažomas plotas"
            formula="S_neto = perimetras × lubų_aukštis − Σ(angos > 0.5 m²) + lubos"
            source="RICS NRM2 §29 — angos < 0.5 m² neatimamos"
          />
          <FormulaRow
            name="Angokraščiai (langai/durys)"
            formula="ilgis = 2 × H + W;  plotas = ilgis × sienos_storis"
            current={`sienos_storis = ${reveal} m`}
            source="CLAUDE.md §1.2"
          />
          <FormulaRow
            name="Glaistymas"
            formula={`kg = plotas × storis_mm × Q_koef\nQ_koef: Q1=0.8 · Q2=1.0 · Q3=1.2 · Q4=1.5 kg/m²/mm`}
            current={`Q_koef = ${qCoef} (lygis ${glaistimoLygis})`}
            source="CLAUDE.md §1.11"
          />
          <FormulaRow
            name="Dažų kiekis"
            formula="l = (plotas × sluoksniai) / coverage_m²/l\ncoverage: glaistytas Q2 ~9 · šviežias tinkas ~4 · gruntas ~7"
            source="2 sluoksniai = ×1.8 (ne ×2 — pirmas sugeria daugiau)"
          />
          <FormulaRow
            name="Glaistymo kampai"
            formula="kampu_metrai = išorinių_kampų_skaičius × lubų_aukštis"
            source="CLAUDE.md §1.3 — vidaus kampai paprastai be apkalo"
          />
          <FormulaRow
            name="Grindjuostės"
            formula="ilgis = perimetras − Σ(durų_plotis) + 10% atliekų"
            source="CLAUDE.md §1.4"
          />
          <FormulaRow
            name="Lubų perimetras (karnizas)"
            formula="ilgis = perimetras + 5% atliekų  (durys neatimamos)"
            source="CLAUDE.md §1.4"
          />
          <FormulaRow
            name="Užuolaidų nišos"
            formula="L_niša = lango_plotis + 2 × 0.20 m\nplotas = L_niša × niša_gylis × 3 (viršus + 2 šonai)"
            source="CLAUDE.md §1.5"
          />
          <FormulaRow
            name="GK lapai"
            formula="lapai = ⌈sienų_plotas / 3.0⌉ × 1.10  (1 lapas = 1.2×2.5 m, +10% atliekų)"
            source="CLAUDE.md §1.8"
          />
          <FormulaRow
            name="Plytelės (sienos)"
            formula="plotas = plyteliuotos_sienos_ilgis × plytelių_aukštis\natliekos: tiesiai +8% · eglutė +12% · šešiakampis +16%"
            source="CLAUDE.md §1.7 — vonia: paprastai iki 2.0–2.4 m"
          />
          <FormulaRow
            name="Hidroizoliacija (vonia)"
            formula="grindys: visas plotas\nsienos: perimetras × 0.30 m + dušo_zona × lubų_aukštis"
            source="CLAUDE.md §1.12 — dažnai pamirštama!"
          />
        </ul>
      )}
    </div>
  );
}

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, ChevronDown, ChevronUp, Plus, Trash2, Info, Calculator } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { recompute } from '../../lib/recomputeApi';

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
  const { t } = useTranslation();
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
            placeholder={t('project.assumptions.widthPlaceholder')}
          />
          <span className="text-muted-foreground">×</span>
          <Input
            type="number"
            value={item.height_mm}
            onChange={e => handleChange(i, 'height_mm', e.target.value)}
            className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
            placeholder={t('project.assumptions.heightPlaceholder')}
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
        <Plus className="w-3 h-3" /> {t('project.assumptions.add', { label: label.toLowerCase() })}
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AssumptionsPanel({ assumptions, onChange, prielaidos, rawData, pozicijos, onRecomputed, defaultOpen = false, title }) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t('project.assumptions.defaultTitle');
  const [open, setOpen] = useState(defaultOpen);
  const [windowsExpanded, setWindowsExpanded] = useState(false);
  const [doorsExpanded, setDoorsExpanded] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  // 2026-05-06: defensive defaults so a fresh project (assumptions={}) doesn't
  // throw when accessing lubu_auksciai[room.nr] etc.
  const safeAssumptions = assumptions || {};
  // 2026-07-05: the sample/demo project's numbers are hand-authored to look
  // complete, so they don't derive from its rooms — a recompute can't reproduce
  // them and any edit would shift the sąmata. Lock it to a pristine, view-only
  // showcase. Live editing/recompute stays fully functional on real projects.
  const isDemo = !!(rawData?.is_demo);
  const sienos_storis_m = safeAssumptions.sienos_storis_m;
  const glaistimo_lygis = safeAssumptions.glaistimo_lygis;
  const lubu_auksciai = safeAssumptions.lubu_auksciai || {};
  const walls_paint_override = safeAssumptions.walls_paint_override || {};
  const custom_windows = safeAssumptions.custom_windows;
  const custom_doors = safeAssumptions.custom_doors;
  const isFallback = prielaidos?.langai_fallback;

  // Derive display windows list: custom or fallback-suggested or empty
  const displayWindows = custom_windows ?? (
    isFallback ? (prielaidos?.langai_suggested || []) : []
  );

  // Derive display doors list: custom or meta doors
  const metaDoors = rawData?.meta?.doors || [];
  const displayDoors = custom_doors ?? metaDoors;

  const setField = (field, val) => onChange({ ...safeAssumptions, [field]: val });

  const handleRecompute = useCallback(async (field, newValue) => {
    if (!onRecomputed || isDemo) return;  // Skip if parent won't accept results, or on the view-only sample
    setRecomputing(true);
    try {
      const result = await recompute({
        rooms: rawData?.patalpos || [],
        pozicijos: pozicijos || [],
        edits: [{ field, new_value: newValue }],
        current_assumptions: assumptions || {},
        // Reader/extraction context so a ceiling-height edit rebuilds the
        // canonical pozicijos (paint iki/virš split, kampai…) without losing
        // the door/fixture/symbol lines. (2026-06-17 recompute fix.)
        context: {
          _door_types: rawData?._door_types,
          detected_symbols_summary: rawData?.detected_symbols_summary,
          _plyteliu_specs: rawData?._plyteliu_specs,
          bendras_plotas_m2: rawData?.bendras_plotas_m2,
          v9_meta: rawData?.v9_meta,
          _overrides: rawData?._overrides,
        },
      });
      onRecomputed(result);
    } catch (err) {
      console.error('Recompute failed:', err);
      toast.error(t('project.assumptions.toastRecomputeErr', { msg: err.message }));
    } finally {
      setRecomputing(false);
    }
  }, [rawData?.patalpos, pozicijos, assumptions, onRecomputed, t]);

  const setLubuAukstis = (roomNr, val) => {
    const next = { ...safeAssumptions, lubu_auksciai: { ...lubu_auksciai, [roomNr]: val } };
    onChange(next);
    handleRecompute('lubu_auksciai', next.lubu_auksciai);
  };

  // Bulk override — set the same height for ALL rooms at once. Useful when
  // the house has uniform ceilings and the user doesn't want to edit each
  // row individually.
  const setLubuAukstisAll = (val) => {
    const rooms = rawData?.patalpos || [];
    const next_lubu = {};
    rooms.forEach(r => { if (r.nr != null) next_lubu[String(r.nr)] = val; });
    const next = { ...safeAssumptions, lubu_auksciai: next_lubu };
    onChange(next);
    handleRecompute('lubu_auksciai', next_lubu);
  };

  // Per-room finishing override (2026-07-05). Some rooms (garažas, tambūras)
  // default to raw/unpainted walls; when a contractor finishes them the user
  // flips this and the paint quantities recalc live (same path as ceiling height).
  const setWallsPaint = (roomNr, painted) => {
    const next = {
      ...safeAssumptions,
      walls_paint_override: { ...walls_paint_override, [roomNr]: painted ? 1 : 0 },
    };
    onChange(next);
    handleRecompute('walls_paint_override', next.walls_paint_override);
  };
  const isWallsPainted = (room) => {
    const ov = walls_paint_override[room.nr];
    if (ov != null) return Number(ov) >= 0.5;
    return Number(room.walls_paintable_m2 || 0) > 0;
  };

  const rooms = rawData?.patalpos || [];
  const avgH  = rooms.length > 0
    ? rooms.reduce((s, r) => s + (Number(r.lubu_aukstis_m) || 2.80), 0) / rooms.length
    : 2.80;

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Info className="w-4 h-4 text-muted-foreground" />
          {resolvedTitle}
          {isFallback && (
            <Badge className="text-xs bg-amber-500/15 text-amber-300 border-amber-500/30 border font-normal">
              {t('project.assumptions.windowsFallbackBadge')}
            </Badge>
          )}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {open && (
        <div className={`px-4 pb-4 pt-3 space-y-1${isDemo ? ' pointer-events-none' : ''}`}>

          {/* Intro: explain that edits live-recalculate everything in the
              right panel (Kiekiai). On the view-only sample, explain instead
              that these are the AI's assumptions and editing is disabled. */}
          {isDemo ? (
            <div className="flex items-start gap-2 p-3 bg-primary/10 border border-primary/30 rounded-lg mb-3">
              <Info className="w-4 h-4 shrink-0 mt-0.5 text-primary" />
              <p className="text-xs text-foreground leading-relaxed">
                {t('project.assumptions.demoReadonly')}
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
              {t('project.assumptions.intro')}
            </p>
          )}

          {/* Window fallback warning */}
          {isFallback && (
            <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-300 mb-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">{t('project.assumptions.windowsNotFound')}</p>
                <p className="text-xs mt-0.5">
                  {t('project.assumptions.windowsNotFoundDesc')}
                </p>
              </div>
            </div>
          )}

          {/* Sienos storis */}
          <Row
            label={t('project.assumptions.wallThickness')}
            note={t('project.assumptions.wallThicknessNote')}
          >
            <NumberInput
              value={sienos_storis_m}
              onChange={v => { setField('sienos_storis_m', v); handleRecompute('sienos_storis_m', v); }}
              min={0.05} max={0.50} step={0.01} unit="m"
            />
          </Row>

          {/* Glaistymo lygis */}
          <Row
            label={t('project.assumptions.puttyLevel')}
            note={t('project.assumptions.puttyLevelNote')}
          >
            <div className="flex gap-1">
              {['Q1','Q2','Q3','Q4'].map(q => (
                <button
                  key={q}
                  onClick={() => { setField('glaistimo_lygis', q); handleRecompute('glaistimo_lygis', q); }}
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
              <p className="text-sm text-foreground mb-1">
                {t('project.assumptions.ceilingHeightLabel')}<span className="text-xs text-muted-foreground">{t('project.assumptions.ceilingHeightDefault', { avg: avgH.toFixed(2) })}</span>
              </p>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                {t('project.assumptions.ceilingHeightNote')}
              </p>

              {/* 2026-05-06: bulk override — set all rooms' aukštis at once.
                  Works for the common case where the whole house has the same
                  height; user can then tweak individual rooms below if needed. */}
              <div className="mb-3 flex items-center gap-2 px-2 py-2 rounded-md bg-muted/40 border border-border/60">
                <span className="text-xs font-medium text-foreground flex-1">
                  {t('project.assumptions.allRooms')}
                </span>
                <Input
                  type="number"
                  defaultValue=""
                  placeholder={avgH.toFixed(2)}
                  min={2.0} max={6.0} step={0.05}
                  onBlur={e => {
                    const v = parseFloat(e.target.value);
                    if (Number.isFinite(v) && v >= 1.5 && v <= 8.0) {
                      setLubuAukstisAll(v);
                      e.target.value = '';
                    }
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.target.blur();
                    }
                  }}
                  className="h-7 w-20 text-xs bg-card border-border text-right tabular-nums"
                  title={t('project.assumptions.allRoomsTitle')}
                />
                <span className="text-xs text-muted-foreground">m</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => (
                  <div key={room.nr} className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground truncate flex-1" title={room.pavadinimas}>
                      {room.pavadinimas || room.nr}
                    </span>
                    <Input
                      type="number"
                      value={lubu_auksciai[room.nr] ?? (Number(room.lubu_aukstis_m) || 2.80)}
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

          {/* Sienų apdaila per kambarį — dažomos vs nedažomos (2026-07-05).
              Garažas/tambūras pagal nutylėjimą nedažomi; užbaigtiems projektams
              vartotojas perjungia ir kiekiai persiskaičiuoja gyvai. */}
          {rooms.length > 0 && (
            <div className="py-2">
              <p className="text-sm text-foreground mb-1">
                {t('project.assumptions.wallsPaintLabel')}
              </p>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                {t('project.assumptions.wallsPaintNote')}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => {
                  const painted = isWallsPainted(room);
                  return (
                    <button
                      key={room.nr}
                      onClick={() => setWallsPaint(room.nr, !painted)}
                      title={room.pavadinimas}
                      className={`flex items-center justify-between gap-1.5 px-2 py-1.5 rounded text-xs border transition-colors ${
                        painted
                          ? 'bg-primary/10 border-primary/40 text-foreground'
                          : 'bg-card border-border text-muted-foreground hover:border-foreground/30'
                      }`}
                    >
                      <span className="truncate">{room.pavadinimas || room.nr}</span>
                      <span className={`shrink-0 text-[10px] font-medium ${painted ? 'text-primary' : 'text-muted-foreground'}`}>
                        {painted ? t('project.assumptions.wallsPaintOn') : t('project.assumptions.wallsPaintOff')}
                      </span>
                    </button>
                  );
                })}
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
                {t('project.assumptions.windows')}
                <span className="text-xs text-muted-foreground ml-2">
                  {t('project.assumptions.windowsCount', { count: displayWindows.length })}
                  {isFallback && !custom_windows && <span className="text-amber-600 ml-1">{t('project.assumptions.windowsFallback')}</span>}
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
                onChange={wins => { setField('custom_windows', wins); handleRecompute('custom_windows', wins); }}
                label={t('project.assumptions.windowLabel')}
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
                {t('project.assumptions.doors')}
                <span className="text-xs text-muted-foreground ml-2">{t('project.assumptions.doorsCount', { count: displayDoors.length })}</span>
              </span>
              {doorsExpanded
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              }
            </button>
            {doorsExpanded && (
              <OpeningEditor
                items={displayDoors}
                onChange={ds => { setField('custom_doors', ds); handleRecompute('custom_doors', ds); }}
                label={t('project.assumptions.doorLabel')}
                defaultItem={{ width_mm: 800, height_mm: 2200 }}
              />
            )}
          </div>

          {recomputing && (
            <p className="text-xs text-muted-foreground pt-1">
              {t('project.assumptions.recomputing')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Calculation formulas card (Phase 14 / QW03) ──────────────────────────────
//
// Surfaces the universal LT interior formulas applied to this project.
// Values from the current Prielaidos panel are plugged in so the user can see
// exactly which numbers their toggles change. Sources: CLAUDE.md §1.

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
      {source && (
        <div className="text-[10px] text-muted-foreground/70">{source}</div>
      )}
    </li>
  );
}

function FormulasCard({ sienosStorisM, glaistimoLygis }) {
  const [open, setOpen] = useState(false);
  const qCoef = Q_LEVEL_KG_PER_M2_MM[glaistimoLygis] ?? 1.0;
  const reveal = (sienosStorisM ?? 0).toFixed(2);

  return (
    <div className="mt-3 border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <Calculator className="w-3.5 h-3.5 text-muted-foreground" />
          Skaičiavimo formulės
          <span className="text-[10px] font-normal text-muted-foreground">
            (kaip kiekvienas skaičius gaunamas)
          </span>
        </span>
        {open
          ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
          : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
      </button>

      {open && (
        <ul className="px-3 py-2 space-y-2">
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
            source="2 sluoksniai = ×1.8 (ne ×2 — pirmas sluoksnis sugeria daugiau)"
          />
          <FormulaRow
            name="Glaistymo kampai"
            formula="kampų_metrai = išorinių_kampų_skaičius × lubų_aukštis"
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
            formula="L_niša = lango_plotis + 2 × 0.20 m\nplotas = L_niša × nišos_gylis × 3 (viršus + 2 šonai)"
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

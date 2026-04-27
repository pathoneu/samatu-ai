/**
 * ProjectMainView — pagrindinis projekto puslapis (Sprint 1).
 *
 * VIENAS ekranas:
 *   ┌───────────────────────────────────────────────────────┐
 *   │  Projekto info  · Bendra suma €  · [Eksportuoti ▾]    │  ← sticky top
 *   ├───────────────────────────────────────────────────────┤
 *   │  Patalpų suvestinė (collapsible)                      │
 *   │     12 patalpų · 132 m²                                │
 *   │  ▾ Atidaryti (rodo per kambarį detales)                │
 *   ├───────────────────────────────────────────────────────┤
 *   │  Darbų sąrašas (grupuotas pagal skyrius)               │
 *   │     Sienų darbai                                       │
 *   │       - Sienų lyginimas Rotband      350 m²  7 €  2450│
 *   │       - Sienų dažymas                350 m²  ...      │
 *   │     Lubų darbai                                        │
 *   │       - GKP lubos                    130 m²  ...      │
 *   ├───────────────────────────────────────────────────────┤
 *   │  [Žiūrėti brėžinį →]   [Pridėti darbų eilutę]          │
 *   └───────────────────────────────────────────────────────┘
 */

import { useState, useMemo } from 'react';
import {
  Home, ChevronDown, ChevronUp, Eye, Plus, FileText,
  Edit2, Check, X, Trash2, AlertCircle, Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import ExportDropdown from './ExportDropdown';
import SanityWarningsBanner from './SanityWarningsBanner';

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(val, d = 1) {
  if (val == null) return '—';
  return Number(val).toLocaleString('lt-LT', { maximumFractionDigits: d });
}
function fmtEur(val) {
  if (val == null) return '—';
  return `${Number(val).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

// ── Group darbų sąrašą pagal skyrius ─────────────────────────────────────────

function groupByCategory(darbu_sarasas) {
  const groups = {};
  (darbu_sarasas || []).forEach(item => {
    const cat = item.skyrius || item.kategorija || 'Kiti darbai';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  });
  return groups;
}

// ── Vienas darbo eilutės redaktorius (inline) ────────────────────────────────

function WorkRow({ item, onChange, onRemove }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    aprasymas: item.aprasymas || '',
    kiekis: item.kiekis || 0,
    kaina: item.kaina || 0,
  });

  const suma = (Number(draft.kiekis) || 0) * (Number(draft.kaina) || 0);
  const itemSuma = (item.kiekis || 0) * (item.kaina || 0);

  const handleSave = () => {
    onChange({
      ...item,
      aprasymas: draft.aprasymas,
      kiekis: parseFloat(draft.kiekis) || 0,
      kaina: parseFloat(draft.kaina) || 0,
      suma: (parseFloat(draft.kiekis) || 0) * (parseFloat(draft.kaina) || 0),
    });
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({
      aprasymas: item.aprasymas || '',
      kiekis: item.kiekis || 0,
      kaina: item.kaina || 0,
    });
    setEditing(false);
  };

  if (editing) {
    return (
      <tr className="bg-muted/30">
        <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
        <td className="px-3 py-2">
          <input type="text" value={draft.aprasymas}
            onChange={e => setDraft({...draft, aprasymas: e.target.value})}
            className="w-full px-2 py-1 border border-border bg-background rounded text-sm" />
        </td>
        <td className="px-3 py-2 text-xs text-muted-foreground">{item.mato_vnt || ''}</td>
        <td className="px-3 py-2">
          <input type="number" step="0.01" value={draft.kiekis}
            onChange={e => setDraft({...draft, kiekis: e.target.value})}
            className="w-20 px-2 py-1 border border-border bg-background rounded text-sm text-right tabular-nums" />
        </td>
        <td className="px-3 py-2">
          <input type="number" step="0.01" value={draft.kaina}
            onChange={e => setDraft({...draft, kaina: e.target.value})}
            className="w-20 px-2 py-1 border border-border bg-background rounded text-sm text-right tabular-nums" />
        </td>
        <td className="px-3 py-2 text-right text-sm font-semibold tabular-nums">
          {fmtEur(suma)}
        </td>
        <td className="px-3 py-2 text-right">
          <button onClick={handleSave}
            className="p-1 hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400 rounded mr-1">
            <Check className="w-3.5 h-3.5" />
          </button>
          <button onClick={handleCancel}
            className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-700 dark:text-red-400 rounded">
            <X className="w-3.5 h-3.5" />
          </button>
        </td>
      </tr>
    );
  }

  const noPrice = !item.kaina;

  // ── Šaltinio indikatorius (Diena 4) ─────────────────────────────────────
  // detected=true → AI Vision rado iš brėžinio (žalias dot, "AI")
  // detected=false → fallback vidurkis (geltonas dot, "vidurkis")
  // confidence high (geom) → mėlynas dot, "geom"
  let sourceDot = null;
  if (item.detected === true) {
    if (item.confidence === 'high') {
      sourceDot = (
        <span title={`Geometrija — ${item.source || 'tikslus'}`}
          className="inline-flex items-center gap-1 text-[10px] text-blue-700 dark:text-blue-300">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
          geom
        </span>
      );
    } else {
      sourceDot = (
        <span title={`AI Vision rado iš brėžinio — ${item.source || ''}`}
          className="inline-flex items-center gap-1 text-[10px] text-emerald-700 dark:text-emerald-300">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          AI
        </span>
      );
    }
  } else if (item.detected === false) {
    sourceDot = (
      <span title={`AI nerado, naudojam vidurkį — ${item.source || ''}`}
        className="inline-flex items-center gap-1 text-[10px] text-amber-700 dark:text-amber-300">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        vidurkis
      </span>
    );
  }

  return (
    <tr className="hover:bg-muted/30 group transition-colors">
      <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
      <td className="px-3 py-2 text-sm text-foreground">
        <div className="flex items-center gap-2 flex-wrap">
          <span>{item.aprasymas}</span>
          {sourceDot}
          {item.confidence === 'low' && !item.detected && (
            <Badge variant="outline" className="text-[10px] py-0 h-4 border-amber-300 text-amber-700">
              tikrink
            </Badge>
          )}
        </div>
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{item.mato_vnt || ''}</td>
      <td className="px-3 py-2 text-sm text-foreground text-right tabular-nums">{fmt(item.kiekis)}</td>
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {item.kaina
          ? fmtEur(item.kaina)
          : <span className="text-muted-foreground italic">įvesk</span>}
      </td>
      <td className="px-3 py-2 text-sm font-semibold text-right tabular-nums">
        {item.kaina ? fmtEur(itemSuma) : '—'}
      </td>
      <td className="px-3 py-2 text-right opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={() => setEditing(true)}
          className="p-1 hover:bg-muted rounded text-muted-foreground" title="Redaguoti">
          <Edit2 className="w-3.5 h-3.5" />
        </button>
        {onRemove && (
          <button onClick={() => onRemove(item)}
            className="p-1 hover:bg-red-50 dark:hover:bg-red-900/30 text-red-600 rounded ml-1" title="Šalinti">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </td>
    </tr>
  );
}

// ── Pagrindinis komponentas ──────────────────────────────────────────────────

export default function ProjectMainView({ project, onProjectChange, onShowDrawing }) {
  const [darbai, setDarbai] = useState(project.darbu_sarasas || []);
  const [patalposExpanded, setPatalposExpanded] = useState(false);

  const grouped = useMemo(() => groupByCategory(darbai), [darbai]);
  const categories = Object.keys(grouped);

  const totals = useMemo(() => {
    let darbo = 0, medz = 0, count = 0;
    darbai.forEach(it => {
      const suma = (it.kiekis || 0) * (it.kaina || 0);
      darbo += suma;
      count++;
    });
    return { darbo, medz, viso: darbo + medz, count };
  }, [darbai]);

  const totalArea = useMemo(() => {
    const rooms = project.v8_rooms || project.patalpos || [];
    return rooms.reduce((s, r) => s + (r.plotas_m2 || 0), 0);
  }, [project]);

  const handleRowChange = (idx, newItem) => {
    const updated = [...darbai];
    updated[idx] = newItem;
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  const handleRowRemove = (idx) => {
    const updated = darbai.filter((_, i) => i !== idx);
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  const handleAddRow = () => {
    const next = {
      eil_nr: darbai.length + 1,
      aprasymas: 'Nauja eilutė',
      mato_vnt: 'm2',
      kiekis: 0,
      kaina: 0,
      skyrius: 'Kiti darbai',
    };
    const updated = [...darbai, next];
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  const projectWithDarbai = { ...project, darbu_sarasas: darbai };

  return (
    <div className="space-y-4">
      {/* TOP STICKY — Projekto suvestinė + Eksportas */}
      <div className="sticky top-0 z-10 bg-background pt-2 pb-3 -mx-1 px-1">
        <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            {/* Left: stats */}
            <div className="flex items-center gap-6 flex-wrap">
              <div>
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
                  Bendra suma (be PVM)
                </div>
                <div className="text-2xl font-semibold tabular-nums text-foreground">
                  {fmtEur(totals.viso)}
                </div>
              </div>
              <div className="border-l border-border pl-6">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium">
                  Su PVM ({project.vat_rate || 21}%)
                </div>
                <div className="text-base font-medium tabular-nums text-foreground/80">
                  {fmtEur(totals.viso * (1 + (project.vat_rate || 21) / 100))}
                </div>
              </div>
              <div className="border-l border-border pl-6 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs">
                <span className="text-muted-foreground">Patalpos:</span>
                <strong className="text-foreground tabular-nums">
                  {(project.v8_rooms || project.patalpos || []).length}
                </strong>
                <span className="text-muted-foreground">Plotas:</span>
                <strong className="text-foreground tabular-nums">{fmt(totalArea)} m²</strong>
                <span className="text-muted-foreground">Pozicijų:</span>
                <strong className="text-foreground tabular-nums">{totals.count}</strong>
                {project.archetipas && (
                  <>
                    <span className="text-muted-foreground">Tipas:</span>
                    <strong className="text-foreground capitalize">
                      {project.archetipas.replace(/_/g, ' ')}
                    </strong>
                  </>
                )}
              </div>
            </div>

            {/* Right: re-extract + export */}
            <div className="flex items-center gap-2">
              <ReextractButton project={project} onComplete={onProjectChange} />
              <ExportDropdown project={projectWithDarbai} />
            </div>
          </div>

          {/* Trūksta kainų — perspėjimas */}
          {totals.viso === 0 && darbai.length > 0 && (
            <div className="mt-3 flex items-start gap-2 p-2.5 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-lg text-xs text-amber-900 dark:text-amber-200">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <div>
                <strong>Kainos neįvestos.</strong> Spauskite ant kainos stulpelio bet kurioje eilutėje
                ir įveskite €/vnt — bendra suma atsinaujins automatiškai.
                Kainynų automatinis užpildymas — ateinančioje versijoje.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* LT sanity warnings — Sprint 2: vartotojas mato kur AI gali būti suklydęs */}
      {project.lt_sanity && (
        <SanityWarningsBanner sanity={project.lt_sanity} />
      )}

      {/* AI _meta — transparency: laikas, tokenai, zoom statistikos */}
      {project._meta && (
        <details className="text-xs text-muted-foreground -mt-2 group">
          <summary className="cursor-pointer hover:text-foreground select-none inline-flex items-center gap-2">
            <span>AI ekstrakcijos detalės</span>
            {project._meta.elapsed_s && (
              <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                {Math.round(project._meta.elapsed_s)}s
              </span>
            )}
            {project._meta.zoom_applied !== undefined && (
              <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                zoom {project._meta.zoom_applied}/{project._meta.zoom_attempted || 0}
              </span>
            )}
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 p-3 bg-muted/30 rounded text-[11px] tabular-nums">
            {project._meta.elapsed_s != null && <><span>Trukmė:</span><span>{project._meta.elapsed_s}s</span></>}
            {project._meta.input_tokens != null && <><span>Input tokenai:</span><span>{project._meta.input_tokens.toLocaleString()}</span></>}
            {project._meta.output_tokens != null && <><span>Output tokenai:</span><span>{project._meta.output_tokens.toLocaleString()}</span></>}
            {project._meta.cache_read_tokens != null && project._meta.cache_read_tokens > 0 && (
              <><span>Cache hit:</span><span>{project._meta.cache_read_tokens.toLocaleString()} ({(project._meta.cache_read_tokens / (project._meta.input_tokens || 1) * 100).toFixed(0)}%)</span></>
            )}
            {project._meta.zoom_attempted != null && <><span>Zoom call'ai:</span><span>{project._meta.zoom_applied} / {project._meta.zoom_attempted}</span></>}
            {project._meta.zoom_elapsed_s != null && <><span>Zoom trukmė:</span><span>{project._meta.zoom_elapsed_s}s</span></>}
            {project._meta.pages_sent != null && <><span>Puslapiai:</span><span>{project._meta.pages_sent}</span></>}
            {project._meta.model && <><span>Modelis:</span><span>{project._meta.model}</span></>}
            {project._meta.input_tokens != null && (() => {
              // Rough cost estimate at $5/M input + $25/M output for Opus 4.7
              const cost = (project._meta.input_tokens || 0) * 0.000005 +
                           (project._meta.output_tokens || 0) * 0.000025 -
                           (project._meta.cache_read_tokens || 0) * 0.0000045;  // 90% discount on cache reads
              return <><span>~Kaina:</span><span>${cost.toFixed(2)}</span></>;
            })()}
          </div>
        </details>
      )}

      {/* AI rasti simboliai (Diena 4) — kuriose brėžiniuose ką AI Vision aptiko */}
      {(() => {
        const sym = project.v9_meta?.symbols_detected
                  || project.detected_symbols_summary
                  || (project.detected_symbols?.by_type
                      ? Object.fromEntries(
                          Object.entries(project.detected_symbols.by_type)
                            .map(([k, v]) => [k, v.total]))
                      : null);
        if (!sym || Object.keys(sym).length === 0) return null;

        const SYM_LABELS = {
          rozetes: 'Rozetės',
          jungikliai: 'Jungikliai',
          sviestuvai: 'Šviestuvai',
          pakabinami_sviestuvai: 'Pakabinami šviestuvai',
          led_juostos: 'LED juostos (m)',
          difuzoriai: 'Difūzoriai',
          klozetai: 'Klozetai',
          praustuvai: 'Praustuvai',
          vonios: 'Vonios',
          trapai: 'Trapai',
          maisytuvai: 'Maišytuvai',
          gyvatukai: 'Gyvatukai',
          skalbimo_masinos: 'Skalbimo mašinos',
          radiatoriai: 'Radiatoriai',
          durys: 'Durys',
          langai: 'Langai',
        };

        return (
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-4 h-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                AI brėžinyje rasti simboliai
              </h3>
              <Badge variant="secondary" className="text-[10px] font-normal">
                {Object.values(sym).reduce((a, b) => a + (b || 0), 0)} viso
              </Badge>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2 text-xs">
              {Object.entries(sym)
                .filter(([, v]) => v && v > 0)
                .sort(([, a], [, b]) => b - a)
                .map(([k, v]) => (
                  <div key={k} className="flex items-baseline justify-between border-b border-border/40 pb-1">
                    <span className="text-muted-foreground truncate pr-2">{SYM_LABELS[k] || k}</span>
                    <strong className="text-foreground tabular-nums">{v}</strong>
                  </div>
                ))}
            </div>
          </div>
        );
      })()}

      {/* PATALPŲ SUVESTINĖ — collapsible */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <button
          onClick={() => setPatalposExpanded(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Home className="w-4 h-4 text-muted-foreground" />
            Patalpų suvestinė
            <Badge variant="secondary" className="text-xs font-normal">
              {(project.v8_rooms || project.patalpos || []).length} patalpų · {fmt(totalArea)} m²
            </Badge>
          </span>
          {patalposExpanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </button>

        {patalposExpanded && (
          <div className="border-t border-border p-3">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground border-b border-border">
                  <tr>
                    <th className="px-2 py-1.5 text-left font-medium">Nr</th>
                    <th className="px-2 py-1.5 text-left font-medium">Pavadinimas</th>
                    <th className="px-2 py-1.5 text-left font-medium">Paskirtis</th>
                    <th className="px-2 py-1.5 text-right font-medium">Plotas m²</th>
                    <th className="px-2 py-1.5 text-right font-medium">Perim. m</th>
                    <th className="px-2 py-1.5 text-right font-medium">Lubos m</th>
                  </tr>
                </thead>
                <tbody>
                  {(project.v8_rooms || project.patalpos || []).map((r, i) => (
                    <tr key={i} className="border-b border-border/40 last:border-0 hover:bg-muted/20">
                      <td className="px-2 py-1.5 text-xs text-muted-foreground tabular-nums">{r.nr}</td>
                      <td className="px-2 py-1.5 text-foreground">{r.pavadinimas}</td>
                      <td className="px-2 py-1.5 text-xs text-muted-foreground">{r.paskirtis}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.plotas_m2)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.perimetras_m)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.lubu_aukstis_m, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* DARBŲ SĄRAŠAS — grupuotas pagal skyrius */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <FileText className="w-4 h-4 text-muted-foreground" />
            Darbų ir medžiagų sąrašas
            <Badge variant="secondary" className="text-xs font-normal">
              {darbai.length} pozicijų
            </Badge>
          </h2>
          <Button variant="outline" size="sm" onClick={handleAddRow} className="gap-1.5 h-8 text-xs">
            <Plus className="w-3.5 h-3.5" />
            Pridėti eilutę
          </Button>
        </div>

        {darbai.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            Darbų sąrašas tuščias. Spauskite „Pridėti eilutę".
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-muted-foreground border-b border-border bg-muted/20">
                <tr>
                  <th className="px-3 py-2 text-left font-medium w-12">Nr</th>
                  <th className="px-3 py-2 text-left font-medium">Aprašymas</th>
                  <th className="px-3 py-2 text-left font-medium w-20">Vnt</th>
                  <th className="px-3 py-2 text-right font-medium w-24">Kiekis</th>
                  <th className="px-3 py-2 text-right font-medium w-24">€/vnt</th>
                  <th className="px-3 py-2 text-right font-medium w-28">Suma €</th>
                  <th className="w-16" />
                </tr>
              </thead>
              <tbody>
                {categories.map(cat => (
                  <>
                    <tr key={`cat-${cat}`} className="bg-muted/40">
                      <td colSpan={7} className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-foreground">
                        {cat}
                      </td>
                    </tr>
                    {grouped[cat].map((item) => {
                      const idx = darbai.indexOf(item);
                      return (
                        <WorkRow
                          key={`${item.eil_nr}-${idx}`}
                          item={item}
                          onChange={(newItem) => handleRowChange(idx, newItem)}
                          onRemove={() => handleRowRemove(idx)}
                        />
                      );
                    })}
                  </>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/20">
                <tr>
                  <td colSpan={5} className="px-3 py-2.5 text-right text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    VISO be PVM:
                  </td>
                  <td className="px-3 py-2.5 text-right text-base font-bold tabular-nums text-foreground">
                    {fmtEur(totals.viso)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* Bottom actions */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        {onShowDrawing && (
          <Button variant="outline" onClick={onShowDrawing} className="gap-2">
            <Eye className="w-4 h-4" />
            Žiūrėti brėžinį
          </Button>
        )}
        <p className="text-xs text-muted-foreground">
          AI tikslumas ~85–95%. Patikrink ir pataisyk reikšmes prieš eksportuodamas.
        </p>
      </div>
    </div>
  );
}

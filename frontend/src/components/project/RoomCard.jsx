/**
 * RoomCard — per kambarį detali kortelė su inline edit.
 *
 * Rodo:
 * - Patalpos pavadinimą, paskirtį
 * - Plotą, perimetrą, lubų aukštį
 * - Dažomas plotas, sienos, lubos
 * - Plytelės sienose, plytelės grindyse
 * - Kampai, grindjuostės
 * - Inline edit: paskirtis, plotas, lubų aukštis
 *
 * Spaudžiant edit ikoną — atveria modal su detalesniais pasirinkimais.
 */

import { useState } from 'react';
import { Edit2, Check, X, AlertCircle, Eye, BookOpen, Palette, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { getPdfBlob } from '@/lib/pdfStore';

// ── Confidence dot (žalia/geltona/raudona) ────────────────────────────────────

function ConfidenceDot({ level, hint }) {
  if (!level) return null;
  const colors = {
    high:   'bg-green-500',
    medium: 'bg-yellow-400',
    low:    'bg-red-500',
  };
  const titles = {
    high:   'Aukšto patikimumo (vertė skaityta tiesiogiai iš brėžinio)',
    medium: 'Vidutinio patikimumo (apskaičiuota iš dalinių duomenų)',
    low:    'Žemo patikimumo (numatyta iš defaults — patikrink!)',
  };
  return (
    <span
      title={hint || titles[level]}
      className={`inline-block w-1.5 h-1.5 rounded-full ${colors[level]} shrink-0 ml-1`}
    />
  );
}

// Confidence per reikšmę. Pirma — bandom backend'o `confidence` (jei extractor
// grąžino) + `plotas_saltinis` / `lubu_aukstis_saltinis` source tags. Fallback —
// senesnė heuristika iš reikšmių šaltinio.
function getFieldConfidence(room, field) {
  const val = room?.[field];
  if (val == null) return null;

  // Priority 1: backend per-room `confidence` from new extractor
  const backendConf = room?.confidence;

  // Priority 2: source tag — eksplikacija/section_pjuvis = high; default_fallback = low
  if (field === 'plotas_m2' && room?.plotas_saltinis) {
    const src = room.plotas_saltinis;
    if (src === 'eksplikacija' || src === 'inline_label') return 'high';
    if (src === 'wall_dim_calc') return backendConf || 'medium';
    if (src === 'default_fallback') return 'low';
  }
  if (field === 'lubu_aukstis_m' && room?.lubu_aukstis_saltinis) {
    const src = room.lubu_aukstis_saltinis;
    if (src === 'section_pjuvis') return 'high';
    if (src === 'ceiling_plan_annotation') return backendConf || 'medium';
    if (src === 'default_fallback') return 'low';
  }

  if (field === 'plotas_m2') {
    if (val <= 0) return 'low';
    return backendConf || 'medium';
  }

  if (field === 'perimetras_m') {
    if (val <= 0) return 'low';
    // _zoom_changes proves perimetras was zoom-refined
    const zoomChanges = room?._zoom_changes || [];
    if (zoomChanges.some(c => c.startsWith('perimetras'))) return 'high';
    const plotas = room.plotas_m2 || 0;
    if (plotas > 0) {
      const aprox = 4.18 * Math.sqrt(plotas);
      if (Math.abs(val - aprox) / aprox < 0.05) return 'medium';
    }
    return backendConf || 'high';
  }

  if (field === 'lubu_aukstis_m') {
    if (Math.abs(val - 2.82) < 0.01) return 'medium';  // default reikšmė
    return 'high';
  }

  return 'medium';
}

const PASKIRTIS_OPTIONS = [
  { value: 'gyvenamoji', label: 'Gyvenamoji' },
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

function getPaskirtisInfo(paskirtis) {
  return PASKIRTIS_OPTIONS.find(o => o.value === paskirtis)
    || { value: paskirtis, label: paskirtis };
}

export default function RoomCard({ room, onChange, onRemove, onShowOnPdf, project, onJumpToPage }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    pavadinimas: room.pavadinimas || '',
    paskirtis: room.paskirtis || 'gyvenamoji',
    plotas_m2: room.plotas_m2 || 0,
    perimetras_m: room.perimetras_m || 0,
    lubu_aukstis_m: room.lubu_aukstis_m || 2.82,
  });

  const info = getPaskirtisInfo(room.paskirtis);

  const handleSave = () => {
    onChange?.({
      ...room,
      ...draft,
      plotas_m2: parseFloat(draft.plotas_m2) || 0,
      perimetras_m: parseFloat(draft.perimetras_m) || 0,
      lubu_aukstis_m: parseFloat(draft.lubu_aukstis_m) || 2.82,
    });
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({
      pavadinimas: room.pavadinimas || '',
      paskirtis: room.paskirtis || 'gyvenamoji',
      plotas_m2: room.plotas_m2 || 0,
      perimetras_m: room.perimetras_m || 0,
      lubu_aukstis_m: room.lubu_aukstis_m || 2.82,
    });
    setEditing(false);
  };

  // Skaičiuojami kiekiai (iš V8 backend'o)
  const dazymo = room.dazymo_plotas_m2 || 0;
  const sienos = room.walls_paintable_m2 || 0;
  const lubos = room.ceiling_paintable_m2 || 0;
  const kampai = room.kampai_m || 0;
  const plytSienos = room.plyteles_sienos_m2 || 0;
  const plytGrindys = room.plyteles_grindys_m2 || 0;
  const grindjuostes = room.grindjuostes_m || 0;
  const isHigh = (room.lubu_aukstis_m || 2.82) > 3.0;

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          {editing ? (
            <input
              type="text"
              value={draft.pavadinimas}
              onChange={e => setDraft({ ...draft, pavadinimas: e.target.value })}
              className="border border-stone-300 rounded px-2 py-1 text-sm font-semibold w-44"
            />
          ) : (
            <div className="min-w-0">
              <div className="font-semibold text-stone-800 truncate">
                <span className="text-xs font-mono text-stone-400 mr-1.5">#{room.nr}</span>
                {room.pavadinimas}
              </div>
              <div className="text-xs text-stone-500 mt-0.5">{info.label}</div>
            </div>
          )}
        </div>
        <div className="flex gap-1">
          {editing ? (
            <>
              <button onClick={handleSave}
                className="p-1.5 hover:bg-green-50 text-green-600 rounded">
                <Check className="w-4 h-4" />
              </button>
              <button onClick={handleCancel}
                className="p-1.5 hover:bg-red-50 text-red-600 rounded">
                <X className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              {onShowOnPdf && room.puslapio_nr && (
                <button onClick={() => onShowOnPdf(room.puslapio_nr, room)}
                  className="p-1.5 hover:bg-blue-50 text-blue-600 rounded"
                  title={`Rodyti brėžinyje (psl. ${room.puslapio_nr})`}>
                  <Eye className="w-4 h-4" />
                </button>
              )}
              <button onClick={() => setEditing(true)}
                className="p-1.5 hover:bg-stone-100 text-stone-500 rounded">
                <Edit2 className="w-4 h-4" />
              </button>
              {onRemove && (
                <button onClick={() => onRemove(room)}
                  className="p-1.5 hover:bg-red-50 text-red-600 rounded">
                  <X className="w-4 h-4" />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Pagrindiniai dydžiai */}
      <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
        <div>
          <div className="text-stone-500 mb-0.5 flex items-center">
            Plotas
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'plotas_m2')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.plotas_m2}
              onChange={e => setDraft({ ...draft, plotas_m2: e.target.value })}
              className="border border-stone-300 rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-stone-800 flex items-center gap-1">
              {dazymo > 0 || room.plotas_m2 ? `${room.plotas_m2} m²` : '—'}
              {room.plotas_saltinis === 'eksplikacija' && (
                <span
                  title="Plotas paimtas iš eksplikacijos lentelės (ground-truth)"
                  className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"
                />
              )}
            </div>
          )}
        </div>
        <div>
          <div className="text-stone-500 mb-0.5 flex items-center">
            Perimetras
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'perimetras_m')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.perimetras_m}
              onChange={e => setDraft({ ...draft, perimetras_m: e.target.value })}
              className="border border-stone-300 rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-stone-800">{room.perimetras_m ? `${room.perimetras_m} m` : '—'}</div>
          )}
        </div>
        <div>
          <div className="text-stone-500 mb-0.5 flex items-center">
            Lubos H
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'lubu_aukstis_m')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.lubu_aukstis_m}
              onChange={e => setDraft({ ...draft, lubu_aukstis_m: e.target.value })}
              className="border border-stone-300 rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-stone-800">{room.lubu_aukstis_m || 2.82} m</div>
          )}
        </div>
      </div>

      {editing && (
        <div className="mb-3">
          <div className="text-xs text-stone-500 mb-1">Paskirtis</div>
          <select value={draft.paskirtis}
            onChange={e => setDraft({ ...draft, paskirtis: e.target.value })}
            className="w-full border border-stone-300 rounded px-2 py-1.5 text-sm">
            {PASKIRTIS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Kiekiai */}
      {!editing && (
        <div className="border-t border-stone-100 pt-3 space-y-1.5 text-sm">
          {dazymo > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Dažomas plotas</span>
              <span className="font-medium text-stone-800">{dazymo.toFixed(2)} m²</span>
            </div>
          )}
          {sienos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-stone-500">└ Sienos (neto)</span>
              <span className="text-stone-600">{sienos.toFixed(2)} m²</span>
            </div>
          )}
          {lubos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-stone-500">└ Lubos {isHigh ? '(virš 3m)' : ''}</span>
              <span className="text-stone-600">{lubos.toFixed(2)} m²</span>
            </div>
          )}
          {kampai > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Dažymo kampai</span>
              <span className="font-medium text-stone-800">{kampai.toFixed(2)} m</span>
            </div>
          )}
          {plytSienos > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės sienose</span>
              <span className="font-medium text-stone-800">{plytSienos.toFixed(2)} m²</span>
            </div>
          )}
          {plytGrindys > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės grindyse</span>
              <span className="font-medium text-stone-800">{plytGrindys.toFixed(2)} m²</span>
            </div>
          )}
          {grindjuostes > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Grindjuostės</span>
              <span className="font-medium text-stone-800">{grindjuostes.toFixed(2)} m</span>
            </div>
          )}
        </div>
      )}

      {/* Warning jei garažas/tambūras (nedažoma) */}
      {!editing && (room.paskirtis === 'garazas' || room.paskirtis === 'tambūras') && (
        <div className="mt-3 flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{info.label} — pagal industries standartą NEDAŽOMA. Pakeiskite paskirtį, jei norite įtraukti.</span>
        </div>
      )}

      {/* High ceiling badge */}
      {!editing && isHigh && (
        <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 text-xs rounded-full">
          Virš 3m — atskira pozicija
        </div>
      )}

      {/* Designer material specs — on-demand extraction (Sprint E3) */}
      {!editing && project?.id && (
        <DesignerMaterialSpecs room={room} project={project} />
      )}

      {/* Eksplikacija row anchor — ground-truth source widget (replaces unreliable bbox overlay) */}
      {!editing && room.eksplikacija_row_idx != null && (
        <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 text-[11px] rounded-full border border-emerald-200 dark:border-emerald-800">
          <BookOpen className="w-3 h-3" />
          <span>Iš eksplikacijos eil. #{room.eksplikacija_row_idx}</span>
          {project?._eksplikacija?.eksplikacija_source_page && onJumpToPage && (
            <button
              onClick={(e) => { e.stopPropagation(); onJumpToPage(project._eksplikacija.eksplikacija_source_page); }}
              className="ml-1 underline hover:text-emerald-600"
            >
              psl. {project._eksplikacija.eksplikacija_source_page}
            </button>
          )}
        </div>
      )}

      {/* Skaičiavimo paaiškinimas — collapsible. Vartotojui matosi formulė
          + iš brėžinio perskaityti matmenys. Backend'o vidiniai laukai
          (_zoom_changes ir kt.) pateikiami draugiškai. */}
      {!editing && ((room._zoom_changes?.length > 0) || room.calculation_trace) && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none">
            {room._zoom_changes?.length > 0
              ? `Patikslinti ${room._zoom_changes.length} matmuo${room._zoom_changes.length === 1 ? '' : 's'} pagal brėžinį`
              : 'Skaičiavimo paaiškinimas'}
          </summary>
          <div className="mt-2 p-2 bg-muted/30 rounded space-y-1.5">
            {room._zoom_changes?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Pataisymai pagal brėžinį:</div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {room._zoom_changes.map((c, i) => (
                    <li key={i} className="text-muted-foreground">{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {room.calculation_trace && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Skaičiavimas:</div>
                <code className="block text-[11px] text-muted-foreground whitespace-pre-wrap">
                  {room.calculation_trace}
                </code>
              </div>
            )}
            {room._zoom?.matmenys_perskaityti?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Iš brėžinio perskaityti matmenys (mm):</div>
                <div className="text-muted-foreground">
                  {room._zoom.matmenys_perskaityti.join(', ')}
                </div>
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}


// ── Designer material specs viewer (on-demand, Sprint E3) ────────────────────
//
// Click → POST PDF blob + room_nr to backend → Vision extracts paint/tiles/
// flooring spec for THIS room → cached on project. Second click is free.

function DesignerMaterialSpecs({ room, project }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // Read cached value from project if present
  const cached = project?._material_specs?.[room.nr] || null;
  const [specs, setSpecs] = useState(cached);

  const handleFetch = async () => {
    if (specs) {
      setOpen(o => !o);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const blob = await getPdfBlob(project.id);
      if (!blob) throw new Error('PDF nepasiekiamas (nesaugotas)');
      const fd = new FormData();
      fd.append('files', blob, 'project.pdf');
      fd.append('room_nr', room.nr);
      const res = await fetch(`/api/projects/${project.id}/material-specs`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setSpecs(data);
      setOpen(true);
    } catch (e) {
      setError(e.message || 'Klaida');
    } finally {
      setLoading(false);
    }
  };

  // Handles all 4 spec types — null-safe rendering
  const hasAny = specs && (
    specs.paint || specs.sienos_plyteles || specs.grindys_plyteles || specs.grindys_medines
  );

  return (
    <div className="mt-2">
      <button
        onClick={handleFetch}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-violet-50 dark:bg-violet-950/30 text-violet-700 dark:text-violet-300 text-[11px] rounded-full border border-violet-200 dark:border-violet-800 hover:bg-violet-100 dark:hover:bg-violet-950/50 transition-colors disabled:opacity-50"
        title="Ištraukti dizainerio specifikuotas medžiagas (~$0.20)"
      >
        {loading
          ? <Loader2 className="w-3 h-3 animate-spin" />
          : <Palette className="w-3 h-3" />}
        <span>Dizainerio medžiagos</span>
        {specs && (open
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />)}
      </button>

      {error && (
        <div className="mt-1 text-[11px] text-destructive">{error}</div>
      )}

      {open && specs && (
        <div className="mt-2 p-2 bg-violet-50/50 dark:bg-violet-950/20 border border-violet-200/50 dark:border-violet-800/50 rounded text-[11px] space-y-1.5">
          {!hasAny && (
            <div className="text-muted-foreground italic">
              Dizainerio specifikacijų puslapyje nerasta — projekte gali nebūti
              dedicated „spalvos" lapo šiai patalpai.
            </div>
          )}
          {specs.paint && (
            <div>
              <div className="font-medium text-violet-900 dark:text-violet-200">Dažai</div>
              <div className="text-violet-800 dark:text-violet-300">
                {[specs.paint.brand, specs.paint.code, specs.paint.name]
                  .filter(Boolean).join(' — ')}
                {specs.paint.where && (
                  <span className="text-muted-foreground"> ({specs.paint.where})</span>
                )}
              </div>
            </div>
          )}
          {specs.sienos_plyteles && (
            <div>
              <div className="font-medium text-violet-900 dark:text-violet-200">Sienų plytelės</div>
              <div className="text-violet-800 dark:text-violet-300">
                {[specs.sienos_plyteles.brand, specs.sienos_plyteles.model]
                  .filter(Boolean).join(' ')}
                {specs.sienos_plyteles.size_mm && (
                  <span> · {specs.sienos_plyteles.size_mm}</span>
                )}
                {specs.sienos_plyteles.storis_mm && (
                  <span> · {specs.sienos_plyteles.storis_mm}mm</span>
                )}
              </div>
            </div>
          )}
          {specs.grindys_plyteles && (
            <div>
              <div className="font-medium text-violet-900 dark:text-violet-200">Grindų plytelės</div>
              <div className="text-violet-800 dark:text-violet-300">
                {[specs.grindys_plyteles.brand, specs.grindys_plyteles.model]
                  .filter(Boolean).join(' ')}
                {specs.grindys_plyteles.size_mm && (
                  <span> · {specs.grindys_plyteles.size_mm}</span>
                )}
                {specs.grindys_plyteles.storis_mm && (
                  <span> · {specs.grindys_plyteles.storis_mm}mm</span>
                )}
              </div>
            </div>
          )}
          {specs.grindys_medines && (
            <div>
              <div className="font-medium text-violet-900 dark:text-violet-200">Grindys (parketas / laminatas)</div>
              <div className="text-violet-800 dark:text-violet-300">
                {[specs.grindys_medines.brand, specs.grindys_medines.model]
                  .filter(Boolean).join(' ')}
                {specs.grindys_medines.supplier && (
                  <span className="text-muted-foreground"> · gamintojas: {specs.grindys_medines.supplier}</span>
                )}
              </div>
            </div>
          )}
          {specs._meta?.pages_inspected && (
            <div className="text-[10px] text-muted-foreground/80 pt-1 border-t border-violet-200/50 dark:border-violet-800/50">
              Šaltinis: psl. {specs._meta.pages_inspected.join(', ')}{specs._cached && ' · cache'}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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
import { Edit2, Check, X, AlertCircle, Eye } from 'lucide-react';

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

export default function RoomCard({ room, onChange, onRemove, onShowOnPdf }) {
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
            <div className="font-semibold text-stone-800">{dazymo > 0 || room.plotas_m2 ? `${room.plotas_m2} m²` : '—'}</div>
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
              <span className="font-medium text-stone-800">{dazymo.toFixed(1)} m²</span>
            </div>
          )}
          {sienos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-stone-500">└ Sienos (neto)</span>
              <span className="text-stone-600">{sienos.toFixed(1)} m²</span>
            </div>
          )}
          {lubos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-stone-500">└ Lubos {isHigh ? '(virš 3m)' : ''}</span>
              <span className="text-stone-600">{lubos.toFixed(1)} m²</span>
            </div>
          )}
          {kampai > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Dažymo kampai</span>
              <span className="font-medium text-stone-800">{kampai.toFixed(1)} m</span>
            </div>
          )}
          {plytSienos > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės sienose</span>
              <span className="font-medium text-stone-800">{plytSienos.toFixed(1)} m²</span>
            </div>
          )}
          {plytGrindys > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės grindyse</span>
              <span className="font-medium text-stone-800">{plytGrindys.toFixed(1)} m²</span>
            </div>
          )}
          {grindjuostes > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Grindjuostės</span>
              <span className="font-medium text-stone-800">{grindjuostes.toFixed(1)} m</span>
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

      {/* Zoom audit trail + calculation_trace — transparency from Phase 8 */}
      {!editing && ((room._zoom_changes?.length > 0) || room.calculation_trace) && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none">
            {room._zoom_changes?.length > 0
              ? `Zoom patikslino ${room._zoom_changes.length} reikšmę${room._zoom_changes.length === 1 ? '' : 's'}`
              : 'Skaičiavimo formulė'}
          </summary>
          <div className="mt-2 p-2 bg-muted/30 rounded space-y-1.5">
            {room._zoom_changes?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Zoom pataisymai:</div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {room._zoom_changes.map((c, i) => (
                    <li key={i} className="text-muted-foreground">{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {room.calculation_trace && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Formulė:</div>
                <code className="block text-[11px] text-muted-foreground whitespace-pre-wrap">
                  {room.calculation_trace}
                </code>
              </div>
            )}
            {room._zoom?.matmenys_perskaityti?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">Vision perskaityti mm:</div>
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

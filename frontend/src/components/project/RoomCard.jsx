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
import { useTranslation } from 'react-i18next';
import { Edit2, Check, X, AlertCircle, Eye, BookOpen, Palette, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { getPdfBlob } from '@/lib/pdfStore';
import ConfidenceBadge from './ConfidenceBadge';
import { API_BASE } from '@/lib/apiBase';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

// ── Confidence dot (žalia/geltona/raudona) ────────────────────────────────────

function ConfidenceDot({ level, hint }) {
  const { t } = useTranslation();
  if (!level) return null;
  const colors = {
    high:   'bg-green-500',
    medium: 'bg-yellow-400',
    low:    'bg-red-500',
  };
  const emojis = { high: '🟢', medium: '🟡', low: '🔴' };
  const titles = {
    high:   t('project.roomCard.confHigh'),
    medium: t('project.roomCard.confMedium'),
    low:    t('project.roomCard.confLow'),
  };
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full ${colors[level]} shrink-0 ml-1 cursor-help`}
        />
      </TooltipTrigger>
      <TooltipContent side="top">
        {hint || `${emojis[level]} ${titles[level]}`}
      </TooltipContent>
    </Tooltip>
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
    if (src === 'eksplikacija' || src === 'inline_label' || src === 'plano_uzrasas') return 'high';
    if (src === 'wall_dim_calc') return backendConf || 'medium';
    if (src === 'default_fallback') return 'low';
  }
  if (field === 'lubu_aukstis_m' && room?.lubu_aukstis_saltinis) {
    const src = room.lubu_aukstis_saltinis;
    if (src === 'section_pjuvis') return 'high';
    // Altitudė, atspausdinta PAČIOJE patalpoje lubų plane ir priskirta
    // deterministiškai (point-in-polygon) — skaityta tiesiai iš brėžinio.
    if (src === 'ceiling_plan_marker') return 'high';
    if (src === 'plano_uzrasas') return 'high';   // the plan's own „H - 2820" statement, read from the PDF text
    if (src === 'ceiling_plan_annotation') return backendConf || 'medium';
    if (src === 'default_fallback') return 'low';
  }

  if (field === 'plotas_m2') {
    if (val <= 0) return 'low';
    return backendConf || 'medium';
  }

  if (field === 'perimetras_m') {
    if (val <= 0) return 'low';
    // 2026-09-19: the geometry lane says where the figure came from. Wall
    // lengths READ from the plan and added up (or a pair of them, the table,
    // his own entry) are the drawing's word; the outline's length and an open
    // plan's share are estimates the check sheet asks him to accept.
    const perimSrc = room?.perimetras_saltinis;
    if (['matmenu_eilutes', 'plano_matmenys', 'eksplikacija', 'user_override', 'manual'].includes(perimSrc)) return 'high';
    if (['konturo_ivertis', 'atviros_erdves_ivertis'].includes(perimSrc)) return 'medium';
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

// Room-purpose options. `label` resolves against i18n at render
// (project.roomCard.paskirtis.<value>).
// 2026-08-23: the list offered 14 of the backend's 22 classes, so a room the
// AI misnamed as e.g. a sauna or a terrace could not be corrected by hand —
// the correction workflow was blocked for exactly the classes the vocabulary
// sweep introduced. Values must match universal_rules.ROOM_TYPE_RULES keys.
const PASKIRTIS_VALUES = [
  'gyvenamoji', 'miegamoji', 'virtuve', 'valgomasis', 'kabinetas',
  'vonia', 'wc', 'san', 'pirtis', 'baseinas',
  'koridorius', 'holas', 'laiptine', 'tambūras',
  'drabuzine', 'rubine', 'sandeliukas', 'skalbykla',
  'garazas', 'katiline', 'techpatalpa', 'terasa',
];

// Resolve the display label for a room purpose via i18n; unknown values pass
// through unchanged (matches the previous getPaskirtisInfo fallback).
function paskirtisLabel(t, paskirtis) {
  if (PASKIRTIS_VALUES.includes(paskirtis)) {
    return t(`project.roomCard.paskirtis.${paskirtis}`);
  }
  return paskirtis;
}

export default function RoomCard({ room, onChange, onRemove, onShowOnPdf, project, onJumpToPage }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    pavadinimas: room.pavadinimas || '',
    paskirtis: room.paskirtis || 'gyvenamoji',
    plotas_m2: room.plotas_m2 || 0,
    perimetras_m: room.perimetras_m || 0,
    lubu_aukstis_m: room.lubu_aukstis_m || 2.82,
  });

  const info = { value: room.paskirtis, label: paskirtisLabel(t, room.paskirtis) };

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
  const angokrasciaiM2 = room.angokrasciai_m2 || 0;
  const angokrasciaiLm = room.angokrasciai_lm || 0;
  const pasleptosKompl = room.pasleptu_duru_kompl || 0;
  const pasleptosStaktosM = room.pasleptu_duru_staktu_m || 0;
  const isHigh = (room.lubu_aukstis_m || 2.82) > 3.0;

  return (
    <div className="bg-card border border-border rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          {editing ? (
            <input
              type="text"
              value={draft.pavadinimas}
              onChange={e => setDraft({ ...draft, pavadinimas: e.target.value })}
              className="border border-input rounded px-2 py-1 text-sm font-semibold w-44"
            />
          ) : (
            <div className="min-w-0">
              <div className="font-semibold text-foreground truncate">
                <span className="text-xs font-mono text-muted-foreground/70 mr-1.5">#{room.nr}</span>
                {room.pavadinimas}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                <span>{info.label}</span>
                <ConfidenceBadge
                  room={room}
                  projectId={project?.id}
                  onClick={() => onShowOnPdf?.(room.puslapio_nr, room)}
                />
              </div>
            </div>
          )}
        </div>
        <div className="flex gap-1">
          {editing ? (
            <>
              <button onClick={handleSave}
                className="p-1.5 hover:bg-emerald-500/10 text-emerald-400 rounded">
                <Check className="w-4 h-4" />
              </button>
              <button onClick={handleCancel}
                className="p-1.5 hover:bg-red-500/10 text-red-400 rounded">
                <X className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              {onShowOnPdf && room.puslapio_nr && (
                <button onClick={() => onShowOnPdf(room.puslapio_nr, room)}
                  className="p-1.5 hover:bg-blue-500/10 text-blue-400 rounded"
                  title={t('project.roomCard.showOnDrawingTitle', { page: room.puslapio_nr })}>
                  <Eye className="w-4 h-4" />
                </button>
              )}
              <button onClick={() => setEditing(true)}
                className="p-1.5 hover:bg-muted text-muted-foreground rounded">
                <Edit2 className="w-4 h-4" />
              </button>
              {onRemove && (
                <button onClick={() => onRemove(room)}
                  className="p-1.5 hover:bg-red-500/10 text-red-400 rounded">
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
          <div className="text-muted-foreground mb-0.5 flex items-center">
            {t('project.roomCard.area')}
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'plotas_m2')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.plotas_m2}
              onChange={e => setDraft({ ...draft, plotas_m2: e.target.value })}
              className="border border-input rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-foreground flex items-center gap-1">
              {dazymo > 0 || room.plotas_m2 ? `${room.plotas_m2} m²` : '—'}
              {room.plotas_saltinis === 'eksplikacija' && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 cursor-help"
                    />
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    {t('project.roomCard.areaSourceTooltip')}
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          )}
        </div>
        <div>
          <div className="text-muted-foreground mb-0.5 flex items-center">
            {t('project.roomCard.perimeter')}
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'perimetras_m')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.perimetras_m}
              onChange={e => setDraft({ ...draft, perimetras_m: e.target.value })}
              className="border border-input rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-foreground">{room.perimetras_m ? `${room.perimetras_m} m` : '—'}</div>
          )}
        </div>
        <div>
          <div className="text-muted-foreground mb-0.5 flex items-center">
            {t('project.roomCard.ceilingH')}
            {!editing && <ConfidenceDot level={getFieldConfidence(room, 'lubu_aukstis_m')} />}
          </div>
          {editing ? (
            <input type="number" step="0.01" value={draft.lubu_aukstis_m}
              onChange={e => setDraft({ ...draft, lubu_aukstis_m: e.target.value })}
              className="border border-input rounded px-1.5 py-1 w-full text-sm" />
          ) : (
            <div className="font-semibold text-foreground">{room.lubu_aukstis_m || 2.82} m</div>
          )}
        </div>
      </div>

      {editing && (
        <div className="mb-3">
          <div className="text-xs text-muted-foreground mb-1">{t('project.roomCard.purpose')}</div>
          <select value={draft.paskirtis}
            onChange={e => setDraft({ ...draft, paskirtis: e.target.value })}
            className="w-full border border-input rounded px-2 py-1.5 text-sm">
            {PASKIRTIS_VALUES.map(v => (
              <option key={v} value={v}>{t(`project.roomCard.paskirtis.${v}`)}</option>
            ))}
          </select>
        </div>
      )}

      {/* Kiekiai */}
      {!editing && (
        <div className="border-t border-border pt-3 space-y-1.5 text-sm">
          {dazymo > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('project.roomCard.paintArea')}</span>
              <span className="font-medium text-foreground">{dazymo.toFixed(2)} m²</span>
            </div>
          )}
          {sienos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-muted-foreground">{t('project.roomCard.wallsNet')}</span>
              <span className="text-muted-foreground">{sienos.toFixed(2)} m²</span>
            </div>
          )}
          {lubos > 0 && (
            <div className="flex justify-between text-xs pl-3">
              <span className="text-muted-foreground">{t('project.roomCard.ceiling')}{isHigh ? t('project.roomCard.over3m') : ''}</span>
              <span className="text-muted-foreground">{lubos.toFixed(2)} m²</span>
            </div>
          )}
          {kampai > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('project.roomCard.paintCorners')}</span>
              <span className="font-medium text-foreground">{kampai.toFixed(2)} m</span>
            </div>
          )}
          {plytSienos > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('project.roomCard.wallTiles')}</span>
              <span className="font-medium text-foreground">{plytSienos.toFixed(2)} m²</span>
            </div>
          )}
          {plytGrindys > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('project.roomCard.floorTiles')}</span>
              <span className="font-medium text-foreground">{plytGrindys.toFixed(2)} m²</span>
            </div>
          )}
          {grindjuostes > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">{t('project.roomCard.baseboards')}</span>
              <span className="font-medium text-foreground">{grindjuostes.toFixed(2)} m</span>
            </div>
          )}
          {angokrasciaiM2 > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground" title={t('project.roomCard.revealsTitle')}>
                {t('project.roomCard.reveals')}
              </span>
              <span className="font-medium text-foreground">
                {angokrasciaiM2.toFixed(2)} m² <span className="text-muted-foreground/70 text-xs">({angokrasciaiLm.toFixed(2)} m)</span>
              </span>
            </div>
          )}
          {pasleptosKompl > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground" title={t('project.roomCard.hiddenDoorsTitle')}>
                {t('project.roomCard.hiddenDoors')}
              </span>
              <span className="font-medium text-foreground">
                {pasleptosKompl}{t('project.roomCard.kompl')}<span className="text-muted-foreground/70 text-xs">({pasleptosStaktosM.toFixed(2)}{t('project.roomCard.framesM')})</span>
              </span>
            </div>
          )}
        </div>
      )}

      {/* Warning jei garažas/tambūras (nedažoma) */}
      {!editing && (room.paskirtis === 'garazas' || room.paskirtis === 'tambūras') && (
        <div className="mt-3 flex items-start gap-2 p-2 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-300">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{t('project.roomCard.notPaintedWarn', { label: info.label })}</span>
        </div>
      )}

      {/* High ceiling badge */}
      {!editing && isHigh && (
        <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 bg-purple-500/10 text-purple-300 text-xs rounded-full border border-purple-500/30">
          {t('project.roomCard.highCeilingBadge')}
        </div>
      )}

      {/* Designer material specs — on-demand extraction (Sprint E3) */}
      {!editing && project?.id && (
        <DesignerMaterialSpecs room={room} project={project} />
      )}

      {/* Eksplikacija row anchor — ground-truth source widget (replaces unreliable bbox overlay) */}
      {!editing && room.eksplikacija_row_idx != null && (
        <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 text-[11px] rounded-full border border-emerald-200">
          <BookOpen className="w-3 h-3" />
          <span>{t('project.roomCard.eksRowPrefix', { idx: room.eksplikacija_row_idx })}</span>
          {project?._eksplikacija?.eksplikacija_source_page && onJumpToPage && (
            <button
              onClick={(e) => { e.stopPropagation(); onJumpToPage(project._eksplikacija.eksplikacija_source_page); }}
              className="ml-1 underline hover:text-emerald-600"
            >
              {t('project.roomCard.eksPage', { page: project._eksplikacija.eksplikacija_source_page })}
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
              ? (room._zoom_changes.length === 1
                  ? t('project.roomCard.refinedSingular', { count: room._zoom_changes.length })
                  : t('project.roomCard.refinedPlural', { count: room._zoom_changes.length }))
              : t('project.roomCard.calcExplanation')}
          </summary>
          <div className="mt-2 p-2 bg-muted/30 rounded space-y-1.5">
            {room._zoom_changes?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">{t('project.roomCard.adjustments')}</div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {room._zoom_changes.map((c, i) => (
                    <li key={i} className="text-muted-foreground">{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {room.calculation_trace && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">{t('project.roomCard.calculation')}</div>
                <code className="block text-[11px] text-muted-foreground whitespace-pre-wrap">
                  {room.calculation_trace}
                </code>
              </div>
            )}
            {room._zoom?.matmenys_perskaityti?.length > 0 && (
              <div>
                <div className="font-medium text-foreground/80 mb-1">{t('project.roomCard.readDimensions')}</div>
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
  const { t } = useTranslation();
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
      if (!blob) throw new Error(t('project.roomCard.pdfUnavailable'));
      const fd = new FormData();
      fd.append('files', blob, 'project.pdf');
      fd.append('room_nr', room.nr);
      const res = await fetch(`${API_BASE}/api/projects/${project.id}/material-specs`, {
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
      setError(e.message || t('project.roomCard.error'));
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
        className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-violet-50 text-violet-700 text-[11px] rounded-full border border-violet-200 hover:bg-violet-100 transition-colors disabled:opacity-50"
        title={t('project.roomCard.designerMaterialsTitle')}
      >
        {loading
          ? <Loader2 className="w-3 h-3 animate-spin" />
          : <Palette className="w-3 h-3" />}
        <span>{t('project.roomCard.designerMaterials')}</span>
        {specs && (open
          ? <ChevronUp className="w-3 h-3" />
          : <ChevronDown className="w-3 h-3" />)}
      </button>

      {error && (
        <div className="mt-1 text-[11px] text-destructive">{error}</div>
      )}

      {open && specs && (
        <div className="mt-2 p-2 bg-violet-50/50 border border-violet-200/50 rounded text-[11px] space-y-1.5">
          {!hasAny && (
            <div className="text-muted-foreground italic">
              {t('project.roomCard.noDesignerSpecs')}
            </div>
          )}
          {specs.paint && (
            <div>
              <div className="font-medium text-violet-900">{t('project.roomCard.specPaint')}</div>
              <div className="text-violet-800">
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
              <div className="font-medium text-violet-900">{t('project.roomCard.specWallTiles')}</div>
              <div className="text-violet-800">
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
              <div className="font-medium text-violet-900">{t('project.roomCard.specFloorTiles')}</div>
              <div className="text-violet-800">
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
              <div className="font-medium text-violet-900">{t('project.roomCard.specWoodFloor')}</div>
              <div className="text-violet-800">
                {[specs.grindys_medines.brand, specs.grindys_medines.model]
                  .filter(Boolean).join(' ')}
                {specs.grindys_medines.supplier && (
                  <span className="text-muted-foreground">{t('project.roomCard.specSupplier', { supplier: specs.grindys_medines.supplier })}</span>
                )}
              </div>
            </div>
          )}
          {specs._meta?.pages_inspected && (
            <div className="text-[10px] text-muted-foreground/80 pt-1 border-t border-violet-200/50">
              {t('project.roomCard.specSource', { pages: specs._meta.pages_inspected.join(', ') })}{specs._cached && t('project.roomCard.specCache')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

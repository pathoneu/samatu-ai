import React, { useState, useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Home, Layers, Paintbrush, Square, AlertCircle, ChevronDown, ChevronUp,
  Zap, Droplets, Lightbulb, CornerUpRight, Ruler, Package, Droplet,
  AlertTriangle, ShieldAlert, FileText, X, CheckCircle2,
} from 'lucide-react';
import AssumptionsPanel from '@/components/project/AssumptionsPanel';
import { calculateInteriorQuantities, DEFAULT_ASSUMPTIONS } from '@/lib/interiorCalc';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(val, decimals = 1) {
  if (val == null) return '—';
  if (typeof val !== 'number') return String(val);
  return val.toLocaleString('lt-LT', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

function heightLabel(mm) {
  if (!mm) return '—';
  return `${(mm / 1000).toLocaleString('lt-LT', { minimumFractionDigits: 2 })} m`;
}

// ── Confidence indicator ──────────────────────────────────────────────────────

function ConfidenceDot({ level }) {
  if (!level) return null;
  const map = {
    high:   { color: 'bg-green-500',  title: 'Aukštas: vertė perskaityta tiesiogiai iš matmenų' },
    medium: { color: 'bg-yellow-400', title: 'Vidutinis: apskaičiuota iš dalinių duomenų' },
    low:    { color: 'bg-red-500',    title: 'Žemas: spėjama pagal standartus (patikrink!)' },
  };
  const c = map[level];
  if (!c) return null;
  return (
    <span
      title={c.title}
      className={`inline-block w-2.5 h-2.5 rounded-full ${c.color} shrink-0`}
    />
  );
}

// ── Tab bar ───────────────────────────────────────────────────────────────────

function TabBar({ tab, setTab, hasPages }) {
  const tabs = [
    { id: 'kiekiai',    label: 'Kiekiai' },
    { id: 'prielaidos', label: 'Prielaidos' },
    ...(hasPages ? [{ id: 'puslapiai', label: 'Puslapiai' }] : []),
  ];
  return (
    <div className="flex gap-1 border-b border-border pb-0 mb-5">
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => setTab(t.id)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            tab === t.id
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Collapsible section ───────────────────────────────────────────────────────

function Section({ icon: Icon, title, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          {Icon && <Icon className="w-4 h-4 text-muted-foreground" />}
          {title}
          {badge != null && (
            <Badge variant="secondary" className="text-xs font-normal">{badge}</Badge>
          )}
        </span>
        {open
          ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
          : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      {open && <div className="px-4 pb-4 pt-3">{children}</div>}
    </div>
  );
}

// ── Simple label-value row ────────────────────────────────────────────────────

function QtyRow({ label, value, unit }) {
  if (value == null) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm tabular-nums text-foreground/80">
        {fmt(value)}{unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
      </span>
    </div>
  );
}

// ── Main calculation card ─────────────────────────────────────────────────────

function CalcCard({ color, title, mainValue, mainUnit, breakdown, extra, note, confidence }) {
  const colorMap = {
    blue:   { bg: 'bg-blue-50 dark:bg-blue-950/30',   border: 'border-blue-200 dark:border-blue-800',   text: 'text-blue-700 dark:text-blue-300',   num: 'text-blue-900 dark:text-blue-100' },
    amber:  { bg: 'bg-amber-50 dark:bg-amber-950/30',  border: 'border-amber-200 dark:border-amber-800',  text: 'text-amber-700 dark:text-amber-300',  num: 'text-amber-900 dark:text-amber-100' },
    green:  { bg: 'bg-green-50 dark:bg-green-950/30',  border: 'border-green-200 dark:border-green-800',  text: 'text-green-700 dark:text-green-300',  num: 'text-green-900 dark:text-green-100' },
    purple: { bg: 'bg-purple-50 dark:bg-purple-950/30', border: 'border-purple-200 dark:border-purple-800', text: 'text-purple-700 dark:text-purple-300', num: 'text-purple-900 dark:text-purple-100' },
    teal:   { bg: 'bg-teal-50 dark:bg-teal-950/30',   border: 'border-teal-200 dark:border-teal-800',   text: 'text-teal-700 dark:text-teal-300',   num: 'text-teal-900 dark:text-teal-100' },
    rose:   { bg: 'bg-rose-50 dark:bg-rose-950/30',   border: 'border-rose-200 dark:border-rose-800',   text: 'text-rose-700 dark:text-rose-300',   num: 'text-rose-900 dark:text-rose-100' },
    indigo: { bg: 'bg-indigo-50 dark:bg-indigo-950/30', border: 'border-indigo-200 dark:border-indigo-800', text: 'text-indigo-700 dark:text-indigo-300', num: 'text-indigo-900 dark:text-indigo-100' },
  };
  const c = colorMap[color] || colorMap.blue;

  return (
    <Card className={`border ${c.border} ${c.bg}`}>
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <p className={`text-xs font-semibold uppercase tracking-wide ${c.text}`}>{title}</p>
          <ConfidenceDot level={confidence} />
        </div>
        <div className="flex items-baseline gap-1 mb-3">
          <span className={`text-3xl font-bold tabular-nums ${c.num}`}>
            {mainValue != null ? fmt(mainValue) : '—'}
          </span>
          {mainValue != null && mainUnit && (
            <span className={`text-base font-medium ${c.text}`}>{mainUnit}</span>
          )}
        </div>
        {extra}
        {breakdown && breakdown.length > 0 && (
          <div className="space-y-1 border-t border-current/10 pt-2 mt-1">
            {breakdown.map(({ label, value, unit }, i) => value != null && (
              <div key={i} className="flex justify-between items-baseline">
                <span className={`text-xs ${c.text} opacity-80`}>{label}</span>
                <span className={`text-xs font-semibold tabular-nums ${c.num}`}>
                  {fmt(value)} {unit}
                </span>
              </div>
            ))}
          </div>
        )}
        {note && (
          <p className={`text-xs mt-2 opacity-60 ${c.text} leading-tight`}>{note}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────────

function Toggle({ label, value, onChange }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
        value
          ? 'bg-amber-100 border-amber-300 text-amber-800 dark:bg-amber-900/40 dark:border-amber-600 dark:text-amber-300'
          : 'bg-card border-border text-muted-foreground hover:border-foreground/30'
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${value ? 'bg-amber-500' : 'bg-muted-foreground'}`} />
      {label}
    </button>
  );
}

// ── Finish type color chip ────────────────────────────────────────────────────

function finishColor(tipas) {
  const t = (tipas || '').toLowerCase();
  if (t.includes('daž')) return 'bg-blue-50 text-blue-700 border-blue-200';
  if (t.includes('plytel')) return 'bg-amber-50 text-amber-700 border-amber-200';
  if (t.includes('medi') || t.includes('plokšt') || t.includes('lukšt')) return 'bg-green-50 text-green-700 border-green-200';
  if (t.includes('tapet')) return 'bg-purple-50 text-purple-700 border-purple-200';
  if (t.includes('veidrod')) return 'bg-sky-50 text-sky-700 border-sky-200';
  if (t.includes('tekstil')) return 'bg-rose-50 text-rose-700 border-rose-200';
  return 'bg-gray-50 text-gray-700 border-gray-200';
}

// ── Room card ─────────────────────────────────────────────────────────────────

function RoomCard({ room }) {
  const apdaila = room.sienu_apdaila || [];
  const uniqueFinishes = [...new Set(apdaila.map(a => a.tipas).filter(Boolean))];
  return (
    <Card className="border border-border bg-card">
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="text-xs font-mono text-muted-foreground">{room.nr}</span>
            <p className="text-sm font-semibold leading-tight mt-0.5">{room.pavadinimas}</p>
          </div>
          <span className="text-sm font-bold whitespace-nowrap">{fmt(room.plotas_m2)} m²</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Layers className="w-3 h-3 shrink-0" />
          {heightLabel(room.lubu_aukstis_mm)}
          {room.lubu_tipas && <span>· {room.lubu_tipas}</span>}
        </div>
        {room.grindu_danga && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Square className="w-3 h-3 shrink-0" />
            {room.grindu_danga}
          </div>
        )}
        {uniqueFinishes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {uniqueFinishes.map(t => (
              <span key={t} className={`px-1.5 py-0.5 rounded border text-xs font-medium ${finishColor(t)}`}>
                {t}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function InteriorProject({ project, onAssumptionsChange }) {
  const [tab, setTab]           = useState('kiekiai');
  const [doubleSides, setDoubleSides] = useState(false);
  const [gkMetodas, setGkMetodas]     = useState('tikslus');  // Task 9
  const [dismissedWarnings, setDismissedWarnings] = useState(new Set()); // Task 6
  const [pageClassifications, setPageClassifications] = useState(  // Task 1 user overrides
    () => project.page_classifications || project.meta?.page_classifications || []
  );
  const [assumptions, setAssumptions] = useState({
    ...DEFAULT_ASSUMPTIONS,
    sienos_storis_m: project.prielaidos?.sienos_storis_m ?? 0.10,
    glaistimo_lygis: project.prielaidos?.glaistimo_lygis ?? 'Q2',
  });

  const rawData = project.raw_calc_data || null;

  // V3 backend path: backend already computed skaiciavimai from Opus output — trust it.
  // V2.1/V1 fallback: recalc on frontend from raw_calc_data so users can tweak prielaidos.
  const sk = useMemo(() => {
    const stored = project.skaiciavimai;
    const storedHasNumbers = stored
      && stored.dazomas_plotas
      && typeof stored.dazomas_plotas.viso_m2 === 'number'
      && stored.dazomas_plotas.viso_m2 > 0;
    if (storedHasNumbers) {
      return stored;
    }
    if (rawData) {
      return calculateInteriorQuantities(rawData, assumptions);
    }
    return stored || {};
  }, [rawData, assumptions, project.skaiciavimai]);

  const pk   = project.papildomi_kiekiai || {};
  const bk   = project.bendri_kiekiai  || {};
  const meta = project.meta            || {};

  const sienuApdaila   = project.sienu_apdaila   || {};
  const lubuData       = project.lubu_data       || {};
  const grindys        = project.grindys         || {};
  const elektra        = project.elektra         || {};
  const santechnika    = project.santechnika      || {};
  const apsvietimas    = project.apsvietimas      || {};
  const rooms          = project.patalpos         || [];
  const notes          = project.pastabos         || [];
  const prielaidos     = project.prielaidos       || {};
  const hidroizoliacija = project.hidroizoliacija || {};  // Task 2
  const perspejimani   = project.perspejimani     || [];  // Task 6

  const dp  = sk.dazomas_plotas    || {};
  const gk  = sk.glaistymo_kampai  || {};
  const ang = sk.angokrasciai      || {};
  const lp  = sk.lubu_perimetras   || {};
  const un  = sk.uzuolaidu_nisos   || {};
  const gj  = sk.grindjuostes      || {};
  const daz = sk.dazai             || {};
  const gkl = sk.gk_lapai          || {};
  const gls = sk.glaistas          || {};
  const validNotes = sk.validation_notes || [];

  const angValue = doubleSides ? ang.viso_m_x2 : ang.viso_m;

  const hasElektra  = Object.keys(elektra).length > 0;
  const hasSantech  = Object.keys(santechnika).length > 0;
  const hasApsviet  = Object.keys(apsvietimas).length > 0;
  const hasLubu     = Object.values(lubuData).some(v => v != null);
  const hasGrindys  = (grindys.medžiagos || []).length > 0 || grindys.grindjuostes_m != null;
  const hasWall     = Object.keys(sienuApdaila).length > 0;
  const hasSkaiciai = Object.keys(sk).length > 0;

  const handleAssumptionsChange = (next) => {
    setAssumptions(next);
    if (onAssumptionsChange) onAssumptionsChange(next);
  };

  return (
    <div className="space-y-5">

      <TabBar tab={tab} setTab={setTab} hasPages={pageClassifications.length > 0} />

      {/* ── TAB: KIEKIAI ──────────────────────────────────────────────────── */}
      {tab === 'kiekiai' && (
        <>
          {/* Low-confidence banner */}
          {project.confidence === 'low' && (
            <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>
                Vizualinė analizė nebuvo atlikta — kiekiai apytiksliai.
                {!meta.poppler_available && ' Įdiekite poppler tikslesniems rezultatams.'}
              </span>
            </div>
          )}

          {/* Window fallback warning */}
          {prielaidos.langai_fallback && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Langai nerasti brėžiniuose</p>
                <p className="text-xs mt-0.5">
                  Angokraščiams naudojami standartiniai langų dydžiai pagal patalpų tipus.
                  Patikrink ir pakoreguok skiltyje „Prielaidos".
                </p>
              </div>
            </div>
          )}

          {/* Validation notes */}
          {validNotes.length > 0 && (
            <div className="space-y-1">
              {validNotes.map((n, i) => (
                <div key={i} className="flex items-center gap-2 p-2.5 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  {n}
                </div>
              ))}
            </div>
          )}

          {/* ── 5 main calculation cards ─────────────────────────────────── */}
          {hasSkaiciai && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-foreground">Apdailos kiekiai</h2>
                {meta.vision_pages > 0 && (
                  <Badge variant="outline" className="text-xs">
                    Vizualiai analizuota: {meta.vision_pages} psl.
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">

                <CalcCard
                  color="blue"
                  title="Dažomas plotas"
                  mainValue={dp.viso_m2}
                  mainUnit="m²"
                  confidence={dp.confidence}
                  breakdown={[
                    { label: 'Sienos (neto)', value: dp.sienos_m2, unit: 'm²' },
                    { label: 'Lubos',         value: dp.lubos_m2,  unit: 'm²' },
                  ]}
                  note={dp.pastaba}
                />

                <CalcCard
                  color="amber"
                  title="Glaistymo kampai"
                  mainValue={gk.viso_m}
                  mainUnit="m"
                  confidence={gk.confidence}
                  breakdown={[
                    { label: 'Išorinių kampų',    value: gk.isoriniu_kampu_vnt, unit: 'vnt' },
                    { label: 'Vid. lubų aukštis',  value: gk.vidutinis_aukstis_m, unit: 'm' },
                  ]}
                />

                <CalcCard
                  color="green"
                  title="Angokraščiai"
                  mainValue={angValue}
                  mainUnit="m"
                  confidence={ang.confidence}
                  extra={
                    <div className="mb-2">
                      <Toggle
                        label="×2 (abi pusės)"
                        value={doubleSides}
                        onChange={setDoubleSides}
                      />
                    </div>
                  }
                  breakdown={[
                    { label: 'Langai',     value: ang.langu_vnt, unit: 'vnt' },
                    { label: 'Durys',      value: ang.duru_vnt,  unit: 'vnt' },
                    { label: 'Plotas',     value: ang.area_m2,   unit: 'm²'  },
                  ]}
                />

                <CalcCard
                  color="purple"
                  title="Lubų perimetras"
                  mainValue={lp.viso_m}
                  mainUnit="m"
                  confidence={lp.confidence}
                  note={lp.skaiciavimo_budas}
                />

                <CalcCard
                  color="teal"
                  title="Užuolaidų nišos"
                  mainValue={un.viso_m || lubuData.uzuolaidu_nisu_m}
                  mainUnit="m"
                  confidence={un.confidence}
                  breakdown={(un.details || []).map((d, i) => ({
                    label: d.vieta || d.room ? `${d.room || ''} ${d.wall || ''}`.trim() || `Niša ${i + 1}` : `Niša ${i + 1}`,
                    value: d.ilgis_mm ? d.ilgis_mm / 1000 : (d.length_mm ? d.length_mm / 1000 : null),
                    unit: 'm',
                  }))}
                />

                <CalcCard
                  color="indigo"
                  title="Grindjuostės"
                  mainValue={gj.viso_m}
                  mainUnit="m"
                  confidence={gj.confidence}
                  note="Perimetras atėmus durų plotį"
                />

              </div>
            </div>
          )}

          {/* ── Additional metrics ─────────────────────────────────────────── */}
          {(daz.viso_l != null || gkl.vnt != null || gls.kg != null) && (
            <div>
              <h2 className="text-sm font-semibold text-foreground mb-3">Medžiagų kiekiai</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <CalcCard
                  color="blue"
                  title="Dažai ir gruntas"
                  mainValue={daz.viso_l}
                  mainUnit="l"
                  confidence={daz.confidence}
                  breakdown={[
                    { label: 'Dažai sienoms (×2)',  value: daz.sienos_l, unit: 'l' },
                    { label: 'Dažai luboms (×2)',   value: daz.lubos_l,  unit: 'l' },
                    { label: 'Gruntas',             value: daz.gruntas_l, unit: 'l' },
                  ]}
                  note="2 sluoksniai; sienos 9 m²/l, lubos 10 m²/l"
                />

                <CalcCard
                  color="green"
                  title={`GK lapai (${gkl.metodas === 'praktinis' ? 'praktinis' : 'tikslus'})`}
                  mainValue={gkl.vnt}
                  mainUnit="vnt"
                  confidence={gkl.confidence}
                  note={gkl.metodas === 'praktinis' ? '1,2×2,5 m = 3 m² · +10% · BE angų atėmimo' : '1,2×2,5 m = 3 m² · +10% atliekos'}
                />

                <CalcCard
                  color="amber"
                  title={`Glaistas (${gls.lygis || 'Q2'})`}
                  mainValue={gls.kg}
                  mainUnit="kg"
                  confidence={gls.confidence}
                  breakdown={[
                    { label: 'Maišai 25 kg', value: gls.maisai_25kg, unit: 'vnt' },
                  ]}
                  note="Q2: 1.25 mm storis · 1.0 kg/m²/mm"
                />

                {/* Task 2: Hidroizoliacija card */}
                {Object.keys(hidroizoliacija).length > 0 && (
                  <CalcCard
                    color="rose"
                    title="Hidroizoliacija"
                    mainValue={hidroizoliacija.grindys_m2}
                    mainUnit="m² grindų"
                    confidence="medium"
                    breakdown={[
                      { label: 'Sienų plotas',    value: hidroizoliacija.sienos_m2,  unit: 'm²' },
                      { label: 'Sandarinimo juosta', value: hidroizoliacija.juosta_m, unit: 'm' },
                      { label: 'Membrana (2 sl.)', value: hidroizoliacija.membrana_kg, unit: 'kg' },
                    ]}
                    note={`Drėgnos patalpos: ${(hidroizoliacija.dregnas_patalpos || []).join(', ')}`}
                  />
                )}

              </div>
            </div>
          )}

          {/* ── Additional materials ──────────────────────────────────────── */}
          {Object.values(pk).some(v => v != null) && (
            <div className="bg-card border border-border rounded-xl p-4">
              <h2 className="text-sm font-semibold text-foreground mb-3">Papildomi kiekiai</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-0">
                <QtyRow label="Sienos plytelės" value={pk.plyteles_m2 ?? bk.sienu_plyteles_m2} unit="m²" />
                <QtyRow label="Parketo grindys" value={pk.parketlentes_m2 ?? bk.grindu_parketlentes_m2} unit="m²" />
                <QtyRow label="Grindjuostės" value={pk.grindjuostes_m} unit="m" />
                <QtyRow label="LED juostos" value={pk.led_juostos_m} unit="m" />
                <QtyRow label="GKP lubos" value={pk.gkp_lubos_m2} unit="m²" />
                <QtyRow label="LED nišos" value={pk.led_nisos_m} unit="m" />
              </div>
            </div>
          )}

          {/* ── Collapsible detail sections ─────────────────────────────── */}

          {hasWall && (
            <Section icon={Paintbrush} title="Sienų apdaila — detaliau" badge={`${Object.keys(sienuApdaila).length} tipai`}>
              <div className="space-y-0">
                {Object.entries(sienuApdaila).map(([tipas, area]) => (
                  <div key={tipas} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                    <span className={`px-2.5 py-1 rounded border text-xs font-medium ${finishColor(tipas)}`}>{tipas}</span>
                    <span className="text-sm font-semibold tabular-nums">
                      {fmt(area)} <span className="text-xs font-normal text-muted-foreground">m²</span>
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {hasLubu && (
            <Section icon={Layers} title="Lubos">
              <div>
                <QtyRow label="GKP lubų plotas"       value={lubuData.gkp_m2}             unit="m²" />
                <QtyRow label="LED nišų ilgis"        value={lubuData.led_nisu_m}          unit="m" />
                <QtyRow label="Užuolaidų nišų ilgis"  value={lubuData.uzuolaidu_nisu_m}    unit="m" />
                <QtyRow label="GKP dėžučių ilgis"     value={lubuData.gkp_dezuciu_m}       unit="m" />
              </div>
            </Section>
          )}

          {hasGrindys && (
            <Section icon={Square} title="Grindys">
              {(grindys.medžiagos || []).map((z, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                  <div className="min-w-0 mr-4">
                    <p className="text-sm text-foreground truncate">{z.medžiaga}</p>
                    {z.patalpos?.length > 0 && (
                      <p className="text-xs text-muted-foreground">{z.patalpos.join(', ')}</p>
                    )}
                  </div>
                  <span className="text-sm font-semibold tabular-nums whitespace-nowrap">
                    {z.plotas_m2 != null
                      ? <>{fmt(z.plotas_m2)} <span className="text-xs font-normal text-muted-foreground">m²</span></>
                      : z.kiekis_vnt != null
                        ? <>{fmt(z.kiekis_vnt, 0)} <span className="text-xs font-normal text-muted-foreground">vnt</span></>
                        : '—'}
                  </span>
                </div>
              ))}
              {grindys.grindjuostes_m != null && (
                <div className="pt-2">
                  <QtyRow label="Grindjuostės" value={grindys.grindjuostes_m} unit="m" />
                </div>
              )}
            </Section>
          )}

          {hasElektra && (
            <Section icon={Zap} title="Elektra">
              <div>
                <QtyRow label="Rozetės"               value={elektra.rozetes_vnt}                unit="vnt" />
                <QtyRow label="Jungikliai"             value={elektra.jungikliai_vnt}             unit="vnt" />
                <QtyRow label="Interneto rozetės"      value={elektra.interneto_rozetes_vnt}      unit="vnt" />
                <QtyRow label="Antenos"                value={elektra.antenos_vnt}                unit="vnt" />
                <QtyRow label="USB-C"                  value={elektra.usb_c_vnt}                  unit="vnt" />
                <QtyRow label="Termostatai"            value={elektra.termostatai_vnt}            unit="vnt" />
                <QtyRow label="Prietaisų pajungimai"   value={elektra.prietaisu_pajungimai_vnt}   unit="vnt" />
                <QtyRow label="Vartų valdymas"         value={elektra.vartai_vnt}                 unit="vnt" />
              </div>
            </Section>
          )}

          {hasSantech && (
            <Section icon={Droplets} title="Santechnika">
              <div>
                <QtyRow label="WC rėmai"           value={santechnika.wc_remai_vnt}           unit="vnt" />
                <QtyRow label="Dušo sistemos"       value={santechnika.duso_sistemos_vnt}      unit="vnt" />
                <QtyRow label="Praustuvės"          value={santechnika.praustuves_vnt}         unit="vnt" />
                <QtyRow label="Vonios maišytuvai"   value={santechnika.vonios_maistuvai_vnt}   unit="vnt" />
                <QtyRow label="Skalbimo mašinos"    value={santechnika.skalbimo_masinos_vnt}   unit="vnt" />
                <QtyRow label="Trapai"              value={santechnika.trapai_vnt}             unit="vnt" />
                <QtyRow label="Kondicionieriai"     value={santechnika.kondicionieriai_vnt}    unit="vnt" />
                <QtyRow label="Maišytuvai"          value={santechnika.maistuvai_vnt}          unit="vnt" />
              </div>
            </Section>
          )}

          {hasApsviet && (
            <Section icon={Lightbulb} title="Apšvietimas">
              <div>
                <QtyRow label="Įleidžiami sviestuvai"  value={apsvietimas.ileidziami_sviestuvai_vnt}  unit="vnt" />
                <QtyRow label="Pakabinami sviestuvai"   value={apsvietimas.pakabinami_sviestuvai_vnt}  unit="vnt" />
                <QtyRow label="Sieniniai sviestuvai"    value={apsvietimas.sieniniai_sviestuvai_vnt}   unit="vnt" />
                <QtyRow label="Paviršiniai sviestuvai"  value={apsvietimas.pavirsiniai_sviestuvai_vnt} unit="vnt" />
                <QtyRow label="LED juostos"             value={apsvietimas.led_juostos_m}              unit="m" />
                <QtyRow label="Judesio davikliai"       value={apsvietimas.judesio_davikliai_vnt}      unit="vnt" />
                <QtyRow label="Gaisro davikliai"        value={apsvietimas.gaisro_davikliai_vnt}       unit="vnt" />
                <QtyRow label="Garso kolonėlės"         value={apsvietimas.garso_koloneles_vnt}        unit="vnt" />
                <QtyRow label="Elektrinės užuolaidos"   value={apsvietimas.elektrines_uzuolaidos_vnt}  unit="vnt" />
              </div>
            </Section>
          )}

          {/* Angokraščiai detail */}
          {ang.details?.length > 0 && (
            <Section icon={CornerUpRight} title="Angokraščiai — detaliau" badge={`${ang.details.length} angos`}>
              <div className="space-y-0">
                {ang.details.map((d, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                    <span className="text-sm text-muted-foreground capitalize">{d.tipas} {i + 1}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {fmt(d.plotis_m)} × {fmt(d.aukstis_m)} m →{' '}
                      <span className="font-medium text-foreground">{fmt(d.perimetras_m)} m</span>
                      {doubleSides && <span className="text-muted-foreground"> (×2: {fmt(d.perimetras_m * 2)} m)</span>}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Rooms */}
          <Section icon={Home} title="Patalpos" badge={rooms.length} defaultOpen={rooms.length <= 12}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {rooms.map(room => <RoomCard key={room.nr} room={room} />)}
            </div>
          </Section>

          {notes.length > 0 && (
            <Section icon={AlertCircle} title="Pastabos">
              <ul className="space-y-1">
                {notes.map((n, i) => (
                  <li key={i} className="text-xs text-muted-foreground">• {n}</li>
                ))}
              </ul>
            </Section>
          )}

          {/* ── Task 6: Forgotten items warnings ───────────────────────────── */}
          {perspejimani.filter(w => !dismissedWarnings.has(w.id)).length > 0 && (
            <div className="border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
                <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">Nepamirškite patikrinti:</span>
              </div>
              <div className="space-y-2">
                {perspejimani
                  .filter(w => !dismissedWarnings.has(w.id))
                  .map(w => (
                    <div key={w.id} className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2">
                        <span className={`mt-0.5 w-2 h-2 rounded-full shrink-0 ${
                          w.kategorija === 'kritiška' ? 'bg-red-500' :
                          w.kategorija === 'techninė' ? 'bg-blue-500' : 'bg-amber-500'
                        }`} />
                        <div>
                          <p className="text-xs text-amber-800 dark:text-amber-300">{w.tekstas}</p>
                          {(w.patalpos || []).length > 0 && (
                            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                              {w.patalpos.join(', ')}
                            </p>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => setDismissedWarnings(prev => new Set([...prev, w.id]))}
                        className="shrink-0 text-amber-400 hover:text-amber-600 dark:hover:text-amber-200"
                        title="Uždaryti"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── TAB: PRIELAIDOS ───────────────────────────────────────────────── */}
      {tab === 'prielaidos' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Keisdami prielaidas, visi kiekiai persiskaičiuoja automatiškai.
            {!rawData && (
              <span className="text-amber-600 ml-1">
                Šiam projektui nėra raw duomenų — atnaujink projektą nauja analize.
              </span>
            )}
          </p>
          <AssumptionsPanel
            assumptions={assumptions}
            onChange={handleAssumptionsChange}
            prielaidos={prielaidos}
            rawData={rawData}
          />

          {/* Summary of current assumptions */}
          <div className="bg-card border border-border rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-3">Dabartinės prielaidos</h3>
            <div className="grid grid-cols-2 gap-x-8 gap-y-0">
              <QtyRow label="Sienos storis" value={assumptions.sienos_storis_m} unit="m" />
              <QtyRow label="Glaistymo lygis" value={null} />
              {assumptions.glaistimo_lygis && (
                <div className="flex items-center justify-between py-1.5 border-b border-border/50">
                  <span className="text-sm text-muted-foreground">Glaistymo lygis</span>
                  <Badge variant="outline">{assumptions.glaistimo_lygis}</Badge>
                </div>
              )}
              <QtyRow
                label="Langai"
                value={
                  assumptions.custom_windows != null
                    ? assumptions.custom_windows.length
                    : (prielaidos.langai_vnt ?? 0)
                }
                unit="vnt"
              />
              <QtyRow
                label="Durys"
                value={
                  assumptions.custom_doors != null
                    ? assumptions.custom_doors.length
                    : (prielaidos.durys_vnt ?? 0)
                }
                unit="vnt"
              />
            </div>
          </div>

          {/* Task 9: GK calculation method toggle */}
          <div className="bg-card border border-border rounded-xl p-4">
            <h3 className="text-sm font-semibold mb-2">GK lapų skaičiavimo metodas</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Tikslus: sienų plotas atėmus angas ÷ 3 m² + 10%. <br />
              Praktinis: visas perimetras × aukštis BE angų atėmimo — nes iškirptos dalys = atliekos + pjovimo darbas.
            </p>
            <div className="flex gap-2">
              {['tikslus', 'praktinis'].map(m => (
                <button
                  key={m}
                  onClick={() => setGkMetodas(m)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    gkMetodas === m
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                  }`}
                >
                  {m === 'tikslus' ? 'Tikslus' : 'Praktinis'}
                </button>
              ))}
            </div>
            {prielaidos.langai_source === 'niches' && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-3">
                ✓ Langai nustatyti iš užuolaidų nišų ({prielaidos.langai_vnt} vnt.)
              </p>
            )}
            {prielaidos.langai_source === 'room_defaults' && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">
                ⚠ Langai — standartiniai pagal patalpų tipą
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: PUSLAPIAI (Task 1) ───────────────────────────────────────── */}
      {tab === 'puslapiai' && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            AI klasifikuoti brėžinių puslapiai. Jei klasifikacija neteisinga — pakeiskite.
          </p>
          <div className="border border-border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground w-12">Psl.</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Tipas</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Tikslumas</th>
                </tr>
              </thead>
              <tbody>
                {pageClassifications.map((pg, i) => {
                  const confColors = {
                    high:   'text-green-600 dark:text-green-400',
                    medium: 'text-yellow-600 dark:text-yellow-400',
                    low:    'text-red-500',
                  };
                  const PAGE_TYPE_OPTIONS = [
                    { value: 'pertvarų',      label: 'Pertvarų planas' },
                    { value: 'baldų',         label: 'Baldų planas' },
                    { value: 'santechnikos',  label: 'Santechnikos planas' },
                    { value: 'rozecių',       label: 'Rozečių planas' },
                    { value: 'apšvietimo',    label: 'Apšvietimo planas' },
                    { value: 'lubų',          label: 'Lubų planas' },
                    { value: 'grindų',        label: 'Grindų planas' },
                    { value: 'apdailų',       label: 'Apdailų planas' },
                    { value: 'išklotinė',     label: 'Išklotinė' },
                    { value: 'fasadas',       label: 'Fasadas' },
                    { value: 'pjūvis',        label: 'Pjūvis' },
                    { value: 'specifikacija', label: 'Specifikacija' },
                    { value: 'vizualizacija', label: 'Vizualizacija' },
                    { value: 'cover',         label: 'Viršelis' },
                    { value: 'kita',          label: 'Kita' },
                  ];
                  return (
                    <tr key={i} className={`border-b border-border/50 last:border-0 ${i % 2 === 0 ? '' : 'bg-muted/20'}`}>
                      <td className="px-3 py-2 text-xs text-muted-foreground font-mono">{pg.page_number}</td>
                      <td className="px-3 py-2">
                        <select
                          value={pg.page_type}
                          onChange={e => {
                            const updated = [...pageClassifications];
                            const opt = PAGE_TYPE_OPTIONS.find(o => o.value === e.target.value);
                            updated[i] = { ...pg, page_type: e.target.value, label_lt: opt?.label || e.target.value, confidence: 'high' };
                            setPageClassifications(updated);
                          }}
                          className="text-xs bg-transparent border border-border rounded px-1.5 py-0.5 text-foreground"
                        >
                          {PAGE_TYPE_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <ConfidenceDot level={pg.confidence} />
                          <span className={`text-xs ${confColors[pg.confidence] || 'text-muted-foreground'}`}>
                            {pg.confidence === 'high' ? 'Aukštas' : pg.confidence === 'medium' ? 'Vidutinis' : 'Žemas'}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

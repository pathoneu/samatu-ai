import React, { useState, useMemo, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Home, Layers, Paintbrush, Square, AlertCircle, ChevronDown, ChevronUp,
  Zap, Droplets, Lightbulb, CornerUpRight, Ruler, Package, Droplet,
  AlertTriangle, ShieldAlert, FileText, X, CheckCircle2,
  Map, ListChecks, MessageSquare, Download,
} from 'lucide-react';
import AssumptionsPanel from '@/components/project/AssumptionsPanel';
import RoomsGrid from '@/components/project/RoomsGrid';
import PdfViewer from '@/components/project/PdfViewer';
import ScaleInfoBanner from '@/components/project/ScaleInfoBanner';
import PageStructureCard from '@/components/project/PageStructureCard';
import AiChat from '@/components/project/AiChat';
import InteriorWorkspace from '@/components/project/InteriorWorkspace';
import ProjectMainView from '@/components/project/ProjectMainView';
import ProjectCanvas from '@/components/project/ProjectCanvas';
import ExportDropdown from '@/components/project/ExportDropdown';
import { getPdfUrl } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';
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

function TabBar({ tab, setTab, hasPdf }) {
  const tabs = [
    ...(hasPdf ? [{ id: 'brezinys', label: 'Brėžinys', Icon: Map }] : []),
    { id: 'main',     label: 'Kiekiai',   Icon: ListChecks },
    { id: 'aichat',   label: 'AI Chat',   Icon: MessageSquare },
    { id: 'eksport',  label: 'Eksportas', Icon: Download },
  ];
  return (
    <div className="flex items-center gap-0 border-b border-border mb-5 -mt-1">
      {tabs.map(t => {
        const Icon = t.Icon;
        const isActive = tab === t.id;
        return (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all -mb-px flex items-center gap-2 ${
              isActive
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon className="w-4 h-4" />
            {t.label}
          </button>
        );
      })}
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
  // Visi metric'ai NEUTRAL — spalva tik confidence dot'e ir, jei reikia, accent border'yje.
  // Color prop'as paliktas backwards-compatibility, bet ignoruojamas (vienodi visiems).
  return (
    <Card className="border border-border bg-card hover:border-foreground/20 transition-colors">
      <CardContent className="p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </p>
          <ConfidenceDot level={confidence} />
        </div>
        <div className="flex items-baseline gap-1 mb-3">
          <span className="text-3xl font-semibold tabular-nums text-foreground">
            {mainValue != null ? fmt(mainValue) : '—'}
          </span>
          {mainValue != null && mainUnit && (
            <span className="text-base font-normal text-muted-foreground">{mainUnit}</span>
          )}
        </div>
        {extra}
        {breakdown && breakdown.length > 0 && (
          <div className="space-y-1 border-t border-border pt-2 mt-1">
            {breakdown.map(({ label, value, unit }, i) => value != null && (
              <div key={i} className="flex justify-between items-baseline">
                <span className="text-xs text-muted-foreground">{label}</span>
                <span className="text-xs font-medium tabular-nums text-foreground">
                  {fmt(value)} {unit}
                </span>
              </div>
            ))}
          </div>
        )}
        {note && (
          <p className="text-xs mt-2 text-muted-foreground/70 leading-tight">{note}</p>
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
          ? 'bg-foreground text-background border-foreground'
          : 'bg-card border-border text-muted-foreground hover:border-foreground/30'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${value ? 'bg-background' : 'bg-muted-foreground'}`} />
      {label}
    </button>
  );
}

// ── Finish type color chip ────────────────────────────────────────────────────

function finishColor() {
  // Visi finishai vienodi — neutral chip'ai. Skirstymas matomas tekste, ne spalvoje.
  return 'bg-muted text-foreground border-border';
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

// ── Detalus darbų sąrašas (rangovo-stiliaus sąmatos pozicijos) ───────────────────

function DarbuSarasas({ items }) {
  const [expandedReasoning, setExpandedReasoning] = useState(new Set());
  const [feedback, setFeedback] = useState({}); // { [kategorija]: 'ok' | 'bad' }

  if (!items || items.length === 0) return null;

  // Group by skyrius preserving server-side order
  const grouped = [];
  const seen = new Map();
  for (const it of items) {
    const key = it.skyrius || 'kita';
    if (!seen.has(key)) {
      seen.set(key, { skyrius: key, label: it.skyrius_label || 'Kita', items: [] });
      grouped.push(seen.get(key));
    }
    seen.get(key).items.push(it);
  }

  const toggleReasoning = (kat) => {
    setExpandedReasoning(prev => {
      const next = new Set(prev);
      if (next.has(kat)) next.delete(kat); else next.add(kat);
      return next;
    });
  };

  const markFeedback = (kat, value) => {
    setFeedback(prev => ({
      ...prev,
      [kat]: prev[kat] === value ? undefined : value,
    }));
  };

  const totalPositions = items.length;

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card">
      <div className="px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold text-foreground">
              Detalus darbų sąrašas
            </h2>
            <Badge variant="secondary" className="text-xs font-normal">
              {totalPositions} pozicijos
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            Pažymėk, ar kiekvienas kiekis atitinka brėžinius
          </span>
        </div>
      </div>

      <div className="divide-y divide-border">
        {grouped.map(group => (
          <div key={group.skyrius}>
            <div className="px-4 py-2 bg-muted/20">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {group.label}
              </span>
              <span className="ml-2 text-xs text-muted-foreground">
                ({group.items.length})
              </span>
            </div>

            <table className="w-full text-sm">
              <tbody>
                {group.items.map(it => {
                  const fb = feedback[it.kategorija];
                  return (
                    <React.Fragment key={it.kategorija}>
                      <tr className="border-t border-border/50 hover:bg-muted/20">
                        <td className="px-4 py-2 text-xs text-muted-foreground font-mono w-10 align-top">
                          {it.nr}
                        </td>
                        <td className="px-2 py-2 align-top">
                          <div className="text-sm text-foreground">{it.pavadinimas}</div>
                          {it.reasoning && (
                            <button
                              onClick={() => toggleReasoning(it.kategorija)}
                              className="text-xs text-muted-foreground hover:text-foreground mt-0.5"
                            >
                              {expandedReasoning.has(it.kategorija) ? 'Slėpti paaiškinimą' : 'Kodėl?'}
                            </button>
                          )}
                        </td>
                        <td className="px-2 py-2 text-right align-top whitespace-nowrap">
                          <span className="text-sm font-semibold tabular-nums">
                            {fmt(it.kiekis, 2)}
                          </span>
                          <span className="ml-1 text-xs text-muted-foreground">{it.vnt}</span>
                        </td>
                        <td className="px-4 py-2 align-top whitespace-nowrap">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => markFeedback(it.kategorija, 'ok')}
                              className={`p-1 rounded border text-xs transition-colors ${
                                fb === 'ok'
                                  ? 'bg-green-500/20 border-green-500 text-green-600 dark:text-green-400'
                                  : 'border-border text-muted-foreground hover:border-green-500/50 hover:text-green-600'
                              }`}
                              title="Teisingai"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => markFeedback(it.kategorija, 'bad')}
                              className={`p-1 rounded border text-xs transition-colors ${
                                fb === 'bad'
                                  ? 'bg-red-500/20 border-red-500 text-red-600 dark:text-red-400'
                                  : 'border-border text-muted-foreground hover:border-red-500/50 hover:text-red-600'
                              }`}
                              title="Neteisingai / peržiūrėti"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedReasoning.has(it.kategorija) && it.reasoning && (
                        <tr className="bg-muted/10">
                          <td></td>
                          <td colSpan={3} className="px-2 py-2 text-xs text-muted-foreground italic">
                            {it.reasoning}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function InteriorProject({ project, onAssumptionsChange }) {
  // ROLLBACK 2026-04-26: ProjectCanvas single-canvas eksperimentas sulaužė
  // realių projektų rendering'ą. Default = sena tabbed UI (kuri DIRBA).
  // Naujas canvas pasiekiamas tik per ?canvas=1 query string (eksperimentinis).
  const useNewCanvas = typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('canvas') === '1';
  const [tab, setTab]           = useState(() => 'brezinys');
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

  // Pasirinktas PDF puslapis (pagal kambarį arba puslapio tipą)
  const [focusedPage, setFocusedPage] = useState(null);

  // page → metadata (label, type) mapping pagal v8_pages
  const pageMetaDict = useMemo(() => {
    const dict = {};
    (project.v8_pages || []).forEach(p => {
      dict[p.page] = { label: p.label, type: p.type, confidence: p.confidence };
    });
    return dict;
  }, [project.v8_pages]);

  // PDF URL iš IndexedDB (sukuriamas blob: URL'as runtime)
  const [pdfUrl, setPdfUrl] = useState(null);
  useEffect(() => {
    let revoked = false;
    let url = null;
    getPdfUrl(project.id).then(u => {
      if (!revoked) {
        url = u;
        setPdfUrl(u);
      } else if (u) {
        URL.revokeObjectURL(u);
      }
    });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [project.id]);

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

  // ROLLBACK: ProjectCanvas tik kai ?canvas=1 (default = senas tabbed UI)
  if (useNewCanvas) {
    return (
      <ProjectCanvas
        project={project}
        onProjectChange={(updated) => {
          updateProject(project.id, updated);
        }}
      />
    );
  }

  return (
    <div className="space-y-5">

      <TabBar
        tab={tab} setTab={setTab}
        hasPdf={!!pdfUrl}
      />

      {/* ── TAB: BRĖŽINYS (default — PDF viewer + AI overlay) ───────── */}
      {tab === 'brezinys' && pdfUrl && (
        <InteriorWorkspace project={project} />
      )}
      {tab === 'brezinys' && !pdfUrl && (
        <div className="flex items-center justify-center h-96 border border-border rounded-xl bg-card text-muted-foreground text-sm">
          Brėžinys nepasiekiamas. Sukurkite naują projektą su PDF.
        </div>
      )}

      {/* ── TAB: KIEKIAI (suvestinė + darbų sąrašas) ────────────────────── */}
      {tab === 'main' && (
        <ProjectMainView
          project={project}
          onProjectChange={(updated) => {
            updateProject(project.id, updated);
          }}
          onShowDrawing={pdfUrl ? () => setTab('brezinys') : null}
        />
      )}

      {/* ── TAB: AI CHAT — natural language Q&A apie projektą ──────────── */}
      {tab === 'aichat' && (
        <div className="border border-border rounded-xl bg-card p-6">
          <div className="mb-4">
            <h2 className="text-base font-semibold mb-1">AI klausimai apie projektą</h2>
            <p className="text-sm text-muted-foreground">
              Užduokite bet kokį klausimą apie patalpas, plotus, kambarius arba kiekius.
              Pvz.: „Kiek bendrai dušo zonų?", „Ar yra patalpų virš 3m aukščio?"
            </p>
          </div>
          <AiChat project={project} inline />
        </div>
      )}

      {/* ── TAB: EKSPORTAS — Excel/PDF download ─────────────────────────── */}
      {tab === 'eksport' && (
        <div className="border border-border rounded-xl bg-card p-6 space-y-5">
          <div>
            <h2 className="text-base font-semibold mb-1">Eksportuoti pasiūlymą</h2>
            <p className="text-sm text-muted-foreground">
              Atsisiųskite užbaigtą pasiūlymą Excel arba PDF formatu.
              Visi kiekiai ir kainos įtraukiami iš „Kiekiai" tab'o.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <ExportDropdown project={project} />
            <span className="text-xs text-muted-foreground">
              {(project.darbu_sarasas || []).length} pozicijų · {(project.v8_rooms || project.patalpos || []).length} patalpų
            </span>
          </div>
          <div className="border-t border-border/50 pt-4 text-xs text-muted-foreground space-y-1">
            <p><strong className="text-foreground">Excel</strong> — pilna sąmata su skyrių grupavimu, formulėmis ir VAT.</p>
            <p><strong className="text-foreground">PDF</strong> — formattuotas pasiūlymas spausdinimui (su antraštės, suvestinės, pvm).</p>
          </div>
        </div>
      )}

      {/* ── TAB: KIEKIAI ──────────────────────────────────────────────────── */}
      {tab === 'kiekiai' && (
        <>
          {/* V8 mastelio info — production-blocking sanity */}
          {project.v8_scale && (
            <ScaleInfoBanner scaleInfo={project.v8_scale} />
          )}

          {/* V8 brėžinio struktūra (auto-klasifikacija) */}
          {project.v8_pages && project.v8_pages.length > 0 && (
            <PageStructureCard
              pages={project.v8_pages}
              summary={project.v8_pages_summary}
              onPageClick={(pageNr) => {
                if (pdfUrl) {
                  setFocusedPage(pageNr);
                  setTab('brezinys');
                }
              }}
            />
          )}

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

          {/* Validation notes — V5 stringai ARBA V6 {level, field, message} */}
          {validNotes.length > 0 && (
            <div className="space-y-1">
              {validNotes.map((n, i) => {
                const text = typeof n === 'string' ? n : (n?.message || JSON.stringify(n));
                const level = typeof n === 'object' ? (n?.level || 'INFO') : 'INFO';
                const colorClass = level === 'ERROR'
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : level === 'WARNING'
                    ? 'bg-yellow-50 border-yellow-200 text-yellow-800'
                    : 'bg-blue-50 border-blue-200 text-blue-800';
                return (
                  <div key={i} className={`flex items-center gap-2 p-2.5 border rounded-lg text-xs ${colorClass}`}>
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    <span>{text}</span>
                  </div>
                );
              })}
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

          {/* ── Per-kambarį view (V8 Universal) ──────────────────────────── */}
          {/* Visada rodom RoomsGrid — net jei project.v8_rooms tuščias.
              Vartotojas gali pridėti patalpas rankomis arba pamato empty state'ą. */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Home className="w-4 h-4 text-muted-foreground" />
                Patalpų sąrašas
                <Badge variant="secondary" className="text-xs font-normal">
                  {(project.v8_rooms || project.patalpos || []).length} patalpų
                </Badge>
              </h2>
              <span className="text-xs text-muted-foreground">
                Galite redaguoti — visi totals atsinaujins automatiškai
              </span>
            </div>
            {(!project.v8_rooms || project.v8_rooms.length === 0) && (
              <div className="mb-3 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-lg text-xs text-amber-900 dark:text-amber-200">
                AI neaptiko patalpų. Galimos priežastys: rastrinis brėžinys, neaiški antraštinė plokštelė,
                arba senas projektas (sukurtas prieš atnaujinimus).
                Spauskite „Pridėti patalpą" žemiau ir įveskite patalpas rankomis.
              </div>
            )}
            <RoomsGrid
              initialRooms={
                project.v8_rooms && project.v8_rooms.length > 0
                  ? project.v8_rooms
                  : (project.patalpos || []).map(p => ({
                      nr: p.nr || '01',
                      pavadinimas: p.pavadinimas || 'Patalpa',
                      paskirtis: p.paskirtis || 'gyvenamoji',
                      plotas_m2: p.plotas_m2 || 0,
                      perimetras_m: p.perimetras_m || 0,
                      lubu_aukstis_m: p.lubu_aukstis_m || 2.82,
                    }))
              }
              onShowOnPdf={(pageNr) => {
                if (pdfUrl) {
                  setFocusedPage(pageNr);
                  setTab('brezinys');
                }
              }}
            />
          </div>

          {/* ── Detalus darbų sąrašas (visos rangovo-stiliaus pozicijos) ──── */}
          <DarbuSarasas items={project.darbu_sarasas || []} />

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

      {/* ── TAB: WORKSPACE (Togal-style split-screen) ─────────────────────── */}
      {tab === 'workspace' && pdfUrl && (
        <InteriorWorkspace project={project} />
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

      {/* Floating AI CHAT — paslėpta MVP versijoj (Sprint 1, Q6) */}
      {/* <AiChat project={project} /> */}
    </div>
  );
}

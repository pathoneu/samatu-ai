import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { rulesWithScope } from '@/lib/scope';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Home, Layers, Paintbrush, Square, AlertCircle, ChevronDown, ChevronUp,
  Zap, Droplets, Lightbulb, CornerUpRight, Ruler,
  AlertTriangle, ShieldAlert, FileText, X, CheckCircle2,
  Map as MapIcon, ListChecks, Sliders, ArrowLeft, Trash2, Pencil,
  ArrowRight, ClipboardCheck, Send, Phone,
} from 'lucide-react';
import AssumptionsPanel from '@/components/project/AssumptionsPanel';
import RoomsGrid from '@/components/project/RoomsGrid';
import ScaleInfoBanner from '@/components/project/ScaleInfoBanner';
import PageStructureCard from '@/components/project/PageStructureCard';
import InteriorWorkspace from '@/components/project/InteriorWorkspace';
import ProjectMainView from '@/components/project/ProjectMainView';
import RereadDiffBanner from '@/components/project/RereadDiffBanner';
import FreeRereadBanner from '@/components/project/FreeRereadBanner';
import ReextractButton from '@/components/project/ReextractButton';
import { pilotSession, releasePilotSession } from '@/lib/telemetry';
import SanitySeverityPill from '@/components/project/SanitySeverityPill';
// Sprint §17 (2026-04-29): ProjectCanvas removed — experimental ?canvas=1
// flow never shipped to production after 2026-04-26 rollback.
import ExportDropdown from '@/components/project/ExportDropdown';
import ShareButton from '@/components/project/ShareButton';
import { getPdfUrl } from '@/lib/pdfStore';
import { updateProject, getProject, flushProjectSaves, logCorrection } from '@/lib/projectStore';
import { calculateInteriorQuantities, DEFAULT_ASSUMPTIONS } from '@/lib/interiorCalc';
import { mergeDarbuSarasasEdits, newlyCarriedOrphans } from '@/lib/mergeDarbuSarasas';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import { toast } from 'sonner';
import { API_BASE } from '@/lib/apiBase';
import { buildRecomputeContext } from '@/lib/recomputeContext';

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(val, decimals = 2) {
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
  const { t } = useTranslation();
  if (!level) return null;
  const map = {
    high:   { color: 'bg-green-500',  emoji: '🟢', title: t('project.interior.confHigh') },
    medium: { color: 'bg-yellow-400', emoji: '🟡', title: t('project.interior.confMedium') },
    low:    { color: 'bg-red-500',    emoji: '🔴', title: t('project.interior.confLow') },
  };
  const c = map[level];
  if (!c) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={`inline-block w-2.5 h-2.5 rounded-full ${c.color} shrink-0 cursor-help`}
        />
      </TooltipTrigger>
      <TooltipContent side="top">{c.emoji} {c.title}</TooltipContent>
    </Tooltip>
  );
}

// ── „Pagalba: paskambinti" ────────────────────────────────────────────────────
//
// Design §E0: „žmogus telefone šiame etape vertesnis už bet kokį vedlį."
// The number is deployment config (VITE_SUPPORT_PHONE), never a literal in the
// source: an out-of-date hard-coded number is worse than no number at all, so
// with the variable unset this renders nothing.

export function SupportPhoneLink({ compact = false }) {
  const { t } = useTranslation();
  const raw = (import.meta.env.VITE_SUPPORT_PHONE || '').trim();
  if (!raw) return null;
  const dial = raw.replace(/[^+0-9]/g, '');
  return (
    <a
      href={`tel:${dial}`}
      title={t('project.steps.helpTitle', { phone: raw })}
      className="inline-flex items-center gap-1.5 rounded border border-border-strong bg-card text-foreground/85 hover:bg-muted/50 transition-colors shrink-0"
      style={{ minHeight: 44, padding: '0 12px', fontSize: 14, fontWeight: 500 }}
    >
      <Phone className="w-4 h-4 shrink-0" aria-hidden />
      <span>{t('project.steps.help')}</span>
      {!compact && <span className="mono tabular hidden lg:inline">{raw}</span>}
    </a>
  );
}

// ── Project top bar (mirrors prototype/screen-project.jsx ProjectTopBar) ─
//
// 52px high single-row bar with: back arrow · project.name (13/600) ·
// company (11 muted) · Interjeras pill · AI patikrinimų pill · spacer ·
// Be PVM (13) | Su PVM (18 bold) · Prielaidos button · Eksportuoti button.
// Always visible above tab bar — which is why the sanity pill lives here:
// the project lands on Brėžinys and the full banner is on Kiekiai.

function ProjectTopBar({ project, totalNet, totalGross, reverseVat = false, onPrielaidos, onDelete, onRename, renameLocked = false, onShowSanity }) {
  const { t } = useTranslation();
  // Inline rename (pre-prod QA 2026-07-15: the name was only settable at
  // creation — no rename control existed anywhere in the UI).
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const startRename = () => { setNameDraft(project.name || ''); setEditingName(true); };
  const commitRename = () => {
    setEditingName(false);
    const v = nameDraft.trim();
    if (v && v !== project.name) onRename?.(v);
  };
  return (
    <div
      className="flex items-center flex-wrap bg-background border-b border-border py-2 sm:py-0 gap-y-2"
      style={{ minHeight: 52, padding: '0 16px', gap: 12, flexShrink: 0 }}
    >
      <Link
        to="/"
        title={t('project.interior.backToList')}
        className="flex items-center justify-center rounded transition-colors shrink-0"
        style={{
          width: 28, height: 28, color: 'hsl(var(--muted-foreground))',
        }}
      >
        <ArrowLeft className="w-3.5 h-3.5" />
      </Link>
      <div className="flex items-baseline gap-2.5 min-w-0">
        {editingName ? (
          <input
            autoFocus
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
              else if (e.key === 'Escape') { e.preventDefault(); setEditingName(false); }
            }}
            aria-label={t('project.interior.renameLabel')}
            className="font-semibold text-foreground bg-background border border-border rounded px-1.5 focus:outline-none focus:border-primary"
            style={{ fontSize: 13, height: 24, minWidth: 180 }}
          />
        ) : (
          <span className="flex items-center gap-1 min-w-0">
            <span className="font-semibold text-foreground truncate" style={{ fontSize: 13 }}>
              {project.name || t('project.interior.untitled')}
            </span>
            {onRename && (
              /* Founder 2026-07-25: pencil stays VISIBLE on the demo (he
                 searched for it and found nothing) — disabled with an honest
                 tooltip instead of hidden. */
              <button
                type="button"
                onClick={renameLocked ? undefined : startRename}
                disabled={renameLocked}
                title={renameLocked ? t('project.interior.renameDemoLocked') : t('project.interior.renameLabel')}
                className="p-0.5 rounded text-muted-foreground hover:text-foreground shrink-0 disabled:opacity-40 disabled:hover:text-muted-foreground disabled:cursor-not-allowed"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </span>
        )}
        {project.company_name && (
          <span className="text-muted-foreground whitespace-nowrap" style={{ fontSize: 11 }}>
            {project.company_name}
          </span>
        )}
        <span
          className="font-medium uppercase tracking-wide whitespace-nowrap"
          style={{
            fontSize: 10, padding: '2px 7px', borderRadius: 3,
            border: '1px solid hsl(var(--border-strong))',
            color: 'hsl(var(--muted-foreground))',
            background: 'hsl(var(--card))',
          }}
        >
          {t('project.interior.typePill')}
        </span>
        <SanitySeverityPill sanity={project.lt_sanity} onOpen={onShowSanity} />
      </div>
      <div className="flex-1 min-w-0" />
      <div
        className="flex items-center pr-3 gap-4 sm:gap-6"
        style={{ borderRight: '1px solid hsl(var(--border))', height: 28 }}
      >
        {/* No prices yet → say so. „0,00 €" twice in the header read as a
            result, not as an empty field (council cut list, 2026-09-13). */}
        {!(totalNet > 0) ? (
          <span className="text-muted-foreground" style={{ fontSize: 12 }}>
            {t('project.interior.pricesNotEntered')}
          </span>
        ) : (
          <>
            <div className="flex items-baseline" style={{ gap: 6 }}>
              <span className="skyrius-header" style={{ fontSize: 10 }}>{t('project.interior.beVat')}</span>
              <span className="mono tabular text-foreground/70" style={{ fontSize: 13 }}>
                {totalNet.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
              </span>
            </div>
            <div className="flex items-baseline" style={{ gap: 6 }}>
              <span className="skyrius-header" style={{ fontSize: 10 }}>
                {reverseVat ? t('project.mainView.totalReverse') : t('project.interior.suVat')}
              </span>
              <span className="mono tabular font-semibold text-foreground" style={{ fontSize: 18 }}>
                {totalGross.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €
              </span>
            </div>
          </>
        )}
      </div>
      <button
        onClick={onPrielaidos}
        title={t('project.interior.prielaidosTitle')}
        className="flex items-center gap-1.5 rounded transition-colors hover:bg-muted/50"
        style={{
          minHeight: 44, padding: '0 14px',
          border: '1px solid hsl(var(--border-strong))',
          background: 'hsl(var(--card))',
          fontSize: 14, fontWeight: 500,
          color: 'hsl(var(--foreground) / 0.85)',
        }}
      >
        <Sliders className="w-4 h-4" /> {t('project.interior.prielaidos')}
      </button>
      {/* „Pagalba: paskambinti" is on EVERY project screen, top right — the one
          affordance that works when nothing else is understood. */}
      <SupportPhoneLink />
      {/* Sprint §FIX-4 (2026-04-29): delete button (icon-only) — soft-delete'as
          per §28; projektas nukeliauja į Šiukšliadėžę 30d. retention.
          Eksportas is no longer a top-bar button: it is step 4, „Siųsti". */}
      {onDelete && (
        <button
          onClick={onDelete}
          title={t('project.interior.deleteTitle')}
          className="flex items-center justify-center rounded transition-colors hover:bg-muted/50"
          style={{
            minHeight: 44, width: 44,
            border: '1px solid hsl(var(--border-strong))',
            background: 'hsl(var(--card))',
            color: 'hsl(var(--muted-foreground))',
          }}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

// ── Step bar ──────────────────────────────────────────────────────────────────
//
// „Rimo kelionė" (2026-09-04): ONE path, FOUR steps, always visible —
// Brėžinys → Patikra → Sąmata → Siųsti. Not tabs: a tab set says "these are
// four unrelated places"; a numbered step row says "this is the order, and you
// are here". Every step is clickable (nobody is ever trapped), the current one
// is the loud one, and each step's own exit is ONE big button at the bottom.
//
// The Brėžinys step is ALWAYS present. Hiding it when a project has no PDF was
// a dead end: the "prisegti brėžinį" affordance lives INSIDE that step, so a
// project that lost its drawing could never get one back.

export const STEPS = ['brezinys', 'patikra', 'samata', 'siusti'];

export function StepBar({ step, setStep, hasPdf }) {
  const { t } = useTranslation();
  const icons = {
    brezinys: MapIcon, patikra: ClipboardCheck, samata: ListChecks, siusti: Send,
  };
  const currentIdx = STEPS.indexOf(step);
  return (
    <nav
      aria-label={t('project.steps.navLabel')}
      className="flex items-center border-b border-border overflow-x-auto bg-card"
      style={{ paddingLeft: 12, paddingRight: 12, gap: 2 }}
    >
      {STEPS.map((id, i) => {
        const Icon = icons[id];
        const isActive = step === id;
        const isDone = i < currentIdx;
        return (
          <React.Fragment key={id}>
            {i > 0 && (
              <span aria-hidden className="text-muted-foreground/50 shrink-0" style={{ fontSize: 15 }}>›</span>
            )}
            <button
              onClick={() => setStep(id)}
              title={id === 'brezinys' && !hasPdf
                ? t('project.steps.brezinysAttachTitle')
                : t(`project.steps.titles.${id}`)}
              aria-current={isActive ? 'step' : undefined}
              /* 44 px tall, 16 px label — the whole product is aimed at 35–60
                 year old eyes and hands (design §5). */
              className={`flex items-center shrink-0 whitespace-nowrap border-b-2 -mb-px transition-colors ${
                isActive
                  ? 'border-primary text-foreground font-semibold'
                  : isDone
                    ? 'border-transparent text-foreground/75 hover:text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
              style={{ minHeight: 44, padding: '0 14px', gap: 8, fontSize: 16 }}
            >
              <span
                aria-hidden
                className={`inline-flex items-center justify-center rounded-full shrink-0 ${
                  isActive ? 'bg-primary text-primary-foreground'
                           : 'bg-muted text-muted-foreground'
                }`}
                style={{ width: 22, height: 22, fontSize: 12, fontWeight: 600 }}
              >
                {i + 1}
              </span>
              <Icon className="w-4 h-4 shrink-0" aria-hidden />
              {t(`project.steps.${id}`)}
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
}

// ── Step footer — „Atgal" left, ONE big next-button right ─────────────────────
//
// Design §2: „kas toliau — vienas didelis mygtukas; atgal — visada galima".
// Any keyboard shortcut is spelled out in Lithuanian next to it; we do NOT
// bind Enter to the step advance here — inside Patikra, Enter belongs to the
// room check sheet („Viskas teisinga — kitas kambarys").

function StepFooter({ step, setStep, nextLabel, nextTitle, onNext, children }) {
  const { t } = useTranslation();
  const idx = STEPS.indexOf(step);
  const prev = idx > 0 ? STEPS[idx - 1] : null;
  return (
    <div
      className="flex items-center justify-between gap-3 flex-wrap border-t border-border bg-card"
      style={{ padding: '10px 16px' }}
    >
      <button
        type="button"
        onClick={() => prev && setStep(prev)}
        disabled={!prev}
        title={prev ? t('project.steps.backTitle', { step: t(`project.steps.${prev}`) }) : undefined}
        className="inline-flex items-center gap-2 rounded border border-border-strong bg-background text-foreground/85 hover:bg-muted/50 transition-colors disabled:opacity-40 disabled:hover:bg-background"
        style={{ minHeight: 44, padding: '0 16px', fontSize: 16 }}
      >
        <ArrowLeft className="w-4 h-4" aria-hidden />
        {t('project.steps.back')}
      </button>
      <div className="flex items-center gap-3 flex-wrap justify-end">
      {children}
      {nextLabel && (
        <button
          type="button"
          onClick={onNext}
          title={nextTitle}
          className="inline-flex items-center gap-2 rounded font-semibold transition-colors"
          style={{
            minHeight: 44, padding: '0 22px', fontSize: 16,
            background: 'hsl(var(--primary))', color: 'hsl(var(--primary-foreground))',
          }}
        >
          {nextLabel}
          <ArrowRight className="w-4 h-4" aria-hidden />
        </button>
      )}
      </div>
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

// ── Detalus darbų sąrašas (Rangovo-stiliaus sąmatos pozicijos) ───────────────────

// mergeDarbuSarasasEdits + its normalizers now live in lib/mergeDarbuSarasas.js
// (extracted 2026-07-28 so the merge is unit-testable — the rule that decides
// whether a priced row survives a rebuild had no tests and deleted 5 281,85 €).

/**
 * Tell the user which rows the rebuild could NOT recompute. They're still in the
 * sąmata with their original numbers (and prices) — that's the point — but they
 * no longer follow the new assumptions, so silence would be a lie. Transient
 * toast on purpose: merging this into project.lt_sanity would stack a duplicate
 * banner entry on every recompute.
 */
/** Positions /api/recompute-quantities reports it carried without recomputing. */
function backendCarriedPositions(result) {
  const deg = (result?._degradations || []).find(
    (d) => d && typeof d === 'object' && d.reason === 'orphans_carried',
  );
  return deg?.positions || [];
}

/** What the ripple card calls the fix that produced it. */
function correctionLabel(correction, t) {
  if (!correction?.field_path) return t('project.interior.assumptionsTitle');
  const field = String(correction.field_path).split('.')[0];
  const name = t(`project.patikra.fieldNames.${field}`, { defaultValue: field });
  return correction.room_nr ? `${name} · ${correction.room_nr}` : name;
}

function notifyCarriedOrphans(labels, t) {
  const unique = [...new Set((labels || []).filter(Boolean))];
  if (unique.length === 0) return;
  // `n`, not `count` — `count` would make i18next resolve Lithuanian plural
  // forms (one/few/other) that this single-string key doesn't define.
  toast.warning(t('project.interior.toastOrphansCarried', {
    n: unique.length,
    labels: unique.slice(0, 3).join(', ') + (unique.length > 3 ? '…' : ''),
  }));
}

/**
 * Surface the OTHER backend degradations (2026-07-28 audit, B2/B3).
 *
 * `orphans_carried` had a dedicated toast; every other _degradations entry —
 * a failed pozicijos rebuild, a failed compat emit, a darbu_sarasas that no
 * longer lines up 1:1 with pozicijos — reached the browser and was dropped on
 * the floor. Those are exactly the cases where the numbers on screen stopped
 * following the assumptions the user just changed, so silence is a lie.
 * The backend already writes the LT sentence; render it verbatim.
 */
function notifyBackendDegradations(result) {
  const seen = new Set();
  for (const d of result?._degradations || []) {
    if (!d || typeof d !== 'object') continue;
    if (d.reason === 'orphans_carried') continue;   // has its own toast
    if (!d.message || seen.has(d.reason)) continue;
    seen.add(d.reason);
    toast.warning(d.message, { id: `recompute-degradation-${d.reason}` });
  }
}

function DarbuSarasas({ items }) {
  const { t } = useTranslation();
  const [expandedReasoning, setExpandedReasoning] = useState(new Set());
  const [feedback, setFeedback] = useState({}); // { [kategorija]: 'ok' | 'bad' }

  if (!items || items.length === 0) return null;

  // Group by skyrius preserving server-side order
  const grouped = [];
  const seen = new Map();
  for (const it of items) {
    const key = it.skyrius || 'kita';
    if (!seen.has(key)) {
      seen.set(key, { skyrius: key, label: it.skyrius_label || t('project.interior.otherCategory'), items: [] });
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
              {t('project.interior.listDetailHead')}
            </h2>
            <Badge variant="secondary" className="text-xs font-normal">
              {t('project.interior.listPositions', { count: totalPositions })}
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            {t('project.interior.listMarkHint')}
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

            <div className="overflow-x-auto">
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
                              {expandedReasoning.has(it.kategorija) ? t('project.interior.hideReasoning') : t('project.interior.why')}
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
                              title={t('project.interior.feedbackOk')}
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
                              title={t('project.interior.feedbackBad')}
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
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function InteriorProject({ project: projectProp, onDelete }) {
  const { t } = useTranslation();
  // Local mirror of project prop — needed because RulesOverridePanel rewrites
  // big swaths of state via /recompute-interior. Keep prop sync via useEffect
  // so navigation between projects still works.
  const [projectState, setProjectState] = useState(projectProp);
  useEffect(() => { setProjectState(projectProp); }, [projectProp]);
  // Saves are debounced 400 ms in projectStore (2026-07-28 perf sweep). Leaving
  // this page — back arrow, project switch, tab close — must not strand the
  // last edit on that timer. (The store also flushes on visibilitychange /
  // pagehide; this covers in-app navigation, which fires neither.)
  useEffect(() => () => flushProjectSaves(), []);
  const project = projectState;
  const setProject = setProjectState;
  // ONE path, four steps (design „Rimo kelionė" §2). `step` replaced the old
  // three-tab set: 'main' → 'samata', 'eksport' → 'siusti', and the AI-chat tab
  // became a small button in the bottom-right corner.
  // The room check sheet lives on its own route (/project/:id/patikra) and
  // hands the contractor back here with `?step=samata`, so the step is read
  // from the URL once on mount. 'patikra' itself is never a local step: asking
  // for it navigates to the sheet (see goStep).
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { id: routeProjectId } = useParams();
  const [step, setStep]         = useState(() => {
    const q = searchParams.get('step');
    return q && STEPS.includes(q) && q !== 'patikra' ? q : 'brezinys';
  });
  const goStep = useCallback((id) => {
    if (id === 'patikra') {
      navigate(`/project/${routeProjectId || projectProp?.id}/patikra`);
      return;
    }
    setStep(id);
  }, [navigate, routeProjectId, projectProp?.id]);
  // Prielaidos used to be a full-screen tab: the panel's own intro promised the
  // quantities recompute „dešinėje" while the takeover had hidden them. It is a
  // right-hand drawer now, so the drawing / sąmata stays on screen behind it.
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  // Pilot telemetry: the clock starts when the project opens, not on step 3.
  useEffect(() => {
    if (!project?.id) return undefined;
    const pid = project.id;
    pilotSession(pid);
    return () => { releasePilotSession(pid); };
  }, [project?.id]);
  // Bumped by the top-bar sanity pill. ProjectMainView watches it to scroll
  // the banner into view and force the loud groups open — otherwise the jump
  // lands on the Sąmata step somewhere above the warnings the user clicked.
  const [sanityFocus, setSanityFocus] = useState(0);
  const showSanity = () => { setStep('samata'); setSanityFocus(n => n + 1); };
  const [doubleSides, setDoubleSides] = useState(false);
  const [dismissedWarnings, setDismissedWarnings] = useState(new Set()); // Task 6
  const [isRecomputing, setIsRecomputing] = useState(false);
  // page_classifications was V8 page_classifier output. New extractor doesn't
  // emit it; the 'puslapiai' tab that consumed it has been removed.
  const [assumptions] = useState({
    ...DEFAULT_ASSUMPTIONS,
    sienos_storis_m: project.prielaidos?.sienos_storis_m ?? 0.10,
    glaistimo_lygis: project.prielaidos?.glaistimo_lygis ?? 'Q2',
  });

  // Pasirinktas PDF puslapis (pagal kambarį arba puslapio tipą)
  const [focusedPage, setFocusedPage] = useState(null);
  // Currently-focused room — used to highlight matching row on eksplikacija
  // page. Set whenever a room-driven jump fires; cleared on tab switch.
  const [focusedRoom, setFocusedRoom] = useState(null);

  const focusOnRoom = (pageNr, room) => {
    setFocusedPage(pageNr);
    setFocusedRoom(room || null);
  };

  // „Pataisyti" / a ⚙ on an assumption-driven term opens Prielaidos ON the
  // control that produced the wrong number. The nonce is what makes a SECOND
  // jump to the same field scroll again. (2026-09-02, Patikra.)
  const [assumptionFocus, setAssumptionFocus] = useState(null);
  const openAssumptions = (focus = null) => {
    setAssumptionsOpen(true);
    setAssumptionFocus(focus
      ? { ...focus, nonce: (assumptionFocus?.nonce || 0) + 1 }
      : null);
  };

  // What the last recompute actually moved, so the fix has a visible result
  // instead of a silently different sąmata. Held in state, not on the project
  // blob: it is a message about one edit, not a property of the estimate.
  const [lastRipple, setLastRipple] = useState(null);
  // What the user changed last, so the ripple card can name it. A REF, not
  // state: the recompute is debounced 400 ms, and the callback that resolves it
  // was captured before the correction was recorded — a state read there would
  // always name the PREVIOUS fix.
  const lastCorrectionRef = useRef(null);
  const reportRipple = useCallback((label, prior, next, extra = {}) => {
    const diff = diffDarbuSarasas(prior || [], next || []);
    setLastRipple({ label, diff, at: new Date().toISOString(), ...extra });
    if (diff.count === 0) return;
    const delta = diff.deltaEur;
    // "+0 €" on a project that has SOME prices but none on the rows that just
    // moved reads as "nothing changed" — say the prices are missing instead.
    const changedRowsPriced = (diff.changed || []).some(c => Number(c?.row?.kaina) > 0);
    if (diff.usePrices && !changedRowsPriced) {
      toast.success(t('project.patikra.toastRippleNoPriceYet', { count: diff.count }));
      return;
    }
    toast.success(diff.usePrices
      ? t('project.patikra.toastRipple', {
        count: diff.count,
        delta: `${delta >= 0 ? '+' : '−'}${Math.abs(delta).toLocaleString('lt-LT', {
          maximumFractionDigits: 0 })} €`,
      })
      : t('project.patikra.toastRippleNoPrice', { count: diff.count }));
  }, [t]);

  // PDF URL iš IndexedDB (sukuriamas blob: URL'as runtime)
  const [pdfUrl, setPdfUrl] = useState(null);
  useEffect(() => {
    let revoked = false;
    let url = null;
    getPdfUrl(project.id).then(u => {
      if (!revoked) {
        url = u;
        setPdfUrl(u);
        // No stored PDF → step 1 has nothing to show but the "įkelkite
        // brėžinį" recovery screen, so land on the sąmata instead. Also covers
        // hasPdf turning false at runtime (project switch), because this
        // effect re-runs per project.id. (2026-07-28 UX walkthrough.)
        if (!u) setStep(cur => (cur === 'brezinys' ? 'samata' : cur));
      } else if (u) {
        URL.revokeObjectURL(u);
      }
    }).catch((e) => {
      // No .catch was a dead end (2026-07-28 audit): a rejected IndexedDB read
      // left the user on an empty 'brezinys' step with no way out. Treat a
      // failure exactly like "no stored PDF".
      console.warn('[InteriorProject] PDF URL load failed:', e);
      if (!revoked) setStep(cur => (cur === 'brezinys' ? 'samata' : cur));
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

  // Edit cascade — kai vartotojas pataiso patalpos primityvą (plotas, perimetras,
  // lubų aukštis, paskirtis), kviečiame backend'o /recompute-interior, kuris
  // deterministiškai perskaičiuoja darbu_sarasas + santrauką. Be Vision call'o.
  // Sub-second roundtrip. Pataisymas neperšviečia kitų laukų — vartotojas
  // niekada nepradeda nuo nulio.
  // Phase C-1 Task 21: wrapped in useCallback so the samatu:project-recompute
  // listener (below) gets a stable reference and re-binds only when project
  // identity / overrides change, not on every render.
  const handleRoomsChange = useCallback(async (newRooms) => {
    if (!Array.isArray(newRooms)) return;
    setIsRecomputing(true);
    try {
      const res = await fetch(`${API_BASE}/recompute-interior`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patalpos: newRooms,
          rules_override: rulesWithScope(project._overrides, project._apimtis),
          per_room_overrides: project._per_room_overrides || {},
          archetipas: project.archetipas,
          bendras_plotas_m2: newRooms.reduce(
            (s, r) => s + (Number(r.plotas_m2) || 0), 0,
          ),
          // Same reader context /api/recompute-quantities sends — without it
          // this path rebuilt the ceiling off the per-room sum (dropping the
          // eksplikacijos anchor) and lost the door/fixture/tile lines.
          _ceiling_anchor: project._ceiling_anchor,
          _door_types: project._door_types,
          _symbol_legend: project._symbol_legend,
          _duru_ziniarastis: project._duru_ziniarastis,
          context: buildRecomputeContext(project),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const result = await res.json();
      if (result.status !== 'ok') {
        throw new Error(result._error || t('project.interior.recomputeErr'));
      }
      // Merge — preserve user fields (name, kainos, etc.) — overwrite computed.
      // `notes` records every row the rebuild couldn't reproduce so we can TELL
      // the user instead of quietly shipping a shorter sąmata. /recompute-interior
      // sends no prior list, so this merge is the ONLY thing standing between a
      // room edit and 15 deleted priced rows. (P0 2026-07-28.)
      const notes = [];
      const merged = {
        ...project,
        ...result,
        // Preserve metadata user may have edited
        name: project.name,
        company_name: project.company_name,
        vat_rate: project.vat_rate,
        // Carry the user's prices + manual count overrides forward, and keep
        // drawing symbol-count lines (the rebuild can't reproduce them).
        darbu_sarasas: mergeDarbuSarasasEdits(
          result.darbu_sarasas, project.darbu_sarasas, notes),
      };
      updateProject(project.id, merged);
      setProject(merged);
      toast.success(t('project.interior.toastRecomputed'));
      notifyCarriedOrphans(newlyCarriedOrphans(notes, project.darbu_sarasas).map((n) => n.aprasymas), t);
    } catch (e) {
      console.error('Edit cascade failed:', e);
      toast.error(t('project.interior.toastRecomputeErr', { msg: e.message }));
    } finally {
      setIsRecomputing(false);
    }
  }, [project, setProject, t]);

  // Phase C-1 Task 21 (closes review feedback): listen for the
  // samatu:project-recompute event dispatched by projectStore.updateRoomPolygon
  // after a manual polygon commit. Without this listener the event fired into
  // the void and downstream darbu_sarasas / kiekiai kept stale plotas_m2.
  // We re-read patalpos from storage (updateRoomPolygon already wrote them)
  // and route them through handleRoomsChange so /recompute-interior reruns.
  useEffect(() => {
    const onRecompute = (e) => {
      if (!e?.detail || e.detail.projectId !== project.id) return;
      const fresh = getProject(project.id);
      if (fresh?.patalpos) {
        handleRoomsChange(fresh.patalpos);
      }
    };
    window.addEventListener('samatu:project-recompute', onRecompute);
    return () => window.removeEventListener('samatu:project-recompute', onRecompute);
  }, [project.id, handleRoomsChange]);

  // Compute totals for ProjectTopBar (mirrors ProjectMainView's logic)
  const totalNet = (project.darbu_sarasas || []).reduce(
    (s, it) => s + (it.kiekis || 0) * (it.kaina || 0), 0,
  );
  // Reverse-VAT (renovacija): no output VAT. The top bar used to add 21%
  // unconditionally, so it disagreed with the Kiekiai tab, the Excel and the
  // PDF — all of which already respect vat_mode. (2026-07-27 audit; mirrors
  // ProjectMainView's condition.)
  const reverseVat = (project.vat_mode || '').toLowerCase() === 'reverse_vat'
    || (project.archetipas || '').toLowerCase() === 'renovacija';
  const vatRate = reverseVat ? 0 : (project.vat_rate || 21);
  const totalGross = totalNet * (1 + vatRate / 100);

  return (
    <div className="flex flex-col">
      <ProjectTopBar
        project={project}
        totalNet={totalNet}
        totalGross={totalGross}
        reverseVat={reverseVat}
        onPrielaidos={() => openAssumptions()}
        onShowSanity={showSanity}
        onDelete={onDelete}
        onRename={(newName) => {
          const updated = updateProject(project.id, { name: newName });
          if (updated) setProject(updated);
        }}
        renameLocked={!!project.is_demo}
      />

      <StepBar
        step={step} setStep={goStep}
        hasPdf={!!pdfUrl}
      />

      <div className="flex-1 px-4 py-4 space-y-5">

      {/* What the last re-read of the drawing changed — on every step, until
          he presses „Supratau" (lib/mergeReextract.js records it). */}
      {/* A project read before the geometry lane existed can be read again for free (no Vision). */}
      <FreeRereadBanner project={project} onComplete={(next) => setProject(next)} className="mt-3" />
      <RereadDiffBanner project={project} onProjectChange={(next) => setProject(next)} />

      {/* ── STEP 1 · BRĖŽINYS — the drawing, its rooms, its measurements ── */}
      {/* ── STEP 2 · PATIKRA — the same workspace with the check rail open.
             ONE component, two entry points (never a parallel surface): the
             room check sheet the next worker builds replaces the rail's card
             in place, and both steps keep the drawing beside it. ─────────── */}
      {(step === 'brezinys' || step === 'patikra') && (
        <InteriorWorkspace
          project={project}
          mode={step}
          focusedPage={focusedPage}
          focusedRoom={focusedRoom}
          onJumpToPage={(pageNr, room) => focusOnRoom(pageNr, room)}
          onOpenAssumptions={openAssumptions}
          lastRipple={lastRipple}
          onProjectChange={(updated) => {
            updateProject(project.id, updated);
            setProject(updated);
            // pdfUrl is only ever used as a boolean here (step gating), so mint
            // a blob URL ONLY when we don't have one. Doing it on every project
            // change leaked an object URL per edit — the old one was never
            // revoked and the effect's cleanup only knows about the first.
            if (!pdfUrl) {
              getPdfUrl(project.id).then((url) => setPdfUrl(url))
                .catch((e) => console.warn('[InteriorProject] PDF URL refresh failed:', e));
            }
          }}
        />
      )}

      {/* ── STEP 3 · SĄMATA (jo lentelė, jo skyriai) ────────────────────── */}
      {step === 'samata' && (
        <ProjectMainView
          project={project}
          onProjectChange={(updated) => {
            // Update both local state (so React re-renders the banner /
            // cards immediately) and persisted store (so the next page
            // reload picks up the same data). Pre-2026-05-10 this only
            // hit the store, leaving the UI showing stale lt_sanity until
            // a full reload — the revalidate button looked like a no-op.
            setProject(updated);
            updateProject(project.id, updated);
          }}
          onShowDrawing={pdfUrl ? () => setStep('brezinys') : null}
          onJumpToPage={pdfUrl ? (pageNr, room) => {
            focusOnRoom(pageNr, room);
            setStep('brezinys');
          } : null}
          // A sanity warning about lubų aukštis is only actionable if the
          // control it names is one click away.
          onOpenAssumptions={openAssumptions}
          focusSanityNonce={sanityFocus}
        />
      )}

      {/* ── NUSTATYMAI (ex-„Prielaidos") — a right-hand DRAWER, not a step.
          It is not part of the four-step path: it is the place you are sent to
          from a „Pataisyti", and you come straight back to where you were.
          2026-05-06: per user request, removed the heavier RulesOverridePanel
          (templates, LT library viewer, formula card, multi-floor multipliers,
          duplicate header). AssumptionsPanel alone. */}
      {assumptionsOpen && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <div
            className="absolute inset-0"
            style={{ background: 'hsl(var(--foreground) / 0.18)' }}
            onClick={() => setAssumptionsOpen(false)}
            aria-hidden
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t('project.interior.assumptionsTitle')}
            className="relative h-full overflow-y-auto bg-background border-l border-border shadow-xl w-full sm:w-[520px] p-4 space-y-4"
          >
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-foreground" style={{ fontSize: 17 }}>
                {t('project.interior.assumptionsTitle')}
              </h2>
              <button
                type="button"
                onClick={() => setAssumptionsOpen(false)}
                title={t('project.steps.settingsClose')}
                aria-label={t('project.steps.settingsClose')}
                className="inline-flex items-center justify-center rounded border border-border-strong bg-card text-foreground/80 hover:bg-muted/50"
                style={{ minHeight: 44, minWidth: 44 }}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          <AssumptionsPanel
            bare
            defaultOpen={true}
            title={t('project.interior.assumptionsTitle')}
            assumptions={project._overrides || {}}
            onChange={(updated) => {
              const nextProject = { ...project, _overrides: updated };
              setProject(nextProject);
              updateProject(project.id, nextProject);
            }}
            prielaidos={project.prielaidos || {}}
            rawData={project}
            pozicijos={project.pozicijos || []}
            darbuSarasas={project.darbu_sarasas || []}
            focusField={assumptionFocus}
            onCorrection={(payload) => {
              // „Įsiminta mokymui" = written to this project's correction log.
              // Nothing more is claimed, and nothing more happens.
              logCorrection(project.id, payload);
              lastCorrectionRef.current = payload;
            }}
            onRecomputed={(result) => {
              const notes = [];
              const nextProject = {
                ...project,
                patalpos: result.rooms || project.patalpos,
                // `v8_rooms` is what the panel and the room sheet READ when it
                // has rooms; leaving it stale meant the next edit was seeded
                // from pre-recompute rooms (2026-09-04, found by the room sheet).
                ...(Array.isArray(project.v8_rooms) && project.v8_rooms.length && result.rooms
                  ? { v8_rooms: result.rooms }
                  : {}),
                pozicijos: result.pozicijos || project.pozicijos,
                // The Kiekiai table, top-bar totals and export all read
                // darbu_sarasas — keep it in sync with the recomputed quantities,
                // preserving prices + manual count overrides + drawing symbol
                // lines. (2026-06-19 hunt: recompute updated pozicijos only and
                // wiped count overrides / symbol lines.)
                darbu_sarasas: mergeDarbuSarasasEdits(
                  result.darbu_sarasas, project.darbu_sarasas, notes,
                  // Rows the backend folded into a renamed sibling are already
                  // represented (with their price) in result.darbu_sarasas —
                  // without this they'd ALSO be carried here and their money
                  // would be counted twice.
                  (result._merge_notes || []).filter((n) => n.reason === 'relabeled')),
                _overrides: { ...(project._overrides || {}), ...(result.assumptions || {}) },
              };
              setProject(nextProject);
              updateProject(project.id, nextProject);
              reportRipple(
                correctionLabel(lastCorrectionRef.current, t),
                project.darbu_sarasas, nextProject.darbu_sarasas);
              // On this path the BACKEND already carried the orphans (it holds the
              // prior pozicijos), so its degradation entry is the authoritative
              // list; the local merge only adds rows the backend never saw.
              {
                // Backend-carried labels are ALL carried orphans; drop the ones
                // that were already orphans before this rebuild (see
                // newlyCarriedOrphans) so the notice fires once, not forever.
                const already = new Set((project.darbu_sarasas || [])
                  .filter((r) => r && r._orphaned_after_rebuild)
                  .map((r) => String(r.aprasymas || '').toLowerCase()));
                notifyCarriedOrphans([
                  ...backendCarriedPositions(result).filter((l) => !already.has(String(l || '').toLowerCase())),
                  ...newlyCarriedOrphans(notes, project.darbu_sarasas).map((n) => n.aprasymas),
                ], t);
              }
              notifyBackendDegradations(result);
            }}
          />
          {/* The paid re-read of the drawing — here, not beside Export: it is
              a repair, not a step (council cut list, 2026-09-13). */}
          <div className="border-t border-border pt-4 space-y-2">
            <h3 className="font-semibold text-foreground" style={{ fontSize: 14 }}>
              {t('project.interior.rereadSection')}
            </h3>
            <ReextractButton
              project={project}
              onComplete={(merged) => { setProject(merged); }}
            />
          </div>
          </div>
        </div>
      )}

      {/* ── STEP 4 · SIŲSTI — three actions and one sentence before sending ─ */}
      {step === 'siusti' && (
        <SendStep project={project} />
      )}

      {/* ── LEGACY BLOCK (unreachable) — the old V8 „Kiekiai" screen.
             It is the only place RoomsGrid / RoomCard are mounted, so it stays
             on disk for the room-check-sheet work; nothing routes to it. ──── */}
      {step === 'roomsgrid_legacy' && (
        <>
          {/* V8 mastelio info — production-blocking sanity */}
          {project.v8_scale && (
            <ScaleInfoBanner scaleInfo={project.v8_scale} />
          )}

          {/* Sprint §42 (2026-04-29): _scale_hint badge — auto-detected from
              text layer in NewProject upload. Lightweight info, dismissable. */}
          {project._scale_hint && project._scale_hint.scale_text && (
            <div
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
              style={{
                background: 'hsl(var(--source-table) / 0.08)',
                border: '1px solid hsl(var(--source-table) / 0.25)',
                color: 'hsl(var(--source-table))',
              }}
            >
              <Ruler className="w-3.5 h-3.5 shrink-0" />
              <span>
                {t('project.interior.scaleAutoPrefix')}
                <strong className="mono tabular">{project._scale_hint.scale_text}</strong>
                {project._scale_hint.page && (
                  <span className="text-muted-foreground ml-2">
                    {t('project.interior.scalePage', { page: project._scale_hint.page })}
                  </span>
                )}
              </span>
            </div>
          )}

          {/* V8 page structure card removed — new extractor doesn't emit v8_pages.
              PageStructureCard component still exists but is dead UI for new schema. */}
          {false && (
            <PageStructureCard
              pages={[]}
              summary={null}
              onPageClick={(pageNr) => {
                if (pdfUrl) {
                  setFocusedPage(pageNr);
                  setStep('brezinys');
                }
              }}
            />
          )}

          {/* Low-confidence banner */}
          {project.confidence === 'low' && (
            <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-300">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>
                {t('project.interior.lowConf')}
                {!meta.poppler_available && t('project.interior.lowConfPoppler')}
              </span>
            </div>
          )}

          {/* Window fallback warning */}
          {prielaidos.langai_fallback && (
            <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">{t('project.interior.windowsNotFound')}</p>
                <p className="text-xs mt-0.5">
                  {t('project.interior.windowsNotFoundDesc')}
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
                  ? 'bg-red-500/10 border-red-500/30 text-red-300'
                  : level === 'WARNING'
                    ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-300'
                    : 'bg-blue-500/10 border-blue-500/30 text-blue-300';
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
                <h2 className="text-sm font-semibold text-foreground">{t('project.interior.finishHead')}</h2>
                {meta.vision_pages > 0 && (
                  <Badge variant="outline" className="text-xs">
                    {t('project.interior.visionAnalyzed', { pages: meta.vision_pages })}
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">

                <CalcCard
                  color="blue"
                  title={t('project.interior.cardPaintArea')}
                  mainValue={dp.viso_m2}
                  mainUnit="m²"
                  confidence={dp.confidence}
                  breakdown={[
                    { label: t('project.interior.brWallsNet'), value: dp.sienos_m2, unit: 'm²' },
                    { label: t('project.interior.brCeiling'),  value: dp.lubos_m2,  unit: 'm²' },
                  ]}
                  note={dp.pastaba}
                />

                <CalcCard
                  color="amber"
                  title={t('project.interior.cardCorners')}
                  mainValue={gk.viso_m}
                  mainUnit="m"
                  confidence={gk.confidence}
                  breakdown={[
                    { label: t('project.interior.brOuterCorners'), value: gk.isoriniu_kampu_vnt, unit: 'vnt' },
                    { label: t('project.interior.brAvgCeiling'),   value: gk.vidutinis_aukstis_m, unit: 'm' },
                  ]}
                />

                <CalcCard
                  color="green"
                  title={t('project.interior.cardReveals')}
                  mainValue={angValue}
                  mainUnit="m"
                  confidence={ang.confidence}
                  extra={
                    <div className="mb-2">
                      <Toggle
                        label={t('project.interior.toggleBothSides')}
                        value={doubleSides}
                        onChange={setDoubleSides}
                      />
                    </div>
                  }
                  breakdown={[
                    { label: t('project.interior.brWindows'), value: ang.langu_vnt, unit: 'vnt' },
                    { label: t('project.interior.brDoors'),   value: ang.duru_vnt,  unit: 'vnt' },
                    { label: t('project.interior.brArea'),    value: ang.area_m2,   unit: 'm²'  },
                  ]}
                />

                <CalcCard
                  color="purple"
                  title={t('project.interior.cardCeilingPerim')}
                  mainValue={lp.viso_m}
                  mainUnit="m"
                  confidence={lp.confidence}
                  note={lp.skaiciavimo_budas}
                />

                <CalcCard
                  color="teal"
                  title={t('project.interior.cardCurtainNiches')}
                  mainValue={un.viso_m || lubuData.uzuolaidu_nisu_m}
                  mainUnit="m"
                  confidence={un.confidence}
                  breakdown={(un.details || []).map((d, i) => ({
                    label: d.vieta || d.room ? `${d.room || ''} ${d.wall || ''}`.trim() || t('project.interior.niche', { n: i + 1 }) : t('project.interior.niche', { n: i + 1 }),
                    value: d.ilgis_mm ? d.ilgis_mm / 1000 : (d.length_mm ? d.length_mm / 1000 : null),
                    unit: 'm',
                  }))}
                />

                <CalcCard
                  color="indigo"
                  title={t('project.interior.cardBaseboards')}
                  mainValue={gj.viso_m}
                  mainUnit="m"
                  confidence={gj.confidence}
                  note={t('project.interior.baseboardNote')}
                />

              </div>
            </div>
          )}

          {/* ── Additional metrics ─────────────────────────────────────────── */}
          {(daz.viso_l != null || gkl.vnt != null || gls.kg != null) && (
            <div>
              <h2 className="text-sm font-semibold text-foreground mb-3">{t('project.interior.materialsHead')}</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">

                <CalcCard
                  color="blue"
                  title={t('project.interior.cardPaintPrimer')}
                  mainValue={daz.viso_l}
                  mainUnit="l"
                  confidence={daz.confidence}
                  breakdown={[
                    { label: t('project.interior.brWallPaint'),    value: daz.sienos_l, unit: 'l' },
                    { label: t('project.interior.brCeilingPaint'), value: daz.lubos_l,  unit: 'l' },
                    { label: t('project.interior.brPrimer'),       value: daz.gruntas_l, unit: 'l' },
                  ]}
                  note={t('project.interior.paintNote')}
                />

                <CalcCard
                  color="green"
                  title={t('project.interior.cardGkSheets', { method: gkl.metodas === 'praktinis' ? t('project.interior.gkPraktinis') : t('project.interior.gkTikslus') })}
                  mainValue={gkl.vnt}
                  mainUnit="vnt"
                  confidence={gkl.confidence}
                  note={gkl.metodas === 'praktinis' ? t('project.interior.gkNotePraktinis') : t('project.interior.gkNoteTikslus')}
                />

                <CalcCard
                  color="amber"
                  title={t('project.interior.cardGlaistas', { level: gls.lygis || 'Q2' })}
                  mainValue={gls.kg}
                  mainUnit="kg"
                  confidence={gls.confidence}
                  breakdown={[
                    { label: t('project.interior.brBags25'), value: gls.maisai_25kg, unit: 'vnt' },
                  ]}
                  note={t('project.interior.glaistasNote')}
                />

                {/* Task 2: Hidroizoliacija card */}
                {Object.keys(hidroizoliacija).length > 0 && (
                  <CalcCard
                    color="rose"
                    title={t('project.interior.cardHidro')}
                    mainValue={hidroizoliacija.grindys_m2}
                    mainUnit={t('project.interior.hidroUnit')}
                    confidence="medium"
                    breakdown={[
                      { label: t('project.interior.brWallArea'), value: hidroizoliacija.sienos_m2,  unit: 'm²' },
                      { label: t('project.interior.brSealTape'), value: hidroizoliacija.juosta_m, unit: 'm' },
                      { label: t('project.interior.brMembrane'), value: hidroizoliacija.membrana_kg, unit: 'kg' },
                    ]}
                    note={t('project.interior.hidroNote', { rooms: (hidroizoliacija.dregnas_patalpos || []).join(', ') })}
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
                {t('project.interior.roomsListHead')}
                <Badge variant="secondary" className="text-xs font-normal">
                  {t('project.interior.roomsCount', { count: (project.v8_rooms || project.patalpos || []).length })}
                </Badge>
              </h2>
              <span className="text-xs text-muted-foreground">
                {t('project.interior.roomsEditHint')}
              </span>
            </div>
            {(!project.v8_rooms || project.v8_rooms.length === 0) && (
              <div className="mb-3 p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-lg text-xs text-amber-900 dark:text-amber-200">
                {t('project.interior.noRooms')}
              </div>
            )}
            <RoomsGrid
              initialRooms={
                project.v8_rooms && project.v8_rooms.length > 0
                  ? project.v8_rooms
                  : (project.patalpos || []).map(p => ({
                      nr: p.nr || '01',
                      pavadinimas: p.pavadinimas || t('project.interior.roomFallback'),
                      paskirtis: p.paskirtis || 'gyvenamoji',
                      plotas_m2: p.plotas_m2 || 0,
                      perimetras_m: p.perimetras_m || 0,
                      lubu_aukstis_m: p.lubu_aukstis_m || 2.82,
                    }))
              }
              onShowOnPdf={(pageNr) => {
                if (pdfUrl) {
                  setFocusedPage(pageNr);
                  setStep('brezinys');
                }
              }}
              project={project}
              onJumpToPage={(pageNr) => {
                if (pdfUrl) {
                  setFocusedPage(pageNr);
                  setStep('brezinys');
                }
              }}
              onChange={handleRoomsChange}
            />
            {isRecomputing && (
              <div className="mt-2 text-xs text-muted-foreground inline-flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                {t('project.interior.recomputing')}
              </div>
            )}
          </div>

          {/* ── Detalus darbų sąrašas (visos Rangovo-stiliaus pozicijos) ──── */}
          <DarbuSarasas items={project.darbu_sarasas || []} />

          {/* ── Additional materials ──────────────────────────────────────── */}
          {Object.values(pk).some(v => v != null) && (
            <div className="bg-card border border-border rounded-xl p-4">
              <h2 className="text-sm font-semibold text-foreground mb-3">{t('project.interior.additionalHead')}</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-0">
                <QtyRow label={t('project.interior.qtyWallTiles')} value={pk.plyteles_m2 ?? bk.sienu_plyteles_m2} unit="m²" />
                <QtyRow label={t('project.interior.qtyParquet')} value={pk.parketlentes_m2 ?? bk.grindu_parketlentes_m2} unit="m²" />
                <QtyRow label={t('project.interior.qtyBaseboards')} value={pk.grindjuostes_m} unit="m" />
                <QtyRow label={t('project.interior.qtyLedStrips')} value={pk.led_juostos_m} unit="m" />
                <QtyRow label={t('project.interior.qtyGkpCeiling')} value={pk.gkp_lubos_m2} unit="m²" />
                <QtyRow label={t('project.interior.qtyLedNiches')} value={pk.led_nisos_m} unit="m" />
              </div>
            </div>
          )}

          {/* ── Collapsible detail sections ─────────────────────────────── */}

          {hasWall && (
            <Section icon={Paintbrush} title={t('project.interior.wallFinishHead')} badge={t('project.interior.wallFinishBadge', { count: Object.keys(sienuApdaila).length })}>
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
            <Section icon={Layers} title={t('project.interior.ceilingHead')}>
              <div>
                <QtyRow label={t('project.interior.qtyGkpArea')}       value={lubuData.gkp_m2}             unit="m²" />
                <QtyRow label={t('project.interior.qtyLedNicheLen')}   value={lubuData.led_nisu_m}          unit="m" />
                <QtyRow label={t('project.interior.qtyCurtainNicheLen')} value={lubuData.uzuolaidu_nisu_m}  unit="m" />
                <QtyRow label={t('project.interior.qtyGkpBoxLen')}     value={lubuData.gkp_dezuciu_m}       unit="m" />
              </div>
            </Section>
          )}

          {hasGrindys && (
            <Section icon={Square} title={t('project.interior.floorHead')}>
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
                  <QtyRow label={t('project.interior.qtyBaseboards')} value={grindys.grindjuostes_m} unit="m" />
                </div>
              )}
            </Section>
          )}

          {hasElektra && (
            <Section icon={Zap} title={t('project.interior.electricHead')}>
              <div>
                <QtyRow label={t('project.interior.qtyOutlets')}         value={elektra.rozetes_vnt}                unit="vnt" />
                <QtyRow label={t('project.interior.qtySwitches')}        value={elektra.jungikliai_vnt}             unit="vnt" />
                <QtyRow label={t('project.interior.qtyInternetOutlets')} value={elektra.interneto_rozetes_vnt}      unit="vnt" />
                <QtyRow label={t('project.interior.qtyAntennas')}        value={elektra.antenos_vnt}                unit="vnt" />
                <QtyRow label={t('project.interior.qtyUsbC')}            value={elektra.usb_c_vnt}                  unit="vnt" />
                <QtyRow label={t('project.interior.qtyThermostats')}     value={elektra.termostatai_vnt}            unit="vnt" />
                <QtyRow label={t('project.interior.qtyApplianceConn')}   value={elektra.prietaisu_pajungimai_vnt}   unit="vnt" />
                <QtyRow label={t('project.interior.qtyGateControl')}     value={elektra.vartai_vnt}                 unit="vnt" />
              </div>
            </Section>
          )}

          {hasSantech && (
            <Section icon={Droplets} title={t('project.interior.plumbingHead')}>
              <div>
                <QtyRow label={t('project.interior.qtyWcFrames')}      value={santechnika.wc_remai_vnt}           unit="vnt" />
                <QtyRow label={t('project.interior.qtyShowerSystems')} value={santechnika.duso_sistemos_vnt}      unit="vnt" />
                <QtyRow label={t('project.interior.qtyWashbasins')}    value={santechnika.praustuves_vnt}         unit="vnt" />
                <QtyRow label={t('project.interior.qtyBathFaucets')}   value={santechnika.vonios_maistuvai_vnt}   unit="vnt" />
                <QtyRow label={t('project.interior.qtyWashers')}       value={santechnika.skalbimo_masinos_vnt}   unit="vnt" />
                <QtyRow label={t('project.interior.qtyDrains')}        value={santechnika.trapai_vnt}             unit="vnt" />
                <QtyRow label={t('project.interior.qtyAircon')}        value={santechnika.kondicionieriai_vnt}    unit="vnt" />
                <QtyRow label={t('project.interior.qtyFaucets')}       value={santechnika.maistuvai_vnt}          unit="vnt" />
              </div>
            </Section>
          )}

          {hasApsviet && (
            <Section icon={Lightbulb} title={t('project.interior.lightingHead')}>
              <div>
                <QtyRow label={t('project.interior.qtyRecessed')}         value={apsvietimas.ileidziami_sviestuvai_vnt}  unit="vnt" />
                <QtyRow label={t('project.interior.qtyPendant')}          value={apsvietimas.pakabinami_sviestuvai_vnt}  unit="vnt" />
                <QtyRow label={t('project.interior.qtyWallLights')}       value={apsvietimas.sieniniai_sviestuvai_vnt}   unit="vnt" />
                <QtyRow label={t('project.interior.qtySurface')}          value={apsvietimas.pavirsiniai_sviestuvai_vnt} unit="vnt" />
                <QtyRow label={t('project.interior.qtyLedStrips')}        value={apsvietimas.led_juostos_m}              unit="m" />
                <QtyRow label={t('project.interior.qtyMotionSensors')}    value={apsvietimas.judesio_davikliai_vnt}      unit="vnt" />
                <QtyRow label={t('project.interior.qtyFireDetectors')}    value={apsvietimas.gaisro_davikliai_vnt}       unit="vnt" />
                <QtyRow label={t('project.interior.qtySpeakers')}         value={apsvietimas.garso_koloneles_vnt}        unit="vnt" />
                <QtyRow label={t('project.interior.qtyElectricCurtains')} value={apsvietimas.elektrines_uzuolaidos_vnt}  unit="vnt" />
              </div>
            </Section>
          )}

          {/* Angokraščiai detail */}
          {ang.details?.length > 0 && (
            <Section icon={CornerUpRight} title={t('project.interior.revealsDetailHead')} badge={t('project.interior.revealsBadge', { count: ang.details.length })}>
              <div className="space-y-0">
                {ang.details.map((d, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                    <span className="text-sm text-muted-foreground capitalize">{d.tipas} {i + 1}</span>
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {fmt(d.plotis_m)} × {fmt(d.aukstis_m)} m →{' '}
                      <span className="font-medium text-foreground">{fmt(d.perimetras_m)} m</span>
                      {doubleSides && <span className="text-muted-foreground">{t('project.interior.revealX2', { value: fmt(d.perimetras_m * 2) })}</span>}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Rooms */}
          <Section icon={Home} title={t('project.interior.roomsSectionHead')} badge={rooms.length} defaultOpen={rooms.length <= 12}>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {rooms.map(room => (
                <RoomCard
                  key={room.nr}
                  room={room}
                  project={project}
                  onJumpToPage={(pageNr) => {
                    if (pdfUrl) { setFocusedPage(pageNr); setStep('brezinys'); }
                  }}
                />
              ))}
            </div>
          </Section>

          {notes.length > 0 && (
            <Section icon={AlertCircle} title={t('project.interior.notesHead')}>
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
                <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">{t('project.interior.checkReminder')}</span>
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
                        title={t('project.interior.close')}
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

      </div>

      {/* ── The step's own exit: „Atgal" + ONE big button ────────────────── */}
      <StepFooter
        step={step}
        setStep={goStep}
        nextLabel={step === 'siusti' ? null : t(`project.steps.next.${step}`)}
        nextTitle={step === 'siusti' ? null : t(`project.steps.nextTitles.${step}`)}
        onNext={() => {
          const i = STEPS.indexOf(step);
          if (i >= 0 && i < STEPS.length - 1) goStep(STEPS[i + 1]);
        }}
      >
      </StepFooter>

    </div>
  );
}

// ── STEP 4 · SIŲSTI ───────────────────────────────────────────────────────────
//
// Design §E5: three actions and, before sending, ONE sentence — not a list of
// warnings. „3 eilutės be kiekio bus praleistos. Siųsti?"

function SendStep({ project }) {
  const { t } = useTranslation();
  const rows = project.darbu_sarasas || [];
  const noQty = rows.filter((r) => !Number(r?.kiekis)).length;
  const noPrice = rows.filter((r) => Number(r?.kiekis) && !Number(r?.kaina)).length;
  return (
    <div className="border border-border rounded-xl bg-card p-6 space-y-5">
      <div>
        <h2 className="font-semibold text-foreground" style={{ fontSize: 17 }}>
          {t('project.send.title')}
        </h2>
        <p className="text-muted-foreground mt-1" style={{ fontSize: 15 }}>
          {t('project.send.subtitle')}
        </p>
      </div>

      {/* The one sentence before sending. Never a wall of warnings. */}
      <p
        className="rounded border px-3 py-2.5"
        style={{
          fontSize: 15,
          borderColor: (noQty || noPrice)
            ? 'hsl(var(--conf-med) / 0.45)' : 'hsl(var(--border))',
          background: (noQty || noPrice)
            ? 'hsl(var(--conf-med) / 0.08)' : 'hsl(var(--muted) / 0.3)',
          color: 'hsl(var(--foreground))',
        }}
      >
        {noQty > 0
          ? t('project.send.checkNoQty', { count: noQty })
          : noPrice > 0
            ? t('project.send.checkNoPrice', { count: noPrice })
            : t('project.send.checkOk', { count: rows.length })}
      </p>

      <div className="flex items-center gap-3 flex-wrap">
        <ExportDropdown project={project} />
        <ShareButton project={project} />
      </div>

      <div className="border-t border-border/50 pt-4 text-muted-foreground space-y-1" style={{ fontSize: 14 }}>
        <p><strong className="text-foreground">{t('project.interior.exportExcelBold')}</strong>{t('project.interior.exportExcelDesc')}</p>
        <p><strong className="text-foreground">{t('project.interior.exportPdfBold')}</strong>{t('project.interior.exportPdfDesc')}</p>
        <p><strong className="text-foreground">{t('project.send.emailBold')}</strong>{t('project.send.emailDesc')}</p>
      </div>
    </div>
  );
}

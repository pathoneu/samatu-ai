/**
 * SanityWarningsBanner — the CLAUDE.md §6 cross-checks, out loud.
 *
 * These checks (dažomas plotas 2,5–4× grindų ploto, lubos ≈ grindys,
 * grindjuostė ≈ perimetras − 0,8 m/durys, dažų sąnaudos, GKP lapai,
 * angokraščiai) are the only thing standing between the estimator and a
 * confidently wrong number on a project we have never seen. A 2026-08 audit
 * found them muted four ways; three of them were here:
 *
 *   · severity was dropped in the backend mirror, so a `severity:"high"`
 *     violation rendered as a blue INFO row (fixed in sanity_mirror.py);
 *   · INFO was collapsed by default AND excluded from the counter, so the
 *     demoted check was invisible in both places at once;
 *   · pressing "Atnaujinti AI patikrinimus" REPLACED the whole list, deleting
 *     every stream the rebuild did not produce.
 *
 * Tiers now come from `lib/sanitySeverity.js` (shared contract with the
 * backend): high → red, expanded, counted; med → amber, expanded, counted;
 * low → muted, collapsed, counted separately as "pastabos".
 *
 * Dismissals persist in localStorage so a user who has judged a warning
 * doesn't re-read it every reload.
 *
 * v3 W1-C (one notice system, audit B#5): ONE Notice instead of three tinted
 * boxes, so the sąmata rows reach the first screen. The line always carries
 * every count; the high tier („Įspėjimai") is always listed in full; „Verta
 * patikrinti" and „Pastabos" open behind „Rodyti visus (N)". Arriving from the
 * top bar's pill (focusNonce) opens everything, as before.
 */

import { useState, useMemo, useEffect } from 'react';
import { useTranslation } from '@/i18n/react';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, X, Eye, RefreshCw, Sliders } from 'lucide-react';

import { revalidateProject } from '../../lib/revalidateApi';
import { noteServerVersion } from '../../lib/projectStore';
import { ltNumber } from '../../lib/ledger';
import {
  SEV_HIGH,
  SEV_MED,
  SEV_LOW,
  ACTION_PRIELAIDOS,
  assumptionFocus,
  expectedSuffix,
  groupBySeverity,
  mergeSanity,
  roomNoteParts,
  summarizeSanity,
  warningAction,
  warningKey,
} from '../../lib/sanitySeverity';
import {
  loadDismissed,
  saveDismissed,
  subscribeDismissals,
  withoutDismissed,
} from '../../lib/sanityDismissals';
import { cleanUserText } from '@/lib/userText';
import Notice from '@/components/ui/Notice';

// Colours come from the semantic confidence tokens in index.css
// (--conf-low red / --conf-med amber) — never raw bg-red-500/bg-gray-900,
// which were dark-theme leftovers invisible on the parchment page.
const SEVERITY_META = {
  [SEV_HIGH]: {
    icon: AlertCircle,
    labelKey: 'project.sanity.severityHigh',
    tone: 'var(--conf-low)',
    defaultOpen: true,
  },
  [SEV_MED]: {
    icon: AlertTriangle,
    labelKey: 'project.sanity.severityMed',
    tone: 'var(--conf-med)',
    defaultOpen: true,
  },
  [SEV_LOW]: {
    icon: Info,
    labelKey: 'project.sanity.severityLow',
    tone: 'var(--muted-foreground)',
    defaultOpen: false,
  },
};

export default function SanityWarningsBanner({
  sanity, projectId, onRevalidated, onOpenAssumptions, focusNonce = 0,
}) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(loadDismissed);
  // `subscribeDismissals` was imported and never wired, so the banner was the
  // only surface NOT listening to the store it writes to: a second tab (or the
  // pill, if it ever grows a reset) could change the set and this list would
  // keep rendering the stale one until a remount.
  useEffect(() => subscribeDismissals(() => setDismissed(loadDismissed())), []);
  const [openOverride, setOpenOverride] = useState({});
  const [revalidating, setRevalidating] = useState(false);
  const [revalidateError, setRevalidateError] = useState(null);
  // The med/low tiers behind one click (the high tier is always shown).
  const [expanded, setExpanded] = useState(false);

  const warnings = useMemo(
    () => (Array.isArray(sanity?.warnings) ? sanity.warnings : []),
    [sanity]
  );
  const summary = sanity?.summary || {};

  // Filter dismissed. Hooks must run unconditionally (rules-of-hooks) — the
  // "no warnings" early return happens after, not before, these calls.
  const active = useMemo(
    () => withoutDismissed(warnings, dismissed, warningKey),
    [warnings, dismissed]
  );
  const counts = useMemo(() => summarizeSanity({ warnings: active }), [active]);
  const groups = useMemo(() => groupBySeverity(active), [active]);

  // Arriving from the landing-tab severity pill: force the loud groups open
  // so the jump never lands on a collapsed header.
  useEffect(() => {
    if (!focusNonce) return;
    setOpenOverride(prev => ({ ...prev, [SEV_HIGH]: true, [SEV_MED]: true }));
    setExpanded(true);
  }, [focusNonce]);

  if (!sanity || warnings.length === 0) return null;

  if (active.length === 0) {
    return (
      <div className="text-meta text-muted-foreground flex items-center gap-2 py-2">
        <Eye className="w-3.5 h-3.5" aria-hidden="true" />
        {t('project.sanity.allHiddenA')}{warnings.length}{t('project.sanity.allHiddenB')}
        <button
          onClick={() => { setDismissed(new Set()); saveDismissed(new Set()); }}
          title={t('project.sanity.resetTitle')}
          className="underline hover:text-foreground"
        >
          {t('project.sanity.reset')}
        </button>
      </div>
    );
  }

  const dismiss = (w) => {
    const key = warningKey(w);
    setDismissed(prev => {
      const next = new Set(prev);
      next.add(key);
      saveDismissed(next);
      return next;
    });
  };

  const dismissAllInGroup = (severity) => {
    setDismissed(prev => {
      const next = new Set(prev);
      for (const [sev, items] of groups) {
        if (sev !== severity) continue;
        for (const w of items) next.add(warningKey(w));
      }
      saveDismissed(next);
      return next;
    });
  };

  const isOpen = (severity) => (
    openOverride[severity] !== undefined
      ? openOverride[severity]
      : SEVERITY_META[severity].defaultOpen
  );

  const toggleGroup = (severity) => {
    setOpenOverride(g => ({ ...g, [severity]: !isOpen(severity) }));
  };

  const handleRevalidate = async () => {
    if (!projectId || revalidating) return;
    setRevalidating(true);
    setRevalidateError(null);
    try {
      const fresh = await revalidateProject(projectId);
      // The server just persisted a new version; re-base the tab on it BEFORE
      // the merged result is written back, or the write-through 409s against
      // our own save and the user is told their changes were lost.
      noteServerVersion(projectId, fresh?.updated_at);
      // MERGE, never replace wholesale: the rows of the checks the refresh
      // re-ran are replaced by its list (a check that passes now leaves); the
      // rest stay — dropping those is how "refresh the checks" quietly turned
      // into "delete most of the checks".
      onRevalidated?.({
        ...fresh,
        lt_sanity: mergeSanity(sanity, fresh?.lt_sanity),
      });
    } catch (err) {
      setRevalidateError(err.message || t('project.sanity.revalidateFail'));
    } finally {
      setRevalidating(false);
    }
  };

  const hasHigh = groups.some(([sev]) => sev === SEV_HIGH);
  const tone = hasHigh ? 'error' : groups.some(([sev]) => sev === SEV_MED) ? 'warning' : 'info';
  const restCount = groups.filter(([sev]) => sev !== SEV_HIGH).reduce((n, [, items]) => n + items.length, 0);
  const shownGroups = expanded ? groups : groups.filter(([sev]) => sev === SEV_HIGH);

  return (
    <Notice
      tone={tone}
      title={t('project.sanity.headerTitle')}
      data-testid="sanity-notice"
      action={(
        <>
          {projectId && (
            <button
              onClick={handleRevalidate}
              disabled={revalidating}
              className="inline-flex items-center gap-1 text-meta underline hover:no-underline disabled:opacity-50 disabled:no-underline"
              style={{ color: 'hsl(var(--accent-2))' }}
              title={t('project.sanity.revalidateTitle')}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${revalidating ? 'animate-spin' : ''}`} aria-hidden="true" />
              {revalidating ? t('project.sanity.revalidating') : t('project.sanity.revalidate')}
            </button>
          )}
          {restCount > 0 && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              aria-expanded={expanded}
              className="inline-flex min-h-[32px] items-center gap-1 rounded border border-border bg-card px-2.5 text-ui font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              data-testid="sanity-toggle"
            >
              {expanded ? <ChevronUp className="w-4 h-4" aria-hidden="true" /> : <ChevronDown className="w-4 h-4" aria-hidden="true" />}
              {expanded ? t('project.sanity.collapse') : t('project.sanity.showAll', { count: restCount })}
            </button>
          )}
        </>
      )}
    >
      {/* every count, always on the line — the honest-disclosure rule */}
      <p className="flex flex-wrap items-center gap-x-2 text-muted-foreground">
        {groups.map(([severity, items], i) => (
          <span key={severity} className="inline-flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">·</span>}
            <span className={severity === SEV_LOW ? undefined : 'font-medium text-foreground'}>
              {t(SEVERITY_META[severity].labelKey)} {items.length}
            </span>
          </span>
        ))}
        {summary.rooms_count != null && (
          <>
            <span aria-hidden="true">·</span>
            <span>{t('project.sanity.summary', { count: Number(summary.rooms_count) || 0, area: ltNumber(summary.total_area_m2, 1) })}</span>
          </>
        )}
      </p>
      {revalidateError && (
        <p className="text-destructive" role="alert">{revalidateError}</p>
      )}

      {shownGroups.map(([severity, items]) => {
        const meta = SEVERITY_META[severity];
        const Icon = meta.icon;
        const open = isOpen(severity);

        return (
          <div key={severity} className="border-t border-border pt-1.5" data-sanity-group={severity}>
            <button
              onClick={() => toggleGroup(severity)}
              aria-expanded={open}
              className="w-full flex items-center gap-2 py-1 text-left"
            >
              <Icon className="w-4 h-4 shrink-0" style={{ color: `hsl(${meta.tone})` }} aria-hidden="true" />
              <span className="text-ui font-semibold text-foreground">
                {t('project.sanity.groupHead', { label: t(meta.labelKey), count: items.length })}
              </span>
              <span className="ml-auto flex items-center gap-2">
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); dismissAllInGroup(severity); }}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); dismissAllInGroup(severity); } }}
                  className="text-meta text-muted-foreground hover:text-foreground underline cursor-pointer"
                  title={t('project.sanity.hideAllTitle')}
                >
                  {t('project.sanity.hideAll')}
                </span>
                {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" aria-hidden="true" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />}
              </span>
            </button>
            {open && (
              <ul className="pb-1 space-y-2">
                {items.map((w, i) => {
                  const action = warningAction(w);
                  const expected = expectedSuffix(w);
                  // „101 Tambūras: …" — never „[101]Tambūras: …"
                  const note = roomNoteParts(w);
                  return (
                    <li key={warningKey(w) + i} className="flex items-start gap-2 group">
                      <span className="text-muted-foreground shrink-0" aria-hidden="true">·</span>
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="text-foreground">
                          {note.room && <><strong>{note.room}</strong>{' '}</>}
                          {cleanUserText(note.text)}
                          {expected && (
                            <span className="text-muted-foreground">
                              {' '}{t('project.sanity.expectedInline', { expected })}
                            </span>
                          )}
                        </div>
                        {w.hint && (
                          <div className="text-muted-foreground">{cleanUserText(w.hint)}</div>
                        )}
                        {action === ACTION_PRIELAIDOS && onOpenAssumptions && (
                          <button
                            type="button"
                            /* Land on the control the warning names, not at
                               the top of a long panel. (2026-09-02, Patikra.) */
                            onClick={() => onOpenAssumptions(assumptionFocus(w))}
                            className="inline-flex items-center gap-1 underline hover:no-underline"
                            style={{ color: 'hsl(var(--accent-2))' }}
                          >
                            <Sliders className="w-3.5 h-3.5" aria-hidden="true" />
                            {t('project.sanity.openAssumptions')}
                          </button>
                        )}
                      </div>
                      <button
                        onClick={() => dismiss(w)}
                        title={t('project.sanity.hideOneTitle')}
                        /* Was hover-only: the only way to dismiss a warning
                           was to find it with the mouse. (Design §5.) */
                        aria-label={t('project.sanity.hideOneTitle')}
                        className="shrink-0 inline-flex items-center justify-center rounded text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                        style={{ width: 28, height: 28 }}
                      >
                        <X className="w-3.5 h-3.5" aria-hidden="true" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </Notice>
  );
}

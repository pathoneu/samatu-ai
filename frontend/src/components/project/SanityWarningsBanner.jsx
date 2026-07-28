/**
 * SanityWarningsBanner — rodo LT specifikos warnings vartotojui.
 *
 * Backend grąžina `lt_sanity.warnings[]` — kiekvienas su level (WARNING/INFO/ERROR)
 * ir message. Vartotojas mato kuriuose kambariuose AI gali būti suklydęs.
 *
 * Sprint §27 (2026-04-29): grouped by severity, dismissable per-warning,
 * collapsible per-group. Dismissals persist in localStorage so users don't
 * see same warnings every reload.
 */

import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, X, Eye, RefreshCw } from 'lucide-react';

import { revalidateProject } from '../../lib/revalidateApi';

// label resolves against i18n at render (project.sanity.level*).
const LEVEL_META = {
  ERROR:   { icon: AlertCircle,   color: 'text-red-300 bg-red-500/10 border-red-500/30',   labelKey: 'project.sanity.levelError',   order: 0 },
  WARNING: { icon: AlertTriangle, color: 'text-amber-300 bg-amber-500/10 border-amber-500/30', labelKey: 'project.sanity.levelWarning', order: 1 },
  INFO:    { icon: Info,          color: 'text-blue-300 bg-blue-500/10 border-blue-500/30',   labelKey: 'project.sanity.levelInfo',    order: 2 },
};

const DISMISSED_KEY = 'samatu_sanity_dismissed';

function loadDismissed() {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

function saveDismissed(set) {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(Array.from(set).slice(-200)));
  } catch {}
}

function warningKey(w) {
  // Stable hash from level + room + field + message for dismissal tracking
  return `${w.level}|${w.room || ''}|${w.field || ''}|${(w.message || '').slice(0, 100)}`;
}

export default function SanityWarningsBanner({ sanity, projectId, onRevalidated }) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(loadDismissed);
  const [expandedGroups, setExpandedGroups] = useState({ ERROR: true, WARNING: true, INFO: false });
  const [revalidating, setRevalidating] = useState(false);
  const [revalidateError, setRevalidateError] = useState(null);

  const warnings = sanity?.warnings || [];
  const summary = sanity?.summary || {};

  // Filter dismissed. Hook must run unconditionally (rules-of-hooks) —
  // the "no warnings" early return happens after, not before, this call.
  const active = useMemo(
    () => warnings.filter(w => !dismissed.has(warningKey(w))),
    [warnings, dismissed]
  );

  if (!sanity || warnings.length === 0) return null;

  if (active.length === 0) {
    return (
      <div className="text-xs text-muted-foreground flex items-center gap-2 py-2">
        <Eye className="w-3 h-3" />
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

  // Group by level
  const groups = active.reduce((acc, w) => {
    const lvl = w.level || 'INFO';
    if (!acc[lvl]) acc[lvl] = [];
    acc[lvl].push(w);
    return acc;
  }, {});

  const dismiss = (w) => {
    const key = warningKey(w);
    setDismissed(prev => {
      const next = new Set(prev);
      next.add(key);
      saveDismissed(next);
      return next;
    });
  };

  const dismissAllInGroup = (level) => {
    setDismissed(prev => {
      const next = new Set(prev);
      for (const w of (groups[level] || [])) next.add(warningKey(w));
      saveDismissed(next);
      return next;
    });
  };

  const toggleGroup = (level) => {
    setExpandedGroups(g => ({ ...g, [level]: !g[level] }));
  };

  const sortedLevels = Object.keys(groups).sort(
    (a, b) => (LEVEL_META[a]?.order ?? 99) - (LEVEL_META[b]?.order ?? 99)
  );

  const handleRevalidate = async () => {
    if (!projectId || revalidating) return;
    setRevalidating(true);
    setRevalidateError(null);
    try {
      const fresh = await revalidateProject(projectId);
      onRevalidated?.(fresh);
    } catch (err) {
      setRevalidateError(err.message || t('project.sanity.revalidateFail'));
    } finally {
      setRevalidating(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{t('project.sanity.aiCheckA')}<strong className="text-foreground">{active.length}</strong>{t('project.sanity.aiCheckB')}</span>
        <span>·</span>
        <span>{t('project.sanity.summary', { rooms: summary.rooms_count, area: summary.total_area_m2 })}</span>
        {projectId && (
          <button
            onClick={handleRevalidate}
            disabled={revalidating}
            className="ml-auto inline-flex items-center gap-1 text-xs text-blue-700 hover:text-blue-900 underline disabled:opacity-50 disabled:no-underline"
            title={t('project.sanity.revalidateTitle')}
          >
            <RefreshCw className={`w-3 h-3 ${revalidating ? 'animate-spin' : ''}`} />
            {revalidating ? t('project.sanity.revalidating') : t('project.sanity.revalidate')}
          </button>
        )}
      </div>
      {revalidateError && (
        <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded px-2 py-1">
          {revalidateError}
        </div>
      )}

      {sortedLevels.map(level => {
        const meta = LEVEL_META[level] || LEVEL_META.INFO;
        const Icon = meta.icon;
        const items = groups[level];
        const expanded = expandedGroups[level] !== false;

        return (
          <div key={level} className={`border rounded-lg ${meta.color}`}>
            <button
              onClick={() => toggleGroup(level)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left"
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="text-sm font-semibold">
                {t('project.sanity.groupHead', { label: t(meta.labelKey), count: items.length })}
              </span>
              <span className="ml-auto flex items-center gap-2">
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); dismissAllInGroup(level); }}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); dismissAllInGroup(level); } }}
                  className="text-xs opacity-70 hover:opacity-100 underline cursor-pointer"
                  title={t('project.sanity.hideAllTitle')}
                >
                  {t('project.sanity.hideAll')}
                </span>
                {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </span>
            </button>
            {expanded && (
              <ul className="px-3 pb-2 space-y-1.5">
                {items.map((w, i) => (
                  <li key={i} className="text-xs flex items-start gap-2 group">
                    <span className="opacity-60 shrink-0 mt-0.5">·</span>
                    <span className="flex-1">
                      {w.room && <strong className="mr-1">[{w.room}]</strong>}
                      {w.message}
                    </span>
                    <button
                      onClick={() => dismiss(w)}
                      title={t('project.sanity.hideOneTitle')}
                      className="opacity-0 group-hover:opacity-60 hover:opacity-100 shrink-0"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

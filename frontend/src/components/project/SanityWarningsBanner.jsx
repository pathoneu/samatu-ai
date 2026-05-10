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
import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp, X, Eye, RefreshCw } from 'lucide-react';

import { revalidateProject } from '../../lib/revalidateApi';

const LEVEL_META = {
  ERROR:   { icon: AlertCircle,   color: 'text-red-700 bg-red-50 border-red-200',   label: 'Klaidos',     order: 0 },
  WARNING: { icon: AlertTriangle, color: 'text-amber-800 bg-amber-50 border-amber-200', label: 'Įspėjimai', order: 1 },
  INFO:    { icon: Info,          color: 'text-blue-700 bg-blue-50 border-blue-200',   label: 'Info',       order: 2 },
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
  const [dismissed, setDismissed] = useState(loadDismissed);
  const [expandedGroups, setExpandedGroups] = useState({ ERROR: true, WARNING: true, INFO: false });
  const [revalidating, setRevalidating] = useState(false);
  const [revalidateError, setRevalidateError] = useState(null);

  if (!sanity || !sanity.warnings || sanity.warnings.length === 0) return null;

  const warnings = sanity.warnings;
  const summary = sanity.summary || {};

  // Filter dismissed
  const active = useMemo(
    () => warnings.filter(w => !dismissed.has(warningKey(w))),
    [warnings, dismissed]
  );

  if (active.length === 0) {
    return (
      <div className="text-xs text-muted-foreground flex items-center gap-2 py-2">
        <Eye className="w-3 h-3" />
        Visi {warnings.length} įspėjimai paslėpti.
        <button
          onClick={() => { setDismissed(new Set()); saveDismissed(new Set()); }}
          className="underline hover:text-foreground"
        >
          Atstatyti
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
      setRevalidateError(err.message || 'Nepavyko atnaujinti');
    } finally {
      setRevalidating(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>AI patikrinimas: <strong className="text-foreground">{active.length}</strong> aktyvūs įspėjimai</span>
        <span>·</span>
        <span>{summary.rooms_count} patalpų, {summary.total_area_m2} m²</span>
        {projectId && (
          <button
            onClick={handleRevalidate}
            disabled={revalidating}
            className="ml-auto inline-flex items-center gap-1 text-xs text-blue-700 hover:text-blue-900 underline disabled:opacity-50 disabled:no-underline"
            title="Iš naujo paleisti AI patikrinimus su naujausia validatoriaus versija"
          >
            <RefreshCw className={`w-3 h-3 ${revalidating ? 'animate-spin' : ''}`} />
            {revalidating ? 'Atnaujinama…' : 'Atnaujinti AI patikrinimus'}
          </button>
        )}
      </div>
      {revalidateError && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
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
                {meta.label} ({items.length})
              </span>
              <span className="ml-auto flex items-center gap-2">
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => { e.stopPropagation(); dismissAllInGroup(level); }}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); dismissAllInGroup(level); } }}
                  className="text-xs opacity-70 hover:opacity-100 underline cursor-pointer"
                  title="Paslėpti visus šios kategorijos įspėjimus"
                >
                  paslėpti visus
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
                      title="Paslėpti šį įspėjimą"
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

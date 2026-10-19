/**
 * ProjectRow — one project as a status row on „Projektai" (Pathon v3 W5-C, C6 / coverage #216): the name,
 * its state in plain words, the last change, the totals, and the one next step as a button. The whole row
 * opens the project; the button goes straight to the step that is waiting. Decisions in lib/projectRows.
 */

import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { format } from 'date-fns';
import { ArrowRight, Loader2 } from 'lucide-react';

import { projectRow, rowEuro } from '@/lib/projectRows';
import { vatPercent } from '@/lib/vatMode';

function when(d) {
  if (!d) return '—';
  try { return format(d, 'yyyy-MM-dd HH:mm'); } catch { return '—'; }
}

export default function ProjectRow({ project }) {
  const { t } = useTranslation();
  const r = projectRow(project, vatPercent(project));
  const name = r.name || t('dashboard.card.untitled');
  const stateText = t(`dashboard.row.state.${r.state}`, r.stateParams);
  const body = (
    <>
      <span className="min-w-0">
        <span className="block truncate text-[15px] font-semibold text-foreground">{name}</span>
        {r.company && <span className="block truncate text-ui text-muted-foreground">{r.company}</span>}
      </span>
      <span className="flex items-center gap-1.5 text-ui text-foreground" data-testid="project-row-state">
        {r.state === 'processing' && <Loader2 className="h-4 w-4 animate-spin text-accent-2" aria-hidden="true" />}
        {stateText}
      </span>
      <span className="text-ui tabular-nums text-muted-foreground" title={t('dashboard.row.lastChangeTitle')}>{when(r.lastChange)}</span>
      <span className="text-ui text-muted-foreground">
        {r.totals.gross > 0 && (
          <span className="block text-[15px] font-semibold tabular-nums text-foreground">
            {t('dashboard.row.gross', { sum: rowEuro(r.totals.gross) })}
          </span>
        )}
        <span className="tabular-nums">{t('dashboard.row.counts', { rooms: r.totals.rooms, rows: r.totals.rows })}</span>
      </span>
    </>
  );
  const grid = 'grid grid-cols-1 gap-x-4 gap-y-1 px-4 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1.6fr)_9rem_minmax(0,1.3fr)] md:items-center';
  return (
    <li className="flex flex-col border-t border-border first:border-t-0 md:flex-row md:items-center" data-testid="project-row" data-state={r.state}>
      {r.openable ? (
        <Link to={`/project/${r.id}`} className={`${grid} min-w-0 flex-1 no-underline hover:bg-muted/60`} title={t('dashboard.card.openTitle', { name })}>
          {body}
        </Link>
      ) : (
        <div className={`${grid} min-w-0 flex-1`}>{body}</div>
      )}
      <div className="px-4 pb-3 md:w-56 md:shrink-0 md:pb-0 md:text-right">
        {r.next && (
          <Link
            to={r.next.href}
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-[2px] border border-border bg-card px-3 text-ui font-semibold text-foreground no-underline hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            data-testid="project-row-next"
          >
            {t(`dashboard.row.next.${r.next.key}`)}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        )}
      </div>
    </li>
  );
}

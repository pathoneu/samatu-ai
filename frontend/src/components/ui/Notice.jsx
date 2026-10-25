/**
 * Notice — the ONE notice of the workspace (Pathon v3 W1-C, design 2026-10-18 §6): three tones on the
 * theme tokens, one shape. It replaces the amber/blue/red boxes each banner drew for itself (the audit
 * counted 12 kinds of notice in 4 tints and 3 shapes).
 *
 *   tone    'info' (evergreen) · 'warning' (amber) · 'error' (red — an error, nothing else)
 *   compact one line, sized to its content (the re-read chip, founder decision 6); otherwise a block
 *   oneLine with compact: never wraps (short words + an action that fit the 340 px panel, B2-B); icon={false}
 *   meta    with oneLine: a second line at the 12 px meta size under the first (what must stay visible, B2-B)
 *           drops the leading icon when the action carries one
 *   metaAction  with meta: a control on the second line beside it (a fold's „Dar pranešimai (2)", NoticeFoldMore)
 *   title   the first line, semibold ink; children follow at the 14 px interface size
 *   action  buttons/links at the right; onDismiss adds the ✕ with `dismissLabel` (named, never hover-only)
 *
 * The tone colours the left rule, the tint and the icon; the words are always slate ink — meaning
 * never rides on colour alone, and every text clears 4.5:1.
 */
import { AlertCircle, AlertTriangle, Info, X } from 'lucide-react';

const TONES = {
  info: { token: '--accent-2', Icon: Info, role: 'status' },
  warning: { token: '--conf-med', Icon: AlertTriangle, role: 'status' },
  error: { token: '--destructive', Icon: AlertCircle, role: 'alert' },
};

export const NOTICE_TONES = Object.keys(TONES);

export default function Notice({
  tone = 'info', icon = null, title = null, children = null, action = null,
  onDismiss = null, dismissLabel = 'Uždaryti', compact = false, oneLine = false, meta = null, metaAction = null,
  className = '', ...rest
}) {
  const t = TONES[tone] || TONES.info;
  const Icon = icon === false ? null : (icon || t.Icon);
  const colour = (a) => (a == null ? `hsl(var(${t.token}))` : `hsl(var(${t.token}) / ${a})`);
  const frame = {
    borderColor: colour(0.35),
    borderLeftColor: colour(),
    background: colour(0.06),
  };
  if (compact) {
    return (
      <div
        role={t.role}
        data-notice={tone}
        className={`inline-flex max-w-full ${oneLine && !meta ? "flex-nowrap" : "flex-wrap"} items-center gap-x-2 ${meta ? "gap-y-0" : "gap-y-1"} rounded-panel border border-l-[3px] px-3 py-1.5 text-ui text-foreground ${className}`}
        style={frame}
        {...rest}
      >
        {Icon && <Icon className="h-4 w-4 shrink-0 self-start mt-0.5" style={{ color: colour() }} aria-hidden="true" />}
        {/* wraps, never truncates — in the 340 px panel the counts are the point of the line; an action that does
            not fit beside the words goes under them (B1-D), never squeezes them to a word a line */}
        <span className={oneLine ? "min-w-0 flex-1 leading-snug whitespace-nowrap overflow-hidden text-ellipsis" : "min-w-[12rem] flex-1 leading-snug"}>
          {title && <span className="font-semibold">{title}</span>}
          {title && children ? <span className="text-muted-foreground" aria-hidden="true"> · </span> : null}
          {children}
        </span>
        {action}
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            aria-label={dismissLabel}
            title={dismissLabel}
            className="-mr-1 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
        {meta && !metaAction && <span className="basis-full text-meta text-muted-foreground" data-notice-meta>{meta}</span>}
        {meta && metaAction && (
          <span className="flex basis-full flex-nowrap items-center gap-x-1">
            <span className="text-meta text-muted-foreground" data-notice-meta>{meta}</span>
            {metaAction}
          </span>
        )}
      </div>
    );
  }
  return (
    <div
      role={t.role}
      data-notice={tone}
      className={`flex flex-wrap items-start gap-x-3 gap-y-2 rounded-panel border border-l-[3px] px-3 py-2.5 text-ui text-foreground ${className}`}
      style={frame}
      {...rest}
    >
      {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colour() }} aria-hidden="true" />}
      {/* the actions wrap under the words when the notice is narrow (the 340 px panel) */}
      <div className="min-w-[14rem] flex-1 space-y-1.5">
        {title && <p className="font-semibold leading-snug">{title}</p>}
        {children}
      </div>
      {(action || onDismiss) && (
        <div className="ml-auto flex shrink-0 flex-wrap items-center gap-2">
          {action}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="inline-flex min-h-[32px] items-center gap-1 rounded px-2 text-ui text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-4 w-4" aria-hidden="true" />
              {dismissLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

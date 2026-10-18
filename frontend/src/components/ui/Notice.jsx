/**
 * Notice — the ONE notice of the workspace (Pathon v3 W1-C, design 2026-10-18 §6): three tones on the
 * theme tokens, one shape. It replaces the amber/blue/red boxes each banner drew for itself (the audit
 * counted 12 kinds of notice in 4 tints and 3 shapes).
 *
 *   tone    'info' (evergreen) · 'warning' (amber) · 'error' (red — an error, nothing else)
 *   compact one line, sized to its content (the re-read chip, founder decision 6); otherwise a block
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
  onDismiss = null, dismissLabel = 'Uždaryti', compact = false, className = '', ...rest
}) {
  const t = TONES[tone] || TONES.info;
  const Icon = icon || t.Icon;
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
        className={`inline-flex max-w-full items-center gap-2 rounded-panel border border-l-[3px] px-3 py-1.5 text-ui text-foreground ${className}`}
        style={frame}
        {...rest}
      >
        <Icon className="h-4 w-4 shrink-0" style={{ color: colour() }} aria-hidden="true" />
        <span className="min-w-0 truncate">
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
      </div>
    );
  }
  return (
    <div
      role={t.role}
      data-notice={tone}
      className={`flex items-start gap-3 rounded-panel border border-l-[3px] px-3 py-2.5 text-ui text-foreground ${className}`}
      style={frame}
      {...rest}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: colour() }} aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1.5">
        {title && <p className="font-semibold leading-snug">{title}</p>}
        {children}
      </div>
      {(action || onDismiss) && (
        <div className="flex shrink-0 items-center gap-2">
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

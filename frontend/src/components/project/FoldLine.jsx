/**
 * FoldLine — one compact line that opens in place (Pathon v3 B1-D, the calmed Sąmata page).
 *
 * The founder on his first walk: „the sąmata page is all over the place, I can't see it properly" — five
 * boxes (checks, reminders, the room summary, prices) stood before the first row. Each is now ONE line that
 * names what is inside with its counts („Patikrinimai · Įspėjimai 1 · Verta patikrinti 6 · Pastabos 3 ▸");
 * a click opens it right there, a second click folds it. Nothing is hidden without its count on the line.
 *
 *   title    the line's first word(s), semibold ink
 *   summary  the counts, muted ink (wraps, never truncates)
 *   icon     optional; `iconColor` tints it (the words carry the meaning — never colour alone)
 *   open / onToggle  controlled by the owner (an outside jump — the top bar's checks pill — opens it)
 */
import { ChevronDown, ChevronRight } from 'lucide-react';

export default function FoldLine({
  title, summary = null, icon: Icon = null, iconColor = null, open = false, onToggle, children = null,
  className = '', 'data-testid': testId = undefined,
}) {
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    // in a wrapping row of lines (the Sąmata page) the open one takes the full width, contents under it
    <div className={`min-w-0 rounded-panel border border-border bg-card ${open ? 'basis-full' : 'max-w-full'} ${className}`} data-testid={testId} data-open={open ? '1' : undefined}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full min-h-[40px] flex-wrap items-center gap-x-2 gap-y-0.5 px-2.5 py-1.5 text-left text-ui leading-snug text-foreground hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <Chevron className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        {Icon && <Icon className="h-4 w-4 shrink-0" style={iconColor ? { color: iconColor } : undefined} aria-hidden="true" />}
        <span className="font-semibold">{title}</span>
        {summary != null && summary !== '' && (
          <span className="min-w-0 flex-1 text-muted-foreground">
            {summary}
          </span>
        )}
      </button>
      {open && children && <div className="border-t border-border px-3 py-2">{children}</div>}
    </div>
  );
}

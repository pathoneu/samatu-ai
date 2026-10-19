/**
 * ShortcutsGuide — the „?" panel (2026-10-16, Togal analysis §11): every viewer
 * shortcut by group, read from lib/viewerShortcuts (the same table ViewerHotkeys
 * dispatches on, so it cannot drift), with a one-page printable PDF of it.
 */
import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { Download, GitCompare, ScanLine, Search } from 'lucide-react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet';
import { isMacPlatform, shortcutGuideRows } from '@/lib/viewerShortcuts';
import { downloadShortcutSheet } from '@/lib/shortcutsPdf';

const TOP_BUTTONS = [
  { id: 'reread', Icon: ScanLine, label: 'Perskaityti lapą (iš naujo) — nemokamai, iš brėžinio' },
  { id: 'compare', Icon: GitCompare, label: 'Palyginti leidimus — naujas brėžinio leidimas ant dabartinio' },
  { id: 'search', Icon: Search, label: 'Paieška brėžinio tekste' },
];

export default function ShortcutsGuide({ open, onOpenChange }) {
  const mac = useMemo(() => isMacPlatform(), []);
  const rows = useMemo(() => shortcutGuideRows({ mac }), [mac]);
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      await downloadShortcutSheet(rows, { mac });
      toast.success('Klavišų lapas atsisiunčiamas (PDF, A4)');
    } catch (e) {
      console.warn('[shortcuts pdf] failed:', e?.message);
      toast.error('Nepavyko sukurti PDF — galite atsispausdinti šį sąrašą naršyklėje (Ctrl+P).');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[440px] sm:max-w-[440px] overflow-y-auto p-0" data-testid="shortcuts-guide">
        <SheetHeader className="px-5 pt-5 pb-3 border-b border-border text-left">
          <SheetTitle>Spartieji klavišai</SheetTitle>
          <SheetDescription>
            Klavišai veikia, kai žymeklis ne teksto laukelyje. {mac ? '⌘ — Command, ⇧ — Shift.' : 'Ctrl — Control.'}
          </SheetDescription>
          <button
            type="button"
            onClick={download}
            disabled={busy}
            className="mt-2 self-start inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-[2px] border border-border text-meta text-foreground hover:bg-muted disabled:opacity-60"
            title="Vieno puslapio A4 PDF su visais klavišais — atsispausdinkite ir laikykite šalia"
            data-testid="shortcuts-guide-pdf"
          >
            <Download className="w-3.5 h-3.5" />
            {busy ? 'Kuriama…' : 'Atsisiųsti PDF'}
          </button>
        </SheetHeader>
        <div className="px-5 py-4 space-y-5">
          {/* B2-B item 4: on a narrow drawing the top-right buttons show only their icons — what each one is */}
          <section data-testid="shortcuts-guide-buttons">
            <h3 className="text-meta font-semibold text-primary mb-1.5">Mygtukai virš brėžinio dešinėje</h3>
            <ul className="divide-y divide-border/60 border-t border-border">
              {TOP_BUTTONS.map(({ id, Icon, label }) => (
                <li key={id} className="flex items-start gap-3 py-1.5 text-ui" data-guide-button={id}>
                  <span className="w-[42%] shrink-0"><Icon className="w-4 h-4 text-foreground" aria-hidden="true" /></span>
                  <span className="flex-1 text-foreground leading-snug">{label}</span>
                </li>
              ))}
            </ul>
          </section>
          {rows.map((g) => (
            <section key={g.group}>
              <h3 className="text-meta font-semibold text-primary mb-1.5">{g.title}</h3>
              <ul className="divide-y divide-border/60 border-t border-border">
                {g.items.map((it) => (
                  <li key={it.id} className="flex items-start gap-3 py-1.5 text-ui" data-shortcut-id={it.id}>
                    <span className="w-[42%] shrink-0 flex flex-wrap gap-1">
                      {it.mouse ? (
                        <span className="text-meta italic text-muted-foreground leading-snug">{it.keys[0]}</span>
                      ) : it.keys.map((k) => (
                        <kbd key={k} className="mono text-meta px-1.5 py-0.5 rounded-[2px] border border-border bg-muted text-foreground whitespace-nowrap">{k}</kbd>
                      ))}
                    </span>
                    <span className="flex-1 text-foreground leading-snug">{it.label}</span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

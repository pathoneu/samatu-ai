/**
 * MeasuredChip — „iš matavimų" on a row that carries measurements (Pathon v3 W4-A M2). One click opens the
 * row's measurement lines („+ matavimas 4,20 m (lapas 1)"), each with how it counts (Pridėti / Atimti /
 * Vietoj), „Rodyti brėžinyje" and „Nuimti"; a line listed but not counted says why. The program's own number
 * is said beside the result. Writes go through useMeasureRows (each with „Atšaukti").
 */

import { Ruler } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { KAIP } from '@/lib/measuredRows';
import { ltQuantity } from '@/lib/ledger';

const KAIP_SHORT = { 'pridėti': 'Pridėti', atimti: 'Atimti', kiekis: 'Vietoj' };
const KAIP_TITLE = {
  'pridėti': 'Pridėti prie programos kiekio',
  atimti: 'Atimti iš programos kiekio',
  kiekis: 'Vietoj programos kiekio — eilutės kiekis lygus matavimams',
};

export default function MeasuredChip({ row, onSetKaip = null, onUnlink = null, onJumpToPage = null, compact = false }) {
  const lines = Array.isArray(row?.matavimai) ? row.matavimai : [];
  if (!lines.length) return null;
  const unit = row.mato_vnt || row.vnt || '';
  const counted = lines.filter((l) => l.taikoma).length;
  const typed = row.manual_override === true || row.quantity_source === 'manual_override';
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          onClick={(e) => e.stopPropagation()}
          onDoubleClick={(e) => e.stopPropagation()}
          className={`inline-flex shrink-0 items-center gap-1 rounded border border-[hsl(var(--ov-read))] px-1 text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${compact ? '' : 'min-h-[24px]'}`}
          style={{ fontSize: 12, lineHeight: '16px' }}
          title="Kiekis su jūsų matavimais — spustelėkite, kad pamatytumėte, kurie ir kaip įtraukti"
          data-testid="measured-chip"
        >
          <Ruler className="w-3 h-3" aria-hidden />
          iš matavimų{lines.length > 1 ? ` (${lines.length})` : ''}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        // keep clear of the bottom-right strip the (empty) toast viewport covers, so „Nuimti" stays clickable
        collisionPadding={{ bottom: 48, top: 8 }}
        className="w-80 p-0 text-ui" onClick={(e) => e.stopPropagation()} data-testid="measured-list">
        <div className="px-3 py-2 border-b border-border">
          <p className="font-medium text-foreground truncate" title={row.aprasymas}>{row.aprasymas}</p>
          <p className="text-muted-foreground">
            {typed
              ? `Kiekį įrašėte ranka: ${ltQuantity(row.kiekis, unit)} — matavimai neįtraukti.`
              : `Programa: ${ltQuantity(row.kiekis_programos, unit)} → su matavimais ${ltQuantity(row.kiekis, unit)}`}
          </p>
        </div>
        <ul className="divide-y divide-border/60">
          {lines.map((l) => (
            <li key={l.key} className="px-3 py-2 space-y-1.5">
              <p className={l.taikoma ? 'text-foreground' : 'text-muted-foreground'}>{l.tekstas}</p>
              {!l.taikoma && l.priezastis && <p className="text-muted-foreground">{l.priezastis}</p>}
              <div className="flex flex-wrap items-center gap-1.5">
                {onSetKaip && !typed && (
                  <span className="inline-flex rounded border border-border overflow-hidden" role="group" aria-label="Kaip įtraukti">
                    {KAIP.map((k) => (
                      <button
                        key={k}
                        type="button"
                        aria-pressed={l.kaip === k}
                        onClick={() => onSetKaip(l.key, k)}
                        title={KAIP_TITLE[k]}
                        className={`min-h-[28px] px-2 ${l.kaip === k ? 'bg-primary text-primary-foreground' : 'bg-card text-foreground hover:bg-muted'}`}
                      >
                        {KAIP_SHORT[k]}
                      </button>
                    ))}
                  </span>
                )}
                {onJumpToPage && l.pages?.[0] != null && (
                  <button type="button" onClick={() => onJumpToPage(l.pages[0])} className="min-h-[28px] px-1.5 text-primary hover:underline">
                    Rodyti brėžinyje
                  </button>
                )}
                {onUnlink && (
                  <button type="button" onClick={() => onUnlink(l.key)} className="ml-auto min-h-[28px] px-1.5 text-foreground hover:underline" data-testid="measured-unlink">
                    Nuimti
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {counted < lines.length && !typed && (
          <p className="px-3 py-2 border-t border-border text-muted-foreground">
            Įtraukta {counted} iš {lines.length}.
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}

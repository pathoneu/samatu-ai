/**
 * MeasureRowPicker — „Į eilutę…": which sąmata row a measurement goes on, and how (Pathon v3 W4-A M2).
 *
 * The keyboard way to what a drag does, and the only way from the viewer's right-click menu. Lists the rows
 * counted in the measurement's own unit (a length never lands on an m² line — the list says the others are
 * hidden and why), a search over line and section, and the three ways with what each does to the number.
 * Nothing is written before „Priskirti"; the write offers „Atšaukti" (useMeasureRows).
 */

import { useEffect, useMemo, useState } from 'react';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { KAIP, KAIP_LABELS, defaultKaip, measureSource, sourceText, unitOfRow, unitsMatch } from '@/lib/measuredRows';
import { foldText } from '@/lib/quantitiesTree';
import { ltQuantity } from '@/lib/ledger';

const KAIP_SAYS = {
  'pridėti': 'eilutės kiekis padidės matavimo dydžiu',
  atimti: 'eilutės kiekis sumažės matavimo dydžiu',
  kiekis: 'eilutės kiekis bus lygus matavimui — programos skaičius lieka šalia',
};

export default function MeasureRowPicker({ open, onOpenChange, project, sourceKey, onPick }) {
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState(null);
  const [kaip, setKaip] = useState(null);
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setPicked(null);
    setKaip(null);
  }, [open, sourceKey]);

  const source = useMemo(() => (open ? measureSource(project, sourceKey) : null), [open, project, sourceKey]);
  const rows = useMemo(() => (project?.darbu_sarasas || []).filter((r) => r?.id), [project?.darbu_sarasas]);
  const fitting = useMemo(
    () => (source ? rows.filter((r) => unitsMatch(unitOfRow(r), source.unit)) : []), [rows, source]);
  const q = foldText(query);
  const shown = useMemo(() => (q
    ? fitting.filter((r) => foldText(r.aprasymas).includes(q) || foldText(r.skyrius).includes(q))
    : fitting), [fitting, q]);
  const hidden = rows.length - fitting.length;
  const how = kaip || (picked ? defaultKaip(picked) : 'pridėti');

  const commit = () => {
    if (!picked) return;
    if (onPick?.(picked, how) !== false) onOpenChange?.(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg grid-cols-[minmax(0,1fr)]" data-testid="measure-row-picker">
        <DialogHeader>
          <DialogTitle>Į kurią eilutę?</DialogTitle>
          <DialogDescription>
            {source ? sourceText(source) : 'Matavimo nebėra.'}
          </DialogDescription>
        </DialogHeader>
        {source && (
          <div className="space-y-3 text-ui">
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && shown.length === 1) { setPicked(shown[0]); }
              }}
              placeholder="Ieškoti eilutės ar skyriaus…"
              aria-label="Ieškoti eilutės ar skyriaus"
              className="w-full h-9 px-2.5 rounded border border-border bg-card text-foreground outline-none focus:border-primary"
            />
            <p className="text-muted-foreground">
              Rodomos eilutės, skaičiuojamos {source.unit} ({fitting.length}).
              {hidden > 0 ? ` Kitų vienetų eilutės (${hidden}) paslėptos — matavimo į jas įtraukti negalima.` : ''}
            </p>
            <ul className="max-h-[40vh] overflow-y-auto rounded border border-border divide-y divide-border/60" role="listbox" aria-label="Eilutės">
              {shown.map((r) => {
                const sel = picked?.id === r.id;
                return (
                  <li key={r.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={sel}
                      onClick={() => setPicked(r)}
                      onDoubleClick={() => { setPicked(r); onPick?.(r, kaip || defaultKaip(r)); onOpenChange?.(false); }}
                      className={`w-full min-h-[40px] px-2.5 py-1.5 text-left flex items-baseline gap-2 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring ${sel ? 'bg-primary/10 shadow-[inset_3px_0_0_hsl(var(--primary))]' : ''}`}
                      data-testid="measure-row-option"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-foreground">{r.aprasymas}</span>
                        <span className="block truncate text-meta text-muted-foreground">{r.skyrius}</span>
                      </span>
                      <span className="mono tabular whitespace-nowrap text-foreground/85">{ltQuantity(r.kiekis, r.mato_vnt || r.vnt)}</span>
                    </button>
                  </li>
                );
              })}
              {shown.length === 0 && (
                <li className="px-2.5 py-3 text-muted-foreground">
                  {fitting.length ? `Nerasta pagal „${query}“.` : `Sąmatoje nėra eilučių, skaičiuojamų ${source.unit}.`}
                </li>
              )}
            </ul>
            <fieldset className="space-y-1">
              <legend className="font-medium text-foreground">Kaip įtraukti</legend>
              {KAIP.map((k) => (
                <label key={k} className="flex items-start gap-2 min-h-[32px] cursor-pointer">
                  <input
                    type="radio"
                    name="measure-kaip"
                    value={k}
                    checked={how === k}
                    onChange={() => setKaip(k)}
                    className="mt-1"
                  />
                  <span>
                    <span className="text-foreground">{KAIP_LABELS[k]}</span>
                    <span className="text-muted-foreground"> — {KAIP_SAYS[k]}</span>
                  </span>
                </label>
              ))}
            </fieldset>
          </div>
        )}
        <DialogFooter>
          <button
            type="button"
            onClick={() => onOpenChange?.(false)}
            className="min-h-[36px] px-3 rounded border border-border text-ui text-foreground hover:bg-muted"
          >
            Atsisakyti
          </button>
          <button
            type="button"
            disabled={!picked}
            onClick={commit}
            className="min-h-[36px] px-3 rounded bg-primary text-primary-foreground text-ui font-medium disabled:opacity-50"
            data-testid="measure-row-pick"
          >
            Priskirti
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

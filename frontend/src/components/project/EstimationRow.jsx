import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { parseLtNumber } from '@/lib/parseLtNumber';

export default function EstimationRow({ row, index, onPriceChange, onRowClick }) {
  // LT decimal comma: `type="number"` reports an EMPTY value for "12,5", so the
  // price silently became 0. Text input + a local draft (so the parent echoing
  // the parsed number back can't eat the character being typed). 2026-07-27.
  const [draft, setDraft] = useState(row.kaina ?? '');
  const [focused, setFocused] = useState(false);
  useEffect(() => { if (!focused) setDraft(row.kaina ?? ''); }, [row.kaina, focused]);

  const handlePriceChange = (e) => {
    const raw = e.target.value;
    setDraft(raw);
    if (raw.trim() === '') { onPriceChange(index, 0); return; }
    const price = parseLtNumber(raw);
    if (!Number.isFinite(price) || price < 0) return;   // wait for a valid number
    onPriceChange(index, price);
  };

  const confidenceColor = {
    high: '',
    medium: 'bg-chart-3/5',
    low: 'bg-destructive/5',
  };

  return (
    <tr
      className={cn(
        "border-b border-border/50 hover:bg-accent/30 transition-colors group",
        confidenceColor[row.confidence]
      )}
    >
      <td className="px-4 py-2.5">
        <span className="font-mono text-xs text-muted-foreground">{row.nr}</span>
      </td>
      <td className="px-4 py-2.5 max-w-md">
        <button
          onClick={() => onRowClick(row)}
          className="text-left text-sm text-foreground truncate block w-full hover:text-primary transition-colors"
          title={row.aprasymas}
        >
          {row.aprasymas}
          {row.warning && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <AlertTriangle className="w-3.5 h-3.5 text-chart-3 inline ml-2" />
                </TooltipTrigger>
                <TooltipContent>
                  <p className="text-xs">{row.warning}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </button>
      </td>
      <td className="px-4 py-2.5">
        <span className="font-mono text-xs text-muted-foreground">{row.mato_vnt || '—'}</span>
      </td>
      <td className="px-4 py-2.5">
        <span className="font-mono text-sm text-foreground">
          {typeof row.kiekis === 'number' ? row.kiekis.toLocaleString('lt-LT', { maximumFractionDigits: 2 }) : '—'}
        </span>
      </td>
      <td className="px-3 py-1.5 w-28">
        <Input
          type="text"
          inputMode="decimal"
          value={draft}
          onChange={handlePriceChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="0,00"
          className="h-8 text-right font-mono text-sm bg-background border-border w-full"
        />
      </td>
      <td className="px-4 py-2.5 text-right">
        <span className={cn("font-mono text-sm font-medium", row.suma > 0 ? 'text-foreground' : 'text-muted-foreground')}>
          {row.suma > 0 ? `${row.suma.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €` : '—'}
        </span>
      </td>
    </tr>
  );
}
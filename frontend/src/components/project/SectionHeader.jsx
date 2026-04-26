import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

export default function SectionHeader({ name, rowCount, subtotal, isCollapsed, onToggle }) {
  return (
    <tr
      onClick={onToggle}
      className="bg-secondary/80 cursor-pointer hover:bg-secondary transition-colors group"
    >
      <td colSpan={4} className="px-4 py-3">
        <div className="flex items-center gap-2">
          {isCollapsed 
            ? <ChevronRight className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />
          }
          <span className="font-semibold text-sm text-foreground uppercase tracking-wide">
            {name}
          </span>
          <span className="text-xs text-muted-foreground font-mono ml-2">
            ({rowCount} eil.)
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-right" colSpan={2}>
        <span className="font-mono text-sm font-semibold text-foreground">
          {subtotal > 0 ? `${subtotal.toLocaleString('lt-LT', { minimumFractionDigits: 2 })} €` : '—'}
        </span>
      </td>
    </tr>
  );
}
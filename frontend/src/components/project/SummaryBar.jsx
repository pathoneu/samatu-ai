import React from 'react';

export default function SummaryBar({ rows, vatRate = 21 }) {
  const subtotal = rows.reduce((sum, r) => sum + (r.suma || 0), 0);
  const vat = subtotal * (vatRate / 100);
  const total = subtotal + vat;

  return (
    <div className="fixed bottom-0 right-0 left-0 bg-card/95 backdrop-blur-sm border-t border-border z-30">
      <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-end gap-8">
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Suma be PVM</p>
          <p className="font-mono text-sm font-semibold text-foreground">
            {subtotal.toLocaleString('lt-LT', { minimumFractionDigits: 2 })} €
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-muted-foreground">PVM {vatRate}%</p>
          <p className="font-mono text-sm font-semibold text-foreground">
            {vat.toLocaleString('lt-LT', { minimumFractionDigits: 2 })} €
          </p>
        </div>
        <div className="text-right pl-4 border-l border-border">
          <p className="text-xs text-primary font-medium">VISO su PVM</p>
          <p className="font-mono text-lg font-bold text-primary">
            {total.toLocaleString('lt-LT', { minimumFractionDigits: 2 })} €
          </p>
        </div>
      </div>
    </div>
  );
}
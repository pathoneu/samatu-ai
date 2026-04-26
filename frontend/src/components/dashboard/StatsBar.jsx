import React from 'react';
import { Folders, Rows3, Calculator } from 'lucide-react';

function StatCard({ icon: Icon, label, value, suffix }) {
  return (
    <div className="flex items-center gap-3 bg-card border border-border rounded-xl px-5 py-4">
      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
        <Icon className="w-5 h-5 text-primary" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-xl font-semibold font-mono text-foreground">
          {value}{suffix && <span className="text-sm text-muted-foreground ml-1">{suffix}</span>}
        </p>
      </div>
    </div>
  );
}

export default function StatsBar({ projects }) {
  const totalProjects = projects.length;
  const totalRows = projects.reduce((sum, p) => sum + (p.total_rows || 0), 0);
  const totalValue = projects.reduce((sum, p) => sum + (p.total_value || 0), 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <StatCard icon={Folders} label="Projektai" value={totalProjects} />
      <StatCard icon={Rows3} label="Eilutės apdorotos" value={totalRows.toLocaleString('lt-LT')} />
      <StatCard
        icon={Calculator}
        label="Bendra vertė"
        value={totalValue > 0 ? totalValue.toLocaleString('lt-LT', { minimumFractionDigits: 2 }) : '—'}
        suffix={totalValue > 0 ? '€' : ''}
      />
    </div>
  );
}
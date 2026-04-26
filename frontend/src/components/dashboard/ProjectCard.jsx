import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, ArrowRight, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';
import { lt } from 'date-fns/locale';

const statusConfig = {
  ready: { label: 'Paruošta', icon: CheckCircle2, class: 'bg-primary/10 text-primary border-primary/20' },
  processing: { label: 'Apdorojama', icon: Loader2, class: 'bg-chart-3/10 text-chart-3 border-chart-3/20' },
  error: { label: 'Klaida', icon: AlertCircle, class: 'bg-destructive/10 text-destructive border-destructive/20' },
};

export default function ProjectCard({ project }) {
  const status = statusConfig[project.status] || statusConfig.ready;
  const StatusIcon = status.icon;

  return (
    <Link
      to={`/project/${project.id}`}
      className="group block bg-card border border-border rounded-xl p-5 hover:border-primary/30 hover:bg-accent/50 transition-all duration-200"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
            <FileText className="w-5 h-5 text-muted-foreground" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-foreground truncate group-hover:text-primary transition-colors">
              {project.name}
            </h3>
            {project.company_name && (
              <p className="text-sm text-muted-foreground truncate">{project.company_name}</p>
            )}
            <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
              <span>{format(new Date(project.created_date), 'yyyy-MM-dd', { locale: lt })}</span>
              <span>•</span>
              <span className="font-mono">{project.total_rows || 0} eilučių</span>
              {project.total_value > 0 && (
                <>
                  <span>•</span>
                  <span className="font-mono text-primary font-medium">
                    {project.total_value.toLocaleString('lt-LT', { minimumFractionDigits: 2 })} €
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 ml-4">
          <Badge variant="outline" className={`${status.class} border text-xs`}>
            <StatusIcon className={`w-3 h-3 mr-1 ${project.status === 'processing' ? 'animate-spin' : ''}`} />
            {status.label}
          </Badge>
          <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </Link>
  );
}
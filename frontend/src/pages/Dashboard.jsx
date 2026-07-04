import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FolderPlus, Search, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import StatsBar from '@/components/dashboard/StatsBar';
import ProjectCard from '@/components/dashboard/ProjectCard';
import EmptyState from '@/components/dashboard/EmptyState';
import UsageMeter from '@/components/billing/UsageMeter';
import { getProjects, pullProjectsFromBackend } from '@/lib/projectStore';
import { useQueryClient } from '@tanstack/react-query';
import SetupWizard, { loadPrefs } from '@/components/project/SetupWizard';

export default function Dashboard() {
  const [search, setSearch] = React.useState('');
  // Sprint 1 (Q3): atsisakom forced Setup Wizard. Vartotojas tiesiog
  // pamatys Dashboard ir spauskite "Nustatymai" mygtuką jei nori konfigūruoti.
  // Default reikšmes naudojam visiems naujiems vartotojams.
  const [showWizard, setShowWizard] = React.useState(false);
  const queryClient = useQueryClient();

  // On first mount, pull DB projects into localStorage (Phase 12.3).
  // Handles: cross-device, localStorage cleared, edit-from-other-tab.
  //
  // W1 Day 1 (2026-05-11): also re-pull on window focus + visibility
  // change. Before this fix, opening a project in tab A, editing it,
  // then returning to Dashboard tab B showed the stale localStorage
  // snapshot from first mount. Real users hit this on the 2026-05-07
  // prod test.
  React.useEffect(() => {
    const refresh = () => {
      pullProjectsFromBackend().then((merged) => {
        if (merged) queryClient.invalidateQueries({ queryKey: ['projects'] });
      });
    };
    refresh();
    const onFocus = () => refresh();
    const onVisibility = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [queryClient]);

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  // Sprint §28: hide archived projects from Dashboard (user can restore from
  // Settings → Šiukšliadėžė).
  const filtered = projects
    .filter(p => !p._archived)
    .filter(p =>
      p.name?.toLowerCase().includes(search.toLowerCase()) ||
      p.company_name?.toLowerCase().includes(search.toLowerCase())
    );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      {showWizard && (
        <SetupWizard
          onComplete={() => setShowWizard(false)}
          onClose={() => setShowWizard(false)}
        />
      )}

      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground mb-2">
            00 / Projektai
          </div>
          <h1 className="text-2xl font-semibold text-foreground tracking-tight">Projektai</h1>
          <p className="text-sm text-muted-foreground mt-1">Statybų sąmatų valdymas</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => setShowWizard(true)}
            title="Pradiniai nustatymai"
          >
            <Settings className="w-4 h-4 mr-2" />
            Nustatymai
          </Button>
          <Link to="/new-project">
            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-medium">
              <FolderPlus className="w-4 h-4 mr-2" />
              Naujas projektas
            </Button>
          </Link>
        </div>
      </div>

      {/* Phase 7 — usage meter. Renders null unless billing is enabled, so the
          flag-off Dashboard is byte-identical to before (no wrapper, no spacer). */}
      <UsageMeter />

      {projects.length > 0 ? (
        <>
          <StatsBar projects={projects} />

          <div className="mt-8 mb-4">
            <div className="relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Ieškoti projektų..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-card border-border"
              />
            </div>
          </div>

          {filtered.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
              {filtered.map(project => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          ) : (
            <div
              className="text-center"
              style={{
                padding: '48px 16px', color: 'hsl(var(--muted-foreground))',
                fontSize: 12,
                border: '1px dashed hsl(var(--border-strong))',
                borderRadius: 6,
              }}
            >
              Nieko nerasta pagal filtrą „<span style={{ color: 'hsl(var(--foreground) / 0.85)' }}>{search}</span>".
            </div>
          )}
        </>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}

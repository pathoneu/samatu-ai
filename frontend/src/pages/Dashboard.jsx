import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { FolderPlus, Search, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import StatsBar from '@/components/dashboard/StatsBar';
import ProjectCard from '@/components/dashboard/ProjectCard';
import EmptyState from '@/components/dashboard/EmptyState';
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
  React.useEffect(() => {
    pullProjectsFromBackend().then((merged) => {
      if (merged) queryClient.invalidateQueries({ queryKey: ['projects'] });
    });
  }, [queryClient]);

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const filtered = projects.filter(p =>
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
          <h1 className="text-2xl font-bold text-foreground">Projektai</h1>
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

          <div className="space-y-3">
            {filtered.length > 0 ? (
              filtered.map(project => (
                <ProjectCard key={project.id} project={project} />
              ))
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <p>Nerasta projektų pagal „{search}"</p>
              </div>
            )}
          </div>
        </>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}

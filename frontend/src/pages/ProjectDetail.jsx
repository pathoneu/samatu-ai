import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Search, Download, ChevronsUpDown, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import SummaryBar from '@/components/project/SummaryBar';
import SectionHeader from '@/components/project/SectionHeader';
import EstimationRow from '@/components/project/EstimationRow';
import RowDetailPanel from '@/components/project/RowDetailPanel';
import ExportModal from '@/components/project/ExportModal';
import InteriorProject from '@/pages/InteriorProject';
import ConstructionProject from '@/pages/ConstructionProject';
import { getProject, updateProject, deleteProject, pullProjectsFromBackend } from '@/lib/projectStore';

export default function ProjectDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [collapsedSections, setCollapsedSections] = useState({});
  const [selectedRow, setSelectedRow] = useState(null);
  const [showExport, setShowExport] = useState(false);
  const [localRows, setLocalRows] = useState([]);
  const [hasUnsaved, setHasUnsaved] = useState(false);

  // Direct-URL access fallback: if project not in localStorage cache (user
  // landed on /project/<id> without visiting Dashboard first), pull from
  // backend and re-run the query.
  const [didFallback, setDidFallback] = useState(false);
  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
    enabled: !!id,
  });

  useEffect(() => {
    if (!isLoading && !project && id && !didFallback) {
      setDidFallback(true);
      pullProjectsFromBackend({ force: true }).then(() => {
        queryClient.invalidateQueries({ queryKey: ['project', id] });
      });
    }
  }, [isLoading, project, id, didFallback, queryClient]);

  useEffect(() => {
    if (project?.rows) {
      setLocalRows(project.rows);
    }
  }, [project]);

  // Auto-save with debounce
  useEffect(() => {
    if (!hasUnsaved || localRows.length === 0) return;
    const timer = setTimeout(() => {
      const totalValue = localRows.reduce((sum, r) => sum + (r.suma || 0), 0);
      updateProject(id, { rows: localRows, total_value: totalValue });
      setHasUnsaved(false);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    }, 1500);
    return () => clearTimeout(timer);
  }, [localRows, hasUnsaved, id, queryClient]);

  const handlePriceChange = useCallback((index, price) => {
    setLocalRows(prev => {
      const updated = [...prev];
      updated[index] = {
        ...updated[index],
        kaina: price,
        suma: price * (updated[index].kiekis || 0),
      };
      return updated;
    });
    setHasUnsaved(true);
  }, []);

  const handleDelete = () => {
    if (window.confirm('Ištrinti projektą?')) {
      deleteProject(id);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate('/');
    }
  };

  const sections = useMemo(() => {
    const sectionMap = {};
    localRows.forEach((row, idx) => {
      const section = row.skyrius || 'KITI DARBAI';
      if (!sectionMap[section]) sectionMap[section] = [];
      sectionMap[section].push({ ...row, _index: idx });
    });
    return sectionMap;
  }, [localRows]);

  const filteredSections = useMemo(() => {
    if (!search) return sections;
    const filtered = {};
    Object.entries(sections).forEach(([name, rows]) => {
      const matchedRows = rows.filter(r =>
        r.aprasymas?.toLowerCase().includes(search.toLowerCase()) ||
        r.nr?.toLowerCase().includes(search.toLowerCase())
      );
      if (matchedRows.length > 0) filtered[name] = matchedRows;
    });
    return filtered;
  }, [sections, search]);

  const toggleSection = (name) => {
    setCollapsedSections(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const toggleAll = () => {
    const allCollapsed = Object.keys(sections).every(k => collapsedSections[k]);
    const newState = {};
    Object.keys(sections).forEach(k => { newState[k] = !allCollapsed; });
    setCollapsedSections(newState);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-4 border-muted border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-8 text-center">
        <p className="text-muted-foreground">Projektas nerastas</p>
        <Link to="/" className="text-primary text-sm mt-2 inline-block">Grįžti</Link>
      </div>
    );
  }

  // ── Construction project: separate render path ───────────────────────────────
  const CONSTRUCTION_TYPES = ['fasadas', 'stogas', 'zeme', 'betonas'];
  if (CONSTRUCTION_TYPES.includes(project?.tipas)) {
    const TYPE_LABELS = { fasadas: 'Fasadų projektas', stogas: 'Stogo projektas', zeme: 'Žemės darbai', betonas: 'Betono konstrukcijos' };
    return (
      <div className="pb-20">
        <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border">
          <div className="px-6 py-4 max-w-[90rem] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Link to="/" className="p-1.5 hover:bg-secondary rounded-lg transition-colors">
                <ArrowLeft className="w-4 h-4 text-muted-foreground" />
              </Link>
              <div>
                <h1 className="text-lg font-bold text-foreground">{project.name}</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  {project.company_name && <span className="text-xs text-muted-foreground">{project.company_name}</span>}
                  <Badge variant="outline" className="text-xs border-border">{TYPE_LABELS[project.tipas]}</Badge>
                </div>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={handleDelete} className="text-muted-foreground hover:text-destructive">
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
        <div className="px-6 max-w-[90rem] mx-auto mt-6">
          <ConstructionProject project={project} />
        </div>
      </div>
    );
  }

  // ── Interior project: full-bleed render. InteriorProject's own
  // ProjectTopBar provides back arrow + name + Be PVM / Su PVM totals +
  // Prielaidos / Eksportuoti buttons. Wrapper header removed (was redundant).
  if (project?.tipas === 'interjeras') {
    return <InteriorProject project={project} onDelete={handleDelete} />;
  }

  // Build the enriched project object for the export modal (with current prices)
  const projectForExport = {
    ...project,
    rows: localRows,
    total_value: localRows.reduce((s, r) => s + (r.suma || 0), 0),
  };

  return (
    <div className="pb-20">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b border-border">
        <div className="px-6 py-4 max-w-[90rem] mx-auto">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Link to="/" className="p-1.5 hover:bg-secondary rounded-lg transition-colors">
                <ArrowLeft className="w-4 h-4 text-muted-foreground" />
              </Link>
              <div>
                <h1 className="text-lg font-bold text-foreground">{project.name}</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  {project.company_name && (
                    <span className="text-xs text-muted-foreground">{project.company_name}</span>
                  )}
                  <Badge variant="outline" className="text-xs font-mono border-border">
                    {localRows.length} eilučių
                  </Badge>
                  {hasUnsaved && (
                    <Badge variant="outline" className="text-xs border-chart-3/30 text-chart-3 bg-chart-3/5">
                      Saugoma...
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={toggleAll} className="border-border">
                <ChevronsUpDown className="w-4 h-4 mr-1.5" />
                <span className="hidden sm:inline">Sutraukti</span>
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowExport(true)} className="border-border">
                <Download className="w-4 h-4 mr-1.5" />
                <span className="hidden sm:inline">Eksportuoti</span>
              </Button>
              <Button variant="ghost" size="sm" onClick={handleDelete} className="text-muted-foreground hover:text-destructive">
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Ieškoti eilučių..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9 bg-card border-border text-sm"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="px-6 max-w-[90rem] mx-auto mt-4">
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-secondary/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider w-16">Nr.</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">Aprašymas</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider w-20">Mat. vnt.</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider w-24">Kiekis</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider w-28">Kaina €</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wider w-32">Suma €</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(filteredSections).map(([sectionName, rows]) => {
                  const subtotal = rows.reduce((sum, r) => sum + (r.suma || 0), 0);
                  const isCollapsed = collapsedSections[sectionName];
                  return (
                    <React.Fragment key={sectionName}>
                      <SectionHeader
                        name={sectionName}
                        rowCount={rows.length}
                        subtotal={subtotal}
                        isCollapsed={isCollapsed}
                        onToggle={() => toggleSection(sectionName)}
                      />
                      {!isCollapsed && rows.map(row => (
                        <EstimationRow
                          key={row._index}
                          row={row}
                          index={row._index}
                          onPriceChange={handlePriceChange}
                          onRowClick={setSelectedRow}
                        />
                      ))}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          {Object.keys(filteredSections).length === 0 && (
            <div className="text-center py-12">
              <p className="text-muted-foreground text-sm">
                {search ? `Nerasta eilučių pagal „${search}"` : 'Nėra eilučių'}
              </p>
            </div>
          )}
        </div>
      </div>

      <SummaryBar rows={localRows} vatRate={project.vat_rate || 21} />

      {selectedRow && (
        <RowDetailPanel row={selectedRow} onClose={() => setSelectedRow(null)} />
      )}

      <ExportModal open={showExport} onClose={() => setShowExport(false)} project={projectForExport} />
    </div>
  );
}

/**
 * AdminDashboard — admin-only view of system state (Phase 13).
 *
 * Shows:
 * - Stats: users, projects, extractions, total cost, corrections count
 * - Top corrections (which fields users override most → manual prompt iteration signal)
 * - User list (email, projects count, registration date, admin flag)
 * - Recent projects (across all users)
 */

import React, { useEffect, useState } from 'react';
import { Users, FolderKanban, Receipt, Activity, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/lib/authContext';
import { Navigate } from 'react-router-dom';

const API = '';

async function fetchAdmin(path) {
  const res = await fetch(`${API}${path}`, { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function StatCard({ icon: Icon, label, value, subtitle }) {
  return (
    <div className="border border-border rounded-xl bg-card p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">{label}</p>
          <p className="text-2xl font-semibold tabular-nums mt-1">{value}</p>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        <Icon className="w-5 h-5 text-muted-foreground" />
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const { user, isAdmin, isLoading } = useAuth();
  const [stats, setStats] = useState(null);
  const [corrections, setCorrections] = useState([]);
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAdmin) return;
    Promise.all([
      fetchAdmin('/api/admin/stats'),
      fetchAdmin('/api/admin/corrections-summary'),
      fetchAdmin('/api/admin/users'),
      fetchAdmin('/api/admin/recent-projects?limit=20'),
    ])
      .then(([s, c, u, p]) => {
        setStats(s);
        setCorrections(c.summary || []);
        setUsers(u.users || []);
        setProjects(p.projects || []);
      })
      .catch((e) => setError(e.message));
  }, [isAdmin]);

  if (isLoading) return <div className="p-8 text-muted-foreground">Kraunama...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/" replace />;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Admin dashboard</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Sistema: vartotojai, sąnaudos, korekcijos, projektai
      </p>

      {error && (
        <div className="flex items-start gap-2 p-3 mb-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <div>{error}</div>
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard icon={Users}        label="Vartotojai"      value={stats.users_count} />
          <StatCard icon={FolderKanban} label="Projektai"        value={stats.projects_count} />
          <StatCard icon={Activity}     label="Ekstrakcijos"     value={stats.extractions_count} subtitle={`vid. ${stats.avg_cost_per_extract_eur}€/projekt.`} />
          <StatCard icon={Receipt}      label="Bendros sąnaudos" value={`${stats.total_cost_eur}€`} subtitle={`${stats.corrections_count} korekcijų`} />
        </div>
      )}

      {/* Top corrected fields — input signal for manual prompt iteration */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Dažniausiai vartotojų pakeičiami laukai</h2>
        <p className="text-xs text-muted-foreground mb-3">
          Šios reikšmės rodo kur AI default'ai dažnai keičiami — signalas peržiūrėti prompt'ą.
        </p>
        <div className="border border-border rounded-xl bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left">
                <th className="px-4 py-2 text-xs font-semibold uppercase">Laukas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase text-right">Korekcijų</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase text-right">Projektų</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase text-right">Paskutinė</th>
              </tr>
            </thead>
            <tbody>
              {corrections.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-4 text-muted-foreground text-center">Nėra duomenų</td></tr>
              )}
              {corrections.slice(0, 20).map((c, i) => (
                <tr key={i} className="border-t border-border/50 last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{c.field_path}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{c.count}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{c.projects}</td>
                  <td className="px-4 py-2 text-right text-xs text-muted-foreground">
                    {c.last_seen ? new Date(c.last_seen).toLocaleDateString('lt-LT') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* User list */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Vartotojai</h2>
        <div className="border border-border rounded-xl bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left">
                <th className="px-4 py-2 text-xs font-semibold uppercase">El. paštas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Vardas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Įmonė</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Registr.</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Pask. login</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Admin</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-t border-border/50 last:border-0">
                  <td className="px-4 py-2">{u.email}</td>
                  <td className="px-4 py-2 text-muted-foreground">{u.name || '—'}</td>
                  <td className="px-4 py-2 text-muted-foreground">{u.company_name || '—'}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('lt-LT') : '—'}
                  </td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('lt-LT') : 'niekada'}
                  </td>
                  <td className="px-4 py-2">
                    {u.is_admin ? (
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">admin</span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent projects */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Naujausi projektai (visi vartotojai)</h2>
        <div className="border border-border rounded-xl bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left">
                <th className="px-4 py-2 text-xs font-semibold uppercase">Pavadinimas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Tipas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Vartotojas</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase text-right">Plotas m²</th>
                <th className="px-4 py-2 text-xs font-semibold uppercase">Atnaujintas</th>
              </tr>
            </thead>
            <tbody>
              {projects.map(p => (
                <tr key={p.id} className="border-t border-border/50 last:border-0">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">{p.tipas}</td>
                  <td className="px-4 py-2 text-xs font-mono text-muted-foreground">
                    {p.user_id ? p.user_id.slice(0, 8) + '...' : '—'}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{p.bendras_plotas_m2 || '—'}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {p.updated_at ? new Date(p.updated_at).toLocaleString('lt-LT') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

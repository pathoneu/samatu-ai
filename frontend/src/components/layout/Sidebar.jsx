/**
 * Sidebar — 56px icon-only navigation rail. Mirrors claude.ai/design
 * prototype/sidebar.jsx exactly:
 * - 56px wide, light bg-1 (warm paper), border-right
 * - SĄ logo (32×32 accent blue, mono font, white text)
 * - 36×36 icon nav items, 4px gap
 * - Active: surface-3 background + 2px vertical accent bar (left edge)
 * - Settings + user avatar at bottom
 *
 * Replaces previous expand/collapse pattern. Tooltips via title attribute.
 */

import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Home, FileText, Plus, Sliders, Download, Settings, ShieldCheck, LogOut,
} from 'lucide-react';
import { useAuth } from '@/lib/authContext';

const NAV_ITEMS = [
  { path: '/', icon: Home, label: 'Projektai' },
  { path: '/active-project', icon: FileText, label: 'Aktyvus projektas', requiresProject: true },
  { path: '/new-project', icon: Plus, label: 'Naujas projektas' },
  { path: '/price-lists', icon: Sliders, label: 'Kainynai' },
  { path: '/exports', icon: Download, label: 'Eksportai' },
];

function NavBtn({ to, icon: Icon, label, isActive, onClick, disabled }) {
  const className = 'relative flex items-center justify-center w-9 h-9 rounded-md transition-colors';
  const activeStyle = {
    background: 'hsl(var(--sidebar-accent))',
    color: 'hsl(var(--sidebar-accent-foreground))',
  };
  const idleStyle = {
    background: 'transparent',
    color: 'hsl(var(--sidebar-foreground))',
  };
  const inner = (
    <>
      {isActive && (
        <span
          aria-hidden
          style={{
            position: 'absolute', left: -10, top: 8, bottom: 8, width: 2,
            background: 'hsl(var(--sidebar-primary))', borderRadius: 1,
          }}
        />
      )}
      <Icon style={{ width: 16, height: 16 }} />
    </>
  );
  if (disabled) {
    return (
      <span title={label} className={className} style={{ ...idleStyle, opacity: 0.4, cursor: 'not-allowed' }}>
        {inner}
      </span>
    );
  }
  if (to) {
    return (
      <Link to={to} title={label} className={className} style={isActive ? activeStyle : idleStyle}
        onClick={onClick}
        onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = 'hsl(var(--surface-2))'; }}
        onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
      >
        {inner}
      </Link>
    );
  }
  return (
    <button onClick={onClick} title={label} className={className} style={isActive ? activeStyle : idleStyle}>
      {inner}
    </button>
  );
}

export default function Sidebar({ onNavigate = null }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAdmin, logout } = useAuth();

  const isActiveProjectRoute = location.pathname.startsWith('/project/');
  const items = NAV_ITEMS.filter(it => !it.requiresProject || isActiveProjectRoute);
  // Replace placeholder /active-project with actual current path so click stays
  const augmented = items.map(it => it.path === '/active-project'
    ? { ...it, path: location.pathname }
    : it);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <aside
      className="fixed left-0 top-0 h-screen flex flex-col z-40"
      style={{
        width: 56,
        background: 'hsl(var(--sidebar-background))',
        borderRight: '1px solid hsl(var(--sidebar-border))',
        padding: '12px 0',
        flexShrink: 0,
      }}
    >
      {/* SĄ Logo — accent square */}
      <Link
        to="/"
        title="Sąmatų AI — į pradžią"
        className="mx-auto mb-4 flex items-center justify-center"
        style={{
          width: 32, height: 32, borderRadius: 6,
          background: 'hsl(var(--sidebar-primary))',
          color: 'hsl(var(--sidebar-primary-foreground))',
          fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13,
          letterSpacing: '0.02em',
        }}
      >
        SĄ
      </Link>

      {/* Nav items */}
      <nav className="flex flex-col items-center gap-1 flex-1">
        {augmented.map(it => {
          const Icon = it.icon;
          const isActive = it.path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(it.path);
          return (
            <NavBtn
              key={it.label}
              to={it.path}
              icon={Icon}
              label={it.label}
              isActive={isActive}
              disabled={it.requiresProject && !isActiveProjectRoute}
              onClick={onNavigate}
            />
          );
        })}
        {isAdmin && (
          <NavBtn
            to="/admin"
            icon={ShieldCheck}
            label="Administravimas"
            isActive={location.pathname.startsWith('/admin')}
            onClick={onNavigate}
          />
        )}
      </nav>

      {/* Bottom: settings + avatar */}
      <div className="flex flex-col items-center gap-2 pb-1">
        <NavBtn
          to="/settings"
          icon={Settings}
          label="Nustatymai"
          isActive={location.pathname.startsWith('/settings')}
          onClick={onNavigate}
        />
        <NavBtn
          icon={LogOut}
          label="Atsijungti"
          onClick={handleLogout}
        />
        {user && (
          <div
            title={user.email}
            className="flex items-center justify-center text-[10px] font-semibold border"
            style={{
              width: 28, height: 28, borderRadius: 6,
              background: 'hsl(var(--surface-2))',
              borderColor: 'hsl(var(--border))',
              color: 'hsl(var(--foreground) / 0.85)',
            }}
          >
            {(user.name || user.email || 'JV').slice(0, 2).toUpperCase()}
          </div>
        )}
      </div>
    </aside>
  );
}

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
import { Link, useLocation, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  Home, FileText, Plus, Sliders, Settings, ShieldCheck, LogOut, CreditCard,
} from 'lucide-react';
import { useAuth } from '@/lib/authContext';
import { useBilling } from '@/hooks/useBilling';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { PathonMark } from '@/components/layout/Logo';

// 2026-05-06: removed '/exports' — route never existed (404). Eksportai
// are accessible from each project's top-bar 'Eksportuoti' button instead.
// `labelKey` resolves against i18n at render time so nav labels/tooltips
// follow the active language (LT default).
const NAV_ITEMS = [
  { path: '/', icon: Home, labelKey: 'layout.nav.projektai' },
  { path: '/active-project', icon: FileText, labelKey: 'layout.nav.aktyvusProjektas', requiresProject: true },
  { path: '/new-project', icon: Plus, labelKey: 'layout.nav.naujasProjektas' },
  { path: '/price-lists', icon: Sliders, labelKey: 'layout.nav.kainynai' },
];

function NavBtn({ to, icon: Icon, label, isActive, onClick, disabled, disabledLabel }) {
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
  // A greyed-out glyph with no name and no reason. The Tooltip below can only
  // fire on hover for a <span>, so carry a title= too and say WHY it is off.
  // (2026-07-28 explainability pass.)
  const tipText = disabled ? (disabledLabel || label) : label;
  let trigger;
  if (disabled) {
    trigger = (
      <span
        className={className}
        aria-label={tipText}
        aria-disabled="true"
        title={tipText}
        style={{ ...idleStyle, opacity: 0.4, cursor: 'not-allowed' }}
      >
        {inner}
      </span>
    );
  } else if (to) {
    trigger = (
      <Link to={to} aria-label={label} className={className} style={isActive ? activeStyle : idleStyle}
        onClick={onClick}
        onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = 'hsl(var(--surface-2))'; }}
        onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
      >
        {inner}
      </Link>
    );
  } else {
    trigger = (
      <button onClick={onClick} aria-label={label} className={className} style={isActive ? activeStyle : idleStyle}>
        {inner}
      </button>
    );
  }

  // shadcn Tooltip on hover (side=right — rail sits on the left edge). The
  // `label` doubles as the accessible name via aria-label above.
  return (
    <Tooltip>
      <TooltipTrigger asChild>{trigger}</TooltipTrigger>
      <TooltipContent side="right">{tipText}</TooltipContent>
    </Tooltip>
  );
}

export default function Sidebar({ onNavigate = null }) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAdmin, logout } = useAuth();
  // Phase 7: the /pricing rail entry appears ONLY when billing is enabled.
  const { enabled: billingEnabled } = useBilling();

  const isActiveProjectRoute = location.pathname.startsWith('/project/');
  const items = NAV_ITEMS.filter(it => !it.requiresProject || isActiveProjectRoute);
  // Replace placeholder /active-project with actual current path so click stays
  const augmented = items.map(it => it.path === '/active-project'
    ? { ...it, path: location.pathname }
    : it);

  const handleLogout = async () => {
    await logout();
    // After logout, send user to public Landing at `/`, not /login.
    // RootRoute will detect no user and render <Landing />.
    navigate('/', { replace: true });
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
      {/* Pathon monogram-P logo → landing/home page (the house icon below
          goes to the app dashboard). */}
      <Link
        to="/about"
        title={t('layout.logoHome')}
        className="mx-auto mb-4 flex items-center justify-center text-foreground"
        style={{ width: 32, height: 32 }}
      >
        <PathonMark icon={26} />
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
              key={it.labelKey}
              to={it.path}
              icon={Icon}
              label={t(it.labelKey)}
              isActive={isActive}
              disabled={it.requiresProject && !isActiveProjectRoute}
              disabledLabel={t('layout.nav.noActiveProject')}
              onClick={onNavigate}
            />
          );
        })}
        {isAdmin && (
          <NavBtn
            to="/admin"
            icon={ShieldCheck}
            label={t('layout.nav.administravimas')}
            isActive={location.pathname.startsWith('/admin')}
            onClick={onNavigate}
          />
        )}
      </nav>

      {/* Bottom: settings + avatar */}
      <div className="flex flex-col items-center gap-2 pb-1">
        {billingEnabled && (
          <NavBtn
            to="/pricing"
            icon={CreditCard}
            label={t('layout.nav.planai')}
            isActive={location.pathname.startsWith('/pricing')}
            onClick={onNavigate}
          />
        )}
        <NavBtn
          to="/settings"
          icon={Settings}
          label={t('layout.nav.nustatymai')}
          isActive={location.pathname.startsWith('/settings')}
          onClick={onNavigate}
        />
        <NavBtn
          icon={LogOut}
          label={t('layout.nav.atsijungti')}
          onClick={handleLogout}
        />
        {user && (
          <div
            title={t('layout.nav.signedInAs', { email: user.email })}
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

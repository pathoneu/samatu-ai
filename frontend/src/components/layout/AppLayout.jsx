import React, { useState } from 'react';
import { Outlet } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';

/**
 * AppLayout — fixed 56px icon sidebar + content area.
 * Sprint §12 (2026-04-29): mobile responsive — sidebar hides on <768px;
 * hamburger toggle slides it in as overlay. Content uses full width on mobile.
 */
export default function AppLayout() {
  const { t } = useTranslation();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar — desktop always visible; mobile only when toggled. */}
      <div className={`md:block ${mobileSidebarOpen ? 'block' : 'hidden'}`}>
        <Sidebar onNavigate={() => setMobileSidebarOpen(false)} />
      </div>

      {/* Mobile hamburger toggle */}
      <button
        onClick={() => setMobileSidebarOpen(v => !v)}
        className="md:hidden fixed top-3 left-3 z-50 w-9 h-9 rounded-md flex items-center justify-center"
        style={{
          background: 'hsl(var(--card))',
          border: '1px solid hsl(var(--border))',
          color: 'hsl(var(--foreground))',
          boxShadow: mobileSidebarOpen ? 'none' : '0 1px 3px rgba(0,0,0,0.1)',
        }}
        title={mobileSidebarOpen ? t('layout.closeMenu') : t('layout.openMenu')}
        aria-label={mobileSidebarOpen ? t('layout.closeMenu') : t('layout.openMenu')}
      >
        {mobileSidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
      </button>

      {/* Backdrop when sidebar open on mobile */}
      {mobileSidebarOpen && (
        <div
          className="md:hidden fixed inset-0 z-30"
          style={{ background: 'rgba(0,0,0,0.4)' }}
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden
        />
      )}

      {/* Main content — left margin only on md+ where sidebar is fixed.
          Mobile gets top padding so hamburger doesn't overlap page titles. */}
      <main className="min-h-screen md:ml-14 pt-14 md:pt-0">
        <Outlet />
      </main>
    </div>
  );
}

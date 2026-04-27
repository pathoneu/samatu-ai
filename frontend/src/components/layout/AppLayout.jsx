import React, { useState, useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import Sidebar from './Sidebar';
import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';

export default function AppLayout() {
  const isMobile = useIsMobile();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Auto-close mobile drawer on route change
  useEffect(() => {
    if (isMobile) setMobileOpen(false);
  }, [location.pathname, isMobile]);

  if (isMobile) {
    return (
      <div className="min-h-screen bg-background">
        {/* Mobile top bar with hamburger */}
        <div className="fixed top-0 left-0 right-0 h-12 bg-sidebar border-b border-sidebar-border flex items-center px-3 z-40">
          <button
            onClick={() => setMobileOpen(v => !v)}
            className="p-2 -ml-2 rounded hover:bg-sidebar-accent text-sidebar-foreground"
            aria-label={mobileOpen ? 'Uždaryti meniu' : 'Atidaryti meniu'}
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          <span className="ml-2 font-semibold text-sm text-sidebar-foreground">Sąmatų AI</span>
        </div>

        {/* Off-canvas drawer */}
        {mobileOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/40 z-40"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
          </>
        )}

        {/* Content offset for top bar; no left margin on mobile */}
        <main className="min-h-screen pt-12">
          <Outlet />
        </main>
      </div>
    );
  }

  // Desktop layout (unchanged from original)
  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className={cn(
        "min-h-screen transition-all duration-300",
        collapsed ? "ml-16" : "ml-60"
      )}>
        <Outlet />
      </main>
    </div>
  );
}

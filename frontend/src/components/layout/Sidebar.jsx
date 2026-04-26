import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, FolderPlus, FileSpreadsheet, Settings, ChevronLeft, ChevronRight } from 'lucide-react';
import Logo from './Logo';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Projektai' },
  { path: '/new-project', icon: FolderPlus, label: 'Naujas projektas' },
  { path: '/price-lists', icon: FileSpreadsheet, label: 'Kainynai' },
  { path: '/settings', icon: Settings, label: 'Nustatymai' },
];

export default function Sidebar({ collapsed, onToggle }) {
  const location = useLocation();

  return (
    <aside className={cn(
      "fixed left-0 top-0 h-screen bg-sidebar border-r border-sidebar-border flex flex-col z-40 transition-all duration-300",
      collapsed ? "w-16" : "w-60"
    )}>
      <div className={cn("h-16 flex items-center border-b border-sidebar-border px-4", collapsed && "justify-center")}>
        {collapsed ? (
          <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
            <span className="text-primary font-bold">S</span>
          </div>
        ) : (
          <Logo />
        )}
      </div>

      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map(({ path, icon: Icon, label }) => {
          const isActive = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
          return (
            <Link
              key={path}
              to={path}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={onToggle}
        className="h-12 flex items-center justify-center border-t border-sidebar-border text-muted-foreground hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}
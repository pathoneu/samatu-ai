import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, FolderPlus, FileSpreadsheet, Settings,
  ChevronLeft, ChevronRight, ShieldCheck, LogOut,
} from 'lucide-react';
import Logo from './Logo';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/authContext';

const baseNav = [
  { path: '/', icon: LayoutDashboard, label: 'Projektai' },
  { path: '/new-project', icon: FolderPlus, label: 'Naujas projektas' },
  { path: '/price-lists', icon: FileSpreadsheet, label: 'Kainynai' },
  { path: '/settings', icon: Settings, label: 'Nustatymai' },
];

export default function Sidebar({ collapsed, onToggle }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, isAdmin, logout } = useAuth();

  const navItems = isAdmin
    ? [...baseNav, { path: '/admin', icon: ShieldCheck, label: 'Admin' }]
    : baseNav;

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

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

      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
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

      {/* User info + logout */}
      {user && (
        <div className={cn("border-t border-sidebar-border p-2", collapsed ? "" : "p-3")}>
          {!collapsed && (
            <div className="px-2 mb-2 min-w-0">
              <div className="text-xs text-muted-foreground">Prisijungęs</div>
              <div className="text-sm font-medium text-sidebar-foreground truncate">
                {user.email}
                {isAdmin && (
                  <span className="ml-1 text-[10px] bg-primary/15 text-primary px-1.5 py-0.5 rounded">admin</span>
                )}
              </div>
              {user.company_name && (
                <div className="text-xs text-muted-foreground truncate">{user.company_name}</div>
              )}
            </div>
          )}
          <button
            onClick={handleLogout}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-sidebar-foreground hover:bg-sidebar-accent transition-colors",
              collapsed && "justify-center px-0"
            )}
            title={collapsed ? 'Atsijungti' : undefined}
          >
            <LogOut className="w-[18px] h-[18px] flex-shrink-0" />
            {!collapsed && <span>Atsijungti</span>}
          </button>
        </div>
      )}

      <button
        onClick={onToggle}
        className="h-12 flex items-center justify-center border-t border-sidebar-border text-muted-foreground hover:text-foreground transition-colors"
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </aside>
  );
}

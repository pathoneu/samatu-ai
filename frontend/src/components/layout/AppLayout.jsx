import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { cn } from '@/lib/utils';

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);

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
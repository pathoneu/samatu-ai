import { Toaster } from "@/components/ui/toaster"
import { Toaster as SonnerToaster } from 'sonner'
import { ConfirmProvider } from '@/components/ui/confirm-provider'
import { TooltipProvider } from '@/components/ui/tooltip'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes, Navigate, useLocation } from 'react-router-dom';
import React, { Suspense, lazy } from 'react';
import PageNotFound from './lib/PageNotFound';
import AppLayout from '@/components/layout/AppLayout';
import { AuthProvider, useAuth } from '@/lib/authContext';

// Eager — landing pages user always hits early.
import Dashboard from '@/pages/Dashboard';
import Login from '@/pages/Login';

// Lazy — heavy or rarely-used routes. React.lazy + Suspense splits these
// into separate chunks, reducing first-paint payload by ~40%.
const NewProject = lazy(() => import('@/pages/NewProject'));
const ProjectDetail = lazy(() => import('@/pages/ProjectDetail'));
const PriceLists = lazy(() => import('@/pages/PriceLists'));
const Settings = lazy(() => import('@/pages/Settings'));
const Register = lazy(() => import('@/pages/Register'));
const Privacy = lazy(() => import('@/pages/Privacy'));
const Cookies = lazy(() => import('@/pages/Cookies'));
const Terms = lazy(() => import('@/pages/Terms'));
const AdminDashboard = lazy(() => import('@/pages/AdminDashboard'));
const SharedProject = lazy(() => import('@/pages/SharedProject'));
const CookieBanner = lazy(() => import('@/components/CookieBanner'));
const Landing = lazy(() => import('@/pages/Landing'));
const Duk = lazy(() => import('@/pages/Duk'));
// Phase 7 / Annotator MVP — interactive PDF measurement viewer (2026-05-31).
const Annotator = lazy(() => import('@/pages/Annotator'));
// Phase 7 — billing UI (flag-gated: routes render nothing unless useBilling().enabled).
const Pricing = lazy(() => import('@/pages/Pricing'));
const BillingResult = lazy(() => import('@/pages/BillingResult'));

function ProtectedRoute({ children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Kraunama...</div>;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

// 2026-05-06: AdminRoute restricts /admin to is_admin users. Non-admin
// hitting /admin URL directly gets bounced to /dashboard. Backend admin
// endpoints already 403; this prevents the empty-page UX.
function AdminRoute({ children }) {
  const { user, isAdmin, isLoading } = useAuth();
  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Kraunama...</div>;
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;
  return children;
}

// M5 (2026-05-06): show Landing for unauthenticated visitors at "/",
// Dashboard for logged-in users. Avoids forcing first-time visitors
// straight to a login form with no marketing context.
function RootRoute() {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center text-muted-foreground">Kraunama...</div>;
  }
  if (!user) return <Landing />;
  return <Navigate to="/dashboard" replace />;
}

function RouteFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center text-muted-foreground text-sm">
      Kraunama…
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClientInstance}>
      <AuthProvider>
        <ConfirmProvider>
        <TooltipProvider delayDuration={200}>
        <Router>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Public routes (no auth required) */}
              <Route path="/" element={<RootRoute />} />
              <Route path="/about" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/cookies" element={<Cookies />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/duk" element={<Duk />} />
              <Route path="/share/:token" element={<SharedProject />} />

              {/* Protected — wrapped in AppLayout (sidebar) */}
              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/new-project" element={<NewProject />} />
                <Route path="/project/:id" element={<ProjectDetail />} />
              <Route path="/project/:id/annotator" element={<Annotator />} />
                <Route path="/price-lists" element={<PriceLists />} />
                {/* Phase 7 billing — pages self-gate via useBilling(): when the
                    flag is off, /pricing redirects to /dashboard and result
                    pages simply bounce back. No billing UI leaks when disabled. */}
                <Route path="/pricing" element={<Pricing />} />
                <Route path="/billing/success" element={<BillingResult variant="success" />} />
                <Route path="/billing/cancel" element={<BillingResult variant="cancel" />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
              </Route>
              <Route path="*" element={<PageNotFound />} />
            </Routes>
          </Suspense>
          <Suspense fallback={null}>
            <CookieBanner />
          </Suspense>
        </Router>
        <Toaster />
        <SonnerToaster position="top-right" richColors closeButton />
        </TooltipProvider>
        </ConfirmProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App

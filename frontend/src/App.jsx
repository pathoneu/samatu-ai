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
// BoFu marketing pages (2026-07-06, seo-playbook §3) — public, listed in
// sitemap.xml and prerendered by `npm run build:seo`.
const SamatininkoKaina = lazy(() => import('@/pages/bofu/SamatininkoKaina'));
const KiekiaiIsBrezinio = lazy(() => import('@/pages/bofu/KiekiaiIsBrezinio'));
const VidausApdailosSamata = lazy(() => import('@/pages/bofu/VidausApdailosSamata'));
const ApvaRenovacijosKiekiai = lazy(() => import('@/pages/bofu/ApvaRenovacijosKiekiai'));
// Phase 7 / Annotator MVP — interactive PDF measurement viewer (2026-05-31).
// DEV-ONLY (2026-07-27): a third viewer with no link anywhere in the UI. The
// import.meta.env.DEV guard is statically replaced with `false` by Vite in a
// production build, so the dynamic import is dead code there and the page is
// not emitted into dist/ at all — not merely unrouted.
const Annotator = import.meta.env.DEV ? lazy(() => import('@/pages/Annotator')) : null;
// Phase 7 — billing UI (flag-gated: routes render nothing unless useBilling().enabled).
const Pricing = lazy(() => import('@/pages/Pricing'));
const BillingResult = lazy(() => import('@/pages/BillingResult'));
const RoomSheet = lazy(() => import('@/pages/RoomSheet'));

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
              {/* English landing — deterministic two-page model (LT at /, EN
                  at /en) with hreflang pairing; see Landing's lang prop. */}
              <Route path="/en" element={<Landing lang="en" />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/privacy" element={<Privacy />} />
              <Route path="/cookies" element={<Cookies />} />
              <Route path="/terms" element={<Terms />} />
              <Route path="/duk" element={<Duk />} />
              <Route path="/samatininko-kaina" element={<SamatininkoKaina />} />
              <Route path="/kiekiai-is-brezinio" element={<KiekiaiIsBrezinio />} />
              <Route path="/vidaus-apdailos-samata" element={<VidausApdailosSamata />} />
              <Route path="/apva-renovacijos-kiekiai" element={<ApvaRenovacijosKiekiai />} />
              <Route path="/share/:token" element={<SharedProject />} />
              {/* Public by founder decision (2026-06 "pricing behind auth is a
                  marketing bug"): prospects must see prices without an account.
                  Pricing self-gates — billing off → redirect to /about#kainos. */}
              <Route path="/pricing" element={<Pricing />} />

              {/* Protected — wrapped in AppLayout (sidebar) */}
              <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/new-project" element={<NewProject />} />
                <Route path="/project/:id" element={<ProjectDetail />} />
                <Route path="/project/:id/patikra" element={<RoomSheet />} />
                {/* Dev-only (see the Annotator import above). React Router
                    ignores non-element children, so this vanishes in prod. */}
                {import.meta.env.DEV && Annotator && (
                  <Route path="/project/:id/annotator" element={<Annotator />} />
                )}
                <Route path="/price-lists" element={<PriceLists />} />
                {/* Phase 7 billing — result pages self-gate via useBilling()
                    and bounce back when the flag is off. (/pricing is public,
                    registered above.) */}
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

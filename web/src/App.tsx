import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthGate } from "./auth/AuthGate";
import { AuthProvider } from "./auth/AuthProvider";
import { RouteErrorBoundary } from "./components/RouteErrorBoundary";
import { AppShell } from "./layout/AppShell";
import { HomePage } from "./pages/HomePage";

// Home and the auth screens stay in the main bundle. The other pages load when first opened.
const TransactionsPage = lazy(() => import("./pages/transactions/TransactionsPage").then((m) => ({ default: m.TransactionsPage })));
const AccountsPage = lazy(() => import("./pages/accounts/AccountsPage").then((m) => ({ default: m.AccountsPage })));
const PlanPage = lazy(() => import("./pages/plan/PlanPage").then((m) => ({ default: m.PlanPage })));
const AssistantPage = lazy(() => import("./pages/AssistantPage").then((m) => ({ default: m.AssistantPage })));

function PageSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true">
      <p className="visually-hidden" role="status">
        Loading page
      </p>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-subhead" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
      </div>
    </div>
  );
}

// Keyed by path, so a failed page gets a fresh attempt when the user moves to another route.
function Lazy({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <RouteErrorBoundary key={pathname}>
      <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
    </RouteErrorBoundary>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route
              path="transactions"
              element={
                <Lazy>
                  <TransactionsPage />
                </Lazy>
              }
            />
            <Route
              path="accounts"
              element={
                <Lazy>
                  <AccountsPage />
                </Lazy>
              }
            />
            <Route
              path="plan"
              element={
                <Lazy>
                  <PlanPage />
                </Lazy>
              }
            />
            <Route
              path="assistant"
              element={
                <Lazy>
                  <AssistantPage />
                </Lazy>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthGate>
    </AuthProvider>
  );
}

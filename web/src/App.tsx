import { Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./auth/AuthGate";
import { AuthProvider } from "./auth/AuthProvider";
import { AppShell } from "./layout/AppShell";
import { AssistantPage } from "./pages/AssistantPage";
import { HomePage } from "./pages/HomePage";
import { PlanPage } from "./pages/plan/PlanPage";
import { AccountsPage } from "./pages/accounts/AccountsPage";
import { TransactionsPage } from "./pages/transactions/TransactionsPage";

export function App() {
  return (
    <AuthProvider>
      <AuthGate>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="transactions" element={<TransactionsPage />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="plan" element={<PlanPage />} />
            <Route path="assistant" element={<AssistantPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthGate>
    </AuthProvider>
  );
}

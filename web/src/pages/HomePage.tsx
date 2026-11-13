import type { DashboardSummary } from "../api/types";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { HomeLoadError, HomeSkeleton } from "./home/HomeStates";
import { InsightsSection } from "./home/InsightsSection";
import { ReviewRow, UpcomingBills } from "./home/UpcomingBills";
import { KpiTiles } from "./home/KpiTiles";
import { SafeToSpend } from "./home/SafeToSpend";
import { useDashboardSummary } from "./home/useDashboardSummary";

export function HomePage() {
  useDocumentTitle("Home");
  const { state, reload } = useDashboardSummary();
  return (
    <div className="home">
      <h1 className="large-title">Home</h1>
      {state.status === "loading" ? <HomeSkeleton /> : null}
      {state.status === "error" ? <HomeLoadError onRetry={reload} /> : null}
      {state.status === "ready" ? <HomeContent summary={state.summary} /> : null}
    </div>
  );
}

function HomeContent({ summary }: { summary: DashboardSummary }) {
  return (
    <>
      <SafeToSpend safe={summary.safe_to_spend} />
      <KpiTiles
        netWorthMinor={summary.net_worth_minor}
        monthExpenseMinor={summary.month_expense_minor}
        monthIncomeMinor={summary.month_income_minor}
      />
      <InsightsSection />
      <UpcomingBills bills={summary.upcoming_bills} />
      <ReviewRow pendingCount={summary.pending_review_count} />
    </>
  );
}

import type { DashboardSummary } from "../api/types";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { HomeLoadError, HomeSkeleton } from "./home/HomeStates";
import { ReviewRow, UpcomingBills } from "./home/UpcomingBills";
import { SafeToSpend } from "./home/SafeToSpend";
import { StatRows } from "./home/StatRows";
import { useDashboardSummary } from "./home/useDashboardSummary";

export function HomePage() {
  useDocumentTitle("Home");
  const { state, reload } = useDashboardSummary();
  return (
    <div className="home">
      <h1 className="title">Home</h1>
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
      <StatRows
        netWorthMinor={summary.net_worth_minor}
        monthExpenseMinor={summary.month_expense_minor}
        monthIncomeMinor={summary.month_income_minor}
      />
      <UpcomingBills bills={summary.upcoming_bills} />
      <ReviewRow pendingCount={summary.pending_review_count} />
    </>
  );
}

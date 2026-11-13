import type { InsightsSummary } from "../../api/types";
import { LoadError } from "../../components/LoadError";
import { CategorySpend } from "./CategorySpend";
import { HighlightList } from "./HighlightList";
import { NO_HIGHLIGHTS_MESSAGE } from "./insightFormat";
import { TrendChart } from "./TrendChart";
import { useInsightsSummary } from "./useInsightsSummary";

// Loads on its own, so a slow or failed insights request never holds back Safe to Spend.
export function InsightsSection() {
  const loader = useInsightsSummary();
  const { state } = loader;
  if (state.status === "loading") {
    return <InsightsSkeleton />;
  }
  if (state.status === "error") {
    return <LoadError message="Could not load your insights. Check your connection and try again." onRetry={loader.reload} />;
  }
  return <InsightCards summary={state.data} />;
}

function InsightCards({ summary }: { summary: InsightsSummary }) {
  return (
    <>
      <CategorySpend categories={summary.categories} />
      <TrendChart summary={summary} />
      <HighlightsCard highlights={summary.highlights} />
    </>
  );
}

function HighlightsCard({ highlights }: { highlights: InsightsSummary["highlights"] }) {
  return (
    <section className="card" aria-labelledby="highlights-heading">
      <h2 id="highlights-heading" className="eyebrow">
        Highlights
      </h2>
      {highlights.length > 0 ? (
        <HighlightList highlights={highlights} />
      ) : (
        <p className="empty-state">{NO_HIGHLIGHTS_MESSAGE}</p>
      )}
    </section>
  );
}

function InsightsSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true">
      <p className="visually-hidden" role="status">
        Loading your insights
      </p>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-subhead" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
      </div>
    </div>
  );
}

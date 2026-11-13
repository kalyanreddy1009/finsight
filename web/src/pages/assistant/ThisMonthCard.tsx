import { LoadError } from "../../components/LoadError";
import { HighlightList } from "../home/HighlightList";
import { NO_HIGHLIGHTS_MESSAGE } from "../home/insightFormat";
import { useInsightsSummary } from "../home/useInsightsSummary";
import { SummariseMonth } from "./SummariseMonth";

interface ThisMonthCardProps {
  aiReady: boolean;
  aiBusy: boolean;
  onBusyChange: (busy: boolean) => void;
  onAiProblem: () => void;
}

// The rule-based highlights are always shown, so the page is useful without a model.
export function ThisMonthCard({ aiReady, aiBusy, onBusyChange, onAiProblem }: ThisMonthCardProps) {
  const loader = useInsightsSummary();
  const { state } = loader;
  return (
    <section className="card" aria-labelledby="this-month-heading">
      <h2 id="this-month-heading" className="eyebrow">
        This Month
      </h2>
      {state.status === "loading" ? (
        <p className="empty-state" role="status">
          Loading this month…
        </p>
      ) : null}
      {state.status === "error" ? (
        <LoadError message="Could not load this month. Check your connection and try again." onRetry={loader.reload} />
      ) : null}
      {state.status === "ready" && state.data.highlights.length > 0 ? <HighlightList highlights={state.data.highlights} /> : null}
      {state.status === "ready" && state.data.highlights.length === 0 ? (
        <p className="empty-state">{NO_HIGHLIGHTS_MESSAGE}</p>
      ) : null}
      {aiReady ? (
        <SummariseMonth aiBusy={aiBusy} onBusyChange={onBusyChange} onAiProblem={onAiProblem} />
      ) : (
        <p className="footnote">A written summary is available once the local AI is ready.</p>
      )}
    </section>
  );
}

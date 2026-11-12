import { useCallback, useEffect, useState } from "react";
import { getDashboardSummary } from "../../api/dashboard";
import type { DashboardSummary } from "../../api/types";

export type SummaryState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; summary: DashboardSummary };

export function useDashboardSummary(): { state: SummaryState; reload: () => void } {
  const [state, setState] = useState<SummaryState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getDashboardSummary().then(
      (summary) => {
        if (!cancelled) {
          setState({ status: "ready", summary });
        }
      },
      () => {
        if (!cancelled) {
          setState({ status: "error" });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((count) => count + 1);
  }, []);

  return { state, reload };
}

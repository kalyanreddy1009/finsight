import { useEffect, useRef, useState } from "react";
import { requestInsight } from "../../api/ai";
import { ApiError } from "../../api/client";
import type { AiInsight } from "../../api/types";
import { Button } from "../../components/Button";
import { isAiStatusProblem } from "./useAiStatus";

type SummaryState =
  | { phase: "idle" }
  | { phase: "pending" }
  | { phase: "done"; insight: AiInsight }
  | { phase: "error"; message: string };

const FALLBACK_MESSAGE = "Could not summarise your month. Try again.";

interface SummariseMonthProps {
  // True while a chat request runs, so the summary waits for it.
  aiBusy: boolean;
  onBusyChange: (busy: boolean) => void;
  onAiProblem: () => void;
}

// Asks the local AI for a written summary. The model text is rendered as plain text only.
export function SummariseMonth({ aiBusy, onBusyChange, onAiProblem }: SummariseMonthProps) {
  const [state, setState] = useState<SummaryState>({ phase: "idle" });
  const mounted = useRef(true);
  const busy = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const pending = state.phase === "pending";

  useEffect(() => {
    onBusyChange(pending);
  }, [pending, onBusyChange]);

  // If this card unmounts mid-request, the parent must not stay locked.
  useEffect(() => () => onBusyChange(false), [onBusyChange]);

  async function summarise() {
    if (busy.current) {
      return;
    }
    busy.current = true;
    setState({ phase: "pending" });
    try {
      const reply = await requestInsight();
      if (mounted.current) {
        setState({ phase: "done", insight: reply.insight });
      }
    } catch (error) {
      if (mounted.current) {
        setState({ phase: "error", message: error instanceof ApiError ? error.message : FALLBACK_MESSAGE });
        if (isAiStatusProblem(error)) {
          onAiProblem();
        }
      }
    } finally {
      busy.current = false;
    }
  }

  return (
    <div className="ai-summary">
      <Button variant="primary" onClick={() => void summarise()} disabled={pending || aiBusy}>
        {pending ? "Summarising…" : "Summarise My Month"}
      </Button>
      {pending ? (
        <p className="footnote" role="status">
          The local AI is working on it. This can take up to two minutes.
        </p>
      ) : null}
      {state.phase === "error" ? (
        <p className="field-error" role="alert">
          {state.message}
        </p>
      ) : null}
      {state.phase === "done" ? <InsightResult insight={state.insight} /> : null}
    </div>
  );
}

function InsightResult({ insight }: { insight: AiInsight }) {
  return (
    <div className="ai-result">
      <h3 className="title2 ai-text">{insight.summary_headline}</h3>
      {insight.key_observations.length > 0 ? (
        <>
          <p className="subhead">Key observations</p>
          <ul className="ai-list">
            {insight.key_observations.map((item, index) => (
              <li key={`obs-${index}`} className="ai-text">
                {item}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {insight.recommended_actions.length > 0 ? (
        <>
          <p className="subhead">Suggested actions</p>
          <ul className="ai-list">
            {insight.recommended_actions.map((item, index) => (
              <li key={`act-${index}`} className="ai-text">
                {item}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="footnote ai-text">{insight.disclaimer}</p>
    </div>
  );
}

import { useState } from "react";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import "../styles/assistant.css";
import { ChatPanel } from "./assistant/ChatPanel";
import { StatusCard } from "./assistant/StatusCard";
import { ThisMonthCard } from "./assistant/ThisMonthCard";
import { useAiStatus } from "./assistant/useAiStatus";

export function AssistantPage() {
  useDocumentTitle("Assistant");
  const { state, check } = useAiStatus();
  const ready = state.kind === "ready";
  // Chat and the summary can each be in flight. The page is busy while either one is.
  const [chatBusy, setChatBusy] = useState(false);
  const [summaryBusy, setSummaryBusy] = useState(false);
  const aiBusy = chatBusy || summaryBusy;

  return (
    <div className="assistant-page">
      <header className="assistant-header">
        <p className="eyebrow">Private · On this device</p>
        <h1 className="large-title">Assistant</h1>
      </header>
      <StatusCard state={state} onCheck={check} />
      <ThisMonthCard aiReady={ready} aiBusy={aiBusy} onBusyChange={setSummaryBusy} onAiProblem={check} />
      <ChatPanel enabled={ready} aiBusy={aiBusy} onBusyChange={setChatBusy} onAiProblem={check} />
    </div>
  );
}

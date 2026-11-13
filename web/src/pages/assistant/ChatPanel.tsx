import { useEffect, useRef } from "react";
import { Button } from "../../components/Button";
import { ChatComposer } from "./ChatComposer";
import { ChatLog } from "./ChatLog";
import { useChat } from "./useChat";

interface ChatPanelProps {
  enabled: boolean;
  // True while any AI request runs, including the summary.
  aiBusy: boolean;
  onBusyChange: (busy: boolean) => void;
  onAiProblem: () => void;
}

// Chat is only enabled when the local AI is ready. The conversation is never stored.
export function ChatPanel({ enabled, aiBusy, onBusyChange, onAiProblem }: ChatPanelProps) {
  const chat = useChat(onAiProblem);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    onBusyChange(chat.pending);
  }, [chat.pending, onBusyChange]);

  function retry() {
    chat.retry();
    inputRef.current?.focus();
  }

  return (
    <section className="card" aria-labelledby="chat-heading">
      <div className="chat-header">
        <h2 id="chat-heading" className="eyebrow">
          Ask the Assistant
        </h2>
        {chat.entries.length > 0 ? (
          <Button variant="plain" onClick={chat.clear} disabled={aiBusy}>
            Clear Conversation
          </Button>
        ) : null}
      </div>
      <ChatLog entries={chat.entries} pending={chat.pending} failure={chat.failure} onRetry={retry} />
      <ChatComposer enabled={enabled} aiBusy={aiBusy} pending={chat.pending} inputRef={inputRef} onSend={chat.send} />
    </section>
  );
}

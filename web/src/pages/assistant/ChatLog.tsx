import { Button } from "../../components/Button";
import type { ChatFailure, ChatEntry } from "./useChat";

interface ChatLogProps {
  entries: readonly ChatEntry[];
  pending: boolean;
  failure: ChatFailure | null;
  onRetry: () => void;
}

// Message text is a plain React text node (pre-wrap in CSS): model output is never parsed as HTML.
export function ChatLog({ entries, pending, failure, onRetry }: ChatLogProps) {
  return (
    <div className="chat-log" role="log" aria-live="polite" aria-label="Conversation">
      {entries.length === 0 && !pending && failure === null ? (
        <p className="empty-state">Ask about your spending, bills or goals. Answers use your own numbers.</p>
      ) : null}
      {entries.map((entry) => (
        <div key={entry.id} className={`chat-msg chat-msg-${entry.role}`}>
          <span className="chat-who">{entry.role === "user" ? "You" : "Assistant"}</span>
          <p className="chat-text">{entry.text}</p>
        </div>
      ))}
      {pending ? <p className="footnote">The local AI is thinking. This can take up to two minutes.</p> : null}
      {failure !== null ? (
        <div className="chat-error">
          <p className="field-error">{failure.message}</p>
          <Button variant="secondary" onClick={onRetry}>
            Try Again
          </Button>
        </div>
      ) : null}
    </div>
  );
}

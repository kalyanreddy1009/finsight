import { useState, type FormEvent, type KeyboardEvent, type RefObject } from "react";
import { MAX_QUESTION_LENGTH } from "../../api/ai";
import { Button } from "../../components/Button";

export const SUGGESTED_QUESTIONS: readonly string[] = [
  "How much can I safely spend this week?",
  "Where did most of my money go this month?",
  "Which bills are due soon?",
  "Am I on track with my goals?",
];

const DISABLED_HINT = "Chat turns on when the local AI is ready. See the status card above.";
const ENABLED_HINT = "Press Enter to send. Press Shift and Enter for a new line.";

interface ChatComposerProps {
  enabled: boolean;
  // True while any AI request runs (chat or summary). Chips, Send and the question box stop accepting input.
  aiBusy: boolean;
  pending: boolean;
  inputRef: RefObject<HTMLTextAreaElement>;
  // Returns true when the question was accepted, so the draft can be cleared.
  onSend: (question: string) => boolean;
}

export function ChatComposer({ enabled, aiBusy, pending, inputRef, onSend }: ChatComposerProps) {
  const [draft, setDraft] = useState("");
  const blocked = !enabled || aiBusy;

  // Keeps keyboard users in place: the control they used may be disabled or removed by the send.
  function focusInput() {
    inputRef.current?.focus();
  }

  function submit() {
    if (!blocked && onSend(draft)) {
      setDraft("");
    }
    focusInput();
  }

  function sendSuggestion(question: string) {
    onSend(question);
    focusInput();
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <>
      <div className="chat-chips" role="group" aria-label="Suggested questions">
        {SUGGESTED_QUESTIONS.map((question) => (
          <button key={question} type="button" className="chat-chip" disabled={blocked} onClick={() => sendSuggestion(question)}>
            {question}
          </button>
        ))}
      </div>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="chat-input">Your question</label>
          <textarea
            id="chat-input"
            ref={inputRef}
            className="field-input chat-input"
            rows={3}
            maxLength={MAX_QUESTION_LENGTH}
            value={draft}
            disabled={!enabled}
            aria-describedby="chat-input-hint"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <p id="chat-input-hint" className="field-hint">
            {enabled ? ENABLED_HINT : DISABLED_HINT}
          </p>
        </div>
        <Button type="submit" variant="primary" disabled={blocked || draft.trim() === ""}>
          {pending ? "Thinking…" : "Send"}
        </Button>
      </form>
    </>
  );
}

import { useState, type ReactNode } from "react";
import { Button } from "../../components/Button";
import type { AiState } from "./useAiStatus";

export const PRIVACY_LINE = "Your data never leaves this device. The assistant reads your numbers; it cannot change them.";

interface StatusCardProps {
  state: AiState;
  onCheck: () => void;
}

export function StatusCard({ state, onCheck }: StatusCardProps) {
  return (
    <section className="card" aria-labelledby="ai-status-heading">
      <h2 id="ai-status-heading" className="eyebrow">
        Local AI
      </h2>
      <StatusBody state={state} onCheck={onCheck} />
      <p className="footnote">{PRIVACY_LINE}</p>
    </section>
  );
}

function StatusBody({ state, onCheck }: StatusCardProps) {
  switch (state.kind) {
    case "loading":
      return (
        <p className="empty-state" role="status">
          Checking the local AI…
        </p>
      );
    case "ready":
      return (
        <StatusLine tone="ready" label="Ready">
          Running locally with <span className="num">{state.model}</span>
        </StatusLine>
      );
    case "missing":
      return (
        <>
          <StatusLine tone="warning" label="Model missing">
            Ollama is running, but <span className="num">{state.model}</span> is not installed
          </StatusLine>
          <CopyCommand command={`ollama pull ${state.model}`} />
          <Button onClick={onCheck}>Check Again</Button>
        </>
      );
    case "down":
      return (
        <>
          <StatusLine tone="warning" label="Not running">
            The local AI is not running
          </StatusLine>
          <ol className="ai-steps">
            <li>
              Install Ollama from <span className="num">ollama.com</span>.
            </li>
            <li>
              {state.model === null ? (
                "Then pull the AI model with ollama pull followed by the model name."
              ) : (
                <>
                  Then run <code className="ai-command">{`ollama pull ${state.model}`}</code>.
                </>
              )}
            </li>
          </ol>
          <Button onClick={onCheck}>Check Again</Button>
        </>
      );
    case "error":
      return (
        <>
          <StatusLine tone="warning" label="Unavailable">
            {state.message}
          </StatusLine>
          <Button onClick={onCheck}>Check Again</Button>
        </>
      );
  }
}

function StatusLine({ tone, label, children }: { tone: "ready" | "warning"; label: string; children: ReactNode }) {
  return (
    <div className="ai-status-line">
      <span className={`ai-pill ai-pill-${tone}`}>
        <span className="dot" aria-hidden="true" />
        {label}
      </span>
      <p className="headline">{children}</p>
    </div>
  );
}

// Shows the command in monospace with a button that copies it. Copying is a convenience only.
function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState<"idle" | "done" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied("done");
    } catch {
      setCopied("failed");
    }
  }

  return (
    <div className="ai-copy">
      <code className="ai-command">{command}</code>
      <Button variant="secondary" onClick={() => void copy()}>
        {copied === "done" ? "Copied" : "Copy Command"}
      </Button>
      {copied === "failed" ? <p className="field-error">Could not copy. Select the command and copy it by hand.</p> : null}
    </div>
  );
}

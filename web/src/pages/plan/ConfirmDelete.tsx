import { Button } from "../../components/Button";

interface ConfirmDeleteProps {
  question: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Asks for a second, explicit click in place, so nothing is removed by a single tap.
export function ConfirmDelete({ question, busy, onConfirm, onCancel }: ConfirmDeleteProps) {
  return (
    <div className="plan-confirm" role="group" aria-label={question}>
      <span className="secondary-text">{question}</span>
      <div className="plan-row-actions">
        <Button variant="secondary" className="plan-danger" onClick={onConfirm} disabled={busy}>
          {busy ? "Deleting…" : "Confirm Delete"}
        </Button>
        <Button variant="plain" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

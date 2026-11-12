import { useState } from "react";
import { commitStatement, type CommitResult, type Statement, type StatementRow } from "../../api/statements";
import { Button } from "../../components/Button";
import { messageFor } from "./format";

interface CommitPanelProps {
  statement: Statement;
  rows: readonly StatementRow[];
  onCommitted: () => void;
}

// Returns why the statement cannot be committed yet, or null when it can.
export function commitBlocker(pending: number, difference: number | null): string | null {
  if (pending > 0) {
    const noun = pending === 1 ? "row still needs" : "rows still need";
    return `${pending} ${noun} a decision. Approve or reject every pending row to commit.`;
  }
  if (difference === null) {
    return "This statement has not been reconciled yet, so it cannot be committed.";
  }
  if (difference !== 0) {
    return "The statement does not reconcile with its closing balance, so it cannot be committed yet.";
  }
  return null;
}

export function CommitPanel({ statement, rows, onCommitted }: CommitPanelProps) {
  const [committing, setCommitting] = useState(false);
  const [result, setResult] = useState<CommitResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pending = rows.filter((row) => row.row_status === "PENDING_REVIEW").length;
  const readOnly = statement.processing_status !== "REVIEW_REQUIRED";
  const blocker = commitBlocker(pending, statement.reconciliation_diff_minor);

  async function handleCommit() {
    setCommitting(true);
    setError(null);
    try {
      const outcome = await commitStatement(statement.id);
      setResult(outcome);
      onCommitted();
    } catch (failure) {
      setError(messageFor(failure));
    } finally {
      setCommitting(false);
    }
  }

  return (
    <section className="card accounts-section" aria-labelledby="commit-heading">
      <h2 id="commit-heading" className="section-title">
        Commit
      </h2>
      {result ? <CommitOutcomeText outcome={result} /> : null}
      {!result && readOnly ? <p className="empty-state">This statement is already committed.</p> : null}
      {readOnly ? null : (
        <>
          {blocker ? <p className="empty-state">{blocker}</p> : null}
          <div>
            <Button variant="primary" disabled={blocker !== null || committing} onClick={() => void handleCommit()}>
              {committing ? "Committing…" : "Commit Statement"}
            </Button>
          </div>
        </>
      )}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function CommitOutcomeText({ outcome }: { outcome: CommitResult }) {
  if (outcome.already_committed) {
    return (
      <p className="status-text" role="status">
        This statement was already committed.
      </p>
    );
  }
  const noun = outcome.committed_count === 1 ? "transaction" : "transactions";
  return (
    <div role="status">
      <p className="status-text">{`Committed ${outcome.committed_count} ${noun}`}</p>
      {outcome.snapshot_written ? null : (
        <p className="warning-text">The ledger balance does not match this statement's closing balance.</p>
      )}
    </div>
  );
}

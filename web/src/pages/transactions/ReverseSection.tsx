import { useRef, useState } from "react";
import { reverseTransaction } from "../../api/transactions";
import type { Transaction } from "../../api/types";
import { Button } from "../../components/Button";
import { useReportBusy } from "../../hooks/useReportBusy";
import { describeError } from "./transactionErrors";

interface ReverseSectionProps {
  transaction: Transaction;
  onReversed: () => void;
  onBusyChange?: (busy: boolean) => void;
}

// Reversal is irreversible, so it sits behind a confirmation step. The trigger is not prominent.
export function ReverseSection({ transaction, onReversed, onBusyChange }: ReverseSectionProps) {
  const [confirming, setConfirming] = useState(false);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  useReportBusy(posting, onBusyChange);

  async function handlePost() {
    setPosting(true);
    setError(null);
    try {
      await reverseTransaction(transaction.id, idempotencyKey.current);
      idempotencyKey.current = crypto.randomUUID();
      onReversed();
    } catch (failure) {
      setPosting(false);
      setError(describeError(failure));
    }
  }

  if (!confirming) {
    return (
      <div className="tx-action-row">
        <Button variant="plain" onClick={() => setConfirming(true)}>
          Reverse Transaction
        </Button>
      </div>
    );
  }

  return (
    <div className="card notice" role="group" aria-label="Confirm reversal">
      <p>Reverse this transaction? This posts an opposite entry and cannot be undone.</p>
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="tx-action-row">
        <Button variant="secondary" onClick={handlePost} disabled={posting}>
          {posting ? "Posting…" : "Post Reversal"}
        </Button>
        <Button variant="plain" onClick={() => setConfirming(false)} disabled={posting}>
          Keep Transaction
        </Button>
      </div>
    </div>
  );
}

import { useState } from "react";
import { listSplits, type Split } from "../../api/splits";
import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { formatMinor } from "../../lib/money";
import { assetAccounts } from "./accountOptions";
import { formatIsoDate } from "./format";
import { LoadError } from "../../components/LoadError";
import { RepaymentDialog } from "./RepaymentDialog";
import { useLoader, type LoadState } from "../../hooks/useLoader";

// Open and partly repaid splits, newest first.
async function loadOutstandingSplits(): Promise<Split[]> {
  const [open, partial] = await Promise.all([listSplits("OPEN"), listSplits("PARTIAL")]);
  return [...open, ...partial].sort((a, b) => b.transaction_date.localeCompare(a.transaction_date));
}

interface SplitsSectionProps {
  accounts: readonly Account[];
}

export function SplitsSection({ accounts }: SplitsSectionProps) {
  const splits = useLoader(loadOutstandingSplits);
  const [active, setActive] = useState<Split | null>(null);
  return (
    <section className="accounts-section" aria-labelledby="owed-heading">
      <h2 id="owed-heading" className="section-title">
        Owed to You
      </h2>
      <SplitList state={splits.state} onRetry={splits.reload} onRecord={setActive} />
      <RepaymentDialog
        split={active}
        bankAccounts={assetAccounts(accounts)}
        onClose={() => setActive(null)}
        onSettled={() => {
          setActive(null);
          splits.reload();
        }}
      />
    </section>
  );
}

interface SplitListProps {
  state: LoadState<Split[]>;
  onRetry: () => void;
  onRecord: (split: Split) => void;
}

function SplitList({ state, onRetry, onRecord }: SplitListProps) {
  if (state.status === "loading") {
    return (
      <p className="empty-state" role="status">
        Loading your splits…
      </p>
    );
  }
  if (state.status === "error") {
    return <LoadError message="Could not load your splits. Check your connection and try again." onRetry={onRetry} />;
  }
  if (state.data.length === 0) {
    return <p className="empty-state">Nobody owes you anything.</p>;
  }
  return (
    <ul className="row-list">
      {state.data.map((split) => (
        <li className="row split-row" key={split.id}>
          <div className="row-main">
            <span className="row-title">{split.counterparty_name}</span>
            <span className="secondary-text">
              {split.description ?? "No description"} · {formatIsoDate(split.transaction_date)}
            </span>
            <span className="secondary-text">{split.status === "PARTIAL" ? "Partly repaid" : "Not repaid yet"}</span>
          </div>
          <div className="split-end">
            <span className="row-amount">{formatMinor(split.outstanding_minor)} outstanding</span>
            <Button variant="secondary" onClick={() => onRecord(split)}>
              Record Repayment
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

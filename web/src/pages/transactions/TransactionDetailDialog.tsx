import { useState } from "react";
import type { Category, Transaction } from "../../api/types";
import { formatMinor } from "../../lib/money";
import { ReverseSection } from "./ReverseSection";
import { TransactionEditForm } from "./TransactionEditForm";
import { Dialog } from "../../components/Dialog";
import { formatDateHeading } from "./groupByDate";
import { displayTitle, isMoneyIn, isSplitExpense, signedAmountText, statusLabel } from "./transactionLabels";

interface TransactionDetailDialogProps {
  transaction: Transaction | null;
  categories: readonly Category[];
  onClose: () => void;
  onSaved: (transaction: Transaction) => void;
  onReversed: () => void;
}

// Keyed by id and version, so the body starts fresh from every server copy.
export function TransactionDetailDialog({
  transaction,
  categories,
  onClose,
  onSaved,
  onReversed,
}: TransactionDetailDialogProps) {
  // Saving and reversing are tracked separately: either one in flight keeps the dialog open.
  const [editing, setEditing] = useState(false);
  const [reversing, setReversing] = useState(false);
  return (
    <Dialog open={transaction !== null} title="Transaction" onClose={onClose} busy={editing || reversing}>
      {transaction !== null ? (
        <TransactionDetailBody
          key={`${transaction.id}:${transaction.version}`}
          transaction={transaction}
          categories={categories}
          onSaved={onSaved}
          onReversed={onReversed}
          onEditBusyChange={setEditing}
          onReverseBusyChange={setReversing}
        />
      ) : null}
    </Dialog>
  );
}

interface TransactionDetailBodyProps {
  transaction: Transaction;
  categories: readonly Category[];
  onSaved: (transaction: Transaction) => void;
  onReversed: () => void;
  onEditBusyChange: (busy: boolean) => void;
  onReverseBusyChange: (busy: boolean) => void;
}

function TransactionDetailBody({
  transaction,
  categories,
  onSaved,
  onReversed,
  onEditBusyChange,
  onReverseBusyChange,
}: TransactionDetailBodyProps) {
  if (transaction.review_status === "SUPERSEDED") {
    return (
      <div className="tx-dialog-body">
        <TransactionFacts transaction={transaction} />
        <p className="card notice">This transaction was reversed, so it can no longer be changed.</p>
      </div>
    );
  }
  return (
    <div className="tx-dialog-body">
      <TransactionFacts transaction={transaction} />
      <TransactionEditForm
        transaction={transaction}
        categories={categories}
        onSaved={onSaved}
        onBusyChange={onEditBusyChange}
      />
      <ReverseSection transaction={transaction} onReversed={onReversed} onBusyChange={onReverseBusyChange} />
    </div>
  );
}

function TransactionFacts({ transaction }: { transaction: Transaction }) {
  const facts: Array<[string, string]> = [
    ["Date", formatDateHeading(transaction.transaction_date)],
    ["Description", displayTitle(transaction)],
    ["Original description", transaction.description ?? "Not recorded"],
    ["Amount", signedAmountText(transaction)],
    ["Direction", isMoneyIn(transaction) ? "Money in" : "Money out"],
    ["Account", transaction.account_name],
    ["Counterparty", transaction.counterparty_account_name],
    ["Type", transaction.transaction_type],
    ["Status", statusLabel(transaction.review_status)],
    ["Verified", transaction.is_verified ? "Yes" : "No"],
  ];
  if (isSplitExpense(transaction)) {
    facts.splice(5, 0, ["Your share", formatMinor(transaction.user_share_minor)]);
  }
  return (
    <dl className="tx-details">
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

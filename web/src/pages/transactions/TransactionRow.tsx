import type { Transaction } from "../../api/types";
import { ChevronIcon } from "../../components/icons";
import { badgesFor, displayTitle, isMoneyIn, signedAmountText, yourShareText } from "./transactionLabels";

interface TransactionRowProps {
  transaction: Transaction;
  onSelect: (transaction: Transaction) => void;
}

export function TransactionRow({ transaction, onSelect }: TransactionRowProps) {
  const reversed = transaction.review_status === "SUPERSEDED";
  const className = reversed ? "row tx-row tx-row--reversed" : "row tx-row";
  const badges = badgesFor(transaction);
  const shareText = yourShareText(transaction);
  return (
    <li>
      <button type="button" className={className} onClick={() => onSelect(transaction)}>
        <span className="row-main tx-row-main">
          <span className="tx-row-title">{displayTitle(transaction)}</span>
          <span className="tx-row-meta">{`${transaction.category_name ?? "No category"} · ${transaction.account_name}`}</span>
          {shareText !== null ? <span className="tx-row-meta">{shareText}</span> : null}
          {badges.length > 0 ? (
            <span className="tx-badges">
              {badges.map((badge) => (
                <span key={badge} className="tx-badge">
                  {badge}
                </span>
              ))}
            </span>
          ) : null}
        </span>
        <span className="tx-row-end">
          <span className="row-amount">
            {signedAmountText(transaction)}
            <span className="visually-hidden">{isMoneyIn(transaction) ? " in" : " out"}</span>
          </span>
          <span aria-hidden="true">
            <ChevronIcon className="row-chevron" />
          </span>
        </span>
      </button>
    </li>
  );
}

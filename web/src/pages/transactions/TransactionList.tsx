import type { Transaction } from "../../api/types";
import { Button } from "../../components/Button";
import { groupByDate, type DateGroup } from "./groupByDate";
import { ListEmpty, ListError, ListSkeleton } from "./ListStates";
import { TransactionRow } from "./TransactionRow";
import type { TransactionListView } from "./useTransactionList";

interface TransactionListProps {
  view: TransactionListView;
  filtersActive: boolean;
  onSelect: (transaction: Transaction) => void;
  onAdd: () => void;
}

export function TransactionList({ view, filtersActive, onSelect, onAdd }: TransactionListProps) {
  if (view.status === "loading") {
    return <ListSkeleton />;
  }
  if (view.status === "error") {
    return <ListError onRetry={view.reload} />;
  }
  if (view.items.length === 0) {
    return <ListEmpty filtersActive={filtersActive} onAdd={onAdd} />;
  }
  return (
    <div className="tx-list">
      {groupByDate(view.items).map((group) => (
        <DateSection key={group.date} group={group} onSelect={onSelect} />
      ))}
      {view.loadMoreFailed ? (
        <p className="field-error" role="alert">
          Could not load more transactions.
        </p>
      ) : null}
      {view.nextCursor !== null ? (
        <Button className="tx-load-more" onClick={view.loadMore} disabled={view.isLoadingMore}>
          {view.isLoadingMore ? "Loading…" : "Load More"}
        </Button>
      ) : null}
    </div>
  );
}

function DateSection({ group, onSelect }: { group: DateGroup; onSelect: (transaction: Transaction) => void }) {
  const headingId = `tx-date-${group.date}`;
  return (
    <section className="tx-group" aria-labelledby={headingId}>
      <h2 id={headingId} className="tx-date-heading">
        {group.label}
      </h2>
      <ul className="tx-group-rows">
        {group.items.map((transaction) => (
          <TransactionRow key={transaction.id} transaction={transaction} onSelect={onSelect} />
        ))}
      </ul>
    </section>
  );
}

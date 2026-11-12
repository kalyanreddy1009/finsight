import { Button } from "../../components/Button";

export function ListSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true">
      <p className="visually-hidden" role="status">
        Loading transactions
      </p>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
      </div>
    </div>
  );
}

interface ListEmptyProps {
  filtersActive: boolean;
  onAdd: () => void;
}

export function ListEmpty({ filtersActive, onAdd }: ListEmptyProps) {
  if (filtersActive) {
    return (
      <div className="card">
        <p className="empty-state">No transactions match these filters. Clear a filter to see more.</p>
      </div>
    );
  }
  return (
    <div className="card empty-block">
      <h2 className="tx-empty-title">No transactions yet</h2>
      <p className="empty-state">Record an expense, income or transfer to start your ledger.</p>
      <Button variant="secondary" onClick={onAdd}>
        Add Expense
      </Button>
    </div>
  );
}

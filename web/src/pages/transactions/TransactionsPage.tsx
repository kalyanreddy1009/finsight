import { useCallback, useState } from "react";
import type { Transaction } from "../../api/types";
import { Button } from "../../components/Button";
import { LoadError } from "../../components/LoadError";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import "../../styles/transactions.css";
import { QuickAddDialog } from "./QuickAddDialog";
import { TransactionDetailDialog } from "./TransactionDetailDialog";
import { TransactionFilters } from "./TransactionFilters";
import { TransactionList } from "./TransactionList";
import { useReferenceData } from "./useReferenceData";
import { useTransactionFilters } from "./useTransactionFilters";
import { useTransactionList } from "./useTransactionList";

export function TransactionsPage() {
  useDocumentTitle("Transactions");
  const { filters, setFilters } = useTransactionFilters();
  const references = useReferenceData();
  const list = useTransactionList(filters);
  const { reload: reloadList } = list;
  const { reload: reloadReferences } = references;
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState<Transaction | null>(null);

  const openAdd = useCallback(() => setAddOpen(true), []);
  const closeAdd = useCallback(() => setAddOpen(false), []);
  const closeDetail = useCallback(() => setSelected(null), []);
  const handleSaved = useCallback(
    (updated: Transaction) => {
      setSelected(updated);
      reloadList();
    },
    [reloadList],
  );
  const handleReversed = useCallback(() => {
    setSelected(null);
    reloadList();
  }, [reloadList]);

  const filtersActive = filters.q.trim() !== "" || filters.accountId !== "" || filters.categoryId !== "" || filters.needsReview;

  return (
    <div className="tx-page">
      <header className="tx-header">
        <h1 className="title">Transactions</h1>
        <Button variant="primary" onClick={openAdd}>
          Add Expense
        </Button>
      </header>
      {references.status === "error" ? (
        <LoadError message="Accounts and categories could not be loaded." onRetry={reloadReferences} />
      ) : null}
      <TransactionFilters
        filters={filters}
        accounts={references.accounts}
        categories={references.categories}
        onChange={setFilters}
      />
      <TransactionList view={list} filtersActive={filtersActive} onSelect={setSelected} onAdd={openAdd} />
      <QuickAddDialog
        open={addOpen}
        accounts={references.accounts}
        categories={references.categories}
        onClose={closeAdd}
        onAdded={reloadList}
      />
      <TransactionDetailDialog
        transaction={selected}
        categories={references.categories}
        onClose={closeDetail}
        onSaved={handleSaved}
        onReversed={handleReversed}
      />
    </div>
  );
}

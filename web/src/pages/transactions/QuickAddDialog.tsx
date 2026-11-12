import type { Account, Category } from "../../api/types";
import { AddTransactionForm } from "./AddTransactionForm";
import { Dialog } from "../../components/Dialog";

interface QuickAddDialogProps {
  open: boolean;
  accounts: readonly Account[];
  categories: readonly Category[];
  onClose: () => void;
  onAdded: () => void;
}

// The form mounts only while open, so every open starts from an empty draft.
export function QuickAddDialog({ open, accounts, categories, onClose, onAdded }: QuickAddDialogProps) {
  const handleAdded = () => {
    onClose();
    onAdded();
  };
  return (
    <Dialog open={open} title="New Transaction" onClose={onClose}>
      <div className="tx-dialog-body">
        {open ? (
          <AddTransactionForm accounts={accounts} categories={categories} onCancel={onClose} onAdded={handleAdded} />
        ) : null}
      </div>
    </Dialog>
  );
}

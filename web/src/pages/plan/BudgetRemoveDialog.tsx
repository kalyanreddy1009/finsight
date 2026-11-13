import { useState } from "react";
import { deleteBudget } from "../../api/budgets";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { errorText } from "./planFormat";

interface BudgetRemoveDialogProps {
  open: boolean;
  month: string;
  monthName: string;
  onClose: () => void;
  onRemoved: () => void;
}

export function BudgetRemoveDialog({ open, month, monthName, onClose, onRemoved }: BudgetRemoveDialogProps) {
  return (
    <Dialog open={open} title="Remove Budget" onClose={onClose}>
      {open ? <RemoveBudgetForm month={month} monthName={monthName} onCancel={onClose} onRemoved={onRemoved} /> : null}
    </Dialog>
  );
}

interface RemoveBudgetFormProps {
  month: string;
  monthName: string;
  onCancel: () => void;
  onRemoved: () => void;
}

function RemoveBudgetForm({ month, monthName, onCancel, onRemoved }: RemoveBudgetFormProps) {
  const [removing, setRemoving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleRemove() {
    setRemoving(true);
    setServerError(null);
    try {
      await deleteBudget(month);
      onRemoved();
    } catch (error) {
      setServerError(errorText(error, "Could not remove the budget. Try again."));
      setRemoving(false);
    }
  }

  return (
    <div className="form-stack">
      <p>Remove the budget for {monthName}? Spending is still tracked. Your category limits are deleted.</p>
      {serverError ? (
        <p className="field-error" role="alert">
          {serverError}
        </p>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={removing}>
          Keep Budget
        </Button>
        <Button variant="secondary" className="plan-danger" onClick={() => void handleRemove()} disabled={removing}>
          {removing ? "Removing…" : "Yes, Remove Budget"}
        </Button>
      </div>
    </div>
  );
}

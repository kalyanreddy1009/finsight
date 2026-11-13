import { useState } from "react";
import { getBudget, type BudgetResponse } from "../../api/budgets";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { LoadError } from "../../components/LoadError";
import { useLoader } from "../../hooks/useLoader";
import { BudgetDialog } from "./BudgetDialog";
import { BudgetRemoveDialog } from "./BudgetRemoveDialog";
import { BudgetSummary } from "./BudgetSummary";
import { monthLabel } from "./planFormat";

type BudgetDialogMode = "edit" | "remove" | null;

interface BudgetBodyProps {
  month: string;
  categories: readonly Category[] | null;
}

// Loads one month's budget and owns its dialogs. Mounted per month via key.
export function BudgetBody({ month, categories }: BudgetBodyProps) {
  const loader = useLoader(() => getBudget(month));
  const [dialog, setDialog] = useState<BudgetDialogMode>(null);
  const state = loader.state;
  if (state.status === "loading") {
    return (
      <p className="empty-state" role="status">
        Loading budget…
      </p>
    );
  }
  if (state.status === "error") {
    return <LoadError message="Could not load this budget. Check your connection and try again." onRetry={loader.reload} />;
  }
  const budget = state.data.budget;
  const monthName = monthLabel(month);

  function handleSaved(response: BudgetResponse) {
    loader.update(() => response);
    setDialog(null);
  }

  function handleRemoved() {
    loader.update(() => ({ month, budget: null }));
    setDialog(null);
  }

  // Editing needs the spending categories so that no existing category limit is dropped on save.
  const canEdit = categories !== null;
  return (
    <>
      {budget === null ? (
        <EmptyBudget monthName={monthName} canEdit={canEdit} onSet={() => setDialog("edit")} />
      ) : (
        <BudgetSummary
          budget={budget}
          canEdit={canEdit}
          onEdit={() => setDialog("edit")}
          onRemove={() => setDialog("remove")}
        />
      )}
      {canEdit ? null : <p className="field-hint">Categories are still loading.</p>}
      <BudgetDialog
        open={dialog === "edit"}
        month={month}
        budget={budget}
        categories={categories}
        onClose={() => setDialog(null)}
        onSaved={handleSaved}
      />
      <BudgetRemoveDialog
        open={dialog === "remove"}
        month={month}
        monthName={monthName}
        onClose={() => setDialog(null)}
        onRemoved={handleRemoved}
      />
    </>
  );
}

function EmptyBudget({ monthName, canEdit, onSet }: { monthName: string; canEdit: boolean; onSet: () => void }) {
  return (
    <div className="empty-block">
      <p className="empty-state">No budget for {monthName} yet. Set a total limit to see how much you have spent.</p>
      <Button onClick={onSet} disabled={!canEdit}>
        Set Budget
      </Button>
    </div>
  );
}

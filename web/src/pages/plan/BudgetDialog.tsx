import { useState, type FormEvent } from "react";
import { saveBudget, type Budget, type BudgetResponse } from "../../api/budgets";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field } from "../../components/Field";
import { useReportBusy } from "../../hooks/useReportBusy";
import {
  budgetFormFor,
  expenseCategoriesOf,
  validateBudgetForm,
  type BudgetFormErrors,
  type BudgetFormValues,
} from "./budgetForm";
import { errorText } from "./planFormat";

interface BudgetDialogProps {
  open: boolean;
  month: string;
  budget: Budget | null;
  categories: readonly Category[] | null;
  onClose: () => void;
  onSaved: (response: BudgetResponse) => void;
}

export function BudgetDialog({ open, month, budget, categories, onClose, onSaved }: BudgetDialogProps) {
  const title = budget === null ? "Set Budget" : "Edit Budget";
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} title={title} onClose={onClose} busy={busy}>
      {open ? (
        <BudgetForm
          month={month}
          budget={budget}
          categories={categories}
          onCancel={onClose}
          onSaved={onSaved}
          onBusyChange={setBusy}
        />
      ) : null}
    </Dialog>
  );
}

interface BudgetFormProps {
  month: string;
  budget: Budget | null;
  categories: readonly Category[] | null;
  onCancel: () => void;
  onSaved: (response: BudgetResponse) => void;
  onBusyChange: (busy: boolean) => void;
}

const NO_ERRORS: BudgetFormErrors = { totalError: null, categoryErrors: {} };

// Mounted only while the dialog is open, so every opening starts from the saved budget.
function BudgetForm({ month, budget, categories, onCancel, onSaved, onBusyChange }: BudgetFormProps) {
  const expenses = expenseCategoriesOf(categories ?? []);
  const [values, setValues] = useState<BudgetFormValues>(() => budgetFormFor(budget, expenses));
  const [errors, setErrors] = useState<BudgetFormErrors>(NO_ERRORS);
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useReportBusy(saving, onBusyChange);

  function setTotal(total: string) {
    setValues((previous) => ({ ...previous, total }));
  }

  function setCategoryLimit(categoryId: string, text: string) {
    setValues((previous) => ({ ...previous, categories: { ...previous.categories, [categoryId]: text } }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Without the loaded categories a save would drop their limits, so it is refused.
    if (categories === null) {
      return;
    }
    const result = validateBudgetForm(values, expenses, budget?.categories ?? []);
    setErrors({ totalError: result.totalError, categoryErrors: result.categoryErrors });
    setServerError(null);
    if (result.body === null) {
      return;
    }
    setSaving(true);
    try {
      onSaved(await saveBudget(month, result.body));
    } catch (error) {
      setServerError(errorText(error, "Could not save. Try again."));
      setSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <Field
        id="budget-total"
        label="Total limit (₹)"
        inputMode="decimal"
        autoComplete="off"
        value={values.total}
        disabled={saving}
        error={errors.totalError ?? undefined}
        onChange={(event) => setTotal(event.target.value)}
      />
      <fieldset className="plan-fieldset">
        <legend>Category limits (optional)</legend>
        {categories === null ? <p className="field-hint">Categories are still loading.</p> : null}
        {categories !== null && expenses.length === 0 ? <p className="field-hint">No spending categories yet.</p> : null}
        {expenses.length > 0 ? <p className="field-hint">Leave a category blank for no limit.</p> : null}
        {expenses.map((category) => (
          <Field
            key={category.id}
            id={`budget-category-${category.id}`}
            label={`${category.name} limit (₹)`}
            inputMode="decimal"
            autoComplete="off"
            value={values.categories[category.id] ?? ""}
            disabled={saving}
            error={errors.categoryErrors[category.id]}
            onChange={(event) => setCategoryLimit(category.id, event.target.value)}
          />
        ))}
      </fieldset>
      {serverError ? (
        <p className="field-error" role="alert">
          {serverError}
        </p>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving || categories === null}>
          {saving ? "Saving…" : "Save Budget"}
        </Button>
      </div>
    </form>
  );
}

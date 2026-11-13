import { useState, type FormEvent } from "react";
import { createRecurring, type RecurringFrequency, type RecurringRule } from "../../api/recurring";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field } from "../../components/Field";
import { SelectField } from "../../components/SelectField";
import { todayIso } from "../accounts/format";
import { expenseCategoriesOf } from "./budgetForm";
import { emptyBillForm, validateBillForm, type BillFormErrors, type BillFormValues } from "./billForm";
import { FREQUENCY_OPTIONS, errorText } from "./planFormat";

interface BillDialogProps {
  open: boolean;
  categories: readonly Category[] | null;
  onClose: () => void;
  onCreated: (rule: RecurringRule) => void;
}

export function BillDialog({ open, categories, onClose, onCreated }: BillDialogProps) {
  return (
    <Dialog open={open} title="Add Bill" onClose={onClose}>
      {open ? <BillForm categories={categories} onCancel={onClose} onCreated={onCreated} /> : null}
    </Dialog>
  );
}

interface BillFormProps {
  categories: readonly Category[] | null;
  onCancel: () => void;
  onCreated: (rule: RecurringRule) => void;
}

// Mounted only while the dialog is open, so every opening starts from an empty form.
function BillForm({ categories, onCancel, onCreated }: BillFormProps) {
  const expenses = expenseCategoriesOf(categories ?? []);
  const [values, setValues] = useState<BillFormValues>(() => emptyBillForm("", todayIso()));
  const [errors, setErrors] = useState<BillFormErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function update(patch: Partial<BillFormValues>) {
    setValues((previous) => ({ ...previous, ...patch }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateBillForm(values);
    setErrors(result.errors);
    setServerError(null);
    if (result.body === null) {
      return;
    }
    setSaving(true);
    try {
      onCreated(await createRecurring(result.body));
    } catch (error) {
      setServerError(errorText(error, "Could not save. Try again."));
      setSaving(false);
    }
  }

  const categoryOptions = expenses.map((category) => ({ value: category.id, label: category.name }));
  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <Field
        id="bill-merchant"
        label="Merchant"
        autoComplete="off"
        value={values.merchant}
        disabled={saving}
        error={errors.merchant}
        onChange={(event) => update({ merchant: event.target.value })}
      />
      <Field
        id="bill-amount"
        label="Amount (₹)"
        inputMode="decimal"
        autoComplete="off"
        value={values.amount}
        disabled={saving}
        error={errors.amount}
        onChange={(event) => update({ amount: event.target.value })}
      />
      <SelectField
        id="bill-category"
        label="Category"
        placeholder="Choose a category"
        value={values.categoryId}
        options={categoryOptions}
        hint={categories === null ? "Categories are still loading." : undefined}
        error={errors.category}
        disabled={saving}
        onChange={(event) => update({ categoryId: event.target.value })}
      />
      <SelectField
        id="bill-frequency"
        label="Frequency"
        value={values.frequency}
        options={FREQUENCY_OPTIONS}
        disabled={saving}
        onChange={(event) => update({ frequency: event.target.value as RecurringFrequency })}
      />
      <Field
        id="bill-next-date"
        label="Next due date"
        type="date"
        value={values.nextDate}
        disabled={saving}
        error={errors.nextDate}
        onChange={(event) => update({ nextDate: event.target.value })}
      />
      <label className="check-row">
        <input
          type="checkbox"
          checked={values.mandatory}
          disabled={saving}
          onChange={(event) => update({ mandatory: event.target.checked })}
        />
        Mandatory
      </label>
      {serverError ? (
        <p className="field-error" role="alert">
          {serverError}
        </p>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving}>
          {saving ? "Adding…" : "Add Bill"}
        </Button>
      </div>
    </form>
  );
}

import { useState, type FormEvent } from "react";
import { createCategory } from "../../api/categories";
import type { TaxSection } from "../../api/types";
import { Button } from "../../components/Button";
import { Dialog } from "../../components/Dialog";
import { Field } from "../../components/Field";
import { SelectField } from "../../components/SelectField";
import { messageFor } from "../accounts/format";
import {
  CATEGORY_TYPE_OPTIONS,
  EMPTY_CATEGORY_FORM,
  NAME_MAX_LENGTH,
  TAX_SECTION_OPTIONS,
  validateCategoryForm,
  type CategoryFormValues,
  type CategoryType,
} from "./categoryForm";

interface AddCategoryDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function AddCategoryDialog({ open, onClose, onCreated }: AddCategoryDialogProps) {
  return (
    <Dialog open={open} title="Add Category" onClose={onClose}>
      {open ? <AddCategoryForm onCancel={onClose} onCreated={onCreated} /> : null}
    </Dialog>
  );
}

interface AddCategoryFormProps {
  onCancel: () => void;
  onCreated: () => void;
}

// Mounted only while the dialog is open, so every opening starts from an empty form.
function AddCategoryForm({ onCancel, onCreated }: AddCategoryFormProps) {
  const [values, setValues] = useState<CategoryFormValues>(EMPTY_CATEGORY_FORM);
  const [nameError, setNameError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function update(patch: Partial<CategoryFormValues>) {
    setValues((previous) => ({ ...previous, ...patch }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateCategoryForm(values);
    setNameError(result.nameError);
    setServerError(null);
    if (result.body === null) {
      return;
    }
    setSaving(true);
    try {
      await createCategory(result.body);
      onCreated();
    } catch (error) {
      setServerError(messageFor(error));
      setSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <Field
        id="category-name"
        label="Name"
        required
        maxLength={NAME_MAX_LENGTH}
        autoComplete="off"
        value={values.name}
        disabled={saving}
        error={nameError ?? undefined}
        onChange={(event) => update({ name: event.target.value })}
      />
      <SelectField
        id="category-type"
        label="Type"
        value={values.type}
        options={CATEGORY_TYPE_OPTIONS}
        disabled={saving}
        onChange={(event) => update({ type: event.target.value as CategoryType })}
      />
      <SelectField
        id="category-tax"
        label="Tax section"
        value={values.taxSection}
        options={TAX_SECTION_OPTIONS}
        disabled={saving}
        onChange={(event) => update({ taxSection: event.target.value as TaxSection })}
      />
      {values.type === "EXPENSE" ? (
        <label className="check-row">
          <input
            type="checkbox"
            checked={values.essential}
            disabled={saving}
            onChange={(event) => update({ essential: event.target.checked })}
          />
          Essential spending
        </label>
      ) : null}
      <label className="check-row">
        <input
          type="checkbox"
          checked={values.privateToAi}
          disabled={saving}
          onChange={(event) => update({ privateToAi: event.target.checked })}
        />
        Keep private from AI summaries
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
          {saving ? "Adding…" : "Add Category"}
        </Button>
      </div>
    </form>
  );
}

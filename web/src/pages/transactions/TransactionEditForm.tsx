import { useState, type FormEvent } from "react";
import { getTransaction, patchTransaction, type TransactionPatch } from "../../api/transactions";
import type { Category, TaxSection, Transaction } from "../../api/types";
import { Button } from "../../components/Button";
import { SelectField, TextareaField } from "./FormControls";
import { describeError, hasErrorCode } from "./transactionErrors";
import { TAX_SECTIONS, parseTaxSection, taxSectionLabel } from "./transactionLabels";

export const CONFLICT_MESSAGE = "This transaction changed elsewhere. Reload to see the latest.";

interface EditDraft {
  categoryId: string;
  taxSection: TaxSection;
  notes: string;
}

// Only changed fields are sent. An empty category is never sent because the API cannot clear it.
export function buildPatch(transaction: Transaction, draft: EditDraft): TransactionPatch {
  const patch: TransactionPatch = {};
  if (draft.categoryId !== "" && draft.categoryId !== (transaction.category_id ?? "")) {
    patch.category_id = draft.categoryId;
  }
  if (draft.taxSection !== transaction.tax_section) {
    patch.tax_section = draft.taxSection;
  }
  if (draft.notes !== (transaction.notes ?? "")) {
    patch.notes = draft.notes;
  }
  return patch;
}

interface TransactionEditFormProps {
  transaction: Transaction;
  categories: readonly Category[];
  onSaved: (transaction: Transaction) => void;
}

const TAX_OPTIONS = TAX_SECTIONS.map((section) => ({ value: section, label: taxSectionLabel(section) }));

export function TransactionEditForm({ transaction, categories, onSaved }: TransactionEditFormProps) {
  const [draft, setDraft] = useState<EditDraft>({
    categoryId: transaction.category_id ?? "",
    taxSection: transaction.tax_section,
    notes: transaction.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = buildPatch(transaction, draft);
  const canSave = Object.keys(patch).length > 0 && !saving && !conflict;
  const categoryOptions = categories.map((category) => ({ value: category.id, label: category.name }));

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onSaved(await patchTransaction(transaction.id, transaction.version, patch));
    } catch (failure) {
      setSaving(false);
      if (hasErrorCode(failure, "VERSION_CONFLICT")) {
        setConflict(true);
      } else {
        setError(describeError(failure));
      }
    }
  }

  async function handleReload() {
    setReloading(true);
    try {
      onSaved(await getTransaction(transaction.id));
    } catch (failure) {
      setReloading(false);
      setError(describeError(failure));
    }
  }

  return (
    <form className="form-stack" onSubmit={handleSave}>
      {conflict ? (
        <div className="card notice" role="alert">
          <p>{CONFLICT_MESSAGE}</p>
          <Button variant="secondary" onClick={handleReload} disabled={reloading}>
            {reloading ? "Reloading…" : "Reload"}
          </Button>
        </div>
      ) : null}
      <SelectField
        id="tx-detail-category"
        label="Category"
        value={draft.categoryId}
        options={categoryOptions}
        placeholder={transaction.category_id === null ? "No category" : undefined}
        onChange={(categoryId) => setDraft((current) => ({ ...current, categoryId }))}
      />
      <SelectField
        id="tx-detail-tax"
        label="Tax section"
        value={draft.taxSection}
        options={TAX_OPTIONS}
        onChange={(value) => {
          const section = parseTaxSection(value);
          if (section !== null) {
            setDraft((current) => ({ ...current, taxSection: section }));
          }
        }}
      />
      <TextareaField
        id="tx-detail-notes"
        label="Notes"
        value={draft.notes}
        maxLength={2000}
        onChange={(notes) => setDraft((current) => ({ ...current, notes }))}
      />
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="tx-action-row">
        <Button variant="primary" type="submit" disabled={!canSave}>
          {saving ? "Saving…" : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}

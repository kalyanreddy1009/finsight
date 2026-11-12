import { useRef, useState, type FormEvent } from "react";
import { createTransaction } from "../../api/transactions";
import type { Account, Category } from "../../api/types";
import { Button } from "../../components/Button";
import { Field } from "../../components/Field";
import { parseRupeesToMinor } from "../../lib/money";
import { SelectField } from "../../components/SelectField";
import { KindSwitch } from "./KindSwitch";
import { SplitSection } from "./SplitSection";
import { describeError } from "./transactionErrors";
import {
  KIND_LABELS,
  emptyDraft,
  toIsoDate,
  validateDraft,
  type EntryDraft,
  type EntryErrors,
  type EntryKind,
} from "./transactionForm";

interface AddTransactionFormProps {
  accounts: readonly Account[];
  categories: readonly Category[];
  onCancel: () => void;
  onAdded: () => void;
}

export function AddTransactionForm({ accounts, categories, onCancel, onAdded }: AddTransactionFormProps) {
  const [draft, setDraft] = useState<EntryDraft>(() => emptyDraft(toIsoDate(new Date())));
  const [errors, setErrors] = useState<EntryErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // One key per attempt-until-success, so a retry after a lost response cannot duplicate the entry.
  const idempotencyKey = useRef(crypto.randomUUID());

  const accountOptions = accounts
    .filter((account) => account.is_active)
    .map((account) => ({ value: account.id, label: account.name }));
  const categoryType = draft.kind === "income" ? "INCOME" : "EXPENSE";
  const categoryOptions = categories
    .filter((category) => category.category_type === categoryType)
    .map((category) => ({ value: category.id, label: category.name }));
  const totalMinor = parseRupeesToMinor(draft.amount);

  const update = (patch: Partial<EntryDraft>) => setDraft((current) => ({ ...current, ...patch }));

  function changeKind(kind: EntryKind) {
    update({ kind, categoryId: "" });
    setErrors({});
    setSubmitError(null);
  }

  function checkAmountOnBlur() {
    setErrors((previous) => ({ ...previous, amount: validateDraft(draft).errors.amount }));
  }

  function checkDateOnBlur() {
    setErrors((previous) => ({ ...previous, date: validateDraft(draft).errors.date }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateDraft(draft);
    setErrors(result.errors);
    setSubmitError(null);
    if (result.body === null) {
      return;
    }
    setSubmitting(true);
    try {
      await createTransaction(result.body, idempotencyKey.current);
      idempotencyKey.current = crypto.randomUUID();
      onAdded();
    } catch (failure) {
      setSubmitError(describeError(failure));
      setSubmitting(false);
    }
  }

  const isTransfer = draft.kind === "transfer";
  const label = KIND_LABELS[draft.kind];

  return (
    <form className="form-stack" onSubmit={handleSubmit} noValidate>
      <KindSwitch value={draft.kind} onChange={changeKind} />
      <Field
        id="tx-add-amount"
        label="Amount (₹)"
        inputMode="decimal"
        autoComplete="off"
        hint="Enter rupees, for example 450 or 1,250.50."
        value={draft.amount}
        error={errors.amount}
        onChange={(event) => update({ amount: event.target.value })}
        onBlur={checkAmountOnBlur}
      />
      <Field
        id="tx-add-date"
        type="date"
        label="Date"
        value={draft.date}
        error={errors.date}
        onChange={(event) => update({ date: event.target.value })}
        onBlur={checkDateOnBlur}
      />
      {isTransfer ? (
        <>
          <SelectField
            id="tx-add-from"
            label="From account"
            value={draft.accountId}
            options={accountOptions}
            placeholder="Choose an account"
            error={errors.accountId}
            onChange={(event) => update({ accountId: event.target.value })}
          />
          <SelectField
            id="tx-add-to"
            label="To account"
            value={draft.toAccountId}
            options={accountOptions}
            placeholder="Choose an account"
            error={errors.toAccountId}
            onChange={(event) => update({ toAccountId: event.target.value })}
          />
        </>
      ) : (
        <>
          <SelectField
            id="tx-add-account"
            label="Account"
            value={draft.accountId}
            options={accountOptions}
            placeholder="Choose an account"
            error={errors.accountId}
            onChange={(event) => update({ accountId: event.target.value })}
          />
          <SelectField
            id="tx-add-category"
            label="Category"
            value={draft.categoryId}
            options={categoryOptions}
            placeholder="Choose a category"
            error={errors.categoryId}
            onChange={(event) => update({ categoryId: event.target.value })}
          />
        </>
      )}
      <Field
        id="tx-add-description"
        label="Description (optional)"
        autoComplete="off"
        value={draft.description}
        onChange={(event) => update({ description: event.target.value })}
      />
      {draft.kind === "expense" ? (
        <SplitSection
          rows={draft.splits}
          totalMinor={totalMinor}
          error={errors.splits}
          onChange={(splits) => update({ splits })}
        />
      ) : null}
      {submitError ? (
        <p className="field-error" role="alert">
          {submitError}
        </p>
      ) : null}
      <div className="tx-action-row">
        <Button variant="primary" type="submit" disabled={submitting}>
          {submitting ? "Adding…" : `Add ${label}`}
        </Button>
        <Button variant="plain" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

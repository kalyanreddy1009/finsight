import { useRef, useState, type FormEvent } from "react";
import { settleSplit, type Split } from "../../api/splits";
import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { Field } from "../../components/Field";
import { formatMinor } from "../../lib/money";
import { Dialog } from "../../components/Dialog";
import { SelectField } from "../../components/SelectField";
import { messageFor, minorToRupeesText, todayIso } from "./format";
import { validateRepayment, type RepaymentErrors, type RepaymentValues } from "./repaymentForm";

interface RepaymentDialogProps {
  split: Split | null;
  bankAccounts: readonly Account[];
  onClose: () => void;
  onSettled: () => void;
}

export function RepaymentDialog({ split, bankAccounts, onClose, onSettled }: RepaymentDialogProps) {
  return (
    <Dialog open={split !== null} title="Record Repayment" onClose={onClose}>
      {split !== null ? (
        <RepaymentForm split={split} bankAccounts={bankAccounts} onCancel={onClose} onSettled={onSettled} />
      ) : null}
    </Dialog>
  );
}

interface RepaymentFormProps {
  split: Split;
  bankAccounts: readonly Account[];
  onCancel: () => void;
  onSettled: () => void;
}

function RepaymentForm({ split, bankAccounts, onCancel, onSettled }: RepaymentFormProps) {
  const [values, setValues] = useState<RepaymentValues>({
    amountText: minorToRupeesText(split.outstanding_minor),
    bankAccountId: bankAccounts[0]?.id ?? "",
    date: todayIso(),
  });
  const [errors, setErrors] = useState<RepaymentErrors>({});
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const idempotencyKey = useRef(crypto.randomUUID());
  const noBankAccount = bankAccounts.length === 0;

  function setField<K extends keyof RepaymentValues>(key: K, value: RepaymentValues[K]) {
    setValues((previous) => ({ ...previous, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateRepayment(values, split.outstanding_minor);
    setErrors(result.errors);
    const body = result.body;
    if (body === null) {
      return;
    }
    setSaving(true);
    setServerError(null);
    try {
      await settleSplit(split.id, body, idempotencyKey.current);
      idempotencyKey.current = crypto.randomUUID();
      onSettled();
    } catch (error) {
      setServerError(messageFor(error));
      setSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <p className="empty-state">
        {split.counterparty_name} owes {formatMinor(split.outstanding_minor)}
      </p>
      <Field
        id="repay-amount"
        label="Amount (₹)"
        inputMode="decimal"
        hint={`Up to ${formatMinor(split.outstanding_minor)}`}
        value={values.amountText}
        disabled={saving}
        error={errors.amount}
        onChange={(event) => setField("amountText", event.target.value)}
      />
      <SelectField
        id="repay-bank-account"
        label="Received in"
        hint={noBankAccount ? "Add a bank or cash account first." : undefined}
        value={values.bankAccountId}
        disabled={saving || noBankAccount}
        error={errors.bankAccountId}
        onChange={(event) => setField("bankAccountId", event.target.value)}
      >
        <option value="" disabled>
          Choose an account
        </option>
        {bankAccounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </SelectField>
      <Field
        id="repay-date"
        label="Date"
        type="date"
        value={values.date}
        disabled={saving}
        error={errors.date}
        onChange={(event) => setField("date", event.target.value)}
      />
      {serverError ? (
        <p className="field-error" role="alert">
          {serverError}
        </p>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={saving || noBankAccount}>
          {saving ? "Recording…" : "Record Repayment"}
        </Button>
      </div>
    </form>
  );
}

import { useState, type FormEvent } from "react";
import { createAccount } from "../../api/accounts";
import type { UserAccountSubtype } from "../../api/types";
import { Button } from "../../components/Button";
import { AccountFormFields } from "./AccountFormFields";
import { Dialog } from "../../components/Dialog";
import { EMPTY_ACCOUNT_FORM, validateAccountForm, type AccountFormErrors, type AccountFormValues, type AccountTextField } from "./accountForm";
import { messageFor } from "./format";
import { useReportBusy } from "../../hooks/useReportBusy";

interface AddAccountDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function AddAccountDialog({ open, onClose, onCreated }: AddAccountDialogProps) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} title="Add Account" onClose={onClose} busy={busy}>
      {open ? <AddAccountForm onCancel={onClose} onCreated={onCreated} onBusyChange={setBusy} /> : null}
    </Dialog>
  );
}

interface AddAccountFormProps {
  onCancel: () => void;
  onCreated: () => void;
  onBusyChange: (busy: boolean) => void;
}

// Mounted only while the dialog is open, so every opening starts from an empty form.
function AddAccountForm({ onCancel, onCreated, onBusyChange }: AddAccountFormProps) {
  const [values, setValues] = useState<AccountFormValues>(EMPTY_ACCOUNT_FORM);
  const [errors, setErrors] = useState<AccountFormErrors>({});
  const [saving, setSaving] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  useReportBusy(saving, onBusyChange);

  function setText(key: AccountTextField, value: string) {
    setValues((previous) => ({ ...previous, [key]: value }));
  }

  function setSubtype(subtype: UserAccountSubtype) {
    setValues((previous) => ({ ...previous, subtype }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateAccountForm(values);
    setErrors(result.errors);
    const body = result.body;
    if (body === null) {
      return;
    }
    setSaving(true);
    setServerError(null);
    try {
      await createAccount(body);
      onCreated();
    } catch (error) {
      setServerError(messageFor(error));
      setSaving(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <AccountFormFields values={values} errors={errors} saving={saving} onText={setText} onSubtype={setSubtype} />
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
          {saving ? "Adding…" : "Add Account"}
        </Button>
      </div>
    </form>
  );
}

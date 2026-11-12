import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { uploadStatement, type StatementKind } from "../../api/statements";
import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { AppDialog } from "./AppDialog";
import { SelectField } from "./SelectField";
import { uploadFailure, type UploadFailure } from "./uploadErrors";

const CSV_KIND: StatementKind = "CSV";
const CSV_NAME = /\.csv$/i;

interface UploadStatementDialogProps {
  open: boolean;
  accounts: readonly Account[];
  onClose: () => void;
  onUploaded: (statementId: string) => void;
}

export function UploadStatementDialog({ open, accounts, onClose, onUploaded }: UploadStatementDialogProps) {
  return (
    <AppDialog open={open} title="Upload Statement" onClose={onClose}>
      {open ? <UploadForm accounts={accounts} onCancel={onClose} onUploaded={onUploaded} /> : null}
    </AppDialog>
  );
}

interface UploadFormProps {
  accounts: readonly Account[];
  onCancel: () => void;
  onUploaded: (statementId: string) => void;
}

interface UploadErrors {
  account?: string;
  file?: string;
}

function UploadForm({ accounts, onCancel, onUploaded }: UploadFormProps) {
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<UploadErrors>({});
  const [uploading, setUploading] = useState(false);
  const [failure, setFailure] = useState<UploadFailure | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: UploadErrors = {};
    if (accountId === "") {
      nextErrors.account = "Choose the account this statement belongs to.";
    }
    if (file === null) {
      nextErrors.file = "Choose a CSV file to upload.";
    } else if (!CSV_NAME.test(file.name)) {
      nextErrors.file = "Choose a file that ends in .csv.";
    }
    setErrors(nextErrors);
    if (file === null || nextErrors.account !== undefined || nextErrors.file !== undefined) {
      return;
    }
    setUploading(true);
    setFailure(null);
    try {
      const result = await uploadStatement(file, accountId, CSV_KIND);
      onUploaded(result.statement_id);
    } catch (error) {
      setFailure(uploadFailure(error));
      setUploading(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={(event) => void handleSubmit(event)} noValidate>
      <SelectField
        id="upload-account"
        label="Account"
        hint={accounts.length === 0 ? "Add an account first." : undefined}
        value={accountId}
        disabled={uploading}
        error={errors.account}
        onChange={(event) => setAccountId(event.target.value)}
      >
        <option value="" disabled>
          Choose an account
        </option>
        {accounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.name}
          </option>
        ))}
      </SelectField>
      <SelectField
        id="upload-kind"
        label="Statement type"
        defaultValue={CSV_KIND}
        hint="PDF statements are not supported yet."
        disabled={uploading}
      >
        <option value="CSV">CSV file</option>
        <option value="BANK_PDF" disabled>
          Bank statement (PDF)
        </option>
        <option value="CARD_PDF" disabled>
          Card statement (PDF)
        </option>
        <option value="CAS_PDF" disabled>
          CAS statement (PDF)
        </option>
      </SelectField>
      <div className="field">
        <label htmlFor="upload-file">Statement file (CSV)</label>
        <input
          id="upload-file"
          className="field-input file-input"
          type="file"
          accept=".csv,text/csv"
          disabled={uploading}
          aria-invalid={errors.file ? true : undefined}
          aria-describedby={errors.file ? "upload-file-error" : undefined}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        {errors.file ? (
          <p id="upload-file-error" className="field-error" role="alert">
            {errors.file}
          </p>
        ) : null}
      </div>
      {failure ? (
        <div className="card notice" role="alert">
          <p>{failure.message}</p>
          {failure.statementId ? (
            <Link className="btn btn-plain" to={`?statement=${encodeURIComponent(failure.statementId)}`}>
              View its review
            </Link>
          ) : null}
        </div>
      ) : null}
      <div className="dialog-actions">
        <Button variant="plain" onClick={onCancel} disabled={uploading}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={uploading || accounts.length === 0}>
          {uploading ? "Uploading…" : "Upload"}
        </Button>
      </div>
    </form>
  );
}

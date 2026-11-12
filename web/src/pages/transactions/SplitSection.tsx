import { formatMinor } from "../../lib/money";
import { Button } from "../../components/Button";
import { Field } from "../../components/Field";
import { newSplitRow, yourShareMinor, type SplitRowDraft } from "./transactionForm";

interface SplitSectionProps {
  rows: SplitRowDraft[];
  totalMinor: number | null;
  error?: string;
  onChange: (rows: SplitRowDraft[]) => void;
}

// Optional expense split. The share is what remains after the friends' amounts.
export function SplitSection({ rows, totalMinor, error, onChange }: SplitSectionProps) {
  const updateRow = (id: string, patch: Partial<SplitRowDraft>) =>
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const removeRow = (id: string) => onChange(rows.filter((row) => row.id !== id));

  return (
    <fieldset className="tx-split">
      <legend className="tx-split-title">Split with friends</legend>
      <p className="field-hint">Optional. Enter what each person owes you. The rest is your share.</p>
      {rows.map((row, index) => {
        const number = index + 1;
        return (
          <div className="tx-split-row" key={row.id}>
            <Field
              id={`tx-split-name-${row.id}`}
              label={`Person ${number} name`}
              value={row.name}
              onChange={(event) => updateRow(row.id, { name: event.target.value })}
            />
            <Field
              id={`tx-split-owed-${row.id}`}
              label={`Person ${number} owes (₹)`}
              inputMode="decimal"
              value={row.owed}
              onChange={(event) => updateRow(row.id, { owed: event.target.value })}
            />
            <Button variant="plain" aria-label={`Remove person ${number}`} onClick={() => removeRow(row.id)}>
              Remove
            </Button>
          </div>
        );
      })}
      <div className="tx-action-row">
        <Button variant="secondary" onClick={() => onChange([...rows, newSplitRow()])}>
          Add Person
        </Button>
      </div>
      {totalMinor !== null ? (
        <p className="tx-share" aria-live="polite">
          Your share: {formatMinor(yourShareMinor(totalMinor, rows))}
        </p>
      ) : null}
      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

import type { StatementImportError } from "../../api/statements";
import { formatMinor } from "../../lib/money";

interface ReconciliationWarningProps {
  difference: number | null;
  importErrors: readonly StatementImportError[];
}

// Shown when the statement does not reconcile or rows failed the running-balance check.
export function ReconciliationWarning({ difference, importErrors }: ReconciliationWarningProps) {
  const off = difference !== null && difference !== 0;
  return (
    <div className="card notice stmt-warning" role="alert">
      <h3 className="group-title">This statement needs a check</h3>
      {off ? (
        <p>
          The rows do not add up to the statement's closing balance. The difference is{" "}
          {formatMinor(Math.abs(difference))}. Check the rows below before you commit.
        </p>
      ) : null}
      {importErrors.length > 0 ? (
        <>
          <p>
            {importErrors.length === 1
              ? "One row could not be checked against the running balance:"
              : `${importErrors.length} rows could not be checked against the running balance:`}
          </p>
          <ol className="error-list">
            {importErrors.map((error) => (
              <li key={error.id}>
                {error.row_index === null ? "Unknown row" : `Row ${error.row_index}`}: {error.error_message}. Expected{" "}
                {minorOrDash(error.expected_running_balance_minor)}, statement states{" "}
                {minorOrDash(error.actual_running_balance_minor)}.
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </div>
  );
}

function minorOrDash(minor: number | null): string {
  return minor === null ? "no balance" : formatMinor(minor);
}

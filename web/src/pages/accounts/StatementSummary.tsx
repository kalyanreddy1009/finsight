import type { Statement, StatementImportError, StatementRow } from "../../api/statements";
import { formatMinor } from "../../lib/money";
import { periodText } from "./format";
import { ReconciliationWarning } from "./ReconciliationWarning";

interface StatementSummaryProps {
  statement: Statement;
  rows: readonly StatementRow[];
  importErrors: readonly StatementImportError[];
}

export function StatementSummary({ statement, rows, importErrors }: StatementSummaryProps) {
  const pending = rows.filter((row) => row.row_status === "PENDING_REVIEW").length;
  const duplicates = rows.filter((row) => row.row_status === "DUPLICATE").length;
  const rejected = rows.filter((row) => row.row_status === "REJECTED").length;
  const difference = statement.reconciliation_diff_minor;
  const needsCheck = (difference !== null && difference !== 0) || importErrors.length > 0;
  return (
    <section className="card accounts-section" aria-labelledby="summary-heading">
      <h2 id="summary-heading" className="section-title">
        Summary
      </h2>
      <dl className="summary-list">
        <SummaryItem label="File" value={statement.original_filename} />
        <SummaryItem label="Period" value={periodText(statement.statement_start_date, statement.statement_end_date)} />
        <SummaryItem label="Opening balance" value={formatMinor(statement.opening_balance_minor)} />
        <SummaryItem label="Closing balance" value={formatMinor(statement.closing_balance_minor)} />
        <SummaryItem
          label="Rows"
          value={`${rows.length} in total, ${pending} pending, ${duplicates} duplicate, ${rejected} rejected`}
        />
        <SummaryItem label="Reconciliation" value={reconciliationText(difference)} />
      </dl>
      {needsCheck ? <ReconciliationWarning difference={difference} importErrors={importErrors} /> : null}
    </section>
  );
}

function reconciliationText(difference: number | null): string {
  if (difference === null) {
    return "Not checked yet";
  }
  if (difference === 0) {
    return "Matches the closing balance";
  }
  return `Differs by ${formatMinor(Math.abs(difference))}`;
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

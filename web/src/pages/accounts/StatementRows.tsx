import type { StatementRow } from "../../api/statements";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import type { RowActions } from "./useRowActions";
import { StatementRowItem } from "./StatementRowItem";

interface StatementRowsProps {
  rows: readonly StatementRow[];
  categories: readonly Category[];
  readOnly: boolean;
  actions: RowActions;
}

export function StatementRows({ rows, categories, readOnly, actions }: StatementRowsProps) {
  const pending = rows.filter((row) => row.row_status === "PENDING_REVIEW").length;
  const approving = actions.progress !== null;
  return (
    <section className="card accounts-section" aria-labelledby="rows-heading">
      <div className="section-header">
        <h2 id="rows-heading" className="section-title">
          Transactions ({rows.length})
        </h2>
        {readOnly ? null : (
          <Button
            onClick={() => void actions.approveAll(rows)}
            disabled={approving || pending === 0}
          >
            {approving ? "Approving…" : "Approve All Pending"}
          </Button>
        )}
      </div>
      {actions.progress ? (
        <p className="secondary-text" role="status">
          Approved {actions.progress.done} of {actions.progress.total}…
        </p>
      ) : null}
      {actions.error ? (
        <p className="field-error" role="alert">
          {actions.error}
        </p>
      ) : null}
      <ul className="row-list">
        {rows.map((row) => (
          <StatementRowItem key={row.id} row={row} categories={categories} readOnly={readOnly} actions={actions} />
        ))}
      </ul>
    </section>
  );
}

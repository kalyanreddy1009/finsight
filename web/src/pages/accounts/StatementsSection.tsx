import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listStatements, type Statement, type StatementProcessingStatus } from "../../api/statements";
import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { LoadError } from "../../components/LoadError";
import { periodText } from "./format";
import { UploadStatementDialog } from "./UploadStatementDialog";
import { useLoader, type LoadState } from "../../hooks/useLoader";

const STATUS_LABELS: Record<StatementProcessingStatus, string> = {
  UPLOADED: "Uploaded",
  PARSING: "Reading file",
  REVIEW_REQUIRED: "Ready to review",
  APPROVED: "Committed",
  FAILED: "Failed",
};

interface StatementsSectionProps {
  accounts: readonly Account[];
}

export function StatementsSection({ accounts }: StatementsSectionProps) {
  const navigate = useNavigate();
  const [uploadOpen, setUploadOpen] = useState(false);
  const statements = useLoader(() => listStatements());
  return (
    <section className="accounts-section" aria-labelledby="statements-heading">
      <div className="section-header">
        <h2 id="statements-heading" className="section-title">
          Statements
        </h2>
        <Button onClick={() => setUploadOpen(true)}>Upload Statement</Button>
      </div>
      <StatementList state={statements.state} onRetry={statements.reload} />
      <UploadStatementDialog
        open={uploadOpen}
        accounts={accounts}
        onClose={() => setUploadOpen(false)}
        onUploaded={(statementId) => navigate(`?statement=${encodeURIComponent(statementId)}`)}
      />
    </section>
  );
}

interface StatementListProps {
  state: LoadState<Statement[]>;
  onRetry: () => void;
}

function StatementList({ state, onRetry }: StatementListProps) {
  if (state.status === "loading") {
    return (
      <p className="empty-state" role="status">
        Loading statements…
      </p>
    );
  }
  if (state.status === "error") {
    return <LoadError message="Could not load statements. Check your connection and try again." onRetry={onRetry} />;
  }
  if (state.data.length === 0) {
    return <p className="empty-state">No statements uploaded yet. Upload a CSV statement to review its transactions.</p>;
  }
  return (
    <ul className="row-list">
      {state.data.map((statement) => (
        <li className="row statement-row" key={statement.id}>
          <div className="row-main">
            <span className="row-title">{statement.original_filename}</span>
            <span className="secondary-text">
              {periodText(statement.statement_start_date, statement.statement_end_date)}
            </span>
            <span className="status-text">{STATUS_LABELS[statement.processing_status]}</span>
          </div>
          <Link className="btn btn-plain" to={`?statement=${encodeURIComponent(statement.id)}`}>
            Review
          </Link>
        </li>
      ))}
    </ul>
  );
}

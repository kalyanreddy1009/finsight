import { Link } from "react-router-dom";
import { getStatementReview, listCategories } from "../../api/statements";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { CommitPanel } from "./CommitPanel";
import { LoadError } from "./LoadError";
import { StatementRows } from "./StatementRows";
import { StatementSummary } from "./StatementSummary";
import { useLoader } from "./useLoader";
import { useRowActions } from "./useRowActions";

interface StatementReviewViewProps {
  statementId: string;
}

export function StatementReviewView({ statementId }: StatementReviewViewProps) {
  useDocumentTitle("Statement review");
  const review = useLoader(() => getStatementReview(statementId));
  const categories = useLoader(listCategories);
  const rowActions = useRowActions(review.update);
  const state = review.state;
  const categoryList = categories.state.status === "ready" ? categories.state.data : [];
  return (
    <div className="accounts-page">
      <header className="page-header">
        <Link className="btn btn-plain" to=".">
          Back to Accounts
        </Link>
        <h1 className="title">Statement review</h1>
      </header>
      {state.status === "loading" ? (
        <p className="empty-state" role="status">
          Loading statement…
        </p>
      ) : null}
      {state.status === "error" ? (
        <LoadError message="Could not load this statement. Check your connection and try again." onRetry={review.reload} />
      ) : null}
      {state.status === "ready" ? (
        <>
          <StatementSummary
            statement={state.data.statement}
            rows={state.data.rows}
            importErrors={state.data.import_errors}
          />
          <StatementRows
            rows={state.data.rows}
            categories={categoryList}
            readOnly={state.data.statement.processing_status !== "REVIEW_REQUIRED"}
            actions={rowActions}
          />
          <CommitPanel
            statement={state.data.statement}
            rows={state.data.rows}
            onCommitted={() =>
              review.update((current) => ({
                ...current,
                statement: { ...current.statement, processing_status: "APPROVED" },
              }))
            }
          />
        </>
      ) : null}
    </div>
  );
}

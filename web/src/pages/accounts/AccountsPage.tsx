import { useSearchParams } from "react-router-dom";
import "../../styles/accounts.css";
import { AccountsOverview } from "./AccountsOverview";
import { StatementReviewView } from "./StatementReviewView";

// Accounts tab. ?statement=<id> switches to the statement review, so it survives a reload.
export function AccountsPage() {
  const [params] = useSearchParams();
  const statementId = params.get("statement");
  if (statementId !== null && statementId !== "") {
    return <StatementReviewView key={statementId} statementId={statementId} />;
  }
  return <AccountsOverview />;
}

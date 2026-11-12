import { useState } from "react";
import { listAccounts } from "../../api/accounts";
import { Button } from "../../components/Button";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { AccountsSection } from "./AccountsSection";
import { AddAccountDialog } from "./AddAccountDialog";
import { LoadError } from "../../components/LoadError";
import { SplitsSection } from "./SplitsSection";
import { StatementsSection } from "./StatementsSection";
import { useLoader } from "../../hooks/useLoader";

export function AccountsOverview() {
  useDocumentTitle("Accounts");
  const accounts = useLoader(listAccounts);
  const [addOpen, setAddOpen] = useState(false);
  const state = accounts.state;
  return (
    <div className="accounts-page">
      <header className="page-header">
        <h1 className="title">Accounts</h1>
        <Button variant="primary" onClick={() => setAddOpen(true)}>
          Add Account
        </Button>
      </header>
      {state.status === "loading" ? <OverviewSkeleton /> : null}
      {state.status === "error" ? (
        <LoadError message="Could not load your accounts. Check your connection and try again." onRetry={accounts.reload} />
      ) : null}
      {state.status === "ready" ? (
        <>
          <AccountsSection accounts={state.data} onAdd={() => setAddOpen(true)} />
          <SplitsSection accounts={state.data} />
          <StatementsSection accounts={state.data} />
        </>
      ) : null}
      <AddAccountDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => {
          setAddOpen(false);
          accounts.reload();
        }}
      />
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="skeleton-stack" aria-busy="true">
      <p className="visually-hidden" role="status">
        Loading your accounts
      </p>
      <div className="card skeleton-card" aria-hidden="true">
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
      </div>
    </div>
  );
}

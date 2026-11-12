import type { Account } from "../../api/types";
import { Button } from "../../components/Button";
import { AccountRow } from "./AccountRow";
import { groupAccounts } from "./accountOptions";

interface AccountsSectionProps {
  accounts: readonly Account[];
  onAdd: () => void;
}

export function AccountsSection({ accounts, onAdd }: AccountsSectionProps) {
  return (
    <section className="accounts-section" aria-labelledby="accounts-heading">
      <h2 id="accounts-heading" className="section-title">
        Accounts
      </h2>
      {accounts.length === 0 ? (
        <div className="card empty-block">
          <p className="empty-state">No accounts yet</p>
          <p className="empty-state">Add a bank, card or loan account to start tracking balances.</p>
          <Button onClick={onAdd}>Add Account</Button>
        </div>
      ) : (
        groupAccounts(accounts).map((group) => (
          <div className="account-group" key={group.title}>
            <h3 className="group-title">{group.title}</h3>
            <ul className="row-list">
              {group.accounts.map((account) => (
                <AccountRow key={account.id} account={account} />
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}

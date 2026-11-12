import type { Account } from "../../api/types";
import { balanceText, institutionOrType, utilisationFor } from "./accountOptions";

export function AccountRow({ account }: { account: Account }) {
  const utilisation = utilisationFor(account);
  return (
    <li className="row">
      <div className="row-main">
        <span className="row-title">{account.name}</span>
        <span className="secondary-text">{institutionOrType(account)}</span>
        {utilisation ? (
          <>
            <span className="secondary-text">{utilisation.text}</span>
            <div className="util-track" aria-hidden="true">
              <div className="util-fill" style={{ width: `${utilisation.barPercent}%` }} />
            </div>
          </>
        ) : null}
      </div>
      <span className="row-amount">{balanceText(account)}</span>
    </li>
  );
}

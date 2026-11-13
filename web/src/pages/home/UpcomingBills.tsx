import { Link } from "react-router-dom";
import type { UpcomingBill } from "../../api/types";
import { ChevronIcon } from "../../components/icons";
import { formatMinor } from "../../lib/money";

const DUE_DATE_FORMAT = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });

function formatDueDate(isoDate: string): string {
  return DUE_DATE_FORMAT.format(new Date(`${isoDate}T00:00:00Z`));
}

export function UpcomingBills({ bills }: { bills: UpcomingBill[] }) {
  return (
    <section className="card" aria-labelledby="upcoming-bills-heading">
      <h2 id="upcoming-bills-heading" className="eyebrow">
        Upcoming Bills
      </h2>
      {bills.length === 0 ? (
        <div className="empty-block">
          <p className="empty-state">No bills are due in the next week. Recurring bills appear here once they are recorded.</p>
          <Link to="/transactions" className="btn btn-secondary">
            Open Transactions
          </Link>
        </div>
      ) : (
        <ul className="row-list">
          {bills.map((bill) => (
            <li key={bill.id} className="row">
              <div className="row-main">
                <p className="headline">{bill.merchant_name}</p>
                <p className="footnote">Due {formatDueDate(bill.next_expected_date)}</p>
              </div>
              <p className="row-amount">{formatMinor(-bill.expected_amount_minor)}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ReviewRow({ pendingCount }: { pendingCount: number }) {
  const detail =
    pendingCount === 0
      ? "Nothing to review"
      : `${pendingCount} ${pendingCount === 1 ? "transaction" : "transactions"} to review`;
  return (
    <Link to="/transactions" className="card review-row">
      <span className="headline">Review</span>
      <span className="footnote">{detail}</span>
      <ChevronIcon className="row-chevron" />
    </Link>
  );
}

import { formatMinor } from "../../lib/money";

interface StatRowsProps {
  netWorthMinor: number;
  monthExpenseMinor: number;
  monthIncomeMinor: number;
}

const SPENDING_LABEL = "This Month's Spending";
const INCOME_LABEL = "This Month's Income";

export function StatRows({ netWorthMinor, monthExpenseMinor, monthIncomeMinor }: StatRowsProps) {
  return (
    <dl className="card stat-list">
      <div className="stat-row">
        <dt>Net Worth</dt>
        <dd>{formatMinor(netWorthMinor)}</dd>
      </div>
      <div className="stat-row">
        <dt>{SPENDING_LABEL}</dt>
        <dd>{formatMinor(monthExpenseMinor)}</dd>
      </div>
      <div className="stat-row">
        <dt>{INCOME_LABEL}</dt>
        <dd>{formatMinor(monthIncomeMinor)}</dd>
      </div>
    </dl>
  );
}

import { formatMinor } from "../../lib/money";

const BP_PER_PERCENT = 100;

interface KpiTilesProps {
  netWorthMinor: number;
  monthExpenseMinor: number;
  monthIncomeMinor: number;
}

// Spending as a whole percent of income, rounded half up in integer paise. Null when no income is recorded.
export function spendPercentOfIncome(expenseMinor: number, incomeMinor: number): number | null {
  if (incomeMinor <= 0) {
    return null;
  }
  // Refunds can make a month's net spending negative; that reads as 0%, never a negative share.
  const spentMinor = Math.max(0, expenseMinor);
  return Math.floor((spentMinor * BP_PER_PERCENT + Math.floor(incomeMinor / 2)) / incomeMinor);
}

export function spendingContext(expenseMinor: number, incomeMinor: number): string {
  const percent = spendPercentOfIncome(expenseMinor, incomeMinor);
  if (percent === null) {
    return "No income recorded this month yet";
  }
  return `${percent}% of this month's income`;
}

// Income minus spending: "Saved" when it is zero or more, "Overspent" when it is less.
export function savingsContext(expenseMinor: number, incomeMinor: number): string {
  const difference = incomeMinor - expenseMinor;
  return difference < 0 ? `Overspent ${formatMinor(-difference)}` : `Saved ${formatMinor(difference)}`;
}

// Three equal tiles: label, amount, and one line of context computed from the dashboard summary only.
export function KpiTiles({ netWorthMinor, monthExpenseMinor, monthIncomeMinor }: KpiTilesProps) {
  return (
    <dl className="kpi-grid">
      <KpiTile label="Net Worth" value={formatMinor(netWorthMinor)} />
      <KpiTile
        label="This Month's Spending"
        value={formatMinor(monthExpenseMinor)}
        context={spendingContext(monthExpenseMinor, monthIncomeMinor)}
      />
      <KpiTile
        label="This Month's Income"
        value={formatMinor(monthIncomeMinor)}
        context={savingsContext(monthExpenseMinor, monthIncomeMinor)}
      />
    </dl>
  );
}

interface KpiTileProps {
  label: string;
  value: string;
  context?: string;
}

function KpiTile({ label, value, context }: KpiTileProps) {
  return (
    <div className="card kpi-tile">
      <dt className="eyebrow">{label}</dt>
      <dd className="kpi-value num">{value}</dd>
      {context === undefined ? null : <dd className="footnote kpi-context">{context}</dd>}
    </div>
  );
}

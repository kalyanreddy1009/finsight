import type { Budget, BudgetCategory } from "../../api/budgets";
import { Button } from "../../components/Button";
import { formatMinor } from "../../lib/money";
import { ProgressBar } from "./ProgressBar";
import { limitStatusFor, statusWordsFor, usedPercent } from "./planFormat";

interface BudgetSummaryProps {
  budget: Budget;
  canEdit: boolean;
  onEdit: () => void;
  onRemove: () => void;
}

export function BudgetSummary({ budget, canEdit, onEdit, onRemove }: BudgetSummaryProps) {
  const overBy = budget.spent_minor - budget.total_limit_minor;
  return (
    <div className="plan-budget">
      <p className="plan-amount-line">
        {formatMinor(budget.spent_minor)} spent of {formatMinor(budget.total_limit_minor)}
      </p>
      <ProgressBar label="Budget used" percent={usedPercent(budget.spent_minor, budget.total_limit_minor)} />
      {overBy > 0 ? <p className="plan-status">{formatMinor(overBy)} over budget</p> : null}
      {budget.categories.length > 0 ? (
        <ul className="row-list">
          {budget.categories.map((category) => (
            <BudgetCategoryRow key={category.category_id} category={category} />
          ))}
        </ul>
      ) : null}
      <div className="plan-row-actions">
        <Button onClick={onEdit} disabled={!canEdit}>
          Edit Budget
        </Button>
        <Button variant="plain" onClick={onRemove}>
          Remove Budget
        </Button>
      </div>
    </div>
  );
}

function BudgetCategoryRow({ category }: { category: BudgetCategory }) {
  const status = limitStatusFor(category.spent_minor, category.limit_minor, category.alert_threshold_pct);
  const words = statusWordsFor(status);
  return (
    <li className="row plan-item-row">
      <div className="row-main">
        <span className="row-title">{category.category_name}</span>
        <span className="secondary-text">
          {formatMinor(category.spent_minor)} of {formatMinor(category.limit_minor)}
        </span>
        <ProgressBar label={`${category.category_name} used`} percent={usedPercent(category.spent_minor, category.limit_minor)} />
      </div>
      {words !== null ? <span className="plan-status">{words}</span> : null}
    </li>
  );
}

import { useState } from "react";
import type { Category } from "../../api/types";
import { Button } from "../../components/Button";
import { monthKeyOf, monthLabel, shiftMonth } from "./planFormat";
import { BudgetBody } from "./BudgetBody";

interface BudgetSectionProps {
  // null while the categories are still loading.
  categories: readonly Category[] | null;
}

// Month navigation lives here; BudgetBody is keyed by month so each month loads on its own.
export function BudgetSection({ categories }: BudgetSectionProps) {
  const [month, setMonth] = useState(() => monthKeyOf(new Date()));
  return (
    <section className="plan-section" aria-labelledby="budget-heading">
      <div className="plan-section-header">
        <h2 id="budget-heading" className="plan-section-title">
          Budget
        </h2>
        <div className="plan-month-nav">
          <Button variant="plain" aria-label="Previous month" onClick={() => setMonth(shiftMonth(month, -1))}>
            Previous month
          </Button>
          <span className="plan-month-name">{monthLabel(month)}</span>
          <Button variant="plain" aria-label="Next month" onClick={() => setMonth(shiftMonth(month, 1))}>
            Next month
          </Button>
        </div>
      </div>
      <BudgetBody key={month} month={month} categories={categories} />
    </section>
  );
}

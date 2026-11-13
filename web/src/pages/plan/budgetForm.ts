import type { Budget, BudgetBody, BudgetCategory, BudgetCategoryBody } from "../../api/budgets";
import type { Category } from "../../api/types";
import { formatMinor, parseRupeesToMinor } from "../../lib/money";
import { minorToRupeesText } from "../accounts/format";

// Rupee text per field. Category keys are category ids; a blank value means no limit.
export interface BudgetFormValues {
  total: string;
  categories: Record<string, string>;
}

export interface BudgetFormErrors {
  totalError: string | null;
  categoryErrors: Record<string, string>;
}

export interface BudgetFormResult extends BudgetFormErrors {
  body: BudgetBody | null;
}

const TOTAL_ERROR = "Enter the total limit in rupees, such as 25000 or 25,000.50.";
const TOTAL_ZERO_ERROR = "Enter a total limit above ₹0.00.";
const CATEGORY_ERROR = "Enter the limit in rupees, such as 5000. Leave it blank for no limit.";
const CATEGORY_ZERO_ERROR = "Enter a limit above ₹0, or leave it blank.";

export function expenseCategoriesOf(categories: readonly Category[]): Category[] {
  return categories.filter((category) => category.category_type === "EXPENSE");
}

export function budgetFormFor(budget: Budget | null, expenses: readonly Category[]): BudgetFormValues {
  const categories: Record<string, string> = {};
  for (const category of expenses) {
    const existing = budget?.categories.find((line) => line.category_id === category.id);
    categories[category.id] = existing ? minorToRupeesText(existing.limit_minor) : "";
  }
  return { total: budget ? minorToRupeesText(budget.total_limit_minor) : "", categories };
}

function totalProblem(total: number | null): string | null {
  if (total === null) {
    return TOTAL_ERROR;
  }
  return total > 0 ? null : TOTAL_ZERO_ERROR;
}

// A line keeps the alert threshold the budget already has, so saving never resets it.
function lineFor(categoryId: string, limit: number, existing: readonly BudgetCategory[]): BudgetCategoryBody {
  const threshold = existing.find((line) => line.category_id === categoryId)?.alert_threshold_pct;
  return threshold === undefined
    ? { category_id: categoryId, limit_minor: limit }
    : { category_id: categoryId, limit_minor: limit, alert_threshold_pct: threshold };
}

// Reads one limit per expense category that has a value. Invalid entries get an error.
function readCategoryLimits(
  values: BudgetFormValues,
  expenses: readonly Category[],
  existing: readonly BudgetCategory[],
): { lines: BudgetCategoryBody[]; errors: Record<string, string> } {
  const lines: BudgetCategoryBody[] = [];
  const errors: Record<string, string> = {};
  for (const category of expenses) {
    const text = (values.categories[category.id] ?? "").trim();
    if (text === "") {
      continue;
    }
    const limit = parseRupeesToMinor(text);
    if (limit === null) {
      errors[category.id] = CATEGORY_ERROR;
    } else if (limit <= 0) {
      errors[category.id] = CATEGORY_ZERO_ERROR;
    } else {
      lines.push(lineFor(category.id, limit, existing));
    }
  }
  return { lines, errors };
}

// Budget lines for categories outside the loaded spending list are kept exactly as they are.
function preservedLines(existing: readonly BudgetCategory[], expenses: readonly Category[]): BudgetCategoryBody[] {
  const expenseIds = new Set(expenses.map((category) => category.id));
  return existing
    .filter((line) => !expenseIds.has(line.category_id))
    .map((line) => ({ category_id: line.category_id, limit_minor: line.limit_minor, alert_threshold_pct: line.alert_threshold_pct }));
}

function sumOfLimits(lines: readonly BudgetCategoryBody[]): number {
  return lines.reduce((sum, line) => sum + line.limit_minor, 0);
}

// Category limits must not add up to more than the total. That message is attached to the total field.
export function validateBudgetForm(
  values: BudgetFormValues,
  expenses: readonly Category[],
  existing: readonly BudgetCategory[],
): BudgetFormResult {
  const total = parseRupeesToMinor(values.total.trim());
  const { lines, errors } = readCategoryLimits(values, expenses, existing);
  const totalMessage = totalProblem(total);
  if (total === null || totalMessage !== null) {
    return { totalError: totalMessage, categoryErrors: errors, body: null };
  }
  if (Object.keys(errors).length > 0) {
    return { totalError: null, categoryErrors: errors, body: null };
  }
  const allLines = [...lines, ...preservedLines(existing, expenses)];
  const categorySum = sumOfLimits(allLines);
  if (categorySum > total) {
    const message = `Category limits add up to ${formatMinor(categorySum)}, which is more than the total of ${formatMinor(total)}. Lower a category limit or raise the total.`;
    return { totalError: message, categoryErrors: {}, body: null };
  }
  return { totalError: null, categoryErrors: {}, body: { total_limit_minor: total, categories: allLines } };
}

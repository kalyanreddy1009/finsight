import { describe, expect, it } from "vitest";
import type { Budget } from "../../api/budgets";
import type { Goal } from "../../api/goals";
import type { RecurringRule } from "../../api/recurring";
import type { Category } from "../../api/types";
import { budgetFormFor, expenseCategoriesOf, validateBudgetForm } from "./budgetForm";
import { emptyBillForm, groupBills, validateBillForm } from "./billForm";
import { goalCreateBody, goalFormFor, goalPatchBody, LOCKED_OVER_TARGET_ERROR, validateGoalForm } from "./goalForm";

function categoryFixture(id: string, name: string, type: Category["category_type"]): Category {
  return {
    id,
    name,
    parent_category_id: null,
    category_type: type,
    default_tax_section: "NONE",
    is_discretionary: true,
    is_sensitive_private: false,
    is_system_category: false,
    created_at: "2026-01-01T00:00:00Z",
  };
}

const expenses = [categoryFixture("food", "Food", "EXPENSE"), categoryFixture("rent", "Rent", "EXPENSE")];
const mixed = [...expenses, categoryFixture("salary", "Salary", "INCOME")];

describe("budget form", () => {
  it("keeps only spending categories", () => {
    expect(expenseCategoriesOf(mixed).map((category) => category.id)).toEqual(["food", "rent"]);
  });

  it("converts rupee text to integer paise in the body", () => {
    const result = validateBudgetForm({ total: "50000.50", categories: { food: "1,000", rent: "" } }, expenses, []);
    expect(result.body).toEqual({ total_limit_minor: 5000050, categories: [{ category_id: "food", limit_minor: 100000 }] });
    expect(result.totalError).toBeNull();
  });

  it("blocks when the category limits add up to more than the total", () => {
    const result = validateBudgetForm({ total: "1000", categories: { food: "600", rent: "500" } }, expenses, []);
    expect(result.body).toBeNull();
    expect(result.totalError).toBe(
      "Category limits add up to ₹1,100.00, which is more than the total of ₹1,000.00. Lower a category limit or raise the total.",
    );
  });

  it("asks for a total and rejects a zero total", () => {
    expect(validateBudgetForm({ total: "", categories: {} }, expenses, []).totalError).toMatch(/Enter the total limit/);
    expect(validateBudgetForm({ total: "0", categories: {} }, expenses, []).totalError).toBe("Enter a total limit above ₹0.00.");
  });

  it("flags a category limit that is not rupee text", () => {
    const result = validateBudgetForm({ total: "1000", categories: { food: "abc" } }, expenses, []);
    expect(result.body).toBeNull();
    expect(result.categoryErrors.food).toMatch(/Enter the limit in rupees/);
  });

  it("prefills from the saved budget in rupees", () => {
    const budget = {
      id: "b1",
      name: "November",
      period_month: "2026-11",
      total_limit_minor: 5000000,
      spent_minor: 0,
      categories: [{ category_id: "food", category_name: "Food", limit_minor: 1000050, alert_threshold_pct: 80, spent_minor: 0 }],
    } satisfies Budget;
    expect(budgetFormFor(budget, expenses)).toEqual({ total: "50000.00", categories: { food: "10000.50", rent: "" } });
  });

  it("rejects a category limit of zero, which the API refuses", () => {
    const result = validateBudgetForm({ total: "1000", categories: { food: "0" } }, expenses, []);
    expect(result.body).toBeNull();
    expect(result.categoryErrors.food).toBe("Enter a limit above ₹0, or leave it blank.");
  });

  it("keeps categories outside the spending list and each saved threshold", () => {
    const existing = [
      { category_id: "food", category_name: "Food", limit_minor: 100000, alert_threshold_pct: 75, spent_minor: 0 },
      { category_id: "fun", category_name: "Fun", limit_minor: 20000, alert_threshold_pct: 90, spent_minor: 0 },
    ];
    const result = validateBudgetForm({ total: "5000", categories: { food: "1200" } }, expenses, existing);
    expect(result.body).toEqual({
      total_limit_minor: 500000,
      categories: [
        { category_id: "food", limit_minor: 120000, alert_threshold_pct: 75 },
        { category_id: "fun", limit_minor: 20000, alert_threshold_pct: 90 },
      ],
    });
  });

  it("counts a kept category toward the total", () => {
    const existing = [{ category_id: "fun", category_name: "Fun", limit_minor: 400000, alert_threshold_pct: 80, spent_minor: 0 }];
    const result = validateBudgetForm({ total: "3000", categories: { food: "2000" } }, expenses, existing);
    expect(result.body).toBeNull();
    expect(result.totalError).toMatch(/add up to ₹6,000.00/);
  });
});

describe("bill form", () => {
  const values = {
    merchant: "  Electricity ",
    amount: "1,250.50",
    categoryId: "food",
    frequency: "MONTHLY" as const,
    nextDate: "2026-12-01",
    mandatory: true,
  };

  it("builds the POST body in paise", () => {
    expect(validateBillForm(values).body).toEqual({
      merchant_name: "Electricity",
      category_id: "food",
      expected_amount_minor: 125050,
      frequency: "MONTHLY",
      next_expected_date: "2026-12-01",
      is_mandatory: true,
    });
  });

  it("reports each missing field", () => {
    const result = validateBillForm({ ...emptyBillForm("", "2026-12-01"), merchant: " ", amount: "0" });
    expect(result.body).toBeNull();
    expect(result.errors.merchant).toBe("Enter the merchant or payee name.");
    expect(result.errors.amount).toMatch(/Enter an amount above/);
    expect(result.errors.category).toBe("Choose a spending category.");
  });

  it("sorts active bills by next date and lists paused ones apart", () => {
    const rule = (id: string, date: string, active: boolean) =>
      ({ id, merchant_name: id, next_expected_date: date, is_active: active }) as RecurringRule;
    const groups = groupBills([rule("late", "2026-12-05", true), rule("paused", "2026-11-01", false), rule("early", "2026-11-18", true)]);
    expect(groups.active.map((item) => item.id)).toEqual(["early", "late"]);
    expect(groups.paused.map((item) => item.id)).toEqual(["paused"]);
  });
});

describe("goal form", () => {
  const values = { name: " Car ", target: "5,00,000", locked: "", monthly: "10000", targetDate: "", status: "ACTIVE" as const };

  it("treats blank amounts as zero and omits the target date from the POST body", () => {
    const result = validateGoalForm(values);
    expect(result.fields).not.toBeNull();
    expect(goalCreateBody(result.fields!)).toEqual({
      name: "Car",
      target_amount_minor: 50000000,
      current_locked_amount_minor: 0,
      monthly_contribution_minor: 1000000,
    });
  });

  it("sends a cleared target date as null in the PATCH body", () => {
    const result = validateGoalForm(values);
    expect(goalPatchBody(result.fields!)).toMatchObject({ target_date: null, status: "ACTIVE" });
  });

  it("rejects a target of zero", () => {
    const result = validateGoalForm({ ...values, target: "0" });
    expect(result.fields).toBeNull();
    expect(result.errors.target).toBe("Enter a target above ₹0.00, such as 100000.");
  });

  it("blocks when the amount set aside is more than the target", () => {
    const result = validateGoalForm({ ...values, locked: "600000" });
    expect(result.fields).toBeNull();
    expect(result.errors.locked).toBe(LOCKED_OVER_TARGET_ERROR);
  });

  it("prefills an existing goal in rupees", () => {
    const goal = {
      id: "g1",
      name: "Fund",
      target_amount_minor: 30000000,
      current_locked_amount_minor: 1500050,
      monthly_contribution_minor: 0,
      target_date: "2027-03-31",
      status: "PAUSED",
    } as Goal;
    expect(goalFormFor(goal)).toMatchObject({ target: "300000.00", locked: "15000.50", targetDate: "2027-03-31", status: "PAUSED" });
  });
});
